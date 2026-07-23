#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_resource_transactions import build_resource_manifest


ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "notes/battle-resource-transaction-observations-20260723.json"


class BattleResourceTransactionTests(unittest.TestCase):
    def _manifest(self):
        return build_resource_manifest(
            ROOT,
            ROOT / "rom/base.gba",
            ROOT / "notes/battle-controller-states-20260723.json",
            OBSERVATIONS,
        )

    def test_chakra_command_exchanges_hp_at_its_commit_boundary(self):
        result = self._manifest()
        row = next(item for item in result["transitions"] if item["id"] == "chakra_exchange")
        self.assertEqual(row["before_controller_state"], "0x3000")
        self.assertEqual(row["after_controller_state"], "0x3210")
        self.assertEqual(row["unit_slot"], 1)
        self.assertEqual(row["character_id"], 1)
        self.assertEqual(row["current_hp"], {"before": 134, "after": 119})
        self.assertEqual(row["current_chakra"], {"before": 4, "after": 5})
        self.assertEqual(row["ninja_tool_inventory_diffs"], [])
        self.assertTrue(row["resource_exchange_committed"])

    def test_rest_heals_without_chakra_or_inventory_cost(self):
        result = self._manifest()
        row = next(item for item in result["transitions"] if item["id"] == "rest_heal")
        self.assertEqual(row["before_controller_state"], "0x3310")
        self.assertEqual(row["after_controller_state"], "0x1220")
        self.assertEqual(row["unit_slot"], 2)
        self.assertEqual(row["character_id"], 2)
        self.assertEqual(row["current_hp"], {"before": 24, "after": 41})
        self.assertEqual(row["current_chakra"], {"before": 4, "after": 4})
        self.assertEqual(row["action_flags_low"], {"before": 0, "after": 32})
        self.assertEqual(row["ninja_tool_inventory_diffs"], [])
        self.assertTrue(row["rest_committed_and_action_completed"])

    def test_ninja_tool_consumes_the_battle_local_equipped_slot(self):
        result = self._manifest()
        row = next(
            item for item in result["transitions"] if item["id"] == "ninja_tool_consumption"
        )
        self.assertEqual(row["before_controller_state"], "0x4100")
        self.assertEqual(row["after_controller_state"], "0x9000")
        self.assertEqual(row["unit_slot"], 1)
        self.assertEqual(row["character_id"], 1)
        self.assertEqual(row["current_hp"], {"before": 46, "after": 46})
        self.assertEqual(row["current_chakra"], {"before": 5, "after": 5})
        self.assertEqual(row["action_flags_low"], {"before": 0, "after": 16})
        self.assertEqual(
            row["battle_local_tool_slot"],
            {
                "offset": "0xB1",
                "address": "0x02024345",
                "before": 1,
                "after": 0,
            },
        )
        self.assertEqual(row["ninja_tool_inventory_diffs"], [])
        self.assertTrue(row["battle_local_tool_consumed"])

    def test_rejects_hash_mismatch(self):
        source = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
        source["observations"][0]["after_sha256"] = "00" * 32
        with tempfile.TemporaryDirectory() as directory:
            observations = Path(directory) / "observations.json"
            observations.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checkpoint SHA-256 mismatch"):
                build_resource_manifest(
                    ROOT,
                    ROOT / "rom/base.gba",
                    ROOT / "notes/battle-controller-states-20260723.json",
                    observations,
                )


if __name__ == "__main__":
    unittest.main()
