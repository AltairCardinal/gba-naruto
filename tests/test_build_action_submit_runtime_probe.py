import hashlib
import importlib
import unittest
from pathlib import Path

from tools.thumb_branch import decode_thumb_bl, encode_thumb_bl
from tests.thumb_observer_machine import execute_stub


ROOT = Path(__file__).resolve().parent.parent

try:
    probe_builder = importlib.import_module("tools.build_action_submit_runtime_probe")
except ModuleNotFoundError:
    probe_builder = None


@unittest.skipIf(probe_builder is None, "action-submit probe builder not implemented")
class ActionSubmitRuntimeProbeTests(unittest.TestCase):
    def setUp(self):
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.probe = probe_builder.build_probe(self.base)

    def test_base_rom_and_both_checked_calls_are_exact(self):
        self.assertEqual(hashlib.sha1(self.base).hexdigest(), probe_builder.BASE_SHA1)
        for site in probe_builder.OBSERVER_SITES:
            hook_offset = site.hook - probe_builder.ROM_BASE
            self.assertEqual(
                self.base[hook_offset : hook_offset + 4],
                encode_thumb_bl(site.hook, site.original),
            )
            self.assertEqual(
                self.probe[hook_offset : hook_offset + 4],
                encode_thumb_bl(site.hook, site.stub),
            )
            first = int.from_bytes(self.probe[hook_offset : hook_offset + 2], "little")
            second = int.from_bytes(self.probe[hook_offset + 2 : hook_offset + 4], "little")
            self.assertEqual(decode_thumb_bl(site.hook, first, second), site.stub)

        self.assertEqual(
            [(site.hook, site.original) for site in probe_builder.OBSERVER_SITES],
            [
                (0x0807443C, 0x080722A8),
                (0x08074918, 0x080722A8),
            ],
        )
        self.assertEqual(
            [site.stub for site in probe_builder.OBSERVER_SITES],
            [0x0809E800, 0x0809E880],
        )

    def test_sites_have_independent_records_events_and_shared_sequence(self):
        first, second = probe_builder.OBSERVER_SITES
        self.assertNotEqual(first.stub, second.stub)
        self.assertNotEqual(first.scratch, second.scratch)
        self.assertNotEqual(first.magic, second.magic)
        self.assertNotEqual(first.event_code, second.event_code)
        self.assertEqual(probe_builder.EVENT_COUNTER % 4, 0)
        self.assertTrue(0x02000000 <= probe_builder.EVENT_COUNTER < 0x02040000)

        for site in probe_builder.OBSERVER_SITES:
            stub_offset = site.stub - probe_builder.ROM_BASE
            stub = self.probe[stub_offset : stub_offset + probe_builder.STUB_SIZE]
            for literal in (
                site.scratch,
                site.magic,
                site.event_code,
                site.hook,
                probe_builder.EVENT_COUNTER,
                probe_builder.CURRENT_OBJECT,
                site.original | 1,
            ):
                self.assertIn(literal.to_bytes(4, "little"), stub)

    def test_hook_record_captures_current_object_and_resolved_unit_before_original(self):
        site = probe_builder.OBSERVER_SITES[0]
        memory = {
            probe_builder.CURRENT_OBJECT: 0x01000001,
            probe_builder.CURRENT_OBJECT + 4: 0x02024294,
            0x02024294: 0x0D0E0101,
            0x02024294 + 0xC0: 0x00000100,
            0x02024294 + 0xC4: 0x04000A04,
            0x02024294 + 0xC8: 0x3322110A,
            0x02024294 + 0xCC: 0x77665544,
            probe_builder.EVENT_COUNTER: 8,
        }
        initial = {
            **{f"r{index}": 0x11110000 + index for index in range(8)},
            "sp": 0x03007E00,
            "lr": site.hook + 5,
        }
        state = execute_stub(
            self.probe[
                site.stub - probe_builder.ROM_BASE:
                site.stub - probe_builder.ROM_BASE + probe_builder.STUB_SIZE
            ],
            registers=initial,
            memory=memory,
        )

        fields = (
            "magic", "hit_count", "sequence", "event_code", "source_hook", "object_word",
            "object_record_pointer", "record_address", "record_word_00", "record_word_c0",
            "record_word_c4", "record_word_c8", "record_word_cc",
        )
        record = {
            field: state.read_u32(site.scratch + index * 4)
            for index, field in enumerate(fields)
        }
        self.assertEqual(
            record,
            {
                "magic": site.magic,
                "hit_count": 1,
                "sequence": 9,
                "event_code": site.event_code,
                "source_hook": site.hook,
                "object_word": 0x01000001,
                "object_record_pointer": 0x02024294,
                "record_address": 0x02024294,
                "record_word_00": 0x0D0E0101,
                "record_word_c0": 0x00000100,
                "record_word_c4": 0x04000A04,
                "record_word_c8": 0x3322110A,
                "record_word_cc": 0x77665544,
            },
        )
        for register in (*[f"r{index}" for index in range(8)], "sp", "lr"):
            self.assertEqual(state.registers[register], initial[register])
        self.assertEqual(state.branch_target, site.original | 1)

    def test_patch_is_confined_to_two_calls_and_two_zero_caves(self):
        allowed = set()
        for site in probe_builder.OBSERVER_SITES:
            allowed.update(range(site.hook - probe_builder.ROM_BASE, site.hook - probe_builder.ROM_BASE + 4))
            allowed.update(range(site.stub - probe_builder.ROM_BASE, site.stub - probe_builder.ROM_BASE + probe_builder.STUB_SIZE))
        changed = {index for index, (before, after) in enumerate(zip(self.base, self.probe)) if before != after}
        self.assertTrue(changed)
        self.assertTrue(changed <= allowed)

    def test_wrong_call_and_occupied_cave_fail_closed(self):
        wrong_call = bytearray(self.base)
        wrong_call[probe_builder.OBSERVER_SITES[0].hook - probe_builder.ROM_BASE] ^= 1
        with self.assertRaisesRegex(ValueError, "call-site bytes do not match"):
            probe_builder.build_probe(bytes(wrong_call), verify_sha1=False)

        occupied = bytearray(self.base)
        occupied[probe_builder.OBSERVER_SITES[1].stub - probe_builder.ROM_BASE] = 1
        with self.assertRaisesRegex(ValueError, "stub region is not zero-filled"):
            probe_builder.build_probe(bytes(occupied), verify_sha1=False)


class ActionSubmitRuntimeProbePresenceTests(unittest.TestCase):
    def test_action_submit_probe_builder_exists(self):
        self.assertIsNotNone(probe_builder, "missing tools.build_action_submit_runtime_probe")


if __name__ == "__main__":
    unittest.main()
