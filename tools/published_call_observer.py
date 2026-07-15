"""Reusable transparent Thumb observer for publishing checked call arguments."""
from __future__ import annotations

from dataclasses import dataclass
import struct

try:
    from tools.thumb_branch import encode_thumb_bl
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from thumb_branch import encode_thumb_bl


ROM_BASE = 0x08000000
RECORD_SIZE = 24
EWRAM_START = 0x02000000
EWRAM_END = 0x02040000
ROM_END = 0x0A000000


@dataclass(frozen=True)
class ObserverSite:
    name: str
    hook: int
    original: int
    stub: int
    scratch: int
    magic: int
    event_code: int


def assert_non_overlapping_sites(
    sites: list[ObserverSite] | tuple[ObserverSite, ...],
    event_counter: int,
    event_counter_size: int,
    stub_size: int = 96,
) -> None:
    """Reject overlapping or out-of-range observer records and ROM stubs."""
    if event_counter_size <= 0 or stub_size <= 0:
        raise ValueError("observer range sizes must be positive")
    if event_counter % 4 or not EWRAM_START <= event_counter < EWRAM_END:
        raise ValueError("event counter must be aligned EWRAM")
    ranges = [(event_counter, event_counter + event_counter_size, "event counter")]
    if ranges[0][1] > EWRAM_END:
        raise ValueError("event counter must fit EWRAM")

    for site in sites:
        if site.scratch % 4 or not EWRAM_START <= site.scratch:
            raise ValueError(f"{site.name} record must be aligned EWRAM")
        if site.scratch + RECORD_SIZE > EWRAM_END:
            raise ValueError(f"{site.name} record must fit EWRAM")
        if site.stub % 4 or not ROM_BASE <= site.stub:
            raise ValueError(f"{site.name} stub must be aligned ROM")
        if site.stub + stub_size > ROM_END:
            raise ValueError(f"{site.name} stub must fit ROM")
        ranges.extend(
            (
                (site.scratch, site.scratch + RECORD_SIZE, f"{site.name} record"),
                (site.stub, site.stub + stub_size, f"{site.name} stub"),
            )
        )

    for index, (start, end, name) in enumerate(ranges):
        for other_start, other_end, other_name in ranges[index + 1:]:
            if start < other_end and other_start < end:
                raise ValueError(f"observer ranges overlap: {name} and {other_name}")


def build_observer_stub(site: ObserverSite, event_counter: int, stub_size: int) -> bytes:
    """Build a no-nested-call wrapper that publishes its record magic last."""
    halfwords: list[int] = []
    literal_loads: list[tuple[int, int, int]] = []

    def emit(*values: int) -> None:
        halfwords.extend(values)

    def ldr_literal(register: int, value: int) -> None:
        literal_loads.append((len(halfwords), register, value))
        halfwords.append(0)

    emit(0xB41F)  # push {r0-r4}; LR remains the hook continuation
    ldr_literal(3, site.scratch)
    emit(0x6818)  # ldr r0, [r3]
    ldr_literal(4, site.magic)
    emit(
        0x42A0,  # cmp r0, r4
        0xD101,  # bne reset_count
        0x6858,  # ldr r0, [r3, #4]
        0xE000,  # b have_count
        0x2000,  # reset_count: movs r0, #0
        0x2100,  # have_count: movs r1, #0
        0x6019,  # str r1, [r3]; invalidate the published record
        0x3001,  # adds r0, #1
        0x6058,  # str r0, [r3, #4]; hit_count
        0x9800,  # ldr r0, [sp]; saved arg0
        0x6098,  # str r0, [r3, #8]
        0x9801,  # ldr r0, [sp, #4]; saved arg1
        0x8198,  # strh r0, [r3, #12]
        0x9802,  # ldr r0, [sp, #8]; saved arg2
        0x81D8,  # strh r0, [r3, #14]
    )
    ldr_literal(1, event_counter)
    emit(
        0x6808,  # ldr r0, [r1]
        0x3001,  # adds r0, #1
        0x6008,  # str r0, [r1]; shared event counter
        0x6118,  # str r0, [r3, #16]; fresh sequence
    )
    ldr_literal(0, site.event_code)
    emit(0x6158)  # str r0, [r3, #20]; event code
    ldr_literal(0, site.magic)
    emit(0x6018)  # str r0, [r3]; publish magic last
    ldr_literal(4, site.original | 1)
    emit(
        0x46A4,  # mov r12, r4
        0xBC1F,  # pop {r0-r4}; restore registers and SP
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
        instruction = 0x4800 | (register << 8) | (distance // 4)
        code[instruction_offset:instruction_offset + 2] = struct.pack("<H", instruction)

    if len(code) > stub_size:
        raise ValueError(
            f"{site.name} observer requires {len(code)} bytes, exceeds stub_size {stub_size}"
        )
    code.extend(b"\x00" * (stub_size - len(code)))
    return bytes(code)


def patch_observer(
    rom: bytearray,
    site: ObserverSite,
    event_counter: int,
    stub_size: int,
) -> None:
    """Install one observer only when its BL and zero-filled cave match."""
    hook_offset = site.hook - ROM_BASE
    stub_offset = site.stub - ROM_BASE
    expected = encode_thumb_bl(site.hook, site.original)
    if rom[hook_offset:hook_offset + 4] != expected:
        raise ValueError(f"{site.name} call-site bytes do not match")
    if len(rom[stub_offset:stub_offset + stub_size]) != stub_size or any(
        rom[stub_offset:stub_offset + stub_size]
    ):
        raise ValueError(f"{site.name} stub region is not zero-filled")
    stub = build_observer_stub(site, event_counter, stub_size)
    rom[stub_offset:stub_offset + stub_size] = stub
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(site.hook, site.stub)
