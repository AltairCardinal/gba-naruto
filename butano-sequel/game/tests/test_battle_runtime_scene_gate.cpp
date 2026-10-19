#include "konoha/battle_runtime_scene.h"
#include "konoha/battle_scene_controller.h"

#include <cassert>
#include <cstddef>

using namespace konoha;

int main()
{
    static_assert(sizeof(battle_action_menu_view) <= 9);
    static_assert(
            sizeof(battle_player_action_flow_snapshot) <=
            384);
    static_assert(
            sizeof(battle_scene_snapshot<12>) <= 1120);
    for(const action_definition& action :
            active_action_definitions)
    {
        assert(action.cost.scalar <= 255);
    }
    for(const action_definition& action :
            ninja_tool_action_definitions)
    {
        assert(action.cost.scalar <= 255);
    }
    static_assert(
            sizeof(battlefield_object_resolution_summary) <= 16);
    static_assert(sizeof(battle_turn_flow_result) <= 32);
    static_assert(sizeof(battle_scene_control_result) <= 256);
    static_assert(
            battle_runtime_scene_sprite_budget::
                    maximum_oam_sprites == 128);
    static_assert(
            battle_runtime_scene_sprite_budget::
                    maximum_text_sprites == 78);
    static_assert(
            battle_runtime_scene_sprite_budget::fits(
                    12, 12, 78));
    static_assert(
            ! battle_runtime_scene_sprite_budget::fits(
                    12, 12, 79));
    static_assert(
            sizeof(battle_runtime_scene_telemetry) == 824);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_command) == 32);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    enemy_completed) == 40);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    cursor_x) == 48);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    last_control_error) == 56);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    render_stage) == 64);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_busy) == 68);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_character_id) == 72);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    action_count) == 76);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    action_index) == 80);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_action_id) == 84);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_action_error) == 88);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    last_resolved_action_id) == 92);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    background_chunk_index) == 96);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    background_chunk_count) == 100);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_action_kind) == 104);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_action_tool_slot) == 108);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    result_participant_count) == 112);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    result_total_experience) == 128);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    result_hp_growth) == 144);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_resource_resolved) == 208);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_resource_type) == 212);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_resource_amount) == 216);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_resource_hp_delta) == 220);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_resource_chakra_delta) == 224);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    ai_secondary_planned) == 228);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    ai_defense_kind) == 232);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    ai_defense_action_id) == 236);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    ai_defense_tool_slot) == 240);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    ai_defense_score) == 244);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    cursor_unit_id) == 304);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    cursor_unit_attack) == 308);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    cursor_unit_defense) == 312);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    cursor_unit_agility) == 316);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    cursor_unit_status_count) == 320);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    cursor_unit_active) == 324);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    cursor_unit_hp) == 328);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_action_level) == 332);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    training_character_id) == 336);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    training_action_id) == 340);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    training_action_level) == 344);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    training_points) == 348);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    training_error) == 352);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    training_entry_kind) == 356);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_combat_schema_version) == 360);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_combat_stage) == 364);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_combat_stage_frame) == 368);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_combat_impact_index) == 372);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_combat_tracks) == 376);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_combat_resource) == 380);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_unit_x) == 384);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_unit_y) == 388);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    first_active_enemy_x) == 392);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    first_active_enemy_y) == 396);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_action_effect_code) == 400);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_action_target_kind) == 404);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_unit_chakra) == 408);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    move_preview_x) == 412);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    move_preview_y) == 416);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    unit_character_ids) == 420);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    unit_active) == 468);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    unit_x) == 516);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    unit_y) == 564);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_unit_hp) == 612);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    selected_unit_max_hp) == 616);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    unit_hp) == 620);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    unit_chakra) == 668);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    unit_side) == 716);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    unit_control) == 764);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    resource_preview_amount) == 812);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    resource_preview_maximum_amount) == 816);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    condition_outcome) == 820);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_passive_resolved) == 248);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_passive_id) == 252);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_passive_kind) == 256);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_passive_hp_delta) == 260);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_passive_chakra_delta) == 264);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_passive_status_code) == 268);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_passive_status_value) == 272);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_passive_status_duration_ticks) == 276);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_passive_status_applied) == 280);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    battlefield_object_count) == 284);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_battlefield_object) == 288);
    static_assert(
            offsetof(
                    battle_runtime_scene_telemetry,
                    presentation_battlefield_object_damage) ==
            300);
    static_assert(
            battle_runtime_scene_telemetry::magic_value ==
                    0x4B42544CU);
}
