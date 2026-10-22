#!/usr/bin/env python3
"""Build a traced ROM whose primary scenario 39 uses a codec-authored script."""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Mapping, Sequence
import struct
from pathlib import Path
from typing import Any

try:
    from tools.build_alternate_chapter_runtime_probe import (
        DISPATCH_HOOK,
        DISPATCH_STUB,
        DISPATCH_STUB_OFFSET,
        EXPECTED_DISPATCH,
        EXPECTED_SELECTOR_CAPTURE,
        MAGIC,
        SCRATCH,
        SELECTOR_CAPTURE_HOOK,
        SELECTOR_STUB,
        SELECTOR_STUB_OFFSET,
    )
    from tools.build_chapter_script_probe import BASE_SHA1
    from tools.build_save_state_runtime_probe import encode_thumb_bl
    from tools.chapter_script_codec import encode_script
except ModuleNotFoundError:
    from build_alternate_chapter_runtime_probe import (
        DISPATCH_HOOK,
        DISPATCH_STUB,
        DISPATCH_STUB_OFFSET,
        EXPECTED_DISPATCH,
        EXPECTED_SELECTOR_CAPTURE,
        MAGIC,
        SCRATCH,
        SELECTOR_CAPTURE_HOOK,
        SELECTOR_STUB,
        SELECTOR_STUB_OFFSET,
    )
    from build_chapter_script_probe import BASE_SHA1
    from build_save_state_runtime_probe import encode_thumb_bl
    from chapter_script_codec import encode_script


ROM_BASE = 0x08000000
PRIMARY_TABLE = 0x60C74
SCENARIO_ID = 39
PRIMARY_SCENARIO_39_POINTER = PRIMARY_TABLE + SCENARIO_ID * 4
EXPECTED_PRIMARY_POINTER = 0x08031020
SCRIPT_ADDRESS = 0x0809E800
SCRIPT_OFFSET = SCRIPT_ADDRESS - ROM_BASE
SCRIPT_REGION_SIZE = 0x20
SELECTOR_STUB_SIZE = 40
DISPATCH_STUB_SIZE = 64
DEFAULT_COMMANDS = (
    {"name": "set_battle", "battle_id": 40, "mode": 2},
    {"name": "end"},
)


def _selector_stub() -> bytes:
    """Capture only scenario 39 so a later selector call cannot overwrite it."""
    halfwords = (
        0xB40F,       # push {r0-r3}
        0x2C27,       # cmp r4,#39
        0xD107,       # bne skip capture
        0x4906,       # ldr r1, =SCRATCH
        0x4A06,       # ldr r2, =MAGIC
        0x600A,       # str r2,[r1]
        0x684A, 0x3201, 0x604A,  # ++selectorHitCount
        0x608C,       # str r4,[r1,#8]
        0x60C8,       # str r0,[r1,#12]
        0xBC0F,       # pop {r0-r3}
        0x7635,       # original strb r5,[r6,#0x18]
        0x2100,       # original movs r1,#0
        0x4770,       # bx lr
        0x46C0,       # alignment nop
    )
    return struct.pack("<16H2I", *halfwords, SCRATCH, MAGIC)


def _dispatch_stub() -> bytes:
    """Capture only the four authored bytes at SCRIPT_ADDRESS."""
    halfwords = (
        0xB40F,       # push {r0-r3}
        0x490C,       # ldr r1, =SCRIPT_ADDRESS
        0x1A7A,       # subs r2,r7,r1
        0x2A03,       # cmp r2,#3
        0xD80E,       # bhi skip capture
        0x490B,       # ldr r1, =SCRATCH
        0x4A0B,       # ldr r2, =MAGIC
        0x600A,       # str r2,[r1]
        0x690A, 0x3201, 0x610A,  # ++opcodeHitCount
        0x614F,       # str r7,[r1,#20]
        0x783A, 0x760A,  # byte0 -> scratch+24
        0x787A, 0x764A,  # byte1 -> scratch+25
        0x78BA, 0x768A,  # byte2 -> scratch+26
        0x78FA, 0x76CA,  # byte3 -> scratch+27
        0xBC0F,       # pop {r0-r3}
        0x7838,       # original ldrb r0,[r7]
        0x2839,       # original cmp r0,#0x39
        0x4770,       # bx lr
        0x46C0, 0x46C0,  # align literals
    )
    return struct.pack("<26H3I", *halfwords, SCRIPT_ADDRESS, SCRATCH, MAGIC)


