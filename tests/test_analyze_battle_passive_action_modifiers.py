import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattlePassiveActionModifierAnalysisTest(unittest.TestCase):
    def test_binds_both_passes_and_both_action_initializers(self):
        from tools.analyze_battle_passive_action_modifiers import (
            build_passive_action_modifier_manifest,
        )

        result = build_passive_action_modifier_manifest(
            ROOT / "rom/base.gba"
        )

        self.assertEqual(
            result["identity"],
            "battle_passive_action_modifier_bindings",
        )
        self.assertEqual(
            result["function"]["range"],
            "0x0806D6B8..0x0806D855",
        )
        self.assertEqual(
            result["initializers"],
            {
                "active_action": {
                    "function": "0x0806D85C",
                    "passive_modifier_callsite": "0x0806D906",
                    "order":
                        "action_level_growth_then_passive_modifiers",
                },
                "ninja_tool": {
                    "function": "0x0806D910",
                    "passive_modifier_callsite": "0x0806D954",
                    "order": "template_then_passive_modifiers",
                },
            },
        )
        self.assertEqual(
            result["runtime_action_fields"],
            {
                "header_0_1": "+0 u16",
                "effect_code": "+2 low 6 bits",
                "potency": "+4 u8",
                "success_rate_percent": "+6 u8",
            },
        )
        self.assertEqual(
            result["pass_order"],
            ["percentage", "flat_addition"],
        )

        percentage = result["passes"]["percentage"]
        self.assertEqual(
            percentage["targets"],
            {
                "14": {
                    "field": "potency",
                    "operation": "increase_percent",
                    "predicate":
                        "(header_0_1 == 0x0102 and "
                        "effect_code != 0x21) or effect_code == 0x0A",
                    "cap": 99,
                },
                "16": {
                    "field": "potency",
                    "operation": "increase_percent",
                    "predicate": "header_0_1 == 0x0101",
                    "cap": 99,
                },
            },
        )

        flat = result["passes"]["flat_addition"]
        self.assertEqual(
            flat["jump_table_entries"],
            [
                "0x0806D7D4",
                "0x0806D846",
                "0x0806D7F2",
                "0x0806D846",
                "0x0806D7FC",
                "0x0806D820",
                "0x0806D832",
            ],
        )
        self.assertEqual(
            flat["targets"]["13"],
            {
                "field": "potency",
                "operation": "add",
                "predicate":
                    "(header_0_1 == 0x0102 and "
                    "effect_code != 0x21) or effect_code == 0x0A",
                "cap": 99,
            },
        )
        self.assertEqual(flat["targets"]["14"], {"operation": "no_op"})
        self.assertEqual(
            flat["targets"]["15"]["predicate"],
            "header_0_1 == 0x0101",
        )
        self.assertEqual(flat["targets"]["16"], {"operation": "no_op"})
        self.assertEqual(
            flat["targets"]["17"]["predicate"],
            "header_0_1 == 0x0105",
        )
        self.assertEqual(
            flat["targets"]["18"],
            {
                "field": "potency",
                "operation": "add",
                "predicate": "effect_code == 0x1A",
                "storage": "u8",
                "explicit_cap": None,
            },
        )
        self.assertEqual(
            flat["targets"]["19"],
            {
                "field": "success_rate_percent",
                "operation": "add",
                "predicate": "all_runtime_actions",
                "storage": "u8",
                "comparison_cap_before_store": 999,
            },
        )

    def test_rom_mismatch_fails_closed(self):
        from tools.analyze_battle_passive_action_modifiers import (
            build_passive_action_modifier_manifest,
        )

        source = bytearray((ROOT / "rom/base.gba").read_bytes())
        source[0x6D7E4] ^= 0x01
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "tampered.gba"
            target.write_bytes(source)
            with self.assertRaisesRegex(
                ValueError,
                "original ROM SHA-256 mismatch",
            ):
                build_passive_action_modifier_manifest(target)


if __name__ == "__main__":
    unittest.main()
