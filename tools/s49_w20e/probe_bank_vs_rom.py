#!/usr/bin/env python3
"""E4 step 1: compare the reverse line's positions/bank.json against the ROM bytes.

Read-only on every tree.  Prints, for a few (group, variant) pairs, the
formation record hex from both sources so the divergence is explicit.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
BANK = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\sequel\content\positions\bank.json")

POSITION_TABLE_FILE = 0x5461C4
GROUP_STRIDE = 0x1AAC
VARIANT_STRIDE = 0x08E4
RECORD_STRIDE = 0x00B8
RECORD_HEADER = 4


def record_offset(group_id: int, variant_id: int, record_id: int) -> int:
    return (
        POSITION_TABLE_FILE
        + group_id * GROUP_STRIDE
        + variant_id * VARIANT_STRIDE
        + RECORD_HEADER
        + record_id * RECORD_STRIDE
    )


def main() -> int:
    rom = ROM.read_bytes()
    bank = json.loads(BANK.read_text(encoding="utf-8"))

    print("=" * 78)
    print("bank meta")
    print("=" * 78)
    for key in ("version", "table_offset_hex", "entry_size", "entry_count", "verification", "evidence"):
        print(f"  {key} = {bank.get(key)!r}")
    fmt = bank.get("format", {})
    print(f"  format.address_formula = {fmt.get('address_formula')!r}")
    print(f"  format.group_count = {fmt.get('group_count')}  variant_count = {fmt.get('variant_count')}")
    entries = bank["entries"]
    print(f"  entries len = {len(entries)}")
    sample = entries[0]
    print(f"  entry keys = {sorted(sample.keys())}")

    by_key = {}
    for row in entries:
        by_key[(row["group_id"], row["variant_id"], row["record_id"])] = row

    for group, variant in ((14, 0), (14, 1), (14, 2)):
        print()
        print("=" * 78)
        print(f"group {group} variant {variant}")
        print("=" * 78)
        for rec in range(12):
            off = record_offset(group, variant, rec)
            rom_raw = rom[off : off + RECORD_STRIDE]
            bank_raw = bytes.fromhex(by_key[(group, variant, rec)]["raw_hex"])
            same = rom_raw == bank_raw
            print(
                f"  rec {rec:2d} off=0x{off:06X} same_as_bank={same} "
                f"be_u16@0x0C={int.from_bytes(rom_raw[0x0C:0x0E], 'little'):5d} "
                f"bank_be={by_key[(group, variant, rec)].get('battle_experience')!r}"
            )
            print(f"        rom  raw = {rom_raw[:0x20].hex()}")
            print(f"        bank raw = {bank_raw[:0x20].hex()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
