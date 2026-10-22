#!/usr/bin/env python3
"""Trace up to 32 calls to the shared numeric UI writer."""
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
WRITER = 0x08066A48
CALL_SITES = (
    0x0806E492, 0x0806E548, 0x0806E696, 0x0806E792, 0x0806F0AC,
    0x0806F0C0, 0x080710AA, 0x080710C4, 0x08071152, 0x08071C6C,
    0x08071C80, 0x08071C94, 0x08072042, 0x0807209E, 0x080720C0,
    0x08073246, 0x080732A4, 0x0807382E, 0x08073F4A, 0x08073F62,
    0x08074ABA, 0x08074AE6, 0x08074AFE, 0x08074B60, 0x08074B8C,
    0x08074BA4, 0x08077DEE, 0x08077F60, 0x08077FC0, 0x08077FDE,
    0x08078002, 0x0807801A, 0x08078036, 0x080780BC, 0x080780F0,
    0x0807810C, 0x08078126, 0x08078148, 0x08078160, 0x08078198,
    0x080781B0, 0x080781C6, 0x080781DE, 0x08078212, 0x0807822C,
    0x08078242, 0x0807825A, 0x0807827E, 0x08078296, 0x08078890,
    0x0807A856, 0x0807A88E, 0x0807A8C2, 0x0807A8EC, 0x080873A8,
    0x08088278, 0x08089C0C, 0x08089C22, 0x08089C3A, 0x08089C52,
    0x08089C6A, 0x08089C82, 0x08089C9A, 0x0808AB4A, 0x0808AD82,
    0x0808B0A4, 0x0808B0D6, 0x0808B10A, 0x08091136, 0x0809115A,
    0x080911A0, 0x080924CA, 0x08092B1E, 0x08092B50, 0x08092BB8,
    0x08092BEA, 0x08092CFA, 0x080931F0, 0x080938EE, 0x08093A58,
    0x08093A92, 0x08093AB6, 0x08093AE0, 0x08093AF8, 0x08093B10,
    0x08093B38, 0x08093B50, 0x08093B68, 0x08093B8A, 0x08093BA0,
    0x08093BD6, 0x08093BEC, 0x08093C02, 0x08093C8E, 0x08093CC2,
    0x08093CDA, 0x08093CF0, 0x08093D08, 0x08093D2C, 0x08093D42,
    0x08094B5C,
)
STUB = 0x0809E800
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 48
SCRATCH = 0x0203F600
MAGIC = 0x52574D4E  # "NMWR"
MAX_RECORDS = 32


def _stub() -> bytes:
    halfwords = (
        0xB5FF,       # push {r0-r7,lr}
        0x4674,       # mov r4,lr
        0x1C05,       # adds r5,r0 (displayed numeric value)
        0x4908,       # ldr r1,=SCRATCH
        0x4B08,       # ldr r3,=MAGIC
        0x600B,       # str r3,[r1]
        0x684A,       # ldr r2,[r1,#4]
        0x2A20,       # cmp r2,#32
        0xD204,       # bhs skip_record
        0x00D0,       # lsls r0,r2,#3
        0x3008,       # adds r0,#8
        0x1840,       # adds r0,r0,r1
        0x6004,       # str r4,[r0]
        0x6045,       # str r5,[r0,#4]
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
    expected = set()
    for address in range(ROM_BASE, ROM_BASE + len(base) - 3, 2):
        try:
            encoded = encode_thumb_bl(address, WRITER)
        except ValueError:
            continue
        if base[address - ROM_BASE:address - ROM_BASE + 4] == encoded:
            expected.add(address)
    if expected != set(CALL_SITES):
        raise ValueError("numeric writer call-site set does not match base ROM")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("numeric writer trace stub region is not zero-filled")

    rom = bytearray(base)
    for address in CALL_SITES:
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
