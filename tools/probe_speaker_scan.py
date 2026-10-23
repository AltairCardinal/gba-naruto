#!/usr/bin/env python3
"""Read-only probe: exhaustive scan for readers of the speaker-name table region.

Scans every aligned u32 in the ROM that points into a target address window,
then walks backwards to find the Thumb `ldr rX,[pc,#imm]` that loads it
(T1 encoding: 0x4800..0x4FFF, literal at ((A+4)&~3) + imm8*4).
This catches readers that use a base+offset literal, not just the exact base.
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import capstone_loader  # noqa: E402

capstone = capstone_loader.load_capstone()
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs  # noqa: E402

ROM_BASE = 0x08000000
TABLE_ROM = 0x085A57C4
TABLE_OFF = TABLE_ROM - ROM_BASE


def thumb_lit_sites(rom, lit_off, back=1024):
    """Return Thumb addresses whose ldr rX,[pc,#imm] targets literal offset lit_off."""
    out = []
    lo = max(0, lit_off - back)
    for a in range(lo, lit_off - 3, 2):
        hw = int.from_bytes(rom[a:a + 2], "little")
        if (hw & 0xF800) == 0x4800:
            imm = (hw & 0xFF) * 4
            target = ((a + 4) & ~3) + imm
            if target == lit_off:
                out.append(ROM_BASE + a)
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = (REPO / "rom" / "base.gba").read_bytes()
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

    windows = [
        ("table exact base", 0x085A57C4, 0x085A57C4),
        ("inside 64 slots", 0x085A57C4, 0x085A5AC4),
        ("region +-0x100", 0x085A56C4, 0x085A5BC4),
        ("region +-0x400", 0x085A53C4, 0x085A5BC4),
    ]
    for label, lo, hi in windows:
        print("=== literals in [%s] : 0x%08X .. 0x%08X ===" % (label, lo, hi))
        n = 0
        for off in range(0, len(rom) - 3, 4):
            val = int.from_bytes(rom[off:off + 4], "little")
            if lo <= val <= hi:
                sites = thumb_lit_sites(rom, off)
                for a in sites:
                    n += 1
                    print("   lit 0x%08X (file 0x%06X)  loaded by 0x%08X  %s"
                          % (val, off, a, "(base)" if val == TABLE_ROM else ""))
        print("   total: %d" % n)

    # what lives right after the table?
    print("\n=== bytes after the 64 slots ===")
    end = TABLE_OFF + 64 * 12
    print("   table ends at file 0x%06X (ROM 0x%08X)" % (end, end + ROM_BASE))
    # try to interpret the tail as a different table: look for NUL-terminated strings
    print("\n=== NUL-terminated strings in [0x%06X, 0x%06X) ===" % (end, end + 0x400))
    i = end
    while i < end + 0x400:
        if rom[i] == 0:
            i += 1
            continue
        j = rom.find(b"\x00", i, end + 0x400)
        if j < 0:
            break
        s = rom[i:j]
        if len(s) <= 24:
            print("   @0x%06X len=%2d  %s" % (i, len(s), s.hex(" ")))
        i = j + 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())