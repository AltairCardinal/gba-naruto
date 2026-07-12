#!/usr/bin/env python3
"""Trace character-profile text selection with an optional same-table pointer A/B."""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from tools.build_relocated_chapter_runtime_probe import build_relocated_probe
    from tools.build_save_state_runtime_probe import encode_thumb_bl
except ModuleNotFoundError:
    from build_relocated_chapter_runtime_probe import build_relocated_probe
    from build_save_state_runtime_probe import encode_thumb_bl


ROM_BASE = 0x08000000
PROFILE_TABLE = 0x5A143C
PROFILE_COUNT = 46
TARGET_CHARACTER_ID = 1
HOOK = 0x0808B1A4
EXPECTED_HOOK = bytes.fromhex("40180068")  # adds r0,r0,r1; ldr r0,[r0]
STUB = 0x0809E8C0
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 60
SCRATCH = 0x0203FE80
MAGIC = 0x52505450  # "PTPR"


def _stub() -> bytes:
    halfwords = (
        0xB40F,       # push {r0-r3}
        0x1840,       # adds r0,r0,r1 (table entry address)
        0x6803,       # ldr r3,[r0] (selected text pointer)
        0x4A0B,       # ldr r2,=SCRATCH
        0x490B,       # ldr r1,=MAGIC
        0x6011,       # str r1,[r2]
        0x6851, 0x3101, 0x6051,  # ++hit count
        0x7831, 0x6091,          # character id -> +8
        0x60D0,                  # table entry address -> +12
        0x6113,                  # selected pointer -> +16
        0x6818, 0x6150,          # target bytes 0..3 -> +20
        0x6858, 0x6190,          # target bytes 4..7 -> +24
        0x6898, 0x61D0,          # target bytes 8..11 -> +28
        0x68D8, 0x6210,          # target bytes 12..15 -> +32
        0xBC0F,                  # pop {r0-r3}
        0x1840, 0x6800,          # replaced originals
        0x4770, 0x46C0,          # bx lr; align
    )
    return struct.pack("<26H2I", *halfwords, SCRATCH, MAGIC)


def build_profile_probe(
    base: bytes,
    spec_path: Path,
    *,
    replacement_id: int | None = None,
) -> bytes:
    """Layer the profile trace and optional character-1 pointer replacement."""
    hook_offset = HOOK - ROM_BASE
    if base[hook_offset:hook_offset + 4] != EXPECTED_HOOK:
        raise ValueError("profile text hook bytes do not match")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("profile text probe stub region is not zero-filled")
    stub = _stub()
    if len(stub) != STUB_SIZE:
        raise AssertionError(len(stub))

    rom = bytearray(build_relocated_probe(base, spec_path))
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(HOOK, STUB)
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = stub
    if replacement_id is not None:
        if not 0 <= replacement_id < PROFILE_COUNT:
            raise ValueError(f"profile replacement ID must be in 0..{PROFILE_COUNT - 1}")
        source = PROFILE_TABLE + replacement_id * 4
        target = PROFILE_TABLE + TARGET_CHARACTER_ID * 4
        pointer = int.from_bytes(base[source:source + 4], "little")
        target_offset = pointer - ROM_BASE
        if not 0 <= target_offset < PROFILE_TABLE:
            raise ValueError("profile replacement pointer is outside the text region")
        if base.find(b"\x00", target_offset, PROFILE_TABLE) < 0:
            raise ValueError("profile replacement text is not NUL terminated")
        rom[target:target + 4] = base[source:source + 4]
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--replacement-id", type=int)
    args = parser.parse_args()
    output = build_profile_probe(
        args.base_rom.read_bytes(), args.spec, replacement_id=args.replacement_id
    )
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
