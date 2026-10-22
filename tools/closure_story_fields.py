#!/usr/bin/env python3
"""Find the code that touches given offsets of the story state block.

The block base is 0x020311D4.  This script lists every `ldr rX, [pc, #imm]`
that loads the base and then, in the following instructions, every memory
access that uses one of the requested offsets.

Usage:
    python tools/closure_story_fields.py 0x10 0x18 0x19 0x1a 0x1b
"""
from __future__ import annotations

import pathlib
import re
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import capstone_loader  # noqa: E402

_cs = capstone_loader.load_capstone()
ROM_BASE = 0x08000000
rom = (REPO / "rom" / "base.gba").read_bytes()
md = _cs.Cs(_cs.CS_ARCH_ARM, _cs.CS_MODE_THUMB)
md.skipdata = True

BASE = 0x020311D4


def loaders(value: int) -> list[int]:
    blob = struct.pack("<I", value)
    out = []
    index = 0
    while True:
        index = rom.find(blob, index)
        if index < 0:
            break
        pool = ROM_BASE + index
        index += 1
        if pool % 4:
            continue
        low = max(ROM_BASE, pool - 1020)
        window = rom[low - ROM_BASE:pool - ROM_BASE + 4]
        for insn in md.disasm(window, low):
            if insn.mnemonic not in ("ldr", "ldr.w") or "[pc" not in insn.op_str:
                continue
            first = int.from_bytes(rom[insn.address - ROM_BASE:
                                       insn.address - ROM_BASE + 2], "little")
            if first & 0xF800 != 0x4800:
                continue
            if ((insn.address + 4) & ~3) + (first & 0xFF) * 4 != pool:
                continue
            out.append(insn.address)
    return sorted(set(out))


def main() -> int:
    offsets = [int(item, 0) for item in sys.argv[1:]] or [0x10, 0x18, 0x19]
    pattern = re.compile(r"\[(r[0-7])(?:, #(" +
                         "|".join(hex(o) for o in offsets) + r")\])?\]")
    found = 0
    for address in loaders(BASE):
        blob = rom[address - ROM_BASE:address - ROM_BASE + 0x60]
        lines = []
        for insn in md.disasm(blob, address):
            line = f"0x{insn.address:08X}: {insn.mnemonic:<9} {insn.op_str}"
            if re.search(r"\[r[0-7], #(0x" + "|".join(
                    f"{o:x}" for o in offsets) + r")\]", insn.op_str):
                lines.append("  >> " + line)
            else:
                lines.append("     " + line)
        text = "\n".join(lines)
        if ">>" in text:
            found += 1
            print(f"--- loader at 0x{address:08X} ---")
            print(text)
    print(f"{found} site(s) with a matching offset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
