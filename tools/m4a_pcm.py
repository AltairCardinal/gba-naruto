#!/usr/bin/env python3
"""ROM-exact forward DirectSound sampling and signed-byte mixing primitives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import wave

PHASE_BITS = 23
PHASE_MASK = (1 << PHASE_BITS) - 1


def _s8(value: int) -> int:
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def linear_sample(sample0: int, sample1: int, phase: int) -> int:
    """Reproduce the signed arithmetic interpolation at 0x0809A10C."""
    if not 0 <= phase <= PHASE_MASK:
        raise ValueError("phase must fit the 23-bit DirectSound fraction")
    return sample0 + ((phase * (sample1 - sample0)) >> PHASE_BITS)


def mix_sample_wrap(existing: int, sample: int, gain: int) -> int:
    """Accumulate one channel contribution with the ROM's byte wrap behavior."""
    contribution = (sample * gain) >> 8
    return _s8(existing + contribution)


def reverb_seed(
    current_right: int,
    current_left: int,
    previous_right: int,
    previous_left: int,
    reverb: int,
) -> int:
    """Build the mono DirectSound buffer seed used at 0x08099E2C..0x08099E5C."""
    value = (
        (current_right + current_left + previous_right + previous_left) * reverb
    ) >> 9
    if value & 0x80:
        value += 1
    return _s8(value)


@dataclass
class DirectSoundState:
    sample_index: int
    remaining: int
    phase: int = 0
    active: bool = True


def render_forward(
    data_with_guard: bytes,
    state: DirectSoundState,
    *,
    step: int,
    div_freq: int,
    frames: int,
    sample_count: int | None = None,
    loop_start: int | None = None,
) -> list[int]:
    """Render the type-0 forward-linear path at 0x0809A080..0x0809A180.

    ``data_with_guard`` must preserve the ROM byte after the declared sample data,
    because the mixer pre-reads it for interpolation at the final sample.
    """
    if min(step, div_freq, frames, state.sample_index, state.remaining) < 0:
        raise ValueError("DirectSound state and render inputs must be non-negative")
    if loop_start is not None:
        if sample_count is None or not 0 <= loop_start < sample_count:
            raise ValueError("looping requires a valid sample_count and loop_start")
    increment = (step * div_freq) & 0xFFFFFFFF
    output: list[int] = []
    for _ in range(frames):
        if not state.active:
            break
        if state.sample_index + 1 >= len(data_with_guard):
            raise ValueError("DirectSound sample is missing its ROM guard byte")
        sample0 = _s8(data_with_guard[state.sample_index])
        sample1 = _s8(data_with_guard[state.sample_index + 1])
        output.append(linear_sample(sample0, sample1, state.phase))

        total = (state.phase + increment) & 0xFFFFFFFF
        advance = total >> PHASE_BITS
        state.phase = total & PHASE_MASK
        if not advance:
            continue

        state.remaining -= advance
        if state.remaining > 0:
            state.sample_index += advance
            continue
        if loop_start is None:
            state.active = False
            continue

        loop_length = sample_count - loop_start
        overshoot = -state.remaining
        state.remaining = loop_length - (overshoot % loop_length)
        if state.remaining == loop_length and overshoot:
            state.remaining = loop_length
        state.sample_index = loop_start + (overshoot % loop_length)
    return output


def interleave_wav_u8(right: list[int], left: list[int]) -> bytes:
    """Convert signed right/left planes to interleaved RIFF unsigned 8-bit PCM."""
    if len(right) != len(left):
        raise ValueError("stereo planes must have equal lengths")
    output = bytearray()
    for right_sample, left_sample in zip(right, left):
        output.extend(((right_sample & 0xFF) ^ 0x80, (left_sample & 0xFF) ^ 0x80))
    return bytes(output)


def write_stereo_wave(
    path: Path, right: list[int], left: list[int], *, sample_rate: int
) -> None:
    """Write the ROM's signed right/left planes as stereo RIFF 8-bit PCM."""
    if sample_rate <= 0:
        raise ValueError("sample rate must be positive")
    frames = interleave_wav_u8(right, left)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(1)
        output.setframerate(sample_rate)
        output.writeframes(frames)
