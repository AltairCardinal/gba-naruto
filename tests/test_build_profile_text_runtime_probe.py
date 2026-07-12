#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_profile_text_runtime_probe import (
    HOOK,
    PROFILE_TABLE,
    ROM_BASE,
    STUB_OFFSET,
    STUB_SIZE,
    build_profile_probe,
)


ROOT = Path(__file__).resolve().parents[1]


class ProfileTextRuntimeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()
        cls.spec = ROOT / "sequel/content/story-b/scenario-39-relocation.json"

    def test_control_changes_only_existing_trace_probe_plus_profile_hook(self):
        output = build_profile_probe(self.base, self.spec)
        self.assertNotEqual(output[HOOK - ROM_BASE:HOOK - ROM_BASE + 4], self.base[HOOK - ROM_BASE:HOOK - ROM_BASE + 4])
        self.assertNotEqual(output[STUB_OFFSET:STUB_OFFSET + STUB_SIZE], b"\x00" * STUB_SIZE)
        self.assertEqual(output[PROFILE_TABLE + 4:PROFILE_TABLE + 8], self.base[PROFILE_TABLE + 4:PROFILE_TABLE + 8])

    def test_variant_changes_only_runtime_naruto_pointer_to_valid_character_seven_text(self):
        control = build_profile_probe(self.base, self.spec)
        changed = build_profile_probe(self.base, self.spec, replacement_id=7)
        target = PROFILE_TABLE
        differences = [index for index, pair in enumerate(zip(control, changed)) if pair[0] != pair[1]]
        self.assertTrue(differences)
        self.assertLessEqual(set(differences), set(range(target, target + 4)))
        self.assertEqual(changed[target:target + 4], self.base[PROFILE_TABLE + 7 * 4:PROFILE_TABLE + 8 * 4])


if __name__ == "__main__":
    unittest.main()
