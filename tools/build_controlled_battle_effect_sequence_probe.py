#!/usr/bin/env python3
"""Build a one-shot controlled battle-effect sequence probe ROM."""

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
SEQUENCE_BINDER = 0x0807C5E8
STUB = 0x0809E840
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 36
SCRATCH = 0x0203FF40
MIN_SEQUENCE_ID = 1
MAX_SEQUENCE_ID = 21


def _stub(sequence_id: int) -> bytes:
    code = struct.pack("<H", 0xB510)  # push {r4,lr}
    code += encode_thumb_bl(STUB + len(code), SOUND_MAIN)
    code += struct.pack(
        "<8H",
        0x4C06,                 # ldr r4, =SCRATCH
        0x6820,                 # ldr r0, [r4]
        0x2800,                 # cmp r0, #0
        0xD105,                 # bne done
        0x2001,                 # movs r0, #1
        0x6020,                 # str r0, [r4]
        0x2000,                 # movs r0, #0 (player side)
        0x2100 | sequence_id,   # movs r1, #sequence_id
    )
    code += encode_thumb_bl(STUB + len(code), SEQUENCE_BINDER)
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


def build_probe(base: bytes, *, sequence_id: int) -> bytes:
    if not MIN_SEQUENCE_ID <= sequence_id <= MAX_SEQUENCE_ID:
        raise ValueError(
            f"sequence ID must be in {MIN_SEQUENCE_ID}..{MAX_SEQUENCE_ID}"
        )
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    if base[HOOK_OFFSET:HOOK_OFFSET + 4] != encode_thumb_bl(HOOK, SOUND_MAIN):
        raise ValueError("SoundMain call-site bytes do not match")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("controlled sequence stub region is not zero-filled")

    rom = bytearray(base)
    rom[HOOK_OFFSET:HOOK_OFFSET + 4] = encode_thumb_bl(HOOK, STUB)
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = _stub(sequence_id)
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--sequence-id", type=int, required=True)
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(), sequence_id=args.sequence_id
    )
    args.output_rom.parent.mkdir(parents=True, exist_ok=True)
    args.output_rom.write_bytes(output)
    print(
        f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
