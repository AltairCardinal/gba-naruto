import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattlePassiveConsumerAnalysisTest(unittest.TestCase):
    def test_all_direct_query_calls_are_inventory_bound(self):
        from tools.analyze_battle_passive_consumers import (
            build_passive_consumer_manifest,
        )

        result = build_passive_consumer_manifest(ROOT / "rom/base.gba")

        self.assertEqual(result["query_address"], "0x0806DDA4")
        self.assertEqual(result["direct_call_count"], 15)
        self.assertEqual(
            [
                (row["callsite"], row["target_type"])
                for row in result["direct_calls"]
            ],
            [
                ("0x08069DD0", 0x1A),
                ("0x08069DF0", 0x1B),
                ("0x08069E0A", 0x1C),
                ("0x0806DFCC", 0x1D),
                ("0x0806E032", 0x1E),
                ("0x0806E0AC", 0x1F),
                ("0x0806E118", 0x20),
                ("0x0807613A", 0x0C),
                ("0x0807618C", 0x19),
                ("0x0807629C", 0x16),
                ("0x080762C0", 0x17),
                ("0x080762E4", 0x18),
                ("0x0807689E", 0x1F),
                ("0x08077C34", 0x14),
                ("0x080890C2", 0x15),
            ],
        )
        self.assertEqual(
            result["unconsumed_target_types"],
            list(range(1, 0x0C)) + list(range(0x0D, 0x14)),
        )

    def test_healing_and_experience_consumers_are_formula_bound(self):
        from tools.analyze_battle_passive_consumers import (
            build_passive_consumer_manifest,
        )

        consumers = build_passive_consumer_manifest(
            ROOT / "rom/base.gba"
        )["verified_consumers"]

        self.assertEqual(
            consumers["hp_restoration_bonus"],
            {
                "function": "0x08077C1C..0x08077C53",
                "sha256": (
                    "4e8b5f365ae591a3ae8580863dcdef4554bcee9e29f7379"
                    "c0c3d3b48efbdb507"
                ),
                "target_type": 0x14,
                "formula": "floor(max_hp / 5) + value_a",
            },
        )
        self.assertEqual(
            consumers["battle_experience_bonus"],
            {
                "function": "0x08089064..0x080890EF",
                "sha256": (
                    "03f7940fd622b6c1b97c54b710c97006c2dd2a804b5e276d"
                    "c8c916ed0f95900c"
                ),
                "target_type": 0x15,
                "formula": "battle_experience + floor(battle_experience * value_a / 100)",
            },
        )

    def test_terrain_consumers_are_bound_to_path_local_limits(self):
        from tools.analyze_battle_passive_consumers import (
            build_passive_consumer_manifest,
        )

        terrain = build_passive_consumer_manifest(
            ROOT / "rom/base.gba"
        )["verified_consumers"]["terrain_traversal_limits"]

        self.assertEqual(
            terrain,
            {
                "configuration_function": "0x08069DB8..0x08069E43",
                "configuration_sha256": (
                    "415a0f9cb1ab184f6b40d257a82905abb4201c7a2d872362"
                    "1624ecbf2bf786fb"
                ),
                "search_function": "0x080698B4..0x08069D1B",
                "search_sha256": (
                    "143a7223550ccd44c69615b39e76fc2f96e7ba4ec62671a"
                    "9ff6de62adaa844aa"
                ),
                "target_to_terrain_class": {
                    "26": 1,
                    "27": 7,
                    "28": 3,
                },
                "limit_formula": (
                    "base_a + per_level_a * (stored_level - 1)"
                ),
                "consumption": (
                    "one matching terrain tile per path step, including "
                    "the starting tile; recursive return restores the limit"
                ),
                "blocked_class": 15,
            },
        )


if __name__ == "__main__":
    unittest.main()
