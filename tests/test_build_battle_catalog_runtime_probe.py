#!/usr/bin/env python3
from __future__ import annotations

import struct
import unittest
from pathlib import Path

from tools.build_battle_catalog_runtime_probe import (
    ACTIVE_LIST_DISPLAY_ACTION_IDS,
    ACTIVE_LIST_NAME_COUNT,
    ACTIVE_LIST_NAME_TABLE,
    CURRENT_PASSIVE_ID,
    CURRENT_UNIT_ID,
    PASSIVE_TEXT_TABLES,
    ROM_BASE,
    UNIT_NAME_COUNT,
    UNIT_NAME_TABLE,
    UNIT_DEFINITION_TABLE,
    UNIT_DEFINITION_SIZE,
    UNIT_SECONDARY_SLOTS_OFFSET,
    build_probe,
)


ROOT = Path(__file__).resolve().parents[1]


class BattleCatalogRuntimeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_redirects_only_current_unit_name_pointer(self):
        output = build_probe(self.base, unit_name_id=62)
        target = UNIT_NAME_TABLE - ROM_BASE + CURRENT_UNIT_ID * 4
        source = UNIT_NAME_TABLE - ROM_BASE + 62 * 4
        self.assertEqual(output[target : target + 4], self.base[source : source + 4])
        differences = {
            index for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        self.assertLessEqual(differences, set(range(target, target + 4)))

    def test_redirects_all_current_passive_text_pointers(self):
        output = build_probe(self.base, passive_text_id=44)
        allowed = set()
        for table in PASSIVE_TEXT_TABLES:
            target = table - ROM_BASE + CURRENT_PASSIVE_ID * 4
            source = table - ROM_BASE + 44 * 4
            self.assertEqual(output[target : target + 4], self.base[source : source + 4])
            allowed.update(range(target, target + 4))
        unit_slot = (
            UNIT_DEFINITION_TABLE - ROM_BASE
            + CURRENT_UNIT_ID * UNIT_DEFINITION_SIZE
            + UNIT_SECONDARY_SLOTS_OFFSET
        )
        self.assertEqual(output[unit_slot], 44)
        allowed.add(unit_slot)
        differences = {
            index for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        self.assertLessEqual(differences, allowed)

    def test_redirects_visible_active_list_names_without_changing_action_ids(self):
        output = build_probe(self.base, active_list_name_id=86)
        source = ACTIVE_LIST_NAME_TABLE - ROM_BASE + 86 * 4
        allowed = set()
        for action_id in ACTIVE_LIST_DISPLAY_ACTION_IDS:
            target = ACTIVE_LIST_NAME_TABLE - ROM_BASE + action_id * 4
            self.assertEqual(
                output[target : target + 4], self.base[source : source + 4]
            )
            allowed.update(range(target, target + 4))
        differences = {
            index for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        self.assertLessEqual(differences, allowed)

    def test_rejects_range_mode_conflict_and_invalid_pointer(self):
        with self.assertRaisesRegex(ValueError, "unit name ID"):
            build_probe(self.base, unit_name_id=UNIT_NAME_COUNT)
        with self.assertRaisesRegex(ValueError, "passive text ID"):
            build_probe(self.base, passive_text_id=45)
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            build_probe(self.base, unit_name_id=1, passive_text_id=1)
        with self.assertRaisesRegex(ValueError, "active list name ID"):
            build_probe(self.base, active_list_name_id=ACTIVE_LIST_NAME_COUNT)
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            build_probe(self.base, unit_name_id=1, active_list_name_id=1)

        tampered = bytearray(self.base)
        pointer_offset = UNIT_NAME_TABLE - ROM_BASE + 62 * 4
        struct.pack_into("<I", tampered, pointer_offset, 0xDEADBEEF)
        with self.assertRaisesRegex(ValueError, "ROM pointer"):
            build_probe(bytes(tampered), unit_name_id=62, verify_sha1=False)


if __name__ == "__main__":
    unittest.main()
