#!/usr/bin/env python3
"""Lock player-visible capacity names to the character overview consumer."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.extract_character_definitions import extract_character_definitions
from tools.extract_character_growth import build_bank


ROOT = Path(__file__).resolve().parents[1]
BASE_ROM = ROOT / "rom" / "base.gba"


class CharacterOverviewFieldSemanticsTests(unittest.TestCase):
    def test_overview_renderer_orders_chakra_before_ninja_tool_capacity(self):
        rom = BASE_ROM.read_bytes()

        # 0x08089B82 emits seven labels in rows 0,2,...,12.  Its literal pool
        # points to 体力/查克拉/攻击力/防御力/敏捷度/移动力/忍具数 in that order.
        self.assertEqual(
            rom[0x89D58:0x89D74],
            bytes.fromhex(
                "908e34089c8e3408a88e3408b08e3408"
                "b88e3408c08e3408c88e3408"
            ),
        )
        self.assertEqual(rom[0x348E90:0x348E94], bytes.fromhex("96e29144"))
        self.assertEqual(rom[0x348E9C:0x348EA2], bytes.fromhex("89e6906990aa"))
        self.assertEqual(rom[0x348EC8:0x348ECE], bytes.fromhex("94c98fdc95fa"))

        # Numeric rows consume template +0E, +08, +02, +03, +04, +05, +06.
        # Therefore the second label (查克拉) is +08 and the last (忍具数) is +06.
        numeric_loads = {
            0x89BF4: bytes.fromhex("f889"),  # ldrh r0, [r7, #0x0E]
            0x89C10: bytes.fromhex("387a"),  # ldrb r0, [r7, #0x08]
            0x89C26: bytes.fromhex("b878"),  # ldrb r0, [r7, #0x02]
            0x89C3E: bytes.fromhex("f878"),  # ldrb r0, [r7, #0x03]
            0x89C56: bytes.fromhex("3879"),  # ldrb r0, [r7, #0x04]
            0x89C6E: bytes.fromhex("7879"),  # ldrb r0, [r7, #0x05]
            0x89C86: bytes.fromhex("b879"),  # ldrb r0, [r7, #0x06]
        }
        for offset, expected in numeric_loads.items():
            self.assertEqual(rom[offset:offset + 2], expected)

    def test_units_bank_exposes_capacity_names(self):
        bank = extract_character_definitions(BASE_ROM.read_bytes())
        self.assertEqual(bank["player_visible_semantics"]["template_06"], "ninja_tool_capacity")
        self.assertEqual(bank["player_visible_semantics"]["template_08"], "chakra_capacity")
        entry = bank["entries"][1]
        self.assertEqual(entry["ninja_tool_capacity_base"], 5)
        self.assertEqual(entry["chakra_capacity_base"], 5)

    def test_growth_bank_exposes_corresponding_capacity_names(self):
        bank = build_bank(BASE_ROM.read_bytes())
        fields = {field["offset"]: field for field in bank["entry_format"]["fields"]}
        self.assertEqual(fields[2]["player_label"], "chakra_capacity")
        self.assertEqual(fields[12]["player_label"], "ninja_tool_capacity")

    def test_runtime_artifact_records_resolved_order(self):
        artifact = json.loads(
            (ROOT / "artifacts/runtime-checkpoints/unit-overview-field-correlation.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(artifact["strong_correlations"]["template_06"], "ninja_tool_capacity")
        self.assertEqual(artifact["strong_correlations"]["template_08"], "chakra_capacity")
        self.assertEqual(artifact["unresolved_order"], [])


if __name__ == "__main__":
    unittest.main()
