#!/usr/bin/env python3
"""Write-back path for the sprite action table (0x596CCC).

The sprite action table is proved in ``notes/sprite-frame-format-20261020.md``
and adjudicated in ``tools/table_registry.py`` (``CONFLICTS["0x53f200"]``):

    0x596CCC + sprite_id * 144 + action * 16   -> 4 x u32 pointer

    +0x00  frames pointer
    +0x04  animations pointer
    +0x08  gfx pointer
    +0x0C  palette pointer

``sprite_id`` runs 1..62 (id 0 and id 63 are all-zero slots), 9 actions per
sprite.

The legacy bank ``resource-pointers`` claimed ``0x596F0C`` as a separate
"resource pointer table".  The registry adjudicated it as a *window* into this
table: ``0x596F0C = 0x596CCC + 0x240`` = sprite 4 / action 0, and the only
native reader of that address (0x0807B220) lives in the same function that
reads the table head (0x0807AF1C).  This tool therefore serves both names:
``read_action_entry_at`` / ``write_action_entry_at`` accept any 16-byte
aligned offset inside the table.

Write-back model: copy the native entry, overwrite only the pointer fields the
author names, keep the other three raw.

Usage:
    python tools/import_sprite_action.py rom/base.gba --sprite 4 --action 0
    python tools/import_sprite_action.py rom/base.gba --sprite 4 --action 0 \\
        --set palette=0x0813E070 --out build/naruto.gba
    python tools/import_sprite_action.py rom/base.gba --window 0x596F0C \\
        --set gfx=0x0813E090
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib.io import write_json  # noqa: E402

SPRITE_ACTION_BASE = 0x596CCC
SPRITE_ID_STRIDE = 0x90          # 144 bytes per sprite
ACTION_ENTRY_STRIDE = 0x10       # 16 bytes per action
ACTIONS_PER_SPRITE = SPRITE_ID_STRIDE // ACTION_ENTRY_STRIDE
SPRITE_ID_MIN = 1
SPRITE_ID_MAX = 62

# 0x596F0C = 0x596CCC + 0x240 = entry 36 = sprite 4 / action 0
RESOURCE_WINDOW_OFFSET = 0x596F0C

ROM_POINTER_MIN = 0x08000000
ROM_POINTER_MAX = 0x085FFFFF

ACTION_FIELDS: tuple[tuple[int, str], ...] = (
    (0x00, "frames"),
    (0x04, "animations"),
    (0x08, "gfx"),
    (0x0C, "palette"),
)


class WriteBackError(ValueError):
    """Raised when an author change is not representable in the ROM record."""


def _u32(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 4], "little")


def entry_offset(sprite_id: int, action: int) -> int:
    if not SPRITE_ID_MIN <= sprite_id <= SPRITE_ID_MAX:
        raise WriteBackError(
            f"sprite id {sprite_id} outside {SPRITE_ID_MIN}..{SPRITE_ID_MAX}"
        )
    if not 0 <= action < ACTIONS_PER_SPRITE:
        raise WriteBackError(f"action {action} outside 0..{ACTIONS_PER_SPRITE - 1}")
    return SPRITE_ACTION_BASE + sprite_id * SPRITE_ID_STRIDE + action * ACTION_ENTRY_STRIDE


def window_offset(offset: int) -> int:
    """Validate that ``offset`` is an entry of the table.

    The table base (0x596CCC) is only 4-byte aligned, so the entries are
    *stride* aligned, not absolutely 16-byte aligned.
    """
    if offset < SPRITE_ACTION_BASE:
        raise WriteBackError(f"0x{offset:X} is before the sprite action table")
    if (offset - SPRITE_ACTION_BASE) % ACTION_ENTRY_STRIDE:
        raise WriteBackError(
            f"0x{offset:X} is not an entry start of the sprite action table"
        )
    if offset >= SPRITE_ACTION_BASE + (SPRITE_ID_MAX + 1) * SPRITE_ID_STRIDE:
        raise WriteBackError(f"0x{offset:X} is past the sprite action table")
    return offset


def _check_pointer(name: str, value: int) -> int:
    if value == 0:
        return value
    if not ROM_POINTER_MIN <= value <= ROM_POINTER_MAX:
        raise WriteBackError(
            f"{name} pointer 0x{value:08X} outside the 48 Mbit ROM range"
        )
    return value


def read_action_entry_at(rom: bytes, offset: int) -> dict:
    """Read one 16-byte action entry (the four pointer fields)."""
    window_offset(offset)
    raw = bytes(rom[offset:offset + ACTION_ENTRY_STRIDE])
    if len(raw) != ACTION_ENTRY_STRIDE:
        raise WriteBackError("ROM too small for the sprite action table")
    out: dict = {"offset": offset}
    for field_off, name in ACTION_FIELDS:
        out[name] = _u32(raw, field_off)
    return out


def read_sprite_action(rom: bytes, sprite_id: int, action: int) -> dict:
    """Read one sprite action entry by sprite id and action index."""
    return read_action_entry_at(rom, entry_offset(sprite_id, action))


def write_action_entry_at(rom: bytearray, offset: int, changes: dict) -> dict:
    """Apply author changes to one action entry, in place.

    The native entry is copied verbatim; only the named pointer fields are
    overwritten.  Returns the normalised author input.
    """
    window_offset(offset)
    native = bytes(rom[offset:offset + ACTION_ENTRY_STRIDE])
    if len(native) != ACTION_ENTRY_STRIDE:
        raise WriteBackError("ROM too small for the sprite action table")
    buf = bytearray(native)
    applied: dict = {"offset": offset}
    for field_off, name in ACTION_FIELDS:
        if name not in changes:
            continue
        value = _check_pointer(name, int(changes[name]))
        buf[field_off:field_off + 4] = value.to_bytes(4, "little")
        applied[name] = value
    unknown = set(changes) - {"offset", *(name for _, name in ACTION_FIELDS)}
    if unknown:
        raise WriteBackError(f"unknown sprite action fields: {sorted(unknown)}")
    if len(applied) == 1:
        raise WriteBackError("no sprite action field to write")
    rom[offset:offset + ACTION_ENTRY_STRIDE] = buf
    return applied


def write_sprite_action(rom: bytearray, sprite_id: int, action: int, changes: dict) -> dict:
    """Apply author changes to one sprite action entry."""
    return write_action_entry_at(rom, entry_offset(sprite_id, action), changes)


# --- CLI --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rom", help="ROM path (a copy is patched, never the original)")
    parser.add_argument("--sprite", type=int, help="sprite id (1..62)")
    parser.add_argument("--action", type=int, default=0, help="action index (0..8)")
    parser.add_argument("--window", type=lambda v: int(v, 0),
                        help="raw entry offset inside the table (e.g. 0x596F0C)")
    parser.add_argument("--set", action="append", default=[], dest="sets",
                        help="field=value change (repeatable)")
    parser.add_argument("--out", help="write the patched ROM copy here")
    parser.add_argument("--json", help="write the read-back report here")
    args = parser.parse_args(argv)

    rom_path = pathlib.Path(args.rom)
    rom = bytearray(rom_path.read_bytes())

    changes: dict = {}
    for pair in args.sets:
        if "=" not in pair:
            raise SystemExit(f"--set expects key=value, got {pair!r}")
        key, raw = pair.split("=", 1)
        changes[key.strip()] = int(raw.strip(), 0)
    if not changes:
        parser.error("no --set change given")

    if args.window is not None:
        offset = args.window
        applied = write_action_entry_at(rom, offset, changes)
    else:
        if args.sprite is None:
            parser.error("--sprite or --window is required")
        offset = entry_offset(args.sprite, args.action)
        applied = write_sprite_action(rom, args.sprite, args.action, changes)

    if args.out:
        out_path = pathlib.Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(bytes(rom))

    readback = read_action_entry_at(rom, offset)
    report = {"applied": applied, "read_back": readback}
    if args.json:
        write_json(args.json, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
