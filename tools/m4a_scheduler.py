#!/usr/bin/env python3
"""MP2K player-tick, SoundMain buffer and six-chunk DMA scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

try:
    from tools.m4a_pcm import reverb_seed
except ModuleNotFoundError:  # direct ``python tools/...`` execution
    from m4a_pcm import reverb_seed

TEMPO_THRESHOLD = 150
BUFFER_FRAMES = 264
PCM_RING_CHUNKS = 6
PCM_RING_FRAMES = BUFFER_FRAMES * PCM_RING_CHUNKS
PCM_RATE = 15768


def tempo_increment(raw_tempo: int, *, tempo_u: int = 0x100) -> int:
    """Reproduce TEMPO's doubled raw value and player tempo scaling."""
    if not 0 <= raw_tempo <= 0xFF or not 0 <= tempo_u <= 0xFFFF:
        raise ValueError("tempo inputs must fit their MP2K fields")
    return ((raw_tempo * 2) * tempo_u) >> 8


def advance_gate(gate_time: int) -> tuple[int, bool]:
    """Advance an existing channel gate at the start of one MP2K track tick."""
    if not 0 <= gate_time <= 0xFF:
        raise ValueError("gate time must fit u8")
    if gate_time == 0:
        return 0, False
    gate_time -= 1
    return gate_time, gate_time == 0


@dataclass
class MPlayClock:
    tempo_i: int
    tempo_c: int = 0

    def advance(self) -> int:
        """Return track ticks executed in one SoundMain invocation."""
        if min(self.tempo_i, self.tempo_c) < 0:
            raise ValueError("player tempo state must be non-negative")
        self.tempo_c += self.tempo_i
        ticks, self.tempo_c = divmod(self.tempo_c, TEMPO_THRESHOLD)
        return ticks


@dataclass(frozen=True)
class SoundMainStep:
    chunk_index: int
    tick_counts: tuple[int, ...]
    output_frames: int = BUFFER_FRAMES


class SoundMainClock:
    """Schedule linked MPlay players before one CGB and DirectSound update."""

    def __init__(self, players: Sequence[MPlayClock]):
        self.players = list(players)
        self.chunk_index = 0

    def advance(
        self,
        *,
        on_tick: Callable[[int, int], None] | None = None,
        on_cgb: Callable[[], None] | None = None,
        on_direct: Callable[[int, int], None] | None = None,
    ) -> SoundMainStep:
        tick_counts = [0] * len(self.players)
        # MPlayMain calls its linked ``next`` player before updating itself.
        for player_index in range(len(self.players) - 1, -1, -1):
            count = self.players[player_index].advance()
            tick_counts[player_index] = count
            if on_tick:
                for tick_index in range(count):
                    on_tick(player_index, tick_index)
        if on_cgb:
            on_cgb()
        current_chunk = self.chunk_index
        if on_direct:
            on_direct(current_chunk, BUFFER_FRAMES)
        self.chunk_index = (self.chunk_index + 1) % PCM_RING_CHUNKS
        return SoundMainStep(current_chunk, tuple(tick_counts))


class PcmRing:
    """Six 264-frame signed planes used by the ROM's DMA and reverb seed."""

    def __init__(self):
        self.right = [0] * PCM_RING_FRAMES
        self.left = [0] * PCM_RING_FRAMES

    def seed_chunk(self, chunk_index: int, *, reverb: int) -> tuple[list[int], list[int]]:
        if not 0 <= chunk_index < PCM_RING_CHUNKS:
            raise ValueError("chunk index must be in the six-slot PCM ring")
        if not 0 <= reverb <= 0xFF:
            raise ValueError("reverb must fit u8")
        current_start = chunk_index * BUFFER_FRAMES
        next_start = ((chunk_index + 1) % PCM_RING_CHUNKS) * BUFFER_FRAMES
        right = []
        left = []
        for index in range(BUFFER_FRAMES):
            seed = reverb_seed(
                self.right[current_start + index],
                self.left[current_start + index],
                self.right[next_start + index],
                self.left[next_start + index],
                reverb,
            )
            right.append(seed)
            left.append(seed)
        self.right[current_start:current_start + BUFFER_FRAMES] = right
        self.left[current_start:current_start + BUFFER_FRAMES] = left
        return right, left
