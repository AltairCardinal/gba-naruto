#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_defense_reaction import build_defense_reaction_manifest


ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "notes/battle-defense-reaction-observations-20260723.json"


class BattleDefenseReactionTests(unittest.TestCase):
    def _manifest(self):
        return build_defense_reaction_manifest(
            ROOT,
            ROOT / "rom/base.gba",
            ROOT / "notes/battle-controller-states-20260723.json",
            OBSERVATIONS,
        )

    def test_controlled_patch_changes_only_unlock_and_current_chakra(self):
        result = self._manifest()
        self.assertEqual(
            result["controlled_patch"]["unit_diffs"],
            [
                {"offset": "0x07", "before": 1, "after": 5},
                {"offset": "0x35", "before": 255, "after": 1},
            ],
        )
        self.assertEqual(result["controlled_patch"]["action_id"], 15)

    def test_preview_commit_and_consumption_are_separate_transactions(self):
        result = self._manifest()
        self.assertEqual(
            result["controller_sequence"],
            ["0x9200", "0x1220", "0x8000", "0x8000"],
        )
        self.assertEqual(result["actor_current_chakra"], [5, 3, 3, 3])
        self.assertEqual(result["prepared_reaction_code"], [0, 16, 0, 0])
        self.assertEqual(result["prepared_action_id"], [0, 15, 15, 15])
        self.assertTrue(result["preview_has_no_domain_write"])
        self.assertTrue(result["commit_is_atomic"])
        self.assertTrue(result["reaction_is_consumed_once"])

    def test_sharingan_reaction_preserves_hp_and_position(self):
        result = self._manifest()
        self.assertEqual(result["actor_current_hp"], [134, 134, 134, 134])
        self.assertEqual(result["actor_position"], [[5, 6]] * 4)
        self.assertEqual(
            result["attacker"],
            {
                "slot": 5,
                "character_id": 35,
                "position": [5, 7],
                "controller_state": "0x8000",
            },
        )
        self.assertEqual(result["reaction_visual"], "写轮眼")

    def test_rejects_checkpoint_hash_mismatch(self):
        source = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
        source["states"][0]["sha256"] = "00" * 32
        with tempfile.TemporaryDirectory() as directory:
            observations = Path(directory) / "observations.json"
            observations.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checkpoint SHA-256 mismatch"):
                build_defense_reaction_manifest(
                    ROOT,
                    ROOT / "rom/base.gba",
                    ROOT / "notes/battle-controller-states-20260723.json",
                    observations,
                )


if __name__ == "__main__":
    unittest.main()
