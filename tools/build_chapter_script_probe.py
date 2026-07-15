#!/usr/bin/env python3
"""Hook the script opcode that writes chapter/battle ID into runtime state."""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from tools.build_save_state_runtime_probe import encode_thumb_bl
except ModuleNotFoundError:
    from build_save_state_runtime_probe import encode_thumb_bl

BASE_SHA1 = "26f60795fa5e63b4f0264b84e453beffd56b9f7d"
ROM_BASE = 0x08000000
HOOK = 0x08097C78
EXPECTED = bytes.fromhex("7878a075")  # ldrb r0,[r7,#1]; strb r0,[r4,#0x16]
STUB = 0x0809E780
STUB_OFFSET = STUB - ROM_BASE
SCRATCH = 0x0203FFB0
STUB_SIZE = 36


def build_probe(base: bytes) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    rom = bytearray(base)
    hook_offset = HOOK - ROM_BASE
    if rom[hook_offset:hook_offset + 4] != EXPECTED:
        raise ValueError(f"chapter hook before bytes mismatch: {rom[hook_offset:hook_offset + 4].hex()}")
    if any(rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("chapter probe stub region is not zero-filled")
    halfwords = (
        0xB50F, 0x4807, 0x6007, 0x7839, 0x7101, 0x7879, 0x7141,
        0x75A1, 0x78B9, 0x7181, 0x78F9, 0x71C1, 0x7A02, 0x3201,
        0x7202, 0xBD0F,
    )
    stub = struct.pack("<16H", *halfwords) + struct.pack("<I", SCRATCH)
    if len(stub) != STUB_SIZE:
        raise AssertionError(len(stub))
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = stub
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(HOOK, STUB)
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