def build_probe(
    base: bytes,
    *,
    commands: Sequence[Mapping[str, Any]] = DEFAULT_COMMANDS,
) -> bytes:
    """Encode commands, redirect primary[39], and add preserving trace hooks."""
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")

    pointer = int.from_bytes(
        base[PRIMARY_SCENARIO_39_POINTER:PRIMARY_SCENARIO_39_POINTER + 4], "little"
    )
    if pointer != EXPECTED_PRIMARY_POINTER:
        raise ValueError(
            "primary scenario 39 pointer mismatch: "
            f"expected 0x{EXPECTED_PRIMARY_POINTER:08X}, got 0x{pointer:08X}"
        )
    selector_hook_offset = SELECTOR_CAPTURE_HOOK - ROM_BASE
    dispatch_hook_offset = DISPATCH_HOOK - ROM_BASE
    if base[selector_hook_offset:selector_hook_offset + 4] != EXPECTED_SELECTOR_CAPTURE:
        raise ValueError("selector capture hook bytes do not match")
    if base[dispatch_hook_offset:dispatch_hook_offset + 4] != EXPECTED_DISPATCH:
        raise ValueError("dispatch hook bytes do not match")
    for name, offset, size in (
        ("selector probe stub", SELECTOR_STUB_OFFSET, SELECTOR_STUB_SIZE),
        ("dispatch probe stub", DISPATCH_STUB_OFFSET, DISPATCH_STUB_SIZE),
        ("semantic script", SCRIPT_OFFSET, SCRIPT_REGION_SIZE),
    ):
        if any(base[offset:offset + size]):
            raise ValueError(f"{name} region is not zero-filled")

    script = encode_script(commands)
    if len(script) > SCRIPT_REGION_SIZE:
        raise ValueError(
            f"encoded chapter script is {len(script)} bytes; region limit is {SCRIPT_REGION_SIZE}"
        )
    selector_stub = _selector_stub()
    dispatch_stub = _dispatch_stub()
    if len(selector_stub) != SELECTOR_STUB_SIZE or len(dispatch_stub) != DISPATCH_STUB_SIZE:
        raise AssertionError((len(selector_stub), len(dispatch_stub)))

    rom = bytearray(base)
    rom[PRIMARY_SCENARIO_39_POINTER:PRIMARY_SCENARIO_39_POINTER + 4] = (
        SCRIPT_ADDRESS.to_bytes(4, "little")
    )
    rom[selector_hook_offset:selector_hook_offset + 4] = encode_thumb_bl(
        SELECTOR_CAPTURE_HOOK, SELECTOR_STUB
    )
    rom[dispatch_hook_offset:dispatch_hook_offset + 4] = encode_thumb_bl(
        DISPATCH_HOOK, DISPATCH_STUB
    )
    rom[SELECTOR_STUB_OFFSET:SELECTOR_STUB_OFFSET + SELECTOR_STUB_SIZE] = selector_stub
    rom[DISPATCH_STUB_OFFSET:DISPATCH_STUB_OFFSET + DISPATCH_STUB_SIZE] = dispatch_stub
    rom[SCRIPT_OFFSET:SCRIPT_OFFSET + len(script)] = script
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--battle-id", type=int, default=40)
    parser.add_argument("--mode", type=int, default=2)
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(),
        commands=(
            {"name": "set_battle", "battle_id": args.battle_id, "mode": args.mode},
            {"name": "end"},
        ),
    )
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
