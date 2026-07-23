#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_effect_resolution import build_effect_resolution_manifest


ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "notes/battle-effect-resolution-observations-20260723.json"


class BattleEffectResolutionTests(unittest.TestCase):
    def _manifest(self):
        return build_effect_resolution_manifest(
            ROOT,
            ROOT / "rom/base.gba",
            ROOT / "notes/battle-controller-states-20260723.json",
            OBSERVATIONS,
        )

    def test_normal_damage_and_substitution_are_distinct_resolution_branches(self):
        result = self._manifest()
        self.assertEqual(result["branch_count"], 2)
        damage, substitution = result["branches"]
        self.assertEqual(damage["controller_sequence"], ["0x4100", "0x8000", "0x9000"])
        self.assertEqual(damage["target_hp"], [46, 46, 32])
        self.assertEqual(damage["target_position"], [[2, 12], [2, 12], [2, 12]])
        self.assertEqual(damage["target_resolution_code"], [0, 0, 0])
        self.assertTrue(damage["damage_applied_without_target_displacement"])
        self.assertEqual(substitution["target_hp"], [110, 110, 110])
        self.assertEqual(substitution["target_position"], [[4, 6], [4, 6], [3, 5]])
        self.assertEqual(substitution["target_resolution_code"], [0, 22, 0])
        self.assertTrue(substitution["substitution_prevented_damage_and_displaced_target"])
        self.assertTrue(substitution["substitution_reaction_staged_before_domain_commit"])

    def test_confirmation_does_not_apply_hp_or_cost_before_shared_resolution(self):
        result = self._manifest()
        for branch in result["branches"]:
            self.assertEqual(branch["target_hp"][0], branch["target_hp"][1])
            self.assertEqual(branch["actor_chakra"][0], branch["actor_chakra"][1])
            self.assertEqual(branch["actor_action_flags_low"][:2], [0, 0])
            self.assertEqual(branch["actor_action_flags_low"][2], 16)
        self.assertTrue(result["preview_is_not_the_committed_outcome"])
        self.assertTrue(result["reaction_branch_occurs_inside_shared_resolution"])

    def test_rejects_resolve_audit_hash_mismatch(self):
        source = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
        source["observations"][1]["resolve_audit_sha256"] = "00" * 32
        with tempfile.TemporaryDirectory() as directory:
            observations = Path(directory) / "observations.json"
            observations.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "resolve audit SHA-256 mismatch"):
                build_effect_resolution_manifest(
                    ROOT,
                    ROOT / "rom/base.gba",
                    ROOT / "notes/battle-controller-states-20260723.json",
                    observations,
                )


if __name__ == "__main__":
    unittest.main()
