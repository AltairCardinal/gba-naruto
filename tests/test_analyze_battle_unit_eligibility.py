#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_unit_eligibility import build_unit_eligibility_manifest


ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "notes/battle-unit-eligibility-observations-20260723.json"


class BattleUnitEligibilityTests(unittest.TestCase):
    def _manifest(self):
        return build_unit_eligibility_manifest(
            ROOT,
            ROOT / "rom/base.gba",
            ROOT / "notes/battle-controller-states-20260723.json",
            OBSERVATIONS,
        )

    def test_confirmation_accepts_only_the_unspent_commandable_unit(self):
        result = self._manifest()
        self.assertEqual(result["case_count"], 3)
        accepted, completed, escort = result["cases"]
        self.assertEqual(accepted["selected_unit"]["slot"], 3)
        self.assertEqual(accepted["controller_transition"], "0x2000 -> 0x3000")
        self.assertEqual(accepted["after_current_unit_pointer"], "0x0202463C")
        self.assertTrue(accepted["command_accepted"])
        self.assertEqual(completed["selected_unit"]["action_flags_low"], 16)
        self.assertEqual(escort["selected_unit"]["action_state"], 2)
        self.assertTrue(completed["command_rejected_without_domain_mutation"])
        self.assertTrue(escort["command_rejected_without_domain_mutation"])

    def test_rejected_confirmation_keeps_roster_browsing_separate_from_command_eligibility(self):
        result = self._manifest()
        for case in result["cases"][1:]:
            self.assertEqual(case["controller_transition"], "0x2000 -> 0x2000")
            self.assertEqual(case["after_current_unit_pointer"], "0x00000000")
            self.assertEqual(case["unit_pool_diffs"], [])
            self.assertEqual(case["battle_control_diffs"], [])
            self.assertEqual(case["action_menu_diffs"], [])
        self.assertTrue(result["roster_browsing_is_separate_from_command_eligibility"])

    def test_rejects_transition_audit_hash_mismatch(self):
        source = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
        source["observations"][0]["audit_sha256"] = "00" * 32
        with tempfile.TemporaryDirectory() as directory:
            observations = Path(directory) / "observations.json"
            observations.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "audit SHA-256 mismatch"):
                build_unit_eligibility_manifest(
                    ROOT,
                    ROOT / "rom/base.gba",
                    ROOT / "notes/battle-controller-states-20260723.json",
                    observations,
                )


if __name__ == "__main__":
    unittest.main()
