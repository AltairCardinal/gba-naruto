#!/usr/bin/env python3
"""Dump a ROM region as u32 words (for callback tables)."""
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
    ap.add_argument("start", help="ROM address (hex)")
    ap.add_argument("--count", type=int, default=32)
    ap.add_argument("--rom", type=pathlib.Path, default=ROM)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = args.rom.read_bytes()
    start = int(args.start, 16)
    off = start - ROM_BASE
    for i in range(args.count):
        addr = start + i * 4
        word = struct.unpack_from("<I", rom, off + i * 4)[0]
        print(f"  0x{addr:08X}: 0x{word:08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
