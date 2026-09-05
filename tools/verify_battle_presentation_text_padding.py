#!/usr/bin/env python3
"""Verify zero gaps between fixed battle-presentation message records."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
MANIFEST = Path("artifacts/battle-presentation-glyphs-v1/manifest.json")
MANIFEST_SHA256 = "ecc44fde0d886b75397d34181112f5b86dbb791b09e3b85797e9b4013f4e74a7"
POINTER_TABLE_START = 0x5A2B08
POINTER_COUNT = 79


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rebuild_battle_presentation_text_padding(
    root: Path, rom: bytes
) -> dict[str, Any]:
    ranges: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        root = Path(root).resolve(strict=True)
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("ROM identity changed")
        raw_manifest = (root / MANIFEST).read_bytes()
        if _sha(raw_manifest) != MANIFEST_SHA256:
            raise ValueError("battle-presentation manifest identity changed")
        manifest = json.loads(raw_manifest)
        if len(manifest["messages"]) != POINTER_COUNT:
            raise ValueError("battle-presentation message denominator changed")
        table_end = POINTER_TABLE_START + POINTER_COUNT * 4
        pointers = struct.unpack_from(f"<{POINTER_COUNT}I", rom, POINTER_TABLE_START)
        starts = [pointer - ROM_BASE for pointer in pointers]
        if starts != sorted(starts) or len(set(starts)) != POINTER_COUNT:
            raise ValueError("battle-presentation pointer order changed")
        records = []
        for index, start in enumerate(starts):
            if not 0 <= start < POINTER_TABLE_START:
                raise ValueError("battle-presentation message pointer changed")
            try:
                end = rom.index(b"\0", start, POINTER_TABLE_START) + 1
            except ValueError as error:
                raise ValueError("battle-presentation message terminator changed") from error
            records.append((start, end))
        for index, ((_, left_end), (right_start, _)) in enumerate(
            zip(records, records[1:])
        ):
            if left_end >= right_start:
                raise ValueError("battle-presentation message ranges overlap")
            gap = rom[left_end:right_start]
            if any(gap):
                raise ValueError("battle-presentation inter-record gap changed")
            ranges.append(
                {
                    "range": [left_end, right_start],
                    "size": right_start - left_end,
                    "bytes_sha256": _sha(gap),
                    "after_message_id": index,
                }
            )
        if len(ranges) != 78 or sum(item["size"] for item in ranges) != 1_293:
            raise ValueError("battle-presentation zero-gap denominator changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": "battle-presentation-text-padding-verification-v1",
        "verified": not errors,
        "errors": errors,
        "padding_range_count": len(ranges),
        "padding_bytes": sum(item["size"] for item in ranges),
        "zero_byte_count": sum(item["size"] for item in ranges),
        "ranges": ranges,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    rom_path = args.rom if args.rom.is_absolute() else root / args.rom
    report = rebuild_battle_presentation_text_padding(root, rom_path.read_bytes())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
