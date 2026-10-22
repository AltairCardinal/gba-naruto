#!/usr/bin/env python3
"""Verify zero alignment bytes between adjacent fixed LZ77 streams."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.export_rom_pointer_lz77_inventory import (
    ROM_SHA256,
    _aligned_rom_pointer_references,
    _parse_lz77,
    _strict_lz77_offsets,
)

ROM_SIZE = 6_291_456


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rebuild_lz77_alignment_padding(root: Path, rom: bytes) -> dict[str, Any]:
    ranges: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        Path(root).resolve(strict=True)
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("ROM identity changed")
        references = _aligned_rom_pointer_references(rom)
        offsets = sorted(
            offset
            for offset in _strict_lz77_offsets(rom)
            if offset % 4 == 0 and offset in references
        )
        if len(offsets) != 896:
            raise ValueError("aligned pointer-reachable LZ77 denominator changed")
        offset_set = set(offsets)
        for offset in offsets:
            parsed = _parse_lz77(rom, offset, materialize=False)
            if parsed is None:
                raise ValueError("fixed LZ77 stream stopped parsing")
            end, _ = parsed
            aligned_end = (end + 3) & ~3
            if aligned_end == end or aligned_end not in offset_set:
                continue
            gap = rom[end:aligned_end]
            if any(gap):
                continue
            ranges.append(
                {
                    "range": [end, aligned_end],
                    "size": aligned_end - end,
                    "bytes_sha256": _sha(gap),
                    "left_stream_offset": offset,
                    "right_stream_offset": aligned_end,
                }
            )
        if len(ranges) != 341 or sum(item["size"] for item in ranges) != 648:
            raise ValueError("LZ77 alignment padding denominator changed")
    except (OSError, ValueError, TypeError) as error:
        errors.append(str(error))
    return {
        "schema": "rom-lz77-alignment-padding-verification-v1",
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
    report = rebuild_lz77_alignment_padding(root, rom_path.read_bytes())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
