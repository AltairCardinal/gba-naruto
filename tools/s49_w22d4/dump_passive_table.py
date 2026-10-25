#!/usr/bin/env python3
"""Wave 22 / D4 -- dump the original passive definition table.

Table base  : ROM 0x5459C8 (GBA 0x085459C8)
Record size : 12 bytes
Record      : +0 u8  type (passive target type)
              +1 u8  pad
              +2 u16 value_a  (base)
              +4 u16 value_d  (base)
              +6 u16 value_b  (per-level increment)
              +8 u16 value_c  (per-level increment)

The unit's passive list lives at unit+0x50, 4 bytes per slot:
  [0] u8 passive id, [1] u8 level, [2..3] unused
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

ROM_BASE = 0x08000000
PASSIVE_TABLE_OFFSET = 0x5459C8
PASSIVE_RECORD_SIZE = 12


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--count", type=int, default=0x60)
    parser.add_argument(
        "--out", type=Path, default=Path(r"D:\Github\gba-naruto\build\w22-d4\passive-table.json")
    )
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    records = []
    for i in range(args.count):
        off = PASSIVE_TABLE_OFFSET + i * PASSIVE_RECORD_SIZE
        blob = rom[off : off + PASSIVE_RECORD_SIZE]
        if len(blob) < PASSIVE_RECORD_SIZE:
            break
        ptype = blob[0]
        value_a, value_d, value_b, value_c = struct.unpack_from("<4H", blob, 2)
        records.append(
            {
                "passive_id": i,
                "rom_offset": off,
                "rom_offset_hex": f"0x{off:06X}",
                "type": ptype,
                "type_hex": f"0x{ptype:02X}",
                "value_a": value_a,
                "value_a_signed": value_a - 0x10000 if value_a & 0x8000 else value_a,
                "value_d": value_d,
                "value_d_signed": value_d - 0x10000 if value_d & 0x8000 else value_d,
                "value_b": value_b,
                "value_c": value_c,
                "raw_hex": blob.hex(),
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "schema": "konoha.s49-w22d4-passive-table.v1",
                "rom_offset": PASSIVE_TABLE_OFFSET,
                "rom_offset_hex": f"0x{PASSIVE_TABLE_OFFSET:06X}",
                "gba_addr": f"0x{ROM_BASE + PASSIVE_TABLE_OFFSET:08X}",
                "record_size": PASSIVE_RECORD_SIZE,
                "count": len(records),
                "records": records,
            },
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )

    print(f"dumped {len(records)} passive records")
    print("-- all type 0x15 records --")
    for r in records:
        if r["type"] == 0x15:
            print(
                f"  id={r['passive_id']:3d} @{r['rom_offset_hex']}  "
                f"value_a={r['value_a']} (signed {r['value_a_signed']})  "
                f"value_b={r['value_b']} value_c={r['value_c']} value_d={r['value_d']}"
            )
    print("-- records with value_a in [-10,-1] --")
    for r in records:
        if -10 <= r["value_a_signed"] <= -1:
            print(
                f"  id={r['passive_id']:3d} @{r['rom_offset_hex']} type=0x{r['type']:02X} "
                f"value_a={r['value_a']} (signed {r['value_a_signed']})"
            )
    print("-- type histogram --")
    hist: dict[int, int] = {}
    for r in records:
        hist[r["type"]] = hist.get(r["type"], 0) + 1
    for t in sorted(hist):
        print(f"  0x{t:02X}: {hist[t]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
