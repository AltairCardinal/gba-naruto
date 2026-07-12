#!/usr/bin/env python3
"""Trace the first and last callers of the shared tilemap panel writer."""
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
WRITER = 0x08066D14
CALL_SITES = (
    0x08066E92, 0x080671DE, 0x08067858, 0x0806ED9E, 0x0806F3BA,
    0x0806F4AE, 0x080708D6, 0x08071158, 0x08071576, 0x08078410,
    0x0807858A, 0x08078918, 0x08078CCA, 0x08078D16, 0x08078F7E,
    0x08078F98, 0x080790C6, 0x080793CC, 0x0807A800, 0x0807A91A,
    0x0807F7EE, 0x0807F7F4, 0x0807F7FA, 0x0807FC2C, 0x0807FC32,
    0x0807FC38, 0x080816DA, 0x080816FA, 0x08086D4A, 0x08086DCC,
    0x08089DCA, 0x0808AB64, 0x0808AFF2, 0x0808D574, 0x0808E418,
    0x0808E6A0, 0x0808EB90, 0x080912B2, 0x080912FC, 0x0809149A,
    0x080914A2, 0x08091AF4, 0x08091BAE, 0x08091C98, 0x08091DF8,
    0x08091E00, 0x08091EAE, 0x08091EB6, 0x080926C2, 0x080926CC,
    0x0809376A, 0x08093EAE, 0x0809402A, 0x08094BE8, 0x08095158,
    0x080951A4, 0x0809541E, 0x08095436, 0x08095550, 0x08095868,
    0x08097030, 0x0809718C, 0x0809730E, 0x0809737A, 0x080973C2,
    0x080973E2, 0x08097454, 0x08097516, 0x080979A6, 0x080979F2,
    0x08097A70, 0x08097B2E, 0x080985D4, 0x08099518, 0x08099CBE,
)
STUB = 0x0809E800
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 48
SCRATCH = 0x0203F800
MAGIC = 0x52574D54  # "TMWR"


def _stub() -> bytes:
    halfwords = (
        0xB5FF,       # push {r0-r7,lr}
        0x4674,       # mov r4,lr (call-site return address)
        0x4908,       # ldr r1,=SCRATCH
        0x4A09,       # ldr r2,=MAGIC
        0x600A,       # str r2,[r1]
        0x684A,       # ldr r2,[r1,#4]
        0x2A00,       # cmp r2,#0
        0xD101,       # bne skip_first
        0x608C,       # str r4,[r1,#8] (first caller return)
        0x60C8,       # str r0,[r1,#12] (first panel ID)
        0x3201,       # adds r2,#1
        0x604A,       # str r2,[r1,#4]
        0x610C,       # str r4,[r1,#16] (last caller return)
        0x6148,       # str r0,[r1,#20] (last panel ID)
        0xBCFF,       # pop {r0-r7}; caller return remains stacked
    )
    code = struct.pack(f"<{len(halfwords)}H", *halfwords)
    code += encode_thumb_bl(STUB + len(code), WRITER)
    code += struct.pack("<3H2I", 0xBD00, 0x46C0, 0x46C0, SCRATCH, MAGIC)
    if len(code) != STUB_SIZE:
        raise AssertionError(len(code))
    return code


def build_probe(base: bytes) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    expected = set()
    for address in range(ROM_BASE, ROM_BASE + len(base) - 3, 2):
        try:
            encoded = encode_thumb_bl(address, WRITER)
        except ValueError:
            continue
        if base[address - ROM_BASE:address - ROM_BASE + 4] == encoded:
            expected.add(address)
    if expected != set(CALL_SITES):
        raise ValueError("tilemap writer call-site set does not match base ROM")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("tilemap writer trace stub region is not zero-filled")

    rom = bytearray(base)
    for address in CALL_SITES:
        offset = address - ROM_BASE
        rom[offset:offset + 4] = encode_thumb_bl(address, STUB)
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = _stub()
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
