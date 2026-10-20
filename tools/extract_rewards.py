#!/usr/bin/env python3
"""Reward table `0x59EAE0` — per-battle loot, decoded.

The third-party package expands this table to 256 entries of 24 bytes and
writes only the first fields of each entry.  The layout below is derived from
the ROM's own data, not from their source:

    +0  u16   金币          (50..500, mode 200)
    +2  u16   奖励/强化点   (25..400, mode 200)
    +4  u16   档位/类型     (1..15, mode 8)
    +6  u16[] (忍具 id << 8) | 小整数
              高字节 = 忍具名表 `0x599634` 的条目 id（1..93）
              低字节 = 0 / 1 / 2，语义待定（数量或档位）

Evidence for the tail layout:
  * across all 77 populated entries, 326 of 328 tail values have a high byte
    inside 1..93 and a low byte in 0..2;
  * the 48 distinct high bytes are all real 忍具 ids (十字手里剑 … 超万能丸);
  * the third-party writer emits `put(reward+6, [1, 73])` for "item 73 × 1",
    which is exactly this encoding with id 73 and low byte 1.

Usage:
    python tools/extract_rewards.py
    python tools/extract_rewards.py --json build/rewards.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools import text_codec  # noqa: E402

REWARDS = 0x59EAE0
ENTRY_SIZE = 24
ORIGINAL_ENTRIES = 112
NINJUTSU_TABLE = 0x599634
NINJUTSU_COUNT = 93


def read_name_table(rom: bytes, base: int, count: int, mapping) -> list[str]:
    """Read a ROM-side name table (u32 pointer per entry) into Chinese names."""
    names = []
    for i in range(1, count + 1):
        ptr = struct.unpack_from("<I", rom, base + i * 4)[0] - 0x08000000
        if not (0 <= ptr < len(rom)):
            names.append("")
            continue
        text, _ = text_codec.decode_tokens(rom, ptr, mapping)
        names.append(text.replace("\n", "").strip())
    return names


def decode_entry(raw: bytes, names: list[str]) -> dict:
    gold, bonus, tier = struct.unpack_from("<HHH", raw, 0)
    items = []
    for off in range(6, ENTRY_SIZE, 2):
        value = struct.unpack_from("<H", raw, off)[0]
        if value == 0:
            break
        item_id, low = value >> 8, value & 0xFF
        items.append({
            "item_id": item_id,
            "low": low,
            "name": names[item_id - 1] if 1 <= item_id <= len(names) else "",
            "raw": value,
        })
    return {
        "gold": gold,
        "bonus": bonus,
        "tier": tier,
        "items": items,
        "tail_words": raw[6:ENTRY_SIZE].hex(),
    }


def read_entries(rom: bytes, mapping, count: int = ORIGINAL_ENTRIES) -> list[dict]:
    names = read_name_table(rom, NINJUTSU_TABLE, NINJUTSU_COUNT, mapping)
    out = []
    for i in range(count):
        base = REWARDS + i * ENTRY_SIZE
        raw = rom[base:base + ENTRY_SIZE]
        entry = {
            "index": i,
            "offset": base,
            "raw_hex": raw.hex(),
            "is_zero": raw == b"\x00" * ENTRY_SIZE,
        }
        if not entry["is_zero"]:
            entry.update(decode_entry(raw, names))
        out.append(entry)
    return out


def layout_evidence(entries: list[dict]) -> dict:
    """Quantify the (item<<8 | low) tail layout claim."""
    live = [e for e in entries if not e["is_zero"]]
    pairs = [it for e in live for it in e["items"]]
    lows = Counter(it["low"] for it in pairs)
    ids = Counter(it["item_id"] for it in pairs)
    return {
        "populated_entries": len(live),
        "zero_entries": len(entries) - len(live),
        "tail_pairs": len(pairs),
        "pairs_with_id_in_1_93": sum(1 for it in pairs if 1 <= it["item_id"] <= 93),
        "pairs_with_low_in_0_2": sum(1 for it in pairs if it["low"] <= 2),
        "distinct_item_ids": len(ids),
        "distinct_item_id_min": min(ids) if ids else 0,
        "distinct_item_id_max": max(ids) if ids else 0,
        "low_byte_distribution": dict(sorted(lows.items())),
        "gold_range": [min(e["gold"] for e in live), max(e["gold"] for e in live)] if live else [],
        "bonus_range": [min(e["bonus"] for e in live), max(e["bonus"] for e in live)] if live else [],
        "tier_values": sorted({e["tier"] for e in live}),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--all", action="store_true", help="print every populated entry")
    args = ap.parse_args()

    rom_path = text_codec.resolve_rom(args.rom)
    rom = rom_path.read_bytes()
    mapping, _ = text_codec.load_mapping(rom_path)
    entries = read_entries(rom, mapping)
    evidence = layout_evidence(entries)

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps({
                "rom": str(rom_path),
                "table": hex(REWARDS),
                "entry_size": ENTRY_SIZE,
                "original_entries": ORIGINAL_ENTRIES,
                "layout_evidence": evidence,
                "entries": entries,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"table {hex(REWARDS)}   entry {ENTRY_SIZE} bytes   "
          f"{ORIGINAL_ENTRIES} entries")
    print(f"populated {evidence['populated_entries']}   zero {evidence['zero_entries']}")
    print()
    print("tail layout evidence:")
    print(f"  pairs total                     : {evidence['tail_pairs']}")
    print(f"  high byte inside 1..93 (忍具 id) : {evidence['pairs_with_id_in_1_93']}")
    print(f"  low byte in 0..2                : {evidence['pairs_with_low_in_0_2']}")
    print(f"  distinct item ids               : {evidence['distinct_item_ids']} "
          f"({evidence['distinct_item_id_min']}..{evidence['distinct_item_id_max']})")
    print(f"  low byte distribution           : {evidence['low_byte_distribution']}")
    print(f"  gold range / bonus range        : {evidence['gold_range']} / "
          f"{evidence['bonus_range']}")
    print()
    shown = [e for e in entries if not e["is_zero"]]
    if not args.all:
        shown = shown[:12]
    print(f"{'idx':>4} {'gold':>5} {'bonus':>6} {'tier':>4}  rewards")
    for e in shown:
        items = " | ".join(f"{it['name'] or '?'}x{it['low']}" for it in e["items"])
        print(f"{e['index']:>4} {e['gold']:>5} {e['bonus']:>6} {e['tier']:>4}  {items}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
