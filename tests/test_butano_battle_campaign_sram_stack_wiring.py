import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAVE_HEADER = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "battle_campaign_save.h"
)
SRAM_HEADER = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "battle_campaign_sram.h"
)
SRAM_SOURCE = (
    ROOT
    / "butano-sequel"
    / "game"
    / "src"
    / "battle_campaign_sram.cpp"
)


class BattleCampaignSramStackWiringTest(unittest.TestCase):
    def test_codec_exposes_caller_owned_decode_workspace(self):
        header = SAVE_HEADER.read_text(encoding="utf-8")

        self.assertIn(
            "decode_battle_campaign_slot_into(",
            header,
        )
        self.assertIn(
            "load_latest_battle_campaign_slot_into(",
            header,
        )
        self.assertIn(
            "next_battle_campaign_save_target_into(",
            header,
        )

    def test_sram_runtime_reuses_ewram_decode_slots(self):
        header = SRAM_HEADER.read_text(encoding="utf-8")
        source = SRAM_SOURCE.read_text(encoding="utf-8")

        self.assertIn("decoded_slots", header)
        self.assertIn(
            "load_latest_battle_campaign_slot_into(",
            source,
        )
        self.assertIn(
            "next_battle_campaign_save_target_into(",
            source,
        )
        self.assertIn(
            "decode_battle_campaign_slot_into(",
            source,
        )
        self.assertNotIn(
            "const battle_campaign_save_decode_result loaded =",
            source,
        )
        self.assertNotIn(
            "const battle_campaign_save_decode_result verified =",
            source,
        )


if __name__ == "__main__":
    unittest.main()
