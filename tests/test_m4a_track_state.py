#!/usr/bin/env python3
import unittest
import json
from pathlib import Path

from tools.decode_m4a_tracks import decode_track
from tools.m4a_command_vm import MPlayTrackVM
from tools.m4a_track_state import MPlayMusicalState


class M4ATrackStateTests(unittest.TestCase):
    def test_commands_produce_runtime_note_request_from_shared_registers(self):
        # TEMPO75, PRIO10, VOICE3, VOL100, PAN64, N06 C4 vel100, W06, FINE.
        raw = bytes.fromhex("bb4bba0abd03be64bf40d53c6486b1")
        commands = decode_track(raw, 0x100)
        command_map = {command["offset"]: command for command in commands}
        vm = MPlayTrackVM(0x100, command_map)
        state = MPlayMusicalState(track_ptr=0x08000100)
        vm.step_tick(
            on_command=lambda command: state.handle_command(command, tick=vm.tick),
            on_lfo=lambda: state.advance_lfo(tick=vm.tick),
        )
        self.assertEqual((state.tempo_raw, state.priority, state.voice), (75, 10, 3))
        self.assertEqual((vm.wait, vm.tick), (5, 1))
        self.assertEqual(len(state.note_requests), 1)
        note = state.note_requests[0]
        self.assertEqual((note.key, note.velocity, note.gate_time), (60, 100, 6))
        self.assertEqual((note.pitch_key, note.pitch_fine), (60, 0))
        self.assertEqual((note.track_right, note.track_left), (100, 99))

    def test_pitch_and_mix_commands_mark_shared_dirty_state(self):
        state = MPlayMusicalState(track_ptr=0x08000200)
        commands = decode_track(bytes.fromhex("bcfec020c10cc844be50bf50b1"), 0x200)
        for command in commands:
            state.handle_command(command, tick=0)
        self.assertEqual(state.pitch_components(), {
            "key_shift": -2, "bend": -32, "bend_range": 12, "tune": 4,
        })
        self.assertTrue(state.pitch_dirty)
        self.assertTrue(state.mix_dirty)
        self.assertEqual((state.volume, state.pan), (80, 80))

    def test_lfo_advances_after_command_phase_and_emits_runtime_updates(self):
        state = MPlayMusicalState(track_ptr=0x08000300)
        commands = decode_track(bytes.fromhex("c240c440"), 0x300)
        for command in commands:
            state.handle_command(command, tick=0)
        observed = []
        for tick in range(4):
            state.advance_lfo(tick=tick)
            observed.append((state.mod_value, state.pitch_dirty))
            state.clear_dirty()
        self.assertEqual(observed, [(64, True), (0, True), (-64, True), (0, True)])

    def test_eot_and_fine_are_explicit_channel_requests(self):
        state = MPlayMusicalState(track_ptr=0x08000400)
        commands = decode_track(bytes.fromhex("cf3c64ce3cb1"), 0x400)
        for command in commands:
            state.handle_command(command, tick=0)
        self.assertEqual(state.release_keys, [60])
        self.assertTrue(state.stop_requested)

    def test_all_rom_tracks_drive_persistent_registers_for_bounded_runtime(self):
        decoded = json.loads(Path("build/audio-v2/tracks-decoded.json").read_text())
        command_map = {
            command["offset"]: command
            for track in decoded["tracks"] for command in track["commands"]
        }
        states = []
        for track in decoded["tracks"]:
            vm = MPlayTrackVM(track["offset"], command_map)
            state = MPlayMusicalState(track_ptr=0x08000000 + track["offset"])
            for _ in range(2048):
                if vm.running:
                    vm.step_tick(
                        on_command=lambda command, vm=vm, state=state: state.handle_command(
                            command, tick=vm.tick
                        ),
                        on_lfo=lambda vm=vm, state=state: state.advance_lfo(tick=vm.tick),
                    )
            states.append(state)
        self.assertEqual(sum(len(state.note_requests) for state in states), 17546)
        self.assertEqual(sum(len(state.release_keys) for state in states), 21)
        self.assertEqual(sum(state.stop_requested for state in states), 79)
        self.assertTrue(all(state.pitch_dirty and state.mix_dirty for state in states))


if __name__ == "__main__":
    unittest.main()
