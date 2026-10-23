#!/usr/bin/env python3
"""Read-only probe: ARM-mode decode around 0x083FC9A6 (the only reference into
the 0xFF ROM tail)."""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import capstone_loader  # noqa: E402

capstone = capstone_loader.load_capstone()
from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs  # noqa: E402

ROM_BASE = 0x08000000


def main() -> int:
    rom = (REPO / "rom" / "base.gba").read_bytes()
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    base = 0x083FC980
    off = base - ROM_BASE
    for insn in md.disasm(rom[off:off + 0x60], base):
        print("  0x%08X: %-10s %s" % (insn.address, insn.mnemonic, insn.op_str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())