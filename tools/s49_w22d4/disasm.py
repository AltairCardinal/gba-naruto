#!/usr/bin/env python3
"""Wave 22 / D4 -- thin Thumb disassembler wrapper over the reverse line's
vendored capstone (read-only use).

Usage:
    python disasm.py --rom <rom> --addr 0x08089F00 --before 0x40 --size 0x200
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

VENDOR = Path(r"D:\Shell\Github\gba-naruto-reverse\tools\_vendor")
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs  # type: ignore

ROM_BASE = 0x08000000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--addr", type=lambda x: int(x, 0), required=True)
    parser.add_argument("--before", type=lambda x: int(x, 0), default=0x0)
    parser.add_argument("--size", type=lambda x: int(x, 0), default=0x100)
    parser.add_argument("--thumb", action="store_true", default=True)
    parser.add_argument("--arm", dest="thumb", action="store_false")
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    start = args.addr - args.before
    blob = rom[start - ROM_BASE : start - ROM_BASE + args.size]
    mode = CS_MODE_THUMB if args.thumb else CS_MODE_ARM
    md = Cs(CS_ARCH_ARM, mode)
    for insn in md.disasm(blob, start):
        mark = "=>" if insn.address == args.addr else "  "
        print(f"{mark} 0x{insn.address:08X}: {insn.mnemonic:<8} {insn.op_str}".rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
