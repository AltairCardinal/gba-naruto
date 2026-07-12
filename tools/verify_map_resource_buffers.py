#!/usr/bin/env python3
"""Compare live GBA memory dumps with one map row's decompressed resources."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from tools.extract_tileset import lz77_decompress, read_map_entries
except ModuleNotFoundError:
    from extract_tileset import lz77_decompress, read_map_entries


def _match(actual: bytes, offset: int, expected: bytes) -> tuple[bool, dict]:
    observed = actual[offset:offset + len(expected)]
    return observed == expected, {
        "offset": offset,
        "length": len(expected),
        "expected_sha256": hashlib.sha256(expected).hexdigest(),
        "observed_sha256": hashlib.sha256(observed).hexdigest(),
    }


def verify_map_resource_buffers(
    rom: bytes, map_id: int, ewram: bytes, palette_ram: bytes, vram: bytes,
) -> dict:
    entries = read_map_entries(rom)
    if not 0 <= map_id < len(entries):
        raise ValueError(f"map_id must be 0..{len(entries) - 1}")
    if len(ewram) < 0x40000 or len(palette_ram) < 0x400 or len(vram) < 0x18000:
        raise ValueError("expected full EWRAM (0x40000), palette RAM (0x400), and VRAM (0x18000) dumps")
    entry = entries[map_id]

    def unpack(name: str) -> bytes | None:
        pointer = entry[name]
        return None if pointer is None else lz77_decompress(rom, pointer)

    details = {}
    gfx = unpack("tile_gfx_ptr")
    buffer_index = ewram[0x22E2D]
    gfx_offset = buffer_index * 0x4000
    checks = {}
    checks["tile_gfx"], details["tile_gfx"] = _match(vram, gfx_offset, gfx)

    palette = unpack("bg_palette_ptr")
    checks["bg_palette"], details["bg_palette"] = _match(palette_ram, 0, palette)

    primary = unpack("primary_layout_ptr")
    checks["primary_layout"], details["primary_layout"] = _match(ewram, 0x1BE2C, primary)

    alternate = unpack("alternate_layout_ptr")
    if alternate is None:
        checks["alternate_layout_skipped"] = True
        details["alternate_layout"] = {"pointer": 0, "expected": "skipped"}
    else:
        checks["alternate_layout"] , details["alternate_layout"] = _match(ewram, 0x1CE2C, alternate)

    metatile = unpack("metatile_attributes_ptr")
    checks["metatile_attributes"], details["metatile_attributes"] = _match(ewram, 0x1DE2C, metatile)

    collision = unpack("collision_grid_ptr")
    checks["collision_grid"], details["collision_grid"] = _match(ewram, 0x21E2C, collision)

    return {
        "schema_version": 1,
        "map_id": map_id,
        "row_file_offset": entry["file_offset"],
        "vram_buffer_index": buffer_index,
        "verified": all(checks.values()),
        "checks": checks,
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("map_id", type=int)
    parser.add_argument("ewram", type=Path, help="0x02000000, length 0x40000")
    parser.add_argument("palette_ram", type=Path, help="0x05000000, length 0x400")
    parser.add_argument("vram", type=Path, help="0x06000000, length 0x18000")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_map_resource_buffers(
        args.rom.read_bytes(), args.map_id, args.ewram.read_bytes(),
        args.palette_ram.read_bytes(), args.vram.read_bytes(),
    )
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
