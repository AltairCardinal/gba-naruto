#!/usr/bin/env python3
"""Read-only probe for the speaker-name table at ROM 0x085A57C4 (file 0x5A57C4).

Dumps:
  * every u32 occurrence of the table base and the instruction that loads it
  * the raw bytes of all 64 fixed 12-byte slots
  * glyph codes, glyph counts, NUL position per slot
  * the "palette" (u32 colour + 8 zero bytes) reading of the same bytes

Usage:  python tools/probe_speaker_names.py rom/base.gba
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
STRIDE = 12
COUNT = 64


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = (REPO / "rom" / "base.gba").read_bytes()
    print("rom size = %d (0x%X)" % (len(rom), len(rom)))

    needle = TABLE_ROM.to_bytes(4, "little")
    occ = []
    off = 0
    while True:
        i = rom.find(needle, off)
        if i < 0:
            break
        occ.append(i)
        off = i + 1

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    print("\n=== u32 occurrences of 0x%08X : %d ===" % (TABLE_ROM, len(occ)))
    for i in occ:
        lo = max(0, i - 0x400)
        found = None
        for insn in md.disasm(rom[lo:i], ROM_BASE + lo):
            if insn.address + insn.size == i:
                found = insn
        txt = ("%08X %-8s %s" % (found.address, found.mnemonic, found.op_str)) if found else "??"
        print("  file 0x%06X (ROM 0x%08X)  loader: %s" % (i, i + ROM_BASE, txt))

    print("\n=== %d slots @ ROM 0x%08X (file 0x%06X), stride %d ===" % (COUNT, TABLE_ROM, TABLE_OFF, STRIDE))
    print("%3s %8s  %-26s %-14s %5s %6s %6s" % ("id", "file", "raw12", "glyphs", "ngly", "nul_at", "b12"))
    maxn = 0
    for i in range(COUNT):
        base = TABLE_OFF + i * STRIDE
        raw = rom[base:base + STRIDE]
        glyphs = []
        nul_at = None
        for k in range(0, STRIDE, 2):
            v = int.from_bytes(raw[k:k + 2], "little")
            if v == 0:
                nul_at = k
                break
            glyphs.append(v)
        n = len(glyphs)
        if n > maxn:
            maxn = n
        gs = " ".join("%04X" % g for g in glyphs)
        print("%3d 0x%06X  %-26s %-14s %5d %6s %6s" % (i, base, raw.hex(" "), gs, n, nul_at, raw[11]))
    print("max glyph count = %d" % maxn)

    print("\n=== distinct tail bytes (slot bytes 6..11) ===")
    tails = {}
    for i in range(COUNT):
        base = TABLE_OFF + i * STRIDE
        tail = rom[base + 6:base + STRIDE].hex(" ")
        tails[tail] = tails.get(tail, 0) + 1
    for k, v in sorted(tails.items(), key=lambda kv: -kv[1]):
        print("  %r x%d" % (k, v))

    print("\n=== u32 'palette' view of the same bytes (first/last) ===")
    for i in list(range(6)) + list(range(60, 64)):
        base = TABLE_OFF + i * STRIDE
        c = int.from_bytes(rom[base:base + 4], "little")
        pad = rom[base + 4:base + STRIDE].hex(" ")
        print("  id %2d: u32=0x%08X  pad=%s" % (i, c, pad))

    print("\n=== bytes AFTER the table (file 0x%06X) ===" % (TABLE_OFF + COUNT * STRIDE))
    tail = rom[TABLE_OFF + COUNT * STRIDE: TABLE_OFF + COUNT * STRIDE + 64]
    print("  " + tail.hex(" "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())