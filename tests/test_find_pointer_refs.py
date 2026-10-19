#!/usr/bin/env python3
"""Regression tests for ROM pointer reference scanning helpers."""

from __future__ import annotations

import unittest

from tools.find_pointer_refs import parse_target


class FindPointerRefsTests(unittest.TestCase):
    def test_parse_target_accepts_file_offsets_and_gba_addresses(self):
        self.assertEqual(parse_target("0x54507A"), 0x54507A)
        self.assertEqual(parse_target("0x0854507A"), 0x54507A)

    def test_parse_target_rejects_outside_rom_range(self):
        with self.assertRaises(ValueError):
            parse_target("0x02000000")


if __name__ == "__main__":
    unittest.main()
