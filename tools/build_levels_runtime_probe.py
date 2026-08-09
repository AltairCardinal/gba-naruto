#!/usr/bin/env python3
"""Trace a controlled levels query from a reached action-menu status caller."""
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
QUERY = 0x0806DDA4
HOOK = 0x08069DD0
EXPECTED_HOOK = encode_thumb_bl(HOOK, QUERY)
STUB = 0x0809E700
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 96
SCRATCH = 0x0203F100
MAGIC = 0x5250564C  # "LVPR"
LEVELS_TABLE = 0x5459C8
TARGET_RECORD_ID = 21
TARGET_TYPE = 0x1A
TARGET_LEVEL = 17
EXPECTED_BASE_A = 2
EXPECTED_PER_LEVEL_A = 1
NARUTO_RECORD = 0x5424D0
ACTIVATION_OFFSET = NARUTO_RECORD + 0x48
EXPECTED_SECONDARY_SLOT = bytes((1, 0xFF, 9, 0))


def _stub() -> bytes:
    halfwords = (
        0xB5F0,                   # push {r4-r7,lr}
        0x1C04, 0x1C0D, 0x1C16,  # template, requested type, output
        0x1C27, 0x3750, 0x883B,  # address and original secondary slot 0
        0xB408,                   # preserve original packed ID/level
        0x2315, 0x2011, 0x0200, 0x4303, 0x803B,  # temporary ID21/level17
        0x1C20, 0x1C29, 0x1C32,  # restore query arguments
    )
    code = struct.pack(f"<{len(halfwords)}H", *halfwords)
    code += encode_thumb_bl(STUB + len(code), QUERY)
    code += struct.pack(
        "<26H",
        0x1C05, 0xBC08, 0x803B,  # preserve return and restore live slot
        0x480B, 0x490B,     # scratch, magic
        0x6001,
        0x6841, 0x3101, 0x6041,
        0x6084, 0x211A, 0x60C1, 0x6106, 0x6145,
        0x8831, 0x6181,     # out A
        0x8871, 0x61C1,     # out B
        0x2115, 0x2211, 0x0212, 0x4311, 0x6201,  # packed ID21/level17
        0x1C28, 0xBDF0, 0x46C0,  # restore return; pop; align
    )
    code += struct.pack("<II", SCRATCH, MAGIC)
    if len(code) != STUB_SIZE:
        raise AssertionError(len(code))
    return code


def build_probe(base: bytes, *, per_level_a: int = EXPECTED_PER_LEVEL_A) -> bytes:
    if not 0 <= per_level_a <= 0xFFFF:
        raise ValueError("per-level A must fit u16")
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    hook_offset = HOOK - ROM_BASE
    if base[hook_offset:hook_offset + 4] != EXPECTED_HOOK:
        raise ValueError("levels query call does not match")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("levels probe stub region is not zero-filled")
    if base[ACTIVATION_OFFSET:ACTIVATION_OFFSET + 4] != EXPECTED_SECONDARY_SLOT:
        raise ValueError("Naruto secondary slot 0 does not match")
    record = LEVELS_TABLE + TARGET_RECORD_ID * 12
    if base[record] != TARGET_TYPE:
        raise ValueError("target levels record type does not match")
    if int.from_bytes(base[record + 2:record + 4], "little") != EXPECTED_BASE_A:
        raise ValueError("target levels record base A does not match")
    if int.from_bytes(base[record + 6:record + 8], "little") != EXPECTED_PER_LEVEL_A:
        raise ValueError("target levels record per-level A does not match")

    rom = bytearray(base)
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(HOOK, STUB)
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = _stub()
    rom[record + 6:record + 8] = struct.pack("<H", per_level_a)
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--per-level-a", type=int, default=EXPECTED_PER_LEVEL_A)
    args = parser.parse_args()
    output = build_probe(args.base_rom.read_bytes(), per_level_a=args.per_level_a)
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
