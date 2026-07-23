#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.extract_battle_controller_states import extract_controller_states


ROOT = Path(__file__).resolve().parents[1]


class BattleControllerStateTests(unittest.TestCase):
    def setUp(self):
        self.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_extracts_complete_dispatch_inventory(self):
        result = extract_controller_states(self.rom)
        self.assertEqual(result["controller_entry"], "0x080732B4")
        self.assertEqual(result["dispatch_state_count"], 36)
        self.assertEqual([row["state"] for row in result["states"]], sorted(
            row["state"] for row in result["states"]
        ))

    def test_exposes_evidence_backed_turn_and_action_boundaries(self):
        by_state = {
            row["state_hex"]: row for row in extract_controller_states(self.rom)["states"]
        }
        self.assertEqual(by_state["0x1300"]["entry"], "0x080738C0")
        self.assertEqual(by_state["0x1300"]["semantic"], "side_scheduler")
        self.assertEqual(by_state["0x2000"]["semantic"], "player_unit_selection")
        self.assertEqual(by_state["0x3000"]["semantic"], "unit_action_menu")
        self.assertEqual(by_state["0x3110"]["semantic"], "player_move_selection")
        self.assertEqual(by_state["0x3210"]["semantic"], "chakra_exchange_result")
        self.assertEqual(by_state["0x3310"]["semantic"], "rest_confirmation")
        self.assertEqual(
            by_state["0x3210"]["semantic_status"],
            "checkpoint_runtime_transaction",
        )
        self.assertEqual(
            by_state["0x3310"]["semantic_status"],
            "checkpoint_runtime_transaction",
        )
        self.assertEqual(by_state["0x4000"]["semantic"], "post_move_action_menu")
        self.assertEqual(by_state["0x4100"]["semantic"], "technique_targeting")
        self.assertEqual(by_state["0x6000"]["semantic"], "player_action_confirmation")
        self.assertEqual(by_state["0x7000"]["semantic"], "enemy_action_preparation")
        self.assertEqual(by_state["0x8000"]["semantic"], "action_resolution_and_outcome")
        self.assertEqual(by_state["0x9000"]["semantic"], "facing_selection")
        self.assertEqual(by_state["0x9100"]["semantic"], "defense_preparation")
        self.assertEqual(by_state["0x9200"]["semantic"], "technique_menu")
        self.assertEqual(
            by_state["0x4100"]["semantic_status"],
            "static_plus_checkpoint_runtime",
        )
        self.assertEqual(by_state["0xD000"]["semantic"], "secondary_action_completion")
        self.assertEqual(by_state["0xF400"]["semantic"], "postbattle")

    def test_preserves_unknown_states_as_unknown(self):
        rows = extract_controller_states(self.rom)["states"]
        unresolved = [row for row in rows if row["semantic_status"] == "unresolved"]
        self.assertGreaterEqual(len(unresolved), 10)
        self.assertTrue(all(row["semantic"].startswith("unresolved_") for row in unresolved))

    def test_rejects_a_dispatcher_that_does_not_match_the_proven_rom(self):
        changed = bytearray(self.rom)
        changed[0x733A0] ^= 0x01
        with self.assertRaisesRegex(ValueError, "dispatcher signature"):
            extract_controller_states(bytes(changed))


if __name__ == "__main__":
    unittest.main()
