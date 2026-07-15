#!/usr/bin/env python3
"""Observe the sole natural UI caller of the complete save wrapper."""
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
HOOK = 0x08074F2C
ORIGINAL = 0x080689A4
STUB = 0x0809E840
STUB_OFFSET = STUB - ROM_BASE
SCRATCH = 0x0203FF40
STUB_SIZE = 32


def build_probe(base: bytes) -> bytes:
    if hashlib.sha1(base).hexdigest() != BASE_SHA1:
        raise ValueError("natural-save probe requires the immutable base ROM")
    rom = bytearray(base); hook_offset = HOOK - ROM_BASE
    expected = encode_thumb_bl(HOOK, ORIGINAL)
    if rom[hook_offset:hook_offset + 4] != expected:
        raise ValueError("natural save call-site bytes do not match")
    if any(rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("natural-save stub region is not zero-filled")
    # Preserve caller-visible registers. Call original wrapper, then record
    # marker A5, return byte and monotonically increasing hit count.
    prefix = struct.pack("<H", 0xB50E)  # push {r1-r3,lr}; r0 remains return
    body = encode_thumb_bl(STUB + 2, ORIGINAL)
    halfwords = (
        0x4905,  # ldr r1, =SCRATCH
        0x22A5,  # movs r2,#A5
        0x700A,  # strb r2,[r1]
        0x7048,  # strb r0,[r1,#1]
        0x788A,  # ldrb r2,[r1,#2]
        0x3201,  # adds r2,#1
        0x708A,  # strb r2,[r1,#2]
        0xBD0E,  # pop {r1-r3,pc}
    )
    stub = prefix + body + struct.pack("<8H", *halfwords)
    stub += bytes(28 - len(stub)) + struct.pack("<I", SCRATCH)
    if len(stub) != STUB_SIZE:
        raise AssertionError(len(stub))
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = stub
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(HOOK, STUB)
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path); parser.add_argument("output_rom", type=Path)
    args = parser.parse_args(); output = build_probe(args.base_rom.read_bytes())
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
