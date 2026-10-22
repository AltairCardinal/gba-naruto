#!/usr/bin/env python3
"""Build a diagnostic ROM that records live 0x0806D85C effect-template calls."""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from tools.build_save_state_runtime_probe import encode_thumb_bl
except ModuleNotFoundError:  # direct `python3 tools/...py` execution
    from build_save_state_runtime_probe import encode_thumb_bl

BASE_SHA1 = "26f60795fa5e63b4f0264b84e453beffd56b9f7d"
ROM_BASE = 0x08000000
CONSUMER = 0x0806D85C
STUB_ADDRESS = 0x0809E740
STUB_OFFSET = STUB_ADDRESS - ROM_BASE
STUB_SIZE = 44
SCRATCH = 0x0203FFD0
LIVE_EFFECT_ID = 2
LIVE_GROWTH_OFFSET = 0x545458 + LIVE_EFFECT_ID * 16 + 14
CALL_SITES = (
    0x0806FE36, 0x080708F0, 0x0807137A, 0x080727C4,
    0x0807557E, 0x08075C58, 0x08075D56, 0x08082430,
    0x080837E2, 0x08084212, 0x08085440, 0x0809280A,
)


def build_probe(base: bytes, growth_value: int | None = None) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    rom = bytearray(base)
    for site in CALL_SITES:
        off = site - ROM_BASE
        expected = encode_thumb_bl(site, CONSUMER)
        if rom[off:off + 4] != expected:
            raise ValueError(f"consumer call before bytes mismatch at 0x{site:08X}")
    if any(rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("effect probe stub region is not zero-filled")
    if growth_value is not None:
        if not 0 <= growth_value <= 0xFFFF:
            raise ValueError("growth value must fit u16")
        if rom[LIVE_GROWTH_OFFSET:LIVE_GROWTH_OFFSET + 2] != bytes.fromhex("0100"):
            raise ValueError("live effect growth before bytes are not 1")
        rom[LIVE_GROWTH_OFFSET:LIVE_GROWTH_OFFSET + 2] = growth_value.to_bytes(2, "little")

    # Preserve id/level/destination in r4/r5/r6, call the original consumer,
    # then record id, level, output type/growth, and output bytes +4..+9.
    halfwords = (
        0xB5F0,       # push {r4-r7,lr}
        0x1C04,       # r4 = r0 (effect id)
        0x1C1E,       # r6 = r3 (destination)
        0x2102,       # force effective level 2 for two-factor A/B
        0x1C0D,       # r5 = r1 (effective level)
    )
    stub = struct.pack("<5H", *halfwords)
    stub += encode_thumb_bl(STUB_ADDRESS + 10, CONSUMER)
    stub += struct.pack(
        "<12H",
        0x4F06, 0x703C, 0x707D, 0x7B30, 0x70B8, 0x89F0,
        0x80B8, 0x6870, 0x60B8, 0x8930, 0x81B8, 0xBDF0,
    )
    stub += bytes(2)
    stub += struct.pack("<I", SCRATCH)
    if len(stub) != STUB_SIZE:
        raise AssertionError(len(stub))
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = stub
    for site in CALL_SITES:
        off = site - ROM_BASE
        rom[off:off + 4] = encode_thumb_bl(site, STUB_ADDRESS)
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--growth-value", type=lambda value: int(value, 0), default=None)
    args = parser.parse_args()
    output = build_probe(args.base_rom.read_bytes(), args.growth_value)
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
