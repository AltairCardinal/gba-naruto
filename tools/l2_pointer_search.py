#!/usr/bin/env python3
"""Where does a ROM function address appear as a data word?

Used to find function-pointer tables that dispatch a function whose direct
call sites are not visible (e.g. a callback table).

Usage:
    python tools/l2_pointer_search.py 0x0807EE50
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
ROM_BASE = 0x08000000
ROM = REPO / "rom" / "base.gba"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("values", nargs="+", help="ROM addresses (hex)")
    ap.add_argument("--rom", type=pathlib.Path, default=ROM)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = args.rom.read_bytes()
    for item in args.values:
        value = int(item, 16)
        needle = struct.pack("<I", value)
        pos = 0
        hits = []
        while True:
            pos = rom.find(needle, pos)
            if pos < 0:
                break
            hits.append(pos)
            pos += 1
        print(f"0x{value:08X}: {len(hits)} data word(s) -> "
              + ", ".join(f"0x{ROM_BASE + h:08X}" for h in hits[:20]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
