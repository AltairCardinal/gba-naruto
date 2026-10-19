import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleEffectHandlerAnalysisTest(unittest.TestCase):
    def test_handler_range_and_specialized_families_are_rom_bound(self):
        from tools.analyze_battle_effect_handlers import (
            build_effect_handler_manifest,
        )

        result = build_effect_handler_manifest(ROOT / "rom/base.gba")
        self.assertEqual(result["handler_range"]["start"], "0x08077040")
        self.assertEqual(
            result["handler_range"]["sha256"],
            "2e80b66092e3dd94ecdc20afdfb93e9cd41b6e549ab04e92c33c1cf6fc2282c0",
        )
        self.assertEqual(
            result["families"]["summon"],
            {
                "0x02": "copy_source_and_link",
                "0x07": "identity_variant_copy_and_link",
                "0x17": "paired_clone_graph",
            },
        )
        self.assertEqual(
            result["families"]["battlefield_object"],
            {
                "0x0C": "type_2",
                "0x18": "type_1_with_source",
            },
        )
        self.assertEqual(
            result["families"]["resource"],
            {
                "0x06": "max_hp_percent_heal",
                "0x11": "status_2_plus_hp_and_chakra_restore",
                "0x1A": "max_hp_percent_heal",
                "0x1C": "chakra_add_capped",
                "0x1D": "chakra_subtract_floored",
            },
        )

    def test_specialized_helpers_and_runtime_contract_are_closed(self):
        from tools.analyze_battle_effect_handlers import (
            build_effect_handler_manifest,
        )

        result = build_effect_handler_manifest(ROOT / "rom/base.gba")
        self.assertEqual(
            result["helper_calls"],
            {
                "single_summon": "0x0806ADD0",
                "variant_summon": "0x0806AEE8",
                "paired_summon": "0x0806B030",
                "battlefield_object_allocate": "0x08081024",
                "damage_resolve": "0x08076A30",
                "reaction_state": "0x0806A8C0",
            },
        )
        self.assertIn(
            "Action cost is committed once before a specialized handler mutates its targets.",
            result["implementation_contract"],
        )
        self.assertIn(
            "Battlefield objects live in the encounter session used by condition evaluation.",
            result["implementation_contract"],
        )


if __name__ == "__main__":
    unittest.main()
