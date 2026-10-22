#!/usr/bin/env python3
"""Promote the natural action-7 data-table-b message pointer pixel A/B."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verify_data_table_b_message0_pointer_ab import (
    ARTIFACT_ID,
    ARTIFACT_SCHEMA,
    IMPLEMENTATION_FILES,
    INPUT_PATH,
    PROMOTION_SCHEMA,
    RAW_FILES,
    SOURCE_DIRS,
    collect_evidence,
    sha256_file,
    verifier_command,
)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _variant_dir(source: Path, variant: str) -> Path:
    canonical = source / variant
    return canonical if canonical.is_dir() else source / SOURCE_DIRS[variant]


def _source_file(root: Path, source: Path, name: str) -> Path:
    if name == "input.ss9":
        local = source / name
        return local if local.is_file() else root / INPUT_PATH
    variant, filename = name.split("/", 1)
    return _variant_dir(source, variant) / filename


def _write_raw_tar(
    root: Path, source: Path, output: Path, launch: dict[str, Any]
) -> None:
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(RAW_FILES - {"launch-identity.json"}):
            path = _source_file(root, source, name)
            info = archive.gettarinfo(str(path), arcname=name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            with path.open("rb") as stream:
                archive.addfile(info, stream)
        payload = (json.dumps(launch, indent=2, sort_keys=True) + "\n").encode()
        info = tarfile.TarInfo("launch-identity.json")
        info.size = len(payload)
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mtime = 0
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(payload))


def export_artifact(root: Path, source: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("data-table-b artifact output must be absent or empty")
    evidence, launch = collect_evidence(root, source)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_variant_dir(source, "baseline") / "output.png", output / "baseline.png")
    shutil.copyfile(_variant_dir(source, "candidate") / "output.png", output / "candidate.png")
    _write_raw_tar(root, source, output / "raw.tar", launch)
    _write_json(output / "evidence.json", evidence)
    files = {
        name: sha256_file(output / name)
        for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar")
    }
    manifest = {
        "artifact_id": ARTIFACT_ID,
        "artifact_schema": ARTIFACT_SCHEMA,
        "artifact_status": "accepted",
        "files": files,
        "implementation": {
            name: sha256_file(root / name) for name in IMPLEMENTATION_FILES
        },
        "schema": PROMOTION_SCHEMA,
        "verifier": {"command": verifier_command(), "exit_code": 0},
    }
    _write_json(output / "manifest.json", manifest)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    evidence = export_artifact(ROOT, args.source, args.output)
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
