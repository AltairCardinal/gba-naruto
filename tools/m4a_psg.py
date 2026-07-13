#!/usr/bin/env python3
"""CGB channel-4/noise primitives used by this ROM's MP2K engine."""

from __future__ import annotations

NOISE_TABLE_OFFSET = 0x46475C
NOISE_TABLE_SIZE = 60


def noise_register(rom: bytes, key: int) -> int:
    """Reproduce MidiKeyToCgbFreq's channel-4 lookup at 0x0809B494."""
    if key <= 20:
        index = 0
    else:
        index = min(key - 21, NOISE_TABLE_SIZE - 1)
    return rom[NOISE_TABLE_OFFSET + index]


def noise_clock_hz(register: int) -> float | int:
    """Decode GBA NR43 into the LFSR clock frequency."""
    shift = (register >> 4) & 0xF
    divisor_code = register & 7
    divisor = divisor_code if divisor_code else 0.5
    value = 262144 / (divisor * (1 << shift))
    return int(value) if value.is_integer() else value


def noise_lfsr_step(lfsr: int, *, width7: bool) -> int:
    """Advance the channel-4 15-bit LFSR once, optionally mirroring into bit 6."""
    feedback = (lfsr & 1) ^ ((lfsr >> 1) & 1)
    result = (lfsr >> 1) | (feedback << 14)
    if width7:
        result = (result & ~(1 << 6)) | (feedback << 6)
    return result & 0x7FFF


def cgb_volume(
    right: int,
    left: int,
    *,
    sustain: int,
    pan_mask: int = 0x88,
    mode: int = 0,
) -> tuple[int, int, int]:
    """Reproduce CgbModVol at 0x0809B58C for one hardware channel."""
    if right >= left and right // 2 >= left:
        pan = 0x0F
        separated = True
    elif left > right and left // 2 >= right:
        pan = 0xF0
        separated = True
    else:
        pan = 0xFF
        separated = False

    goal = (right + left) // 16
    if not (mode & 1) and separated:
        goal = min(15, goal)
    sustain_goal = (goal * sustain + 15) >> 4
    return goal, sustain_goal, pan & pan_mask


def noise_start_registers(
    rom: bytes,
    *,
    key: int,
    length: int,
    pointer: int,
    attack: int,
    sustain: int,
    track_right: int,
    track_left: int,
    velocity: int,
) -> dict[str, int]:
    """Return the channel-4 register vector produced at note start."""
    try:
        from tools.map_m4a_instruments import _channel_mix_coefficients
    except ModuleNotFoundError:  # direct ``python tools/...`` execution
        from map_m4a_instruments import _channel_mix_coefficients

    right, left = _channel_mix_coefficients(
        track_right, track_left, velocity=velocity, tone_pan=0
    )
    goal, sustain_goal, pan = cgb_volume(right, left, sustain=sustain)
    # attack=0 skips directly through decay=0 to sustain for this ROM's tone.
    envelope_volume = sustain_goal if attack == 0 else 0
    frequency = noise_register(rom, key)
    nr43 = ((pointer << 3) & 0x08) | frequency
    return {
        "NR41": length & 0xFF,
        "NR42": ((envelope_volume & 0xF) << 4) | 0x08,
        "NR43": nr43 & 0xFF,
        "NR44": (0x40 if length else 0x00) | 0x80,
        "NR51": pan,
    }


def noise_stop_registers() -> dict[str, int]:
    """Return channel-4 writes for this ROM's release=0 terminal tone."""
    return {"NR42": 0x08, "NR44": 0x80}
