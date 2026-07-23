#!/usr/bin/env python3
from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from tools.extract_battle_content_catalog import extract_catalog


ROOT = Path(__file__).resolve().parents[1]


class BattleContentCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = extract_catalog(
            (ROOT / "rom/base.gba").read_bytes(),
            ROOT / "sequel/content/units/bank.json",
            ROOT / "sequel/content/skills/bank.json",
            ROOT / "sequel/content/battle-config/bank.json",
            ROOT / "sequel/content/levels/bank.json",
            ROOT / "sequel/content/battle-config/action-identities.json",
            ROOT / "sequel/content/units/unit-identities.json",
        )

    def test_closes_all_structural_catalog_counts(self):
        self.assertEqual(len(self.catalog["units"]), 63)
        self.assertEqual(len(self.catalog["active_actions"]), 87)
        self.assertEqual(len(self.catalog["passives"]), 45)
        self.assertEqual(len(self.catalog["ninja_tools"]), 94)
        self.assertEqual(
            self.catalog["active_action_numeric_templates"]["entry_count"], 87
        )

    def test_binds_each_active_action_to_the_same_index_numeric_template(self):
        action = self.catalog["active_actions"][5]
        self.assertEqual(action["action_id"], 5)
        self.assertEqual(action["numeric_template"]["effect_id"], 5)
        self.assertEqual(action["numeric_template"]["byte_04"], 10)
        self.assertEqual(action["numeric_template"]["byte_05"], 1)
        self.assertEqual(action["numeric_template"]["byte_06"], 98)

    def test_maps_unit_slots_to_action_and_passive_usage(self):
        unit = self.catalog["units"][1]
        self.assertEqual(unit["unit_id"], 1)
        self.assertEqual(unit["primary_action_ids"], [2, 3, 4, 5, 6, 7, 8, 9])
        self.assertEqual(unit["secondary_passive_ids"], list(range(1, 25)))
        self.assertIn(1, self.catalog["passives"][1]["referenced_by_unit_ids"])
        self.assertIn(1, self.catalog["active_actions"][2]["referenced_by_unit_ids"])

    def test_keeps_legacy_skills_bank_but_corrects_its_identity(self):
        tool = self.catalog["ninja_tools"][93]
        self.assertEqual(tool["action_id"], 93)
        self.assertEqual(tool["template_identity"], "ninja_tool_action_template")
        self.assertEqual(len(tool["template_raw_hex"]), 32)
        self.assertEqual(
            self.catalog["legacy_paths"]["skills_bank_identity"],
            "misnamed_ninja_tool_action_templates",
        )

    def test_preserves_raw_text_and_pointer_provenance(self):
        self.assertTrue(self.catalog["units"][1]["name"]["raw_hex"])
        self.assertTrue(self.catalog["active_actions"][86]["name"]["raw_hex"])
        self.assertTrue(self.catalog["active_actions"][86]["description"]["raw_hex"])
        self.assertTrue(self.catalog["passives"][44]["description"]["raw_hex"])
        self.assertTrue(self.catalog["ninja_tools"][93]["description"]["raw_hex"])

    def test_distinguishes_actions_with_and_without_description_text(self):
        no_description_ids = [
            action["action_id"]
            for action in self.catalog["active_actions"]
            if not action["description_available"]
        ]
        self.assertEqual(no_description_ids, [0, 10, 11, 13, 17, 18, 20, 39, 40, 52])
        self.assertNotIn(
            "standalone_detail_available", self.catalog["active_actions"][11]
        )
        self.assertTrue(self.catalog["active_actions"][11]["name"]["raw_hex"])
        self.assertIsNone(
            self.catalog["active_actions"][11]["description"]["pointer"]
        )

    def test_binds_checked_display_identity_without_replacing_rom_text(self):
        identities = [
            action["display_identity"] for action in self.catalog["active_actions"]
        ]
        self.assertEqual(len(identities), 87)
        self.assertEqual(identities[5]["display_name"], "忍者组合拳")
        self.assertEqual(identities[19]["display_name"], "狮子连弹")
        self.assertEqual(identities[67]["display_name"], "魔镜冰晶")
        self.assertEqual(identities[5]["confidence"], "runtime_visual_exact")
        self.assertEqual(
            identities[86]["confidence"], "runtime_visual_ambiguous"
        )
        self.assertEqual(
            identities[5]["name_raw_hex"],
            self.catalog["active_actions"][5]["name"]["raw_hex"],
        )

    def test_binds_all_unit_display_identities_to_templates_and_skill_slots(self):
        identities = [unit["display_identity"] for unit in self.catalog["units"]]
        self.assertEqual(len(identities), 63)
        self.assertEqual(identities[1]["display_name"], "漩涡鸣人")
        self.assertEqual(identities[2]["display_name"], "宇智波佐助")
        self.assertEqual(identities[29]["display_name"], "大蛇丸")
        self.assertEqual(identities[51]["display_name"], "御手洗红豆")
        self.assertEqual(identities[62]["display_name"], "岸本齐史")
        self.assertEqual(identities[22]["confidence"], "runtime_visual_ambiguous")
        self.assertEqual(
            identities[1]["name_raw_hex"], self.catalog["units"][1]["name"]["raw_hex"]
        )
        self.assertEqual(self.catalog["units"][1]["primary_action_ids"], [2, 3, 4, 5, 6, 7, 8, 9])

    def test_rejects_unit_identity_not_bound_to_rom_name_bytes(self):
        source = json.loads(
            (ROOT / "sequel/content/units/unit-identities.json").read_text(
                encoding="utf-8"
            )
        )
        source["entries"][1]["name_raw_hex"] = "00"
        with tempfile.TemporaryDirectory() as temp_dir:
            bad_path = Path(temp_dir) / "unit-identities.json"
            bad_path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unit identity.*ROM name bytes"):
                extract_catalog(
                    (ROOT / "rom/base.gba").read_bytes(),
                    ROOT / "sequel/content/units/bank.json",
                    ROOT / "sequel/content/skills/bank.json",
                    ROOT / "sequel/content/battle-config/bank.json",
                    ROOT / "sequel/content/levels/bank.json",
                    ROOT / "sequel/content/battle-config/action-identities.json",
                    bad_path,
                )

    def test_rejects_identity_overlay_not_bound_to_rom_name_bytes(self):
        source = json.loads(
            (ROOT / "sequel/content/battle-config/action-identities.json").read_text(
                encoding="utf-8"
            )
        )
        source["entries"][5]["name_raw_hex"] = "00"
        with tempfile.TemporaryDirectory() as temp_dir:
            bad_path = Path(temp_dir) / "identities.json"
            bad_path.write_text(
                json.dumps(source, ensure_ascii=False), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "identity.*ROM name bytes"):
                extract_catalog(
                    (ROOT / "rom/base.gba").read_bytes(),
                    ROOT / "sequel/content/units/bank.json",
                    ROOT / "sequel/content/skills/bank.json",
                    ROOT / "sequel/content/battle-config/bank.json",
                    ROOT / "sequel/content/levels/bank.json",
                    bad_path,
                )


if __name__ == "__main__":
    unittest.main()
