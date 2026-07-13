#!/usr/bin/env python3
"""Wire runtime NoteRequest objects through terminal tones into MP2K channels."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from tools.m4a_channels import (
        ACTIVE_MASK,
        CGB_CHANNEL_COUNT,
        DIRECT_CHANNEL_COUNT,
        Channel,
        TrackChannels,
        cgb_can_allocate,
        clear_chain,
        direct_channel_index,
        effective_priority,
        link_head,
        release_first_key,
    )
    from tools.m4a_command_vm import MPlayTrackVM
    from tools.m4a_track_state import MPlayMusicalState, NoteRequest
    from tools.map_m4a_instruments import resolve_tone
    from tools.extract_audio_assets import parse_wave
    from tools.m4a_envelope import EnvelopeState
    from tools.m4a_pitch_step import midi_key_to_step
    from tools.m4a_psg import noise_register, noise_start_registers
    from tools.map_m4a_instruments import _channel_mix_coefficients
    from tools.m4a_envelope import advance_envelope, mixer_gains
    from tools.m4a_pcm import DirectSoundState, mix_sample_wrap, render_forward
    from tools.m4a_scheduler import BUFFER_FRAMES, PcmRing
except ModuleNotFoundError:  # direct ``python tools/...`` execution
    from m4a_channels import (
        ACTIVE_MASK,
        CGB_CHANNEL_COUNT,
        DIRECT_CHANNEL_COUNT,
        Channel,
        TrackChannels,
        cgb_can_allocate,
        clear_chain,
        direct_channel_index,
        effective_priority,
        link_head,
        release_first_key,
    )
    from m4a_command_vm import MPlayTrackVM
    from m4a_track_state import MPlayMusicalState, NoteRequest
    from map_m4a_instruments import resolve_tone
    from extract_audio_assets import parse_wave
    from m4a_envelope import EnvelopeState
    from m4a_pitch_step import midi_key_to_step
    from m4a_psg import noise_register, noise_start_registers
    from map_m4a_instruments import _channel_mix_coefficients
    from m4a_envelope import advance_envelope, mixer_gains
    from m4a_pcm import DirectSoundState, mix_sample_wrap, render_forward
    from m4a_scheduler import BUFFER_FRAMES, PcmRing


@dataclass(frozen=True)
class AllocationResult:
    kind: str
    channel_index: int
    tone_type: int
    tone_offset: int
    effective_priority: int


class M4AChannelRuntime:
    """One player's voicegroup, track chains and shared 10+4 channel pool."""

    def __init__(
        self,
        rom: bytes,
        *,
        voicegroup_offset: int,
        player_priority: int,
    ):
        self.rom = rom
        self.voicegroup_offset = voicegroup_offset
        self.player_priority = player_priority
        self.channels = [
            Channel() for _ in range(DIRECT_CHANNEL_COUNT + CGB_CHANNEL_COUNT)
        ]
        self.direct = self.channels[:DIRECT_CHANNEL_COUNT]
        self.cgb = self.channels[DIRECT_CHANNEL_COUNT:]
        self.tracks: dict[int, TrackChannels] = {}

    def _track(self, track_ptr: int) -> TrackChannels:
        return self.tracks.setdefault(
            track_ptr, TrackChannels(track_ptr=track_ptr)
        )

    def _unlink_old(self, global_index: int) -> None:
        channel = self.channels[global_index]
        if channel.track_ptr:
            old_track = self.tracks.get(channel.track_ptr)
            if old_track is not None:
                clear_chain(self.channels, old_track, global_index)

    def allocate(
        self, request: NoteRequest, *, track_priority: int
    ) -> AllocationResult | None:
        resolved = resolve_tone(
            self.rom,
            self.voicegroup_offset,
            request.voice,
            request.key,
        )
        terminal = resolved["terminal"]
        priority = effective_priority(self.player_priority, track_priority)
        if terminal["type"] == 0:
            local_index = direct_channel_index(
                self.direct, priority, request.track_ptr
            )
            if local_index is None:
                return None
            global_index = local_index
            kind = "direct"
        else:
            local_index = (terminal["type"] & 7) - 1
            if not 0 <= local_index < CGB_CHANNEL_COUNT:
                raise ValueError(
                    f"unsupported CGB tone type 0x{terminal['type']:02X}"
                )
            channel = self.cgb[local_index]
            if not cgb_can_allocate(channel, priority, request.track_ptr):
                return None
            global_index = DIRECT_CHANNEL_COUNT + local_index
            kind = "cgb"

        self._unlink_old(global_index)
        track = self._track(request.track_ptr)
        link_head(self.channels, track, global_index)
        channel = self.channels[global_index]
        channel.status = 0x80
        channel.priority = priority
        channel.midi_key = request.key
        channel.gate_time = request.gate_time
        channel.tone_offset = terminal["offset"]
        channel.tone_type = terminal["type"]
        channel.pitch_key = (
            max(0, terminal["key"] + request.pitch_key_delta)
            if resolved["drum"]
            else request.pitch_key
        )
        channel.pitch_base_key = terminal["key"] if resolved["drum"] else request.key
        channel.pitch_fine = request.pitch_fine
        channel.track_right = request.track_right
        channel.track_left = request.track_left
        channel.velocity = request.velocity
        channel.adsr = (
            terminal["attack"], terminal["decay"],
            terminal["sustain"], terminal["release"],
        )
        channel.registers = {}
        channel.wave_offset = 0
        channel.sample_count = 0
        channel.loop_start = 0
        channel.step = 0
        channel.envelope = None
        channel.data_offset = 0
        channel.sample_index = 0
        channel.remaining = 0
        channel.phase = 0
        tone_pan = (
            (terminal["pan_sweep"] - 0xC0) << 1
            if resolved["drum"] and terminal["pan_sweep"] & 0x80
            else 0
        )
        channel.tone_pan = tone_pan
        channel.pre_right, channel.pre_left = _channel_mix_coefficients(
            request.track_right,
            request.track_left,
            velocity=request.velocity,
            tone_pan=tone_pan,
        )
        channel.echo_length = 0
        channel.echo_volume = 0
        if kind == "direct":
            wave_offset = terminal["pointer"] - 0x08000000
            wave = parse_wave(self.rom, wave_offset)
            if wave is None:
                raise ValueError(
                    f"DirectSound tone 0x{terminal['offset']:X} has invalid wave"
                )
            channel.wave_offset = wave_offset
            channel.wave_frequency_raw = wave["frequency_raw"]
            channel.data_offset = wave["data_offset"]
            channel.sample_count = wave["sample_count"]
            channel.loop_start = wave["loop_start"]
            channel.remaining = wave["sample_count"]
            channel.step = midi_key_to_step(
                self.rom,
                wave["frequency_raw"],
                key=channel.pitch_key,
                fine=channel.pitch_fine,
            )
            channel.envelope = EnvelopeState.new(
                looped_sample=bool(wave["status"] & 0x4000)
            )
            channel.envelope.echo_remaining = channel.echo_length
        elif (terminal["type"] & 7) == 4:
            channel.echo_length = terminal["length"]
            channel.echo_volume = (
                8
                if terminal["pan_sweep"] & 0xF0
                else terminal["pan_sweep"]
            )
            channel.registers = noise_start_registers(
                self.rom,
                key=channel.pitch_key,
                length=terminal["length"],
                pointer=terminal["pointer"],
                attack=terminal["attack"],
                sustain=terminal["sustain"],
                track_right=request.track_right,
                track_left=request.track_left,
                velocity=request.velocity,
            )
        return AllocationResult(
            kind=kind,
            channel_index=local_index,
            tone_type=terminal["type"],
            tone_offset=terminal["offset"],
            effective_priority=priority,
        )

    def propagate_track(self, state: MPlayMusicalState) -> list[int]:
        """Apply pending TrkVolPitSet state to every linked active channel."""
        track = self.tracks.get(state.track_ptr)
        updated: list[int] = []
        if track is None:
            state.clear_dirty()
            return updated
        pitch_delta, pitch_fine = state.pitch_offset()
        track_right, track_left = state.mix_coefficients()
        index = track.head
        while index is not None:
            channel = self.channels[index]
            if channel.status & ACTIVE_MASK:
                if state.pitch_dirty:
                    channel.pitch_key = max(0, channel.pitch_base_key + pitch_delta)
                    channel.pitch_fine = pitch_fine
                    if channel.tone_type == 0:
                        channel.step = midi_key_to_step(
                            self.rom,
                            channel.wave_frequency_raw,
                            key=channel.pitch_key,
                            fine=channel.pitch_fine,
                        )
                    elif (channel.tone_type & 7) == 4:
                        channel.registers["NR43"] = (
                            (channel.registers.get("NR43", 0) & 0x08)
                            | noise_register(self.rom, channel.pitch_key)
                        )
                if state.mix_dirty:
                    channel.track_right = track_right
                    channel.track_left = track_left
                    channel.pre_right, channel.pre_left = _channel_mix_coefficients(
                        track_right,
                        track_left,
                        velocity=channel.velocity,
                        tone_pan=channel.tone_pan,
                    )
                updated.append(index)
            index = channel.next
        state.clear_dirty()
        return updated

    def release_key(self, track_ptr: int, midi_key: int) -> int | None:
        track = self.tracks.get(track_ptr)
        if track is None:
            return None
        global_index = release_first_key(self.channels, track, midi_key)
        if global_index is None:
            return None
        return (
            global_index
            if global_index < DIRECT_CHANNEL_COUNT
            else global_index - DIRECT_CHANNEL_COUNT
        )

    def scan_gates(self, track_ptr: int) -> list[int]:
        track = self.tracks.get(track_ptr)
        if track is None:
            return []
        released = []
        index = track.head
        while index is not None:
            channel = self.channels[index]
            next_index = channel.next
            if (channel.status & ACTIVE_MASK) == 0:
                clear_chain(self.channels, track, index)
                index = next_index
                continue
            if channel.gate_time:
                channel.gate_time -= 1
                if channel.gate_time == 0:
                    channel.status |= 0x40
                    released.append(index)
            index = next_index
        return released

    def stop_track(self, track_ptr: int) -> list[int]:
        track = self.tracks.get(track_ptr)
        if track is None:
            return []
        stopped = []
        index = track.head
        while index is not None:
            channel = self.channels[index]
            next_index = channel.next
            channel.status |= 0x40
            stopped.append(index)
            clear_chain(self.channels, track, index)
            index = next_index
        return stopped

    def mix_direct_chunk(
        self,
        ring: PcmRing,
        *,
        chunk_index: int,
        reverb: int,
        master_volume: int = 15,
        div_freq: int = 532,
    ) -> tuple[list[int], list[int]]:
        """Advance ADSR once and mix all active DirectSound slots for 264 frames."""
        right, left = ring.seed_chunk(chunk_index, reverb=reverb)
        for channel in self.direct:
            envelope = channel.envelope
            if channel.status == 0 or envelope is None:
                continue
            if channel.status & 0x40:
                envelope.status |= 0x40
            active = advance_envelope(
                envelope,
                attack=channel.adsr[0],
                decay=channel.adsr[1],
                sustain=channel.adsr[2],
                release=channel.adsr[3],
                pseudo_echo_volume=channel.echo_volume,
            )
            if not active:
                channel.status = 0
                continue
            gain_right, gain_left = mixer_gains(
                channel.pre_right,
                channel.pre_left,
                level=envelope.level,
                master_volume=master_volume,
            )
            sample_end = channel.data_offset + channel.sample_count
            source = self.rom[channel.data_offset:sample_end + 1]
            sample_state = DirectSoundState(
                sample_index=channel.sample_index,
                remaining=channel.remaining,
                phase=channel.phase,
            )
            samples = render_forward(
                source,
                sample_state,
                step=channel.step,
                div_freq=div_freq,
                frames=BUFFER_FRAMES,
                sample_count=channel.sample_count,
                loop_start=(
                    channel.loop_start
                    if envelope.status & 0x10
                    else None
                ),
            )
            channel.sample_index = sample_state.sample_index
            channel.remaining = sample_state.remaining
            channel.phase = sample_state.phase
            if not sample_state.active:
                channel.status = 0
            for frame, sample in enumerate(samples):
                right[frame] = mix_sample_wrap(right[frame], sample, gain_right)
                left[frame] = mix_sample_wrap(left[frame], sample, gain_left)

        start = chunk_index * BUFFER_FRAMES
        ring.right[start:start + BUFFER_FRAMES] = right
        ring.left[start:start + BUFFER_FRAMES] = left
        return right, left


