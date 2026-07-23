#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_defense_preparation import build_defense_preparation_manifest


ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "notes/battle-defense-preparation-observations-20260723.json"


class BattleDefensePreparationTests(unittest.TestCase):
    def _manifest(self):
        return build_defense_preparation_manifest(
            ROOT,
            ROOT / "rom/base.gba",
            ROOT / "notes/battle-controller-states-20260723.json",
            OBSERVATIONS,
        )

    def test_defense_prompt_opens_the_shared_action_list_before_category_revalidation(self):
        result = self._manifest()
        self.assertEqual(result["input_sequence"], ["Up", "A", "A"])
        self.assertEqual(result["controller_sequence"], ["0x9100", "0x9100", "0x9200", "0x9200"])
        self.assertEqual(result["actor_pointer_sequence"], ["0x02024468"] * 4)
        self.assertEqual(result["actor_action_flags_sequence"], ["0x00000110"] * 4)
        self.assertEqual(result["visible_rejection"]["selected_action"], "火遁术")
        self.assertTrue(result["defense_list_is_browsable_but_confirmation_revalidates_category"])

    def test_all_three_ui_transitions_preserve_domain_state(self):
        result = self._manifest()
        for transition in result["transitions"]:
            self.assertEqual(transition["unit_pool_diffs"], [])
            self.assertEqual(transition["battle_control_diffs"], [])
            self.assertTrue(transition["action_menu_diffs"])
        self.assertTrue(result["offensive_action_rejected_without_domain_mutation"])

    def test_rejects_transition_audit_hash_mismatch(self):
        source = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
        source["transitions"][2]["audit_sha256"] = "00" * 32
        with tempfile.TemporaryDirectory() as directory:
            observations = Path(directory) / "observations.json"
            observations.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "audit SHA-256 mismatch"):
                build_defense_preparation_manifest(
                    ROOT,
                    ROOT / "rom/base.gba",
                    ROOT / "notes/battle-controller-states-20260723.json",
                    observations,
                )


if __name__ == "__main__":
    unittest.main()
