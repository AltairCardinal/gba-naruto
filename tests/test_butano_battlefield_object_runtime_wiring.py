#!/usr/bin/env python3
"""Static wiring guard for battlefield-object domain and expiry presentation."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ButanoBattlefieldObjectRuntimeWiringTests(unittest.TestCase):
    def test_runtime_refreshes_object_telemetry_from_controller_snapshot(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("battle_scene_object_snapshot object_state", source)
        self.assertIn("controller.object_snapshot()", source)
        self.assertIn(
            "update_battlefield_object_expiry_sprite(",
            source,
        )
        state_refresh = source.rindex(
            "state = controller.snapshot();"
        )
        training_refresh = source.index(
            "training_state = controller.training_snapshot();",
            state_refresh,
        )
        object_refresh = source.index(
            "object_state = controller.object_snapshot();",
            training_refresh,
        )
        self.assertLess(state_refresh, training_refresh)
        self.assertLess(training_refresh, object_refresh)

    def test_runtime_does_not_render_grid_metadata_as_cursor_sprites(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertNotIn("object_sprites", source)
        self.assertIn(
            "update_battlefield_object_expiry_sprite(",
            source,
        )
        self.assertRegex(
            source,
            r"bn::sprite_items::\s*battlefield_object_type_2_expiry",
        )

    def test_primary_runtime_fixture_equips_real_explosive_tag(self):
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
            "character_equipped_tools[1][0] = 67;",
            fixture,
        )
        self.assertIn(
            "request.load_policy."
            "character_equipped_tools[1][1] = 11;",
            fixture,
        )
        self.assertIn(
            "request.load_policy."
            "character_equipped_tools[1][2] = 37;",
            fixture,
        )
        main = (ROOT / "butano-sequel/src/main.cpp").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            main,
            r"campaign_checkpoint\.characters\[1\]"
            r"\.equipped_tools\s*=\s*\{\s*67,\s*11,\s*37,",
        )

    def test_runtime_latches_only_consumed_object_presentation(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "battlefield_object_telemetry_latch",
            source,
        )
        self.assertRegex(
            source,
            r"capture_telemetry\([\s\S]{0,900}"
            r"const battlefield_object_telemetry_latch&",
        )
        self.assertRegex(
            source,
            r"presentation_started\s*&&\s*"
            r"presentation_event\s*"
            r"\.has_battlefield_object"
            r"[\s\S]{0,500}object_telemetry\.presented\s*=\s*true",
        )
        self.assertNotIn(
            "result.player.object_event_count",
            source,
        )
        self.assertNotIn(
            "result.ai.turn.object_event_count",
            source,
        )

    def test_type_2_expiry_is_not_dropped_by_the_controller(self):
        source = (
            ROOT
            / "butano-sequel/game/include/konoha/"
            "battle_scene_controller.h"
        ).read_text(encoding="utf-8")
        self.assertNotRegex(
            source,
            r"kind\s*==\s*"
            r"battlefield_object_tick_kind::"
            r"type_2_expired\s*\)\s*\{\s*continue;",
        )
        self.assertIn(
            "battlefield_object_tile_index_end",
            (
                ROOT
                / "butano-sequel/game/include/konoha/"
                "battle_scene_presentation.h"
            ).read_text(encoding="utf-8"),
        )

    def test_runtime_keeps_large_scene_state_out_of_the_gba_stack(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        for declaration in (
            r"static\s+battle_scene_snapshot<12>\s+state",
            r"static\s+battle_scene_object_snapshot\s+object_state",
            r"static\s+battle_scene_control_result\s+result",
        ):
            self.assertRegex(
                source,
                rf"BN_DATA_EWRAM(?:_BSS)?"
                rf"[\s\S]{{0,100}}{declaration}",
            )

    def test_mgba_route_observes_domain_object_then_real_explosion(self):
        script = (
            ROOT / "tools/butano/mgba_battlefield_object_runtime.lua"
        )
        self.assertTrue(script.is_file())
        source = script.read_text(encoding="utf-8")
        for token in (
            "MGBA_OBJECT_OUTPUT_DIR",
            "MGBA_OBJECT_DONE_MARKER",
            "MGBA_OBJECT_TELEMETRY_ADDRESS",
            "selected_action_id == 67",
            "telemetry.object_count == 1",
            "telemetry.presentation_object == 1",
            "telemetry.presentation_object_damage > 0",
            "telemetry.presentation_busy == 1",
            "object-explosion.png",
        ):
            self.assertIn(token, source)
        self.assertNotIn("object-marker.png", source)

    def test_mgba_type_2_route_waits_for_real_expiry_presentation(self):
        script = (
            ROOT
            / "tools/butano/"
            "mgba_battlefield_object_type_2_runtime.lua"
        )
        self.assertTrue(script.is_file())
        source = script.read_text(encoding="utf-8")
        for token in (
            "selected_action_id == 37",
            "presentation_object_kind == 2",
            "presentation_object_damage == 0",
            "object_count == 0",
            "presentation_busy == 1",
            "type-2-expiry.png",
            "COMMAND_END_ACTION",
        ):
            self.assertIn(token, source)
        self.assertNotIn("object-marker.png", source)


if __name__ == "__main__":
    unittest.main()
