#!/usr/bin/env python3
"""Inventory every direct caller of the shared ROM GPU-copy queue."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Any
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-gpu-copy-queue-inventory-v1"
VERIFY_SCHEMA = "rom-gpu-copy-queue-inventory-verification-v1"
PAYLOAD_NAME = "rom-gpu-copy-queue-inventory.json"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ENQUEUE = 0x080635B8
SOURCE_FILES = {
    "battle_effect_queue": Path(
        "artifacts/battle-effect-sprite-animations-v1/manifest.json"
    ),
    "menu_ui_bank": Path("sequel/content/menu-ui/bank.json"),
    "menu_portraits": Path("artifacts/menu-portraits-v1/manifest.json"),
    "overview": Path(
        "artifacts/overview-gradient-overlay-v1/overview-gradient-overlay.json"
    ),
    "overview_manifest": Path(
        "artifacts/overview-gradient-overlay-v1/manifest.json"
    ),
    "tile_assets_bg": Path("artifacts/tile-assets-bg-v2/manifest.json"),
}
EXPECTED_CALLS = [
    0x08063168,
    0x0808812E,
    0x0808D9C6,
    0x0808DA0E,
    0x080962EE,
    0x080962FE,
    0x08096536,
    0x0809655C,
    0x080965A4,
    0x08096DBA,
    0x08096E00,
    0x08096E44,
    0x08098B6C,
    0x08098D90,
]
SCOPE = {
    "queue_status_1_abi_complete": True,
    "queue_status_3_enqueue_shape_complete": True,
    "queue_status_3_lifecycle_complete": False,
    "direct_thumb_bl_callers_complete": True,
    "direct_caller_resource_classification_complete": True,
    "indirect_enqueue_callers_complete": False,
    "runtime_reachability_complete": False,
    "all_async_transfer_queues_complete": False,
    "dialogue_tilemap_submit_complete": False,
    "raw_uncompressed_graphics_complete": False,
    "all_game_visual_states_complete": False,
    "generic_image_writeback_complete": False,
}
SELECTION_RULE = {
    "denominator": (
        "every halfword-aligned Thumb BL in the hash-bound base ROM whose "
        "decoded target is 0x080635B8"
    ),
    "classification_window": (
        "caller-local register flow may bind a source only when the queue "
        "arguments or an accepted upstream table relationship are explicit"
    ),
    "dynamic_value_policy": (
        "record IDs, variants, task fields, work pointers and palette banks "
        "remain expressions and are never promoted to constants"
    ),
    "new_source_policy": (
        "a ROM source already present in an accepted artifact is bound to that "
        "artifact and is not exported again"
    ),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _format_address(value: int) -> str:
    return f"0x{value:08X}"


def _require(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def _load(root: Path, path: Path) -> dict[str, Any]:
    return json.loads((root / path).read_text(encoding="utf-8"))


def _slice(rom: bytes, start: int, end: int) -> dict[str, Any]:
    begin = start - ROM_BASE
    finish = end - ROM_BASE
    if begin < 0 or finish <= begin or finish > len(rom):
        raise ValueError(f"invalid ROM slice {_format_address(start)}..{_format_address(end)}")
    data = rom[begin:finish]
    return {
        "start": _format_address(start),
        "end_exclusive": _format_address(end),
        "size": len(data),
        "sha256": _sha(data),
    }


def _decode_thumb_bl(address: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    if displacement & (1 << 22):
        displacement -= 1 << 23
    return address + 4 + displacement


def _find_direct_calls(rom: bytes, target: int) -> list[int]:
    calls = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        address = ROM_BASE + offset
        if _decode_thumb_bl(address, first, second) == target:
            calls.append(address)
    return calls


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, address - ROM_BASE)[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, address - ROM_BASE)[0]


def _expect_u16(rom: bytes, address: int, expected: int, label: str) -> None:
    _require(_u16(rom, address), expected, label)


def _expect_u32(rom: bytes, address: int, expected: int, label: str) -> None:
    _require(_u32(rom, address), expected, label)


def _expect_bl(rom: bytes, address: int, target: int, label: str) -> None:
    _require(
        _decode_thumb_bl(
            address, _u16(rom, address), _u16(rom, address + 2)
        ),
        target,
        label,
    )


def _ldr_word_offset(instruction: int) -> int | None:
    if instruction & 0xF800 != 0x6800:
        return None
    return ((instruction >> 6) & 0x1F) * 4


def _instruction_evidence(rom: bytes) -> dict[str, Any]:
    for address, expected in [
        (0x08096142, 0x2905),
        (0x08096146, 0x4801),
        (0x08096150, 0x0090),
        (0x08096152, 0x1880),
        (0x08096154, 0x00C0),
        (0x08096156, 0x00C9),
        (0x08096158, 0x4A02),
    ]:
        _expect_u16(rom, address, expected, "menu selector instruction")
    _expect_u32(rom, 0x0809614C, 0x085A4DE4, "special menu pair")
    _expect_u32(rom, 0x08096164, 0x085A4DEC, "menu pair table")

    route_sites = [
        (0x080962FE, 0x08096298, 0x080962F8, 0x080962FC, 0x08096320),
        (0x0809655C, 0x0809654C, 0x08096550, 0x0809655A, 0x0809657C),
        (0x080965A4, 0x08096594, 0x08096598, 0x080965A2, 0x080965AC),
        (0x08096DBA, 0x08096DB0, 0x08096DB4, 0x08096DB8, 0x08096DD0),
        (0x08096E00, 0x08096DF6, 0x08096DFA, 0x08096DFE, 0x08096E58),
    ]
    menu_routes = []
    for enqueue, selector, palette_load, size_load, destination_literal in route_sites:
        _expect_bl(rom, selector, 0x08096138, "menu selector BL")
        _require(
            _ldr_word_offset(_u16(rom, palette_load)),
            4,
            "menu palette pointer field",
        )
        _expect_u16(rom, size_load, 0x2280, "menu palette size")
        _expect_u32(
            rom, destination_literal, 0x05000200, "menu palette destination base"
        )
        _expect_bl(rom, enqueue, ENQUEUE, "menu palette enqueue BL")
        menu_routes.append(
            {
                "enqueue_callsite": _format_address(enqueue),
                "selector_callsite": _format_address(selector),
                "selector_target": "0x08096138",
                "palette_load": _format_address(palette_load),
                "palette_load_offset": 4,
                "destination_base": "0x05000200",
                "size_bytes": 128,
            }
        )

    _expect_u16(rom, 0x08096246, 0x9D0B, "menu graphics buffer argument")
    _expect_u16(rom, 0x08096260, 0x9501, "menu graphics saved buffer")
    _expect_bl(rom, 0x08096298, 0x08096138, "menu graphics selector BL")
    _require(_ldr_word_offset(_u16(rom, 0x080962A6)), 0, "menu gfx pointer field")
    _expect_bl(rom, 0x080962AA, 0x0809C0EC, "menu graphics LZ77 BL")
    _expect_u16(rom, 0x080962E6, 0x22C8, "menu graphics size seed")
    _expect_u16(rom, 0x080962E8, 0x0152, "menu graphics size scale")
    _expect_u16(rom, 0x080962EA, 0x9801, "menu graphics queue source")
    _expect_bl(rom, 0x080962EE, ENQUEUE, "menu graphics enqueue BL")

    fixed_literals = [
        ("0x0808812E", 0x08088164, 0x02002BC0),
        ("0x08096536", 0x0809653C, 0x02002880),
        ("0x08096E44", 0x08096E5C, 0x02002880),
        ("0x08098B6C", 0x08098AF4, 0x02002880),
    ]
    for callsite, literal, expected in fixed_literals:
        _expect_u32(rom, literal, expected, f"{callsite} source literal")

    _expect_bl(rom, 0x08096E3A, 0x08096D4C, "palette transform helper")
    _expect_u16(rom, 0x08098D7E, 0x3540, "work palette buffer offset")
    _expect_bl(rom, 0x08098D86, 0x080986B0, "work palette generator")
    _expect_bl(rom, 0x08098D90, ENQUEUE, "work palette enqueue")
    return {
        "menu_pair_selector": {
            "table_base": "0x085A4DEC",
            "special_variant": "0x085A4DE4",
            "record_stride": 40,
            "variant_stride": 8,
            "palette_field_offset": 4,
        },
        "menu_palette_routes": menu_routes,
        "menu_graphics_staged_route": {
            "source": "stack_arg_6_graphics_work_buffer",
            "lz77_source": "Pair(r1_in,r2_in).gfx_ptr",
            "lz77_target": "0x0809C0EC",
            "enqueue_callsite": "0x080962EE",
            "size_bytes": 6400,
        },
        "fixed_ram_source_literals": {
            callsite: _format_address(expected)
            for callsite, _, expected in fixed_literals
        },
        "helper_chains": {
            "0x08096E44": "0x08096E3A -> 0x08096D4C",
            "0x08098D90": "0x08098D86 -> 0x080986B0",
        },
    }


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha(
            (root / "tools/export_rom_gpu_copy_queue_inventory.py").read_bytes()
        ),
        "verifier_sha256": _sha(
            (root / "tools/verify_rom_gpu_copy_queue_inventory.py").read_bytes()
        ),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_gpu_copy_queue_inventory.py").read_bytes()
        ),
    }


def _queue_abi(rom: bytes) -> dict[str, Any]:
    return {
        "enqueue_helper": _slice(rom, 0x080635B8, 0x08063604),
        "status_3_enqueue_helper": _slice(rom, 0x08063604, 0x0806365C),
        "consumer": _slice(rom, 0x0806365C, 0x080636DC),
        "dispatcher_order": _slice(rom, 0x080612BC, 0x080614E4),
        "queue_start": "0x03005BBC",
        "queue_end_exclusive": "0x03005CBC",
        "slot_count": 16,
        "slot_stride": 16,
        "enqueue_result": "1 when a free slot is reserved; 0 when full",
        "status_1_fields": [
            {"offset": 0, "name": "flags", "type": "u32"},
            {"offset": 4, "name": "source", "type": "u32"},
            {"offset": 8, "name": "destination", "type": "u32"},
            {"offset": 12, "name": "size_bytes", "type": "u16"},
        ],
        "status_1_consumer": "CpuSet(source,destination,u16(size_bytes)>>1)",
        "status_1_completion": "clear flags bit 0",
        "status_3_fields": [
            {"offset": 0, "name": "flags", "type": "u32", "value": 3},
            {"offset": 4, "name": "source", "type": "u32"},
            {"offset": 8, "name": "destination", "type": "u32"},
            {"offset": 12, "name": "source_stride_halfwords", "type": "u16"},
            {"offset": 14, "name": "row_count", "type": "u16"},
        ],
        "status_3_consumer": (
            "for i<row_count: CpuSet(source+2*stride*i,"
            "destination+64*i,stride)"
        ),
        "status_3_observed_completion": "clear flags bit 1; bit 0 remains set",
        "dispatch_calls": {
            "renderer": "0x08061320 -> 0x08062924",
            "first_flush": "0x080613FC -> 0x0806365C",
            "optional_second_flush": "0x080614C2 -> 0x0806365C",
        },
        "dispatch_boundary": (
            "relative call order is code-proven; unique hardware VBlank phase "
            "and status-3 post-flush lifecycle are not"
        ),
    }


def _caller_definitions() -> list[dict[str, Any]]:
    menu_selector = {
        "function": "0x08096138",
        "formula": (
            "Pair(record,variant<5)=0x085A4DEC+record*40+variant*8; "
            "Pair(record,variant=5)=0x085A4DE4"
        ),
        "fields": {"gfx_ptr": 0, "palette_ptr": 4},
        "dynamic_zero_sentinel_possible": True,
    }
    menu_palette = {
        "id": "menu_ui_palette_records",
        "path": SOURCE_FILES["menu_ui_bank"].as_posix(),
        "table": "0x085A4DEC",
        "record_count": 63,
        "record_size": 40,
        "variant_count": 5,
        "special_variant": "0x085A4DE4",
        "pointer_field": "palette_ptr_<variant>",
        "source_size": 128,
    }
    return [
        {
            "callsite": "0x08063168",
            "classification": "dynamic_unresolved_source",
            "source": "task.tile_source_ptr+s16(component.tile_index)*32",
            "destination": (
                "0x06010000+u16(task.tile_base+running_dynamic_tile_offset)*32"
            ),
            "size_bytes": (
                "u16(trunc0_div64(s16(component.width)*"
                "s16(component.height))*32)"
            ),
            "reason": (
                "The task source field is not statically proven to be a mapped "
                "ROM address for any reachable runtime instance."
            ),
            "existing_artifact_overlap": {
                "id": "battle_effect_dynamic_obj_queue_model",
                "path": SOURCE_FILES["battle_effect_queue"].as_posix(),
            },
            "function": {"start": 0x08063122, "end": 0x080631F6},
        },
        {
            "callsite": "0x0808812E",
            "classification": "known_ram_source",
            "source": "0x02002BC0",
            "destination": "0x05000000",
            "size_bytes": 416,
            "reason": "Fixed EWRAM-to-PRAM copy; no ROM source is used by enqueue.",
        },
        {
            "callsite": "0x0808D9C6",
            "classification": "known_ram_source",
            "source": "0x02002AB0",
            "destination": "0x06002000",
            "size_bytes": 352,
            "reason": "Overview tiles are generated in EWRAM before enqueue.",
            "resource_binding": {
                "id": "overview_generated_bg0_tiles",
                "path": SOURCE_FILES["overview"].as_posix(),
            },
            "function": {"start": 0x0808D934, "end": 0x0808DA80},
        },
        {
            "callsite": "0x0808DA0E",
            "classification": "known_ram_source",
            "source": "0x02002C10",
            "destination": "0x050001A0",
            "size_bytes": 32,
            "reason": "Overview palette is generated in EWRAM before enqueue.",
            "resource_binding": {
                "id": "overview_generated_bg0_palette",
                "path": SOURCE_FILES["overview"].as_posix(),
            },
            "function": {"start": 0x0808D934, "end": 0x0808DA80},
        },
        {
            "callsite": "0x080962EE",
            "classification": "existing_rom_derived_ram",
            "source": "stack_arg_6_graphics_work_buffer",
            "destination": "0x06010000+u16(r3_in)*32",
            "size_bytes": 6400,
            "reason": (
                "The same function LZ77-decompresses Pair(r1_in,r2_in).gfx_ptr "
                "into this buffer and adjusts its tile bytes before enqueue."
            ),
            "selector": menu_selector,
            "resource_binding": {
                "id": "menu_ui_graphics_transformed_in_ram",
                "path": SOURCE_FILES["menu_portraits"].as_posix(),
            },
            "function": {"start": 0x08096168, "end": 0x08096312},
        },
        {
            "callsite": "0x080962FE",
            "classification": "existing_rom_source",
            "source": "u32[Pair(r1_in,r2_in)+4]",
            "destination": "0x05000200+u8(stack_arg_5)*32",
            "size_bytes": 128,
            "reason": "Dynamic selector into the accepted menu-ui palette bank.",
            "selector": menu_selector,
            "resource_binding": menu_palette,
            "function": {"start": 0x08096168, "end": 0x08096312},
        },
        {
            "callsite": "0x08096536",
            "classification": "unknown_ram_producer",
            "source": "0x02002880",
            "destination": "0x05000200+u8(state_plus_0x2C+7)*32",
            "size_bytes": 128,
            "reason": (
                "The enqueue source is fixed EWRAM, but this caller-local "
                "branch does not prove the buffer producer."
            ),
            "function": {"start": 0x08096324, "end": 0x080965E8},
        },
        *[
            {
                "callsite": callsite,
                "classification": "existing_rom_source",
                "source": (
                    "u32[Pair(u8(state_plus_0x2C+2),"
                    "u8(state_plus_0x2C+3))+4]"
                ),
                "destination": "0x05000200+u8(state_plus_0x2C+7)*32",
                "size_bytes": 128,
                "reason": "Dynamic selector into the accepted menu-ui palette bank.",
                "selector": menu_selector,
                "resource_binding": menu_palette,
                **(
                    {"function": {"start": 0x08096324, "end": 0x080965E8}}
                    if callsite in {"0x0809655C", "0x080965A4"}
                    else {}
                ),
            }
            for callsite in ["0x0809655C", "0x080965A4", "0x08096DBA"]
        ],
        {
            "callsite": "0x08096E00",
            "classification": "existing_rom_source",
            "source": (
                "u32[Pair(u8(state_plus_0x2C+2),"
                "u8(state_plus_0x2C+3))+4]"
            ),
            "destination": "0x05000200+u8(state_plus_0x2C+7)*32",
            "size_bytes": 128,
            "reason": "Dynamic selector into the accepted menu-ui palette bank.",
            "selector": menu_selector,
            "resource_binding": menu_palette,
            "function": {"start": 0x08096DD4, "end": 0x08096E52},
        },
        {
            "callsite": "0x08096E44",
            "classification": "known_ram_source",
            "source": "0x02002880",
            "destination": "0x05000200+u8(state_plus_0x2C+7)*32",
            "size_bytes": 128,
            "reason": (
                "A preceding helper writes the fixed EWRAM buffer from a "
                "dynamic palette pointer; its complete producer semantics "
                "remain intentionally unclaimed."
            ),
            "function": {"start": 0x08096DD4, "end": 0x08096E52},
        },
        {
            "callsite": "0x08098B6C",
            "classification": "known_ram_source",
            "source": "0x02002880",
            "destination": "0x05000000+u8(0x0203120C+0x0D)*32",
            "size_bytes": 32,
            "reason": (
                "The function generates a transformed 16-color palette in "
                "EWRAM; nearby 0x085A320C is not the enqueue source."
            ),
            "excluded_neighbor": {
                "id": "tile_assets_bg_descriptor_table",
                "path": SOURCE_FILES["tile_assets_bg"].as_posix(),
                "table": "0x085A320C",
            },
            "function": {"start": 0x08098A7C, "end": 0x08098B80},
        },
        {
            "callsite": "0x08098D90",
            "classification": "known_ram_source",
            "source": "work_ram_object+0x40",
            "destination": "0x05000000+u8(work_ram_object+0x0B)*32",
            "size_bytes": 32,
            "reason": (
                "The immediately preceding helper generates the queued "
                "palette in the work object; no ROM-to-work producer is proven."
            ),
        },
    ]


def _build(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    rom = (root / ROM_PATH).read_bytes()
    _require(_sha(rom), ROM_SHA256, "base ROM SHA-256")
    calls = _find_direct_calls(rom, ENQUEUE)
    _require(calls, EXPECTED_CALLS, "direct enqueue caller denominator")

    menu_bank = _load(root, SOURCE_FILES["menu_ui_bank"])
    _require(menu_bank["table_offset"], 0x5A4DEC, "menu-ui table offset")
    _require(menu_bank["entry_count"], 63, "menu-ui entry count")
    _require(menu_bank["entry_size"], 40, "menu-ui entry size")
    _require(menu_bank["verification"], "runtime_verified", "menu-ui verification")
    menu_portraits = _load(root, SOURCE_FILES["menu_portraits"])
    _require(
        menu_portraits["source_table"]["gba_address"],
        "0x085A4DEC",
        "menu portrait source table",
    )
    battle_effect = _load(root, SOURCE_FILES["battle_effect_queue"])
    _require(
        battle_effect["dynamic_obj_vram_model"]["copy_enqueue"][
            "enqueue_helper"
        ],
        "0x080635B8",
        "battle-effect queue helper",
    )
    overview = _load(root, SOURCE_FILES["overview"])
    _require(
        [row["call"] for row in overview["generator"]["copy_routes"][:2]],
        ["0x0808D9C6", "0x0808DA0E"],
        "overview queue routes",
    )
    tile_assets = _load(root, SOURCE_FILES["tile_assets_bg"])
    _require(
        tile_assets["source_table"]["gba_address"],
        "0x085A320C",
        "tile-assets table",
    )

    selector_code = _slice(rom, 0x08096138, 0x08096162)
    _require(
        selector_code["sha256"],
        "6a981ff31b2c8dbf979d0ffab751ccfa395e70e2a6e85380f549535295fee96e",
        "menu pair selector code",
    )
    definitions = _caller_definitions()
    direct_callers = []
    for definition in definitions:
        callsite = int(definition["callsite"], 16)
        row = {
            key: value
            for key, value in definition.items()
            if key != "function"
        }
        row["callsite_window"] = _slice(rom, callsite - 32, callsite + 4)
        if "function" in definition:
            row["function_code"] = _slice(
                rom,
                definition["function"]["start"],
                definition["function"]["end"],
            )
        direct_callers.append(row)

    classifications = [row["classification"] for row in direct_callers]
    summary = {
        "direct_caller_count": len(direct_callers),
        "existing_rom_source_caller_count": classifications.count(
            "existing_rom_source"
        ),
        "existing_rom_derived_ram_caller_count": classifications.count(
            "existing_rom_derived_ram"
        ),
        "known_ram_source_caller_count": classifications.count(
            "known_ram_source"
        ),
        "unknown_ram_producer_caller_count": classifications.count(
            "unknown_ram_producer"
        ),
        "dynamic_unresolved_source_caller_count": classifications.count(
            "dynamic_unresolved_source"
        ),
        "new_rom_source_count": 0,
    }
    payload = {
        "schema": SCHEMA,
        "implementation": _implementation(root),
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": ROM_SHA256,
        },
        "upstream_evidence": {
            name: {
                "path": path.as_posix(),
                "sha256": _sha((root / path).read_bytes()),
            }
            for name, path in sorted(SOURCE_FILES.items())
        },
        "selection_rule": SELECTION_RULE,
        "menu_pair_selector": {
            "code": selector_code,
            "formula": (
                "Pair(record,variant<5)=0x085A4DEC+record*40+variant*8; "
                "Pair(record,variant=5)=0x085A4DE4"
            ),
            "zero_sentinel_boundary": (
                "dynamic record/variant expressions do not guarantee a "
                "nonzero source pointer"
            ),
        },
        "instruction_evidence": _instruction_evidence(rom),
        "queue_abi": _queue_abi(rom),
        "summary": summary,
        "direct_callers": direct_callers,
        "new_rom_sources": [],
        "scope": SCOPE,
    }
    files = {
        PAYLOAD_NAME: (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode()
    }
    return payload, files


def _manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {name: _sha(data) for name, data in sorted(files.items())},
        "scope": SCOPE,
        "source": {
            "rom_sha256": ROM_SHA256,
            "upstream_evidence": payload["upstream_evidence"],
        },
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_gpu_copy_queue_inventory.py",
                "--root",
                ".",
                "--output-dir",
                f"artifacts/{SCHEMA}",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_gpu_copy_queue_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "errors": [],
                "direct_caller_count": 14,
                "new_rom_source_count": 0,
            },
        },
    }


def _validate_output(root: Path, output: Path) -> Path:
    root = root.resolve()
    target = output.expanduser().resolve()
    if output.is_symlink() or target == root or target in root.parents:
        raise ValueError("output directory is unsafe")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("refusing to replace foreign output")
    try:
        manifest = json.loads(
            (target / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("refusing to replace foreign output") from error
    actual = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file()
    }
    if (
        any(path.is_symlink() for path in target.rglob("*"))
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or actual != set(manifest.get("files", {})) | {"manifest.json"}
    ):
        raise ValueError("refusing to replace foreign output")
    for name, expected in manifest["files"].items():
        if _sha((target / name).read_bytes()) != expected:
            raise ValueError("refusing to replace corrupted output")
    return target


def _replace(
    output: Path, files: dict[str, bytes], manifest: dict[str, Any]
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent)
    )
    backup = None
    try:
        for name, data in files.items():
            (temporary / name).write_bytes(data)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        if output.exists():
            backup = output.parent / f".{output.name}.backup-{uuid.uuid4().hex}"
            output.rename(backup)
        try:
            os.replace(temporary, output)
        except BaseException:
            if backup is not None and backup.exists() and not output.exists():
                backup.rename(output)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists():
            if not output.exists():
                backup.rename(output)
            else:
                shutil.rmtree(backup)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    target = _validate_output(root, output)
    payload, files = _build(root)
    _replace(target, files, _manifest(payload, files))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    payload = export_artifact(args.root, output)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
