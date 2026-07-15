#!/usr/bin/env python3
"""Build a diagnostic ROM that invokes the proven save wrapper during first battle."""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from tools.thumb_branch import encode_thumb_bl
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from thumb_branch import encode_thumb_bl


BASE_SHA1 = "26f60795fa5e63b4f0264b84e453beffd56b9f7d"
ROM_BASE = 0x08000000
ORIGINAL_GROWTH = 0x0806D964
SAVE_ALL_GROUPS = 0x080689A4
STUB_ADDRESS = 0x0809E700
STUB_FILE_OFFSET = STUB_ADDRESS - ROM_BASE
SAVE_RESULT_WRAM = 0x0203FFF0
STUB_SIZE = 32
GROWTH_CALL_SITES = (
    0x0806AD40, 0x0806D20C, 0x0806D5C6, 0x0807760A,
    0x08077D3A, 0x0807D820, 0x08085D7A, 0x08089B68,
    0x08089B76, 0x080931C6, 0x08093868, 0x08097714,
)

def build_probe(base: bytes) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    rom = bytearray(base)
    for call_site in GROWTH_CALL_SITES:
        hook_offset = call_site - ROM_BASE
        expected_hook = encode_thumb_bl(call_site, ORIGINAL_GROWTH)
        if rom[hook_offset:hook_offset + 4] != expected_hook:
            raise ValueError(f"growth call before bytes do not match at 0x{call_site:08X}")
    if any(rom[STUB_FILE_OFFSET:STUB_FILE_OFFSET + STUB_SIZE]):
        raise ValueError("diagnostic stub region is not zero-filled")

    # Preserve the original growth return value across the diagnostic save.
    stub = (
        struct.pack("<H", 0xB510)
        + encode_thumb_bl(STUB_ADDRESS + 2, ORIGINAL_GROWTH)
        + struct.pack("<HHHH", 0x1C04, 0x22A5, 0x4904, 0x700A)
        + encode_thumb_bl(STUB_ADDRESS + 14, SAVE_ALL_GROUPS)
        + struct.pack("<HHH", 0x7048, 0x1C20, 0xBD10)
        + bytes(4)
        + struct.pack("<I", SAVE_RESULT_WRAM)
    )
    rom[STUB_FILE_OFFSET:STUB_FILE_OFFSET + len(stub)] = stub
    for call_site in GROWTH_CALL_SITES:
        hook_offset = call_site - ROM_BASE
        rom[hook_offset:hook_offset + 4] = encode_thumb_bl(call_site, STUB_ADDRESS)
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    args = parser.parse_args()
    output = build_probe(args.base_rom.read_bytes())
    args.output_rom.parent.mkdir(parents=True, exist_ok=True)
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
