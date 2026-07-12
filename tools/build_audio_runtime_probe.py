#!/usr/bin/env python3
"""Hook the public sound-ID wrapper and log live IDs/descriptors to EWRAM."""
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
HOOK = 0x08061E72
ORIGINAL = 0x0809AAC0
STUB = 0x0809E800
STUB_OFFSET = STUB - ROM_BASE
SCRATCH = 0x0203FF60
MASTER = 0x08465B70
STUB_SIZE = 56


def build_probe(base: bytes) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    rom = bytearray(base)
    hook_offset = HOOK - ROM_BASE
    expected = encode_thumb_bl(HOOK, ORIGINAL)
    if rom[hook_offset:hook_offset + 4] != expected:
        raise ValueError("sound wrapper call-site bytes do not match")
    if any(rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("audio probe stub region is not zero-filled")

    # scratch: +0 hit_count, +4 last_id, +8 first_id, +0x0c last_descriptor.
    halfwords = (
        0xB50F,       # push {r0-r3,lr}
        0x490B,       # ldr r1, =SCRATCH
        0x680A,       # ldr r2, [r1]
        0x2A00,       # cmp r2, #0
        0xD100,       # bne store_last
        0x6088,       # str r0, [r1,#8]
        0x6048,       # store_last: str r0, [r1,#4]
        0x3201,       # adds r2,#1
        0x600A,       # str r2,[r1]
        0x4B08,       # ldr r3, =MASTER
        0x00C2,       # lsls r2,r0,#3
        0x189B,       # adds r3,r3,r2
        0x681B,       # ldr r3,[r3]
        0x60CB,       # str r3,[r1,#0x0c]
    )
    prefix = struct.pack(f"<{len(halfwords)}H", *halfwords)
    call_at = STUB + len(prefix)
    stub = prefix + encode_thumb_bl(call_at, ORIGINAL) + struct.pack("<H", 0xBD0F)
    stub += bytes(0x30 - len(stub)) + struct.pack("<II", SCRATCH, MASTER)
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
