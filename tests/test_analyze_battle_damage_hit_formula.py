#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_damage_hit_formula import build_damage_hit_manifest


ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "notes/battle-damage-hit-observations-20260723.json"


class BattleDamageHitFormulaTests(unittest.TestCase):
    def _manifest(self):
        return build_damage_hit_manifest(ROOT, ROOT / "rom/base.gba", OBSERVATIONS)

    def test_static_formula_separates_power_attack_defense_and_critical_candidates(self):
        result = self._manifest()
        self.assertEqual(result["event_builder"], "0x080754A8")
        self.assertEqual(result["hit_generator"], "0x08076034")
        self.assertEqual(
            result["damage_formula"],
            {
                "scaled_attack": "floor(attack * attack_percent / 100)",
                "raw_power": "floor(power * scaled_attack / 10)",
                "defense_factor": "100 - 5 * isqrt(defense)",
                "critical_raw_power": "floor(150 * raw_power / 100)",
                "candidate_offsets": {
                    "normal_defended": "event+0x18",
                    "critical_defended": "event+0x1A",
                    "normal_ignore_defense": "event+0x1C",
                    "critical_ignore_defense": "event+0x1E",
                },
            },
        )

    def test_hit_formula_uses_template_rate_agility_delta_and_one_rng_per_hit(self):
        result = self._manifest()
        self.assertEqual(
            result["base_hit_formula"],
            {
                "success_rate": "min(99, template_rate + trunc((source_agility - target_agility) / 2))",
                "rng_percent": "(rng_value * 100) >> 15",
                "hit_condition": "rng_percent < success_rate",
                "evaluated_per_hit": True,
            },
        )

    def test_natural_three_hit_sample_matches_formula_and_contains_one_miss(self):
        result = self._manifest()
        self.assertEqual(
            result["natural_sample"],
            {
                "action_id": 129,
                "power": 6,
                "hit_count": 3,
                "template_success_rate": 90,
                "source_attack": 19,
                "source_agility": 13,
                "target_defense": 14,
                "target_agility": 14,
                "computed_success_rate": 90,
                "damage_candidates": [9, 13, 11, 16],
                "target_hp": [49, 31],
                "total_damage": 18,
                "uniquely_inferred_outcomes": {
                    "normal_defended": 2,
                    "miss": 1,
                },
            },
        )

    def test_rejects_checkpoint_hash_mismatch(self):
        source = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
        source["natural_sample"]["preview_sha256"] = "00" * 32
        with tempfile.TemporaryDirectory() as directory:
            observations = Path(directory) / "observations.json"
            observations.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "preview checkpoint SHA-256 mismatch"):
                build_damage_hit_manifest(ROOT, ROOT / "rom/base.gba", observations)


if __name__ == "__main__":
    unittest.main()
