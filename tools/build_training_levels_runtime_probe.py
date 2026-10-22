#!/usr/bin/env python3
"""Observe natural training entry, row confirmation, and levels +6 consumption."""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from tools.build_chapter_script_probe import BASE_SHA1
    from tools.published_call_observer import (
        ObserverSite,
        RECORD_SIZE,
        assert_non_overlapping_sites,
        patch_observer,
    )
    from tools.thumb_branch import encode_thumb_bl
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from build_chapter_script_probe import BASE_SHA1
    from published_call_observer import (
        ObserverSite,
        RECORD_SIZE,
        assert_non_overlapping_sites,
        patch_observer,
    )
    from thumb_branch import encode_thumb_bl


ROM_BASE = 0x08000000
EVENT_COUNTER = 0x0203F160
STUB_SIZE = 96
CALL_SITES = (
    ObserverSite(
        "training-entry",
        0x0808E16E,
        0x08093698,
        0x0809E700,
        0x0203F180,
        int.from_bytes(b"LTE1", "little"),
        1,
    ),
)
CONFIRM_HOOK = 0x08093670
CONFIRM_ORIGINAL = 0x08093070
CONFIRM_STUB = 0x0809E780
CONFIRM_STUB_SIZE = 96
CONFIRM_SCRATCH = 0x0203F1A0
CONFIRM_RECORD_SIZE = 32
CONFIRM_MAGIC = int.from_bytes(b"LTC1", "little")
CONFIRM_EVENT = 2
CONSUMER_HOOK = 0x080932CA
CONSUMER_EXPECTED = bytes.fromhex("0e4aa179")  # ldr r2,=table; ldrb r1,[r4,#6]
CONSUMER_STUB = 0x0809E800
CONSUMER_STUB_SIZE = 128
CONSUMER_SCRATCH = 0x0203F1C0
CONSUMER_RECORD_SIZE = 64
CONSUMER_MAGIC = int.from_bytes(b"LTV1", "little")
CONSUMER_EVENT = 3
LEVELS_TABLE = 0x085459C8


