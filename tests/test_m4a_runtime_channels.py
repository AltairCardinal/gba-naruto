#!/usr/bin/env python3
import unittest
from pathlib import Path
import json
import hashlib

from tools.m4a_command_vm import MPlayTrackVM
from tools.m4a_runtime_channels import (
    M4AChannelRuntime,
    M4ATrackRunner,
    simulate_bounded_bank,
)
from tools.m4a_track_state import MPlayMusicalState, NoteRequest
from tools.m4a_scheduler import BUFFER_FRAMES, PcmRing
from tools.m4a_pcm import interleave_wav_u8


def note(*, track: int, voice: int, key: int, velocity: int, gate: int) -> NoteRequest:
    return NoteRequest(
        tick=0, track_ptr=track, voice=voice, key=key, velocity=velocity,
        gate_time=gate, tied=False, pitch_key=key, pitch_fine=0,
        pitch_key_delta=0,
        track_right=100, track_left=99,
    )


class M4ARuntimeChannelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = Path("rom/base.gba").read_bytes()

    def test_real_directsound_note_resolves_and_allows_same_key_polyphony(self):
        runtime = M4AChannelRuntime(
            self.rom, voicegroup_offset=0x46480C, player_priority=255
        )
        first = runtime.allocate(note(
            track=0x08535CFC, voice=0, key=57, velocity=72, gate=2
        ), track_priority=0)
        second = runtime.allocate(note(
            track=0x08535CFC, voice=0, key=57, velocity=72, gate=2
        ), track_priority=0)
        self.assertEqual((first.kind, first.channel_index, first.tone_type), ("direct", 0, 0))
        self.assertEqual((second.kind, second.channel_index), ("direct", 1))
        channel = runtime.direct[0]
        self.assertEqual(channel.wave_offset, 0x46606C)
        self.assertEqual((channel.sample_count, channel.loop_start), (20789, 10505))
        self.assertEqual(channel.step, 11772)
        self.assertEqual(channel.adsr, (255, 0, 255, 0))
        self.assertEqual(channel.envelope.phase, "new")
        right, left = runtime.mix_direct_chunk(PcmRing(), chunk_index=0, reverb=0)
        self.assertEqual((len(right), len(left)), (BUFFER_FRAMES, BUFFER_FRAMES))
        self.assertTrue(any(right) or any(left))
        self.assertEqual(channel.envelope.level, 255)
        self.assertEqual(
            hashlib.sha256(interleave_wav_u8(right, left)).hexdigest(),
            "da11e7ede6b8fa119983d90d69f526aeffb11a9a49682d9caf36aea215d5939c",
        )
        self.assertEqual(
            (channel.sample_index, channel.remaining, channel.phase),
            (197, 20592, 798080),
        )
        track = runtime.tracks[0x08535CFC]
        self.assertEqual(track.head, 1)
        self.assertEqual(runtime.release_key(0x08535CFC, 57), 1)
        self.assertFalse(runtime.direct[0].status & 0x40)

    def test_real_sound_144_uses_fixed_noise_channel_and_retriggers(self):
        runtime = M4AChannelRuntime(
            self.rom, voicegroup_offset=0x465778, player_priority=255
        )
        request = note(track=0x0853D38C, voice=43, key=72, velocity=12, gate=6)
        first = runtime.allocate(request, track_priority=0)
        second = runtime.allocate(request, track_priority=0)
        self.assertEqual(
            (first.kind, first.channel_index, first.tone_type, first.tone_offset),
            ("cgb", 3, 0x0C, 0x46597C),
        )
        self.assertEqual(second.channel_index, 3)
        self.assertEqual(runtime.tracks[0x0853D38C].head, 13)
        self.assertEqual(
            runtime.cgb[3].registers,
            {"NR41": 0x00, "NR42": 0x18, "NR43": 0x14, "NR44": 0x80, "NR51": 0x88},
        )

    def test_drum_note_applies_track_pitch_delta_without_cgb_echo_fields(self):
        runtime = M4AChannelRuntime(
            self.rom, voicegroup_offset=0x46480C, player_priority=255
        )
        request = NoteRequest(
            tick=0,
            track_ptr=0x08535CFC,
            voice=4,
            key=36,
            velocity=72,
            gate_time=2,
            tied=False,
            pitch_key=37,
            pitch_fine=128,
            pitch_key_delta=1,
            track_right=100,
            track_left=99,
        )
        result = runtime.allocate(request, track_priority=0)
        channel = runtime.direct[result.channel_index]
        self.assertEqual((result.kind, result.tone_offset), ("direct", 0x464F2C))
        self.assertEqual((channel.pitch_key, channel.pitch_fine), (61, 128))
        self.assertEqual(channel.step, 15273)
        self.assertEqual((channel.echo_length, channel.echo_volume), (0, 0))

    def test_gate_scan_releases_and_fine_unlinks_channels(self):
        runtime = M4AChannelRuntime(
            self.rom, voicegroup_offset=0x46480C, player_priority=255
        )
        runtime.allocate(note(
            track=0x08535CFC, voice=0, key=57, velocity=72, gate=2
        ), track_priority=0)
        self.assertEqual(runtime.scan_gates(0x08535CFC), [])
        self.assertEqual(runtime.scan_gates(0x08535CFC), [0])
        self.assertTrue(runtime.direct[0].status & 0x40)
        self.assertEqual(runtime.stop_track(0x08535CFC), [0])
        self.assertIsNone(runtime.tracks[0x08535CFC].head)
        self.assertEqual(runtime.direct[0].track_ptr, 0)

    def test_track_sweep_unlinks_a_naturally_finished_direct_channel(self):
        runtime = M4AChannelRuntime(
            self.rom, voicegroup_offset=0x46480C, player_priority=255
        )
        runtime.allocate(note(
            track=0x08535CFC, voice=0, key=57, velocity=72, gate=4
        ), track_priority=0)
        channel = runtime.direct[0]
        channel.sample_count = 1
        channel.remaining = 1
        channel.step = 20000
        channel.envelope.status &= ~0x10
        runtime.mix_direct_chunk(PcmRing(), chunk_index=0, reverb=0)
        self.assertEqual(channel.status, 0)
        self.assertEqual(runtime.scan_gates(0x08535CFC), [])
        self.assertIsNone(runtime.tracks[0x08535CFC].head)
        self.assertEqual(channel.track_ptr, 0)

    def test_dirty_track_pitch_and_mix_propagate_to_an_active_channel(self):
        track_ptr = 0x08535CFC
        runtime = M4AChannelRuntime(
            self.rom, voicegroup_offset=0x46480C, player_priority=255
        )
        runtime.allocate(note(
            track=track_ptr, voice=0, key=57, velocity=72, gate=8
        ), track_priority=0)
        state = MPlayMusicalState(track_ptr=track_ptr)
        state.handle_command({"name": "BEND", "value": 0x50}, tick=1)
        state.handle_command({"name": "VOL", "value": 64}, tick=1)
        self.assertTrue(state.pitch_dirty and state.mix_dirty)
        runtime.propagate_track(state)
        channel = runtime.direct[0]
        self.assertEqual((channel.pitch_key, channel.pitch_fine), (57, 128))
        self.assertEqual(channel.step, 12122)
        self.assertEqual((channel.pre_right, channel.pre_left), (36, 35))
        self.assertFalse(state.pitch_dirty or state.mix_dirty)

    def test_real_decoded_tracks_reach_direct_and_noise_allocators(self):
        bank = json.loads(Path("sequel/content/audio/bank.json").read_text())
        decoded = json.loads(Path("build/audio-v2/tracks-decoded.json").read_text())
        command_map = {
            command["offset"]: command
            for track in decoded["tracks"] for command in track["commands"]
        }
        for sound_id, expected_kind, minimum_ticks in ((1, "direct", 105), (144, "cgb", 3)):
            entry = next(row for row in bank["entries"] if row["sound_id"] == sound_id)
            track_ptr = entry["track_ptrs"][0]
            vm = MPlayTrackVM(track_ptr - 0x08000000, command_map)
            state = MPlayMusicalState(track_ptr=track_ptr)
            runtime = M4AChannelRuntime(
                self.rom,
                voicegroup_offset=entry["voicegroup_ptr"] - 0x08000000,
                player_priority=entry["priority"],
            )
            runner = M4ATrackRunner(vm, state, runtime)
            for _ in range(minimum_ticks):
                runner.step_tick()
            self.assertTrue(runner.allocations)
            self.assertEqual(runner.allocations[0].kind, expected_kind)

    def test_all_songs_wire_every_bounded_note_request_to_or_through_allocator(self):
        bank = json.loads(Path("sequel/content/audio/bank.json").read_text())
        decoded = json.loads(Path("build/audio-v2/tracks-decoded.json").read_text())
        result = simulate_bounded_bank(self.rom, bank, decoded, ticks=2048)
        self.assertEqual(result["note_request_count"], 17546)
        self.assertEqual(result["direct_allocation_count"], 17121)
        self.assertEqual(result["cgb_allocation_count"], 11)
        self.assertEqual(result["dropped_note_count"], 414)
        self.assertEqual(result["gate_release_count"], 16848)
        self.assertEqual(result["matched_eot_count"], 18)


if __name__ == "__main__":
    unittest.main()
