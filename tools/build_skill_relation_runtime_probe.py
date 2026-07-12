#!/usr/bin/env python3
"""Trace the selected-skill relationship reader and its post-call candidate state."""
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
HOOK = 0x0808E4A4
ORIGINAL = 0x0808FF24
EXPECTED_HOOK = encode_thumb_bl(HOOK, ORIGINAL)
STUB = 0x0809E900
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 112
SCRATCH = 0x0203FDC0
MAGIC = 0x52524B53  # "SKRR"
SKILL_TABLE = 0x545BE4
ROW_3 = 0x545C14
ROW_3_BUS = ROM_BASE + ROW_3
PARENT_FIELD = ROW_3 + 0x0A
CHILD_FIELD = ROW_3 + 0x0B
EXPECTED_PARENT = 2
EXPECTED_CHILD = 3


def _stub() -> bytes:
    halfwords: list[int] = []
    literal_loads: list[tuple[int, int, int]] = []

    def emit(*values: int) -> None:
        halfwords.extend(values)

    def ldr_literal(register: int, value: int) -> None:
        literal_loads.append((len(halfwords), register, value))
        halfwords.append(0)

    emit(0xB5F0, 0x1C04, 0x1C0D)  # save regs; controller->r4, slot->r5
    ldr_literal(6, SCRATCH)
    ldr_literal(7, MAGIC)
    emit(
        0x6037,                   # magic
        0x6872, 0x3201, 0x6072,  # ++hit count
        0x60B4, 0x60F5,           # controller, selected slot
        0x1C2A, 0x0092, 0x18A2, 0x3270,  # selected entry address
        0x7813, 0x6133,           # selected skill ID
        0x7863, 0x6173,           # controller candidate-entry count
    )
    ldr_literal(2, ROW_3_BUS)
    emit(
        0x61B2,                   # row 3 bus pointer
        0x7A93, 0x7AD1, 0x0209, 0x430B, 0x61F3,  # packed +A/+B
        0x1C20, 0x1C29,           # restore original args
    )
    code = struct.pack(f"<{len(halfwords)}H", *halfwords)
    code += encode_thumb_bl(STUB + len(code), ORIGINAL)
    post_halfwords = [0x1C07]  # preserve original return in r7
    post_start = (len(code) // 2)
    literal_loads.append((post_start + len(post_halfwords), 2, 0x24F))
    post_halfwords.append(0)
    post_halfwords.extend((0x18A2, 0x7813, 0x6233, 0x6277))
    literal_loads.append((post_start + len(post_halfwords), 2, 0x204))
    post_halfwords.append(0)
    post_halfwords.extend((0x18A2, 0x7813, 0x62B3, 0x7893, 0x62F3, 0x1C38, 0xBDF0))
    code += struct.pack(f"<{len(post_halfwords)}H", *post_halfwords)
    if len(code) % 4:
        code += struct.pack("<H", 0x46C0)

    literal_offsets: dict[int, int] = {}
    for value in (SCRATCH, MAGIC, ROW_3_BUS, 0x24F, 0x204):
        literal_offsets[value] = len(code)
        code += struct.pack("<I", value)

    mutable = bytearray(code)
    for halfword_index, register, value in literal_loads:
        instruction_offset = halfword_index * 2
        pc = (STUB + instruction_offset + 4) & ~3
        target = STUB + literal_offsets[value]
        distance = target - pc
        if distance < 0 or distance % 4 or distance // 4 > 0xFF:
            raise AssertionError((instruction_offset, target, pc))
        opcode = 0x4800 | (register << 8) | (distance // 4)
        mutable[instruction_offset:instruction_offset + 2] = struct.pack("<H", opcode)

    if len(mutable) > STUB_SIZE:
        raise AssertionError(len(mutable))
    mutable.extend(b"\x00" * (STUB_SIZE - len(mutable)))
    return bytes(mutable)


def build_probe(base: bytes, *, parent_skill_id: int = EXPECTED_PARENT) -> bytes:
    if not 0 <= parent_skill_id <= 0xFF:
        raise ValueError("parent skill ID must fit u8")
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    hook_offset = HOOK - ROM_BASE
    if base[hook_offset:hook_offset + 4] != EXPECTED_HOOK:
        raise ValueError("skill relation call-site bytes do not match")
    if base[PARENT_FIELD] != EXPECTED_PARENT or base[CHILD_FIELD] != EXPECTED_CHILD:
        raise ValueError("skill row 3 relationship bytes do not match")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("skill relation probe stub region is not zero-filled")

    rom = bytearray(base)
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(HOOK, STUB)
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = _stub()
    rom[PARENT_FIELD] = parent_skill_id
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--parent-skill-id", type=int, default=EXPECTED_PARENT)
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(), parent_skill_id=args.parent_skill_id
    )
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
