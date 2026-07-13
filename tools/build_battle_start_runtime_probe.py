#!/usr/bin/env python3
"""Trace scenario-41 prebattle menu and start-task controller results."""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from tools.build_alternate_chapter_runtime_probe import build_probe as build_chapter_probe
    from tools.build_save_state_runtime_probe import encode_thumb_bl
except ModuleNotFoundError:
    from build_alternate_chapter_runtime_probe import build_probe as build_chapter_probe
    from build_save_state_runtime_probe import encode_thumb_bl


ROM_BASE = 0x08000000
SCRATCH = 0x0203F0C0
MAGIC = 0x54534250  # "PBST"

MENU_CALL = 0x0808F894
MENU_TARGET = 0x0808F190
EXPECTED_MENU_CALL = encode_thumb_bl(MENU_CALL, MENU_TARGET)
MENU_STUB = 0x0809E700
MENU_STUB_OFFSET = MENU_STUB - ROM_BASE
MENU_STUB_SIZE = 64

START_CALL = 0x0808FA0A
START_TARGET = 0x08086A54
EXPECTED_START_CALL = encode_thumb_bl(START_CALL, START_TARGET)
START_STUB = 0x0809E740
START_STUB_OFFSET = START_STUB - ROM_BASE
START_STUB_SIZE = 64

LINEUP_CALL = 0x08086B0A
LINEUP_TARGET = 0x080861C8
EXPECTED_LINEUP_CALL = encode_thumb_bl(LINEUP_CALL, LINEUP_TARGET)
LINEUP_STUB = 0x0809E900
LINEUP_STUB_OFFSET = LINEUP_STUB - ROM_BASE
LINEUP_STUB_SIZE = 48

LINEUP_EXIT_HOOK = 0x080866AC
EXPECTED_LINEUP_EXIT = bytes.fromhex("28140fb0")  # asrs r0,r5,#16; add sp,#0x3c
LINEUP_EXIT_STUB = 0x0809E980
LINEUP_EXIT_STUB_OFFSET = LINEUP_EXIT_STUB - ROM_BASE
LINEUP_EXIT_STUB_SIZE = 24
LINEUP_EXIT_SCRATCH = SCRATCH + 0x40

DEPLOY_CALL = 0x08086BD0
DEPLOY_TARGET = 0x080868AC
EXPECTED_DEPLOY_CALL = encode_thumb_bl(DEPLOY_CALL, DEPLOY_TARGET)
DEPLOY_STUB = 0x0809E940
DEPLOY_STUB_OFFSET = DEPLOY_STUB - ROM_BASE
DEPLOY_STUB_SIZE = 48

A880 = 0x0200A880
OUTER_STATE = 0x020311D4
BATTLE_CONTROL = 0x02026804


def _menu_stub() -> bytes:
    # Scratch layout:
    # +00 magic, +04 menu call count, +09 result, +0A raw A880,
    # +0B A882, +0C outer state, +0E chapter ID.
    prefix = struct.pack(
        "<2H",
        0xB5FE,  # push {r1-r7,lr}
        0xF000,  # first half of BL, replaced below
    )
    prefix += b"\x00\x00"
    suffix = struct.pack(
        "<20H",
        0x1C05,       # mov r5,r0
        0x4906,       # ldr r1,=SCRATCH
        0x4A0A,       # ldr r2,=MAGIC
        0x600A,       # str r2,[r1]
        0x684A, 0x3201, 0x604A,  # ++menu call count
        0x724D,       # strb r5,[r1,#9]
        0x4A08,       # ldr r2,=A880
        0x7813, 0x728B,  # A880 -> +0A
        0x7893, 0x72CB,  # A882 -> +0B
        0x4A06,       # ldr r2,=OUTER_STATE
        0x8A53, 0x818B,  # outer +12 halfword -> scratch +0C
        0x7D93, 0x738B,  # outer +16 chapter -> scratch +0E
        0x1C28,       # mov r0,r5
        0xBDFE,       # pop {r1-r7,pc}
    )
    code = bytearray(prefix + suffix + struct.pack("<H", 0x46C0))
    code[2:6] = encode_thumb_bl(MENU_STUB + 2, MENU_TARGET)
    code += struct.pack("<4I", SCRATCH, MAGIC, A880, OUTER_STATE)
    if len(code) != MENU_STUB_SIZE:
        raise AssertionError(len(code))
    return bytes(code)


