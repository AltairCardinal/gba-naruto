#!/usr/bin/env python3
"""Verify zero gaps between adjacent fixed SJIS font source extents."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
MANIFEST = Path("artifacts/dialogue-font-v2/manifest.json")
MANIFEST_SHA256 = "818684d7533ae44bbe4f56b4b6df9a6d6f69612a43ae041dfb5a7b0b0698e69c"
MAX_NEAR_GAP_SIZE = 2_048


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _offset(pointer: object) -> int:
    if not isinstance(pointer, str) or not pointer.startswith("0x"):
        raise ValueError("dialogue font source pointer changed")
    offset = int(pointer, 16) - ROM_BASE
    if not 0 <= offset <= ROM_SIZE:
        raise ValueError("dialogue font source pointer is outside ROM")
    return offset


def rebuild_dialogue_font_source_padding(
    root: Path, rom: bytes
) -> dict[str, Any]:
    ranges: list[dict[str, Any]] = []
    errors: list[str] = []
    excluded_nonzero_gap_count = 0
    excluded_far_gap_count = 0
    try:
        root = Path(root).resolve(strict=True)
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("ROM identity changed")
        raw = (root / MANIFEST).read_bytes()
        if _sha(raw) != MANIFEST_SHA256:
            raise ValueError("dialogue font manifest identity changed")
        entries = json.loads(raw)["sjis_entries"]
        if not isinstance(entries, list) or len(entries) != 26:
            raise ValueError("dialogue font SJIS entry denominator changed")

        for left, right in zip(entries, entries[1:]):
            start = _offset(left["source_end_pointer"])
            end = _offset(right["source_pointer"])
            if start >= end:
                continue
            size = end - start
            if size > MAX_NEAR_GAP_SIZE:
                excluded_far_gap_count += 1
                continue
            gap = rom[start:end]
            if any(gap):
                excluded_nonzero_gap_count += 1
                continue
            ranges.append(
                {
                    "range": [start, end],
                    "size": size,
                    "bytes_sha256": _sha(gap),
                    "left_entry_index": left["index"],
                    "right_entry_index": right["index"],
                }
            )

        if (
            len(ranges) != 19
            or sum(item["size"] for item in ranges) != 2_848
            or excluded_nonzero_gap_count != 1
            or excluded_far_gap_count != 1
        ):
            raise ValueError("dialogue font source-gap denominator changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))

    return {
        "schema": "dialogue-font-source-padding-verification-v1",
        "verified": not errors,
        "errors": errors,
        "padding_range_count": len(ranges),
        "padding_bytes": sum(item["size"] for item in ranges),
        "zero_byte_count": sum(item["size"] for item in ranges),
        "excluded_nonzero_gap_count": excluded_nonzero_gap_count,
        "excluded_far_gap_count": excluded_far_gap_count,
        "ranges": ranges,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    rom_path = args.rom if args.rom.is_absolute() else root / args.rom
    report = rebuild_dialogue_font_source_padding(root, rom_path.read_bytes())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
