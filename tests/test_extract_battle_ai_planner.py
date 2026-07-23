#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.extract_battle_ai_planner import extract_ai_planner


ROOT = Path(__file__).resolve().parents[1]


class BattleAiPlannerExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = extract_ai_planner(ROOT / "rom/base.gba")

    def test_function_ranges_are_hash_gated(self):
        self.assertEqual(
            self.result["functions"],
            {
                "planner": {
                    "start": "0x080851F8",
                    "end": "0x080855FE",
                    "size": 1030,
                    "sha256": "d94ce211153c95b9d6065691179a6887b149c443be27311c8baaf679c8d85b95",
                },
                "tile_score": {
                    "start": "0x08085160",
                    "end": "0x080851F4",
                    "size": 148,
                    "sha256": "f8cfc39845d11a4bd2d845d5e56803e834632cbd1d091f3dd903e6906b03ad7a",
                },
                "grid_candidate": {
                    "start": "0x08085610",
                    "end": "0x080857B0",
                    "size": 416,
                    "sha256": "8fa4917189c73d871232fce933e7f0b0f3e3c93ad418f65274cfda35c70966af",
                },
            },
        )

    def test_planner_enumerates_candidates_and_keeps_a_strictly_better_score(self):
        decision = self.result["max_candidate_selection"]
        self.assertEqual(decision["score_callsite"], "0x080855A2")
        self.assertEqual(decision["score_target"], "0x08085160")
        self.assertEqual(decision["comparison"], "candidate_score > best_score")
        self.assertEqual(decision["candidate_copy_size"], 20)
        self.assertEqual(
            decision["enumeration_calls"],
            [
                {"callsite": "0x080855C0", "target": "0x08083364"},
                {"callsite": "0x080855C6", "target": "0x08083040"},
            ],
        )

    def test_tile_score_is_additive_and_uses_terrain_facing_and_rng(self):
        score = self.result["tile_score"]
        self.assertEqual(score["unit_pool_base"], "0x020240C0")
        self.assertEqual(score["unit_record_size"], "0x01D4")
        self.assertEqual(score["position_offsets"], ["0xC4", "0xC5"])
        self.assertEqual(score["facing_offset"], "0xC6")
        self.assertEqual(score["candidate_facing_offset"], "0xC9")
        self.assertEqual(score["tile_flags_base"], "0x0201BE2A")
        self.assertEqual(score["map_width_address"], "0x02002880")
        self.assertEqual(
            score["components"],
            [
                {"when": "unit[0xC6] == unit[0xC9]", "add": 50},
                {"when": "tile_flags & 1 == 0", "add": 200},
                {
                    "when": "tile_flags & 1 != 0 and ((tile_flags >> (unit[0xC6] + 4)) & 1) == 0",
                    "add": 100,
                },
                {
                    "when": "tile_flags & 1 != 0",
                    "add": "(rng_value * 50) >> 15",
                },
            ],
        )
        self.assertEqual(score["rng_state_pointer"], "0x03000010")
        self.assertEqual(score["rng_call"], "0x0809C110")

    def test_static_evidence_does_not_overclaim_ai_objectives(self):
        self.assertIn("does not establish", self.result["boundary"])
        self.assertIn("target priority", self.result["boundary"])
        self.assertIn("damage utility", self.result["boundary"])


if __name__ == "__main__":
    unittest.main()
