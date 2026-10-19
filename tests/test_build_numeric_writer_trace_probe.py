#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_numeric_writer_trace_probe import (
    CALL_SITES,
    ROM_BASE,
    STUB_OFFSET,
    STUB_SIZE,
    WRITER,
    build_probe,
)
from tools.build_save_state_runtime_probe import encode_thumb_bl


ROOT = Path(__file__).resolve().parents[1]


class NumericWriterTraceProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_call_sites_are_complete_checked_writer_calls(self):
        expected = set()
        for address in range(ROM_BASE, ROM_BASE + len(self.base) - 3, 2):
            try:
                encoded = encode_thumb_bl(address, WRITER)
            except ValueError:
                continue
            if self.base[address - ROM_BASE:address - ROM_BASE + 4] == encoded:
                expected.add(address)
        self.assertEqual(set(CALL_SITES), expected)
        self.assertGreater(len(CALL_SITES), 90)

    def test_probe_changes_only_writer_calls_and_zero_filled_stub(self):
        output = build_probe(self.base)
        differences = {
            index for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        allowed = set(range(STUB_OFFSET, STUB_OFFSET + STUB_SIZE))
        for address in CALL_SITES:
            allowed.update(range(address - ROM_BASE, address - ROM_BASE + 4))
        self.assertTrue(differences)
        self.assertLessEqual(differences, allowed)


if __name__ == "__main__":
    unittest.main()
