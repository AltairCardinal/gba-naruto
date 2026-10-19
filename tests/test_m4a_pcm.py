#!/usr/bin/env python3
import unittest
import tempfile
import wave
from pathlib import Path

from tools.m4a_pcm import (
    DirectSoundState,
    interleave_wav_u8,
    linear_sample,
    mix_sample_wrap,
    render_forward,
    reverb_seed,
    write_stereo_wave,
)


class M4APcmTests(unittest.TestCase):
    def test_signed_linear_interpolation_uses_arithmetic_floor(self):
        self.assertEqual(linear_sample(-128, 127, 0), -128)
        self.assertEqual(linear_sample(-128, 127, 0x400000), -1)
        self.assertEqual(linear_sample(-128, 127, 0x7FFFFF), 126)
        self.assertEqual(linear_sample(127, -128, 0x400000), -1)
        self.assertEqual(linear_sample(127, -128, 0x7FFFFF), -128)

    def test_channel_gain_and_accumulation_wrap_instead_of_saturating(self):
        self.assertEqual(mix_sample_wrap(0, 127, 255), 126)
        self.assertEqual(mix_sample_wrap(0, -128, 255), -128)
        self.assertEqual(mix_sample_wrap(100, 80, 256), -76)
        self.assertEqual(mix_sample_wrap(-100, -80, 256), 76)
        self.assertEqual(mix_sample_wrap(127, 1, 256), -128)
        self.assertEqual(mix_sample_wrap(-128, -1, 256), 127)

    def test_forward_nonloop_stops_at_sample_end(self):
        state = DirectSoundState(sample_index=0, remaining=4, phase=0)
        samples = bytes([10, 20, 30, 40, 99])
        output = render_forward(samples, state, step=0x800000, div_freq=1, frames=8)
        self.assertEqual(output, [10, 20, 30, 40])
        self.assertFalse(state.active)

    def test_forward_loop_wraps_at_exact_end(self):
        state = DirectSoundState(sample_index=0, remaining=4, phase=0)
        samples = bytes([10, 20, 30, 40, 99])
        output = render_forward(
            samples, state, step=0x800000, div_freq=1, frames=8,
            sample_count=4, loop_start=2,
        )
        self.assertEqual(output, [10, 20, 30, 40, 30, 40, 30, 40])
        self.assertTrue(state.active)

    def test_phase_can_advance_multiple_source_samples(self):
        state = DirectSoundState(sample_index=0, remaining=5, phase=0)
        samples = bytes([10, 20, 30, 40, 50, 99])
        output = render_forward(samples, state, step=0xC00000, div_freq=1, frames=3)
        self.assertEqual(output, [10, 25, 40])
        self.assertEqual(state.phase, 0x400000)

    def test_reverb_seed_matches_rom_bias(self):
        self.assertEqual(reverb_seed(-1, -1, -1, 0, 128), 0)
        self.assertEqual(reverb_seed(-1, -1, -1, -1, 128), 0)
        self.assertEqual(reverb_seed(-2, -1, -1, -1, 128), -1)
        self.assertEqual(reverb_seed(127, 127, 127, 127, 128), 127)
        self.assertEqual(reverb_seed(10, 20, 30, 40, 0), 0)

    def test_signed_stereo_planes_convert_to_unsigned_interleaved_wav(self):
        self.assertEqual(
            interleave_wav_u8([-128, -1, 0, 127], [127, 0, -1, -128]),
            bytes([0, 255, 127, 128, 128, 127, 255, 0]),
        )

    def test_stereo_wave_writer_preserves_frames_and_rate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mix.wav"
            write_stereo_wave(path, [-128, 0], [127, -1], sample_rate=15768)
            with wave.open(str(path), "rb") as result:
                self.assertEqual(result.getnchannels(), 2)
                self.assertEqual(result.getsampwidth(), 1)
                self.assertEqual(result.getframerate(), 15768)
                self.assertEqual(result.getnframes(), 2)
                self.assertEqual(result.readframes(2), bytes([0, 255, 128, 127]))


if __name__ == "__main__":
    unittest.main()
