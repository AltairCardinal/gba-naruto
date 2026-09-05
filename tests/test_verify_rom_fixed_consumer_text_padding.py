#!/usr/bin/env python3
from pathlib import Path
import json
import subprocess
import sys
import unittest

from tools.verify_rom_fixed_consumer_text_padding import (
    rebuild_fixed_consumer_text_padding,
)

ROOT = Path(__file__).resolve().parents[1]


class FixedConsumerTextPaddingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_rebuilds_exact_same_table_zero_gap_denominator(self):
        report = rebuild_fixed_consumer_text_padding(ROOT, self.rom)
        self.assertTrue(report["verified"], report)
        self.assertEqual(590, report["padding_range_count"])
        self.assertEqual(6_738, report["padding_bytes"])
        self.assertEqual(6_738, report["zero_byte_count"])

    def test_rejects_each_tampered_padding_range(self):
        report = rebuild_fixed_consumer_text_padding(ROOT, self.rom)
        for item in report["ranges"]:
            tampered = bytearray(self.rom)
            tampered[item["range"][0]] = 1
            with self.subTest(offset=item["range"][0]):
                self.assertFalse(
                    rebuild_fixed_consumer_text_padding(
                        ROOT, bytes(tampered)
                    )["verified"]
                )

    def test_cli_emits_structured_verification_report(self):
        result = subprocess.run(
            [
                sys.executable,
                "tools/verify_rom_fixed_consumer_text_padding.py",
                "--root",
                ".",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["verified"], report)
        self.assertEqual(590, report["padding_range_count"])
        self.assertEqual(6_738, report["padding_bytes"])


if __name__ == "__main__":
    unittest.main()
