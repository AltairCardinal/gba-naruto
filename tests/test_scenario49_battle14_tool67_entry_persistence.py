from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from tools.find_battlefield_object_effect_seeds import inspect_state
from tools.inspect_mgba_savestate import load_gba_state


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-entry.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-entry-evidence.json"
STATE_SHA256 = "2c95de937efb785d537c45f39224bb3fdae319e410f6abbc3cbdfcc32fb2812c"


class Scenario49Battle14Tool67EntryPersistenceTests(unittest.TestCase):
    def test_checkpoint_is_battle14_with_tool67_in_persistent_and_battle_slots(self):
        self.assertEqual(hashlib.sha256(STATE.read_bytes()).hexdigest(), STATE_SHA256)
        state = load_gba_state(STATE)
        self.assertEqual(state.read_memory(0x02026804, 8), bytes.fromhex("000e000000000000"))
        inspected = inspect_state(state)
        self.assertEqual(
            inspected["persistent_equipped_special_tools"],
            [{"template_slot": 1, "character_id": 1, "tool_slot": 0, "ninja_tool_id": 67}],
        )
        self.assertEqual(
            inspected["equipped_special_tools"],
            [{"unit_slot": 1, "character_id": 1, "tool_slot": 0, "ninja_tool_id": 67}],
        )
        self.assertEqual(inspected["inventory_special_tools"], [{"ninja_tool_id": 67, "count": 1}])
        self.assertEqual(inspected["active_special_objects"], [])

    def test_evidence_keeps_runtime_boundary_claims_fail_closed(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["artifact_status"], "accepted")
        self.assertEqual(evidence["output"]["sha256"], STATE_SHA256)
        self.assertEqual(evidence["battle"]["battle_id"], 14)
        self.assertEqual(evidence["battle"]["battle_local_tool"], {
            "unit_slot": 1,
            "character_id": 1,
            "tool_slot": 0,
            "ninja_tool_id": 67,
        })
        self.assertTrue(evidence["scope"]["battle_local_copy_verified"])
        self.assertFalse(evidence["scope"]["natural_action_submission_verified"])
        self.assertFalse(evidence["scope"]["natural_expiry_handler_verified"])


if __name__ == "__main__":
    unittest.main()