def _start_stub() -> bytes:
    # Scratch layout extension:
    # +10 start call count, +14 result, +15 raw A880,
    # +18 outer state, +1A chapter ID, +1B battle ID.
    prefix = struct.pack("<2H", 0xB5FE, 0xF000) + b"\x00\x00"
    suffix = struct.pack(
        "<19H",
        0x1C05,       # mov r5,r0
        0x4908,       # ldr r1,=SCRATCH
        0x690A, 0x3201, 0x610A,  # ++start call count
        0x750D,       # strb r5,[r1,#20]
        0x4A07,       # ldr r2,=A880
        0x7813, 0x754B,  # A880 -> +15
        0x4A06,       # ldr r2,=OUTER_STATE
        0x8A53, 0x830B,  # outer +12 halfword -> scratch +18
        0x7D93, 0x768B,  # outer +16 chapter -> scratch +1A
        0x4A05,       # ldr r2,=BATTLE_CONTROL
        0x7853, 0x76CB,  # battle +1 -> scratch +1B
        0x1C28,       # mov r0,r5
        0xBDFE,       # pop {r1-r7,pc}
    )
    code = bytearray(prefix + suffix)
    code[2:6] = encode_thumb_bl(START_STUB + 2, START_TARGET)
    code += struct.pack("<4I", SCRATCH, A880, OUTER_STATE, BATTLE_CONTROL)
    code += struct.pack("<2H", 0x46C0, 0x46C0)
    if len(code) != START_STUB_SIZE:
        raise AssertionError(len(code))
    return bytes(code)


def _result_stub(
    *, stub: int, target: int, count_load: int, count_store: int,
    result_store: int, a880_store: int, outer_store: int,
) -> bytes:
    # Keep the original call transparent while retaining both the raw signed
    # result and the UI/outer-state words visible at that return boundary.
    code = bytearray(struct.pack(
        "<18H",
        0xB5FE,       # push {r1-r7,lr}
        0xF000, 0x0000,  # BL placeholder
        0x1C05,       # mov r5,r0
        0x4906,       # ldr r1,=SCRATCH
        count_load, 0x3201, count_store,
        result_store,
        0x4A05,       # ldr r2,=A880
        0x6813,       # ldr r3,[r2]
        a880_store,
        0x4A04,       # ldr r2,=OUTER_STATE
        0x6953,       # ldr r3,[r2,#0x14]
        outer_store,
        0x1C28,       # mov r0,r5
        0xBDFE,       # pop {r1-r7,pc}
        0x46C0,       # align literals
    ))
    code[2:6] = encode_thumb_bl(stub + 2, target)
    code += struct.pack("<3I", SCRATCH, A880, OUTER_STATE)
    if len(code) != 48:
        raise AssertionError(len(code))
    return bytes(code)


def _lineup_stub() -> bytes:
    # +20 count, +24 signed result, +28 A880..A883, +2C outer +14..+17.
    return _result_stub(
        stub=LINEUP_STUB,
        target=LINEUP_TARGET,
        count_load=0x6A0A,
        count_store=0x620A,
        result_store=0x848D,
        a880_store=0x628B,
        outer_store=0x62CB,
    )


def _lineup_exit_stub() -> bytes:
    # This hook also catches checkpoints saved inside the original lineup
    # function, before the patched caller wrapper could have run. Keep its
    # counter/result separate from the caller wrapper at scratch +0x20 so a
    # normal return cannot masquerade as two independent calls.
    code = struct.pack(
        "<10HI",
        0x1428,       # original asrs r0,r5,#16
        0x1C03,       # mov r3,r0
        0x4903,       # ldr r1,=LINEUP_EXIT_SCRATCH
        0x680A, 0x3201, 0x600A,  # ++lineup exit count
        0x808B,       # strh r3,[r1,#0x04]
        0x1C18,       # mov r0,r3
        0xB00F,       # original add sp,#0x3c
        0x4770,       # bx lr
        LINEUP_EXIT_SCRATCH,
    )
    if len(code) != LINEUP_EXIT_STUB_SIZE:
        raise AssertionError(len(code))
    return code


