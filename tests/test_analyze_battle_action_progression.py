import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_action_progression import (
    build_battle_action_progression_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class BattleActionProgressionAnalysisTest(unittest.TestCase):
    def test_binds_slot_state_transitions_and_training_growth(self):
        manifest = build_battle_action_progression_manifest(
            ROOT, ROOT / "rom/base.gba"
        )

        self.assertEqual(
            manifest["state_model"],
            {
                "locked": 255,
                "unlocked_unlearned": 0,
                "learned_minimum": 1,
                "learned_maximum": 3,
            },
        )
        self.assertEqual(
            manifest["transitions"]["level_threshold"],
            "0xFF -> 0",
        )
        self.assertEqual(
            manifest["transitions"]["spend_training_point"],
            "0..2 -> 1..3",
        )
        self.assertEqual(
            manifest["training_allocation"],
            {
                "shared_training_point_field": "character_template+0xBA",
                "row_type_field": "training_row+4",
                "secondary_row_type": 4,
                "primary_state_base": "character_template+0x15",
                "secondary_state_base": "character_template+0x51",
                "slot_stride": 4,
                "primary_slot_count": 15,
                "secondary_slot_count": 24,
                "row_identity_field": "training_row+6",
                "row_slot_index_field": "training_row+7",
            },
        )
        self.assertEqual(
            manifest["transitions"]["training_point_write"],
            (
                "0x08093160 decrements template +0xBA once; "
                "row type 4 increments template +0x51+slot*4, "
                "all other trainable rows increment "
                "template +0x15+slot*4."
            ),
        )
        self.assertEqual(
            manifest["battle_catalog"]["accepted_states"],
            "1..254",
        )
        self.assertEqual(
            manifest["battle_catalog"]["rejected_states"],
            [0, 255],
        )
        self.assertEqual(
            manifest["growth"]["formula"],
            "base_byte + per_level_growth * (action_level - 1), stored as u8",
        )
        self.assertEqual(
            manifest["resolver_capable_actions_only_initially_zero"],
            [
                23,
                24,
                25,
                26,
                27,
                31,
                33,
                36,
                37,
                38,
                41,
                51,
                54,
                55,
                56,
                57,
                58,
                60,
                61,
                66,
            ],
        )
        self.assertEqual(
            manifest["evidence"]["training_allocation"]["sha256"],
            "81a9e46969e5844a003af593ae885e28c518ce343e376525b3d3a267f42dc6c2",
        )
        self.assertIn(
            "Spend one training point to raise a trainable secondary passive by one level, capped at three.",
            manifest["implementation_contract"],
        )

    def test_cli_shape_is_json_serializable(self):
        manifest = build_battle_action_progression_manifest(
            ROOT, ROOT / "rom/base.gba"
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"
            output.write_text(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["identity"],
                "battle_action_progression",
            )


if __name__ == "__main__":
    unittest.main()
