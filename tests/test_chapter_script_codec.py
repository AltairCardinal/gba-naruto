#!/usr/bin/env python3
"""TDD contract for the first semantics-safe chapter opcode subset."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.chapter_script_codec import (
    ChapterScriptError,
    ReservedOpcodeError,
    TruncatedCommandError,
    UnsupportedOpcodeError,
    decode_script,
    encode_script,
)


class ChapterScriptCodecTests(unittest.TestCase):
    def test_complete_alternate_scenario_39_round_trips_byte_exactly(self):
        rom = (Path(__file__).resolve().parents[1] / "rom/base.gba").read_bytes()
        script = rom[0x31281:0x3142F]
        commands = decode_script(script)
        self.assertEqual(len(commands), 25)
        self.assertEqual(encode_script(commands), script)

    def test_decodes_set_battle_then_independent_end(self):
        commands = decode_script(bytes.fromhex("1a280200"))
        self.assertEqual(commands, [
            {
                "opcode": 0x1A,
                "name": "set_battle",
                "offset": 0,
                "length": 3,
                "battle_id": 40,
                "mode": 2,
            },
            {
                "opcode": 0x00,
                "name": "end",
                "offset": 3,
                "length": 1,
                "call_depth_semantics": (
                    "end script at depth zero; otherwise return from interpreter subroutine"
                ),
            },
        ])

    def test_round_trip_is_byte_exact(self):
        decoded = decode_script(bytes.fromhex("1a280200"))
        self.assertEqual(encode_script(decoded), bytes.fromhex("1a280200"))
        self.assertEqual(
            encode_script([
                {"name": "set_battle", "battle_id": 255, "mode": 0},
                {"name": "end"},
            ]),
            bytes.fromhex("1aff0000"),
        )

    def test_audio_cue_and_speaker_label_subset_round_trips(self):
        data = bytes.fromhex("1b0400080700")
        commands = decode_script(data)
        self.assertEqual(commands[0]["name"], "audio_cue")
        self.assertEqual(commands[0]["cue_id"], 4)
        self.assertEqual(commands[0]["mode"], "play")
        self.assertEqual(commands[1]["name"], "set_speaker_label")
        self.assertEqual(commands[1]["speaker_label_id"], 7)
        self.assertEqual(encode_script(commands), data)
        with self.assertRaisesRegex(ChapterScriptError, "audio mode"):
            encode_script([{"name": "audio_cue", "cue_id": 4, "mode": "loop"}, {"name": "end"}])

    def test_portrait_show_and_update_subset_round_trips(self):
        data = bytes.fromhex("020107000400010000")
        commands = decode_script(data)
        self.assertEqual(commands[0], {
            "opcode": 0x02,
            "name": "show_portrait",
            "offset": 0,
            "length": 4,
            "portrait_slot": 1,
            "portrait_id": 7,
            "expression_id": 0,
        })
        self.assertEqual(commands[1], {
            "opcode": 0x04,
            "name": "update_portrait",
            "offset": 4,
            "length": 4,
            "portrait_slot": 0,
            "portrait_id": 1,
            "expression_id": 0,
        })
        self.assertEqual(encode_script(commands), data)
        for field, value in (("portrait_slot", 2), ("portrait_id", 63), ("expression_id", 6)):
            command = {
                "name": "show_portrait",
                "portrait_slot": 0,
                "portrait_id": 1,
                "expression_id": 0,
            }
            command[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ChapterScriptError, field):
                encode_script([command, {"name": "end"}])

    def test_encoded_render_text_round_trips_without_claiming_unicode_identity(self):
        data = bytes.fromhex("0181670a81400000")
        commands = decode_script(data)
        self.assertEqual(commands[0], {
            "opcode": 0x01,
            "name": "render_text",
            "offset": 0,
            "length": 7,
            "encoded_text_hex": "81670a8140",
        })
        self.assertEqual(encode_script(commands), data)
        with self.assertRaisesRegex(ChapterScriptError, "encoded_text_hex"):
            encode_script([
                {"name": "render_text", "encoded_text_hex": "8167ff"},
                {"name": "end"},
            ])

    def test_decode_rejects_truncation_and_bytes_after_end(self):
        with self.assertRaisesRegex(TruncatedCommandError, "set_battle"):
            decode_script(bytes.fromhex("1a28"))
        with self.assertRaisesRegex(ChapterScriptError, "after end"):
            decode_script(bytes.fromhex("001a2802"))

    def test_decode_rejects_reserved_and_unproved_opcodes(self):
        with self.assertRaisesRegex(ReservedOpcodeError, "0x24"):
            decode_script(bytes.fromhex("24"))
        with self.assertRaisesRegex(UnsupportedOpcodeError, "0x05"):
            decode_script(bytes.fromhex("05"))

    def test_encode_requires_terminal_end_and_u8_operands(self):
        with self.assertRaisesRegex(ChapterScriptError, "terminal end"):
            encode_script([{"name": "set_battle", "battle_id": 40, "mode": 2}])
        for field in ("battle_id", "mode"):
            command = {"name": "set_battle", "battle_id": 40, "mode": 2}
            command[field] = 256
            with self.subTest(field=field), self.assertRaisesRegex(ChapterScriptError, field):
                encode_script([command, {"name": "end"}])


if __name__ == "__main__":
    unittest.main()
