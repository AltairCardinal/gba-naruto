"""Prove a bounded straight-line r0 argument reaches a display bridge.

Callers must independently validate the source CFG and instruction ownership.
This helper proves local raw encoding effects only; it neither verifies a CFG
entry nor establishes natural runtime reachability or a complete caller domain.
"""
from __future__ import annotations

import hashlib

from tools.verify_rom_fixed_consumer_text_inventory import _half, _thumb_call

DISPLAY_BRIDGES = frozenset((0x66758, 0x667A0))
MAX_PATH_BYTES = 16


def _destination(half: int) -> int | None:
    """Return the written register for the supported ARMv4T Thumb subset."""
    group = half & 0xF800
    if group in (0x2000, 0x3000, 0x4800, 0x9800):
        return (half >> 8) & 7  # MOV/ADD immediate, PC literal, SP load.
    if group == 0x1800:
        return half & 7  # ADD/SUB register or immediate-3.
    if group == 0x9000:
        return None  # SP-relative STR: reads a register, writes memory.
    if half & 0xFF00 == 0x4600:
        destination = (half & 7) | ((half >> 4) & 8)
        if destination < 13:
            return destination  # High-register MOV; no SP/LR/PC writes.
    raise ValueError(f"unsupported or control encoding: 0x{half:04x}")


def prove_parameter_flow(rom: bytes, *, site: int, sink: int, target: int,
                         owner_range: list[int] | tuple[int, int]) -> dict:
    """Reject every unknown effect, r0 overwrite, boundary or sink mismatch."""
    if (not isinstance(rom, bytes)
            or any(type(value) is not int for value in (site, sink, target))
            or not isinstance(owner_range, (list, tuple)) or len(owner_range) != 2
            or any(type(value) is not int for value in owner_range)):
        raise ValueError("invalid integer or byte contract")
    start, end = owner_range
    if (not 0 <= start <= site < sink or not sink + 4 <= end <= len(rom)
            or (start | end | site | sink) & 1
            or sink + 4 - site > MAX_PATH_BYTES or not 0 <= target < len(rom)):
        raise ValueError("invalid path bounds or alignment")
    half = _half(rom, site)
    if half & 0xFF00 != 0x4800:
        raise ValueError("initial literal must load r0")
    literal = ((site + 4) & ~3) + (half & 255) * 4
    if literal + 4 > len(rom):
        raise ValueError("literal target is outside ROM")
    if int.from_bytes(rom[literal:literal + 4], 'little') != 0x08000000 + target:
        raise ValueError("literal target changed")
    for at in range(site + 2, sink, 2):
        half = _half(rom, at)
        if _destination(half) == 0:
            raise ValueError(f"r0 overwritten at 0x{at:06x}")
    first = _half(rom, sink)
    second = _half(rom, sink + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError("sink must be an ARMv4T Thumb BL pair")
    callee = _thumb_call(rom, sink)
    if callee not in DISPLAY_BRIDGES:
        raise ValueError("display callee changed")
    return {'site': site, 'sink': sink, 'literal_word': literal, 'target': target,
            'callee': callee, 'instruction_count': (sink - site) // 2 + 1,
            'path_sha256': hashlib.sha256(rom[site:sink + 4]).hexdigest(),
            'source_cfg_verified': False, 'natural_runtime_reachability': False}
