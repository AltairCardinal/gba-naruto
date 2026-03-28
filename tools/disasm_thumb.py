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

ROM_BASE = 0x08000000


def read_window(
    rom_path: Path, gba_addr: int, before: int, size: int
) -> tuple[int, bytes]:
    start_addr = max(ROM_BASE, gba_addr - before)
    start_off = start_addr - ROM_BASE
    data = rom_path.read_bytes()
    end_off = min(len(data), start_off + size)
    return start_addr, data[start_off:end_off]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Disassemble a GBA ROM region as Thumb code."
    )
    parser.add_argument("rom", help="ROM path")
    parser.add_argument("address", help="GBA ROM address, e.g. 0x08066D74")
    parser.add_argument("--before", type=lambda x: int(x, 0), default=0x20)
    parser.add_argument("--size", type=lambda x: int(x, 0), default=0x80)
    parser.add_argument("--output", help="Optional output path")
    args = parser.parse_args()

    rom_path = Path(args.rom)
    gba_addr = int(args.address, 0)
    start_addr, blob = read_window(rom_path, gba_addr, args.before, args.size)

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    lines = [
        f"rom={rom_path}",
        f"start=0x{start_addr:08X}",
        f"focus=0x{gba_addr:08X}",
        f"size=0x{len(blob):X}",
        "",
    ]
    for insn in md.disasm(blob, start_addr):
        marker = "=>" if insn.address == gba_addr else "  "
        lines.append(
            f"{marker} 0x{insn.address:08X}: {insn.mnemonic:<8} {insn.op_str}".rstrip()
        )
    text = "\n".join(lines) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
