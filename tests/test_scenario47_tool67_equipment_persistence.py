from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from tools.find_battlefield_object_effect_seeds import inspect_state
from tools.inspect_mgba_savestate import load_gba_state


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "artifacts/runtime-checkpoints/scenario-47-tool67-equipped-world-map.ss9"
EVIDENCE = ROOT / "artifacts/runtime-checkpoints/scenario-47-tool67-equipped-world-map-evidence.json"
STATE_SHA256 = "ecea4dc669f4e7d8a72d6c6e28fe456ec335c3c113c8c1426ed5e7eba225e601"


class Scenario47Tool67EquipmentPersistenceTests(unittest.TestCase):
    def test_checkpoint_preserves_natural_tool67_inventory_and_loadout(self):
        self.assertEqual(hashlib.sha256(STATE.read_bytes()).hexdigest(), STATE_SHA256)
        inspected = inspect_state(load_gba_state(STATE))
        self.assertEqual(
            inspected["inventory_special_tools"],
            [{"ninja_tool_id": 67, "count": 1}],
        )
        self.assertEqual(
            inspected["persistent_equipped_special_tools"],
            [
                {
                    "template_slot": 1,
                    "character_id": 1,
                    "tool_slot": 0,
                    "ninja_tool_id": 67,
                }
            ],
        )
        self.assertEqual(inspected["equipped_special_tools"], [])
        self.assertEqual(inspected["active_special_objects"], [])

    def test_evidence_binds_natural_ui_commit_and_delayed_effect_identity(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["artifact_status"], "accepted")
        self.assertEqual(evidence["input"]["sha256"], "e80779dc048fd862d0a8fc1a47f77bcfe1ab06810859f38015c562679958b800")
        self.assertEqual(evidence["output"]["sha256"], STATE_SHA256)
        self.assertEqual(evidence["persistent_commit"], {
            "address": "0x02022FA1",
            "before": 1,
            "after": 67,
            "character_id": 1,
            "template_slot": 1,
            "tool_slot": 0,
        })
        self.assertEqual(evidence["runtime_binding"], {
            "ninja_tool_id": 67,
            "encoded_action": "0xC3",
            "expiry_action": "0xE4",
            "resource_group_id": 3,
        })
        self.assertTrue(evidence["scope"]["checkpoint_restore_verified"])
        self.assertFalse(evidence["scope"]["battle_local_copy_verified"])
        self.assertFalse(evidence["scope"]["natural_expiry_handler_verified"])


if __name__ == "__main__":
    unittest.main()
