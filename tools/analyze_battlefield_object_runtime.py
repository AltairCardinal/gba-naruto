#!/usr/bin/env python3
"""Bind battlefield-object creation and side-end lifecycle to the original ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.thumb_branch import iter_thumb_direct_branches
from tools.extract_tileset import lz77_decompress


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
OBJECT_TABLE = 0x02026604
OBJECT_ALLOCATOR = 0x08081024
OBJECT_FREE = 0x08081084
SIDE_END_TICK = 0x08081B70

RANGES = {
    "effect_0x0c": (
        0x0807726E,
        0x08077282,
        "10073e437347337ed7b54b3875a06483c7f5bb2948b6635c6ee214a496eba6f2",
    ),
    "effect_0x18": (
        0x08077514,
        0x08077532,
        "575b1743e7a1467926f7d97c859d3a76c4de7b2deea72bef2a87592ba8c248fa",
    ),
    "allocator": (
        0x08081024,
        0x08081084,
        "c2d9429855e9a91fabf5783581a0466a88a63f209dded259c359aef7e5ba73e8",
    ),
    "side_end_tick": (
        0x08081B70,
        0x0808203E,
        "c575f74ad7453e16a348e53fb3dbe352e0f91ea1f181f95a3970b34fb542ff70",
    ),
    "type_2_expiry_presentation": (
        0x08081B9A,
        0x08081C34,
        "62f0f7151a9e828a2dd16588007b8399ef2d719fb559aa833a4975f3a140e03c",
    ),
    "effect_resource_builder": (
        0x0807FDCC,
        0x0807FE2C,
        "2715bad870d8d7ea84bd03c537f08200be80b178c0dd570aea30155bb9431a84",
    ),
    "effect_sequence_selector": (
        0x0807FE2C,
        0x080800A4,
        "690232cbbed4b7f9d19602e91feca3299191cccb8369a10d3235b2d415751c94",
    ),
    "object_grid_binding": (
        0x08080FC8,
        0x08081024,
        "53303616ae87741db9efae8ade2f51cc998480f33b49c4638396073f464a9f6f",
    ),
    "side_controller": (
        0x0807367C,
        0x080736BC,
        "152bab8b0a79ab2ef02ae220b20a18097f722f02a46c8a536614fad8e0286834",
    ),
}


def _offset(address: int) -> int:
    return address - ROM_BASE


def _hex(address: int) -> str:
    return f"0x{address:08X}"


def _u32(rom: bytes, address: int) -> int:
    start = _offset(address)
    return int.from_bytes(rom[start : start + 4], "little")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch: expected {expected!r}, got {actual!r}"
        )


def _range_manifest(rom: bytes) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, (start, end, expected_sha256) in RANGES.items():
        blob = rom[_offset(start) : _offset(end)]
        actual_sha256 = hashlib.sha256(blob).hexdigest()
        _expect(actual_sha256, expected_sha256, f"{name} SHA-256")
        result[name] = {
            "start": _hex(start),
            "end": _hex(end),
            "sha256": actual_sha256,
        }
    return result


def build_battlefield_object_runtime_manifest(
    rom_path: Path | str,
) -> dict[str, Any]:
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()
    rom_sha256 = hashlib.sha256(rom).hexdigest()
    _expect(rom_sha256, ROM_SHA256, "ROM SHA-256")
    ranges = _range_manifest(rom)

    branches = {
        branch.address: (branch.mnemonic, branch.target)
        for branch in iter_thumb_direct_branches(
            rom,
            rom_base=ROM_BASE,
            start=0x08070000,
            end=0x08082100,
        )
    }
    expected_calls = {
        0x08073688: SIDE_END_TICK,
        0x0807752C: OBJECT_ALLOCATOR,
        0x08081BB0: 0x0806F210,
        0x08081BD4: 0x0807FDCC,
        0x08081BDA: 0x0807FE2C,
        0x08081BF4: 0x080800A4,
        0x08081C14: OBJECT_FREE,
        0x08081068: 0x08080FC8,
        0x08081098: 0x08080FF8,
        0x08081CB4: 0x0806D910,
        0x08081F8E: OBJECT_FREE,
    }
    for callsite, target in expected_calls.items():
        _expect(
            branches.get(callsite),
            ("bl", target),
            f"call at {_hex(callsite)}",
        )
    _expect(
        branches.get(0x08077280),
        ("b", 0x0807752A),
        "effect 0x0C shared allocator branch",
    )
    _expect(
        _u32(rom, 0x08081C30),
        0x0000037F,
        "type 2 expiry effect resource literal",
    )
    sequence_entry = rom[
        _offset(0x0853EFD8) : _offset(0x0853EFF0)
    ]
    _expect(
        _sha256(sequence_entry),
        "8c38e996b584c2d18b1dbfa15dbd854c146e23fa5044f7787e7430e395dffdf8",
        "effect sequence 7 entry SHA-256",
    )
    sequence_resource_group = _u32(rom, 0x0853EFD8)
    _expect(sequence_resource_group, 0x12, "effect sequence 7 resource group")
    resource_pair_address = (
        0x0859911C + sequence_resource_group * 8
    )
    resource_pair = rom[
        _offset(resource_pair_address) :
        _offset(resource_pair_address + 8)
    ]
    _expect(
        _sha256(resource_pair),
        "7ac32473a04b0c0714a586d41b5f91aba9a54534df70b5c0db2af3b7e9a969f8",
        "effect resource group 18 pair SHA-256",
    )
    graphics_pointer, palette_pointer = struct.unpack(
        "<II", resource_pair
    )
    _expect(graphics_pointer, 0x083478F4, "type 2 graphics pointer")
    _expect(palette_pointer, 0x083480C8, "type 2 palette pointer")
    graphics = lz77_decompress(
        rom, graphics_pointer - ROM_BASE
    )
    palette = lz77_decompress(
        rom, palette_pointer - ROM_BASE
    )
    _expect(len(graphics), 0x0E00, "type 2 graphics size")
    _expect(
        _sha256(graphics),
        "9162bda2e90536bbe5982e94b4d4de9b18111538b548137ca057701d36b7bc55",
        "type 2 graphics SHA-256",
    )
    _expect(
        _sha256(palette),
        "d53a7a56bded0b6727002a3fb4ad69454dccee15e8f849ad3a16c3b5639244c1",
        "type 2 palette SHA-256",
    )
    for address, expected in {
        0x08080FF0: 0x02021E2C,
        0x08080FF4: 0x0201BE2A,
        0x08081018: 0x02021E2C,
        0x0808101C: 0x0201BE2A,
    }.items():
        _expect(_u32(rom, address), expected, f"grid literal at {_hex(address)}")
    _expect(
        int.from_bytes(
            rom[_offset(0x08081020) : _offset(0x08081022)],
            "little",
        ),
        0xF83F,
        "object grid clear mask",
    )

    return {
        "schema_version": 1,
        "identity": "battlefield_object_runtime",
        "rom": str(rom_path),
        "rom_sha256": rom_sha256,
        "code_ranges": ranges,
        "object_table": {
            "address": _hex(OBJECT_TABLE),
            "record_size": 16,
            "slot_count": 32,
            "reserved_slot": 0,
            "allocator": _hex(OBJECT_ALLOCATOR),
            "free": _hex(OBJECT_FREE),
            "copied_u16_offsets": [4, 6, 8, 10],
        },
        "creation": {
            "0x0C": {
                "handler": "0x0807726E",
                "type": 2,
                "payload_u16_at_4": "event_u8_at_0x0C",
                "duration_u16_at_6": "event_u8_at_0x11_times_2",
                "source_u16_at_8": "unused_zero",
            },
            "0x18": {
                "handler": "0x08077514",
                "type": 1,
                "payload_u16_at_4": "event_u8_at_0x0C",
                "duration_u16_at_6": "event_u8_at_0x11_times_2",
                "source_u16_at_8": "event_u8_at_0x00",
            },
        },
        "lifecycle": {
            "side_end_callsite": "0x08073688",
            "side_toggle": "0x080736B6",
            "tick_function": "0x08081B70",
            "type_2_entry": "0x08081B9A",
            "type_2_free": "0x08081C14",
            "type_1_entry": "0x08081C34",
            "type_1_payload_lookup": "0x08081CB4",
            "type_1_free": "0x08081F8E",
            "free_function": _hex(OBJECT_FREE),
        },
        "semantics": {
            "duration": "decremented_once_before_each_side_toggle",
            "type_1": "resolve_payload_area_then_free",
            "type_2": "play_expiry_effect_then_free",
            "payload": (
                "The +4 word is a ninja-tool template ID, not attack potency; "
                "0x08081CB4 passes its low seven bits to 0x0806D910."
            ),
        },
        "type_2_presentation": {
            "coordinate_effect_call": "0x08081BB0 -> 0x0806F210",
            "effect_builder_call": "0x08081BD4 -> 0x0807FDCC",
            "tile_index_start": 0x0300,
            "tile_index_end": 0x037F,
            "palette_bank_start": 12,
            "palette_bank_end": 14,
            "effect_sequence": 7,
            "effect_sequence_call": "0x08081BDA -> 0x0807FE2C",
            "sequence_resource_group": sequence_resource_group,
            "graphics_pointer": _hex(graphics_pointer),
            "palette_pointer": _hex(palette_pointer),
            "graphics_decompressed_size": len(graphics),
            "graphics_frame_count": 7,
            "wait_state": 3,
            "free_after_wait": "0x08081C14",
        },
        "grid_binding": {
            "set_call": "0x08081068 -> 0x08080FC8",
            "clear_call": "0x08081098 -> 0x08080FF8",
            "cell_buffer": "0x02021E2C",
            "map_width": "0x0201BE2A",
            "object_slot_shift": 6,
            "object_slot_mask": "0x07C0",
            "rendering": "grid_metadata_not_visible_sprite",
        },
        "implementation_contract": [
            "Preserve the 16-byte record layout and 32-slot table with slot zero reserved.",
            "Store the action or ninja-tool ID at +4 and the doubled side duration at +6.",
            "Tick type-1 and type-2 objects exactly once at each side-end boundary.",
            "Resolve type-1 payload area effects before freeing the object.",
            "Play the type-2 positional expiry effect before freeing the object.",
            "Evaluate scenario conditions after due object effects mutate the domain.",
        ],
        "boundary": (
            "The seven exact sprite frames and palette are recoverable from the "
            "hash-gated sequence-7 resource pair. The original frame-hold timing "
            "is not yet proven by a natural runtime capture. Unwritten +8/+10 "
            "words for type 2 are treated as zero in the sequel rather than "
            "retaining stack garbage."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_battlefield_object_runtime_manifest(args.rom)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
