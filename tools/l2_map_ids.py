#!/usr/bin/env python3
"""List the map descriptors whose object/layer pointers are non-null."""
from __future__ import annotations

import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
ROM_BASE = 0x08000000
ROM = REPO / "rom" / "base.gba"
BASE = 0x53D910
STRIDE = 32


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = ROM.read_bytes()
    non_null = []
    for i in range(50):
        off = BASE + i * STRIDE
        words = struct.unpack_from("<8I", rom, off)
        ptrs = [w for w in words if ROM_BASE <= w < ROM_BASE + len(rom)]
        if len(ptrs) >= 2:
            non_null.append(i)
        print(f"  [{i:2d}] @0x{BASE + i * STRIDE:08X} " +
              " ".join(f"{w:08X}" for w in words))
    print(f"\nnon-null map ids (>=2 ROM pointers): {non_null}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
