import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_resource_command_rules import (
    build_resource_command_rule_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class BattleResourceCommandRuleTest(unittest.TestCase):
    def test_static_chakra_exchange_and_cross_sample_rest_rules(self):
        result = build_resource_command_rule_manifest(
            ROOT / "rom" / "base.gba",
            ROOT / "notes" / "battle-resource-transaction-bindings-20260723.json",
            ROOT / "artifacts" / "runtime-checkpoints",
        )

        self.assertEqual(
            result["chakra_exchange"],
            {
                "cost_field": "unit+0x0A",
                "cost_semantic": "hand_seals",
                "hp_guard": "current_hp > cost",
                "per_point": True,
                "minimum_remaining_hp": 1,
                "current_chakra_cap_field": "unit+0x08",
                "preview_is_rolled_back_before_confirmation": True,
            },
        )
        self.assertEqual(
            result["rest"]["formula"],
            "floor(max_hp / 5)",
        )
        self.assertEqual(result["rest"]["max_hp_field"], "unit+0x0E")
        self.assertEqual(result["rest"]["commit_behavior"], "complete_unit_action")
        self.assertEqual(
            result["rest"]["samples"],
            [
                {
                    "character_id": 2,
                    "level": 3,
                    "max_hp": 89,
                    "hp_before": 24,
                    "hp_after": 41,
                    "expected_restore": 17,
                },
                {
                    "character_id": 1,
                    "level": 6,
                    "max_hp": 152,
                    "hp_before": 17,
                    "hp_after": 47,
                    "expected_restore": 30,
                },
            ],
        )
        self.assertEqual(
            result["inputs"]["transaction_bindings"]["sha256"],
            "6e6bdde545219997980eb6fe0a6ed798813457f8efa50cabe8bf15aafc77c1a5",
        )
        self.assertEqual(
            result["inputs"]["checkpoints"]["battle_13_entry"]["sha256"],
            "af1c2f79643bbe45bf4f179ea36e4b951bdaa4de70d54aa754c11085c30f8e03",
        )
        self.assertEqual(
            result["inputs"]["checkpoints"]["battle_15_entry"]["sha256"],
            "9e74b086029b0873dfae1c6237e1ebf5fbccc4a01b493cdff35981b0bb6c2cc8",
        )
        self.assertEqual(
            result["inputs"]["checkpoints"]["battle_15_rest_before"]["sha256"],
            "ef761db1ff4ba3d985150d9ec7d1e75d49e35717d3fe76acaf995ea1673922b8",
        )

    def test_tampered_transaction_bindings_fail_closed(self):
        bindings = json.loads(
            (
                ROOT
                / "notes"
                / "battle-resource-transaction-bindings-20260723.json"
            ).read_text(encoding="utf-8")
        )
        bindings["transitions"][0]["character_id"] = 2
        with tempfile.TemporaryDirectory() as directory:
            tampered = Path(directory) / "bindings.json"
            tampered.write_text(
                json.dumps(bindings, ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "transaction bindings SHA-256 mismatch",
            ):
                build_resource_command_rule_manifest(
                    ROOT / "rom" / "base.gba",
                    tampered,
                    ROOT / "artifacts" / "runtime-checkpoints",
                )

    def test_formula_is_not_overclaimed(self):
        result = build_resource_command_rule_manifest(
            ROOT / "rom" / "base.gba",
            ROOT / "notes" / "battle-resource-transaction-bindings-20260723.json",
            ROOT / "artifacts" / "runtime-checkpoints",
        )

        self.assertIn("passive modifiers", result["boundary"])
        self.assertIn("status modifiers", result["boundary"])


if __name__ == "__main__":
    unittest.main()
