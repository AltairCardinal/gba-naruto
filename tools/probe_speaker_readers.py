#!/usr/bin/env python3
"""Read-only probe: disassemble every native reader of the speaker-name table.

Prints a window BEFORE each literal load (to catch the index arithmetic) and
AFTER it (to catch how the entry pointer is consumed).
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

READERS = [
    0x0807908C, 0x080811D2, 0x0808123E, 0x08086048, 0x08088814, 0x08088DB2,
    0x08089362, 0x0808D29A, 0x08090152, 0x08095514, 0x08095CF6, 0x08097A12,
]


def disasm(md, rom, addr, size):
    off = addr - ROM_BASE
    out = []
    for insn in md.disasm(rom[off:off + size], addr):
        out.append("   %s 0x%08X: %-9s %s" % ("", insn.address, insn.mnemonic, insn.op_str))
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = (REPO / "rom" / "base.gba").read_bytes()
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

    for r in READERS:
        print("=" * 78)
        print("READER 0x%08X" % r)
        print("-- context BEFORE (0x40) --")
        for line in disasm(md, rom, r - 0x40, 0x40):
            print(line)
        print("-- reader + AFTER (0x30) --")
        for line in disasm(md, rom, r, 0x30):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())