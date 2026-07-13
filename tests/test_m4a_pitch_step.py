#!/usr/bin/env python3
from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

from tools.m4a_pitch_step import midi_key_to_step, mixer_advance


class M4APitchStepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = Path("rom/base.gba").read_bytes()

    def test_rom_integer_formula_matches_known_wave_vectors(self):
        raw = 0x00DAC000
        vectors = {
            (0, 0): 437,
            (59, 0): 13214,
            (60, 0): 14000,
            (60, 128): 14416,
            (60, 255): 14829,
            (61, 0): 14832,
            (69, 0): 23545,
            (178, 0): 12771924,
            (179, 0): 13528415,
        }
        for (key, fine), expected in vectors.items():
            with self.subTest(key=key, fine=fine):
                self.assertEqual(
                    midi_key_to_step(self.rom, raw, key=key, fine=fine), expected
                )

    def test_key_above_engine_limit_clamps_key_and_fine(self):
        raw = 0x00DAC000
        self.assertEqual(
            midi_key_to_step(self.rom, raw, key=255, fine=0),
            midi_key_to_step(self.rom, raw, key=178, fine=255),
        )

    def test_all_extracted_waves_have_positive_center_step(self):
        manifest = json.loads(Path("build/audio-v2/manifest.json").read_text())
        steps = [
            midi_key_to_step(self.rom, wave["frequency_raw"], key=60, fine=0)
            for wave in manifest["waves"]
        ]
        self.assertEqual(len(steps), 79)
        self.assertTrue(all(step > 0 for step in steps))

    def test_mixer_uses_23_bit_fractional_phase(self):
        phase, advance = mixer_advance(phase=0x7FFFF0, step=14000, div_freq=532)
        total = 0x7FFFF0 + 14000 * 532
        self.assertEqual(advance, total >> 23)
        self.assertEqual(phase, total & 0x7FFFFF)

    def test_track_pitch_command_jump_table_matches_handlers(self):
        table = 0x464534
        expected = {
            0xBC: 0x0809A2FD,
            0xC0: 0x0809A369,
            0xC1: 0x0809A37D,
            0xC2: 0x0809A971,
            0xC3: 0x0809A391,
            0xC4: 0x0809A985,
            0xC5: 0x0809A39D,
            0xC8: 0x0809A3B5,
        }
        for opcode, pointer in expected.items():
            with self.subTest(opcode=hex(opcode)):
                self.assertEqual(
                    struct.unpack_from(
                        "<I", self.rom, table + (opcode - 0xB1) * 4
                    )[0],
                    pointer,
                )


if __name__ == "__main__":
    unittest.main()
