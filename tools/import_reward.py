#!/usr/bin/env python3
"""Write-back path for the battle reward table (0x59EAE0).

The 24-byte reward record layout is proved from native code in
``notes/reward-and-rules-semantics-20261020.md`` and
``notes/evidence/char-reward-fields-20261020.md``:

    +0x00 u16  gold            (0x080893FC ldrh / 0x08089400 strh)
    +0x02 u16  upgrade_points  (0x0808940C ldrh / 0x0808940E strh)
    +0x04 u16  tier            (0x08089406 ldrh / 0x08089408 cmp)
    +0x06      eight 2-byte tail slots; each slot is
                low byte  = category tag (0 忍具 / 1 强化素材 / 2 认识卡 / 3 技术)
                high byte = item id, 0 terminates the list
    +0x16 u8   always 0, never read by any consumer -> copied raw
    +0x17 u8   always 0, never read by any consumer -> copied raw

The table holds 112 records at a 24-byte stride.  The category -> name-table
map is the ROM's own 4-slot pointer table at ``0x59F5E0`` (loaded by
``0x0808A02A``, indexed with the tail byte), so the writer can check an
author-supplied item id against the real capacity of that category's name
table instead of a hand-written bound.

Write-back model: copy the native record, overwrite only the fields the
author names, keep the unknown bytes (``+0x16`` / ``+0x17``) raw.

Usage:
    python tools/import_reward.py rom/base.gba --index 0
    python tools/import_reward.py rom/base.gba --index 0 \\
        --set gold=500 --set tier=12 \\
        --set slots='[{"category":0,"item_id":3},{"category":1,"item_id":5}]' \\
        --out build/naruto.gba
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

REWARD_BASE = 0x59EAE0
REWARD_STRIDE = 24
REWARD_ENTRY_COUNT = 112

REWARD_HEAD_FIELDS: tuple[tuple[int, str, int], ...] = (
    (0x00, "gold", 2),
    (0x02, "upgrade_points", 2),
    (0x04, "tier", 2),
)

REWARD_TAIL_OFFSET = 0x06
REWARD_TAIL_SLOTS = 8
REWARD_TAIL_END = REWARD_TAIL_OFFSET + REWARD_TAIL_SLOTS * 2
REWARD_RESERVED = (0x16, 0x17)

REWARD_CATEGORY_TABLE = 0x59F5E0
REWARD_CATEGORY_COUNT = 4
REWARD_CATEGORY_NAMES = ("忍具", "强化素材", "认识卡", "技术")

ROM_BASE = 0x08000000
ROM_POINTER_MIN = 0x08000000
ROM_POINTER_MAX = 0x085FFFFF


class WriteBackError(ValueError):
    """Raised when an author change is not representable in the ROM record."""


def record_offset(index: int) -> int:
    if not 0 <= index < REWARD_ENTRY_COUNT:
        raise WriteBackError(
            f"reward index {index} outside 0..{REWARD_ENTRY_COUNT - 1}")
    return REWARD_BASE + index * REWARD_STRIDE


def category_name_table(rom: bytes, category: int) -> int | None:
    """The name table the ROM's own category->name-table table selects."""
    if not 0 <= category < REWARD_CATEGORY_COUNT:
        return None
    off = REWARD_CATEGORY_TABLE + category * 4
    if off + 4 > len(rom):
        return None
    table = int.from_bytes(rom[off:off + 4], "little")
    return table or None


def name_table_capacity(rom: bytes, table: int | None, limit: int = 512) -> int:
    """Number of consecutive ROM text pointers at ``table``."""
    if not table:
        return 0
    start = table - ROM_BASE
    count = 0
    for i in range(limit):
        off = start + i * 4
        if off < 0 or off + 4 > len(rom):
            break
        value = int.from_bytes(rom[off:off + 4], "little")
        if not (ROM_POINTER_MIN <= value <= ROM_POINTER_MAX):
            break
        count += 1
    return count


def _u16(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 2], "little")


def read_reward_record(rom: bytes, index: int) -> dict:
    """Read one 24-byte reward record with every field named."""
    off = record_offset(index)
    raw = bytes(rom[off:off + REWARD_STRIDE])
    if len(raw) != REWARD_STRIDE:
        raise WriteBackError("ROM too small for the reward table")
    out: dict = {"index": index, "offset": off}
    for field_off, name, size in REWARD_HEAD_FIELDS:
        out[name] = _u16(raw, field_off)
    slots = []
    for slot in range(REWARD_TAIL_SLOTS):
        slot_off = REWARD_TAIL_OFFSET + slot * 2
        value = _u16(raw, slot_off)
        item_id = (value >> 8) & 0xFF
        slots.append({
            "slot": slot,
            "category_tag": value & 0xFF,
            "item_id": item_id,
            "empty": item_id == 0,
        })
    out["slots"] = slots
    out["reserved"] = {f"0x{REWARD_RESERVED[0]:02X}": raw[REWARD_RESERVED[0]],
                       f"0x{REWARD_RESERVED[1]:02X}": raw[REWARD_RESERVED[1]]}
    return out


