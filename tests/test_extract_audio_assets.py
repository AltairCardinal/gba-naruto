#!/usr/bin/env python3
import tempfile
import unittest
import wave
from pathlib import Path

from tools.extract_audio_assets import parse_wave, write_wave


class AudioAssetTests(unittest.TestCase):
    def test_real_wave_header_uses_16_bytes_and_fixed_point_frequency(self):
        rom = Path("rom/base.gba").read_bytes()
        result = parse_wave(rom, 0x46606C)
        self.assertIsNotNone(result)
        self.assertEqual(result["sample_rate"], 14000)
        self.assertEqual(result["sample_count"], 0x5135)
        self.assertEqual(result["data_offset"], 0x46607C)

    def test_wav_converts_signed_pcm_to_unsigned_riff_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.wav"
            write_wave(path, bytes((0x80, 0x00, 0x7F)), 14000)
            with wave.open(str(path), "rb") as source:
                self.assertEqual(source.getframerate(), 14000)
                self.assertEqual(source.readframes(3), bytes((0x00, 0x80, 0xFF)))


if __name__ == "__main__":
    unittest.main()
