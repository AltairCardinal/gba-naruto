#!/usr/bin/env python3
"""Exact ROM-table DirectSound pitch-step and mixer phase helpers."""
from __future__ import annotations

import struct


SCALE_TABLE = 0x4645C4
SCALE_COUNT = 180
FREQUENCY_TABLE = 0x464678
FREQUENCY_COUNT = 12
MAX_KEY = 178
PHASE_BITS = 23
PHASE_MASK = (1 << PHASE_BITS) - 1


def high32_unsigned(left: int, right: int) -> int:
    if not 0 <= left <= 0xFFFFFFFF or not 0 <= right <= 0xFFFFFFFF:
        raise ValueError("high32 operands must fit u32")
    return ((left * right) >> 32) & 0xFFFFFFFF


def _base_pitch(rom: bytes, key: int) -> int:
    descriptor = rom[SCALE_TABLE + key]
    frequency_index = descriptor & 0x0F
    shift = descriptor >> 4
    if frequency_index >= FREQUENCY_COUNT:
        raise ValueError(f"pitch frequency index {frequency_index} is invalid")
    frequency = struct.unpack_from(
        "<I", rom, FREQUENCY_TABLE + frequency_index * 4
    )[0]
    return frequency >> shift


def midi_key_to_step(
    rom: bytes, wave_frequency_raw: int, *, key: int, fine: int = 0
) -> int:
    """Reproduce 0x0809A998 using ROM scale/frequency tables and UMULL high32."""
    if len(rom) < FREQUENCY_TABLE + FREQUENCY_COUNT * 4:
        raise ValueError("ROM is too small for MP2K pitch tables")
    if not 0 <= wave_frequency_raw <= 0xFFFFFFFF:
        raise ValueError("wave frequency must fit u32")
    if not 0 <= key <= 0xFF or not 0 <= fine <= 0xFF:
        raise ValueError("key and fine must fit u8")
    if key > MAX_KEY:
        key = MAX_KEY
        fine = 0xFF
    pitch0 = _base_pitch(rom, key)
    pitch1 = _base_pitch(rom, key + 1)
    delta = (pitch1 - pitch0) & 0xFFFFFFFF
    interpolated = (pitch0 + high32_unsigned(delta, fine << 24)) & 0xFFFFFFFF
    return high32_unsigned(wave_frequency_raw, interpolated)


def mixer_advance(*, phase: int, step: int, div_freq: int) -> tuple[int, int]:
    """Advance the 23-bit SoundMainRAM DirectSound source phase once."""
    if min(phase, step, div_freq) < 0:
        raise ValueError("mixer inputs must be non-negative")
    total = phase + step * div_freq
    return total & PHASE_MASK, total >> PHASE_BITS
