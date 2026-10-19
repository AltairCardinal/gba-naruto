#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_skill_detail_runtime_probe import (
    HOOK,
    FORCE_ID_LOAD,
    ROM_BASE,
    SKILL_TABLE,
    STUB_OFFSET,
    STUB_SIZE,
    build_probe,
)


ROOT = Path(__file__).resolve().parents[1]


class SkillDetailRuntimeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_control_changes_only_detail_call_and_stub(self):
        output = build_probe(self.base)
        differences = {
            index for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        allowed = set(range(HOOK - ROM_BASE, HOOK - ROM_BASE + 4))
        allowed.update(range(STUB_OFFSET, STUB_OFFSET + STUB_SIZE))
        self.assertTrue(differences)
        self.assertLessEqual(differences, allowed)

    def test_variant_changes_only_selected_skill_byte_four(self):
        control = build_probe(self.base)
        changed = build_probe(self.base, skill_id=2, byte_04=7)
        target = SKILL_TABLE + 2 * 16 + 4
        differences = {
            index for index, pair in enumerate(zip(control, changed))
            if pair[0] != pair[1]
        }
        self.assertEqual(differences, {target})
        self.assertEqual(changed[target], 7)

    def test_forced_detail_changes_only_checked_action_id_load(self):
        control = build_probe(self.base)
        forced = build_probe(self.base, force_skill_id=2)
        differences = {
            index for index, pair in enumerate(zip(control, forced))
            if pair[0] != pair[1]
        }
        self.assertLessEqual(
            differences,
            set(range(FORCE_ID_LOAD - ROM_BASE, FORCE_ID_LOAD - ROM_BASE + 2)),
        )
        self.assertTrue(differences)

    def test_rejects_out_of_range_skill_or_byte(self):
        with self.assertRaisesRegex(ValueError, "skill ID"):
            build_probe(self.base, skill_id=94, byte_04=7)
        with self.assertRaisesRegex(ValueError, "byte \+4"):
            build_probe(self.base, skill_id=2, byte_04=256)
        with self.assertRaisesRegex(ValueError, "forced skill ID"):
            build_probe(self.base, force_skill_id=94)


if __name__ == "__main__":
    unittest.main()