def _deploy_stub() -> bytes:
    # +30 count, +34 signed result, +38 A880..A883, +3C outer +14..+17.
    return _result_stub(
        stub=DEPLOY_STUB,
        target=DEPLOY_TARGET,
        count_load=0x6B0A,
        count_store=0x630A,
        result_store=0x868D,
        a880_store=0x638B,
        outer_store=0x63CB,
    )


def build_probe(base: bytes) -> bytes:
    menu_offset = MENU_CALL - ROM_BASE
    start_offset = START_CALL - ROM_BASE
    lineup_offset = LINEUP_CALL - ROM_BASE
    lineup_exit_offset = LINEUP_EXIT_HOOK - ROM_BASE
    deploy_offset = DEPLOY_CALL - ROM_BASE
    if base[menu_offset:menu_offset + 4] != EXPECTED_MENU_CALL:
        raise ValueError("prebattle menu call bytes do not match")
    if base[start_offset:start_offset + 4] != EXPECTED_START_CALL:
        raise ValueError("start-task call bytes do not match")
    if base[lineup_offset:lineup_offset + 4] != EXPECTED_LINEUP_CALL:
        raise ValueError("lineup call bytes do not match")
    if base[lineup_exit_offset:lineup_exit_offset + 4] != EXPECTED_LINEUP_EXIT:
        raise ValueError("lineup exit bytes do not match")
    if base[deploy_offset:deploy_offset + 4] != EXPECTED_DEPLOY_CALL:
        raise ValueError("deployment call bytes do not match")
    if any(base[MENU_STUB_OFFSET:MENU_STUB_OFFSET + MENU_STUB_SIZE]):
        raise ValueError("menu stub region is not zero-filled")
    if any(base[START_STUB_OFFSET:START_STUB_OFFSET + START_STUB_SIZE]):
        raise ValueError("start stub region is not zero-filled")
    if any(base[LINEUP_STUB_OFFSET:LINEUP_STUB_OFFSET + LINEUP_STUB_SIZE]):
        raise ValueError("lineup stub region is not zero-filled")
    if any(base[LINEUP_EXIT_STUB_OFFSET:LINEUP_EXIT_STUB_OFFSET + LINEUP_EXIT_STUB_SIZE]):
        raise ValueError("lineup exit stub region is not zero-filled")
    if any(base[DEPLOY_STUB_OFFSET:DEPLOY_STUB_OFFSET + DEPLOY_STUB_SIZE]):
        raise ValueError("deployment stub region is not zero-filled")

    rom = bytearray(build_chapter_probe(base, force_alternate=False))
    rom[menu_offset:menu_offset + 4] = encode_thumb_bl(MENU_CALL, MENU_STUB)
    rom[start_offset:start_offset + 4] = encode_thumb_bl(START_CALL, START_STUB)
    rom[lineup_offset:lineup_offset + 4] = encode_thumb_bl(LINEUP_CALL, LINEUP_STUB)
    rom[lineup_exit_offset:lineup_exit_offset + 4] = encode_thumb_bl(LINEUP_EXIT_HOOK, LINEUP_EXIT_STUB)
    rom[deploy_offset:deploy_offset + 4] = encode_thumb_bl(DEPLOY_CALL, DEPLOY_STUB)
    rom[MENU_STUB_OFFSET:MENU_STUB_OFFSET + MENU_STUB_SIZE] = _menu_stub()
    rom[START_STUB_OFFSET:START_STUB_OFFSET + START_STUB_SIZE] = _start_stub()
    rom[LINEUP_STUB_OFFSET:LINEUP_STUB_OFFSET + LINEUP_STUB_SIZE] = _lineup_stub()
    rom[LINEUP_EXIT_STUB_OFFSET:LINEUP_EXIT_STUB_OFFSET + LINEUP_EXIT_STUB_SIZE] = _lineup_exit_stub()
    rom[DEPLOY_STUB_OFFSET:DEPLOY_STUB_OFFSET + DEPLOY_STUB_SIZE] = _deploy_stub()
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
