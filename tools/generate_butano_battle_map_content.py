#!/usr/bin/env python3
"""Generate fixed-capacity Butano battle-map collision content from the ROM."""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path
from typing import Any, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.extract_tileset import lz77_decompress, read_map_entries


EXPECTED_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
DISTANCE_RECORDS_ADDRESS = 0x0853F888
DISTANCE_RECORD_COUNT = 8
DISTANCE_RECORD_SIZE = 16
MAP_23_DISTANCE_LOOKUP_ADDRESS = 0x08541008
MAP_24_DISTANCE_LOOKUP_ADDRESS = 0x08541107


def load_map_content(root: Path) -> list[dict[str, Any]]:
    rom_path = root / "rom" / "base.gba"
    rom = rom_path.read_bytes()
    digest = hashlib.sha256(rom).hexdigest()
    if digest != EXPECTED_ROM_SHA256:
        raise ValueError(f"ROM SHA-256 mismatch: {digest}")

    maps: list[dict[str, Any]] = []
    for entry in read_map_entries(rom):
        width = entry["width_tiles"] >> 2
        height = entry["height_tiles"] >> 1
        collision = lz77_decompress(rom, entry["collision_grid_ptr"])
        cell_count = width * height
        if len(collision) != cell_count * 2:
            raise ValueError(
                f"map {entry['map_id']} collision size does not match dimensions"
            )
        cells = list(struct.unpack(f"<{cell_count}H", collision))
        distance_record_offset = (
            DISTANCE_RECORDS_ADDRESS
            - 0x08000000
            + entry["map_id"] * DISTANCE_RECORD_COUNT * DISTANCE_RECORD_SIZE
        )
        distance_records = [
            rom[
                distance_record_offset
                + record_index * DISTANCE_RECORD_SIZE:
                distance_record_offset
                + (record_index + 1) * DISTANCE_RECORD_SIZE
            ]
            for record_index in range(DISTANCE_RECORD_COUNT)
        ]
        maps.append(
            {
                "battle_id": entry["map_id"],
                "width": width,
                "height": height,
                "cells": cells,
                "distance_records": distance_records,
            }
        )
    if [row["battle_id"] for row in maps] != list(range(47)):
        raise ValueError("battle map IDs must be contiguous from 0 through 46")
    map_23_lookup_offset = MAP_23_DISTANCE_LOOKUP_ADDRESS - 0x08000000
    map_24_lookup_offset = MAP_24_DISTANCE_LOOKUP_ADDRESS - 0x08000000
    maps[23]["distance_lookup"] = rom[
        map_23_lookup_offset:
        map_23_lookup_offset + maps[23]["width"] * maps[23]["height"]
    ]
    maps[24]["distance_lookup"] = rom[
        map_24_lookup_offset:
        map_24_lookup_offset + maps[24]["width"] * maps[24]["height"]
    ]
    return maps


