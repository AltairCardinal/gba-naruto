#!/usr/bin/env python3
"""Verify that tracked .ss9 files are mGBA PNG containers with GBA state data."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.inspect_mgba_savestate import _validated_png_chunks, load_gba_state


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIRECTORY = ROOT / "artifacts/runtime-checkpoints"


def verify_checkpoints(directory: Path) -> dict[str, Any]:
    directory = Path(directory).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("runtime checkpoint path must be a directory")

    checkpoints = sorted(directory.glob("*.ss9"))
    errors: list[str] = []
    valid_count = 0
    plain_png_count = 0
    invalid_count = 0
    versions: Counter[str] = Counter()
    saved_pcs: Counter[str] = Counter()

    for checkpoint in checkpoints:
        label = checkpoint.name
        if checkpoint.is_symlink():
            invalid_count += 1
            errors.append(f"{label}: symlink checkpoint is not allowed")
            continue
        try:
            chunks = _validated_png_chunks(checkpoint.read_bytes())
        except (OSError, ValueError) as error:
            invalid_count += 1
            errors.append(f"{label}: invalid PNG container: {error}")
            continue

        state_chunks = [payload for tag, payload in chunks if tag == b"gbAs"]
        if not state_chunks:
            plain_png_count += 1
            errors.append(f"{label}: missing gbAs state chunk; file is a plain PNG")
            continue
        try:
            state = load_gba_state(checkpoint)
        except (OSError, ValueError) as error:
            invalid_count += 1
            errors.append(f"{label}: invalid mGBA state: {error}")
            continue

        valid_count += 1
        versions[f"0x{state.version_magic:08X}"] += 1
        saved_pcs[f"0x{state.registers[15]:08X}"] += 1

    if not checkpoints:
        errors.append("runtime checkpoint directory contains no .ss9 files")

    return {
        "verified": not errors,
        "errors": errors,
        "checkpoint_count": len(checkpoints),
        "valid_mgba_state_count": valid_count,
        "plain_png_count": plain_png_count,
        "invalid_count": invalid_count,
        "version_counts": dict(sorted(versions.items())),
        "saved_pc_counts": dict(sorted(saved_pcs.items())),
        "scope": {
            "png_crc_validated": True,
            "exactly_one_gbas_required": True,
            "gbas_zlib_and_size_validated": True,
            "gba_version_magic_validated": True,
            "runtime_semantics_reverified": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    result = verify_checkpoints(args.directory)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
