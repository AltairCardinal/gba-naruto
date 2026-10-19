#!/usr/bin/env python3
"""Extract hash-gated evidence for battle-map collision and occupancy words."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.extract_tileset import lz77_decompress, read_map_entries


ROM_BASE = 0x08000000
EXPECTED_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
FUNCTIONS = {
    "consumer": (
        0x080698B4,
        0x08069D1C,
        "143a7223550ccd44c69615b39e76fc2f96e7ba4ec62671a9ff6de62adaa844aa",
    ),
    "path_setup": (
        0x08069D1C,
        0x08069DB8,
        "7a33e919213bcd0f218293306f08587dd642414fb5f99e0da9147febcf0579be",
    ),
    "traversal_configuration": (
        0x08069DB8,
        0x08069E44,
        "415a0f9cb1ab184f6b40d257a82905abb4201c7a2d8723621624ecbf2bf786fb",
    ),
    "occupancy_set": (
        0x0806A9EC,
        0x0806AA2A,
        "d6806b36d847701cca41569f8bb189e46d531090dfdbdd4443a9b7e87c81f9a5",
    ),
    "occupancy_clear": (
        0x0806AA38,
        0x0806AA58,
        "a4c090b88b422af9a960b0593f9afbea83f557ec07e04afe5652f7a9c6d93a73",
    ),
}
EXPECTED_HALFWORDS = {
    0x080698E0: 0x2001,
    0x080698EA: 0x2002,
    0x0806990C: 0x2004,
    0x08069928: 0x2008,
    0x08069B54: 0x2E01,
    0x08069B5C: 0x2E00,
    0x08069B68: 0x2E02,
    0x08069B6C: 0x2E03,
    0x08069C0E: 0x200F,
}
EXPECTED_LITERALS = {
    0x08069904: 0x02021E2C,
    0x0806AA2C: 0x020240C0,
    0x0806AA30: 0x02021E2C,
    0x0806AA34: 0x0201BE2A,
    0x0806AA58: 0x02021E2C,
    0x0806AA5C: 0x0201BE2A,
    0x0806AA60: 0x000007FF,
}


def _slice(rom: bytes, start: int, end: int) -> bytes:
    if not ROM_BASE <= start <= end <= ROM_BASE + len(rom):
        raise ValueError("collision function range is outside the mapped ROM")
    return rom[start - ROM_BASE : end - ROM_BASE]


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, address - ROM_BASE)[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, address - ROM_BASE)[0]


def analyze_collision_runtime(rom_path: Path | str) -> dict[str, object]:
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()
    digest = hashlib.sha256(rom).hexdigest()
    if digest != EXPECTED_ROM_SHA256:
        raise ValueError(f"ROM SHA-256 mismatch: {digest}")

    functions: dict[str, object] = {}
    for name, (start, end, expected_hash) in FUNCTIONS.items():
        blob = _slice(rom, start, end)
        actual_hash = hashlib.sha256(blob).hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f"{name} function SHA-256 mismatch")
        functions[name] = {
            "start": f"0x{start:08X}",
            "end": f"0x{end:08X}",
            "sha256": actual_hash,
        }
    for address, expected in EXPECTED_HALFWORDS.items():
        if _u16(rom, address) != expected:
            raise ValueError(f"collision opcode mismatch at 0x{address:08X}")
    for address, expected in EXPECTED_LITERALS.items():
        if _u32(rom, address) != expected:
            raise ValueError(f"collision literal mismatch at 0x{address:08X}")

    maps: list[dict[str, object]] = []
    for entry in read_map_entries(rom):
        width = entry["width_tiles"] >> 2
        height = entry["height_tiles"] >> 1
        collision = lz77_decompress(rom, entry["collision_grid_ptr"])
        expected_size = width * height * 2
        if len(collision) != expected_size:
            raise ValueError(
                f"map {entry['map_id']} collision size {len(collision)} != {expected_size}"
            )
        words = struct.unpack(f"<{width * height}H", collision)
        low_nibbles = [word & 0xF for word in words]
        counts = Counter(low_nibbles)
        maps.append(
            {
                "battle_id": entry["map_id"],
                "width": width,
                "height": height,
                "cell_count": len(words),
                "sha256": hashlib.sha256(collision).hexdigest(),
                "low_nibble_values": sorted(counts),
                "low_nibble_counts": {
                    str(value): counts[value] for value in sorted(counts)
                },
            }
        )

    return {
        "schema_version": 2,
        "identity": "battle_map_collision_runtime",
        "rom": {
            "path": str(rom_path),
            "sha256": digest,
        },
        "functions": functions,
        "consumer": {
            "function": "0x080698B4",
            "terrain_class_switch": "0x08069B54",
            "path_setup": "0x08069D1C",
            "traversal_configuration": "0x08069DB8",
            "collision_buffer": "0x02021E2C",
            "map_width": "0x0201BE2A",
            "map_height": "0x0201BE2B",
        },
        "terrain": {
            "classes": {
                "normal": 0,
                "passive_0x1A": 1,
                "passive_0x1C": 3,
                "passive_0x1B": 7,
                "blocked": 15,
            },
            "traversal_limit_targets": {
                "1": "0x1A",
                "3": "0x1C",
                "7": "0x1B",
            },
            "fully_closed": 15,
            "boundary": (
                "The low nibble is a terrain class, not four independent direction "
                "bits. A path consumes one matching class budget for every visited "
                "tile, including its origin; recursive backtracking restores the "
                "budget for sibling paths. Classes 1, 3, and 7 receive budgets from "
                "passive targets 0x1A, 0x1C, and 0x1B respectively, while 0xF is "
                "always blocked. Values 2 and 4 occur only on map 0 in the extracted "
                "content and are not assigned a traversal passive by this consumer."
            ),
        },
        "occupancy": {
            "unit_slot_shift": 11,
            "unit_slot_mask": "0x7800",
            "side_shift": 15,
            "side_mask": "0x8000",
            "terrain_mask": "0x000F",
        },
        "maps": maps,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, nargs="?", default=Path("rom/base.gba"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-map-collision-semantics-20260724.json"),
    )
    args = parser.parse_args(argv)
    result = analyze_collision_runtime(args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
