#!/usr/bin/env python3
"""Find the original ROM code that touches a WRAM work struct.

Why this tool exists
--------------------
Stream E4 (wave 20) has to answer "where do the original settlement numbers
live?" for the remake line.  Offline savestate dumps show that the settlement
screen of the original ROM keeps its numbers in the EWRAM work struct that
starts at ``0x02002880`` -- but the two per-character bonus vectors in that
struct cannot be told apart from the dumps alone (the scenario-46 screen prints
``59`` where the unit record says ``60``).

This tool therefore does the static part of the answer: it finds every literal
reference to the struct base in the ROM, resolves the ``LDR Rn, [PC, #imm]``
that loads it, and reports which struct offsets the surrounding code touches.
A function that reads the base exp, both bonus vectors and the totals is the
settlement computer.

Usage::

    python tools/s49_w20e/rom_struct_xref.py --base 0x02002880 --rom rom/base.gba
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

try:
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
except ImportError as error:  # pragma: no cover - tool dependency
    raise SystemExit("capstone is required: pip install capstone") from error

LITERAL_POOL_WINDOW = 1024
FUNC_WINDOW = 96


def find_literal_sites(rom: bytes, base: int) -> list[int]:
    pattern = struct.pack("<I", base)
    sites: list[int] = []
    cursor = rom.find(pattern)
    while cursor != -1:
        sites.append(cursor)
        cursor = rom.find(pattern, cursor + 1)
    return sites


def thumb_loads_literal(cs, rom: bytes, literal_offset: int) -> list[tuple[int, int]]:
    """Return (instruction_offset, register) for LDRs that load ``literal_offset``."""
    hits: list[tuple[int, int]] = []
    start = max(0, literal_offset - LITERAL_POOL_WINDOW)
    window = rom[start:literal_offset]
    for instruction in cs.disasm(window, 0x08000000 + start, count=0):
        if instruction.mnemonic != "ldr" or not instruction.op_str.startswith("r"):
            continue
        if "[pc" not in instruction.op_str.replace(" ", ""):
            continue
        # recompute the literal address the way Thumb PC rules do
        try:
            pc_value = instruction.address + 4
            operand = instruction.op_str.split("[pc,")[-1].split("]")[0].strip()
            displacement = int(operand.replace("#", ""), 0)
        except (IndexError, ValueError):
            continue
        target = (pc_value & ~3) + displacement
        if target == 0x08000000 + literal_offset:
            register = instruction.op_str.split(",")[0].strip()
            hits.append((instruction.address - 0x08000000, register))
    return hits


def offsets_touched(cs, rom: bytes, function_offset: int, register: str) -> list[int]:
    """Collect struct offsets accessed through ``register`` in a short window."""
    window = rom[function_offset:function_offset + FUNC_WINDOW * 2]
    offsets: set[int] = set()
    for instruction in cs.disasm(window, 0x08000000 + function_offset, count=0):
        text = instruction.op_str.replace(" ", "")
        if f"[{register}," not in text:
            continue
        operand = text.split(f"[{register},")[-1].split("]")[0].replace("#", "")
        try:
            value = int(operand, 0)
        except ValueError:
            continue
        if 0 <= value <= 0x40:
            offsets.add(value)
    return sorted(offsets)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="0x02002880")
    parser.add_argument("--rom", required=True)
    parser.add_argument("--window", type=int, default=FUNC_WINDOW)
    args = parser.parse_args(argv)

    base = int(args.base, 0)
    rom = Path(args.rom).read_bytes()
    cs = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    cs.detail = False

    sites = find_literal_sites(rom, base)
    report = []
    for site in sites:
        for instruction_offset, register in thumb_loads_literal(cs, rom, site):
            offsets = offsets_touched(cs, rom, instruction_offset, register)
            report.append({
                "literal_site": f"0x{0x08000000 + site:08X}",
                "load_insn": f"0x{0x08000000 + instruction_offset:08X}",
                "register": register,
                "offsets": [f"0x{value:02X}" for value in offsets],
            })
    report.sort(key=lambda entry: -len(entry["offsets"]))
    print(json.dumps({
        "rom": args.rom,
        "base": f"0x{base:08X}",
        "literal_sites": len(sites),
        "resolved": len(report),
        "entries": report,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
