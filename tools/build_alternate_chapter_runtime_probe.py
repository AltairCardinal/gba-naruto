#!/usr/bin/env python3
"""Trace chapter selection/opcodes, optionally forcing alternate table 0x60D54."""
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
SCRATCH = 0x0203FFB0
MAGIC = 0x52504341  # "ACPR" in little-endian memory

SELECTOR_BRANCH = 0x0808F5A4
SELECTOR_OFFSET = SELECTOR_BRANCH - ROM_BASE
EXPECTED_BRANCH = bytes.fromhex("0cd0")  # beq primary path at 0x0808F5C0
FORCE_ALTERNATE = bytes.fromhex("c046")  # nop: fall through alternate path

# Capture r4=scenario and r0=selected script immediately before the interpreter.
SELECTOR_CAPTURE_HOOK = 0x0808F5CC
EXPECTED_SELECTOR_CAPTURE = bytes.fromhex("35760021")  # strb r5,[r6,#0x18]; movs r1,#0
SELECTOR_STUB = 0x0809E780
SELECTOR_STUB_OFFSET = SELECTOR_STUB - ROM_BASE
SELECTOR_STUB_SIZE = 36

# Capture r7 and four bytes at every opcode dispatch, including terminal opcode 00.
DISPATCH_HOOK = 0x080977D8
EXPECTED_DISPATCH = bytes.fromhex("38783928")  # ldrb r0,[r7]; cmp r0,#0x39
DISPATCH_STUB = 0x0809E7C0
DISPATCH_STUB_OFFSET = DISPATCH_STUB - ROM_BASE
DISPATCH_STUB_SIZE = 48


def _selector_stub() -> bytes:
    halfwords = (
        0xB40F,       # push {r0-r3}
        0x4906,       # ldr r1, =SCRATCH
        0x4A06,       # ldr r2, =MAGIC
        0x600A,       # str r2, [r1]
        0x684A, 0x3201, 0x604A,  # ++selectorHitCount
        0x608C,       # str r4, [r1,#8] (scenarioId)
        0x60C8,       # str r0, [r1,#12] (selectedScriptStart)
        0xBC0F,       # pop {r0-r3}
        0x7635,       # original strb r5,[r6,#0x18]
        0x2100,       # original movs r1,#0
        0x4770,       # bx lr
        0x46C0,       # alignment nop
    )
    return struct.pack("<14H2I", *halfwords, SCRATCH, MAGIC)


def _dispatch_stub() -> bytes:
    halfwords = (
        0xB40F,       # push {r0-r3}
        0x4909,       # ldr r1, =SCRATCH
        0x4A09,       # ldr r2, =MAGIC
        0x600A,       # str r2, [r1]
        0x690A, 0x3201, 0x610A,  # ++opcodeHitCount
        0x614F,       # str r7, [r1,#20] (lastOpcodeCursor)
        0x783A, 0x760A,  # byte 0 -> scratch+24
        0x787A, 0x764A,  # byte 1 -> scratch+25
        0x78BA, 0x768A,  # byte 2 -> scratch+26
        0x78FA, 0x76CA,  # byte 3 -> scratch+27
        0xBC0F,       # pop {r0-r3}
        0x7838,       # original ldrb r0,[r7]
        0x2839,       # original cmp r0,#0x39
        0x4770,       # bx lr
    )
    return struct.pack("<20H2I", *halfwords, SCRATCH, MAGIC)


def build_probe(base: bytes, *, force_alternate: bool = True) -> bytes:
    if base[SELECTOR_OFFSET:SELECTOR_OFFSET + 2] != EXPECTED_BRANCH:
        raise ValueError("alternate selector branch bytes do not match")

    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")

    selector_hook_offset = SELECTOR_CAPTURE_HOOK - ROM_BASE
    dispatch_hook_offset = DISPATCH_HOOK - ROM_BASE
    if base[selector_hook_offset:selector_hook_offset + 4] != EXPECTED_SELECTOR_CAPTURE:
        raise ValueError("selector capture hook bytes do not match")
    if base[dispatch_hook_offset:dispatch_hook_offset + 4] != EXPECTED_DISPATCH:
        raise ValueError("dispatch hook bytes do not match")
    if any(base[SELECTOR_STUB_OFFSET:SELECTOR_STUB_OFFSET + SELECTOR_STUB_SIZE]):
        raise ValueError("selector probe stub region is not zero-filled")
    if any(base[DISPATCH_STUB_OFFSET:DISPATCH_STUB_OFFSET + DISPATCH_STUB_SIZE]):
        raise ValueError("dispatch probe stub region is not zero-filled")

    selector_stub = _selector_stub()
    dispatch_stub = _dispatch_stub()
    if len(selector_stub) != SELECTOR_STUB_SIZE or len(dispatch_stub) != DISPATCH_STUB_SIZE:
        raise AssertionError((len(selector_stub), len(dispatch_stub)))

    rom = bytearray(base)
    if force_alternate:
        rom[SELECTOR_OFFSET:SELECTOR_OFFSET + 2] = FORCE_ALTERNATE
    rom[selector_hook_offset:selector_hook_offset + 4] = encode_thumb_bl(SELECTOR_CAPTURE_HOOK, SELECTOR_STUB)
    rom[dispatch_hook_offset:dispatch_hook_offset + 4] = encode_thumb_bl(DISPATCH_HOOK, DISPATCH_STUB)
    rom[SELECTOR_STUB_OFFSET:SELECTOR_STUB_OFFSET + SELECTOR_STUB_SIZE] = selector_stub
    rom[DISPATCH_STUB_OFFSET:DISPATCH_STUB_OFFSET + DISPATCH_STUB_SIZE] = dispatch_stub
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument(
        "--natural-selector",
        action="store_true",
        help="trace the ROM's natural primary/alternate decision without forcing it",
    )
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(), force_alternate=not args.natural_selector
    )
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
