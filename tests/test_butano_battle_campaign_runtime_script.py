import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ROOT / "butano-sequel" / "game" / "include" / "konoha"
SOURCE = ROOT / "butano-sequel" / "game" / "src"
TOOLS = ROOT / "tools" / "butano"


class ButanoBattleCampaignRuntimeScriptTest(unittest.TestCase):
    def test_campaign_telemetry_exposes_load_save_and_character_state(self):
        header = (
            INCLUDE / "battle_campaign_sram.h"
        ).read_text(encoding="utf-8")
        source = (
            SOURCE / "battle_campaign_sram.cpp"
        ).read_text(encoding="utf-8")

        for field in (
            "load_generation",
            "load_slot",
            "load_used_default",
            "save_generation",
            "save_slot",
            "save_verified",
            "naruto_level",
            "naruto_experience",
            "naruto_training_points",
            "naruto_action_8_level",
            "naruto_tool_0",
            "naruto_tool_1",
            "naruto_tool_2",
            "owned_tool_67",
            "owned_tool_68",
            "owned_tool_1",
            "material_6",
            "last_error",
            "scenario_id",
            "route_complete",
        ):
            with self.subTest(field=field):
                self.assertIn(field, header)
        self.assertIn(
            'extern "C"',
            header,
        )
        self.assertIn(
            "konoha_battle_campaign_runtime_telemetry",
            header,
        )
        self.assertIn(
            "BN_DATA_EWRAM_BSS volatile",
            source,
        )
        self.assertIn(
            "output.magic = "
            "battle_campaign_runtime_telemetry::magic_value;",
            source,
        )
        self.assertIn(
            "campaign.inventory.ninja_tools[67]",
            source,
        )
        self.assertIn(
            "campaign.inventory.ninja_tools[68]",
            source,
        )
        self.assertIn(
            "campaign.inventory.ninja_tools[1]",
            source,
        )
        self.assertIn(
            "campaign.inventory.materials[6]",
            source,
        )

    def test_runtime_scene_telemetry_wires_complete_unit_state_tail(
        self,
    ):
        header = (
            INCLUDE / "battle_runtime_scene.h"
        ).read_text(encoding="utf-8")
        source = (
            SOURCE / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")

        for field in (
            "unit_hp[12]",
            "unit_chakra[12]",
            "unit_side[12]",
            "unit_control[12]",
            "resource_preview_amount",
            "resource_preview_maximum_amount",
            "condition_outcome",
        ):
            with self.subTest(field=field):
                self.assertIn(field, header)

        for assignment in (
            "output.unit_hp[index] =",
            "output.unit_chakra[index] =",
            "output.unit_side[index] =",
            "output.unit_control[index] =",
            "output.resource_preview_amount =",
            "output.resource_preview_maximum_amount =",
            "output.condition_outcome =",
        ):
            with self.subTest(assignment=assignment):
                self.assertIn(assignment, source)

    def test_shared_battle_route_waits_for_verified_sram_save(self):
        script = (
            TOOLS / "mgba_battle_41_shared_runtime.lua"
        ).read_text(encoding="utf-8")
        for token in (
            "MGBA_S41_SHARED_CAMPAIGN_TELEMETRY_ADDRESS",
            "CAMPAIGN_TELEMETRY_MAGIC",
            "campaign.save_generation",
            "campaign.save_verified",
            "campaign.naruto_level",
            "campaign.naruto_experience == 0",
            "campaign.naruto_action_8_level",
            "campaign.scenario_id == 42",
            '"campaign_save_generation":%d',
            '"campaign_scenario_id":%d',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)
        self.assertNotIn(
            "MGBA_S41_SHARED_CONSUME_TOOL37",
            script,
        )

    def test_shared_battle_route_waits_until_preparation_input_is_armed(
        self,
    ):
        script = (
            TOOLS / "mgba_battle_41_shared_runtime.lua"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "PREPARATION_SETTLE_FRAME = 120",
            script,
        )
        self.assertIn(
            "frame >= PREPARATION_SETTLE_FRAME",
            script,
        )
        self.assertIn(
            'preparation_step == 0 and not active_key',
            script,
        )
        self.assertIn(
            'preparation_step == 1 and not active_key',
            script,
        )
        self.assertIn(
            'capture_once(\n\t\t\t\t\t"preparation-root"',
            script,
        )
        self.assertIn(
            'preparation_step == 7 and not active_key',
            script,
        )
        self.assertIn(
            'press("A")',
            script,
        )

    def test_cold_load_route_is_zero_input_and_checks_generation(self):
        script_path = TOOLS / "mgba_battle_campaign_load.lua"
        self.assertTrue(script_path.is_file())
        script = script_path.read_text(encoding="utf-8")
        for token in (
            "MGBA_CAMPAIGN_LOAD_OUTPUT_DIR",
            "MGBA_CAMPAIGN_LOAD_DONE_MARKER",
            "MGBA_CAMPAIGN_LOAD_TELEMETRY_ADDRESS",
            "MGBA_CAMPAIGN_EXPECTED_TOOL_2",
            "MGBA_CAMPAIGN_EXPECTED_LEVEL",
            "MGBA_CAMPAIGN_EXPECTED_EXPERIENCE",
            "MGBA_CAMPAIGN_EXPECTED_ACTION_8_LEVEL",
            "MGBA_CAMPAIGN_EXPECTED_TOOL_0",
            "MGBA_CAMPAIGN_EXPECTED_OWNED_TOOL_67",
            "MGBA_CAMPAIGN_EXPECTED_OWNED_TOOL_68",
            "MGBA_CAMPAIGN_EXPECTED_OWNED_TOOL_1",
            "MGBA_CAMPAIGN_EXPECTED_MATERIAL_6",
            "load_generation",
            "load_used_default",
            "naruto_level",
            "naruto_action_8_level",
            "campaign.naruto_tool_2 ==",
            "campaign.owned_tool_1 ==",
            '"naruto_tool_2":%d',
            '"owned_tool_1":%d',
            '"status":"campaign-load-complete"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)
        self.assertNotIn("emu:addKey", script)
        self.assertNotIn("emu:clearKey", script)

    def test_preparation_upgrade_route_checks_atomic_campaign_writeback(
        self,
    ):
        script_path = (
            TOOLS / "mgba_battle_preparation_upgrade.lua"
        )
        self.assertTrue(script_path.is_file())
        script = script_path.read_text(encoding="utf-8")
        for token in (
            "MGBA_BATTLE_PREPARATION_OUTPUT_DIR",
            "MGBA_BATTLE_PREPARATION_DONE_MARKER",
            "MGBA_BATTLE_PREPARATION_CAMPAIGN_TELEMETRY_ADDRESS",
            "MGBA_BATTLE_PREPARATION_BATTLE_TELEMETRY_ADDRESS",
            "BATTLE_TELEMETRY_MAGIC",
            "battle.battle_id == 41",
            "battle.phase == PHASE_DEPLOY_UNIT",
            'press("Down")',
            'press("A")',
            'press("B")',
            "campaign.save_verified == 1",
            "campaign.naruto_tool_0 == 68",
            "campaign.owned_tool_67 == 0",
            "campaign.owned_tool_68 == 1",
            "campaign.material_6 == 0",
            '"status":"preparation-upgrade-complete"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_preparation_equipment_route_checks_allocation_save_and_battle(
        self,
    ):
        script_path = (
            TOOLS / "mgba_battle_preparation_equipment.lua"
        )
        self.assertTrue(script_path.is_file())
        script = script_path.read_text(encoding="utf-8")
        for token in (
            "MGBA_BATTLE_EQUIPMENT_OUTPUT_DIR",
            "MGBA_BATTLE_EQUIPMENT_DONE_MARKER",
            "MGBA_BATTLE_EQUIPMENT_CAMPAIGN_TELEMETRY_ADDRESS",
            "MGBA_BATTLE_EQUIPMENT_BATTLE_TELEMETRY_ADDRESS",
            "battle.battle_id == 41",
            "drive_deployment(battle)",
            "PHASE_DEPLOY_UNIT",
            "campaign.save_verified == 1",
            "campaign.naruto_tool_0 == 1",
            "campaign.owned_tool_1 == 1",
            "campaign.owned_tool_67 == 1",
            '"status":"preparation-equipment-complete"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_terrain_passive_route_rejects_untrained_class_seven_tile(
        self,
    ):
        script_path = (
            TOOLS / "mgba_battle_terrain_traversal.lua"
        )
        self.assertTrue(script_path.is_file())
        script = script_path.read_text(encoding="utf-8")
        for token in (
            "MGBA_TERRAIN_OUTPUT_DIR",
            "MGBA_TERRAIN_DONE_MARKER",
            "MGBA_TERRAIN_BATTLE_TELEMETRY_ADDRESS",
            "PHASE_MOVE_SELECTION",
            'press("Left")',
            'press("Up")',
            "battle.cursor_x == 3",
            "battle.cursor_y == 9",
            "battle.last_player_error == MOVE_REJECTED",
            "battle.phase == PHASE_COMMAND_SELECTION",
            '"status":"terrain-traversal-complete"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)


if __name__ == "__main__":
    unittest.main()
