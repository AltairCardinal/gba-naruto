#!/usr/bin/env python3
"""Export the static half of the generic sprite runtime asset chain.

The table at ROM file offset 0x53F140 contains definition/animation pointer
pairs, not pixel or palette pointers.  This exporter records the complete
component lists and the code-proven runtime addresses needed to capture the
eventual OBJ VRAM payload without claiming that the pixels live in this table.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAIR_TABLE_OFFSET = 0x53F140
PAIR_ENTRY_COUNT = 43
PAIR_ENTRY_SIZE = 8
TILE_OFFSET_TABLE_OFFSET = 0x53F298
TILE_OFFSET_ENTRY_SIZE = 2
COMPONENT_SIZE = 0x14
TERMINATOR = bytes.fromhex("ffff0000")

PAIR_TABLE_SHA256 = (
    "5873ae022e9b6290f876aab367b6dbe95b7a97b9b7a2f15d0861dc747196f3f8"
)
TILE_OFFSET_TABLE_SHA256 = (
    "86d57e438c3b3e9a877ebea8d910e2782c30b5bcbf8ca4f305df1deee6d231d6"
)
RESOLVED_WINDOW_0X28_SHA256 = (
    "439eb69f5ee2eadefe6fbd66b88ba27fb53c6552ac184267a803917fe8e98248"
)

CODE_SLICES = (
    {
        "name": "table_and_runtime_base_loader",
        "file_offset": 0x080B08,
        "gba_address": "0x08080B08",
        "size": 0x74,
        "sha256": "ff28fa10e4606f706a4fd4986126d8a14fe2baf66f1cc2621c5fe6b15d2ff8c2",
    },
    {
        "name": "sprite_task_allocator",
        "file_offset": 0x0625A4,
        "gba_address": "0x080625A4",
        "size": 0x10C,
        "sha256": "e238cd1ee159265fb8b718766f336f8d5462596954f93c7805d1bf33dd6b3c54",
    },
    {
        "name": "component_selector",
        "file_offset": 0x06298C,
        "gba_address": "0x0806298C",
        "size": 0x7E,
        "sha256": "722200eb6511a974b79fe00ee335f21e557cc0fc1898343a5eab4c7032e8ed2f",
    },
    {
        "name": "attr2_and_obj_vram_path",
        "file_offset": 0x063108,
        "gba_address": "0x08063108",
        "size": 0x7E,
        "sha256": "748340bb724a0fc8a4911c8879e8fb0c1152c84bac87b910cb36b3e15d790b17",
    },
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pointer(value: int) -> str:
    return f"0x{value:08X}"


def _rom_offset(pointer: int, rom_size: int) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"pointer {_pointer(pointer)} is outside the ROM")
    return offset


def _parse_component(raw: bytes, index: int) -> dict[str, Any]:
    if len(raw) != COMPONENT_SIZE:
        raise ValueError("component record is truncated")
    (
        tile_offset,
        flag_02,
        flag_03,
        horizontal_position_input,
        vertical_position_input,
        width,
        height,
        transform_factor_0c,
        transform_factor_0e,
        unknown_10_byte,
        oam_attribute_byte,
        unknown_12,
    ) = struct.unpack("<HBBhhhhhhBBH", raw)
    if tile_offset == 0xFFFF:
        raise ValueError("terminator was parsed as a component")
    if width not in (8, 16, 32, 64) or height not in (8, 16, 32, 64):
        raise ValueError(
            f"component {index} has unsupported dimensions {width}x{height}"
        )
    return {
        "index": index,
        "tile_offset": tile_offset,
        "flag_02": flag_02,
        "flag_03": flag_03,
        "horizontal_position_input": horizontal_position_input,
        "vertical_position_input": vertical_position_input,
        "width": width,
        "height": height,
        "transform_factor_0c": transform_factor_0c,
        "transform_factor_0e": transform_factor_0e,
        "unknown_10_byte": unknown_10_byte,
        "oam_attribute_byte": oam_attribute_byte,
        "unknown_12": unknown_12,
        "raw_hex": raw.hex(),
    }


def _read_component_list(
    rom: bytes,
    pointer: int,
    *,
    definition_pointer: int,
) -> tuple[list[dict[str, Any]], bytes]:
    cursor = _rom_offset(pointer, len(rom))
    definition_offset = _rom_offset(definition_pointer, len(rom))
    start = cursor
    components: list[dict[str, Any]] = []
    while cursor + 4 <= len(rom):
        if rom[cursor : cursor + 4] == TERMINATOR:
            cursor += 4
            break
        if cursor + COMPONENT_SIZE > len(rom):
            raise ValueError(f"component list at {_pointer(pointer)} is truncated")
        components.append(
            _parse_component(
                rom[cursor : cursor + COMPONENT_SIZE],
                len(components),
            )
        )
        cursor += COMPONENT_SIZE
        if len(components) > 32:
            raise ValueError(
                f"component list at {_pointer(pointer)} has no bounded terminator"
            )
    else:
        raise ValueError(f"component list at {_pointer(pointer)} has no terminator")
    if not components:
        raise ValueError(f"component list at {_pointer(pointer)} is empty")
    if cursor != definition_offset:
        raise ValueError(
            f"component list at {_pointer(pointer)} ends at "
            f"{_pointer(ROM_BASE + cursor)}, expected definition "
            f"{_pointer(definition_pointer)}"
        )
    return components, rom[start:cursor]


def build_manifest(rom: bytes) -> dict[str, Any]:
    rom_sha256 = _sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError(
            f"unexpected ROM SHA-256 {rom_sha256}; expected {ROM_SHA256}"
        )

    pair_table_size = PAIR_ENTRY_COUNT * PAIR_ENTRY_SIZE
    tile_offset_table_size = PAIR_ENTRY_COUNT * TILE_OFFSET_ENTRY_SIZE
    pair_table = rom[PAIR_TABLE_OFFSET : PAIR_TABLE_OFFSET + pair_table_size]
    tile_offset_table = rom[
        TILE_OFFSET_TABLE_OFFSET : TILE_OFFSET_TABLE_OFFSET + tile_offset_table_size
    ]
    if _sha256(pair_table) != PAIR_TABLE_SHA256:
        raise ValueError("sprite pair table SHA-256 mismatch")
    if _sha256(tile_offset_table) != TILE_OFFSET_TABLE_SHA256:
        raise ValueError("tile-offset table SHA-256 mismatch")

    entries: list[dict[str, Any]] = []
    resolved_windows: list[bytes] = []
    for entry_id in range(PAIR_ENTRY_COUNT):
        pair_offset = PAIR_TABLE_OFFSET + entry_id * PAIR_ENTRY_SIZE
        definition_pointer, animation_pointer = struct.unpack_from(
            "<II",
            rom,
            pair_offset,
        )
        definition_offset = _rom_offset(definition_pointer, len(rom))
        _rom_offset(animation_pointer, len(rom))
        if animation_pointer - definition_pointer != 12:
            raise ValueError(
                f"entry {entry_id} animation pointer is not definition + 12"
            )
        component_list_pointer = struct.unpack_from(
            "<I",
            rom,
            definition_offset,
        )[0]
        components, component_list_raw = _read_component_list(
            rom,
            component_list_pointer,
            definition_pointer=definition_pointer,
        )
        component_list_offset = _rom_offset(component_list_pointer, len(rom))
        resolved_window = rom[
            component_list_offset : component_list_offset + 0x28
        ]
        if len(resolved_window) != 0x28:
            raise ValueError(f"entry {entry_id} resolved window is truncated")
        resolved_windows.append(resolved_window)
        definition_header = rom[definition_offset : definition_offset + 12]
        tile_base_offset = struct.unpack_from(
            "<H",
            tile_offset_table,
            entry_id * 2,
        )[0]
        entries.append(
            {
                "id": entry_id,
                "pair_file_offset": pair_offset,
                "definition_pointer": _pointer(definition_pointer),
                "animation_pointer": _pointer(animation_pointer),
                "tile_base_offset": tile_base_offset,
                "component_list_pointer": _pointer(component_list_pointer),
                "component_count": len(components),
                "component_list_size": len(component_list_raw),
                "component_list_sha256": _sha256(component_list_raw),
                "components": components,
                "terminator_raw_hex": TERMINATOR.hex(),
                "definition_header_raw_hex": definition_header.hex(),
                "definition_header_sha256": _sha256(definition_header),
                "resolved_window_0x28_sha256": _sha256(resolved_window),
            }
        )

    resolved_window_sha256 = _sha256(b"".join(resolved_windows))
    if resolved_window_sha256 != RESOLVED_WINDOW_0X28_SHA256:
        raise ValueError("resolved component-list window SHA-256 mismatch")

    code_slices = []
    for expected in CODE_SLICES:
        code = rom[
            expected["file_offset"] : expected["file_offset"] + expected["size"]
        ]
        actual = _sha256(code)
        if actual != expected["sha256"]:
            raise ValueError(f"{expected['name']} code slice SHA-256 mismatch")
        code_slices.append(dict(expected))

    return {
        "schema": "sprite-definition-runtime-chain-v1",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": rom_sha256,
        },
        "pair_table": {
            "file_offset": PAIR_TABLE_OFFSET,
            "gba_address": _pointer(ROM_BASE + PAIR_TABLE_OFFSET),
            "entry_count": PAIR_ENTRY_COUNT,
            "entry_size": PAIR_ENTRY_SIZE,
            "sha256": _sha256(pair_table),
        },
        "tile_offset_table": {
            "file_offset": TILE_OFFSET_TABLE_OFFSET,
            "gba_address": _pointer(ROM_BASE + TILE_OFFSET_TABLE_OFFSET),
            "entry_count": PAIR_ENTRY_COUNT,
            "entry_size": TILE_OFFSET_ENTRY_SIZE,
            "sha256": _sha256(tile_offset_table),
        },
        "resolved_window_0x28_definition": (
            "concat in pair-table order of ROM[D_i[0]:D_i[0]+0x28]"
        ),
        "resolved_window_0x28_sha256": resolved_window_sha256,
        "entry_count": len(entries),
        "component_count": sum(entry["component_count"] for entry in entries),
        "multi_component_entry_ids": [
            entry["id"] for entry in entries if entry["component_count"] > 1
        ],
        "entries": entries,
        "component_schema": {
            "record_size": COMPONENT_SIZE,
            "terminator_raw_hex": TERMINATOR.hex(),
            "terminator_rule": (
                "component +0x00 is read as s16; -1 terminates the list"
            ),
            "field_evidence": {
                "tile_offset": [
                    "0x080629FC",
                    "0x08063108",
                    "0x080631FE",
                ],
                "flag_02": ["0x08062EB4..0x08062EEE"],
                "flag_03": ["0x08062EFC..0x08062F9E"],
                "horizontal_position_input": ["0x08062A26..0x08062A64"],
                "vertical_position_input": ["0x08062A2C..0x08062A7C"],
                "width": [
                    "0x08062A50",
                    "0x08062DCA..0x08062DEC",
                    "0x0806314E",
                ],
                "height": [
                    "0x08062A66",
                    "0x08062DEE..0x08062EB2",
                    "0x08063150",
                ],
                "transform_factor_0c": [
                    "0x08062F12..0x08062F44",
                    "0x08063002..0x08063048",
                ],
                "transform_factor_0e": [
                    "0x08062F56..0x08062F7C",
                    "0x0806301C..0x08063060",
                ],
                "unknown_10_byte": [],
                "oam_attribute_byte": [
                    "0x08062B62..0x08062B6E",
                    "0x08062DB4..0x08062DBC",
                ],
                "unknown_12": [],
            },
        },
        "runtime_chain": {
            "pair_table_loader": "0x08080B08",
            "sprite_task_allocator": "0x080625A4",
            "pair_index_install": "0x08062668",
            "component_selector": "0x0806298C",
            "attr2_builder": "0x08063108",
            "obj_vram_copy_path": "0x08063134",
            "component_stride_and_terminator_check": "0x080631F6..0x08063210",
            "tile_base_global": "0x0202CA24",
            "palette_bank_global": "0x0202CA26",
            "obj_vram_base": "0x06010000",
            "obj_palette_base": "0x05000200",
            "task_tile_base_formula": (
                "task.tile_base = u16[0x0202CA24] + tile_base_offset[id]"
            ),
            "attr2_tile_formula": (
                "attr2.tile = task.tile_base + component.tile_offset"
            ),
            "attr2_palette_formula": (
                "attr2.palette = u8[0x0202CA26] << 12"
            ),
            "obj_vram_address_formula": (
                "OBJ tile bytes begin at 0x06010000 + attr2.tile * 32"
            ),
            "obj_palette_address_formula": (
                "OBJ palette bytes begin at 0x05000200 + "
                "u8[0x0202CA26] * 32"
            ),
            "code_slices": code_slices,
        },
        "scope": {
            "kind": (
                "static definition/animation metadata plus code-proven runtime "
                "OBJ address chain"
            ),
            "pixel_payload_in_pair_table": False,
            "runtime_pixels_exported": False,
            "runtime_palette_verified": False,
            "obj_vram_capture_required": True,
            "obj_palette_capture_required": True,
            "animation_sequence_fully_interpreted": False,
        },
    }


def export_sprite_definition_runtime_chain(
    root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    rom = (root / "rom/base.gba").read_bytes()
    manifest = build_manifest(rom)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the 0x53F140 sprite definition runtime chain",
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/sprite-definition-runtime-v1"),
    )
    args = parser.parse_args()
    manifest = export_sprite_definition_runtime_chain(
        args.root.resolve(),
        args.output_dir,
    )
    print(
        json.dumps(
            {
                "schema": manifest["schema"],
                "entries": manifest["entry_count"],
                "components": manifest["component_count"],
                "output": str(args.output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
