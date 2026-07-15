#!/usr/bin/env python3
"""Trace skill ID 2 initialization and optionally change its copied byte +4."""
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
HOOK = 0x0806D916
EXPECTED_HOOK = bytes.fromhex("0006000d")  # lsls r0,#24; lsrs r0,#20
STUB = 0x0809E840
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 52
SCRATCH = 0x0203FF00
MAGIC = 0x52504B53  # "SKPR"
SKILL_2_RECORD = 0x545C04
SKILL_BYTE_04 = SKILL_2_RECORD + 4
EXPECTED_SKILL_BYTE_04 = 6


def _stub() -> bytes:
    halfwords = (
        0xB40F,       # push {r0-r3}
        0x2802,       # cmp r0,#2
        0xD107,       # bne skip capture
        0x4909,       # ldr r1, =SCRATCH
        0x4A09,       # ldr r2, =MAGIC
        0x600A,       # str r2,[r1]
        0x684A, 0x3201, 0x604A,  # ++hitCount
        0x608C,       # str r4,[r1,#8] (destination)
        0x60C8,       # str r0,[r1,#12] (skill ID)
        0xBC0F,       # pop {r0-r3}
        0x0600,       # original lsls r0,#24
        0x0D00,       # original lsrs r0,#20
        0x4770,       # bx lr
        0x46C0,       # alignment nop
        0x46C0, 0x46C0,  # pad literals to +0x2c
        0x46C0, 0x46C0, 0x46C0, 0x46C0,
    )
    return struct.pack("<22H2I", *halfwords, SCRATCH, MAGIC)


def build_probe(
    base: bytes, *, skill_byte_04: int = EXPECTED_SKILL_BYTE_04,
    skill_overrides: dict[int, int] | None = None,
) -> bytes:
    if not 0 <= skill_byte_04 <= 0xFF:
        raise ValueError("skill byte +4 must fit u8")
    overrides = dict(skill_overrides or {})
    for offset, value in overrides.items():
        if not 0 <= offset < 16:
            raise ValueError("skill override offset must be 0..15")
        if not 0 <= value <= 0xFF:
            raise ValueError("skill override value must fit u8")
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    hook_offset = HOOK - ROM_BASE
    if base[hook_offset:hook_offset + 4] != EXPECTED_HOOK:
        raise ValueError("skill hook bytes do not match")
    if base[SKILL_BYTE_04] != EXPECTED_SKILL_BYTE_04:
        raise ValueError("skill 2 byte +4 does not match")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("skill probe stub region is not zero-filled")
    stub = _stub()
    if len(stub) != STUB_SIZE:
        raise AssertionError(len(stub))
    rom = bytearray(base)
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(HOOK, STUB)
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = stub
    rom[SKILL_BYTE_04] = skill_byte_04
    for offset, value in overrides.items():
        rom[SKILL_2_RECORD + offset] = value
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--skill-byte-04", type=int, default=EXPECTED_SKILL_BYTE_04)
    parser.add_argument("--set", action="append", default=[], metavar="OFFSET=VALUE")
    args = parser.parse_args()
    overrides = {}
    for assignment in args.set:
        offset, value = assignment.split("=", 1)
        overrides[int(offset, 0)] = int(value, 0)
    output = build_probe(
        args.base_rom.read_bytes(), skill_byte_04=args.skill_byte_04,
        skill_overrides=overrides,
    )
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
