#!/usr/bin/env python3
"""Trace battle-message table selection with an optional same-table pointer A/B."""
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
HOOK = 0x080985E2
EXPECTED_HOOK = bytes.fromhex("327c0221")  # ldrb r2,[r6,#0x10]; movs r1,#2
STUB = 0x0809E900
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 68
SCRATCH = 0x0203FD60
MAGIC = 0x52504D42  # "BMPR"
MESSAGE_TABLE = 0x5A2034
MESSAGE_TABLE_BUS = ROM_BASE + MESSAGE_TABLE
MESSAGE_COUNT = 79


def _stub() -> bytes:
    halfwords = (
        0xB40F,                   # push {r0-r3}; r0 is selected pointer
        0x4A0D, 0x490D, 0x6011,  # scratch, magic
        0x6851, 0x3101, 0x6051,  # ++hit count
        0x7831, 0x6091,           # zero-based r6[0] message ID
        0x7831, 0x0089,           # id * 4
        0x4B0A, 0x18C9, 0x60D1,  # table entry address
        0x6110,                   # selected pointer
        0x6801, 0x6151,           # target bytes 0..3
        0x6841, 0x6191,           # target bytes 4..7
        0x6881, 0x61D1,           # target bytes 8..11
        0x68C1, 0x6211,           # target bytes 12..15
        0xBC0F,                   # pop {r0-r3}
        0x7C32, 0x2102,           # replaced originals
        0x4770, 0x46C0,           # bx lr; align
    )
    return struct.pack(
        f"<{len(halfwords)}H3I",
        *halfwords,
        SCRATCH,
        MAGIC,
        MESSAGE_TABLE_BUS,
    )


def build_probe(
    base: bytes,
    *,
    message_id: int | None = None,
    replacement_id: int | None = None,
) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    if (message_id is None) != (replacement_id is None):
        raise ValueError("message ID and replacement ID must be provided together")
    for label, value in (("message ID", message_id), ("replacement ID", replacement_id)):
        if value is not None and not 0 <= value < MESSAGE_COUNT:
            raise ValueError(f"{label} must be in 0..{MESSAGE_COUNT - 1}")

    hook_offset = HOOK - ROM_BASE
    if base[hook_offset:hook_offset + 4] != EXPECTED_HOOK:
        raise ValueError("battle-message selector bytes do not match")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("battle-message probe stub region is not zero-filled")
    stub = _stub()
    if len(stub) != STUB_SIZE:
        raise AssertionError(len(stub))

    rom = bytearray(base)
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(HOOK, STUB)
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = stub
    if message_id is not None and replacement_id is not None:
        target = MESSAGE_TABLE + message_id * 4
        source = MESSAGE_TABLE + replacement_id * 4
        rom[target:target + 4] = base[source:source + 4]
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--message-id", type=int)
    parser.add_argument("--replacement-id", type=int)
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(),
        message_id=args.message_id,
        replacement_id=args.replacement_id,
    )
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
