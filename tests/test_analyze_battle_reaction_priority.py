#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_reaction_priority import build_reaction_priority_manifest


ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "notes/battle-reaction-priority-observations-20260723.json"


class BattleReactionPriorityTests(unittest.TestCase):
    def _manifest(self):
        return build_reaction_priority_manifest(
            ROOT,
            ROOT / "rom/base.gba",
            OBSERVATIONS,
        )

    def test_preprocessor_has_explicit_blocker_and_reaction_priority(self):
        result = self._manifest()
        self.assertEqual(
            result["preprocessor"]["blocking_status_priority"],
            [0x3F, 0x3E, 0x3D, 0x0F, 0x11, 0x15],
        )
        self.assertEqual(
            result["preprocessor"]["reaction_status_priority"],
            [0x04, 0x0A, 0x09, 0x10, 0x16, 0x19],
        )
        self.assertTrue(result["preprocessor"]["only_nonzero_hit_can_trigger"])

    def test_sharingan_wraps_first_effective_hit_and_truncates_later_hits(self):
        result = self._manifest()
        self.assertEqual(
            result["natural_multihit_baseline"],
            {
                "action_id": 129,
                "attacker_slot": 1,
                "target_slot": 5,
                "queued_hit_count": 3,
                "target_hp": [49, 31],
                "total_damage": 18,
            },
        )
        self.assertEqual(
            result["runtime_queue"],
            {
                "attacker_slot": 5,
                "target_slot": 2,
                "action_id": 5,
                "reaction_action_id": 15,
                "reaction_code": 0x10,
                "queued_hit_count": 1,
            },
        )
        self.assertEqual(result["resolver"]["normal_handler"], "0x08077040")
        self.assertEqual(result["resolver"]["shared_resolver"], "0x08076A30")
        self.assertEqual(result["resolver"]["reaction_helper"], "0x080768D8")
        self.assertTrue(result["resolver"]["reaction_metadata_is_cleared_after_hit"])
        self.assertEqual(
            result["resolver"]["status_0x10_policy"],
            "replace_first_effective_hit_and_truncate_following_hits",
        )

    def test_counter_like_reactions_reverse_source_and_target(self):
        result = self._manifest()
        self.assertEqual(result["resolver"]["reverse_source_target_statuses"], [0x0A, 0x09, 0x19])
        self.assertEqual(result["resolver"]["adjacency_required_statuses"], [0x04, 0x16, 0x19])
        self.assertEqual(
            result["counter_runtime_sample"],
            {
                "prepared_unit_slot": 2,
                "prepared_character_id": 2,
                "tool_id": 46,
                "runtime_action_id": 174,
                "reaction_code": 0x19,
                "attacker_slot": 5,
                "target_slot": 2,
                "incoming_action_id": 5,
                "queued_hit_count": 1,
                "defender_hp": [134, 134],
                "attacker_hp": [17, 3],
                "counter_damage": 14,
                "reaction_was_consumed": True,
                "reaction_metadata_was_cleared": True,
            },
        )
        self.assertTrue(result["resolver"]["counter_runtime_sample_complete"])

    def test_rejects_rom_hash_mismatch(self):
        source = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
        source["rom_sha256"] = "00" * 32
        with tempfile.TemporaryDirectory() as directory:
            observations = Path(directory) / "observations.json"
            observations.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ROM SHA-256 mismatch"):
                build_reaction_priority_manifest(
                    ROOT,
                    ROOT / "rom/base.gba",
                    observations,
                )


if __name__ == "__main__":
    unittest.main()
