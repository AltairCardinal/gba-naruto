#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

from tools.map_m4a_instruments import (
    _channel_mix_coefficients,
    analyze,
    resolve_tone,
)


class MapM4AInstrumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = Path("rom/base.gba").read_bytes()

    def test_channel_mix_coefficients_match_chn_vol_set_asm(self):
        self.assertEqual(
            _channel_mix_coefficients(127, 126, velocity=127, tone_pan=0),
            (126, 124),
        )
        self.assertEqual(
            _channel_mix_coefficients(127, 126, velocity=127, tone_pan=126),
            (250, 0),
        )
        self.assertEqual(
            _channel_mix_coefficients(127, 126, velocity=127, tone_pan=-128),
            (0, 249),
        )

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
        self.assertEqual(result["track_pitch_step_count"], 16169)
        self.assertEqual(result["invalid_track_pitch_step_count"], 0)
        self.assertEqual(result["noncenter_track_pitch_note_count"], 971)
        self.assertEqual(result["mid_note_pitch_update_count"], 30937)
        self.assertEqual(result["invalid_mid_note_pitch_update_count"], 0)
        self.assertEqual(
            sum(result["mid_note_pitch_update_command_counts"].values()), 30937
        )
        self.assertGreater(result["mid_note_pitch_update_command_counts"]["LFO"], 0)
        self.assertGreater(result["mid_note_pitch_update_command_counts"]["BEND"], 0)
        self.assertEqual(result["channel_mix_note_count"], 16169)
        self.assertEqual(result["invalid_channel_mix_note_count"], 0)
        self.assertEqual(result["mid_note_mix_update_count"], 39)
        self.assertEqual(result["invalid_mid_note_mix_update_count"], 0)
        self.assertEqual(result["mid_note_mix_update_command_counts"], {"VOL": 39})
        self.assertEqual(result["envelope_note_count"], 16169)
        self.assertEqual(result["envelope_parameter_tuple_count"], 4)
        self.assertEqual(result["invalid_envelope_parameter_count"], 0)
        self.assertEqual(result["nonzero_decay_note_count"], 837)
        self.assertEqual(result["nonzero_release_note_count"], 326)


if __name__ == "__main__":
    unittest.main()
