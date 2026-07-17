#!/usr/bin/env python3
"""Build a transparent two-site MOVEDONE observer with hook-time unit snapshots."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct

try:
    from tools.published_call_observer import ObserverSite
    from tools.thumb_branch import encode_thumb_bl
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from published_call_observer import ObserverSite
    from thumb_branch import encode_thumb_bl


BASE_SHA1 = "26f60795fa5e63b4f0264b84e453beffd56b9f7d"
ROM_BASE = 0x08000000
STUB_SIZE = 128
RECORD_SIZE = 52
CURRENT_OBJECT = 0x0202680C
EVENT_COUNTER = 0x0203F0E0

MOVEDONE_PRIMARY_SITE = ObserverSite(
    "movedone-primary",
    0x0807443C,
    0x080722A8,
    0x0809E800,
    0x0203F100,
    int.from_bytes(b"MOD1", "little"),
    1,
)
MOVEDONE_SECONDARY_SITE = ObserverSite(
    "movedone-secondary",
    0x08074918,
    0x080722A8,
    0x0809E880,
    0x0203F140,
    int.from_bytes(b"MOD2", "little"),
    2,
)
OBSERVER_SITES = (MOVEDONE_PRIMARY_SITE, MOVEDONE_SECONDARY_SITE)


def _validate_layout(base: bytes) -> None:
    ranges = [(EVENT_COUNTER, EVENT_COUNTER + 4, "event counter")]
    for site in OBSERVER_SITES:
        ranges.extend(
            (
                (site.scratch, site.scratch + RECORD_SIZE, f"{site.name} record"),
                (site.stub, site.stub + STUB_SIZE, f"{site.name} stub"),
            )
        )
        hook_offset = site.hook - ROM_BASE
        stub_offset = site.stub - ROM_BASE
        if base[hook_offset : hook_offset + 4] != encode_thumb_bl(site.hook, site.original):
            raise ValueError(f"{site.name} call-site bytes do not match")
        cave = base[stub_offset : stub_offset + STUB_SIZE]
        if len(cave) != STUB_SIZE or any(cave):
            raise ValueError(f"{site.name} stub region is not zero-filled")

    for index, (start, end, name) in enumerate(ranges):
        for other_start, other_end, other_name in ranges[index + 1 :]:
            if start < other_end and other_start < end:
                raise ValueError(f"observer ranges overlap: {name} and {other_name}")


def _build_snapshot_stub(site: ObserverSite) -> bytes:
    halfwords: list[int] = []
    literal_loads: list[tuple[int, int, int]] = []

    def emit(*values: int) -> None:
        halfwords.extend(values)

    def ldr_literal(register: int, value: int) -> None:
        literal_loads.append((len(halfwords), register, value))
        halfwords.append(0)

    def ldr_word(destination: int, base: int, byte_offset: int) -> None:
        emit(0x6800 | ((byte_offset // 4) << 6) | (base << 3) | destination)

    def str_word(source: int, base: int, byte_offset: int) -> None:
        emit(0x6000 | ((byte_offset // 4) << 6) | (base << 3) | source)

    emit(0xB4FF)  # push {r0-r7}; preserve all low registers and SP
    ldr_literal(3, site.scratch)
    ldr_word(0, 3, 0)
    ldr_literal(4, site.magic)
    emit(
        0x42A0,  # cmp r0, r4
        0xD101,  # bne reset_count
    )
    ldr_word(0, 3, 4)
    emit(
        0xE000,  # b have_count
        0x2000,  # reset_count: movs r0, #0
        0x2100,  # have_count: movs r1, #0
    )
    str_word(1, 3, 0)  # invalidate record while publishing
    emit(0x3001)  # adds r0, #1
    str_word(0, 3, 4)

    ldr_literal(1, EVENT_COUNTER)
    ldr_word(0, 1, 0)
    emit(0x3001)
    str_word(0, 1, 0)
    str_word(0, 3, 8)
    ldr_literal(0, site.event_code)
    str_word(0, 3, 12)
    ldr_literal(0, site.hook)
    str_word(0, 3, 16)

    ldr_literal(1, CURRENT_OBJECT)
    ldr_word(0, 1, 0)
    str_word(0, 3, 20)  # current object +0..+3; slot is byte +3
    ldr_word(2, 1, 4)
    str_word(2, 3, 24)  # current object +4 record pointer
    str_word(2, 3, 28)  # resolved record address used below
    ldr_word(0, 2, 0)
    str_word(0, 3, 32)
    emit(0x32C0)  # adds r2, #0xC0
    for source_offset, record_offset in ((0, 36), (4, 40), (8, 44), (12, 48)):
        ldr_word(0, 2, source_offset)
        str_word(0, 3, record_offset)

    ldr_literal(0, site.magic)
    str_word(0, 3, 0)  # publish magic last
    ldr_literal(4, site.original | 1)
    emit(
        0x46A4,  # mov r12, r4
        0xBCFF,  # pop {r0-r7}; restore arguments, registers and SP
        0x4760,  # bx r12; original returns through untouched LR
    )

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
        pc = (site.stub + instruction_offset + 4) & ~3
        target = site.stub + literal_offsets[value]
        distance = target - pc
        if distance < 0 or distance % 4 or distance // 4 > 0xFF:
            raise ValueError(f"{site.name} literal is outside Thumb LDR range")
        code[instruction_offset : instruction_offset + 2] = struct.pack(
            "<H", 0x4800 | (register << 8) | (distance // 4)
        )
    if len(code) > STUB_SIZE:
        raise ValueError(f"{site.name} observer requires {len(code)} bytes")
    code.extend(b"\x00" * (STUB_SIZE - len(code)))
    return bytes(code)


def build_probe(base: bytes, *, verify_sha1: bool = True) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if verify_sha1 and digest != BASE_SHA1:
        raise ValueError(f"action-submit probe requires the immutable base ROM ({BASE_SHA1})")
    _validate_layout(base)
    rom = bytearray(base)
    for site in OBSERVER_SITES:
        hook_offset = site.hook - ROM_BASE
        stub_offset = site.stub - ROM_BASE
        rom[stub_offset : stub_offset + STUB_SIZE] = _build_snapshot_stub(site)
        rom[hook_offset : hook_offset + 4] = encode_thumb_bl(site.hook, site.stub)
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
