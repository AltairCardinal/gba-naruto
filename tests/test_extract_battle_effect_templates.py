import unittest
from pathlib import Path

from tools.extract_battle_effect_templates import ENTRY_COUNT, ENTRY_SIZE, TABLE_OFFSET, build_bank


class BattleEffectTemplateExtractionTests(unittest.TestCase):
    def test_extracts_lossless_byte_level_records(self):
        rom = bytearray(TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE)
        for index in range(ENTRY_COUNT):
            start = TABLE_OFFSET + index * ENTRY_SIZE
            rom[start:start + ENTRY_SIZE] = bytes((index + n) & 0xFF for n in range(ENTRY_SIZE))
        bank = build_bank(bytes(rom))
        self.assertEqual("runtime_verified", bank["verification"])
        self.assertEqual(ENTRY_COUNT, len(bank["entries"]))
        self.assertEqual(bytes(rom[TABLE_OFFSET:TABLE_OFFSET + ENTRY_SIZE]).hex(), bank["entries"][0]["raw_hex"])
        self.assertEqual(int.from_bytes(rom[TABLE_OFFSET + 14:TABLE_OFFSET + 16], "little"), bank["entries"][0]["per_level_growth"])

    def test_names_ui_proven_active_action_fields_without_swapping_hits_and_distance(self):
        root = Path(__file__).resolve().parents[1]
        bank = build_bank((root / "rom/base.gba").read_bytes())
        fields = {field["offset"]: field for field in bank["entry_format"]["fields"]}
        self.assertEqual(fields[0]["semantic"], "cost_kind")
        self.assertEqual(fields[1]["semantic"], "display_animation_family")
        self.assertEqual(fields[2]["semantic"], "effect_type_and_flags")
        self.assertEqual(fields[3]["semantic"], "target_policy_and_flags")
        self.assertEqual(fields[4]["semantic"], "potency")
        self.assertEqual(fields[5]["semantic"], "hit_count")
        self.assertEqual(fields[6]["semantic"], "success_rate_percent")
        self.assertEqual(fields[7]["semantic"], "distance_and_line_flags")
        self.assertEqual(fields[8]["semantic"], "area_range_and_shape_flags")
        self.assertEqual(fields[9]["semantic"], "duration_turns")
        self.assertEqual(fields[10]["semantic"], "resource_cost_low_byte")
        self.assertEqual(fields[11]["semantic"], "resource_cost_high_byte")
        lion_barrage = bank["entries"][19]
        self.assertEqual(lion_barrage["cost_kind"], 2)
        self.assertEqual(lion_barrage["effect_code"], 1)
        self.assertEqual(lion_barrage["effect_flags"], 0)
        self.assertEqual(lion_barrage["target_policy"], 2)
        self.assertEqual(lion_barrage["target_flags"], 0)
        self.assertEqual(lion_barrage["potency"], 10)
        self.assertEqual(lion_barrage["hit_count"], 3)
        self.assertEqual(lion_barrage["distance_and_line_flags"], 1)
        self.assertEqual(lion_barrage["resource_cost_value"], 80)
        self.assertEqual(lion_barrage["resource_cost_u16"], 80)


if __name__ == "__main__":
    unittest.main()
