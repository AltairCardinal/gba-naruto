#!/usr/bin/env python3
"""Wave 24 / G4 -- find every code site that materialises the constant 0xCE
into a register, with a disassembly window, so the `unit+0xCE` writer can be
identified by hand.

Why this search shape (wave 22 / D4 missed it):
  The original ROM's battle-unit record is 0x1D4 (468) bytes wide at EWRAM
  0x020240C0 (see the settlement routine at 0x08089064).  `carried_experience`
  is unit+0xCE, but the address is built with TWO separate adds, e.g.
      adds r0, r2, #0        ; copy the base
      adds r0, #0xCE         ; + field offset
      ldrh r0, [r0]
  so neither `strh [rm,#0xCE]` nor `adds rd,#0xCE` + `strh` matches.

Read-only: never writes to the ROM or to the reverse line.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VENDOR = Path(r"D:\Shell\Github\gba-naruto-reverse\tools\_vendor")
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs  # type: ignore
from capstone.arm import ARM_OP_IMM  # type: ignore

ROM_BASE = 0x08000000
DEFAULT_ROM = Path(r"D:\Shell\Github\gba-naruto-reverse\rom\base.gba")


def make_md():
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True
    md.skipdata = True
    return md


def sweep(rom: bytes, start: int, end: int):
    md = make_md()
    blob = rom[start - ROM_BASE : end - ROM_BASE]
    for insn in md.disasm(blob, start):
        yield insn.address, insn


def single_imm(insn) -> int | None:
    if insn.id == 0:  # capstone skipdata pseudo-instruction
        return None
    imms = [o.imm for o in insn.operands if o.type == ARM_OP_IMM]
    return imms[0] if len(imms) == 1 else None


def window(rom: bytes, addr: int, before: int, after: int) -> list[str]:
    """Disassemble a window of instructions around `addr`."""
    md = make_md()
    start = addr - before
    blob = rom[start - ROM_BASE : start - ROM_BASE + before + after + 8]
    out: list[str] = []
    for insn in md.disasm(blob, start):
        if insn.address > addr + after:
            break
        mark = "=>" if insn.address == addr else "  "
        out.append(f"{mark} 0x{insn.address:08X}: {insn.mnemonic:<8} {insn.op_str}".rstrip())
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    ap.add_argument("--start", type=lambda x: int(x, 0), default=0x08000000)
    ap.add_argument("--end", type=lambda x: int(x, 0), default=0x08500000)
    ap.add_argument("--field", type=lambda x: int(x, 0), default=0xCE)
    ap.add_argument("--before", type=int, default=0x40)
    ap.add_argument("--after", type=int, default=0x60)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    rom = args.rom.read_bytes()
    target = args.field

    sites: list[dict] = []
    for addr, insn in sweep(rom, args.start, args.end):
        imm = single_imm(insn)
        if imm != target:
            continue
        if insn.mnemonic.startswith(("str", "cmp", "b", "push", "pop")):
            continue
        sites.append(
            {
                "addr": f"0x{addr:08X}",
                "insn": f"{insn.mnemonic} {insn.op_str}",
                "window": window(rom, addr, args.before, args.after),
            }
        )

    report = {
        "rom": str(args.rom),
        "field": target,
        "count": len(sites),
        "sites": sites,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(f"field={target:#x} sites={len(sites)}")
    for s in sites:
        print(s["addr"], s["insn"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
