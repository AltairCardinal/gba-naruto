from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from tools.find_battlefield_object_effect_seeds import (
    PERSISTENT_TEMPLATE_POOL,
    PERSISTENT_TEMPLATE_STRIDE,
    TOOL_COUNT_OFFSET,
    TOOL_FIRST_ID_OFFSET,
    UNIT_POOL,
    UNIT_STRIDE,
)
from tools.inspect_mgba_savestate import load_gba_state


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-tool37-confirmation.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-tool37-confirmation-evidence.json"
STATE_SHA256 = "af37457d4cd41e180e61338fed77d6322b4aecd21386917739f2e56599708a46"


class Scenario49Tool37ConfirmationPersistenceTests(unittest.TestCase):
    def test_checkpoint_is_before_tool37_submission(self):
        self.assertEqual(hashlib.sha256(STATE.read_bytes()).hexdigest(), STATE_SHA256)
        state = load_gba_state(STATE)
        self.assertEqual(state.read_memory(0x02026804, 8), bytes.fromhex("000e000000000000"))

        unit = state.read_memory(UNIT_POOL + UNIT_STRIDE, UNIT_STRIDE)
        self.assertEqual(unit[0], 1)
        self.assertEqual(unit[TOOL_COUNT_OFFSET], 1)
        self.assertEqual(unit[TOOL_FIRST_ID_OFFSET], 37)

        template = state.read_memory(
            PERSISTENT_TEMPLATE_POOL + PERSISTENT_TEMPLATE_STRIDE,
            PERSISTENT_TEMPLATE_STRIDE,
        )
        self.assertEqual(template[0], 1)
        self.assertEqual(template[TOOL_COUNT_OFFSET], 1)
        self.assertEqual(template[TOOL_FIRST_ID_OFFSET], 37)

    def test_evidence_keeps_confirmation_and_group17_scope_separate(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["artifact_status"], "accepted")
        self.assertEqual(evidence["output"]["sha256"], STATE_SHA256)
        self.assertEqual(evidence["next_input"], "A:5:13")
        self.assertEqual(evidence["battle"]["battle_local_tool"]["ninja_tool_id"], 37)
        self.assertTrue(evidence["restore_verification"]["zero_input_verified"])
        self.assertTrue(evidence["restore_verification"]["pgid_clean"])
        self.assertTrue(evidence["restore_verification"]["mgba_listener_clean"])
        self.assertFalse(evidence["scope"]["natural_action_submission_verified"])
        self.assertFalse(evidence["scope"]["natural_group17_creation_verified"])


if __name__ == "__main__":
    unittest.main()
