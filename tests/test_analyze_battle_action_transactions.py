#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_action_transactions import build_transaction_manifest


ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "notes/battle-action-transaction-observations-20260723.json"


class BattleActionTransactionTests(unittest.TestCase):
    def _manifest(self):
        return build_transaction_manifest(
            ROOT,
            ROOT / "rom/base.gba",
            ROOT / "notes/battle-controller-states-20260723.json",
            OBSERVATIONS,
        )

    def test_cancel_paths_preserve_all_domain_regions(self):
        result = self._manifest()
        cancels = [row for row in result["transitions"] if row["kind"] == "cancel"]
        self.assertEqual(len(cancels), 3)
        self.assertEqual(
            {row["id"] for row in cancels},
            {"move_menu_cancel", "target_to_action_cancel", "nested_skill_cancel"},
        )
        for row in cancels:
            self.assertTrue(row["domain_state_preserved"])
            self.assertEqual(row["unit_pool_diffs"], [])
            self.assertEqual(row["ninja_tool_inventory_diffs"], [])
            self.assertEqual(row["battle_control_diffs"], [])

    def test_teleport_commit_deducts_resource_only_at_resolution_boundary(self):
        result = self._manifest()
        row = next(
            item for item in result["transitions"] if item["id"] == "teleport_commit"
        )
        self.assertEqual(row["before_controller_state"], "0x8000")
        self.assertEqual(row["after_controller_state"], "0x9000")
        self.assertEqual(row["current_unit_pointer"], "0x02024468")
        self.assertEqual(
            row["semantic_current_unit_diffs"],
            {
                "action_flags_low": {"offset": "0xC0", "before": 0, "after": 16},
                "current_chakra": {"offset": "0x07", "before": 1, "after": 0},
                "position_x": {"offset": "0xC4", "before": 5, "after": 3},
                "position_y": {"offset": "0xC5", "before": 6, "after": 5},
            },
        )
        self.assertEqual(row["ninja_tool_inventory_diffs"], [])
        self.assertTrue(row["atomic_resource_and_position_commit"])

    def test_rejects_checkpoint_hash_mismatch_before_analysis(self):
        source = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
        source["observations"][0]["before_sha256"] = "00" * 32
        with tempfile.TemporaryDirectory() as directory:
            observations = Path(directory) / "observations.json"
            observations.write_text(
                json.dumps(source, ensure_ascii=False), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "checkpoint SHA-256 mismatch"):
                build_transaction_manifest(
                    ROOT,
                    ROOT / "rom/base.gba",
                    ROOT / "notes/battle-controller-states-20260723.json",
                    observations,
                )

    def test_direct_cli_generates_the_same_four_transitions(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "transactions.json"
            subprocess.run(
                [
                    "python3",
                    str(ROOT / "tools/analyze_battle_action_transactions.py"),
                    "--root",
                    str(ROOT),
                    "--rom",
                    str(ROOT / "rom/base.gba"),
                    "--states",
                    str(ROOT / "notes/battle-controller-states-20260723.json"),
                    "--observations",
                    str(OBSERVATIONS),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
            )
            result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["transition_count"], 4)


if __name__ == "__main__":
    unittest.main()
