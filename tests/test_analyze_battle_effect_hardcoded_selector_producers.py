from __future__ import annotations

import copy
import importlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HardcodedSelectorProducerAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = importlib.import_module(
            "tools.analyze_battle_effect_hardcoded_selector_producers"
        )
        cls.result = cls.module.analyze(ROOT)

    def test_preserves_complete_selector_and_handler_denominators(self):
        self.assertEqual(self.result["schema"], "battle-effect-hardcoded-selector-producers-v1")
        self.assertEqual(
            self.result["sources"]["rom"]["sha256"],
            "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
        )
        self.assertEqual(
            self.result["counts"],
            {
                "selector_callsites": 67,
                "immediate_selector_callsites": 66,
                "dynamic_selector_callsites": 1,
                "handler_pairs": 256,
            },
        )

    def test_sequence_two_links_exact_action_handlers_without_relabeling_dynamic_sequence(self):
        sequence_two = self.result["by_sequence"]["2"]
        self.assertEqual(sequence_two["hardcoded_sequence_id"], 2)
        self.assertEqual(sequence_two["resource_group_ids"], [2, 0, 0, 0])
        self.assertEqual(sequence_two["callsite_count"], 11)
        links = [
            link
            for callsite in sequence_two["callsites"]
            for link in callsite["handler_links"]
        ]
        self.assertEqual(
            [link["action_id"] for link in links],
            [1, 7, 50, 63, 69, 71, 73, 33, 54, 2, 4, 22, 62],
        )
        self.assertEqual(
            [link["display_name"] for link in links],
            [
                "分身术",
                "影分身术",
                "砂分身",
                "水分身术",
                "岩分身术",
                "岩分身术",
                "岩分身术",
                "兽人分身",
                "傀儡术",
                "瞬身术",
                "变化术",
                "解",
                "雾隐术",
            ],
        )
        self.assertEqual({link["dynamic_action_sequence_id"] for link in links}, {0})
        self.assertTrue(all(link["hardcoded_and_dynamic_sequences_are_distinct"] for link in links))
        self.assertTrue(all(link["natural_route_status"] == "not_runtime_proven" for link in links))

    def test_sequence_two_keeps_generic_callsites_unresolved(self):
        sequence_two = self.result["by_sequence"]["2"]
        unresolved = [
            callsite["selector_callsite"]
            for callsite in sequence_two["callsites"]
            if callsite["association_status"] == "unresolved"
        ]
        self.assertEqual(
            unresolved,
            ["0x0807BB90", "0x0807BD70", "0x0807C516"],
        )

    def test_handler_bank_validation_rejects_non_thumb_or_rom_mismatch(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        bank = json.loads((ROOT / "sequel/content/map-events/bank.json").read_text())
        bad_pointer = copy.deepcopy(bank)
        bad_pointer["entries"][1]["primary_handler_ptr"] &= ~1
        with self.assertRaisesRegex(ValueError, "Thumb"):
            self.module.validate_handler_bank(rom, bad_pointer)

        bad_bytes = copy.deepcopy(bank)
        bad_bytes["entries"][1]["primary_handler_ptr"] ^= 2
        with self.assertRaisesRegex(ValueError, "ROM bytes"):
            self.module.validate_handler_bank(rom, bad_bytes)

    def test_scope_does_not_promote_static_links_to_natural_runtime(self):
        self.assertEqual(
            self.result["scope"],
            {
                "hardcoded_selector_producer_links_complete": True,
                "handler_pair_associations_are_static_only": True,
                "natural_route_proven": False,
                "modified_rom_pixel_ab_proven": False,
            },
        )

    def test_tracked_evidence_matches_fresh_analysis(self):
        tracked = json.loads(
            (ROOT / "notes/battle-effect-hardcoded-selector-producers-20260802.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(tracked, self.result)


if __name__ == "__main__":
    unittest.main()
