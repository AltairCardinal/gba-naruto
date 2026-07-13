#!/usr/bin/env python3
import unittest
from pathlib import Path

from tools.m4a_psg import (
    cgb_volume,
    noise_clock_hz,
    noise_lfsr_step,
    noise_register,
    noise_start_registers,
    noise_stop_registers,
)


class M4APsgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = Path("rom/base.gba").read_bytes()

    def test_noise_key_table_and_clamps(self):
        self.assertEqual(noise_register(self.rom, 20), 0xD7)
        self.assertEqual(noise_register(self.rom, 21), 0xD7)
        self.assertEqual(noise_register(self.rom, 22), 0xD6)
        self.assertEqual(noise_register(self.rom, 72), 0x14)
        self.assertEqual(noise_register(self.rom, 79), 0x01)
        self.assertEqual(noise_register(self.rom, 80), 0x00)
        self.assertEqual(noise_register(self.rom, 127), 0x00)

    def test_noise_clock_and_lfsr_width(self):
        self.assertEqual(noise_clock_hz(0x14), 32768)
        self.assertEqual(noise_clock_hz(0x00), 524288)
        self.assertEqual(noise_lfsr_step(0x0001, width7=False), 0x4000)
        self.assertEqual(noise_lfsr_step(0x4000, width7=False), 0x2000)
        self.assertEqual(noise_lfsr_step(0x0001, width7=True), 0x4040)
        self.assertEqual(noise_lfsr_step(0x4040, width7=True), 0x2020)

    def test_cgb_volume_pan_and_sustain(self):
        self.assertEqual(cgb_volume(8, 8, sustain=15), (1, 1, 0x88))
        self.assertEqual(cgb_volume(22, 22, sustain=15), (2, 2, 0x88))
        self.assertEqual(cgb_volume(36, 35, sustain=15), (4, 4, 0x88))
        self.assertEqual(cgb_volume(32, 8, sustain=15), (2, 2, 0x08))
        self.assertEqual(cgb_volume(8, 32, sustain=15), (2, 2, 0x80))

    def test_sound_144_noise_register_vectors(self):
        expected = {
            12: {"NR41": 0x00, "NR42": 0x18, "NR43": 0x14, "NR44": 0x80, "NR51": 0x88},
            32: {"NR41": 0x00, "NR42": 0x28, "NR43": 0x14, "NR44": 0x80, "NR51": 0x88},
            52: {"NR41": 0x00, "NR42": 0x48, "NR43": 0x14, "NR44": 0x80, "NR51": 0x88},
        }
        for velocity, registers in expected.items():
            self.assertEqual(
                noise_start_registers(
                    self.rom,
                    key=72,
                    length=0,
                    pointer=0,
                    attack=0,
                    sustain=15,
                    track_right=90,
                    track_left=89,
                    velocity=velocity,
                ),
                registers,
            )

        self.assertEqual(noise_stop_registers(), {"NR42": 0x08, "NR44": 0x80})


if __name__ == "__main__":
    unittest.main()
