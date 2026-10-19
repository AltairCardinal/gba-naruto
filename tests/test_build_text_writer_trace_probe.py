#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_text_writer_trace_probe import (
    ROM_BASE,
    STUB_OFFSET,
    STUB_SIZE,
    build_probe,
    find_call_sites,
)


ROOT = Path(__file__).resolve().parents[1]


class TextWriterTraceProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_discovers_expected_number_of_checked_calls(self):
        call_sites = find_call_sites(self.base)
        self.assertEqual(len(call_sites), 256)
        self.assertEqual(call_sites[0], 0x0806EDB0)
        self.assertEqual(call_sites[-1], 0x08098310)

    def test_probe_changes_only_discovered_calls_and_zero_filled_stub(self):
        output = build_probe(self.base)
        differences = {
            index for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        allowed = set(range(STUB_OFFSET, STUB_OFFSET + STUB_SIZE))
        for address in find_call_sites(self.base):
            allowed.update(range(address - ROM_BASE, address - ROM_BASE + 4))
        self.assertTrue(differences)
        self.assertLessEqual(differences, allowed)


if __name__ == "__main__":
    unittest.main()
