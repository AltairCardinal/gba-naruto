from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class ThumbBranch:
    address: int
    target: int
    mnemonic: str
    op_str: str


def encode_thumb_bl(callsite: int, target: int) -> bytes:
    displacement = target - (callsite + 4)
    if displacement & 1:
        raise ValueError("Thumb BL target must be halfword aligned")
    if not -(1 << 22) <= displacement < (1 << 22):
        raise ValueError("Thumb BL target is outside ARMv4T range")
    encoded = displacement & 0x7FFFFF
    return struct.pack(
        "<HH",
        0xF000 | ((encoded >> 12) & 0x7FF),
        0xF800 | ((encoded >> 1) & 0x7FF),
    )


def decode_thumb_bl(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def decode_thumb_b(callsite: int, halfword: int) -> int | None:
    if halfword & 0xF800 != 0xE000:
        return None
    displacement = (halfword & 0x7FF) << 1
    if displacement & 0x800:
        displacement -= 0x1000
    return callsite + 4 + displacement


def _validated_offsets(data: bytes, rom_base: int, start: int | None, end: int | None) -> tuple[int, int]:
    mapped_end = rom_base + len(data)
    start = rom_base if start is None else start
    end = mapped_end if end is None else end
    if start > end:
        raise ValueError("start must not exceed end")
    if start < rom_base or end > mapped_end:
        raise ValueError("start/end must be inside the mapped ROM range")
    if (start | end | rom_base) & 1:
        raise ValueError("ROM base and scan bounds must be halfword aligned")
    return start - rom_base, end - rom_base


def iter_thumb_direct_branches(
    data: bytes,
    *,
    rom_base: int,
    start: int | None = None,
    end: int | None = None,
) -> Iterator[ThumbBranch]:
    start_offset, end_offset = _validated_offsets(data, rom_base, start, end)
    for offset in range(start_offset, end_offset, 2):
        address = rom_base + offset
        halfword = struct.unpack_from("<H", data, offset)[0]
        if offset + 4 <= end_offset:
            second = struct.unpack_from("<H", data, offset + 2)[0]
            target = decode_thumb_bl(address, halfword, second)
            if target is not None:
                yield ThumbBranch(address, target, "bl", f"#0x{target:08x}")
                continue
        target = decode_thumb_b(address, halfword)
        if target is not None:
            yield ThumbBranch(address, target, "b", f"#0x{target:08x}")


def find_thumb_branches(
    data: bytes,
    target: int,
    *,
    rom_base: int,
    start: int | None = None,
    end: int | None = None,
) -> list[ThumbBranch]:
    return [
        branch
        for branch in iter_thumb_direct_branches(data, rom_base=rom_base, start=start, end=end)
        if branch.target == target
    ]
