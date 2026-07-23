#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_unit_selection import build_unit_selection_manifest


ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "notes/battle-unit-selection-observations-20260723.json"


class BattleUnitSelectionTests(unittest.TestCase):
    def _manifest(self):
        return build_unit_selection_manifest(
            ROOT,
            ROOT / "rom/base.gba",
            ROOT / "notes/battle-controller-states-20260723.json",
            ROOT / "notes/battle-content-catalog-20260723.json",
            OBSERVATIONS,
        )

    def test_l_cycles_the_precommit_roster_without_binding_an_actor(self):
        result = self._manifest()
        self.assertEqual(result["controller_state"], "0x2000")
        self.assertEqual(
            result["selection_sequence"],
            [
                {"slot": 1, "character_id": 1, "display_name": "漩涡鸣人"},
                {"slot": 5, "character_id": 41, "display_name": "猫"},
                {"slot": 3, "character_id": 3, "display_name": "春野樱"},
                {"slot": 2, "character_id": 2, "display_name": "宇智波佐助"},
                {"slot": 1, "character_id": 1, "display_name": "漩涡鸣人"},
            ],
        )
        self.assertEqual(result["input_sequence"], ["L", "L", "L", "L"])
        self.assertEqual(result["current_unit_pointers"], ["0x00000000"] * 5)
        self.assertEqual(
            result["r_selection_from_initial"],
            {"slot": 2, "character_id": 2, "display_name": "宇智波佐助"},
        )
        self.assertEqual(result["r_current_unit_pointer"], "0x00000000")
        self.assertTrue(result["selection_is_precommit"])

    def test_each_l_press_moves_only_the_unit_selection_marker(self):
        result = self._manifest()
        self.assertEqual(
            result["transitions"][0]["unit_pool_diffs"],
            [
                {
                    "slot": 1,
                    "character_id": 1,
                    "offset": "0xC1",
                    "address": "0x02024355",
                    "before": 1,
                    "after": 0,
                },
                {
                    "slot": 5,
                    "character_id": 41,
                    "offset": "0xC1",
                    "address": "0x02024AA5",
                    "before": 0,
                    "after": 1,
                },
            ],
        )
        self.assertEqual(result["transitions"][0]["battle_control_diffs"], [])
        self.assertEqual(result["transitions"][1]["battle_control_diffs"], [])
        self.assertEqual(
            result["transitions"][4]["unit_pool_diffs"],
            [
                {
                    "slot": 1,
                    "character_id": 1,
                    "offset": "0xC1",
                    "address": "0x02024355",
                    "before": 1,
                    "after": 0,
                },
                {
                    "slot": 2,
                    "character_id": 2,
                    "offset": "0xC1",
                    "address": "0x02024529",
                    "before": 0,
                    "after": 1,
                },
            ],
        )
        self.assertEqual(result["transitions"][4]["key"], "R")
        self.assertEqual(result["transitions"][4]["battle_control_diffs"], [])
        self.assertEqual(
            [row["to_selection"]["slot"] for row in result["transitions"][:4]],
            [5, 3, 2, 1],
        )
        self.assertTrue(result["l_cycle_wraps_to_initial"])
        self.assertTrue(all(row["only_selection_marker_changed"] for row in result["transitions"]))

    def test_rejects_audit_hash_mismatch(self):
        source = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
        source["transitions"][0]["audit_sha256"] = "00" * 32
        with tempfile.TemporaryDirectory() as directory:
            observations = Path(directory) / "observations.json"
            observations.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "audit SHA-256 mismatch"):
                build_unit_selection_manifest(
                    ROOT,
                    ROOT / "rom/base.gba",
                    ROOT / "notes/battle-controller-states-20260723.json",
                    ROOT / "notes/battle-content-catalog-20260723.json",
                    observations,
                )


if __name__ == "__main__":
    unittest.main()
