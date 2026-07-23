#!/usr/bin/env python3
"""Lock code-proven non-UI semantics in the 94-record skill table."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.extract_skill_templates import build_bank


ROOT = Path(__file__).resolve().parents[1]
BASE_ROM = ROOT / "rom" / "base.gba"


class SkillRelationshipSemanticsTests(unittest.TestCase):
    def test_extractor_names_code_proven_relationship_fields(self):
        bank = build_bank(BASE_ROM.read_bytes())
        fields = {field["offset"]: field for field in bank["entry_format"]["fields"]}
        self.assertEqual(fields[0]["semantic"], "display_animation_family")
        self.assertEqual(fields[10]["semantic"], "parent_ninja_tool_id")
        self.assertEqual(fields[11]["semantic"], "eligible_ninja_tool_id")
        self.assertEqual(fields[12]["semantic"], "eligibility_whitelist_id_0")
        self.assertEqual(fields[13]["semantic"], "eligibility_whitelist_id_1")
        self.assertEqual(bank["entries"][2]["parent_ninja_tool_id"], 1)
        self.assertEqual(bank["entries"][2]["eligible_ninja_tool_id"], 3)

    def test_extractor_records_natural_detail_panel_semantics(self):
        bank = build_bank(BASE_ROM.read_bytes())
        fields = {field["offset"]: field for field in bank["entry_format"]["fields"]}
        self.assertEqual(bank["verification"], "runtime_verified")
        self.assertEqual(fields[4]["semantic"], "attack_power")
        self.assertEqual(fields[5]["semantic"], "hit_count")
        self.assertEqual(fields[6]["semantic"], "success_rate_percent")
        self.assertEqual(fields[7]["semantic"], "distance_and_line_shape")
        self.assertEqual(fields[8]["semantic"], "range")
        skill = bank["entries"][1]
        self.assertEqual(skill["attack_power"], 6)
        self.assertEqual(skill["hit_count"], 3)
        self.assertEqual(skill["success_rate_percent"], 90)
        self.assertEqual(skill["distance_and_line_shape"], 0x83)
        self.assertEqual(skill["range"], 1)

    def test_parent_child_consumer_reads_offsets_0a_and_0b(self):
        rom = BASE_ROM.read_bytes()
        self.assertEqual(rom[0x8FFC4:0x8FFC8], (0x08545BE4).to_bytes(4, "little"))
        self.assertEqual(rom[0x8FF7C:0x8FF7E], bytes.fromhex("917a"))  # ldrb r1,[r2,#0x0A]
        self.assertEqual(rom[0x8FF88:0x8FF8A], bytes.fromhex("d67a"))  # ldrb r6,[r2,#0x0B]

    def test_whitelist_consumer_reads_offsets_0c_and_0d(self):
        rom = BASE_ROM.read_bytes()
        self.assertEqual(rom[0x8FC38:0x8FC3C], (0x08545BE4).to_bytes(4, "little"))
        self.assertEqual(rom[0x8FC2E:0x8FC30], bytes.fromhex("007b"))  # ldrb r0,[r0,#0x0C]
        # The loop starts at record +0x0C and checks exactly two bytes.
        self.assertEqual(rom[0x8FC3C:0x8FC52], bytes.fromhex("00220c335018c0180078a042f4d0501c0004020c012a"))

    def test_display_consumer_indexes_byte_zero_by_skill_id(self):
        rom = BASE_ROM.read_bytes()
        self.assertEqual(rom[0x78F04:0x78F08], (0x08545BE4).to_bytes(4, "little"))
        self.assertEqual(rom[0x78F10:0x78F18], bytes.fromhex("0978090109180f78"))
        self.assertEqual(rom[0x953A0:0x953A4], (0x08545BE4).to_bytes(4, "little"))
        self.assertEqual(rom[0x953AE:0x953B6], bytes.fromhex("0978090109180f78"))


if __name__ == "__main__":
    unittest.main()
