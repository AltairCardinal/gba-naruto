from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from tools.find_battlefield_object_effect_seeds import inspect_state
from tools.inspect_mgba_savestate import load_gba_state


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-expiry-ready.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-expiry-ready-evidence.json"
STATE_SHA256 = "34eb56d34d876a275546a2b6875804aa5e24c97600a9d299c0c6ba0ae165b501"


class Scenario49Tool67ExpiryReadyPersistenceTests(unittest.TestCase):
    def test_checkpoint_contains_zero_turn_c3_object(self):
        self.assertEqual(hashlib.sha256(STATE.read_bytes()).hexdigest(), STATE_SHA256)
        inspected = inspect_state(load_gba_state(STATE))
        self.assertEqual(
            inspected["active_special_objects"],
            [{"slot": 3, "state": 1, "encoded_action": "0xC3", "remaining_turns": 0}],
        )

    def test_evidence_stops_before_claiming_expiry_dispatch(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["artifact_status"], "accepted")
        self.assertEqual(evidence["output"]["sha256"], STATE_SHA256)
        self.assertTrue(evidence["scope"]["natural_countdown_zero_verified"])
        self.assertFalse(evidence["scope"]["natural_expiry_handler_verified"])


if __name__ == "__main__":
    unittest.main()
