#!/usr/bin/env python3
"""Wave 22 / D4 -- dump a character's passive list and resolve it against the
original passive definition table.

Character definition table : ROM 0x54241C, 63 records, stride 0xB4
  +0      active flag
  +0C..47 15 "main" slots (4 bytes each)
  +48..A7 24 "secondary" slots (4 bytes each)  <- the passive list
  +A8..B0 9 filter candidate ids

Secondary slot: [0] u8 passive id, [1] u8 runtime state/level,
                [2] u8 unlock level, [3] u8 reserved

Passive definition table    : ROM 0x5459C8, stride 12
  +0 u8 type, +2 u16 value_a, +4 u16 value_d, +6 u16 value_b, +8 u16 value_c
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

CHAR_DEF_OFFSET = 0x54241C
CHAR_DEF_STRIDE = 0xB4
PASSIVE_TABLE_OFFSET = 0x5459C8
PASSIVE_RECORD_SIZE = 12


def s16(v: int) -> int:
    return v - 0x10000 if v & 0x8000 else v


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--chars", type=lambda x: int(x, 0), nargs="+", required=True)
    parser.add_argument(
        "--out", type=Path, default=Path(r"D:\Github\gba-naruto\build\w22-d4\char-passives.json")
    )
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    out_chars = []
    for cid in args.chars:
        base = CHAR_DEF_OFFSET + cid * CHAR_DEF_STRIDE
        rec = rom[base : base + CHAR_DEF_STRIDE]
        slots = []
        for i in range(24):
            off = 0x48 + i * 4
            pid, state, unlock, reserved = rec[off : off + 4]
            pbase = PASSIVE_TABLE_OFFSET + pid * PASSIVE_RECORD_SIZE
            prec = rom[pbase : pbase + PASSIVE_RECORD_SIZE]
            ptype = prec[0]
            value_a, value_d, value_b, value_c = struct.unpack_from("<4H", prec, 2)
            slots.append(
                {
                    "slot": i,
                    "passive_id": pid,
                    "state_byte": state,
                    "unlock_level": unlock,
                    "reserved": reserved,
                    "passive_type": ptype,
                    "passive_type_hex": f"0x{ptype:02X}",
                    "value_a": value_a,
                    "value_a_signed": s16(value_a),
                    "value_b": value_b,
                    "value_c": value_c,
                    "value_d": value_d,
                    "is_0x15": ptype == 0x15,
                }
            )
        out_chars.append(
            {
                "character_id": cid,
                "rom_offset": base,
                "rom_offset_hex": f"0x{base:06X}",
                "active": rec[0],
                "raw_hex": rec.hex(),
                "secondary_slots": slots,
                "has_0x15": any(s["is_0x15"] for s in slots),
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "schema": "konoha.s49-w22d4-char-passives.v1",
                "char_def_offset": CHAR_DEF_OFFSET,
                "passive_table_offset": PASSIVE_TABLE_OFFSET,
                "characters": out_chars,
            },
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )

    for c in out_chars:
        print(f"== character {c['character_id']} @ {c['rom_offset_hex']} (active={c['active']}) ==")
        for s in c["secondary_slots"]:
            if s["passive_id"] == 0 and s["state_byte"] == 0:
                continue
            mark = "  <<< TYPE 0x15" if s["is_0x15"] else ""
            print(
                f"   slot {s['slot']:2d}: id={s['passive_id']:3d} type=0x{s['passive_type']:02X} "
                f"state={s['state_byte']:3d} unlock={s['unlock_level']:3d} "
                f"value_a={s['value_a']}({s['value_a_signed']}) value_b={s['value_b']} "
                f"value_c={s['value_c']} value_d={s['value_d']}{mark}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
