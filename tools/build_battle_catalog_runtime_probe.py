#!/usr/bin/env python3
"""Redirect checked battle-catalog text pointers for runtime screenshots."""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from tools.build_chapter_script_probe import BASE_SHA1
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from build_chapter_script_probe import BASE_SHA1


ROM_BASE = 0x08000000
UNIT_NAME_TABLE = 0x08599280
UNIT_NAME_COUNT = 63
CURRENT_UNIT_ID = 1
ACTIVE_LIST_NAME_TABLE = 0x0859937C
ACTIVE_LIST_NAME_COUNT = 87
ACTIVE_LIST_DISPLAY_ACTION_IDS = tuple(range(2, 10))
UNIT_DEFINITION_TABLE = 0x0854241C
UNIT_DEFINITION_SIZE = 0xB4
UNIT_SECONDARY_SLOTS_OFFSET = 0x48
PASSIVE_TEXT_TABLES = (0x085A7060, 0x085A73E0, 0x085AAEDC)
PASSIVE_TEXT_COUNT = 45
CURRENT_PASSIVE_ID = 1


def _checked_pointer(base: bytes, table: int, index: int) -> int:
    offset = table - ROM_BASE + index * 4
    if offset < 0 or offset + 4 > len(base):
        raise ValueError("pointer table lies outside ROM")
    pointer = struct.unpack_from("<I", base, offset)[0]
    if not ROM_BASE <= pointer < ROM_BASE + len(base):
        raise ValueError(
            f"table 0x{table:08X} index {index} is not a ROM pointer: "
            f"0x{pointer:08X}"
        )
    return pointer


def _redirect(rom: bytearray, table: int, current: int, target: int, base: bytes) -> None:
    _checked_pointer(base, table, current)
    pointer = _checked_pointer(base, table, target)
    struct.pack_into("<I", rom, table - ROM_BASE + current * 4, pointer)


def build_probe(
    base: bytes,
    *,
    unit_name_id: int | None = None,
    passive_text_id: int | None = None,
    active_list_name_id: int | None = None,
    verify_sha1: bool = True,
) -> bytes:
    if verify_sha1:
        digest = hashlib.sha1(base).hexdigest()
        if digest != BASE_SHA1:
            raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    modes = (unit_name_id, passive_text_id, active_list_name_id)
    if sum(value is not None for value in modes) > 1:
        raise ValueError("catalog redirect modes are mutually exclusive")
    if unit_name_id is not None and not 0 <= unit_name_id < UNIT_NAME_COUNT:
        raise ValueError(f"unit name ID must be in 0..{UNIT_NAME_COUNT - 1}")
    if passive_text_id is not None and not 0 <= passive_text_id < PASSIVE_TEXT_COUNT:
        raise ValueError(f"passive text ID must be in 0..{PASSIVE_TEXT_COUNT - 1}")
    if active_list_name_id is not None and not 0 <= active_list_name_id < ACTIVE_LIST_NAME_COUNT:
        raise ValueError(
            f"active list name ID must be in 0..{ACTIVE_LIST_NAME_COUNT - 1}"
        )
    if all(value is None for value in modes):
        raise ValueError("one catalog redirect mode is required")

    rom = bytearray(base)
    if unit_name_id is not None:
        _redirect(rom, UNIT_NAME_TABLE, CURRENT_UNIT_ID, unit_name_id, base)
    elif passive_text_id is not None:
        assert passive_text_id is not None
        for table in PASSIVE_TEXT_TABLES:
            _redirect(rom, table, CURRENT_PASSIVE_ID, passive_text_id, base)
        unit_slot = (
            UNIT_DEFINITION_TABLE - ROM_BASE
            + CURRENT_UNIT_ID * UNIT_DEFINITION_SIZE
            + UNIT_SECONDARY_SLOTS_OFFSET
        )
        if base[unit_slot] != CURRENT_PASSIVE_ID:
            raise ValueError("current unit secondary-slot source ID does not match")
        rom[unit_slot] = passive_text_id
    else:
        assert active_list_name_id is not None
        for action_id in ACTIVE_LIST_DISPLAY_ACTION_IDS:
            _redirect(
                rom,
                ACTIVE_LIST_NAME_TABLE,
                action_id,
                active_list_name_id,
                base,
            )
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--unit-name-id", type=int)
    modes.add_argument("--passive-text-id", type=int)
    modes.add_argument("--active-list-name-id", type=int)
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(),
        unit_name_id=args.unit_name_id,
        passive_text_id=args.passive_text_id,
        active_list_name_id=args.active_list_name_id,
    )
    args.output_rom.parent.mkdir(parents=True, exist_ok=True)
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
