#!/usr/bin/env python3
"""Wave 22 / D4 -- locate the original reward table and every code reference to it.

Reads the original ROM read-only, dumps the 112 reward records at 0x59EAE0 and
searches the whole ROM for the table address (both the raw ROM offset and the
GBA virtual address) so the consumer code can be located.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

ROM_BASE = 0x08000000
REWARD_TABLE_OFFSET = 0x59EAE0
REWARD_RECORD_COUNT = 112
REWARD_RECORD_SIZE = 24

DEFAULT_ROM = Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_BANK = Path(
    r"D:\Shell\Github\gba-naruto-butano\sequel\content\battle-results\bank.json"
)


def find_all(haystack: bytes, needle: bytes) -> list[int]:
    out: list[int] = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx < 0:
            return out
        out.append(idx)
        start = idx + 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument(
        "--out", type=Path, default=Path(r"D:\Github\gba-naruto\build\w22-d4\rom-reward-table.json")
    )
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    sha = hashlib.sha256(rom).hexdigest()

    # ---- 1. dump the reward table straight out of the ROM -------------------
    table = rom[
        REWARD_TABLE_OFFSET : REWARD_TABLE_OFFSET + REWARD_RECORD_COUNT * REWARD_RECORD_SIZE
    ]
    records = []
    for i in range(REWARD_RECORD_COUNT):
        blob = table[i * REWARD_RECORD_SIZE : (i + 1) * REWARD_RECORD_SIZE]
        mission, bonus, limit = struct.unpack_from("<HHH", blob, 0)
        words = struct.unpack_from("<9H", blob, 6)
        records.append(
            {
                "record_id": i,
                "rom_offset": REWARD_TABLE_OFFSET + i * REWARD_RECORD_SIZE,
                "rom_offset_hex": f"0x{REWARD_TABLE_OFFSET + i * REWARD_RECORD_SIZE:06X}",
                "mission_experience": mission,
                "round_bonus_experience": bonus,
                "round_limit": limit,
                "postbattle_words": list(words),
                "raw_hex": blob.hex(),
            }
        )

    # ---- 2. find every reference to the table --------------------------------
    refs: dict[str, list[int]] = {}
    for label, needle in (
        ("rom_offset_le", struct.pack("<I", REWARD_TABLE_OFFSET)),
        ("gba_addr_le", struct.pack("<I", ROM_BASE + REWARD_TABLE_OFFSET)),
        ("rom_offset_be", struct.pack(">I", REWARD_TABLE_OFFSET)),
        ("gba_addr_be", struct.pack(">I", ROM_BASE + REWARD_TABLE_OFFSET)),
    ):
        hits = find_all(rom, needle)
        refs[label] = [
            {
                "rom_offset": h,
                "rom_offset_hex": f"0x{h:06X}",
                "gba_addr": f"0x{ROM_BASE + h:08X}",
                "context_hex": rom[max(0, h - 8) : h + 12].hex(),
            }
            for h in hits
        ]

    # ---- 3. cross-check against the bank.json used by the generator ---------
    bank_mismatches: list[dict] = []
    bank_records: list[dict] = []
    if args.bank.exists():
        bank = json.loads(args.bank.read_text(encoding="utf-8"))
        for row in bank["reward_records"]:
            bank_records.append(row)
            rom_row = records[row["record_id"]]
            for field in ("mission_experience", "round_bonus_experience", "round_limit"):
                if row[field] != rom_row[field]:
                    bank_mismatches.append(
                        {
                            "record_id": row["record_id"],
                            "field": field,
                            "bank": row[field],
                            "rom": rom_row[field],
                        }
                    )
            if list(row["postbattle_words"]) != list(rom_row["postbattle_words"]):
                bank_mismatches.append(
                    {
                        "record_id": row["record_id"],
                        "field": "postbattle_words",
                        "bank": row["postbattle_words"],
                        "rom": rom_row["postbattle_words"],
                    }
                )

    payload = {
        "schema": "konoha.s49-w22d4-rom-reward-table.v1",
        "rom_path": str(args.rom),
        "rom_sha256": sha,
        "reward_table": {
            "rom_offset": REWARD_TABLE_OFFSET,
            "rom_offset_hex": f"0x{REWARD_TABLE_OFFSET:06X}",
            "gba_addr": f"0x{ROM_BASE + REWARD_TABLE_OFFSET:08X}",
            "record_count": REWARD_RECORD_COUNT,
            "record_size": REWARD_RECORD_SIZE,
            "table_sha256": hashlib.sha256(table).hexdigest(),
        },
        "records": records,
        "references": refs,
        "bank_cross_check": {
            "bank_path": str(args.bank),
            "record_count": len(bank_records),
            "mismatch_count": len(bank_mismatches),
            "mismatches": bank_mismatches,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")

    print(f"rom sha256       : {sha}")
    print(f"reward table     : 0x{REWARD_TABLE_OFFSET:06X} ({REWARD_RECORD_COUNT} x {REWARD_RECORD_SIZE})")
    print(f"table sha256     : {payload['reward_table']['table_sha256']}")
    print(f"bank records     : {len(bank_records)}")
    print(f"bank mismatches  : {len(bank_mismatches)}")
    for label, hits in refs.items():
        print(f"refs[{label}]     : {len(hits)} -> {[h['rom_offset_hex'] for h in hits]}")
    # quick stats on the round_limit column
    limits = [r["round_limit"] for r in records]
    nonzero = [r for r in records if r["round_limit"]]
    print(f"round_limit!=0   : {len(nonzero)}/{REWARD_RECORD_COUNT}")
    print(f"round_limit set  : {sorted({r['round_limit'] for r in nonzero})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
