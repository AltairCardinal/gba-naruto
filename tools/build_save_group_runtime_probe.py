#!/usr/bin/env python3
"""Call save groups 3..9 individually and record each return byte."""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from tools.build_save_state_runtime_probe import BASE_SHA1, GROWTH_CALL_SITES, ORIGINAL_GROWTH, encode_thumb_bl
except ModuleNotFoundError:
    from build_save_state_runtime_probe import BASE_SHA1, GROWTH_CALL_SITES, ORIGINAL_GROWTH, encode_thumb_bl

ROM_BASE = 0x08000000
SAVE_HANDLER = 0x08068684
STUB = 0x0809E800
STUB_OFFSET = STUB - ROM_BASE
SCRATCH = 0x0203FFA0


def build_probe(base: bytes) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    rom = bytearray(base)
    for site in GROWTH_CALL_SITES:
        off = site - ROM_BASE
        if rom[off:off + 4] != encode_thumb_bl(site, ORIGINAL_GROWTH):
            raise ValueError(f"growth call mismatch at 0x{site:08X}")

    code = struct.pack("<H", 0xB530)  # push {r4,r5,lr}
    code += encode_thumb_bl(STUB + len(code), ORIGINAL_GROWTH)
    code += struct.pack("<H", 0x1C04)  # preserve growth result in r4
    # LDR r5 literal is patched after the final aligned literal location is known.
    ldr_offset = len(code)
    code += b"\x00\x00"
    for output_index, group in enumerate(range(3, 10)):
        code += struct.pack("<HH", 0x2000, 0x2100 | group)
        code += encode_thumb_bl(STUB + len(code), SAVE_HANDLER)
        code += struct.pack("<H", 0x7028 | (output_index << 6))
    code += struct.pack("<HH", 0x1C20, 0xBD30)
    while len(code) % 4:
        code += b"\x00\x00"
    literal_offset = len(code)
    code += struct.pack("<I", SCRATCH)
    ldr_address = STUB + ldr_offset
    pc_base = (ldr_address + 4) & ~3
    immediate = (STUB + literal_offset - pc_base) // 4
    if not 0 <= immediate <= 0xFF:
        raise ValueError("scratch literal out of LDR range")
    code = code[:ldr_offset] + struct.pack("<H", 0x4D00 | immediate) + code[ldr_offset + 2:]
    if any(rom[STUB_OFFSET:STUB_OFFSET + len(code)]):
        raise ValueError("save-group stub region is not zero-filled")
    rom[STUB_OFFSET:STUB_OFFSET + len(code)] = code
    for site in GROWTH_CALL_SITES:
        off = site - ROM_BASE
        rom[off:off + 4] = encode_thumb_bl(site, STUB)
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    args = parser.parse_args()
    output = build_probe(args.base_rom.read_bytes())
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
