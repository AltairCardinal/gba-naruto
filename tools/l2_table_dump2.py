#!/usr/bin/env python3
"""Dump the sprite-action table at its 144-byte id stride, and the handler table."""
from __future__ import annotations

import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
ROM_BASE = 0x08000000
ROM = REPO / "rom" / "base.gba"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = ROM.read_bytes()

    print("== sprite-action-table  base=0x08596CCC  id stride 144, entry stride 16")
    base = 0x08596CCC
    for i in range(0, 8):
        blk = base + i * 144
        off = blk - ROM_BASE
        words = [struct.unpack_from("<I", rom, off + k * 4)[0] for k in range(36)]
        nz = sum(1 for w in words if w)
        print(f"  id {i:2d} @0x{blk:08X} nonzero_words={nz}")
        for a in range(9):
            e = off + a * 16
            vals = [struct.unpack_from("<I", rom, e + k * 4)[0] for k in range(4)]
            print(f"      act {a}: " + " ".join(f"{v:08X}" for v in vals))

    print()
    print("== battle-handlers  base=0x0853E698  stride 8, 256 entries")
    base = 0x0853E698
    nonzero = 0
    for i in range(256):
        off = base - ROM_BASE + i * 8
        a, b = struct.unpack_from("<II", rom, off)
        if a or b:
            nonzero += 1
    print(f"  non-empty entries: {nonzero}/256")
    for i in range(0, 256, 1):
        off = base - ROM_BASE + i * 8
        a, b = struct.unpack_from("<II", rom, off)
        if i < 20 or i > 250:
            print(f"   [{i:3d}] @0x{base + i * 8:08X} {a:08X} {b:08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
