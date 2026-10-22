#!/usr/bin/env python3
"""Build a one-shot effect probe after resetting the natural OBJ resource window."""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from tools.build_save_state_runtime_probe import encode_thumb_bl
except ModuleNotFoundError:  # direct ``python3 tools/...py`` execution
    from build_save_state_runtime_probe import encode_thumb_bl


BASE_SHA1 = "26f60795fa5e63b4f0264b84e453beffd56b9f7d"
ROM_BASE = 0x08000000
HOOK = 0x08061F76
HOOK_OFFSET = HOOK - ROM_BASE
SOUND_MAIN = 0x0809AAB4
RESOURCE_ALLOCATOR_RESET = 0x0807FDCC
SEQUENCE_BINDER = 0x0807C5E8
STUB = 0x0809E820
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 68
SCRATCH = 0x0203FF40
BINDER_RETURN = 0x0809E85A
RESET_CALL_OFFSET = 0x20
BINDER_ARGUMENT_OFFSET = 0x32
BINDER_CALL_OFFSET = 0x36
BINDER_RETURN_OFFSET = 0x3A
MIN_SEQUENCE_ID = 1
MAX_SEQUENCE_ID = 21


def _stub(sequence_id: int, side: int) -> bytes:
    code = struct.pack("<H", 0xB510)  # push {r4,lr}
    code += encode_thumb_bl(STUB + len(code), SOUND_MAIN)
    code += struct.pack(
        "<13H",
        0x4C0E,                 # ldr r4, =SCRATCH
        0x6820,                 # ldr r0, [r4]
        0x2800,                 # cmp r0, #0
        0xD115,                 # bne done
        0x2001,                 # movs r0, #1
        0x6020,                 # str r0, [r4]
        0x20C0,                 # movs r0, #0xC0
        0x0080,                 # lsls r0, r0, #2 -> tile 0x300
        0x21E0,                 # movs r1, #0xE0
        0x0089,                 # lsls r1, r1, #2 -> 0x380
        0x3901,                 # subs r1, #1 -> tile 0x37F
        0x220C,                 # movs r2, #12 -> palette start
        0x230E,                 # movs r3, #14 -> palette end
    )
    if len(code) != RESET_CALL_OFFSET:
        raise AssertionError(len(code))
    code += encode_thumb_bl(STUB + len(code), RESOURCE_ALLOCATOR_RESET)
    code += struct.pack("<7H", *(0x46C0 for _ in range(7)))  # alignment NOPs
    if len(code) != BINDER_ARGUMENT_OFFSET:
        raise AssertionError(len(code))
    code += struct.pack("<2H", 0x2000 | side, 0x2100 | sequence_id)
    code += encode_thumb_bl(STUB + len(code), SEQUENCE_BINDER)
    if STUB + len(code) != BINDER_RETURN:
        raise AssertionError(hex(STUB + len(code)))
    code += struct.pack(
        "<HHHI",
        0xBC10,                 # done: pop {r4}
        0xBC01,                 # pop {r0}
        0x4700,                 # bx r0
        SCRATCH,
    )
    if len(code) != STUB_SIZE:
        raise AssertionError(len(code))
    return code


def build_probe(base: bytes, *, sequence_id: int, side: int) -> bytes:
    if not MIN_SEQUENCE_ID <= sequence_id <= MAX_SEQUENCE_ID:
        raise ValueError(
            f"sequence ID must be in {MIN_SEQUENCE_ID}..{MAX_SEQUENCE_ID}"
        )
    if side not in (0, 1):
        raise ValueError("side must be 0 or 1")
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    if base[HOOK_OFFSET:HOOK_OFFSET + 4] != encode_thumb_bl(HOOK, SOUND_MAIN):
        raise ValueError("SoundMain call-site bytes do not match")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("controlled allocator-reset stub region is not zero-filled")

    rom = bytearray(base)
    rom[HOOK_OFFSET:HOOK_OFFSET + 4] = encode_thumb_bl(HOOK, STUB)
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = _stub(sequence_id, side)
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--sequence-id", type=int, required=True)
    parser.add_argument("--side", type=int, required=True, choices=(0, 1))
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(), sequence_id=args.sequence_id, side=args.side
    )
    args.output_rom.parent.mkdir(parents=True, exist_ok=True)
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
