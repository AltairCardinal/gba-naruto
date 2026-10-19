import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattlePassiveQueryAnalysisTest(unittest.TestCase):
    def test_query_function_and_progression_table_are_hash_bound(self):
        from tools.analyze_battle_passive_query import (
            build_passive_query_manifest,
        )

        result = build_passive_query_manifest(ROOT / "rom/base.gba")

        self.assertEqual(
            result["query_function"],
            {
                "start": "0x0806DDA4",
                "end_inclusive": "0x0806DE15",
                "size": 114,
                "sha256": (
                    "1a129adf0d5d492f5cbd8531c9bd2b6e49934b56879b2163"
                    "ee9971f6ccc04681"
                ),
            },
        )
        self.assertEqual(
            result["progression_table"],
            {
                "address": "0x085459C8",
                "entry_count": 45,
                "entry_size": 12,
                "sha256": (
                    "4746ef6114975d356d893267d1bd78e5e7c49a0cc705b8c7"
                    "21acaf7d1664aafd"
                ),
            },
        )

    def test_query_contract_matches_the_24_slot_rom_loop(self):
        from tools.analyze_battle_passive_query import (
            build_passive_query_manifest,
        )

        result = build_passive_query_manifest(ROOT / "rom/base.gba")

        self.assertEqual(
            result["slot_layout"],
            {
                "count": 24,
                "base_offset": "0x50",
                "stride": 4,
                "passive_id_offset": 0,
                "stored_level_offset": 1,
            },
        )
        self.assertEqual(
            result["query_contract"],
            {
                "inactive_passive_ids": [0],
                "inactive_stored_levels": [0, 255],
                "selection": "first_active_slot_with_matching_target_type",
                "return_value": "slot_index_or_0xFF",
                "value_a": "base_a + per_level_a * (stored_level - 1)",
                "value_b": "base_b + per_level_b * (stored_level - 1)",
            },
        )

    def test_all_45_progression_records_are_extracted_without_inference(self):
        from tools.analyze_battle_passive_query import (
            build_passive_query_manifest,
        )

        records = build_passive_query_manifest(
            ROOT / "rom/base.gba"
        )["records"]

        self.assertEqual(len(records), 45)
        self.assertEqual(
            records[9],
            {
                "passive_id": 9,
                "target_type": 0x0C,
                "reserved1": 0,
                "base_a": 10,
                "base_b": 0,
                "per_level_a": 5,
                "per_level_b": 0,
                "reserved_a": 0,
                "raw_hex": "0c000a000000050000000000",
            },
        )
        self.assertEqual(records[20]["target_type"], 0x19)
        self.assertEqual(records[20]["base_a"], 20)
        self.assertEqual(records[20]["per_level_a"], 5)


if __name__ == "__main__":
    unittest.main()
