#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import unittest

from tools.build_character_growth_probe import (
    CHAR1_TEMPLATE_02_GROWTH,
    LEVEL_MINUS_ONE_IMMEDIATE,
    build_probe,
)


class CharacterGrowthProbeTests(unittest.TestCase):
    def fixture(self) -> bytes:
        rom = bytearray(CHAR1_TEMPLATE_02_GROWTH + 2)
        rom[LEVEL_MINUS_ONE_IMMEDIATE : LEVEL_MINUS_ONE_IMMEDIATE + 2] = bytes.fromhex("0138")
        rom[CHAR1_TEMPLATE_02_GROWTH : CHAR1_TEMPLATE_02_GROWTH + 2] = (100).to_bytes(2, "little")
        return bytes(rom)

    def test_builds_two_factor_probe_with_only_expected_changes(self):
        from tools import build_character_growth_probe as module

        base = self.fixture()
        old_sha = module.BASE_SHA1
        module.BASE_SHA1 = hashlib.sha1(base).hexdigest()
        try:
            control = build_probe(base, None)
            changed = build_probe(base, 200)
        finally:
            module.BASE_SHA1 = old_sha
        control_diffs = [i for i, (a, b) in enumerate(zip(base, control)) if a != b]
        changed_vs_control = [i for i, (a, b) in enumerate(zip(control, changed)) if a != b]
        self.assertEqual([LEVEL_MINUS_ONE_IMMEDIATE], control_diffs)
        self.assertEqual([CHAR1_TEMPLATE_02_GROWTH], changed_vs_control)
        self.assertEqual(bytes.fromhex("0038"), control[LEVEL_MINUS_ONE_IMMEDIATE:LEVEL_MINUS_ONE_IMMEDIATE + 2])
        self.assertEqual((200).to_bytes(2, "little"), changed[CHAR1_TEMPLATE_02_GROWTH:CHAR1_TEMPLATE_02_GROWTH + 2])

    def test_rejects_wrong_base_hash(self):
        with self.assertRaisesRegex(ValueError, "SHA-1"):
            build_probe(self.fixture(), None)


if __name__ == "__main__":
    unittest.main()
