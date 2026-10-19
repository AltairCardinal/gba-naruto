"""Tests for the ROM-backed battle-result content extractor."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.extract_battle_result_content import (
    EXPERIENCE_THRESHOLD_COUNT,
    EXPERIENCE_THRESHOLD_TABLE_FILE,
    REWARD_RECORD_COUNT,
    REWARD_RECORD_SIZE,
    REWARD_TABLE_FILE,
    SCENARIO_REWARD_MAP_COUNT,
    SCENARIO_REWARD_MAP_FILE,
    extract_battle_result_content,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_ROM = ROOT / "rom" / "base.gba"


class ExtractBattleResultContentTests(unittest.TestCase):
    def test_table_boundaries_are_exact(self):
        self.assertEqual(REWARD_TABLE_FILE, 0x59EAE0)
        self.assertEqual(REWARD_RECORD_SIZE, 0x18)
        self.assertEqual(REWARD_RECORD_COUNT, 112)
        self.assertEqual(
            REWARD_TABLE_FILE + REWARD_RECORD_SIZE * REWARD_RECORD_COUNT,
            EXPERIENCE_THRESHOLD_TABLE_FILE,
        )
        self.assertEqual(EXPERIENCE_THRESHOLD_COUNT, 63)
        self.assertEqual(SCENARIO_REWARD_MAP_FILE, 0x348DAC)
        self.assertEqual(SCENARIO_REWARD_MAP_COUNT, 48)

    def test_extracts_known_cross_scenario_rewards_and_thresholds(self):
        bank = extract_battle_result_content(BASE_ROM.read_bytes())
        self.assertEqual(
            (
                bank["reward_records"][104]["mission_experience"],
                bank["reward_records"][104]["round_bonus_experience"],
                bank["reward_records"][104]["round_limit"],
            ),
            (100, 25, 3),
        )
        self.assertEqual(
            (
                bank["reward_records"][24]["mission_experience"],
                bank["reward_records"][24]["round_bonus_experience"],
                bank["reward_records"][24]["round_limit"],
            ),
            (125, 75, 8),
        )
        self.assertEqual(bank["scenario_reward_record_indices"][41], 104)
        self.assertEqual(bank["scenario_reward_record_indices"][9], 24)
        self.assertEqual(
            (
                bank["experience_thresholds"][1]["per_level_increment"],
                bank["experience_thresholds"][1]["base_threshold"],
            ),
            (15, 250),
        )
        self.assertEqual(
            (
                bank["experience_thresholds"][2]["per_level_increment"],
                bank["experience_thresholds"][2]["base_threshold"],
            ),
            (15, 180),
        )
        self.assertEqual(
            (
                bank["experience_thresholds"][3]["per_level_increment"],
                bank["experience_thresholds"][3]["base_threshold"],
            ),
            (15, 150),
        )


if __name__ == "__main__":
    unittest.main()
