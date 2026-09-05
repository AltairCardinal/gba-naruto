#!/usr/bin/env python3
from pathlib import Path
import unittest

from tools.verify_battle_presentation_text_padding import (
    rebuild_battle_presentation_text_padding,
)

ROOT = Path(__file__).resolve().parents[1]


class BattlePresentationTextPaddingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_rebuilds_exact_fixed_message_zero_gap_denominator(self):
        report = rebuild_battle_presentation_text_padding(ROOT, self.rom)
        self.assertTrue(report["verified"], report)
        self.assertEqual(78, report["padding_range_count"])
        self.assertEqual(1_293, report["padding_bytes"])

    def test_rejects_each_tampered_padding_range(self):
        report = rebuild_battle_presentation_text_padding(ROOT, self.rom)
        for item in report["ranges"]:
            tampered = bytearray(self.rom)
            tampered[item["range"][0]] = 1
            with self.subTest(offset=item["range"][0]):
                self.assertFalse(
                    rebuild_battle_presentation_text_padding(
                        ROOT, bytes(tampered)
                    )["verified"]
                )


if __name__ == "__main__":
    unittest.main()
