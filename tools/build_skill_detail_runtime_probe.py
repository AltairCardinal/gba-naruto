#!/usr/bin/env python3
"""Trace the live skill-detail initializer and optionally change source byte +4."""
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
HOOK = 0x08070906
INITIALIZER = 0x0806D910
EXPECTED_HOOK = encode_thumb_bl(HOOK, INITIALIZER)
STUB = 0x0809E800
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 60
SCRATCH = 0x0203F300
MAGIC = 0x52504453  # "SDPR"
SKILL_TABLE = 0x545BE4
SKILL_COUNT = 94
SKILL_SIZE = 16
FORCE_ID_LOAD = 0x08071104
EXPECTED_FORCE_ID_LOAD = bytes.fromhex("0278")  # ldrb r2,[r0]


def _stub() -> bytes:
    halfwords = (
        0xB5FF,       # push {r0-r7,lr}
        0x4B0C,       # ldr r3,=SCRATCH
        0x4C0C,       # ldr r4,=MAGIC
        0x601C,       # str r4,[r3]
        0x685C,       # ldr r4,[r3,#4]
        0x3401,       # adds r4,#1
        0x605C,       # str r4,[r3,#4]
        0x6098,       # str r0,[r3,#8] (skill ID)
        0x60D9,       # str r1,[r3,#12] (level/context)
        0x611A,       # str r2,[r3,#16] (destination)
        0xBCFF,       # pop {r0-r7}; caller return remains stacked
    )
    code = struct.pack(f"<{len(halfwords)}H", *halfwords)
    code += encode_thumb_bl(STUB + len(code), INITIALIZER)
    code += struct.pack(
        "<12H",
        0xB40F,       # push {r0-r3}
        0x4805,       # ldr r0,=SCRATCH
        0x6901,       # ldr r1,[r0,#16]
        0x680A, 0x6142,  # output +0..+3
        0x684A, 0x6182,  # output +4..+7
        0x688A, 0x61C2,  # output +8..+11
        0x68CA, 0x6202,  # output +12..+15
        0xBC0F,       # pop {r0-r3}
    )
    code += struct.pack("<H2I", 0xBD00, SCRATCH, MAGIC)
    if len(code) != STUB_SIZE:
        raise AssertionError(len(code))
    return code


def build_probe(
    base: bytes, *, skill_id: int | None = None, byte_04: int | None = None,
    force_skill_id: int | None = None,
) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    if (skill_id is None) != (byte_04 is None):
        raise ValueError("skill ID and byte +4 must be provided together")
    if skill_id is not None and not 0 <= skill_id < SKILL_COUNT:
        raise ValueError(f"skill ID must be in 0..{SKILL_COUNT - 1}")
    if byte_04 is not None and not 0 <= byte_04 <= 0xFF:
        raise ValueError("byte +4 must fit u8")
    if force_skill_id is not None and not 0 <= force_skill_id < SKILL_COUNT:
        raise ValueError(f"forced skill ID must be in 0..{SKILL_COUNT - 1}")
    hook_offset = HOOK - ROM_BASE
    if base[hook_offset:hook_offset + 4] != EXPECTED_HOOK:
        raise ValueError("skill-detail initializer call does not match")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("skill-detail probe stub region is not zero-filled")
    force_offset = FORCE_ID_LOAD - ROM_BASE
    if base[force_offset:force_offset + 2] != EXPECTED_FORCE_ID_LOAD:
        raise ValueError("skill-detail action-ID load does not match")

    rom = bytearray(base)
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(HOOK, STUB)
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = _stub()
    if skill_id is not None:
        rom[SKILL_TABLE + skill_id * SKILL_SIZE + 4] = byte_04
    if force_skill_id is not None:
        rom[force_offset:force_offset + 2] = struct.pack("<H", 0x2280 | force_skill_id)
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--skill-id", type=int)
    parser.add_argument("--byte-04", type=int)
    parser.add_argument("--force-skill-id", type=int)
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(), skill_id=args.skill_id, byte_04=args.byte_04,
        force_skill_id=args.force_skill_id,
    )
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
