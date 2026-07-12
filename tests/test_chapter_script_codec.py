#!/usr/bin/env python3
"""TDD contract for the first semantics-safe chapter opcode subset."""

from __future__ import annotations

import unittest

from tools.chapter_script_codec import (
    ChapterScriptError,
    ReservedOpcodeError,
    TruncatedCommandError,
    UnsupportedOpcodeError,
    decode_script,
    encode_script,
)


class ChapterScriptCodecTests(unittest.TestCase):
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

    def test_decode_rejects_truncation_and_bytes_after_end(self):
        with self.assertRaisesRegex(TruncatedCommandError, "set_battle"):
            decode_script(bytes.fromhex("1a28"))
        with self.assertRaisesRegex(ChapterScriptError, "after end"):
            decode_script(bytes.fromhex("001a2802"))

    def test_decode_rejects_reserved_and_unproved_opcodes(self):
        with self.assertRaisesRegex(ReservedOpcodeError, "0x24"):
            decode_script(bytes.fromhex("24"))
        with self.assertRaisesRegex(UnsupportedOpcodeError, "0x01"):
            decode_script(bytes.fromhex("01"))

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
