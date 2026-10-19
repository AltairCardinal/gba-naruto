import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_action_reachability import (
    build_battle_action_reachability_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class BattleActionReachabilityAnalysisTest(unittest.TestCase):
    def test_classifies_all_action_identities_by_natural_source(self):
        manifest = build_battle_action_reachability_manifest(ROOT)

        self.assertEqual(manifest["action_count"], 87)
        self.assertEqual(
            [row["action_id"] for row in manifest["actions"]],
            list(range(87)),
        )
        by_id = {
            row["action_id"]: row for row in manifest["actions"]
        }

        self.assertEqual(
            by_id[23]["base_template"]["unlocked_unlearned_count"],
            1,
        )
        self.assertIn(
            "base_training",
            by_id[23]["natural_routes"],
        )
        self.assertEqual(
            by_id[62]["classification"],
            "formation_catalog",
        )
        self.assertEqual(
            by_id[62]["formation"]["catalog_accepted_records"],
            [
                {
                    "record_id": "g08_v0_r01",
                    "selector": 20,
                    "slot": 4,
                    "state": 3,
                },
                {
                    "record_id": "g08_v2_r03",
                    "selector": 20,
                    "slot": 4,
                    "state": 3,
                },
            ],
        )
        self.assertEqual(
            by_id[19]["classification"],
            "scenario_unlock_then_training",
        )
        self.assertIn(
            "scenario_31_variant_0_unlock_then_training",
            by_id[19]["natural_routes"],
        )
        self.assertEqual(
            by_id[19]["scenario_unlock"],
            {
                "battle_id": 31,
                "variant": 0,
                "character_id": 2,
                "action_id": 19,
                "state_after_unlock": 0,
                "requires_training": True,
            },
        )
        self.assertEqual(
            manifest["scenario_unlock_evidence"],
            {
                "function_range": "0x080899EC..0x08089AE0",
                "special_case_range": "0x08089A1A..0x08089A4A",
                "caller": "0x08089B7E",
                "chapter_state_address": "0x020311D4",
                "action_definition_table": "0x0854241C",
            },
        )
        self.assertEqual(
            [
                action_id
                for action_id in (10, 11, 13, 17, 18)
                if by_id[action_id]["classification"]
                == "combination_result"
            ],
            [10, 11, 13, 17, 18],
        )
        self.assertEqual(
            by_id[20]["classification"],
            "separate_resource_command_identity",
        )
        self.assertEqual(
            by_id[20]["effect_code"],
            0,
        )
        self.assertEqual(
            [
                action_id
                for action_id in (39, 40, 52)
                if by_id[action_id]["classification"]
                == "unreferenced_zero_template"
            ],
            [39, 40, 52],
        )
        self.assertEqual(
            by_id[0]["classification"],
            "sentinel",
        )
        self.assertEqual(by_id[0]["natural_routes"], [])
        self.assertEqual(
            manifest["unclassified_action_ids"],
            [],
        )

    def test_input_hash_mismatch_fails_closed(self):
        source = json.loads(
            (
                ROOT
                / "sequel/content/battle-config/action-identities.json"
            ).read_text(encoding="utf-8")
        )
        source["entries"][62]["display_name"] = "tampered"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = (
                root
                / "sequel/content/battle-config/action-identities.json"
            )
            target.parent.mkdir(parents=True)
            target.write_text(
                json.dumps(source, ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "action identities SHA-256 mismatch",
            ):
                build_battle_action_reachability_manifest(
                    ROOT,
                    input_overrides={"action_identities": target},
                )

    def test_original_rom_mismatch_fails_closed(self):
        source = bytearray((ROOT / "rom/base.gba").read_bytes())
        source[0x089A2A] ^= 0x01
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "tampered.gba"
            target.write_bytes(source)
            with self.assertRaisesRegex(
                ValueError,
                "original ROM SHA-256 mismatch",
            ):
                build_battle_action_reachability_manifest(
                    ROOT,
                    input_overrides={"original_rom": target},
                )


if __name__ == "__main__":
    unittest.main()
