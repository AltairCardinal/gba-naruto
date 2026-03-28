#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "tools" / "_vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs  # type: ignore
from capstone.arm import ARM_OP_IMM  # type: ignore

ROM_BASE = 0x08000000


def scan_calls(rom_path: Path, target: int) -> list[tuple[int, str, str]]:
    data = rom_path.read_bytes()
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True
    md.skipdata = True
    matches: list[tuple[int, str, str]] = []
    for insn in md.disasm(data, ROM_BASE):
        if insn.mnemonic not in {"bl", "blx", "b"}:
            continue
        if not insn.operands:
            continue
        op = insn.operands[0]
        if op.type != ARM_OP_IMM:
            continue
        if op.imm == target:
            matches.append((insn.address, insn.mnemonic, insn.op_str))
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find Thumb branch/call sites that target a ROM address."
    )
    parser.add_argument("rom", help="ROM path")
    parser.add_argument("target", help="GBA ROM address, e.g. 0x08066D14")
    parser.add_argument("--output", help="Optional output path")
    args = parser.parse_args()

    rom_path = Path(args.rom)
    target = int(args.target, 0)
    hits = scan_calls(rom_path, target)
    lines = [f"rom={rom_path}", f"target=0x{target:08X}", f"matches={len(hits)}", ""]
    for address, mnemonic, op_str in hits:
        lines.append(f"0x{address:08X}: {mnemonic:<4} {op_str}")
    text = "\n".join(lines) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
