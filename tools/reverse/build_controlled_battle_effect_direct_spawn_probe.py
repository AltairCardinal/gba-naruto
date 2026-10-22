#!/usr/bin/env python3
"""Build controlled probes for the remaining direct selector/spawn entries."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct

try:
    from tools.build_save_state_runtime_probe import encode_thumb_bl
except ModuleNotFoundError:
    from build_save_state_runtime_probe import encode_thumb_bl


BASE_SHA1 = "26f60795fa5e63b4f0264b84e453beffd56b9f7d"
ROM_BASE = 0x08000000
HOOK = 0x08061F76
HOOK_OFFSET = HOOK - ROM_BASE
SOUND_MAIN = 0x0809AAB4
RESOURCE_ALLOCATOR_RESET = 0x0807FDCC
SEQUENCE_SELECTOR = 0x0807FE2C
SPAWN_WITHOUT_SIDE = 0x080800A4
SPAWN_WITH_SIDE = 0x08080108
STUB = 0x0809E800
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 64
SCRATCH = 0x0203FF40
SELECTOR_RESULT_SCRATCH = SCRATCH + 4
SOUND_MAIN_CALLSITE = STUB + 2
DONE_BRANCH_OFFSET = 12
RESET_ARGS_OFFSET = 18
RESET_CALLSITE = STUB + 32
SELECTOR_CALLSITE = STUB + 38
SPAWN_CALLSITE = STUB + 50


@dataclass(frozen=True)
class DirectSpawnCase:
    case_id: str
    group_id: int
    sequence_id: int
    spawn_function: int
    side: int | None
    spawn_x: int
    spawn_y: int
    allocator_tile_start: int
    allocator_tile_end: int
    allocator_palette_start: int
    allocator_palette_end: int
    selector_callsite: int = SELECTOR_CALLSITE
    spawn_callsite: int = SPAWN_CALLSITE


CASES = (
    DirectSpawnCase(
        "group-03-sequence-03-side-0-direct-spawn",
        3,
        3,
        SPAWN_WITH_SIDE,
        0,
        104,
        80,
        0x100,
        0x39F,
        4,
        14,
    ),
    DirectSpawnCase(
        "group-03-sequence-03-side-1-direct-spawn",
        3,
        3,
        SPAWN_WITH_SIDE,
        1,
        104,
        80,
        0x100,
        0x39F,
        4,
        14,
    ),
    DirectSpawnCase(
        "group-18-sequence-07-direct-spawn",
        18,
        7,
        SPAWN_WITHOUT_SIDE,
        None,
        120,
        80,
        0x300,
        0x37F,
        12,
        14,
    ),
    DirectSpawnCase(
        "group-18-sequence-18-direct-spawn",
        18,
        18,
        SPAWN_WITHOUT_SIDE,
        None,
        120,
        80,
        0x300,
        0x37F,
        12,
        14,
    ),
)
CASES_BY_ID = {case.case_id: case for case in CASES}


def _patch_literal_load(code: bytearray, instruction_offset: int, literal_offset: int) -> None:
    pc_base = (STUB + instruction_offset + 4) & ~3
    displacement = STUB + literal_offset - pc_base
    if displacement < 0 or displacement % 4 or displacement // 4 > 0xFF:
        raise ValueError("scratch literal is out of Thumb LDR range")
    struct.pack_into("<H", code, instruction_offset, 0x4C00 | (displacement // 4))


def _patch_bne(code: bytearray, instruction_offset: int, target_offset: int) -> None:
    displacement = target_offset - (instruction_offset + 4)
    if displacement % 2 or not -256 <= displacement <= 254:
        raise ValueError("direct-spawn done branch is out of range")
    struct.pack_into("<H", code, instruction_offset, 0xD100 | ((displacement // 2) & 0xFF))


def decode_conditional_branch_target(instruction_offset: int, halfword: int) -> int:
    if halfword & 0xFF00 != 0xD100:
        raise ValueError("instruction is not Thumb BNE")
    displacement = (halfword & 0xFF) << 1
    if displacement & 0x100:
        displacement -= 0x200
    return instruction_offset + 4 + displacement


def _mov_shift(value: int, *, register: int) -> tuple[int, int]:
    for shift in range(8):
        if value % (1 << shift) == 0 and value >> shift <= 0xFF:
            immediate = value >> shift
            return 0x2000 | (register << 8) | immediate, 0x0000 | (shift << 6) | (register << 3) | register
    raise ValueError(f"allocator value 0x{value:X} cannot use compact Thumb mov/shift")


def encode_allocator_reset_arguments(case: DirectSpawnCase) -> tuple[int, ...]:
    if case.allocator_tile_start > case.allocator_tile_end:
        raise ValueError("allocator tile range is reversed")
    if not 0 <= case.allocator_palette_start <= case.allocator_palette_end <= 0xFF:
        raise ValueError("allocator palette range is invalid")
    start_mov, start_shift = _mov_shift(case.allocator_tile_start, register=0)
    end_mov, end_shift = _mov_shift(case.allocator_tile_end + 1, register=1)
    return (
        start_mov,
        start_shift,
        end_mov,
        end_shift,
        0x3901,
        0x2200 | case.allocator_palette_start,
        0x2300 | case.allocator_palette_end,
    )


def encode_spawn_arguments(case: DirectSpawnCase) -> tuple[int, int, int]:
    if not 0 <= case.spawn_x <= 0xFF or not 0 <= case.spawn_y <= 0xFF:
        raise ValueError("spawn coordinates must fit Thumb immediates")
    if case.spawn_function == SPAWN_WITH_SIDE:
        if case.side not in (0, 1):
            raise ValueError("side-aware spawn requires side 0 or 1")
        return 0x2100 | case.side, 0x2200 | case.spawn_x, 0x2300 | case.spawn_y
    if case.spawn_function == SPAWN_WITHOUT_SIDE:
        if case.side is not None:
            raise ValueError("side-less spawn must not carry a side")
        return 0x2100 | case.spawn_x, 0x2200 | case.spawn_y, 0x46C0
    raise ValueError("unsupported direct spawn function")


def build_stub(case: DirectSpawnCase) -> bytes:
    code = bytearray(struct.pack("<H", 0xB510))  # push {r4,lr}
    code.extend(encode_thumb_bl(STUB + len(code), SOUND_MAIN))
    literal_load_offset = len(code)
    code.extend(struct.pack("<H", 0))
    code.extend(struct.pack("<HH", 0x6820, 0x2800))
    done_branch_offset = len(code)
    code.extend(struct.pack("<H", 0))
    code.extend(struct.pack("<HH", 0x2001, 0x6020))
    if len(code) != RESET_ARGS_OFFSET:
        raise AssertionError("allocator reset arguments drift")
    code.extend(struct.pack("<7H", *encode_allocator_reset_arguments(case)))
    if STUB + len(code) != RESET_CALLSITE:
        raise AssertionError("allocator reset callsite drift")
    code.extend(encode_thumb_bl(STUB + len(code), RESOURCE_ALLOCATOR_RESET))
    code.extend(struct.pack("<H", 0x2000 | case.sequence_id))
    if STUB + len(code) != case.selector_callsite:
        raise AssertionError("selector callsite drift")
    code.extend(encode_thumb_bl(STUB + len(code), SEQUENCE_SELECTOR))
    code.extend(struct.pack("<H", 0x6060))  # str r0, [r4, #4]
    code.extend(struct.pack("<3H", *encode_spawn_arguments(case)))
    if STUB + len(code) != case.spawn_callsite:
        raise AssertionError("spawn callsite drift")
    code.extend(encode_thumb_bl(STUB + len(code), case.spawn_function))
    done_offset = len(code)
    code.extend(struct.pack("<HHH", 0xBC10, 0xBC01, 0x4700))
    while len(code) % 4:
        code.extend(struct.pack("<H", 0x46C0))
    literal_offset = len(code)
    code.extend(struct.pack("<I", SCRATCH))
    if len(code) > STUB_SIZE:
        raise AssertionError("direct-spawn stub overflow")
    code.extend(bytes(STUB_SIZE - len(code)))
    _patch_literal_load(code, literal_load_offset, literal_offset)
    _patch_bne(code, done_branch_offset, done_offset)
    return bytes(code)


def build_probe(base: bytes, *, case_id: str) -> bytes:
    case = CASES_BY_ID.get(case_id)
    if case is None:
        raise ValueError(f"unknown direct-spawn case: {case_id}")
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    if base[HOOK_OFFSET:HOOK_OFFSET + 4] != encode_thumb_bl(HOOK, SOUND_MAIN):
        raise ValueError("SoundMain call-site bytes do not match")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("direct-spawn stub region is not zero-filled")
    output = bytearray(base)
    output[HOOK_OFFSET:HOOK_OFFSET + 4] = encode_thumb_bl(HOOK, STUB)
    output[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = build_stub(case)
    return bytes(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--case-id", choices=tuple(CASES_BY_ID), required=True)
    args = parser.parse_args()
    output = build_probe(args.base_rom.read_bytes(), case_id=args.case_id)
    args.output_rom.parent.mkdir(parents=True, exist_ok=True)
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
