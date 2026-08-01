from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from tools.find_battlefield_object_effect_seeds import inspect_state
from tools.inspect_mgba_savestate import load_gba_state


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-active-c3.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-active-c3-evidence.json"
STATE_SHA256 = "401256e00877169e98b3e6584488e732f9254b4426806ad2b6b3bdc770259939"


class Scenario49Tool67ActiveObjectPersistenceTests(unittest.TestCase):
    def test_checkpoint_contains_naturally_created_c3_object(self):
        self.assertEqual(hashlib.sha256(STATE.read_bytes()).hexdigest(), STATE_SHA256)
        inspected = inspect_state(load_gba_state(STATE))
        self.assertEqual(
            inspected["active_special_objects"],
            [{"slot": 3, "state": 1, "encoded_action": "0xC3", "remaining_turns": 2}],
        )
        self.assertEqual(inspected["equipped_special_tools"], [])
        self.assertEqual(
            inspected["persistent_equipped_special_tools"],
            [{"template_slot": 1, "character_id": 1, "tool_slot": 0, "ninja_tool_id": 67}],
        )
        self.assertEqual(inspected["inventory_special_tools"], [{"ninja_tool_id": 67, "count": 1}])

    def test_evidence_does_not_claim_expiry_before_it_is_observed(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["artifact_status"], "accepted")
        self.assertEqual(evidence["output"]["sha256"], STATE_SHA256)
        self.assertTrue(evidence["scope"]["natural_action_submission_verified"])
        self.assertTrue(evidence["scope"]["natural_object_creation_verified"])
        self.assertFalse(evidence["scope"]["natural_expiry_handler_verified"])


if __name__ == "__main__":
    unittest.main()
