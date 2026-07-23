#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_objective_transitions import build_objective_manifest


ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "notes/battle-objective-transition-observations-20260723.json"


class BattleObjectiveTransitionTests(unittest.TestCase):
    def _manifest(self):
        return build_objective_manifest(
            ROOT,
            ROOT / "rom/base.gba",
            ROOT / "notes/battle-controller-states-20260723.json",
            OBSERVATIONS,
        )

    def test_composite_position_and_facing_goal_sets_victory(self):
        result = self._manifest()
        row = next(item for item in result["transitions"] if item["id"] == "bells_victory")
        self.assertEqual(row["battle_id"], 0x2C)
        self.assertEqual(row["before_controller_state"], "0xE000")
        self.assertEqual(row["after_controller_state"], "0xE010")
        self.assertEqual(row["result_before"], 0)
        self.assertEqual(row["result_after"], 1)
        self.assertEqual(row["actor"], {
            "slot": 3,
            "character_id": 3,
            "current_x": 4,
            "current_y": 3,
            "facing": 2,
        })
        self.assertEqual(row["required_defeated_slot"], 4)
        self.assertEqual(row["required_defeated_character_id"], 0)
        self.assertTrue(row["composite_goal_observed"])

    def test_escort_loss_sets_failure_inside_shared_resolution_state(self):
        result = self._manifest()
        row = next(item for item in result["transitions"] if item["id"] == "scroll_escort_failure")
        self.assertEqual(row["battle_id"], 0x0F)
        self.assertEqual(row["before_controller_state"], "0x8000")
        self.assertEqual(row["after_controller_state"], "0x8000")
        self.assertEqual(row["result_before"], 0)
        self.assertEqual(row["result_after"], 2)
        self.assertEqual(row["escort_slot"], 4)
        self.assertEqual(row["escort_character_id_before"], 0)
        self.assertEqual(row["escort_character_id_after"], 0)
        self.assertEqual(row["living_player_slots"], [1, 2, 3])
        self.assertEqual(row["battle_control_diffs"], [
            {"address": "0x02026807", "offset": "0x03", "before": 0, "after": 2}
        ])
        self.assertTrue(row["outcome_interrupts_within_resolution"])

    def test_rejects_hash_mismatch(self):
        source = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
        source["observations"][0]["before_sha256"] = "00" * 32
        with tempfile.TemporaryDirectory() as directory:
            observations = Path(directory) / "observations.json"
            observations.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checkpoint SHA-256 mismatch"):
                build_objective_manifest(
                    ROOT,
                    ROOT / "rom/base.gba",
                    ROOT / "notes/battle-controller-states-20260723.json",
                    observations,
                )


if __name__ == "__main__":
    unittest.main()
