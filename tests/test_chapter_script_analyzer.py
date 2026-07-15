#!/usr/bin/env python3
"""Golden structural decode for the runtime-observed alternate scenario 39."""

from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from tools.chapter_script_analyzer import analyze_observed_script, find_render_text_end


ROOT = Path(__file__).resolve().parents[1]


class ChapterScriptAnalyzerTests(unittest.TestCase):
    def test_text_walker_skips_zero_operands_inside_control_records(self):
        self.assertEqual(find_render_text_end(bytes.fromhex("02000000"), 0), 3)
        self.assertEqual(find_render_text_end(bytes.fromhex("010000"), 0), 2)
        self.assertEqual(find_render_text_end(bytes.fromhex("8167814000"), 0), 4)

    def test_decodes_alternate_scenario_39_to_exact_runtime_distribution(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        start, end = 0x31281, 0x3142F
        commands = analyze_observed_script(rom[start:end], base_address=0x08031281)
        self.assertEqual(len(commands), 25)
        self.assertEqual(Counter(command["opcode"] for command in commands), {
            0x1B: 1,
            0x02: 5,
            0x08: 8,
            0x01: 8,
            0x04: 2,
            0x00: 1,
        })
        self.assertEqual(commands[0]["address"], "0x08031281")
        self.assertEqual(commands[0]["length"], 3)
        self.assertEqual(commands[0]["name"], "audio_cue")
        self.assertEqual(commands[0]["cue_id"], 4)
        self.assertEqual(commands[0]["mode"], "play")
        show_commands = [command for command in commands if command["opcode"] == 0x02]
        self.assertTrue(all(command["name"] == "show_portrait" for command in show_commands))
        self.assertEqual(
            [(command["portrait_slot"], command["portrait_id"], command["expression_id"])
             for command in show_commands],
            [(1, 7, 0), (0, 1, 1), (1, 3, 0), (1, 7, 0), (0, 2, 0)],
        )
        update_commands = [command for command in commands if command["opcode"] == 0x04]
        self.assertTrue(all(command["name"] == "update_portrait" for command in update_commands))
        self.assertEqual(
            [(command["portrait_slot"], command["portrait_id"], command["expression_id"])
             for command in update_commands],
            [(0, 1, 0), (0, 1, 1)],
        )
        text_commands = [command for command in commands if command["opcode"] == 0x01]
        self.assertTrue(all(command["name"] == "render_text" for command in text_commands))
        self.assertTrue(all(command["encoded_text_hex"] for command in text_commands))
        speaker_commands = [command for command in commands if command["opcode"] == 0x08]
        self.assertEqual([command["speaker_label_id"] for command in speaker_commands], [7, 1, 3, 1, 7, 1, 7, 2])
        self.assertTrue(all(command["name"] == "set_speaker_label" for command in speaker_commands))
        self.assertEqual(commands[-1], {
            "opcode": 0,
            "name": "end",
            "offset": 0x1AD,
            "address": "0x0803142E",
            "length": 1,
            "raw_hex": "00",
        })
        self.assertEqual(sum(command["length"] for command in commands), end - start)

    def test_rejects_opcode_outside_observed_subset(self):
        with self.assertRaisesRegex(ValueError, "0x03"):
            analyze_observed_script(bytes.fromhex("0300"), base_address=0x08000000)


if __name__ == "__main__":
    unittest.main()
