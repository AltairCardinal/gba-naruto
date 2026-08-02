from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from tools.inspect_mgba_savestate import load_gba_state
from tools.verify_battle_effect_frame_phase import TASK_BASE, TASK_COUNT, TASK_SIZE


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-tool37-group17-active.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-tool37-group17-active-evidence.json"
STATE_SHA256 = "ac99cf9eba9582bad085226dd8683f33babafc3df83a0647e0deb05a9e76755f"


class Scenario49Tool37Group17PersistenceTests(unittest.TestCase):
    def test_checkpoint_contains_naturally_created_group17_task(self):
        self.assertEqual(hashlib.sha256(STATE.read_bytes()).hexdigest(), STATE_SHA256)
        state = load_gba_state(STATE)
        matching_slots = []
        for slot in range(TASK_COUNT):
            task = state.read_memory(TASK_BASE + slot * TASK_SIZE, TASK_SIZE)
            if (
                int.from_bytes(task[0:4], "little") & 1
                and int.from_bytes(task[0x1C:0x20], "little") == 0x083478B4
                and int.from_bytes(task[0x20:0x24], "little") == 0x083478F0
            ):
                matching_slots.append(slot)
        self.assertEqual(matching_slots, [125])

    def test_evidence_binds_final_input_to_group17(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["artifact_status"], "accepted")
        self.assertEqual(evidence["output"]["sha256"], STATE_SHA256)
        self.assertEqual(evidence["provenance"]["confirmation_parent_sha256"],
                         "af37457d4cd41e180e61338fed77d6322b4aecd21386917739f2e56599708a46")
        self.assertEqual(evidence["runtime_binding"]["ninja_tool_id"], 37)
        self.assertEqual(evidence["runtime_binding"]["encoded_action_id"], 165)
        self.assertEqual(evidence["runtime_binding"]["resource_group_id"], 17)
        self.assertEqual(evidence["active_task"]["slot"], 125)
        self.assertTrue(evidence["scope"]["natural_action_submission_verified"])
        self.assertTrue(evidence["scope"]["natural_group17_creation_verified"])


if __name__ == "__main__":
    unittest.main()
