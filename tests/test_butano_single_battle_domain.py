import unittest
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ROOT / "butano-sequel" / "game" / "include" / "konoha"
SOURCE = ROOT / "butano-sequel" / "game" / "src"
GRAPHICS = ROOT / "butano-sequel" / "graphics"


def production_files():
    return sorted(INCLUDE.glob("*.h")) + sorted(SOURCE.glob("*.cpp"))


class ButanoSingleBattleDomainTest(unittest.TestCase):
    def test_legacy_scenario_41_facade_is_not_production_code(self):
        for path in (
            INCLUDE / "scenario_41_battle.h",
            INCLUDE / "scenario_41_extended_layers.h",
            INCLUDE / "scenario_41_prebattle_frames.h",
            INCLUDE / "scenario_41_presenter.h",
            INCLUDE / "scenario_41_scene.h",
            SOURCE / "scenario_41_scene.cpp",
        ):
            with self.subTest(path=path.name):
                self.assertFalse(path.exists())

        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in production_files()
        )
        self.assertNotIn("class scenario_41_battle", source)
        self.assertNotIn("run_scenario_41_scene", source)

    def test_legacy_scenario_41_state_screens_are_not_built_as_assets(self):
        remaining = {
            path.name
            for path in GRAPHICS.glob("scenario_41_*")
        }
        self.assertEqual(
            remaining,
            {
                "scenario_41_cursor.bmp",
                "scenario_41_cursor.json",
                "scenario_41_cursor_shadow.bmp",
                "scenario_41_cursor_shadow.json",
            },
        )

    def test_interactive_battle_cannot_load_precomposed_screen_assets(self):
        runtime = (
            SOURCE / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        direct_background_headers = re.findall(
            r'#include "bn_regular_bg_items_([^"]+)\.h"',
            runtime,
        )
        self.assertEqual(
            direct_background_headers,
            [
                "battle_action_16_cutin_dialogue",
                "battle_action_16_cutin_portrait",
                "battle_action_16_movie_actor",
                "battle_action_16_movie_dialogue",
                "battle_action_16_movie_fire",
                "battle_action_16_movie_streaks",
                "battle_duel_forest",
            ],
        )
        for forbidden in (
            "regular_bg_items::scenario_",
            "scenario_41_prebattle_frames",
            "reference_frame",
            "screenshot",
            "golden_route",
            "confirmation_bottom",
            "confirmation_middle",
            "confirmation_top",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, runtime)

        forbidden_assets = sorted(
            path.name
            for pattern in (
                "scenario_*frame*",
                "scenario_*screen*",
                "scenario_*prebattle*",
                "scenario_*confirmation*",
                "scenario_*attack*",
                "scenario_*result*",
            )
            for path in GRAPHICS.glob(pattern)
        )
        self.assertEqual(forbidden_assets, [])

    def test_production_tree_has_one_action_resolver(self):
        self.assertFalse((INCLUDE / "battle_abilities.h").exists())
        self.assertFalse((INCLUDE / "battle_effects.h").exists())

        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in production_files()
        )
        for forbidden in (
            "ability_resolver",
            "ability_definition<",
            "apply_effect_chain",
            "substitution_ready",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

        self.assertEqual(source.count("class deterministic_rng"), 1)
        self.assertTrue((INCLUDE / "battle_random.h").is_file())

    def test_embedded_self_test_uses_read_only_domain_preview(self):
        self_test = (
            ROOT
            / "butano-sequel"
            / "benchmark"
            / "src"
            / "self_test.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "battle_action_resolver::preview_units",
            self_test,
        )
        self.assertNotIn(
            "battle_action_resolver::resolve_draft",
            self_test,
        )

    def test_incoming_reactions_use_one_rom_ordered_selector(self):
        action_system = (
            INCLUDE / "battle_action_system.h"
        ).read_text(encoding="utf-8")
        self.assertRegex(
            action_system,
            r"inline constexpr std::array<std::uint8_t, 6>\s+"
            r"incoming_reaction_priority",
        )
        priority_start = action_system.index(
            "incoming_reaction_priority"
        )
        priority_end = action_system.index("}};", priority_start)
        priority = action_system[priority_start:priority_end]
        offsets = [
            priority.index(code)
            for code in (
                "0x04",
                "0x0A",
                "0x09",
                "0x10",
                "0x16",
                "0x19",
            )
        ]
        self.assertEqual(offsets, sorted(offsets))
        self.assertEqual(
            action_system.count("_select_incoming_reaction("),
            2,
        )

    def test_ai_executes_inside_its_existing_transaction_workspace(self):
        ai_flow = (
            INCLUDE / "battle_ai_turn_flow.h"
        ).read_text(encoding="utf-8")
        for required in (
            "battle_resource_commands::commit_in_place(",
            "battle_action_execution::resolve_in_place(",
            "battle_turn_flow::after_effects_in_place(",
            "battle_turn_flow::complete_defense_in_place(",
        ):
            with self.subTest(required=required):
                self.assertIn(required, ai_flow)
        self.assertNotIn(
            "battle_action_execution::resolve(\n",
            ai_flow,
        )
        self.assertNotIn(
            "battle_turn_flow::complete_defense(\n",
            ai_flow,
        )

    def test_runtime_reuses_one_transaction_for_resources_and_defense(self):
        encounter = (
            INCLUDE / "battle_encounter_runtime.h"
        ).read_text(encoding="utf-8")
        for required in (
            "next_flow.confirm_chakra_in_place(",
            "next_flow.confirm_rest_in_place(",
        ):
            with self.subTest(required=required):
                self.assertIn(required, encounter)

        turn_flow = (
            INCLUDE / "battle_turn_flow.h"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "battle_defense_preparation::commit_in_place(",
            turn_flow,
        )

    def test_terrain_class_is_one_shared_domain_semantic(self):
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in production_files()
        )
        for forbidden in (
            "directional_mask",
            "set_directional_mask",
            "grid_direction_up",
            "battle_map_direction_up",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

        pathfinder = (
            INCLUDE / "grid_pathfinder.h"
        ).read_text(encoding="utf-8")
        player_flow = (
            INCLUDE / "battle_player_action_flow.h"
        ).read_text(encoding="utf-8")
        ai = (
            INCLUDE / "battle_ai.h"
        ).read_text(encoding="utf-8")
        threat_field = (
            INCLUDE / "battle_ai_candidate_field.h"
        ).read_text(encoding="utf-8")
        self.assertIn("set_terrain_class(", pathfinder)
        self.assertIn("terrain_class(", pathfinder)
        for consumer in (player_flow, ai, threat_field):
            self.assertIn(
                "battle_terrain_traversal_limits(",
                consumer,
            )

    def test_postbattle_training_is_a_controller_owned_flow(self):
        controller = (
            INCLUDE / "battle_scene_controller.h"
        ).read_text(encoding="utf-8")
        runtime_header = (
            INCLUDE / "battle_runtime_scene.h"
        ).read_text(encoding="utf-8")
        runtime = (
            SOURCE / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn(
            '#include "konoha/battle_training_flow.h"',
            controller,
        )
        self.assertIn("battle_scene_phase::training", controller)
        self.assertIn(
            "_training.confirm(\n"
            "                    _progression_roster)",
            controller,
        )
        self.assertNotIn("train_primary_action(", runtime)
        self.assertNotIn("train_secondary_passive(", runtime)
        self.assertIn(
            "battle_training_entry_kind::\n"
            "                            secondary_passive",
            runtime,
        )
        self.assertIn('detail_status += "PASSIVE #";', runtime)
        self.assertIn(
            'case battle_scene_phase::training:\n'
            '        return "TRAINING";',
            runtime,
        )
        for field in (
            "training_character_id",
            "training_action_id",
            "training_action_level",
            "training_points",
            "training_error",
            "training_entry_kind",
        ):
            with self.subTest(field=field):
                self.assertIn(field, runtime_header)
                self.assertIn(f"output.{field}", runtime)

        input_loop = runtime[runtime.index("while(true)") :]
        self.assertIn("controller.cycle_unit(-1)", input_loop)
        self.assertIn("controller.cycle_unit(1)", input_loop)
        self.assertIn("result = controller.confirm()", input_loop)
        self.assertIn("result = controller.cancel()", input_loop)

    def test_campaign_progression_is_projected_and_merged_at_scene_boundary(self):
        runtime_header = (
            INCLUDE / "battle_runtime_scene.h"
        ).read_text(encoding="utf-8")
        runtime = (
            SOURCE / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        main = (
            ROOT / "butano-sequel" / "src" / "main.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn(
            '#include "konoha/battle_campaign.h"',
            runtime_header,
        )
        self.assertIn(
            "battle_campaign_state* campaign = nullptr;",
            runtime_header,
        )
        self.assertIn(
            '#include "konoha/battle_campaign_scene_progression.h"',
            runtime,
        )
        self.assertIn(
            "scene_progression.begin(*request.campaign)",
            runtime,
        )
        self.assertIn(
            "scene_progression.commit(*request.campaign)",
            runtime,
        )
        for tool_writeback in (
            "config.equipped_tools_output",
            "controller.equipped_tools_roster()",
            "&scene_progression.equipped_tools()",
        ):
            with self.subTest(tool_writeback=tool_writeback):
                self.assertIn(tool_writeback, runtime)

        self.assertIn(
            '#include "konoha/battle_campaign_sram.h"',
            main,
        )
        self.assertIn(
            "BN_DATA_EWRAM_BSS static unsigned char",
            main,
        )
        self.assertIn("campaign_storage[", main)
        self.assertIn("campaign_checkpoint_storage[", main)
        self.assertIn(
            "*::new(static_cast<void*>(campaign_storage))",
            main,
        )
        self.assertNotIn(
            "BN_DATA_EWRAM_BSS static "
            "konoha::battle_campaign_state",
            main,
        )
        self.assertIn(
            "load_battle_campaign_from_sram(",
            main,
        )
        self.assertIn(
            "save_battle_campaign_to_sram(",
            main,
        )


if __name__ == "__main__":
    unittest.main()
