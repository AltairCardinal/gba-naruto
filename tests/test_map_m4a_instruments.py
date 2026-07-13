#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

from tools.map_m4a_instruments import analyze, resolve_tone


class MapM4AInstrumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = Path("rom/base.gba").read_bytes()

    def test_drum_key_resolves_to_directsound_child(self):
        result = resolve_tone(self.rom, 0x46480C, 4, 46)
        self.assertTrue(result["drum"])
        self.assertEqual(result["parent"]["type"], 0x80)
        self.assertEqual(result["terminal"]["type"], 0)
        self.assertEqual(result["terminal"]["pointer"], 0x084851B4)

    def test_all_executed_notes_have_terminal_instruments(self):
        result = analyze(
            self.rom,
            json.loads(Path("sequel/content/audio/bank.json").read_text()),
            json.loads(Path("build/audio-v2/tracks-decoded.json").read_text()),
        )
        self.assertEqual(result["song_count"], 80)
        self.assertEqual(result["note_count"], 16180)
        self.assertEqual(result["drum_note_count"], 5340)
        self.assertEqual(result["terminal_type_counts"], {"0x00": 16169, "0x0C": 11})
        self.assertEqual(result["unique_wave_count"], 79)
        self.assertEqual(result["missing_wave_count"], 0)
        self.assertEqual(result["center_pitch_step_count"], 16169)
        self.assertEqual(result["invalid_center_pitch_step_count"], 0)
        self.assertGreater(result["center_pitch_step_range"]["min"], 0)
        self.assertGreaterEqual(
            result["center_pitch_step_range"]["max"],
            result["center_pitch_step_range"]["min"],
        )


if __name__ == "__main__":
    unittest.main()