def _normalise_slots(rom: bytes, raw_slots: list) -> list[dict]:
    """Validate the author's slot list against the real name tables."""
    if not isinstance(raw_slots, list):
        raise WriteBackError("slots must be a list")
    if len(raw_slots) > REWARD_TAIL_SLOTS:
        raise WriteBackError(
            f"at most {REWARD_TAIL_SLOTS} tail slots fit in a reward record")
    out: list[dict] = []
    for item in raw_slots:
        if isinstance(item, dict):
            category = item.get("category", item.get("category_tag"))
            item_id = item.get("item_id", item.get("id"))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            category, item_id = item
        else:
            raise WriteBackError(
                "each slot must be {category, item_id} or a (category, item_id) pair")
        if category is None or item_id is None:
            raise WriteBackError("each slot needs a category and an item id")
        category = int(category)
        item_id = int(item_id)
        if not 0 <= category < REWARD_CATEGORY_COUNT:
            raise WriteBackError(
                f"category {category} outside 0..{REWARD_CATEGORY_COUNT - 1}")
        if not 1 <= item_id <= 0xFF:
            raise WriteBackError(
                f"item id {item_id} outside 1..255 (0 terminates the slot list)")
        table = category_name_table(rom, category)
        capacity = name_table_capacity(rom, table)
        if capacity and item_id >= capacity:
            raise WriteBackError(
                f"item id {item_id} is outside the {capacity}-entry "
                f"{REWARD_CATEGORY_NAMES[category]} name table "
                f"(0x{table:08X})")
        out.append({"category_tag": category, "item_id": item_id})
    return out


def write_reward_record(rom: bytearray, index: int, changes: dict) -> dict:
    """Apply author changes to one reward record, in place.

    The native record is copied verbatim; only the named fields are
    overwritten.  The tail slot list is a *single* field: when the author
    supplies it, the whole list is rewritten and the terminator moves with
    it, so the slots past the author's list are zeroed.
    """
    off = record_offset(index)
    native = bytes(rom[off:off + REWARD_STRIDE])
    if len(native) != REWARD_STRIDE:
        raise WriteBackError("ROM too small for the reward table")
    buf = bytearray(native)
    applied: dict = {"index": index}
    allowed = {name for _, name, _ in REWARD_HEAD_FIELDS} | {"slots"}
    unknown = set(changes) - allowed
    if unknown:
        raise WriteBackError(f"unknown reward fields: {sorted(unknown)}")
    for field_off, name, size in REWARD_HEAD_FIELDS:
        if name not in changes:
            continue
        value = int(changes[name])
        if not 0 <= value <= 0xFFFF:
            raise WriteBackError(f"{name} {value} outside 0..65535")
        buf[field_off:field_off + size] = value.to_bytes(2, "little")
        applied[name] = value
    if "slots" in changes:
        slots = _normalise_slots(bytes(rom), changes["slots"])
        for slot in range(REWARD_TAIL_SLOTS):
            slot_off = REWARD_TAIL_OFFSET + slot * 2
            if slot < len(slots):
                value = (slots[slot]["item_id"] << 8) | slots[slot]["category_tag"]
            else:
                value = 0
            buf[slot_off:slot_off + 2] = value.to_bytes(2, "little")
        applied["slots"] = slots
    if len(applied) == 1:
        raise WriteBackError("no reward field to write")
    rom[off:off + REWARD_STRIDE] = buf
    return applied


# --- CLI --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rom", help="ROM path (a copy is patched, never the original)")
    parser.add_argument("--index", type=int, help="reward record index (0..111)")
    parser.add_argument("--set", action="append", default=[], dest="sets",
                        help="field=value change (repeatable); slots takes JSON")
    parser.add_argument("--out", help="write the patched ROM copy here")
    parser.add_argument("--json", help="write the read-back report here")
    args = parser.parse_args(argv)

    rom_path = pathlib.Path(args.rom)
    rom = bytearray(rom_path.read_bytes())
    if args.index is None:
        parser.error("--index is required")

    changes: dict = {}
    for pair in args.sets:
        if "=" not in pair:
            raise SystemExit(f"--set expects key=value, got {pair!r}")
        key, raw = pair.split("=", 1)
        key = key.strip()
        if key == "slots":
            try:
                changes[key] = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SystemExit(
                    f"--set slots expects a JSON list, got {raw!r}: {exc}"
                ) from exc
        else:
            changes[key] = int(raw.strip(), 0)
    if not changes:
        parser.error("no --set change given")

    applied = write_reward_record(rom, args.index, changes)
    if args.out:
        out_path = pathlib.Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(bytes(rom))

    readback = read_reward_record(rom, args.index)
    report = {"applied": applied, "read_back": readback}
    if args.json:
        write_json(args.json, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
