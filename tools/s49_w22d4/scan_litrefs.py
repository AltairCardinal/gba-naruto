#!/usr/bin/env python3
"""Wave 22 / D4 -- scan the original ROM for Thumb LDR-literal instructions
that reference a given 32-bit address.

Every `ldr rX, [pc, #imm8]` in Thumb form (0x4800..0x4FFF) is decoded over the
whole ROM and the literal it points at is resolved.  The result is the set of
code addresses that load a given constant -- e.g. the address of the original
reward table -- which is how the consumer routines are located.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

ROM_BASE = 0x08000000


def thumb_literal_refs(rom: bytes, target: int) -> list[dict]:
    hits: list[dict] = []
    limit = len(rom) - 4
    for off in range(0, limit, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        rt = (hw >> 8) & 0x7
        imm8 = hw & 0xFF
        pc = (ROM_BASE + off + 4) & ~3
        lit_addr = pc + imm8 * 4
        lit_off = lit_addr - ROM_BASE
        if lit_off < 0 or lit_off + 4 > len(rom):
            continue
        value = struct.unpack_from("<I", rom, lit_off)[0]
        if value != target:
            continue
        hits.append(
            {
                "insn_addr": ROM_BASE + off,
                "insn_addr_hex": f"0x{ROM_BASE + off:08X}",
                "reg": f"r{rt}",
                "literal_addr": lit_addr,
                "literal_addr_hex": f"0x{lit_addr:08X}",
                "value": value,
                "value_hex": f"0x{value:08X}",
            }
        )
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument(
        "--target", type=lambda x: int(x, 0), action="append", required=True
    )
    parser.add_argument(
        "--out", type=Path, default=Path(r"D:\Github\gba-naruto\build\w22-d4\literal-refs.json")
    )
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    result: dict[str, list[dict]] = {}
    for target in args.target:
        result[f"0x{target:08X}"] = thumb_literal_refs(rom, target)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
    for key, hits in result.items():
        print(f"{key}: {len(hits)} refs")
        for h in hits:
            print(f"   {h['insn_addr_hex']}  ldr {h['reg']}, [pc, ...]  -> {h['literal_addr_hex']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