def _finish_literals(
    halfwords: list[int],
    literal_loads: list[tuple[int, int, int]],
    *,
    stub_address: int,
    stub_size: int,
) -> bytes:
    code = bytearray(struct.pack(f"<{len(halfwords)}H", *halfwords))
    if len(code) % 4:
        code.extend(struct.pack("<H", 0x46C0))
    literal_offsets: dict[int, int] = {}
    for _, _, value in literal_loads:
        if value not in literal_offsets:
            literal_offsets[value] = len(code)
            code.extend(struct.pack("<I", value))
    for halfword_index, register, value in literal_loads:
        instruction_offset = halfword_index * 2
        pc = (stub_address + instruction_offset + 4) & ~3
        target = stub_address + literal_offsets[value]
        distance = target - pc
        if distance < 0 or distance % 4 or distance // 4 > 0xFF:
            raise ValueError("observer literal is outside Thumb LDR range")
        code[instruction_offset : instruction_offset + 2] = struct.pack(
            "<H", 0x4800 | (register << 8) | (distance // 4)
        )
    if len(code) > stub_size:
        raise ValueError("observer exceeds its checked cave")
    code.extend(b"\x00" * (stub_size - len(code)))
    return bytes(code)


def build_confirm_stub() -> bytes:
    """Publish full r0-r3 call arguments, then tail-call the original function."""
    halfwords: list[int] = []
    literal_loads: list[tuple[int, int, int]] = []

    def emit(*values: int) -> None:
        halfwords.extend(values)

    def ldr_literal(register: int, value: int) -> None:
        literal_loads.append((len(halfwords), register, value))
        halfwords.append(0)

    emit(0xB41F)  # push {r0-r4}
    ldr_literal(4, CONFIRM_SCRATCH)
    emit(0x6820)  # ldr r0,[r4]
    ldr_literal(1, CONFIRM_MAGIC)
    emit(
        0x4288, 0xD101, 0x6860, 0xE000, 0x2000,  # checked prior count
        0x2100, 0x6021, 0x3001, 0x6060,          # invalidate and increment
        0x9800, 0x60A0,  # r0 -> +8
        0x9801, 0x60E0,  # r1 -> +12
        0x9802, 0x6120,  # r2 -> +16
        0x9803, 0x6160,  # r3 -> +20
    )
    ldr_literal(1, EVENT_COUNTER)
    emit(
        0x6808, 0x3001, 0x6008, 0x61A0,  # sequence -> +24
        0x2002, 0x61E0,                  # event -> +28
    )
    ldr_literal(0, CONFIRM_MAGIC)
    emit(0x6020)
    ldr_literal(4, CONFIRM_ORIGINAL | 1)
    emit(0x46A4, 0xBC1F, 0x4760)
    return _finish_literals(
        halfwords,
        literal_loads,
        stub_address=CONFIRM_STUB,
        stub_size=CONFIRM_STUB_SIZE,
    )


def build_consumer_stub() -> bytes:
    """Replay the two replaced instructions, then publish their live context."""
    halfwords: list[int] = []
    literal_loads: list[tuple[int, int, int]] = []

    def emit(*values: int) -> None:
        halfwords.extend(values)

    def ldr_literal(register: int, value: int) -> None:
        literal_loads.append((len(halfwords), register, value))
        halfwords.append(0)

    ldr_literal(2, LEVELS_TABLE)
    emit(
        0x79A1,  # ldrb r1,[r4,#6] -- second replaced instruction
        0xB40F,  # push {r0-r3}; preserve original continuation values
    )
    ldr_literal(0, CONSUMER_SCRATCH)
    emit(0x6803)  # ldr r3,[r0]
    ldr_literal(2, CONSUMER_MAGIC)
    emit(
        0x4293,  # cmp r3,r2
        0xD101,  # bne reset_count
        0x6843,  # ldr r3,[r0,#4]
        0xE000,  # b have_count
        0x2300,  # reset_count: movs r3,#0
        0x2200,  # have_count: movs r2,#0
        0x6002,  # invalidate magic
        0x3301,
        0x6043,  # hit count
    )
    ldr_literal(3, EVENT_COUNTER)
    emit(
        0x681A, 0x3201, 0x601A, 0x6082,  # shared sequence -> +8
        0x2303, 0x60C3,                  # event code -> +12
        0x6104,                          # selected row pointer -> +16
        0x9B01, 0x6143,                  # saved levels ID -> +20
        0x1C0B, 0x210C, 0x434B,          # ID * 12
        0x9A02, 0x18D2, 0x6182,          # record address -> +24
        0x6813, 0x61C3,                  # record bytes 0..3 -> +28
        0x6853, 0x6203,                  # record bytes 4..7 -> +32
        0x6893, 0x6243,                  # record bytes 8..11 -> +36
        0x783B, 0x6283,                  # template +BA before -> +40
        0x62C5,                          # template pointer -> +44
        0x6823, 0x6303,                  # row bytes 0..3 -> +48
        0x6863, 0x6343,                  # row bytes 4..7 -> +52
        0x68A3, 0x6383,                  # row bytes 8..11 -> +56
        0x63C7,                          # template +BA pointer -> +60
    )
    ldr_literal(3, CONSUMER_MAGIC)
    emit(
        0x6003,  # publish magic last
        0xBC0F,  # restore original r0-r3, including table and ID
        0x4770,  # bx lr -> 0x080932CE
        0x46C0,
    )

    return _finish_literals(
        halfwords,
        literal_loads,
        stub_address=CONSUMER_STUB,
        stub_size=CONSUMER_STUB_SIZE,
    )


def build_probe(base: bytes, *, verify_sha1: bool = True) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if verify_sha1 and digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    assert_non_overlapping_sites(CALL_SITES, EVENT_COUNTER, 4, STUB_SIZE)
    consumer_hook_offset = CONSUMER_HOOK - ROM_BASE
    consumer_stub_offset = CONSUMER_STUB - ROM_BASE
    confirm_hook_offset = CONFIRM_HOOK - ROM_BASE
    confirm_stub_offset = CONFIRM_STUB - ROM_BASE
    if base[confirm_hook_offset : confirm_hook_offset + 4] != encode_thumb_bl(
        CONFIRM_HOOK, CONFIRM_ORIGINAL
    ):
        raise ValueError("confirm call-site bytes do not match")
    if any(base[confirm_stub_offset : confirm_stub_offset + CONFIRM_STUB_SIZE]):
        raise ValueError("confirm stub region is not zero-filled")
    if base[consumer_hook_offset : consumer_hook_offset + 4] != CONSUMER_EXPECTED:
        raise ValueError("consumer hook bytes do not match")
    if any(base[consumer_stub_offset : consumer_stub_offset + CONSUMER_STUB_SIZE]):
        raise ValueError("consumer stub region is not zero-filled")
    consumer_ranges = (
        (CONFIRM_SCRATCH, CONFIRM_SCRATCH + CONFIRM_RECORD_SIZE),
        (CONFIRM_STUB, CONFIRM_STUB + CONFIRM_STUB_SIZE),
        (CONSUMER_SCRATCH, CONSUMER_SCRATCH + CONSUMER_RECORD_SIZE),
        (CONSUMER_STUB, CONSUMER_STUB + CONSUMER_STUB_SIZE),
    )
    generic_ranges = [
        (EVENT_COUNTER, EVENT_COUNTER + 4),
        *[(site.scratch, site.scratch + RECORD_SIZE) for site in CALL_SITES],
        *[(site.stub, site.stub + STUB_SIZE) for site in CALL_SITES],
    ]
    for start, end in consumer_ranges:
        if any(start < other_end and other_start < end for other_start, other_end in generic_ranges):
            raise ValueError("consumer observer overlaps a call observer")

    rom = bytearray(base)
    for site in CALL_SITES:
        patch_observer(rom, site, EVENT_COUNTER, STUB_SIZE)
    rom[confirm_hook_offset : confirm_hook_offset + 4] = encode_thumb_bl(
        CONFIRM_HOOK, CONFIRM_STUB
    )
    rom[confirm_stub_offset : confirm_stub_offset + CONFIRM_STUB_SIZE] = (
        build_confirm_stub()
    )
    rom[consumer_hook_offset : consumer_hook_offset + 4] = encode_thumb_bl(
        CONSUMER_HOOK, CONSUMER_STUB
    )
    rom[consumer_stub_offset : consumer_stub_offset + CONSUMER_STUB_SIZE] = (
        build_consumer_stub()
    )
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
