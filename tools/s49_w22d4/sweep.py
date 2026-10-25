#!/usr/bin/env python3
"""Wave 22 / D4 -- linear Thumb sweep of the original ROM with literal-pool
annotation.

Decodes halfwords one at a time (so 32-bit Thumb-2 instructions are handled
correctly) and resolves every `ldr rX, [pc, #imm]` to the value it loads.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

VENDOR = Path(r"D:\Shell\Github\gba-naruto-reverse\tools\_vendor")
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs  # type: ignore

ROM_BASE = 0x08000000


def annotate(rom: bytes, addr: int, mnemonic: str, op_str: str) -> str:
    """Resolve pc-relative literal loads to their values."""
    if not mnemonic.startswith("ldr"):
        return ""
    if "[pc" not in op_str:
        return ""
    try:
        # op_str looks like "r0, [pc, #32]"
        imm = int(op_str.split("#")[1].rstrip("]").strip(), 0)
    except (IndexError, ValueError):
        return ""
    pc = (addr + 4) & ~3
    lit = pc + imm
    off = lit - ROM_BASE
    if off < 0 or off + 4 > len(rom):
        return ""
    val = struct.unpack_from("<I", rom, off)[0]
    return f"    ; =0x{val:08X} @0x{lit:08X}"


def sweep(rom: bytes, start: int, size: int) -> list[str]:
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = False
    blob = rom[start - ROM_BASE : start - ROM_BASE + size]
    lines: list[str] = []
    off = 0
    while off < len(blob):
        addr = start + off
        decoded = None
        for count_bytes in (4, 2):
            chunk = blob[off : off + count_bytes]
            if len(chunk) < count_bytes:
                continue
            got = list(md.disasm(chunk, addr, count=1))
            if got and got[0].size == count_bytes:
                decoded = got[0]
                break
        if decoded is None:
            lines.append(f"  0x{addr:08X}: .short 0x{struct.unpack_from('<H', blob, off)[0]:04X}")
            off += 2
            continue
        note = annotate(rom, addr, decoded.mnemonic, decoded.op_str)
        lines.append(
            f"  0x{addr:08X}: {decoded.mnemonic:<8} {decoded.op_str}{note}".rstrip()
        )
        off += decoded.size
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--addr", type=lambda x: int(x, 0), required=True)
    parser.add_argument("--size", type=lambda x: int(x, 0), default=0x200)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    lines = sweep(rom, args.addr, args.size)
    text = "\n".join(lines) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
