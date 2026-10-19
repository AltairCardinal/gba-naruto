import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleRangeShapeAnalysisTest(unittest.TestCase):
    def test_area_builder_is_hash_bound_and_decodes_both_shapes(self):
        from tools.analyze_battle_range_shape import build_range_shape_manifest

        result = build_range_shape_manifest(ROOT / "rom/base.gba")
        self.assertEqual(result["area_builder"]["start"], "0x0806A4AC")
        self.assertEqual(
            result["area_builder"]["sha256"],
            "01c73a6dc0b944ee7d4574cd3e3e6ea0bde47c0e886d8b448b84ca81fa63c874",
        )
        self.assertEqual(
            result["area_shape_encoding"],
            {
                "size": "low_7_bits_including_center",
                "high_bit_0": "manhattan_diamond",
                "high_bit_1": "four_cardinal_axes",
                "zero_size": "center_only_for_implicit_or_special_actions",
            },
        )
        self.assertEqual(
            result["examples"],
            {
                "0x01": ["center"],
                "0x02": ["center", "four_cardinal_neighbors"],
                "0x83": ["center", "four_cardinal_axes_through_distance_2"],
            },
        )

    def test_area_builder_reuses_target_policy_for_every_covered_tile(self):
        from tools.analyze_battle_range_shape import build_range_shape_manifest

        result = build_range_shape_manifest(ROOT / "rom/base.gba")
        self.assertEqual(result["target_policy_function"], "0x0806A2F4")
        self.assertEqual(
            result["target_policy_calls"],
            ["0x0806A5D2", "0x0806A658", "0x0806A740"],
        )
        self.assertEqual(
            result["implementation_contract"],
            [
                "Decode area size independently from maximum selection distance.",
                "Collect every active unit on covered cells that passes the same target policy.",
                "Preserve unit-slot scan order when constructing the target set.",
                "Charge action cost once and resolve one queued effect event per collected target.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
