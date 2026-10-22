#!/usr/bin/env python3
"""Player-level MP2K track scheduling and DirectSound buffer rendering."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from tools.m4a_command_vm import MPlayTrackVM
    from tools.m4a_runtime_channels import M4AChannelRuntime, M4ATrackRunner
    from tools.m4a_scheduler import (
        BUFFER_FRAMES,
        PCM_RING_CHUNKS,
        MPlayClock,
        PcmRing,
        tempo_increment,
    )
    from tools.m4a_track_state import MPlayMusicalState
except ModuleNotFoundError:  # direct ``python tools/...`` execution
    from m4a_command_vm import MPlayTrackVM
    from m4a_runtime_channels import M4AChannelRuntime, M4ATrackRunner
    from m4a_scheduler import (
        BUFFER_FRAMES,
        PCM_RING_CHUNKS,
        MPlayClock,
        PcmRing,
        tempo_increment,
    )
    from m4a_track_state import MPlayMusicalState


@dataclass(frozen=True)
class SongSoundMainStep:
    chunk_index: int
    tick_count: int
    right: tuple[int, ...]
    left: tuple[int, ...]


class M4ASongEngine:
    """Render one dispatched song descriptor as one isolated MPlay player."""

    def __init__(self, rom: bytes, entry: dict, command_map: dict[int, dict]):
        self.rom = rom
        self.entry = entry
        self.channels = M4AChannelRuntime(
            rom,
            voicegroup_offset=entry["voicegroup_ptr"] - 0x08000000,
            player_priority=entry["priority"],
        )
        self.runners = [
            M4ATrackRunner(
                MPlayTrackVM(track_ptr - 0x08000000, command_map),
                MPlayMusicalState(track_ptr=track_ptr),
                self.channels,
            )
            for track_ptr in entry["track_ptrs"]
        ]
        self.clock = MPlayClock(tempo_increment(75))
        self.ring = PcmRing()
        self.chunk_index = 0
        self.invocations = 0
        self.right: list[int] = []
        self.left: list[int] = []

    @classmethod
    def from_bank(
        cls,
        rom: bytes,
        bank: dict,
        decoded: dict,
        *,
        sound_id: int,
    ) -> "M4ASongEngine":
        try:
            entry = next(
                row for row in bank["entries"] if row["sound_id"] == sound_id
            )
        except StopIteration as exc:
            raise ValueError(f"sound ID {sound_id} is not active") from exc
        command_map = {
            command["offset"]: command
            for track in decoded["tracks"]
            for command in track["commands"]
        }
        return cls(rom, entry, command_map)

    @property
    def finished(self) -> bool:
        return (
            all(not runner.vm.running for runner in self.runners)
            and all(channel.status == 0 for channel in self.channels.channels)
        )

    def advance_soundmain(self) -> SongSoundMainStep:
        """Execute all due player ticks, propagate state, then mix one chunk."""
        tick_count = self.clock.advance()
        for _ in range(tick_count):
            for runner in self.runners:
                before = len(runner.tempo_updates)
                runner.step_tick()
                for raw_tempo in runner.tempo_updates[before:]:
                    self.clock.tempo_i = tempo_increment(raw_tempo)

        for runner in self.runners:
            if runner.state.pitch_dirty or runner.state.mix_dirty:
                self.channels.propagate_track(runner.state)

        chunk_index = self.chunk_index
        cgb_right, cgb_left = self.channels.render_cgb_chunk()
        direct_right, direct_left = self.channels.mix_direct_chunk(
            self.ring,
            chunk_index=chunk_index,
            reverb=self.entry["reverb"],
        )
        right = [
            max(-128, min(127, direct + cgb))
            for direct, cgb in zip(direct_right, cgb_right)
        ]
        left = [
            max(-128, min(127, direct + cgb))
            for direct, cgb in zip(direct_left, cgb_left)
        ]
        self.chunk_index = (chunk_index + 1) % PCM_RING_CHUNKS
        self.invocations += 1
        self.right.extend(right)
        self.left.extend(left)
        if len(right) != BUFFER_FRAMES or len(left) != BUFFER_FRAMES:
            raise AssertionError("SoundMain must emit exactly 264 stereo frames")
        return SongSoundMainStep(
            chunk_index=chunk_index,
            tick_count=tick_count,
            right=tuple(right),
            left=tuple(left),
        )

    def render_invocations(self, count: int) -> tuple[list[int], list[int]]:
        if count < 0:
            raise ValueError("invocation count must be non-negative")
        for _ in range(count):
            self.advance_soundmain()
        return self.right, self.left

    def render_until_finished(self, *, max_invocations: int) -> int:
        if max_invocations <= 0:
            raise ValueError("maximum invocation count must be positive")
        start = self.invocations
        while not self.finished and self.invocations - start < max_invocations:
            self.advance_soundmain()
        return self.invocations - start

    def render_until_loop_boundary(
        self,
        looping_track_ptrs: set[int],
        *,
        max_invocations: int,
    ) -> tuple[int, bool]:
        if not looping_track_ptrs:
            raise ValueError("at least one looping track is required")
        if max_invocations <= 0:
            raise ValueError("maximum invocation count must be positive")
        runners = [
            runner for runner in self.runners
            if runner.state.track_ptr in looping_track_ptrs
        ]
        if len(runners) != len(looping_track_ptrs):
            raise ValueError("looping track is not owned by this player")
        start = self.invocations
        reached = False
        while self.invocations - start < max_invocations:
            self.advance_soundmain()
            if all(runner.vm.command_counts["GOTO"] for runner in runners):
                reached = True
                break
        return self.invocations - start, reached
