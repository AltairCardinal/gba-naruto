import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattlePassiveCoverageAnalysisTest(unittest.TestCase):
    def test_all_45_rows_include_inline_and_query_consumers(self):
        from tools.analyze_battle_passive_coverage import (
            build_passive_coverage_manifest,
        )

        result = build_passive_coverage_manifest(ROOT)

        self.assertEqual(result["definition_count"], 45)
        self.assertEqual(result["rom_consumer_row_count"], 44)
        self.assertEqual(
            result["rom_direct_query_consumer_row_count"],
            17,
        )
        self.assertEqual(
            result["rom_inline_stat_consumer_row_count"],
            18,
        )
        self.assertEqual(
            result["rom_inline_action_modifier_consumer_row_count"],
            9,
        )
        self.assertEqual(result["rom_no_consumer_row_count"], 1)
        self.assertEqual(
            result["rom_consumer_target_types"],
            list(range(1, 0x21)),
        )
        self.assertEqual(
            result["rom_direct_query_consumer_target_types"],
            [0x0C] + list(range(0x14, 0x21)),
        )
        self.assertEqual(
            result["rom_inline_stat_consumer_target_types"],
            list(range(1, 12)),
        )
        self.assertEqual(
            result[
                "rom_inline_action_modifier_consumer_target_types"
            ],
            list(range(13, 20)),
        )
        self.assertEqual(len(result["rows"]), 45)

        no_consumer = [
            row["passive_id"]
            for row in result["rows"]
            if row["evidence_status"] == "no_rom_consumer"
        ]
        self.assertEqual(no_consumer, [0])
        self.assertNotIn(1, no_consumer)
        self.assertNotIn(14, no_consumer)
        self.assertNotIn(35, no_consumer)

    def test_butano_status_distinguishes_gameplay_and_unproven_rows(self):
        from tools.analyze_battle_passive_coverage import (
            build_passive_coverage_manifest,
        )

        rows = {
            row["passive_id"]: row
            for row in build_passive_coverage_manifest(ROOT)["rows"]
        }

        self.assertEqual(rows[9]["butano_status"], "implemented_gameplay")
        self.assertEqual(rows[1]["butano_status"], "implemented_gameplay")
        self.assertEqual(
            rows[1]["evidence_status"],
            "rom_inline_stat_consumer",
        )
        self.assertEqual(
            rows[1]["inline_consumers"],
            [
                {
                    "function": "0x0806D964",
                    "context":
                        "persistent_character_stat_recalculation",
                    "pass_order": "flat_addition",
                }
            ],
        )
        self.assertEqual(
            rows[10]["evidence_status"],
            "rom_inline_action_modifier_consumer",
        )
        self.assertEqual(
            rows[10]["inline_consumers"],
            [
                {
                    "function": "0x0806D6B8",
                    "context": "runtime_action_definition_modifier",
                    "pass_order": "flat_addition",
                }
            ],
        )
        self.assertEqual(rows[10]["butano_status"], "implemented_gameplay")
        self.assertEqual(
            rows[36]["inline_consumers"],
            [
                {
                    "function": "0x0806D6B8",
                    "context": "runtime_action_definition_modifier",
                    "pass_order": "percentage",
                }
            ],
        )
        self.assertEqual(rows[15]["butano_status"], "implemented_gameplay")
        self.assertEqual(rows[21]["butano_status"], "implemented_gameplay")
        self.assertEqual(rows[22]["butano_status"], "implemented_gameplay")
        self.assertEqual(rows[23]["butano_status"], "implemented_gameplay")
        self.assertEqual(rows[35]["butano_status"], "implemented_gameplay")
        self.assertEqual(
            rows[35]["rom_calls"],
            [
                {
                    "callsite": "0x0806E118",
                    "context": "side_start_trigger",
                }
            ],
        )
        self.assertEqual(rows[35]["referenced_by_unit_ids"], [12, 60])

    def test_summary_counts_all_direct_consumer_rows_as_gameplay(self):
        from tools.analyze_battle_passive_coverage import (
            build_passive_coverage_manifest,
        )

        summary = build_passive_coverage_manifest(ROOT)["butano_summary"]

        self.assertEqual(summary["implemented_gameplay_rows"], 44)
        self.assertEqual(summary["unimplemented_visual_rows"], 0)
        self.assertEqual(summary["no_rom_consumer_rows"], 1)
        self.assertEqual(summary["unimplemented_visual_target_types"], [])


if __name__ == "__main__":
    unittest.main()
