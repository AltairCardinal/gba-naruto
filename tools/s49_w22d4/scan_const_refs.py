#!/usr/bin/env python3
"""Wave 22 / D4 -- find every instruction form in the original ROM that
materialises a given 32-bit constant.

Three encodings are covered:
  1. Thumb 16-bit  LDR  rX, [pc, #imm8]      (0x4800..0x4FFF)
  2. Thumb-2       LDR.W rX, [pc, #imm12]     (0xF8DF ..)
  3. Thumb-2       MOVW/MOVT pair building a 32-bit value

Usage:
    python scan_const_refs.py --rom base.gba --target 0x08059EAE0
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

ROM_BASE = 0x08000000


def _ldr16(rom: bytes, off: int, target: int) -> dict | None:
    hw = struct.unpack_from("<H", rom, off)[0]
    if (hw & 0xF800) != 0x4800:
        return None
    rt = (hw >> 8) & 0x7
    imm8 = hw & 0xFF
    pc = (ROM_BASE + off + 4) & ~3
    lit_addr = pc + imm8 * 4
    lit_off = lit_addr - ROM_BASE
    if lit_off < 0 or lit_off + 4 > len(rom):
        return None
    value = struct.unpack_from("<I", rom, lit_off)[0]
    if value != target:
        return None
    return {
        "form": "ldr16",
        "insn_addr": ROM_BASE + off,
        "insn_addr_hex": f"0x{ROM_BASE + off:08X}",
        "detail": f"ldr r{rt}, [pc, #{imm8 * 4}] ; pool @ 0x{lit_addr:08X}",
    }


def _ldr32(rom: bytes, off: int, target: int) -> dict | None:
    if off + 4 > len(rom):
        return None
    hw1, hw2 = struct.unpack_from("<HH", rom, off)
    if hw1 != 0xF8DF:
        return None
    rt = (hw2 >> 12) & 0xF
    imm12 = hw2 & 0xFFF
    pc = (ROM_BASE + off + 4) & ~3
    lit_addr = pc + imm12 * 4
    lit_off = lit_addr - ROM_BASE
    if lit_off < 0 or lit_off + 4 > len(rom):
        return None
    value = struct.unpack_from("<I", rom, lit_off)[0]
    if value != target:
        return None
    return {
        "form": "ldr32",
        "insn_addr": ROM_BASE + off,
        "insn_addr_hex": f"0x{ROM_BASE + off:08X}",
        "detail": f"ldr.w r{rt}, [pc, #{imm12 * 4}] ; pool @ 0x{lit_addr:08X}",
    }


def _movw_movt(rom: bytes, off: int, target: int) -> dict | None:
    if off + 4 > len(rom):
        return None
    hw1, hw2 = struct.unpack_from("<HH", rom, off)
    if (hw1 & 0xFBF0) != 0xF240:  # MOVW
        return None
    rd = (hw1 >> 8) & 0xF
    imm16 = ((hw1 >> 10) & 1) << 11 | ((hw2 >> 4) & 0x700) | (hw2 & 0xFF)
    lo = imm16
    # look ahead up to 6 halfwords for a matching MOVT on the same register
    for delta in range(4, 4 + 12, 2):
        if off + delta + 2 > len(rom):
            break
        h1, h2 = struct.unpack_from("<HH", rom, off + delta)
        if (h1 & 0xFBF0) != 0xF2C0:  # MOVT
            continue
        rd2 = (h1 >> 8) & 0xF
        if rd2 != rd:
            continue
        imm16_hi = ((h1 >> 10) & 1) << 11 | ((h2 >> 4) & 0x700) | (h2 & 0xFF)
        value = ((imm16_hi & 0xFFFF) << 16) | (lo & 0xFFFF)
        if value == target:
            return {
                "form": "movw_movt",
                "insn_addr": ROM_BASE + off,
                "insn_addr_hex": f"0x{ROM_BASE + off:08X}",
                "detail": (
                    f"movw r{rd}, #0x{lo:04X} @0x{ROM_BASE + off:08X} ; "
                    f"movt r{rd}, #0x{imm16_hi:04X} @0x{ROM_BASE + off + delta:08X}"
                ),
            }
    return None


def find_const_refs(rom: bytes, target: int) -> list[dict]:
    hits: list[dict] = []
    for off in range(0, len(rom) - 4, 2):
        for fn in (_ldr16, _ldr32, _movw_movt):
            hit = fn(rom, off, target)
            if hit:
                hits.append(hit)
                break
    hits.sort(key=lambda h: h["insn_addr"])
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument(
        "--target", type=lambda x: int(x, 0), action="append", required=True
    )
    parser.add_argument(
        "--out", type=Path, default=Path(r"D:\Github\gba-naruto\build\w22-d4\const-refs.json")
    )
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    result: dict[str, list[dict]] = {}
    for target in args.target:
        result[f"0x{target:08X}"] = find_const_refs(rom, target)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
    for key, hits in result.items():
        print(f"{key}: {len(hits)} refs")
        for h in hits:
            print(f"   {h['insn_addr_hex']}  {h['form']:<10} {h['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
