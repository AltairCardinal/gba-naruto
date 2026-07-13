#!/usr/bin/env python3
"""Start one selected sound immediately after a clean m4a initialization."""
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
HOOK = 0x08061E28
SOUND_INIT = 0x0809AA3C
SOUND_DISPATCH = 0x0809AAC0
STUB = 0x0809E800
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 16


def build_probe(base: bytes, *, sound_id: int) -> bytes:
    if not 0 <= sound_id <= 0xFF:
        raise ValueError("sound ID must fit in one byte")
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")

    rom = bytearray(base)
    hook_offset = HOOK - ROM_BASE
    expected = encode_thumb_bl(HOOK, SOUND_INIT)
    if rom[hook_offset:hook_offset + 4] != expected:
        raise ValueError("m4a initialization call-site bytes do not match")
    if any(rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("controlled audio stub region is not zero-filled")

    stub = struct.pack("<H", 0xB500)  # push {lr}
    stub += encode_thumb_bl(STUB + len(stub), SOUND_INIT)
    stub += struct.pack("<H", 0x2000 | sound_id)  # movs r0, #sound_id
    stub += encode_thumb_bl(STUB + len(stub), SOUND_DISPATCH)
    stub += struct.pack("<HH", 0xBC01, 0x4700)  # pop {r0}; bx r0
    if len(stub) != STUB_SIZE:
        raise AssertionError(len(stub))

    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = stub
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(HOOK, STUB)
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--sound-id", type=lambda value: int(value, 0), required=True)
    args = parser.parse_args()
    output = build_probe(args.base_rom.read_bytes(), sound_id=args.sound_id)
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
