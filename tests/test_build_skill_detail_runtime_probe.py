#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_skill_detail_runtime_probe import (
    HOOK,
    FORCE_BRANCH_ID_LOAD,
    FORCE_HIGH_TEXT_ID_LOADS,
    FORCE_ID_LOAD,
    FORCE_LOW_TEXT_ID_LOADS,
    LOW_DETAIL_DESCRIPTION_TABLE,
    LOW_DETAIL_NAME_TABLE,
    PASSIVE_DETAIL_DESCRIPTION_TABLE,
    PASSIVE_DETAIL_NAME_TABLE,
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

    def test_forced_detail_changes_checked_numeric_name_and_description_loads(self):
        control = build_probe(self.base)
        forced = build_probe(self.base, force_skill_id=2)
        differences = {
            index for index, pair in enumerate(zip(control, forced))
            if pair[0] != pair[1]
        }
        allowed = set(range(FORCE_ID_LOAD - ROM_BASE, FORCE_ID_LOAD - ROM_BASE + 2))
        allowed.update(range(FORCE_BRANCH_ID_LOAD - ROM_BASE, FORCE_BRANCH_ID_LOAD - ROM_BASE + 2))
        for address in FORCE_HIGH_TEXT_ID_LOADS:
            allowed.update(range(address - ROM_BASE, address - ROM_BASE + 2))
        self.assertLessEqual(differences, allowed)
        self.assertEqual(len(FORCE_HIGH_TEXT_ID_LOADS), 2)
        self.assertEqual(
            forced[FORCE_ID_LOAD - ROM_BASE : FORCE_ID_LOAD - ROM_BASE + 2],
            bytes.fromhex("8222"),
        )
        self.assertEqual(
            forced[FORCE_BRANCH_ID_LOAD - ROM_BASE : FORCE_BRANCH_ID_LOAD - ROM_BASE + 2],
            bytes.fromhex("8221"),
        )
        for address in FORCE_HIGH_TEXT_ID_LOADS:
            self.assertEqual(
                forced[address - ROM_BASE : address - ROM_BASE + 2],
                bytes.fromhex("8220"),
            )

    def test_forced_effect_uses_low_action_id_for_all_detail_text_loads(self):
        forced = build_probe(self.base, force_effect_id=2)
        self.assertEqual(
            forced[FORCE_ID_LOAD - ROM_BASE : FORCE_ID_LOAD - ROM_BASE + 2],
            bytes.fromhex("0222"),
        )
        self.assertEqual(
            forced[FORCE_BRANCH_ID_LOAD - ROM_BASE : FORCE_BRANCH_ID_LOAD - ROM_BASE + 2],
            bytes.fromhex("0221"),
        )
        for address in FORCE_LOW_TEXT_ID_LOADS:
            self.assertEqual(
                forced[address - ROM_BASE : address - ROM_BASE + 2],
                bytes.fromhex("0220"),
            )

    def test_forced_action_changes_only_checked_text_loads(self):
        control = build_probe(self.base)
        forced = build_probe(self.base, force_action_id=86)
        differences = {
            index for index, pair in enumerate(zip(control, forced))
            if pair[0] != pair[1]
        }
        allowed = set()
        allowed.update(range(FORCE_BRANCH_ID_LOAD - ROM_BASE, FORCE_BRANCH_ID_LOAD - ROM_BASE + 2))
        for address in FORCE_LOW_TEXT_ID_LOADS:
            allowed.update(range(address - ROM_BASE, address - ROM_BASE + 2))
        self.assertLessEqual(differences, allowed)
        self.assertEqual(
            forced[FORCE_ID_LOAD - ROM_BASE : FORCE_ID_LOAD - ROM_BASE + 2],
            control[FORCE_ID_LOAD - ROM_BASE : FORCE_ID_LOAD - ROM_BASE + 2],
        )
        self.assertEqual(
            forced[FORCE_BRANCH_ID_LOAD - ROM_BASE : FORCE_BRANCH_ID_LOAD - ROM_BASE + 2],
            bytes.fromhex("5621"),
        )
        for address in FORCE_LOW_TEXT_ID_LOADS:
            self.assertEqual(
                forced[address - ROM_BASE : address - ROM_BASE + 2],
                bytes.fromhex("5620"),
            )

    def test_forced_action_text_redirect_keeps_a_known_display_action(self):
        control = build_probe(self.base)
        forced = build_probe(self.base, force_action_text_id=86)
        allowed = set()
        allowed.update(range(FORCE_BRANCH_ID_LOAD - ROM_BASE, FORCE_BRANCH_ID_LOAD - ROM_BASE + 2))
        for address in FORCE_LOW_TEXT_ID_LOADS:
            allowed.update(range(address - ROM_BASE, address - ROM_BASE + 2))
        for table in (LOW_DETAIL_NAME_TABLE, LOW_DETAIL_DESCRIPTION_TABLE):
            allowed.update(range(table - ROM_BASE + 4, table - ROM_BASE + 8))
        differences = {
            index for index, pair in enumerate(zip(control, forced))
            if pair[0] != pair[1]
        }
        self.assertLessEqual(differences, allowed)
        self.assertEqual(
            forced[FORCE_BRANCH_ID_LOAD - ROM_BASE : FORCE_BRANCH_ID_LOAD - ROM_BASE + 2],
            bytes.fromhex("0121"),
        )
        for table in (LOW_DETAIL_NAME_TABLE, LOW_DETAIL_DESCRIPTION_TABLE):
            destination = table - ROM_BASE + 4
            source = table - ROM_BASE + 86 * 4
            self.assertEqual(
                forced[destination : destination + 4],
                self.base[source : source + 4],
            )

    def test_forced_passive_redirects_checked_low_detail_text_pointers(self):
        control = build_probe(self.base)
        forced = build_probe(self.base, force_passive_id=44)
        allowed = set()
        allowed.update(range(FORCE_BRANCH_ID_LOAD - ROM_BASE, FORCE_BRANCH_ID_LOAD - ROM_BASE + 2))
        for address in FORCE_LOW_TEXT_ID_LOADS:
            allowed.update(range(address - ROM_BASE, address - ROM_BASE + 2))
        for table in (LOW_DETAIL_NAME_TABLE, LOW_DETAIL_DESCRIPTION_TABLE):
            allowed.update(range(table - ROM_BASE + 4, table - ROM_BASE + 8))
        differences = {
            index for index, pair in enumerate(zip(control, forced))
            if pair[0] != pair[1]
        }
        self.assertLessEqual(differences, allowed)
        self.assertEqual(
            forced[LOW_DETAIL_NAME_TABLE - ROM_BASE + 4 : LOW_DETAIL_NAME_TABLE - ROM_BASE + 8],
            self.base[PASSIVE_DETAIL_NAME_TABLE - ROM_BASE + 44 * 4 : PASSIVE_DETAIL_NAME_TABLE - ROM_BASE + 44 * 4 + 4],
        )
        self.assertEqual(
            forced[LOW_DETAIL_DESCRIPTION_TABLE - ROM_BASE + 4 : LOW_DETAIL_DESCRIPTION_TABLE - ROM_BASE + 8],
            self.base[PASSIVE_DETAIL_DESCRIPTION_TABLE - ROM_BASE + 44 * 4 : PASSIVE_DETAIL_DESCRIPTION_TABLE - ROM_BASE + 44 * 4 + 4],
        )

    def test_rejects_out_of_range_skill_or_byte(self):
        with self.assertRaisesRegex(ValueError, "skill ID"):
            build_probe(self.base, skill_id=94, byte_04=7)
        with self.assertRaisesRegex(ValueError, r"byte \+4"):
            build_probe(self.base, skill_id=2, byte_04=256)
        with self.assertRaisesRegex(ValueError, "forced skill ID"):
            build_probe(self.base, force_skill_id=94)
        with self.assertRaisesRegex(ValueError, "forced effect ID"):
            build_probe(self.base, force_effect_id=87)
        with self.assertRaisesRegex(ValueError, "forced action ID"):
            build_probe(self.base, force_action_id=87)
        with self.assertRaisesRegex(ValueError, "forced action text ID"):
            build_probe(self.base, force_action_text_id=87)
        with self.assertRaisesRegex(ValueError, "forced passive ID"):
            build_probe(self.base, force_passive_id=45)
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            build_probe(self.base, force_skill_id=1, force_effect_id=1)
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            build_probe(self.base, force_effect_id=1, force_action_id=1)
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            build_probe(self.base, force_action_id=1, force_passive_id=1)
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            build_probe(self.base, force_action_id=1, force_action_text_id=1)


if __name__ == "__main__":
    unittest.main()
