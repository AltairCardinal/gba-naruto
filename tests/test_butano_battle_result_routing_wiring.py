import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_HEADER = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "battle_runtime_scene.h"
)
RUNTIME_SOURCE = (
    ROOT
    / "butano-sequel"
    / "game"
    / "src"
    / "battle_runtime_scene.cpp"
)
MAIN_SOURCE = ROOT / "butano-sequel" / "src" / "main.cpp"
FIXTURE_SOURCE = (
    ROOT
    / "butano-sequel"
    / "game"
    / "src"
    / "scenario_43_scene.cpp"
)
ROUTE_HEADER = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "battle_campaign_route.h"
)
RESULT_ROUTE_SCRIPT = (
    ROOT
    / "tools"
    / "butano"
    / "mgba_battle_result_routing.lua"
)


class ButanoBattleResultRoutingWiringTest(unittest.TestCase):
    def test_visible_scene_has_no_hidden_next_battle_input(self):
        header = RUNTIME_HEADER.read_text(encoding="utf-8")
        source = RUNTIME_SOURCE.read_text(encoding="utf-8")

        self.assertNotIn("allow_next_battle", header)
        self.assertNotIn("allow_next_battle", source)
        self.assertNotIn("battle_runtime_scene_next_gate", header)
        self.assertNotIn("battle_runtime_scene_next_gate", source)
        self.assertNotIn("bn::keypad::select_pressed()", source)

    def test_complete_phase_returns_controller_outcome_without_exit_page(self):
        source = RUNTIME_SOURCE.read_text(encoding="utf-8")

        self.assertRegex(
            source,
            r"(?s)state = controller\.snapshot\(\);\s*"
            r"if\(state\.phase ==\s*"
            r"battle_scene_phase::complete\)\s*\{.*?"
            r"return finish_scene\(\s*"
            r"battle_runtime_exit_for_outcome\(\s*"
            r"state\.outcome\)\);\s*\}",
        )
        self.assertNotIn('"A EXIT"', source)

    def test_complete_phase_releases_visible_scene_before_task_menu(self):
        source = RUNTIME_SOURCE.read_text(encoding="utf-8")
        first_snapshot = source.index("state = controller.snapshot();")
        terminal_snapshot = source.index(
            "state = controller.snapshot();",
            first_snapshot + 1,
        )
        terminal_branch = source[
            terminal_snapshot:
            source.index(
                "if(battle_phase_uses_full_screen_result(",
                terminal_snapshot,
            )
        ]

        for token in (
            "range_overlay.reset();",
            "ui_renderer.reset();",
            "portrait_renderer.reset();",
            "message_window_renderer.reset();",
            "combat_stage_renderer.reset();",
            "text_sprites.clear();",
            "script_glyph_sprites.clear();",
            "cursor_shadow.reset();",
            "cursor.reset();",
            "map.reset();",
            "bn::core::update();",
        ):
            with self.subTest(token=token):
                self.assertIn(token, terminal_branch)

        self.assertLess(
            terminal_branch.index("text_sprites.clear();"),
            terminal_branch.index("return finish_scene("),
        )
        self.assertLess(
            terminal_branch.index("bn::core::update();"),
            terminal_branch.index("return finish_scene("),
        )

    def test_campaign_writeback_is_victory_transaction(self):
        source = RUNTIME_SOURCE.read_text(encoding="utf-8")

        self.assertIn(
            "battle_runtime_exit_commits_campaign(exit)",
            source,
        )

    def test_full_screen_postbattle_phases_do_not_restore_the_map_bg(self):
        source = RUNTIME_SOURCE.read_text(encoding="utf-8")

        policy = source[
            source.index(
                "battle_phase_uses_full_screen_result("
            ):
            source.index(
                "void dispatch_battle_combat_stage_audio("
            )
        ]
        for phase in (
            "battle_scene_phase::outcome",
            "battle_scene_phase::result",
            "battle_scene_phase::level_up",
            "battle_scene_phase::training",
            "battle_scene_phase::complete",
        ):
            with self.subTest(phase=phase):
                self.assertIn(phase, policy)

        self.assertRegex(
            source,
            r"if\(battle_phase_uses_full_screen_result\(\s*"
            r"state\.phase\)\s*&&\s*map\)",
        )
        self.assertRegex(
            source,
            r"resource_coordinator\.current\(\)\s*==\s*"
            r"battle_visual_resource_cohort::map\s*&&\s*"
            r"!\s*battle_phase_uses_full_screen_result\(\s*"
            r"state\.phase\)",
        )
        self.assertRegex(
            source,
            r"if\(request\.campaign &&\s*"
            r"battle_runtime_exit_commits_campaign\(exit\) &&\s*"
            r"scene_progression\.commit",
        )

    def test_callers_advance_only_from_battle_result(self):
        main = MAIN_SOURCE.read_text(encoding="utf-8")
        fixture = FIXTURE_SOURCE.read_text(encoding="utf-8")
        route = ROUTE_HEADER.read_text(encoding="utf-8")

        self.assertRegex(
            main,
            r"advance_battle_campaign_stage\(\s*"
            r"campaign,\s*battle_exit,\s*"
            r"campaign_route_workspace\)",
        )
        self.assertIn(
            "battle_runtime_exit_advances_campaign(",
            route,
        )
        self.assertNotIn("run_battle_09_scene()", fixture)
        self.assertNotIn(
            "battle_runtime_scene_exit::next_battle",
            main,
        )
        self.assertNotIn(
            "battle_runtime_scene_exit::next_battle",
            fixture,
        )

    def test_runtime_probe_rejects_select_as_level_skip(self):
        self.assertTrue(RESULT_ROUTE_SCRIPT.is_file())
        script = RESULT_ROUTE_SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MGBA_BATTLE_RESULT_ROUTING_OUTPUT_DIR",
            "MGBA_BATTLE_RESULT_ROUTING_DONE_MARKER",
            "MGBA_BATTLE_RESULT_ROUTING_TELEMETRY_ADDRESS",
            "C.GBA_KEY.SELECT",
            "phase_before_select",
            "battle_id_before_select",
            '"status":"select-does-not-route"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)


if __name__ == "__main__":
    unittest.main()
