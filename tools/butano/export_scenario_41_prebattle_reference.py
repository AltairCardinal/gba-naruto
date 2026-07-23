#!/usr/bin/env python3
"""Publish the six hash-bound scenario 41 prebattle screens."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.inspect_mgba_savestate import png_screen_fingerprint  # noqa: E402


EXPECTED_RGB_SHA256 = {
    "menu-0": "bf0ffd7484bc0d4c8e2f94af623b265f8f462a891133a0bccf67f757c849d035",
    "menu-1": "1e68324b6496cda1dc4cff6821a1c6b86dbfc422ac15fdfd1bcdfd0a9246352d",
    "menu-2": "5c364baf4ff92f79916613780779b7f79fbaf44493a17fac79c0dfb1aaa67c0b",
    "menu-3": "df5eadcc5455db5b749917b79d5f3ffb27b8e204dad88d5af6fac1621bb4d1ea",
    "confirmation-yes": "0bd89a244d934a531b0fb27f902c272c34711ba2fc227d3fc8bbf13ae103d89c",
    "confirmation-no": "c49cbfd9c41b6782965246fc90df8b8ca33e13272c00fa6a83b115ffdd887b8f",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_prebattle_reference(
    sources: Mapping[str, Path], output: Path
) -> dict[str, object]:
    if list(sources) != list(EXPECTED_RGB_SHA256):
        raise ValueError("prebattle source order or names changed")
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    published = False
    try:
        screens = temporary / "screens"
        screens.mkdir()
        boundaries = {}
        for name, source_value in sources.items():
            source = Path(source_value)
            fingerprint = png_screen_fingerprint(source)
            rgb_sha256 = str(fingerprint["rgb_pixels_sha256"])
            if rgb_sha256 != EXPECTED_RGB_SHA256[name]:
                raise ValueError(f"{name} RGB SHA-256 mismatch: {rgb_sha256}")
            filename = f"{name}.png"
            shutil.copyfile(source, screens / filename)
            boundaries[name] = {
                "file": filename,
                "rgb_sha256": rgb_sha256,
                "png_sha256": _sha256(source),
                "width": fingerprint["width"],
                "height": fingerprint["height"],
            }
        manifest: dict[str, object] = {
            "schema_version": 1,
            "boundaries": boundaries,
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(output)
        published = True
        return manifest
    finally:
        if not published and temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in EXPECTED_RGB_SHA256:
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = {name: getattr(args, name.replace("-", "_")) for name in EXPECTED_RGB_SHA256}
    manifest = export_prebattle_reference(sources, args.output)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