class M4ATrackRunner:
    """Connect one persistent command VM and register state to channel requests."""

    def __init__(
        self,
        vm: MPlayTrackVM,
        state: MPlayMusicalState,
        channels: M4AChannelRuntime,
    ):
        self.vm = vm
        self.state = state
        self.channels = channels
        self.allocations: list[AllocationResult] = []
        self.dropped_notes = 0
        self.gate_releases: list[int] = []
        self.eot_releases: list[int] = []
        self.stop_releases: list[int] = []

    def _command(self, command: dict) -> None:
        note_count = len(self.state.note_requests)
        release_count = len(self.state.release_keys)
        stop_before = self.state.stop_requested
        self.state.handle_command(command, tick=self.vm.tick)
        for request in self.state.note_requests[note_count:]:
            result = self.channels.allocate(
                request, track_priority=self.state.priority
            )
            if result is None:
                self.dropped_notes += 1
            else:
                self.allocations.append(result)
        for key in self.state.release_keys[release_count:]:
            released = self.channels.release_key(self.state.track_ptr, key)
            if released is not None:
                self.eot_releases.append(released)
        if not stop_before and self.state.stop_requested:
            self.stop_releases.extend(
                self.channels.stop_track(self.state.track_ptr)
            )

    def step_tick(self) -> None:
        if not self.vm.running:
            return
        self.vm.step_tick(
            on_gate_scan=lambda: self.gate_releases.extend(
                self.channels.scan_gates(self.state.track_ptr)
            ),
            on_command=self._command,
            on_lfo=lambda: self.state.advance_lfo(tick=self.vm.tick),
        )


