#!/usr/bin/env python3
import unittest
import json
from pathlib import Path

from tools.decode_m4a_tracks import decode_track
from tools.m4a_command_vm import MPlayTrackVM


class M4ACommandVmTests(unittest.TestCase):
    def _vm(self, raw: bytes, offset: int = 0x100) -> MPlayTrackVM:
        commands = decode_track(raw, offset)
        return MPlayTrackVM(offset, {item["offset"]: item for item in commands})

    def test_wait_is_loaded_and_decremented_in_the_same_tick(self):
        vm = self._vm(bytes((0x86, 0xB1)))  # W06, FINE
        vm.step_tick()
        self.assertEqual((vm.tick, vm.wait, vm.running), (1, 5, True))
        for _ in range(5):
            vm.step_tick()
        self.assertEqual((vm.tick, vm.wait, vm.running), (6, 0, True))
        vm.step_tick()
        self.assertFalse(vm.running)

    def test_backward_goto_continues_across_requested_runtime_ticks(self):
        # W01; GOTO start. Unlike the structural MIDI executor, runtime must
        # not terminate at the first backward edge.
        vm = self._vm(bytes.fromhex("81b200010008"))
        observed = []
        for _ in range(4):
            vm.step_tick(on_command=lambda command: observed.append(command["name"]))
        self.assertEqual(observed, ["W01", "GOTO", "W01", "GOTO", "W01", "GOTO", "W01"])
        self.assertTrue(vm.running)
        self.assertEqual(vm.tick, 4)

    def test_pattern_stack_and_repeat_state_persist_between_ticks(self):
        # Main PATT pattern; W01; REPT once back to W01; FINE. Pattern is W01/PEND.
        raw = bytes.fromhex("b30d01000881b50105010008b181b4")
        vm = self._vm(raw)
        names = []
        for _ in range(8):
            vm.step_tick(on_command=lambda command: names.append(command["name"]))
            if not vm.running:
                break
        self.assertIn("PATT", names)
        self.assertIn("PEND", names)
        self.assertIn("REPT", names)
        self.assertFalse(vm.running)

    def test_gate_scan_precedes_new_commands(self):
        vm = self._vm(bytes((0x81, 0xB1)))
        order = []
        vm.step_tick(
            on_gate_scan=lambda: order.append("gate"),
            on_command=lambda command: order.append(command["name"]),
        )
        self.assertEqual(order, ["gate", "W01"])

    def test_control_flow_without_wait_fails_explicitly(self):
        vm = self._vm(bytes.fromhex("b200010008"))
        with self.assertRaisesRegex(ValueError, "without WAIT"):
            vm.step_tick(max_commands=8)

    def test_all_rom_tracks_execute_for_bounded_runtime_without_loop_cutoff(self):
        decoded = json.loads(Path("build/audio-v2/tracks-decoded.json").read_text())
        command_map = {
            command["offset"]: command
            for track in decoded["tracks"] for command in track["commands"]
        }
        vms = [MPlayTrackVM(track["offset"], command_map) for track in decoded["tracks"]]
        for vm in vms:
            for _ in range(2048):
                if vm.running:
                    vm.step_tick()
        self.assertEqual(len(vms), 217)
        self.assertEqual(sum(vm.running for vm in vms), 138)
        self.assertEqual(sum(not vm.running for vm in vms), 79)
        self.assertEqual(sum(vm.command_counts["GOTO"] for vm in vms), 163)
        self.assertEqual(sum(sum(vm.command_counts.values()) for vm in vms), 39825)


if __name__ == "__main__":
    unittest.main()
