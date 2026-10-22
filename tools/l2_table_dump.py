#!/usr/bin/env python3
"""Dump the ROM bytes of the batch-2 tables (for writing precise checks)."""
from __future__ import annotations

import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

ROM_BASE = 0x08000000
ROM = REPO / "rom" / "base.gba"

TABLES = [
    ("battle-handlers", 0x0853E698, 8, 16),
    ("fonts", 0x0853E596, 1, 32),
    ("data-table-a", 0x085A143C, 4, 12),
    ("data-table-b", 0x085A2034, 4, 12),
    ("function-pointers", 0x0853D5F0, 4, 13),
    ("tile-assets", 0x085A320C, 68, 3),
    ("sprite-frame-descriptors", 0x0853EE98, 10, 15),
    ("battle-encounters", 0x0854229C, 16, 6),
    ("ninjutsu-names", 0x08599634, 4, 12),
    ("reward-table", 0x0859EAE0, 24, 6),
    ("cutscene-scripts", 0x0853DF70, 8, 4),
    ("sprite-action-table", 0x08596CCC, 16, 6),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = ROM.read_bytes()
    for name, base, stride, count in TABLES:
        print(f"== {name}  base=0x{base:08X} stride={stride} count={count}")
        for i in range(count):
            off = base - ROM_BASE + i * stride
            chunk = rom[off:off + stride]
            words = [struct.unpack_from("<I", chunk, k)[0]
                     for k in range(0, len(chunk) - 3, 4)]
            text = " ".join(f"{w:08X}" for w in words)
            print(f"   [{i:3d}] @0x{base + i * stride:08X}  {chunk.hex(' '):<24s}"
                  f" | {text}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
