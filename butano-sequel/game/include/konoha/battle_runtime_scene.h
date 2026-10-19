#ifndef KONOHA_BATTLE_RUNTIME_SCENE_H
#define KONOHA_BATTLE_RUNTIME_SCENE_H

#include "konoha/battle_arena_roster.h"
#include "konoha/battle_campaign.h"
#include "konoha/battle_campaign_route.h"
#include "konoha/battle_runtime_result.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/battle_progression.h"

#include <cstdint>

namespace konoha
{

struct battle_runtime_scene_request
{
    int battle_id = 0;
    int variant = 0;
    std::uint32_t rng_seed = 0;
    const char* title = "";
    battle_scenario_load_policy load_policy = {};
    std::array<character_progression_record, 3>
            progression_roster = {};
    battle_campaign_state* campaign = nullptr;
    const battle_arena_match_roster* arena_roster =
            nullptr;
};

struct battle_runtime_scene_telemetry
{
    static constexpr std::uint32_t magic_value =
            0x4B42544CU;
    static constexpr std::uint32_t
            deployment_unit_phase_value =
                    0xFFFFFFFEU;
    static constexpr std::uint32_t
            deployment_start_phase_value =
                    0xFFFFFFFDU;

    std::uint32_t magic = 0;
    std::uint32_t battle_id = 0;
    std::uint32_t phase = 0;
    std::uint32_t round = 0;
    std::uint32_t current_side = 0;
    std::uint32_t selected_unit = 0;
    std::uint32_t active_unit_count = 0;
    std::uint32_t unit_count = 0;
    std::uint32_t selected_command = 0;
    std::uint32_t player_completed = 0;
    std::uint32_t enemy_completed = 0;
    std::uint32_t scene_frame = 0;
    std::uint32_t cursor_x = 0;
    std::uint32_t cursor_y = 0;
    std::uint32_t last_control_error = 0;
    std::uint32_t last_player_error = 0;
    std::uint32_t render_stage = 0;
    std::uint32_t presentation_busy = 0;
    std::uint32_t selected_character_id = 0;
    std::uint32_t action_count = 0;
    std::uint32_t action_index = 0;
    std::uint32_t selected_action_id = 0;
    std::uint32_t selected_action_error = 0;
    std::uint32_t last_resolved_action_id = 0;
    std::uint32_t background_chunk_index = 0;
    std::uint32_t background_chunk_count = 0;
    std::uint32_t selected_action_kind = 0;
    std::uint32_t selected_action_tool_slot = 0;
    std::uint32_t result_participant_count = 0;
    std::uint32_t result_mission_experience = 0;
    std::uint32_t result_battle_experience = 0;
    std::uint32_t result_round_bonus_experience = 0;
    std::uint32_t result_total_experience = 0;
    std::uint32_t result_level_before = 0;
    std::uint32_t result_level_after = 0;
    std::uint32_t result_experience_after = 0;
    std::uint32_t result_hp_growth = 0;
    std::uint32_t script_phase = 0;
    std::uint32_t script_selector = 0;
    std::uint32_t script_command_index = 0;
    std::uint32_t script_text_address = 0;
    std::uint32_t script_message_window_visible = 0;
    std::uint32_t script_portrait_0_visible = 0;
    std::uint32_t script_portrait_0_focused = 0;
    std::uint32_t script_portrait_0_id = 0;
    std::uint32_t script_portrait_0_expression = 0;
    std::uint32_t script_portrait_0_motion = 0;
    std::uint32_t script_portrait_1_visible = 0;
    std::uint32_t script_portrait_1_focused = 0;
    std::uint32_t script_portrait_1_id = 0;
    std::uint32_t script_portrait_1_expression = 0;
    std::uint32_t script_portrait_1_motion = 0;
    std::uint32_t presentation_resource_resolved = 0;
    std::uint32_t presentation_resource_type = 0;
    std::uint32_t presentation_resource_amount = 0;
    std::uint32_t presentation_resource_hp_delta = 0;
    std::uint32_t presentation_resource_chakra_delta = 0;
    std::uint32_t ai_secondary_planned = 0;
    std::uint32_t ai_defense_kind = 0;
    std::uint32_t ai_defense_action_id = 0;
    std::uint32_t ai_defense_tool_slot = 0;
    std::uint32_t ai_defense_score = 0;
    std::uint32_t presentation_passive_resolved = 0;
    std::uint32_t presentation_passive_id = 0;
    std::uint32_t presentation_passive_kind = 0;
    std::uint32_t presentation_passive_hp_delta = 0;
    std::uint32_t presentation_passive_chakra_delta = 0;
    std::uint32_t presentation_passive_status_code = 0;
    std::uint32_t presentation_passive_status_value = 0;
    std::uint32_t
            presentation_passive_status_duration_ticks = 0;
    std::uint32_t
            presentation_passive_status_applied = 0;
    std::uint32_t battlefield_object_count = 0;
    std::uint32_t presentation_battlefield_object = 0;
    std::uint32_t presentation_battlefield_object_kind = 0;
    std::uint32_t presentation_battlefield_object_slot = 0;
    std::uint32_t presentation_battlefield_object_damage = 0;
    std::uint32_t cursor_unit_id = 0;
    std::uint32_t cursor_unit_attack = 0;
    std::uint32_t cursor_unit_defense = 0;
    std::uint32_t cursor_unit_agility = 0;
    std::uint32_t cursor_unit_status_count = 0;
    std::uint32_t cursor_unit_active = 0;
    std::uint32_t cursor_unit_hp = 0;
    std::uint32_t selected_action_level = 0;
    std::uint32_t training_character_id = 0;
    std::uint32_t training_action_id = 0;
    std::uint32_t training_action_level = 0;
    std::uint32_t training_points = 0;
    std::uint32_t training_error = 0;
    std::uint32_t training_entry_kind = 0;
    std::uint32_t presentation_combat_schema_version = 0;
    std::uint32_t presentation_combat_stage = 0;
    std::uint32_t presentation_combat_stage_frame = 0;
    std::uint32_t presentation_combat_impact_index = 0;
    std::uint32_t presentation_combat_tracks = 0;
    std::uint32_t presentation_combat_resource = 0;
    std::uint32_t selected_unit_x = 0;
    std::uint32_t selected_unit_y = 0;
    std::uint32_t first_active_enemy_x = 0;
    std::uint32_t first_active_enemy_y = 0;
    std::uint32_t selected_action_effect_code = 0;
    std::uint32_t selected_action_target_kind = 0;
    std::uint32_t selected_unit_chakra = 0;
    std::uint32_t move_preview_x = 0;
    std::uint32_t move_preview_y = 0;
    std::uint32_t unit_character_ids[12] = {};
    std::uint32_t unit_active[12] = {};
    std::uint32_t unit_x[12] = {};
    std::uint32_t unit_y[12] = {};
    std::uint32_t selected_unit_hp = 0;
    std::uint32_t selected_unit_max_hp = 0;
    std::uint32_t unit_hp[12] = {};
    std::uint32_t unit_chakra[12] = {};
    std::uint32_t unit_side[12] = {};
    std::uint32_t unit_control[12] = {};
    std::uint32_t resource_preview_amount = 0;
    std::uint32_t resource_preview_maximum_amount = 0;
    std::uint32_t condition_outcome = 0;
    std::uint32_t training_detail_page = 0;
    std::uint32_t map_movement_active = 0;
    std::uint32_t map_movement_sequence = 0;
    std::uint32_t map_movement_elapsed = 0;
    std::int32_t map_movement_offset_x = 0;
    std::int32_t map_movement_offset_y = 0;
    std::uint32_t map_visual_facing = 0;
    std::uint32_t map_graphics_frame = 0;
    std::uint32_t pickup_sequence = 0;
    std::uint32_t material_3 = 0;
    std::uint32_t material_4 = 0;
};

struct battle_runtime_scene_sprite_budget
{
    static constexpr int maximum_oam_sprites = 128;
    static constexpr int cursor_sprites = 2;
    static constexpr int maximum_label_sprites_per_unit = 3;
    static constexpr int maximum_text_sprites = 78;
    static constexpr int maximum_ui_sprites = 16;

    [[nodiscard]] static constexpr bool fits(
            int unit_sprites,
            int labelled_units,
            int text_sprites,
            int ui_sprites = 0)
    {
        return unit_sprites + cursor_sprites +
                labelled_units *
                        maximum_label_sprites_per_unit +
                text_sprites + ui_sprites <=
                        maximum_oam_sprites;
    }
};

[[nodiscard]] battle_runtime_scene_exit run_battle_43_scene();

[[nodiscard]] battle_runtime_scene_exit run_battle_41_scene();

[[nodiscard]] battle_runtime_scene_exit run_battle_41_scene(
        battle_campaign_state& campaign);

[[nodiscard]] battle_runtime_scene_exit run_battle_09_scene();

[[nodiscard]] battle_runtime_scene_exit run_battle_11_scene();

[[nodiscard]] battle_runtime_scene_exit
run_battle_32_arena_fixture_scene();

[[nodiscard]] battle_runtime_scene_exit run_battle_scene(
        const battle_runtime_scene_request& request);

[[nodiscard]] battle_runtime_scene_exit
run_battle_campaign_stage(
        battle_campaign_state& campaign);

}

#endif
