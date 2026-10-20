#!/usr/bin/env python3
"""Write-back path for the character template table (0x54241C) and neighbours.

The repository-wide write-back model is *copy a native entry, then overwrite
only the fields whose meaning is proven*.  Everything else is copied raw, so
an unknown byte is never damaged by an import.

Three ROM structures are covered here, all proved in
``notes/character-template-format-20261020.md``:

============================  ==============  ==========================
structure                    file offset     geometry
============================  ==============  ==========================
character template           0x54241C        0xB4 bytes / entry, id 1..62
per-character growth table    0x545068        0x10 bytes / entry, id 1..62
battle record table           0x545458        0x10 bytes / entry, 87 records
============================  ==============  ==========================

Known fields (everything else in the record stays untouched):

* template ``+0x01..+0x06``  six attribute base values (u8)
* template ``+0x08``         sub-attribute base value (u16)
* template ``+0x0A``         HP base value (u16)
* template ``+0x0C``         15 x (index, value, level gate, pad)
* template ``+0x48``         24 x (index, value, level gate, pad)
* template ``+0xA8``         9 x item/ninjutsu id (0 = empty)
* growth    ``+0x00..+0x0F`` 8 x u16 growth rates (x100)
* record    ``+0x04..+0x09`` 6 x byte fields that grow with the level
* record    ``+0x0C``        growth type (0..7)
* record    ``+0x0E``        u16 growth amount

Usage:
    python tools/import_character_template.py rom/base.gba --id 1
    python tools/import_character_template.py rom/base.gba --id 1 \\
        --set attr_a=12 --set hp_base=85 --out build/naruto.gba
    python tools/import_character_template.py rom/base.gba --id 1 \\
        --set entries2='[{"slot": 0, "index": 1, "value": 2}]'
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

# --- geometry ---------------------------------------------------------------

TEMPLATE_BASE = 0x54241C
TEMPLATE_STRIDE = 0xB4
TEMPLATE_ID_MIN = 1
TEMPLATE_ID_MAX = 62

GROWTH_BASE = 0x545068
GROWTH_STRIDE = 0x10

BATTLE_RECORD_BASE = 0x545458
BATTLE_RECORD_STRIDE = 0x10
BATTLE_RECORD_COUNT = 87

# template header fields: offset -> (name, size)
TEMPLATE_FIELDS: tuple[tuple[int, str, int], ...] = (
    (0x01, "attr_a", 1),
    (0x02, "attr_b", 1),
    (0x03, "attr_c", 1),
    (0x04, "attr_d", 1),
    (0x05, "attr_e", 1),
    (0x06, "attr_f", 1),
    (0x08, "sub_attr", 2),
    (0x0A, "hp_base", 2),
)

# (offset, count) of the two 4-byte entry areas and the item list
ENTRY_AREA_1 = (0x0C, 15)
ENTRY_AREA_2 = (0x48, 24)
ITEM_LIST = (0xA8, 9)

# growth table: u16 index -> name
GROWTH_FIELDS: tuple[tuple[int, str], ...] = (
    (0, "hp_growth"),
    (1, "attr_f_growth"),
    (2, "attr_a_growth"),
    (3, "attr_b_growth"),
    (4, "attr_c_growth"),
    (5, "attr_d_growth"),
    (6, "attr_e_growth"),
    (7, "unused"),
)

# battle record: offset -> (name, size)
RECORD_FIELDS: tuple[tuple[int, str, int], ...] = (
    (0x04, "grow_0", 1),
    (0x05, "grow_1", 1),
    (0x06, "grow_2", 1),
    (0x07, "grow_3", 1),
    (0x08, "grow_4", 1),
    (0x09, "grow_5", 1),
    (0x0C, "growth_type", 1),
    (0x0E, "growth_amount", 2),
)

ENTRY_AREA_FIELDS = ("index", "value", "gate")


class WriteBackError(ValueError):
    """Raised when an author change is not representable in the ROM record."""


# --- helpers ----------------------------------------------------------------

def _u(raw: bytes, offset: int, size: int) -> int:
    return int.from_bytes(raw[offset:offset + size], "little")


def _put(buf: bytearray, offset: int, size: int, value: int) -> None:
    if not 0 <= value < (1 << (size * 8)):
        raise WriteBackError(
            f"value {value} does not fit into {size} byte(s) at 0x{offset:X}"
        )
    buf[offset:offset + size] = value.to_bytes(size, "little")


def template_offset(character_id: int) -> int:
    if not TEMPLATE_ID_MIN <= character_id <= TEMPLATE_ID_MAX:
        raise WriteBackError(
            f"character id {character_id} outside {TEMPLATE_ID_MIN}..{TEMPLATE_ID_MAX}"
        )
    return TEMPLATE_BASE + character_id * TEMPLATE_STRIDE


def growth_offset(character_id: int) -> int:
    if not TEMPLATE_ID_MIN <= character_id <= TEMPLATE_ID_MAX:
        raise WriteBackError(
            f"character id {character_id} outside {TEMPLATE_ID_MIN}..{TEMPLATE_ID_MAX}"
        )
    return GROWTH_BASE + character_id * GROWTH_STRIDE


def battle_record_offset(index: int) -> int:
    if not 0 <= index < BATTLE_RECORD_COUNT:
        raise WriteBackError(f"battle record {index} outside 0..{BATTLE_RECORD_COUNT - 1}")
    return BATTLE_RECORD_BASE + index * BATTLE_RECORD_STRIDE


# --- read -------------------------------------------------------------------

def read_character_template(rom: bytes, character_id: int) -> dict:
    """Read the *known* fields of one character template entry."""
    off = template_offset(character_id)
    raw = bytes(rom[off:off + TEMPLATE_STRIDE])
    if len(raw) != TEMPLATE_STRIDE:
        raise WriteBackError("ROM too small for the character template table")
    out: dict = {"id": character_id, "offset": off}
    for offset, name, size in TEMPLATE_FIELDS:
        out[name] = _u(raw, offset, size)
    for area, (area_off, count) in (("entries1", ENTRY_AREA_1), ("entries2", ENTRY_AREA_2)):
        out[area] = [
            {
                "index": _u(raw, area_off + 4 * i, 1),
                "value": _u(raw, area_off + 4 * i + 1, 1),
                "gate": _u(raw, area_off + 4 * i + 2, 1),
            }
            for i in range(count)
        ]
    item_off, item_count = ITEM_LIST
    out["items"] = [_u(raw, item_off + i, 1) for i in range(item_count)]
    return out


def read_growth(rom: bytes, character_id: int) -> dict:
    """Read the per-character growth table entry (8 u16)."""
    off = growth_offset(character_id)
    raw = bytes(rom[off:off + GROWTH_STRIDE])
    out: dict = {"id": character_id, "offset": off}
    for index, name in GROWTH_FIELDS:
        out[name] = _u(raw, index * 2, 2)
    return out


def read_battle_record(rom: bytes, index: int) -> dict:
    """Read the known fields of one 16-byte battle record."""
    off = battle_record_offset(index)
    raw = bytes(rom[off:off + BATTLE_RECORD_STRIDE])
    out: dict = {"index": index, "offset": off}
    for offset, name, size in RECORD_FIELDS:
        out[name] = _u(raw, offset, size)
    return out


# --- write ------------------------------------------------------------------

def write_character_template(rom: bytearray, character_id: int, changes: dict) -> dict:
    """Apply author changes to one template entry, in place.

    The native 0xB4 entry is copied verbatim and only the named fields are
    overwritten.  Returns the normalised author input so the caller can
    compare it against a fresh read-back.
    """
    off = template_offset(character_id)
    native = bytes(rom[off:off + TEMPLATE_STRIDE])
    if len(native) != TEMPLATE_STRIDE:
        raise WriteBackError("ROM too small for the character template table")
    buf = bytearray(native)
    applied: dict = {"id": character_id, "offset": off}

    for offset, name, size in TEMPLATE_FIELDS:
        if name not in changes:
            continue
        value = int(changes[name])
        _put(buf, offset, size, value)
        applied[name] = value

    for area, (area_off, count) in (("entries1", ENTRY_AREA_1), ("entries2", ENTRY_AREA_2)):
        if area not in changes:
            continue
        rows = changes[area]
        if not isinstance(rows, list):
            raise WriteBackError(f"{area} must be a list of slot patches")
        patched = []
        for row in rows:
            slot = int(row["slot"])
            if not 0 <= slot < count:
                raise WriteBackError(f"{area} slot {slot} outside 0..{count - 1}")
            base = area_off + 4 * slot
            entry = {}
            for field_index, field in enumerate(ENTRY_AREA_FIELDS):
                if field in row:
                    value = int(row[field])
                    _put(buf, base + field_index, 1, value)
                    entry[field] = value
                else:
                    entry[field] = _u(native, base + field_index, 1)
            patched.append({"slot": slot, **entry})
        applied[area] = patched

    if "items" in changes:
        rows = changes["items"]
        if not isinstance(rows, list):
            raise WriteBackError("items must be a list of slot patches")
        item_off, item_count = ITEM_LIST
        patched = []
        for row in rows:
            slot = int(row["slot"])
            if not 0 <= slot < item_count:
                raise WriteBackError(f"items slot {slot} outside 0..{item_count - 1}")
            value = int(row["id"])
            _put(buf, item_off + slot, 1, value)
            patched.append({"slot": slot, "id": value})
        applied["items"] = patched

    unknown = set(changes) - {
        "id", "offset", *(name for _, name, _ in TEMPLATE_FIELDS),
        "entries1", "entries2", "items",
    }
    if unknown:
        raise WriteBackError(f"unknown character template fields: {sorted(unknown)}")

    rom[off:off + TEMPLATE_STRIDE] = buf
    return applied


def write_growth(rom: bytearray, character_id: int, changes: dict) -> dict:
    """Apply author changes to one growth-table entry (8 u16)."""
    off = growth_offset(character_id)
    native = bytes(rom[off:off + GROWTH_STRIDE])
    buf = bytearray(native)
    applied: dict = {"id": character_id, "offset": off}
    for index, name in GROWTH_FIELDS:
        if name not in changes:
            continue
        value = int(changes[name])
        _put(buf, index * 2, 2, value)
        applied[name] = value
    unknown = set(changes) - {"id", "offset", *(name for _, name in GROWTH_FIELDS)}
    if unknown:
        raise WriteBackError(f"unknown growth fields: {sorted(unknown)}")
    rom[off:off + GROWTH_STRIDE] = buf
    return applied


def write_battle_record(rom: bytearray, index: int, changes: dict) -> dict:
    """Apply author changes to one 16-byte battle record."""
    off = battle_record_offset(index)
    native = bytes(rom[off:off + BATTLE_RECORD_STRIDE])
    buf = bytearray(native)
    applied: dict = {"index": index, "offset": off}
    for offset, name, size in RECORD_FIELDS:
        if name not in changes:
            continue
        value = int(changes[name])
        if name == "growth_type" and not 0 <= value <= 7:
            raise WriteBackError(f"growth_type {value} outside 0..7")
        _put(buf, offset, size, value)
        applied[name] = value
    unknown = set(changes) - {"index", "offset", *(name for _, name, _ in RECORD_FIELDS)}
    if unknown:
        raise WriteBackError(f"unknown battle record fields: {sorted(unknown)}")
    rom[off:off + BATTLE_RECORD_STRIDE] = buf
    return applied


def _parse_changes(pairs: list[str]) -> dict:
    changes: dict = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--set expects key=value, got {pair!r}")
        key, raw = pair.split("=", 1)
        key = key.strip()
        raw = raw.strip()
        if raw.startswith(("[", "{")):
            try:
                path = pathlib.Path(raw)
            except (OSError, ValueError):
                path = None
            if path is not None and path.is_file():
                raw = path.read_text(encoding="utf-8")
            try:
                changes[key] = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SystemExit(
                    f"--set {key}= expects inline JSON or a JSON file path ({exc})"
                )
        else:
            changes[key] = int(raw, 0)
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rom", help="ROM path (a copy is patched, never the original)")
    parser.add_argument("--id", type=int, default=1, help="character id (1..62)")
    parser.add_argument("--record", type=int, help="battle record index (0..86)")
    parser.add_argument("--growth", action="store_true", help="patch the growth table")
    parser.add_argument("--set", action="append", default=[], dest="sets",
                        help="field=value change (repeatable)")
    parser.add_argument("--out", help="write the patched ROM copy here")
    parser.add_argument("--json", help="write the read-back report here")
    args = parser.parse_args(argv)

    rom_path = pathlib.Path(args.rom)
    rom = bytearray(rom_path.read_bytes())
    changes = _parse_changes(args.sets)
    if not changes:
        parser.error("no --set change given")

    if args.record is not None:
        applied = write_battle_record(rom, args.record, changes)
    elif args.growth:
        applied = write_growth(rom, args.id, changes)
    else:
        applied = write_character_template(rom, args.id, changes)

    if args.out:
        out_path = pathlib.Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(bytes(rom))

    if args.record is not None:
        readback = read_battle_record(rom, args.record)
    elif args.growth:
        readback = read_growth(rom, args.id)
    else:
        readback = read_character_template(rom, args.id)

    report = {"applied": applied, "read_back": readback}
    if args.json:
        write_json(args.json, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
