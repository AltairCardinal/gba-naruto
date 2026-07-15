#!/usr/bin/env python3
"""Trace the five-record battle resource descriptor table with a safe palette A/B."""
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
HOOK = 0x0807B256
ORIGINAL = 0x080625A4
EXPECTED_HOOK = encode_thumb_bl(HOOK, ORIGINAL)
STUB = 0x0809E900
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 76
SCRATCH = 0x0203FE40
MAGIC = 0x52505252  # "RRPR"
RESOURCE_TABLE = 0x596F0C
RESOURCE_COUNT = 5
RESOURCE_SIZE = 0x10
PALETTE_FIELD = 0x0C
EXPECTED_PALETTE = 0x08170F90


def _stub() -> bytes:
    halfwords = (
        0xB5F0,                   # push {r4-r7,lr}
        0x1C04, 0x1C0D, 0x1C16, 0x1C1F,  # preserve r0-r3
        0x480E, 0x490E,           # ldr r0,=SCRATCH; ldr r1,=MAGIC
        0x6001,                   # magic
        0x6841, 0x3101, 0x6041,  # ++hit count
        0x6085, 0x60C4, 0x6106, 0x6147,  # id, base, arg2, arg3
        0x1C2A, 0x0112, 0x18A2,  # entry = base + id*16
        0x6182,                   # entry address
        0x6811, 0x61C1,           # ptr0
        0x6851, 0x6201,           # ptr1
        0x6891, 0x6241,           # ptr2
        0x68D1, 0x6281,           # ptr3
        0x1C20, 0x1C29, 0x1C32, 0x1C3B,  # restore r0-r3
    )
    code = struct.pack(f"<{len(halfwords)}H", *halfwords)
    code += encode_thumb_bl(STUB + len(code), ORIGINAL)
    code += struct.pack("<HII", 0xBDF0, SCRATCH, MAGIC)
    if len(code) != STUB_SIZE:
        raise AssertionError(len(code))
    return code


def build_probe(
    base: bytes,
    *,
    descriptor_id: int | None = None,
    palette_shift: int = 0,
) -> bytes:
    """Add the dedicated call-site trace and optionally shift one palette source."""
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    if descriptor_id is not None and not 0 <= descriptor_id < RESOURCE_COUNT:
        raise ValueError(f"descriptor ID must be in 0..{RESOURCE_COUNT - 1}")
    if palette_shift not in (0, 8):
        raise ValueError("palette shift must be 0 or 8")
    if palette_shift and descriptor_id is None:
        raise ValueError("descriptor ID is required for a palette shift")

    hook_offset = HOOK - ROM_BASE
    if base[hook_offset:hook_offset + 4] != EXPECTED_HOOK:
        raise ValueError("resource descriptor call-site bytes do not match")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("resource descriptor probe stub region is not zero-filled")

    for index in range(RESOURCE_COUNT):
        field = RESOURCE_TABLE + index * RESOURCE_SIZE + PALETTE_FIELD
        if int.from_bytes(base[field:field + 4], "little") != EXPECTED_PALETTE:
            raise ValueError(f"descriptor {index} palette pointer does not match")

    rom = bytearray(base)
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(HOOK, STUB)
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = _stub()
    if palette_shift:
        field = RESOURCE_TABLE + descriptor_id * RESOURCE_SIZE + PALETTE_FIELD
        rom[field:field + 4] = struct.pack("<I", EXPECTED_PALETTE + palette_shift)
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--descriptor-id", type=int)
    parser.add_argument("--palette-shift", type=int, default=0)
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(),
        descriptor_id=args.descriptor_id,
        palette_shift=args.palette_shift,
    )
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
