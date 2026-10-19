#!/usr/bin/env python3
"""Trace natural UI task callback selection with an optional same-table A/B."""
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
DISPATCHER = 0x08061D8C
HOOKS = (0x08061D84, 0x0807C61C)
EXPECTED_HOOKS = tuple(encode_thumb_bl(hook, DISPATCHER) for hook in HOOKS)
STUB = 0x0809E700
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 76
SCRATCH = 0x0203F1C0
TRACE_SIZE = 40
MAGIC = 0x52504650  # "PFPR"
SENTINEL_BASE = 0x0853D5F0
POINTER_TABLE = 0x53D5F4
POINTER_COUNT = 11


def _stub() -> bytes:
    halfwords = (
        0xB5F0,                   # push {r4-r7,lr}
        0x1C04, 0x1C0D, 0x1C16,  # preserve callback ID and arguments
        0x4F0D, 0x4B0E,           # ldr r7,=SCRATCH; ldr r3,=MAGIC
        0x603B,                   # magic
        0x687B, 0x3301, 0x607B,  # ++hit count
        0x60BC, 0x60FD, 0x613E,  # callback ID, arg1, arg2
        0x00A3, 0x4A0A, 0x189B,  # entry = sentinel + callback_id*4
        0x617B,                   # entry address
        0x681A, 0x61BA,           # selected callback pointer
        0x2C02, 0xD104,           # keep a durable callback-2 sample
        0x69F9, 0x3101, 0x61F9,  # ++callback-2 hit count
        0x623B, 0x627A,           # callback-2 entry and selected pointer
        0x1C20, 0x1C29, 0x1C32,  # restore r0-r2
    )
    code = struct.pack(f"<{len(halfwords)}H", *halfwords)
    code += encode_thumb_bl(STUB + len(code), DISPATCHER)
    code += struct.pack("<HIII", 0xBDF0, SCRATCH, MAGIC, SENTINEL_BASE)
    if len(code) != STUB_SIZE:
        raise AssertionError(len(code))
    return code


def build_probe(
    base: bytes,
    *,
    callback_id: int | None = None,
    replacement_id: int | None = None,
) -> bytes:
    """Install the call trace and optionally replace one callback with a peer."""
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    if (callback_id is None) != (replacement_id is None):
        raise ValueError("callback ID and replacement ID must be provided together")
    if callback_id is not None and not 1 <= callback_id <= POINTER_COUNT:
        raise ValueError(f"callback ID must be in 1..{POINTER_COUNT}")
    if replacement_id is not None and not 1 <= replacement_id <= POINTER_COUNT:
        raise ValueError(f"replacement ID must be in 1..{POINTER_COUNT}")

    for hook, expected in zip(HOOKS, EXPECTED_HOOKS):
        offset = hook - ROM_BASE
        if base[offset : offset + 4] != expected:
            raise ValueError(f"dispatcher call at 0x{hook:08X} does not match")
    if any(base[STUB_OFFSET : STUB_OFFSET + STUB_SIZE]):
        raise ValueError("function pointer probe stub region is not zero-filled")
    for index in range(POINTER_COUNT):
        expected = 0x08061C8D + index * 12
        actual = int.from_bytes(
            base[POINTER_TABLE + index * 4 : POINTER_TABLE + index * 4 + 4],
            "little",
        )
        if actual != expected:
            raise ValueError(f"callback pointer {index + 1} does not match")

    rom = bytearray(base)
    for hook in HOOKS:
        offset = hook - ROM_BASE
        rom[offset : offset + 4] = encode_thumb_bl(hook, STUB)
    rom[STUB_OFFSET : STUB_OFFSET + STUB_SIZE] = _stub()
    if callback_id is not None and replacement_id is not None:
        target = POINTER_TABLE + (callback_id - 1) * 4
        source = POINTER_TABLE + (replacement_id - 1) * 4
        rom[target : target + 4] = base[source : source + 4]
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--callback-id", type=int)
    parser.add_argument("--replacement-id", type=int)
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(),
        callback_id=args.callback_id,
        replacement_id=args.replacement_id,
    )
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
