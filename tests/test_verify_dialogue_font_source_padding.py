#!/usr/bin/env python3
from pathlib import Path
import unittest

from tools.verify_dialogue_font_source_padding import (
    rebuild_dialogue_font_source_padding,
)

ROOT = Path(__file__).resolve().parents[1]


class DialogueFontSourcePaddingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_rebuilds_exact_zero_gaps_between_fixed_sjis_source_extents(self):
        report = rebuild_dialogue_font_source_padding(ROOT, self.rom)
        self.assertTrue(report["verified"], report)
        self.assertEqual(19, report["padding_range_count"])
        self.assertEqual(2_848, report["padding_bytes"])
        self.assertEqual(1, report["excluded_nonzero_gap_count"])

    def test_rejects_each_tampered_padding_range(self):
        report = rebuild_dialogue_font_source_padding(ROOT, self.rom)
        for item in report["ranges"]:
            tampered = bytearray(self.rom)
            tampered[item["range"][0]] = 1
            with self.subTest(offset=item["range"][0]):
                self.assertFalse(
                    rebuild_dialogue_font_source_padding(
                        ROOT, bytes(tampered)
                    )["verified"]
                )


if __name__ == "__main__":
    unittest.main()