def generate_header(maps: list[dict[str, Any]]) -> str:
    definitions: list[str] = []
    rendered_cells: list[str] = []
    rendered_distance_records: list[str] = []
    offset = 0
    for expected_id, row in enumerate(maps):
        if row["battle_id"] != expected_id:
            raise ValueError("battle map IDs must be contiguous")
        cells = row["cells"]
        expected_count = row["width"] * row["height"]
        if len(cells) != expected_count:
            raise ValueError(f"battle map {expected_id} cell count mismatch")
        definitions.append(
            "battle_map_definition{ "
            f"{expected_id}, {row['width']}, {row['height']}, {offset}, {len(cells)}"
            " }"
        )
        rendered_cells.extend(
            f"battle_map_cell{{ 0x{cell:04X} }}" for cell in cells
        )
        distance_records = row["distance_records"]
        if len(distance_records) != DISTANCE_RECORD_COUNT:
            raise ValueError(
                f"battle map {expected_id} distance record count mismatch"
            )
        for record in distance_records:
            if len(record) != DISTANCE_RECORD_SIZE:
                raise ValueError(
                    f"battle map {expected_id} distance record size mismatch"
                )
            rendered_distance_records.append(
                "battle_map_distance_record{ { "
                + ", ".join(f"0x{value:02X}" for value in record)
                + " } }"
            )
        offset += len(cells)

    definition_body = ",\n    ".join(definitions)
    cell_body = ",\n    ".join(rendered_cells)
    distance_record_body = ",\n    ".join(rendered_distance_records)
    map_23_lookup_size = maps[23]["width"] * maps[23]["height"]
    map_24_lookup_size = maps[24]["width"] * maps[24]["height"]
    map_23_lookup = maps[23]["distance_lookup"]
    map_24_lookup = maps[24]["distance_lookup"]
    if len(map_23_lookup) != map_23_lookup_size:
        raise ValueError("battle map 23 distance lookup size mismatch")
    if len(map_24_lookup) != map_24_lookup_size:
        raise ValueError("battle map 24 distance lookup size mismatch")
    map_23_lookup_body = ", ".join(f"0x{value:02X}" for value in map_23_lookup)
    map_24_lookup_body = ", ".join(f"0x{value:02X}" for value in map_24_lookup)
    return f"""// Generated by tools/generate_butano_battle_map_content.py. Do not edit.
#ifndef KONOHA_GENERATED_BATTLE_MAP_CONTENT_H
#define KONOHA_GENERATED_BATTLE_MAP_CONTENT_H

#include "konoha/battle_map_content.h"

#include <array>

namespace konoha
{{

inline constexpr std::array<battle_map_definition, {len(definitions)}>
        battle_map_definitions = {{{{
    {definition_body}
}}}};

inline constexpr std::array<battle_map_cell, {len(rendered_cells)}>
        battle_map_cells = {{{{
    {cell_body}
}}}};

inline constexpr std::array<battle_map_distance_record, {len(rendered_distance_records)}>
        battle_map_distance_records = {{{{
    {distance_record_body}
}}}};

inline constexpr std::array<std::uint8_t, {map_23_lookup_size}>
        battle_map_23_distance_lookup = {{{{
    {map_23_lookup_body}
}}}};

inline constexpr std::array<std::uint8_t, {map_24_lookup_size}>
        battle_map_24_distance_lookup = {{{{
    {map_24_lookup_body}
}}}};

[[nodiscard]] inline constexpr const battle_map_definition*
battle_map_definition_for(int battle_id)
{{
    if(battle_id < 0 ||
            battle_id >= static_cast<int>(
                    battle_map_definitions.size()))
    {{
        return nullptr;
    }}
    const battle_map_definition& definition =
            battle_map_definitions[
                    static_cast<std::size_t>(battle_id)];
    return definition.battle_id == battle_id ?
            &definition : nullptr;
}}

[[nodiscard]] inline constexpr const battle_map_distance_record*
battle_map_distance_records_for(int battle_id)
{{
    if(battle_id < 0 ||
            battle_id >= static_cast<int>(
                    battle_map_definitions.size()))
    {{
        return nullptr;
    }}
    return &battle_map_distance_records[
            static_cast<std::size_t>(
                    battle_id * {DISTANCE_RECORD_COUNT})];
}}

[[nodiscard]] inline constexpr const battle_map_cell* battle_map_cell_at(
        const battle_map_definition& definition, int x, int y)
{{
    if(! definition.contains(x, y))
    {{
        return nullptr;
    }}
    const std::size_t index = static_cast<std::size_t>(
            definition.cell_offset + y * definition.width + x);
    return index < battle_map_cells.size() ? &battle_map_cells[index] : nullptr;
}}

}}

#endif
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "butano-sequel/game/include/konoha/generated_battle_map_content.h"
        ),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output
    if not output.is_absolute():
        output = root / output
    maps = load_map_content(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generate_header(maps), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
