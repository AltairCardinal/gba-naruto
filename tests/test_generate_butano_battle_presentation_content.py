#!/usr/bin/env python3
"""Tests for fixed-capacity Butano battle-presentation content."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GenerateButanoBattlePresentationContentTests(unittest.TestCase):
    def _content(self):
        from tools.generate_butano_battle_presentation_content import (
            load_battle_presentation_content,
        )

        return load_battle_presentation_content(ROOT)

    def test_loads_all_rom_bound_scripts_into_fixed_capacity_tables(self):
        content = self._content()
        self.assertEqual(len(content["definitions"]), 47)
        self.assertEqual(len(content["selector_instructions"]), 1741)
        self.assertEqual(len(content["cases"]), 400)
        self.assertEqual(len(content["commands"]), 3213)
        self.assertEqual(content["presentation_text_byte_count"], 48104)
        self.assertLessEqual(len(content["text_bytes"]), 65535)
        self.assertLessEqual(
            max(definition["selector_instruction_count"]
                for definition in content["definitions"]),
            255,
        )
        self.assertLessEqual(
            max(case["command_count"] for case in content["cases"]),
            255,
        )

    def test_battle_41_and_44_share_the_same_generated_schema(self):
        content = self._content()
        battle_41 = content["definitions"][41]
        battle_44 = content["definitions"][44]
        self.assertEqual(battle_41["case_count"], 2)
        self.assertEqual(battle_44["case_count"], 4)
        self.assertEqual(
            [content["cases"][battle_41["case_offset"] + index]["selector"]
             for index in range(battle_41["case_count"])],
            [1, 2],
        )
        self.assertEqual(
            [content["cases"][battle_44["case_offset"] + index]["selector"]
             for index in range(battle_44["case_count"])],
            [1, 2, 3, 4],
        )

    def test_unknown_payload_opcode_fails_closed(self):
        from tools.generate_butano_battle_presentation_content import (
            normalize_battle_presentation_manifest,
        )

        manifest = copy.deepcopy(self._content()["manifest"])
        command = manifest["battles"][41]["presentation_cases"][0]["commands"][0]
        command["opcode"] = "0x24"
        with self.assertRaisesRegex(ValueError, "unsupported presentation opcode"):
            normalize_battle_presentation_manifest(manifest)

    def test_generated_header_is_deterministic_and_has_no_dynamic_storage(self):
        from tools.generate_butano_battle_presentation_content import (
            generate_header,
        )

        content = self._content()
        first = generate_header(content)
        second = generate_header(content)
        self.assertEqual(first, second)
        self.assertIn(
            "std::array<battle_presentation_definition, 47>", first
        )
        self.assertIn(
            "std::array<battle_presentation_case, 400>", first
        )
        self.assertIn(
            "std::array<battle_presentation_command, 3213>", first
        )
        self.assertIn(
            "std::array<battle_presentation_selector_instruction, 1741>",
            first,
        )
        self.assertIn("return fallback;", first)
        self.assertNotIn("std::vector", first)
        self.assertNotIn("new ", first)


if __name__ == "__main__":
    unittest.main()