def simulate_bounded_bank(
    rom: bytes,
    bank: dict,
    decoded: dict,
    *,
    ticks: int,
) -> dict:
    """Exercise every song's shared channel pool for a bounded track-tick run."""
    if ticks <= 0:
        raise ValueError("bounded simulation ticks must be positive")
    command_map = {
        command["offset"]: command
        for track in decoded["tracks"]
        for command in track["commands"]
    }
    totals = {
        "note_request_count": 0,
        "direct_allocation_count": 0,
        "cgb_allocation_count": 0,
        "dropped_note_count": 0,
        "gate_release_count": 0,
        "matched_eot_count": 0,
        "fine_unlinked_channel_count": 0,
    }
    songs = []
    for entry in bank["entries"]:
        channels = M4AChannelRuntime(
            rom,
            voicegroup_offset=entry["voicegroup_ptr"] - 0x08000000,
            player_priority=entry["priority"],
        )
        runners = []
        for track_ptr in entry["track_ptrs"]:
            runners.append(M4ATrackRunner(
                MPlayTrackVM(track_ptr - 0x08000000, command_map),
                MPlayMusicalState(track_ptr=track_ptr),
                channels,
            ))
        for _ in range(ticks):
            for runner in runners:
                runner.step_tick()
        allocations = [
            allocation for runner in runners for allocation in runner.allocations
        ]
        direct = sum(result.kind == "direct" for result in allocations)
        cgb = sum(result.kind == "cgb" for result in allocations)
        dropped = sum(runner.dropped_notes for runner in runners)
        gate_releases = sum(len(runner.gate_releases) for runner in runners)
        eot_releases = sum(len(runner.eot_releases) for runner in runners)
        stop_releases = sum(len(runner.stop_releases) for runner in runners)
        totals["direct_allocation_count"] += direct
        totals["cgb_allocation_count"] += cgb
        totals["dropped_note_count"] += dropped
        totals["note_request_count"] += direct + cgb + dropped
        totals["gate_release_count"] += gate_releases
        totals["matched_eot_count"] += eot_releases
        totals["fine_unlinked_channel_count"] += stop_releases
        songs.append({
            "sound_id": entry["sound_id"],
            "direct_allocations": direct,
            "cgb_allocations": cgb,
            "dropped_notes": dropped,
        })
    return {"ticks": ticks, "song_count": len(songs), **totals, "songs": songs}
