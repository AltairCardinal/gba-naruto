#!/usr/bin/env python3
"""Trace up to 32 calls to the shared encoded-text UI writer."""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from tools.build_chapter_script_probe import BASE_SHA1
    from tools.build_save_state_runtime_probe import encode_thumb_bl
except ModuleNotFoundError:
    from build_chapter_script_probe import BASE_SHA1
    from build_save_state_runtime_probe import encode_thumb_bl


ROM_BASE = 0x08000000
WRITER = 0x08066758
STUB = 0x0809E800
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 56
SCRATCH = 0x0203F400
MAGIC = 0x52574D53  # "SMWR"
MAX_RECORDS = 32


def find_call_sites(base: bytes) -> tuple[int, ...]:
    calls = []
    for address in range(ROM_BASE, ROM_BASE + len(base) - 3, 2):
        try:
            encoded = encode_thumb_bl(address, WRITER)
        except ValueError:
            continue
        offset = address - ROM_BASE
        if base[offset:offset + 4] == encoded:
            calls.append(address)
    return tuple(calls)


def _stub() -> bytes:
    halfwords = (
        0xB5FF,       # push {r0-r7,lr}
        0x4674,       # mov r4,lr
        0x1C05,       # adds r5,r0 (encoded-text pointer)
        0x490A,       # ldr r1,=SCRATCH
        0x4B0A,       # ldr r3,=MAGIC
        0x600B,       # str r3,[r1]
        0x684A,       # ldr r2,[r1,#4]
        0x2A20,       # cmp r2,#32
        0xD208,       # bhs skip_record
        0x0050,       # lsls r0,r2,#1
        0x1880,       # adds r0,r0,r2
        0x0080,       # lsls r0,r0,#2
        0x3008,       # adds r0,#8
        0x1840,       # adds r0,r0,r1
        0x6004,       # str r4,[r0]
        0x6045,       # str r5,[r0,#4]
        0x682B,       # ldr r3,[r5]
        0x6083,       # str r3,[r0,#8]
        0x3201,       # adds r2,#1
        0x604A,       # str r2,[r1,#4]
        0xBCFF,       # pop {r0-r7}
    )
    code = struct.pack(f"<{len(halfwords)}H", *halfwords)
    code += encode_thumb_bl(STUB + len(code), WRITER)
    code += struct.pack("<H2I", 0xBD00, SCRATCH, MAGIC)
    if len(code) != STUB_SIZE:
        raise AssertionError(len(code))
    return code


def build_probe(base: bytes) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    call_sites = find_call_sites(base)
    if len(call_sites) != 256:
        raise ValueError(f"expected 256 text-writer calls, found {len(call_sites)}")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("text writer trace stub region is not zero-filled")

    rom = bytearray(base)
    for address in call_sites:
        offset = address - ROM_BASE
        rom[offset:offset + 4] = encode_thumb_bl(address, STUB)
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = _stub()
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
