import unittest

from tools.extract_skill_templates import ENTRY_COUNT, ENTRY_SIZE, TABLE_END, TABLE_OFFSET, build_bank


class SkillTemplateExtractionTests(unittest.TestCase):
    def test_boundaries_and_lossless_records(self):
        self.assertEqual(94, ENTRY_COUNT)
        self.assertEqual(TABLE_END, TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE)
        rom = bytearray(TABLE_END)
        for index in range(ENTRY_COUNT):
            start = TABLE_OFFSET + index * ENTRY_SIZE
            rom[start:start + ENTRY_SIZE] = bytes((index + n) & 0xFF for n in range(ENTRY_SIZE))
        bank = build_bank(bytes(rom))
        self.assertEqual("runtime_verified", bank["verification"])
        self.assertEqual("ninja_tool_numeric_templates", bank["identity"])
        self.assertIn("ninja-tool", bank["description"])
        self.assertEqual("ninja_tool_template", bank["entries"][1]["template_identity"])
        self.assertEqual(1, bank["entries"][1]["ninja_tool_id"])
        self.assertEqual(bytes(rom[TABLE_OFFSET:TABLE_OFFSET + 16]).hex(), bank["entries"][0]["raw_hex"])
        self.assertEqual(TABLE_END - ENTRY_SIZE, bank["entries"][-1]["_raw_offset"])

        fields = {field["offset"]: field for field in bank["entry_format"]["fields"]}
        self.assertEqual(fields[0]["initializer_destination"], 1)
        self.assertIsNone(fields[1]["initializer_destination"])
        for offset in range(2, 10):
            self.assertEqual(fields[offset]["initializer_destination"], offset)
        self.assertEqual(fields[10]["separate_consumer"], "0x0808FF7C")
        self.assertEqual(fields[11]["separate_consumer"], "0x0808FF88")
        self.assertEqual(fields[10]["semantic"], "parent_ninja_tool_id")
        self.assertEqual(fields[11]["semantic"], "required_material_id")
        self.assertNotEqual(
            fields[11].get("semantic"),
            "eligible_ninja_tool_id",
        )

    def test_exposes_runtime_action_semantics_without_treating_relationship_bytes_as_cost(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        bank = build_bank((root / "rom/base.gba").read_bytes())
        fields = {field["offset"]: field for field in bank["entry_format"]["fields"]}
        self.assertEqual(fields[0]["semantic"], "display_animation_family")
        self.assertEqual(fields[2]["semantic"], "effect_type_and_flags")
        self.assertEqual(fields[3]["semantic"], "target_policy_and_flags")
        self.assertEqual(fields[7]["semantic"], "distance_and_line_flags")
        self.assertEqual(fields[8]["semantic"], "area_range_and_shape_flags")

        tool = bank["entries"][1]
        self.assertEqual(tool["runtime_cost_kind"], 5)
        self.assertEqual(tool["effect_code"], 1)
        self.assertEqual(tool["effect_flags"], 0)
        self.assertEqual(tool["target_policy"], 2)
        self.assertEqual(tool["target_flags"], 0)
        self.assertNotIn("resource_cost_u16", tool)

        eight_way = bank["entries"][2]
        wing = bank["entries"][5]
        aluminum = bank["entries"][8]
        self.assertEqual(
            (eight_way["parent_ninja_tool_id"], eight_way["required_material_id"]),
            (1, 3),
        )
        self.assertEqual(
            (wing["parent_ninja_tool_id"], wing["required_material_id"]),
            (1, 1),
        )
        self.assertEqual(
            (aluminum["parent_ninja_tool_id"], aluminum["required_material_id"]),
            (1, 2),
        )


if __name__ == "__main__":
    unittest.main()
