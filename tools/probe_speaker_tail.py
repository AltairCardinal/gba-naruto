#!/usr/bin/env python3
"""Read-only probe: are the tail-region u32 values real code references?"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
ROM_BASE = 0x08000000
TAIL_LO, TAIL_HI = 0x085DFBEC, 0x08600000


def thumb_lit_sites(rom, lit_off, back=1024):
    out = []
    lo = max(0, lit_off - back)
    for a in range(lo, lit_off - 3, 2):
        hw = int.from_bytes(rom[a:a + 2], "little")
        if (hw & 0xF800) == 0x4800:
            imm = (hw & 0xFF) * 4
            if ((a + 4) & ~3) + imm == lit_off:
                out.append(ROM_BASE + a)
    return out


def main() -> int:
    rom = (REPO / "rom" / "base.gba").read_bytes()
    print("=== u32 values in the tail window: are they loaded by ldr rX,[pc,#imm]? ===")
    for off in range(0, len(rom) - 3, 4):
        v = int.from_bytes(rom[off:off + 4], "little")
        if TAIL_LO <= v < TAIL_HI:
            sites = thumb_lit_sites(rom, off)
            print("  0x%08X @file 0x%06X  aligned=%s  ldr-sites=%s"
                  % (v, off, v % 4 == 0, ["0x%08X" % s for s in sites] or "NONE"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())