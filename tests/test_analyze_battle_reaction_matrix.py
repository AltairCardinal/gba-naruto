#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.durable_evidence import load_binding, raw_evidence_available
from tools.analyze_battle_reaction_matrix import build_reaction_matrix_manifest


ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "notes/battle-reaction-matrix-observations-20260723.json"
RAW_EVIDENCE_AVAILABLE = raw_evidence_available(ROOT, OBSERVATIONS)


class BattleReactionMatrixTests(unittest.TestCase):
    def _manifest(self):
        return load_binding(ROOT, "battle-reaction-matrix-bindings-20260723.json")

    def test_resolution_code_separates_damage_from_substitution(self):
        result = self._manifest()
        self.assertEqual(result["sample_count"], 29)
        self.assertEqual(result["outcome_counts"], {"damage": 18, "substitution": 11})
        self.assertEqual(result["confirmed_resolution_codes"], {"damage": [0], "substitution": [22]})
        self.assertTrue(result["resolution_code_is_disjoint_for_sampled_outcomes"])
        self.assertTrue(result["all_samples_cross_shared_resolution_to_facing"])

    def test_each_sample_is_hash_bound_and_matches_domain_outcome(self):
        result = self._manifest()
        for sample in result["samples"]:
            self.assertEqual(sample["controller_sequence"], ["0x8000", "0x9000"])
            self.assertTrue(sample["audit_sha256"])
            self.assertEqual(len(sample["state_sha256"]), 2)
            if sample["kind"] == "damage":
                self.assertGreater(sample["target_hp"][0], sample["target_hp"][1])
                self.assertEqual(sample["target_position"][0], sample["target_position"][1])
                self.assertEqual(sample["target_resolution_code"], [0, 0])
            else:
                self.assertEqual(sample["target_hp"][0], sample["target_hp"][1])
                self.assertNotEqual(sample["target_position"][0], sample["target_position"][1])
                self.assertEqual(sample["target_resolution_code"], [22, 0])

    @unittest.skipUnless(RAW_EVIDENCE_AVAILABLE, "raw build evidence is unavailable")
    def test_rejects_audit_hash_mismatch(self):
        source = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
        source["observations"][0]["audit_sha256"] = "00" * 32
        with tempfile.TemporaryDirectory() as directory:
            observations = Path(directory) / "observations.json"
            observations.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "audit SHA-256 mismatch"):
                build_reaction_matrix_manifest(
                    ROOT,
                    ROOT / "rom/base.gba",
                    ROOT / "notes/battle-controller-states-20260723.json",
                    observations,
                )


if __name__ == "__main__":
    unittest.main()
