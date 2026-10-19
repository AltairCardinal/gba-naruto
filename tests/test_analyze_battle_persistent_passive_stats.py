import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattlePersistentPassiveStatAnalysisTest(unittest.TestCase):
    def test_binds_both_ordered_passes_to_the_character_stat_loader(self):
        from tools.analyze_battle_persistent_passive_stats import (
            build_persistent_passive_stat_manifest,
        )

        result = build_persistent_passive_stat_manifest(
            ROOT / "rom/base.gba"
        )

        self.assertEqual(
            result["identity"],
            "battle_persistent_passive_stat_bindings",
        )
        self.assertEqual(
            result["function"],
            {
                "range": "0x0806D964..0x0806DDA3",
                "sha256":
                    "9cbcf9e7a568f31c837e2aa7acdb3ed265ccde914044746dd99eaa498a9c2a2c",
            },
        )
        self.assertEqual(
            result["secondary_slots"],
            {
                "count": 24,
                "stride": 4,
                "passive_id_offset": "unit+0x50",
                "stored_level_offset": "unit+0x51",
                "inactive_passive_id": 0,
                "inactive_stored_levels": [0, 255],
            },
        )
        self.assertEqual(
            result["definition_table"],
            {
                "address": "0x085459C8",
                "record_size": 12,
                "target_type_offset": 0,
                "base_a_offset": 2,
                "per_level_a_offset": 6,
            },
        )
        self.assertEqual(
            result["value_formula"],
            "base_a + per_level_a * (stored_level - 1)",
        )
        self.assertEqual(
            result["pass_order"],
            ["percentage_and_reduction", "flat_addition"],
        )

        percentage = result["passes"]["percentage_and_reduction"]
        self.assertEqual(
            percentage["range"],
            "0x0806DAE6..0x0806DC19",
        )
        self.assertEqual(
            percentage["targets"],
            {
                "2": {
                    "field": "max_hp",
                    "operation": "increase_percent",
                    "cap": 999,
                },
                "6": {
                    "field": "defense",
                    "operation": "increase_percent",
                    "cap": 99,
                },
                "8": {
                    "field": "agility",
                    "operation": "increase_percent",
                    "cap": 99,
                },
                "11": {
                    "field": "hand_seals",
                    "operation": "reduce_percent",
                    "minimum": 1,
                },
            },
        )

        flat = result["passes"]["flat_addition"]
        self.assertEqual(
            flat["jump_table_entries"],
            [
                "0x0806DCA4",
                "0x0806DD86",
                "0x0806DCC8",
                "0x0806DCE8",
                "0x0806DD08",
                "0x0806DD86",
                "0x0806DD28",
                "0x0806DD86",
                "0x0806DD48",
                "0x0806DD68",
            ],
        )
        self.assertEqual(flat["targets"]["1"]["field"], "max_hp")
        self.assertEqual(flat["targets"]["1"]["cap"], 999)
        self.assertEqual(flat["targets"]["2"], {"operation": "no_op"})
        self.assertEqual(
            flat["targets"]["3"],
            {
                "field": "chakra_capacity",
                "operation": "add",
                "cap": 9,
            },
        )
        self.assertEqual(flat["targets"]["4"]["field"], "attack")
        self.assertEqual(flat["targets"]["5"]["field"], "defense")
        self.assertEqual(flat["targets"]["6"], {"operation": "no_op"})
        self.assertEqual(flat["targets"]["7"]["field"], "agility")
        self.assertEqual(flat["targets"]["8"], {"operation": "no_op"})
        self.assertEqual(flat["targets"]["9"]["field"], "movement")
        self.assertEqual(
            flat["targets"]["10"],
            {
                "field": "ninja_tool_capacity",
                "operation": "add",
                "cap": 99,
            },
        )

    def test_rom_mismatch_fails_closed(self):
        from tools.analyze_battle_persistent_passive_stats import (
            build_persistent_passive_stat_manifest,
        )

        source = bytearray((ROOT / "rom/base.gba").read_bytes())
        source[0x6DB2A] ^= 0x01
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "tampered.gba"
            target.write_bytes(source)
            with self.assertRaisesRegex(
                ValueError,
                "original ROM SHA-256 mismatch",
            ):
                build_persistent_passive_stat_manifest(target)


if __name__ == "__main__":
    unittest.main()
