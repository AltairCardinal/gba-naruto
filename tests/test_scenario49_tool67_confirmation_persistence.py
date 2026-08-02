from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from tools.find_battlefield_object_effect_seeds import inspect_state
from tools.inspect_mgba_savestate import load_gba_state


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-confirmation.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-confirmation-evidence.json"
CHILD_EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-active-c3-evidence.json"
STATE_SHA256 = "95cc6805139fa6bad2a8af3353bcc161b38db51067b558f02b6c7c1dc4764012"


class Scenario49Tool67ConfirmationPersistenceTests(unittest.TestCase):
    def test_checkpoint_is_before_tool67_submission(self):
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
        self.assertEqual(inspected["active_special_objects"], [])

    def test_evidence_is_anchored_by_the_accepted_child_checkpoint(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        child = json.loads(CHILD_EVIDENCE.read_text(encoding="utf-8"))
        child_sha256 = hashlib.sha256(CHILD_EVIDENCE.read_bytes()).hexdigest()
        self.assertEqual(evidence["artifact_status"], "accepted")
        self.assertEqual(evidence["output"]["sha256"], STATE_SHA256)
        self.assertEqual(evidence["next_input"], "A:5:13")
        self.assertEqual(evidence["accepted_child"]["sha256"], child_sha256)
        self.assertEqual(
            evidence["accepted_child"]["confirmation_parent_sha256"],
            child["provenance"]["confirmation_parent_sha256"],
        )
        self.assertEqual(
            child["provenance"]["confirmation_parent_sha256"], STATE_SHA256
        )
        self.assertTrue(evidence["restore_verification"]["zero_input_verified"])
        self.assertEqual(evidence["restore_verification"]["capture_frame"], 60)
        self.assertTrue(evidence["restore_verification"]["pgid_clean"])
        self.assertTrue(evidence["restore_verification"]["mgba_listener_clean"])
        self.assertFalse(evidence["scope"]["natural_action_submission_verified"])


if __name__ == "__main__":
    unittest.main()
