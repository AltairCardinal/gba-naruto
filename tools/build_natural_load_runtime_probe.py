#!/usr/bin/env python3
"""Observe the optional battle-state caller of the complete load wrapper."""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from tools.build_save_state_runtime_probe import encode_thumb_bl
except ModuleNotFoundError:
    from build_save_state_runtime_probe import encode_thumb_bl

BASE_SHA1 = "26f60795fa5e63b4f0264b84e453beffd56b9f7d"
ROM_BASE = 0x08000000
HOOK = 0x080752DA
ORIGINAL = 0x08068AF0
STUB = 0x0809E860
STUB_OFFSET = STUB - ROM_BASE
# The load transition clears EWRAM after this call.  Reserve the final 16 SRAM
# bytes (outside the proven 0x57C4 descriptor span) so the observer survives
# long enough for the browser probe to read it.
SCRATCH = 0x0E007FF0
STUB_SIZE = 32


def build_probe(base: bytes) -> bytes:
    if hashlib.sha1(base).hexdigest() != BASE_SHA1:
        raise ValueError("natural-load probe requires the immutable base ROM")
    rom = bytearray(base)
    hook_offset = HOOK - ROM_BASE
    expected = encode_thumb_bl(HOOK, ORIGINAL)
    if rom[hook_offset:hook_offset + 4] != expected:
        raise ValueError("natural load call-site bytes do not match")
    if any(rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("natural-load stub region is not zero-filled")
    stub = struct.pack("<H", 0xB50E) + encode_thumb_bl(STUB + 2, ORIGINAL)
    stub += struct.pack(
        "<8H", 0x4905, 0x22A6, 0x700A, 0x7048,
        0x788A, 0x3201, 0x708A, 0xBD0E,
    )
    stub += bytes(28 - len(stub)) + struct.pack("<I", SCRATCH)
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = stub
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(HOOK, STUB)
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    args = parser.parse_args()
    output = build_probe(args.base_rom.read_bytes())
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
