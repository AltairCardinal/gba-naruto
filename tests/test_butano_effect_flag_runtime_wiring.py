#!/usr/bin/env python3
"""Static guards for the visible effect-flag runtime route."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ButanoEffectFlagRuntimeWiringTests(unittest.TestCase):
    def test_primary_runtime_fixture_equips_poison_shuriken(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        start = source.index(
            "battle_runtime_scene_exit run_battle_41_scene()"
        )
        end = source.index(
            "battle_runtime_scene_exit run_battle_09_scene()",
            start,
        )
        fixture = source[start:end]
        self.assertIn(
            "request.load_policy."
            "character_equipped_tools[1][1] = 11;",
            fixture,
        )

    def test_runtime_exports_cursor_unit_domain_state(self):
        header = (
            ROOT / "butano-sequel/game/include/konoha/"
            "battle_runtime_scene.h"
        ).read_text(encoding="utf-8")
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        for field in (
            "cursor_unit_id",
            "cursor_unit_attack",
            "cursor_unit_defense",
            "cursor_unit_agility",
            "cursor_unit_status_count",
            "cursor_unit_active",
            "cursor_unit_hp",
        ):
            self.assertIn(field, header)
            self.assertIn(f"output.{field}", source)
        self.assertIn(
            "if(state.cursor == unit.position &&",
            source,
        )
        self.assertIn('detail_status += " ST";', source)
        self.assertIn("unit->status_count", source)

    def test_mgba_route_requires_real_poison_state(self):
        script = (
            ROOT / "tools/butano/mgba_effect_flag_runtime.lua"
        )
        self.assertTrue(script.is_file())
        source = script.read_text(encoding="utf-8")
        for token in (
            "MGBA_EFFECT_FLAG_OUTPUT_DIR",
            "MGBA_EFFECT_FLAG_DONE_MARKER",
            "MGBA_EFFECT_FLAG_TELEMETRY_ADDRESS",
            "selected_action_id == 11",
            "cursor_unit_id == 2",
            "cursor_unit_status_count == 3",
            "cursor_unit_active == 0",
            "cursor_unit_hp == 0",
            "last_resolved_action_id == 11",
            "poison-resolved.png",
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
