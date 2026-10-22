#!/usr/bin/env python3
"""Bind packed action range/area fields to the original target-area builder."""

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


ROM_BASE = 0x08000000
AREA_BUILDER = 0x0806A4AC
AREA_BUILDER_END = 0x0806A774
AREA_BUILDER_SHA256 = (
    "01c73a6dc0b944ee7d4574cd3e3e6ea0bde47c0e886d8b448b84ca81fa63c874"
)
TARGET_POLICY = 0x0806A2F4


def _offset(address: int) -> int:
    return address - ROM_BASE


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _hex(address: int) -> str:
    return f"0x{address:08X}"


def build_range_shape_manifest(rom_path: Path | str) -> dict[str, Any]:
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()
    blob = rom[_offset(AREA_BUILDER) : _offset(AREA_BUILDER_END)]
    _expect(
        hashlib.sha256(blob).hexdigest(),
        AREA_BUILDER_SHA256,
        "area-builder SHA-256",
    )

    # +8 is split into a shape bit and seven-bit size in both branches.
    for address, halfword in {
        0x0806A4F0: 0x7A11,  # ldrb r1, [runtime_action, #8]
        0x0806A4F2: 0x2080,  # high-bit shape mask
        0x0806A4FC: 0x207F,  # diamond size mask
        0x0806A662: 0x7A20,  # reload runtime_action[8]
        0x0806A664: 0x217F,  # cardinal-axis size mask
    }.items():
        _expect(_u16(rom, address), halfword, f"instruction at {_hex(address)}")

    target_policy_calls = [
        branch.address
        for branch in iter_thumb_direct_branches(
            rom,
            rom_base=ROM_BASE,
            start=AREA_BUILDER,
            end=AREA_BUILDER_END,
        )
        if branch.mnemonic == "bl" and branch.target == TARGET_POLICY
    ]
    _expect(
        target_policy_calls,
        [0x0806A5D2, 0x0806A658, 0x0806A740],
        "area target-policy calls",
    )

    return {
        "schema_version": 1,
        "identity": "battle_range_shape",
        "rom": str(rom_path),
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "area_builder": {
            "start": _hex(AREA_BUILDER),
            "end": _hex(AREA_BUILDER_END),
            "sha256": hashlib.sha256(blob).hexdigest(),
        },
        "target_policy_function": _hex(TARGET_POLICY),
        "target_policy_calls": [_hex(address) for address in target_policy_calls],
        "area_shape_encoding": {
            "size": "low_7_bits_including_center",
            "high_bit_0": "manhattan_diamond",
            "high_bit_1": "four_cardinal_axes",
            "zero_size": "center_only_for_implicit_or_special_actions",
        },
        "examples": {
            "0x01": ["center"],
            "0x02": ["center", "four_cardinal_neighbors"],
            "0x83": ["center", "four_cardinal_axes_through_distance_2"],
        },
        "implementation_contract": [
            "Decode area size independently from maximum selection distance.",
            "Collect every active unit on covered cells that passes the same target policy.",
            "Preserve unit-slot scan order when constructing the target set.",
            "Charge action cost once and resolve one queued effect event per collected target.",
        ],
        "boundary": (
            "The original function closes the two area geometries and repeated target-policy "
            "evaluation. Terrain blocking in the cardinal branch remains a map-service concern; "
            "the zero-size convention is retained only for implicit or special actions."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_range_shape_manifest(args.rom)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
