#!/usr/bin/env python3
"""Resolve a pc-relative literal load: target address and loaded value.

Usage:
    python tools/l2_batch2.py --literal 0x08087DE0 0x08087DEC ...
"""
from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from consumer_locate import (arm_ldr_literal_target,          # noqa: E402
                             thumb1_ldr_literal_target,
                             thumb2_ldr_literal_target)

ROM_BASE = 0x08000000


def literal_of(rom: bytes, addr: int) -> tuple[int | None, int | None]:
    """(pool address, loaded value) for the literal load at `addr`."""
    off = addr - ROM_BASE
    half = int.from_bytes(rom[off:off + 2], "little")
    word = int.from_bytes(rom[off:off + 4], "little")
    target = None
    if (half & 0xF800) == 0x4800:
        target = thumb1_ldr_literal_target(half, addr)
    elif addr % 4 == 0 and (word & 0xFF7F0000) == 0xF85F0000:
        target = thumb2_ldr_literal_target(word, addr)
    else:
        target = arm_ldr_literal_target(word, addr)
    if target is None:
        return None, None
    toff = target - ROM_BASE
    if toff < 0 or toff + 4 > len(rom):
        return target, None
    return target, int.from_bytes(rom[toff:toff + 4], "little")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("addresses", nargs="+", help="reader addresses (hex)")
    ap.add_argument("--rom", type=pathlib.Path, default=REPO / "rom" / "base.gba")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = args.rom.read_bytes()
    for item in args.addresses:
        addr = int(item, 16)
        target, value = literal_of(rom, addr)
        if target is None:
            print(f"0x{addr:08X}: no literal load")
        else:
            print(f"0x{addr:08X}: pool @0x{target:08X} value=0x{value:08X}"
                  f" (file offset 0x{target - ROM_BASE:06X})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
