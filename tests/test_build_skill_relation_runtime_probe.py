#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_skill_relation_runtime_probe import (
    HOOK,
    PARENT_FIELD,
    ROM_BASE,
    STUB_OFFSET,
    STUB_SIZE,
    build_probe,
)


ROOT = Path(__file__).resolve().parents[1]


class SkillRelationRuntimeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_control_changes_only_call_site_and_stub(self):
        output = build_probe(self.base)
        differences = {
            index for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        allowed = set(range(HOOK - ROM_BASE, HOOK - ROM_BASE + 4))
        allowed.update(range(STUB_OFFSET, STUB_OFFSET + STUB_SIZE))
        self.assertTrue(differences)
        self.assertLessEqual(differences, allowed)

    def test_variant_changes_only_row_three_parent_field(self):
        control = build_probe(self.base)
        changed = build_probe(self.base, parent_skill_id=0)
        differences = [
            index for index, pair in enumerate(zip(control, changed))
            if pair[0] != pair[1]
        ]
        self.assertEqual(differences, [PARENT_FIELD])
        self.assertEqual(changed[PARENT_FIELD], 0)

    def test_rejects_parent_outside_u8(self):
        with self.assertRaisesRegex(ValueError, "u8"):
            build_probe(self.base, parent_skill_id=256)


if __name__ == "__main__":
    unittest.main()
