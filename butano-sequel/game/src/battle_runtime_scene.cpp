#include "konoha/battle_runtime_scene.h"

#include "bn_camera_ptr.h"
#include "bn_bpp_mode.h"
#include "bn_blending.h"
#include "bn_bg_tiles.h"
#include "bn_bg_palette_ptr.h"
#include "bn_bg_palettes.h"
#include "bn_color.h"
#include "bn_common.h"
#include "bn_compression_type.h"
#include "bn_core.h"
#include "bn_assert.h"
#include "bn_fixed.h"
#include "bn_keypad.h"
#include "bn_memory.h"
#include "bn_optional.h"
#include "bn_regular_bg_item.h"
#include "bn_regular_bg_map_cell.h"
#include "bn_regular_bg_map_cell_info.h"
#include "bn_regular_bg_map_item.h"
#include "bn_regular_bg_map_ptr.h"
#include "bn_regular_bg_tiles_item.h"
#include "bn_regular_bg_tiles_ptr.h"
#include "bn_regular_bg_items_battle_action_16_cutin_dialogue.h"
#include "bn_regular_bg_items_battle_action_16_cutin_portrait.h"
#include "bn_regular_bg_items_battle_action_16_movie_actor.h"
#include "bn_regular_bg_items_battle_action_16_movie_dialogue.h"
#include "bn_regular_bg_items_battle_action_16_movie_fire.h"
#include "bn_regular_bg_items_battle_action_16_movie_streaks.h"
#include "bn_regular_bg_items_battle_duel_forest.h"
#include "bn_regular_bg_items_battle_duel_hud_shell.h"
#include "bn_regular_bg_items_battle_ui_dialogue_background.h"
#include "bn_regular_bg_items_battle_ui_level_up_panel.h"
#include "bn_regular_bg_items_battle_ui_result_background.h"
#include "bn_regular_bg_items_battle_ui_result_panel.h"
#include "bn_regular_bg_items_battle_ui_training_panel.h"
#include "bn_regular_bg_items_battle_ui_training_text_0.h"
#include "bn_regular_bg_items_battle_ui_training_text_1.h"
#include "bn_regular_bg_items_battle_ui_training_text_2.h"
#include "bn_regular_bg_items_battle_ui_training_text_3.h"
#include "bn_regular_bg_items_battle_ui_training_text_4.h"
#include "bn_regular_bg_items_battle_ui_training_text_5.h"
#include "bn_regular_bg_ptr.h"
#include "bn_rect_window.h"
#include "bn_span.h"
#include "bn_sprite_palette_item.h"
#include "bn_sprite_palette_ptr.h"
#include "bn_sprite_palettes.h"
#include "bn_sprite_items_battle_action_16_movie_title_0.h"
#include "bn_sprite_items_battle_action_16_movie_title_1.h"
#include "bn_sprite_items_battle_action_16_movie_title_2.h"
#include "bn_sprite_items_scenario_41_cursor.h"
#include "bn_sprite_items_scenario_41_cursor_shadow.h"
#include "bn_sprite_items_battle_scenario_49_destination_cursor.h"
#include "bn_sprite_items_battlefield_object_type_2_expiry.h"
#include "bn_sprite_items_battle_presentation_glyphs.h"
#include "bn_sprite_items_battle_ui_action_icon.h"
#include "bn_sprite_items_battle_ui_action_cursor.h"
#include "bn_sprite_items_battle_ui_action_start_hint.h"
#include "bn_sprite_items_battle_ui_action_back_hint.h"
#include "bn_sprite_items_battle_ui_action_actor_stats.h"
#include "bn_sprite_items_battle_ui_bar.h"
#include "bn_sprite_items_battle_ui_command_cursor.h"
#include "bn_sprite_items_battle_ui_confirmation_cursor.h"
#include "bn_sprite_items_battle_ui_dialog_panel.h"
#include "bn_sprite_items_battle_ui_large_dialog_panel.h"
#include "bn_sprite_items_battle_ui_level_up_eye.h"
#include "bn_sprite_items_battle_ui_level_up_portrait_16x16.h"
#include "bn_sprite_items_battle_ui_level_up_portrait_16x32.h"
#include "bn_sprite_items_battle_ui_level_up_portrait_32x16.h"
#include "bn_sprite_items_battle_ui_level_up_portrait_64x64.h"
#include "bn_sprite_items_battle_ui_level_up_title.h"
#include "bn_sprite_items_battle_ui_level_up_value.h"
#include "bn_sprite_items_battle_ui_dialogue_speaker_label.h"
#include "bn_sprite_items_battle_ui_dialogue_advance_icon.h"
#include "bn_sprite_items_battle_ui_message_black_bar.h"
#include "bn_sprite_items_battle_ui_select_prompt.h"
#include "bn_sprite_items_battle_ui_turn_banner_panel.h"
#include "bn_sprite_items_battle_ui_message_panel.h"
#include "bn_sprite_items_battle_ui_panel.h"
#include "bn_sprite_items_battle_ui_result_naruto.h"
#include "bn_sprite_items_battle_ui_result_sakura.h"
#include "bn_sprite_items_battle_ui_result_sasuke.h"
#include "bn_sprite_items_battle_ui_status_end.h"
#include "bn_sprite_items_battle_ui_status_panel.h"
#include "bn_sprite_items_battle_scenario_49_chest.h"
#include "bn_sprite_palette_items_battle_ui_map_hint_palette.h"
#include "bn_sprite_palette_items_battle_ui_dialogue_speaker_palette.h"
#include "bn_sprite_palette_items_battle_ui_dialogue_text_palette.h"
#include "bn_sprite_palette_items_battle_ui_result_total_palette.h"
#include "bn_sprite_palette_items_battle_unit_dimmed_palette.h"
#include "bn_sprite_palette_items_battle_ui_text_accent_palette.h"
#include "bn_sprite_palette_items_battle_ui_text_warning_palette.h"
#include "bn_sprite_item.h"
#include "bn_sprite_ptr.h"
#include "bn_sprite_shape_size.h"
#include "bn_sprite_text_generator.h"
#include "bn_sprite_tiles_ptr.h"
#include "bn_string.h"
#include "bn_tile.h"
#include "bn_vector.h"
#include "bn_window.h"

#include "konoha/battle_identity_sprite_font.h"
#include "konoha/battle_action_menu_sprite_font.h"
#include "konoha/battle_action_ui_map_projection.h"
#include "konoha/battle_duel_status_sprite_font.h"
#include "konoha/battle_preparation_sprite_font.h"
#include "konoha/battle_result_compact_sprite_font.h"
#include "konoha/battle_result_sprite_font.h"
#include "konoha/battle_target_metrics_sprite_font.h"
#include "konoha/battle_target_status_sprite_font.h"
#include "konoha/battle_range_ui_style.h"
#include "konoha/battle_ui_sprite_font.h"
#include "konoha/battle_map_visual_projection.h"
#include "konoha/battle_map_movement.h"
#include "konoha/battle_map_scenery.h"
#include "konoha/battle_presentation_projection.h"
#include "konoha/battle_audio_runtime.h"
#include "konoha/battle_background_stream.h"
#include "konoha/battle_actor_choreography.h"
#include "konoha/battle_campaign_scene_progression.h"
#include "konoha/battle_combat_presentation.h"
#include "konoha/battle_content_catalog.h"
#include "konoha/battle_deployment_flow.h"
#include "konoha/battle_presentation_portrait_renderer.h"
#include "konoha/battle_runtime_grid.h"
#include "konoha/battle_presentation_text_layout.h"
#include "konoha/battle_scene_presentation.h"
#include "konoha/battle_ui_model.h"
#include "konoha/battle_visual_resource_coordinator.h"
#include "konoha/generated_battle_background_content.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/generated_battle_action_05_effect_content.h"
#include "konoha/generated_battle_action_05_effect_items.h"
#include "konoha/generated_battle_action_05_dust_effect_content.h"
#include "konoha/generated_battle_action_05_dust_effect_items.h"
#include "konoha/generated_battle_action_16_fire_effect_content.h"
#include "konoha/generated_battle_action_16_fire_effect_items.h"
#include "konoha/generated_battle_action_16_movie_runtime_content.h"
#include "konoha/generated_battle_ninja_tool_bomb_projectile_content.h"
#include "konoha/generated_battle_ninja_tool_bomb_projectile_items.h"
#include "konoha/generated_battle_ninja_tool_bomb_smoke_content.h"
#include "konoha/generated_battle_ninja_tool_bomb_smoke_items.h"
#include "konoha/generated_battle_identity_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_presentation_portrait_content.h"
#include "konoha/generated_battle_presentation_glyph_content.h"
#include "konoha/generated_battle_unit_visual_content.h"
#include "konoha/scenario_41_definition.h"

#include <array>
#include <cstddef>

namespace konoha
{

extern "C"
{
    BN_DATA_EWRAM_BSS volatile
            battle_runtime_scene_telemetry
                    konoha_battle_runtime_telemetry;
}

namespace
{

constexpr int map_center_x = 256;
constexpr int map_center_y = 256;
constexpr int cell_width = 32;
constexpr int cell_height = 16;
constexpr int screen_width = 240;
constexpr int screen_height = 160;

[[nodiscard]] constexpr bool
battle_phase_uses_full_screen_result(
        battle_scene_phase phase)
{
    switch(phase)
    {
    case battle_scene_phase::outcome:
    case battle_scene_phase::result:
    case battle_scene_phase::level_up:
    case battle_scene_phase::training:
    case battle_scene_phase::complete:
        return true;
    default:
        return false;
    }
}

void dispatch_battle_combat_stage_audio(
        const battle_audio_director& director,
        battle_combat_presentation_stage stage,
        bool special_combination)
{
    switch(stage)
    {
    case battle_combat_presentation_stage::technique_title:
        dispatch_battle_audio(
                director,
                battle_audio_event::technique_title,
                special_combination);
        break;
    case battle_combat_presentation_stage::action_movie:
        dispatch_battle_audio(
                director,
                battle_audio_event::action_movie);
        break;
    case battle_combat_presentation_stage::impact:
        dispatch_battle_audio(
                director,
                battle_audio_event::impact);
        break;
    case battle_combat_presentation_stage::result:
        dispatch_battle_audio(
                director,
                battle_audio_event::combat_popup,
                special_combination);
        break;
    default:
        break;
    }
}

void dispatch_battle_phase_audio(
        const battle_audio_director& director,
        battle_scene_phase previous,
        const battle_scene_snapshot<12>& current)
{
    if(previous == current.phase)
    {
        return;
    }
    switch(current.phase)
    {
    case battle_scene_phase::outcome:
        if(current.outcome ==
                battle_condition_outcome::win)
        {
            dispatch_battle_audio(
                    director,
                    battle_audio_event::victory_shown);
        }
        break;
    case battle_scene_phase::result:
        dispatch_battle_audio(
                director,
                battle_audio_event::result_shown);
        break;
    case battle_scene_phase::level_up:
        dispatch_battle_audio(
                director,
                battle_audio_event::level_up_shown);
        break;
    case battle_scene_phase::complete:
        dispatch_battle_audio(
                director,
                battle_audio_event::postbattle_opened);
        break;
    default:
        break;
    }
}

struct battle_runtime_scene_config
{
    int battle_id = 0;
    int variant = 0;
    std::uint32_t rng_seed = 0;
    const char* title = "";
    battle_scenario_load_policy load_policy = {};
    std::array<character_progression_record, 3>
            progression_roster = {};
    std::array<character_progression_record, 3>*
            progression_output = nullptr;
    battle_campaign_party_equipment*
            equipped_tools_output = nullptr;
    battle_campaign_inventory initial_inventory = {};
    std::array<std::uint8_t, battle_campaign_material_quantity_capacity>* materials_output = nullptr;
    int map_pixel_width = 0;
    int map_pixel_height = 0;
    std::array<
            const bn::regular_bg_item*,
            battle_background_max_chunks>
            map_items = {};
    std::array<
            int,
            battle_background_max_chunks>
            map_chunk_origins = {};
    std::size_t map_chunk_count = 0;
};

struct battlefield_object_telemetry_latch
{
    bool presented = false;
    battlefield_object_tick_kind kind =
            battlefield_object_tick_kind::none;
    std::uint8_t slot = no_battlefield_object;
    int damage = 0;
};

void capture_telemetry(
        const battle_scene_snapshot<12>& state,
        const battle_training_snapshot&
                training,
        const battle_result& result,
        const battle_runtime_scene_config& config,
        std::uint32_t scene_frame,
        std::uint32_t last_control_error,
        std::uint32_t last_player_error,
        std::uint32_t last_resolved_action_id,
        const battle_ai_secondary_command&
                last_ai_secondary,
        bool presentation_busy,
        const battle_scene_presentation_event*
                presentation_event,
        const battle_combat_presentation*
                combat_presentation,
        const battle_scene_object_snapshot& object_state,
        const battlefield_object_telemetry_latch&
                object_telemetry,
        const battle_background_stream& background)
{
    volatile battle_runtime_scene_telemetry& output =
            konoha_battle_runtime_telemetry;
    output.magic = 0;
    output.battle_id =
            static_cast<std::uint32_t>(config.battle_id);
    output.phase =
            static_cast<std::uint32_t>(state.phase);
    output.round =
            static_cast<std::uint32_t>(state.round);
    output.current_side =
            static_cast<std::uint32_t>(
                    state.current_side);
    output.selected_unit =
            static_cast<std::uint32_t>(
                    state.selected_unit);
    output.active_unit_count =
            static_cast<std::uint32_t>(
                    state.active_unit_count);
    output.unit_count =
            static_cast<std::uint32_t>(
                    state.unit_count);
    output.selected_command =
            static_cast<std::uint32_t>(
                    state.player.selected_command);

    std::uint32_t player_completed = 0;
    std::uint32_t enemy_completed = 0;
    std::uint32_t selected_character_id = 0xFFFFFFFFU;
    output.selected_unit_x = 0xFFFFFFFFU;
    output.selected_unit_y = 0xFFFFFFFFU;
    output.selected_unit_chakra = 0xFFFFFFFFU;
    output.selected_unit_hp = 0xFFFFFFFFU;
    output.selected_unit_max_hp = 0xFFFFFFFFU;
    output.resource_preview_amount =
            static_cast<std::uint32_t>(
                    state.player.resource_preview.amount);
    output.resource_preview_maximum_amount =
            static_cast<std::uint32_t>(
                    state.player.resource_preview
                            .maximum_amount);
    output.condition_outcome =
            static_cast<std::uint32_t>(state.outcome);
    output.training_detail_page =
            static_cast<std::uint32_t>(
                    state.training_detail_page);
    output.move_preview_x =
            static_cast<std::uint32_t>(
                    state.player.move_position.x);
    output.move_preview_y =
            static_cast<std::uint32_t>(
                    state.player.move_position.y);
    output.first_active_enemy_x = 0xFFFFFFFFU;
    output.first_active_enemy_y = 0xFFFFFFFFU;
    output.cursor_unit_id =
            static_cast<std::uint32_t>(no_battle_unit);
    output.cursor_unit_attack = 0;
    output.cursor_unit_defense = 0;
    output.cursor_unit_agility = 0;
    output.cursor_unit_status_count = 0;
    output.cursor_unit_active = 0;
    output.cursor_unit_hp = 0;
    for(std::size_t index = 0; index < 12; ++index)
    {
        output.unit_character_ids[index] = 0;
        output.unit_active[index] = 0;
        output.unit_x[index] = 0xFFFFFFFFU;
        output.unit_y[index] = 0xFFFFFFFFU;
        output.unit_hp[index] = 0;
        output.unit_chakra[index] = 0;
        output.unit_side[index] = 0xFFFFFFFFU;
        output.unit_control[index] = 0xFFFFFFFFU;
    }
    for(std::size_t index = 0;
            index < state.unit_count; ++index)
    {
        const battle_scene_unit_view& unit =
                state.units[index];
        if(index < 12)
        {
            output.unit_character_ids[index] =
                    static_cast<std::uint32_t>(
                            unit.character_id);
            output.unit_active[index] =
                    static_cast<std::uint32_t>(
                            unit.active);
            output.unit_x[index] =
                    static_cast<std::uint32_t>(
                            unit.position.x);
            output.unit_y[index] =
                    static_cast<std::uint32_t>(
                            unit.position.y);
            output.unit_hp[index] =
                    static_cast<std::uint32_t>(unit.hp);
            output.unit_chakra[index] =
                    static_cast<std::uint32_t>(
                            unit.chakra);
            output.unit_side[index] =
                    static_cast<std::uint32_t>(
                            unit.side);
            output.unit_control[index] =
                    static_cast<std::uint32_t>(
                            unit.control);
        }
        if(state.cursor == unit.position &&
                (unit.active ||
                 output.cursor_unit_id ==
                         static_cast<std::uint32_t>(
                                 no_battle_unit)))
        {
            output.cursor_unit_id =
                    static_cast<std::uint32_t>(unit.id);
            output.cursor_unit_attack =
                    static_cast<std::uint32_t>(unit.attack);
            output.cursor_unit_defense =
                    static_cast<std::uint32_t>(unit.defense);
            output.cursor_unit_agility =
                    static_cast<std::uint32_t>(unit.agility);
            output.cursor_unit_status_count =
                    static_cast<std::uint32_t>(
                            unit.status_count);
            output.cursor_unit_active =
                    static_cast<std::uint32_t>(
                            unit.active);
            output.cursor_unit_hp =
                    static_cast<std::uint32_t>(
                            unit.hp);
        }
        if(unit.id == state.selected_unit)
        {
            selected_character_id =
                    static_cast<std::uint32_t>(
                            unit.character_id);
            output.selected_unit_x =
                    static_cast<std::uint32_t>(
                            unit.position.x);
            output.selected_unit_y =
                    static_cast<std::uint32_t>(
                            unit.position.y);
            output.selected_unit_chakra =
                    static_cast<std::uint32_t>(
                            unit.chakra);
            output.selected_unit_hp =
                    static_cast<std::uint32_t>(
                            unit.hp);
            output.selected_unit_max_hp =
                    static_cast<std::uint32_t>(
                            unit.max_hp);
        }
        if(unit.active &&
                unit.side == battle_side::enemy &&
                output.first_active_enemy_x ==
                        0xFFFFFFFFU)
        {
            output.first_active_enemy_x =
                    static_cast<std::uint32_t>(
                            unit.position.x);
            output.first_active_enemy_y =
                    static_cast<std::uint32_t>(
                            unit.position.y);
        }
        if(! unit.active || ! unit.completed)
        {
            continue;
        }
        if(unit.side == battle_side::player)
        {
            ++player_completed;
        }
        else
        {
            ++enemy_completed;
        }
    }
    output.player_completed = player_completed;
    output.enemy_completed = enemy_completed;
    output.scene_frame = scene_frame;
    output.cursor_x =
            static_cast<std::uint32_t>(state.cursor.x);
    output.cursor_y =
            static_cast<std::uint32_t>(state.cursor.y);
    output.last_control_error = last_control_error;
    output.last_player_error = last_player_error;
    output.render_stage = 0;
    output.presentation_busy =
            presentation_busy ? 1U : 0U;
    const bool resource_resolved =
            presentation_event &&
            presentation_event->has_resource;
    output.presentation_resource_resolved =
            resource_resolved ? 1U : 0U;
    output.presentation_resource_type =
            resource_resolved ?
                    static_cast<std::uint32_t>(
                            presentation_event->
                                    resource_type) :
                    0;
    output.presentation_resource_amount =
            resource_resolved ?
                    static_cast<std::uint32_t>(
                            presentation_event->
                                    resource_amount) :
                    0;
    output.presentation_resource_hp_delta =
            resource_resolved ?
                    static_cast<std::uint32_t>(
                            presentation_event->
                                    resource_hp_delta) :
                    0;
    output.presentation_resource_chakra_delta =
            resource_resolved ?
                    static_cast<std::uint32_t>(
                            presentation_event->
                                    resource_chakra_delta) :
                    0;
    const bool passive_resolved =
            presentation_event &&
            presentation_event->
                    has_side_start_passive;
    output.presentation_passive_resolved =
            passive_resolved ? 1U : 0U;
    output.presentation_passive_id =
            passive_resolved ?
                    static_cast<std::uint32_t>(
                            presentation_event->
                                    passive) :
                    0;
    output.presentation_passive_kind =
            passive_resolved ?
                    static_cast<std::uint32_t>(
                            presentation_event->
                                    passive_kind) :
                    0;
    output.presentation_passive_hp_delta =
            passive_resolved ?
                    static_cast<std::uint32_t>(
                            presentation_event->
                                    resource_hp_delta) :
                    0;
    output.presentation_passive_chakra_delta =
            passive_resolved ?
                    static_cast<std::uint32_t>(
                            presentation_event->
                                    resource_chakra_delta) :
                    0;
    output.presentation_passive_status_code =
            passive_resolved ?
                    presentation_event->
                            passive_status_code :
                    0;
    output.presentation_passive_status_value =
            passive_resolved ?
                    presentation_event->
                            passive_status_value :
                    0;
    output.presentation_passive_status_duration_ticks =
            passive_resolved ?
                    presentation_event->
                            passive_status_duration_ticks :
                    0;
    output.presentation_passive_status_applied =
            passive_resolved &&
                    presentation_event->
                            passive_status_applied ?
            1U :
            0U;
    output.battlefield_object_count =
            static_cast<std::uint32_t>(
                    object_state.count);
    output.presentation_battlefield_object =
            object_telemetry.presented ? 1U : 0U;
    output.presentation_battlefield_object_kind =
            static_cast<std::uint32_t>(
                    object_telemetry.kind);
    output.presentation_battlefield_object_slot =
            object_telemetry.slot;
    output.presentation_battlefield_object_damage =
            static_cast<std::uint32_t>(
                    object_telemetry.damage);
    output.ai_secondary_planned =
            last_ai_secondary.planned ? 1U : 0U;
    output.ai_defense_kind =
            static_cast<std::uint32_t>(
                    last_ai_secondary.defense_kind);
    output.ai_defense_action_id =
            static_cast<std::uint32_t>(
                    last_ai_secondary.defense_action_id);
    output.ai_defense_tool_slot =
            static_cast<std::uint32_t>(
                    last_ai_secondary.defense_tool_slot);
    output.ai_defense_score =
            static_cast<std::uint32_t>(
                    last_ai_secondary.score);
    output.selected_character_id = selected_character_id;
    output.action_count =
            static_cast<std::uint32_t>(
                    state.player.action_count);
    output.action_index =
            static_cast<std::uint32_t>(
                    state.player.action_index);
    output.selected_action_id =
            static_cast<std::uint32_t>(
                    state.player.selected_action_id);
    const int selected_action_index =
            state.player.action_index;
    const battle_action_menu_view* selected_action =
            selected_action_index >= 0 &&
                    selected_action_index <
                            state.player.action_count &&
                    selected_action_index <
                            static_cast<int>(
                                    state.player.
                                            action_entries.
                                            size()) ?
                    &state.player.action_entries[
                            static_cast<std::size_t>(
                                    selected_action_index)] :
                    nullptr;
    output.selected_action_level =
            selected_action ?
                    selected_action->action_level :
                    0;
    output.selected_action_effect_code =
            selected_action ?
                    selected_action->effect_code :
                    0;
    output.selected_action_target_kind =
            selected_action ?
                    static_cast<std::uint32_t>(
                            selected_action->target_kind) :
                    0;
    output.training_character_id =
            training.active ?
                    training.character_id :
                    0;
    output.training_action_id =
            training.active ?
                    training.selected_definition_id :
                    no_ability;
    output.training_action_level =
            training.active ?
                    training.selected_level :
                    0;
    output.training_points =
            training.active ?
                    static_cast<std::uint32_t>(
                            training.training_points) :
                    0;
    output.training_error =
            training.active ?
                    static_cast<std::uint32_t>(
                            training.last_error) :
                    0;
    output.training_entry_kind =
            training.active ?
                    static_cast<std::uint32_t>(
                            training.selected_kind) :
                    0;
    output.presentation_combat_schema_version = 1;
    const bool combat_busy =
            combat_presentation &&
            combat_presentation->busy();
    output.presentation_combat_stage =
            combat_busy ?
                    static_cast<std::uint32_t>(
                            combat_presentation->stage()) :
                    static_cast<std::uint32_t>(
                            battle_combat_presentation_stage::
                                    complete);
    output.presentation_combat_stage_frame =
            combat_busy ?
                    static_cast<std::uint32_t>(
                            combat_presentation->
                                    stage_frame()) :
                    0;
    output.presentation_combat_impact_index =
            combat_busy ?
                    static_cast<std::uint32_t>(
                            combat_presentation->
                                    current_impact_index()) :
                    0xFFFFFFFFU;
    output.presentation_combat_tracks =
            combat_busy ?
                    static_cast<std::uint32_t>(
                            combat_presentation->
                                    current_step().tracks) :
                    0;
    output.presentation_combat_resource =
            combat_busy ?
                    static_cast<std::uint32_t>(
                            combat_presentation->
                                    resource()) :
                    0;
    output.selected_action_error =
            static_cast<std::uint32_t>(
                    state.phase ==
                                    battle_scene_phase::
                                            target_selection ||
                    state.phase ==
                                    battle_scene_phase::
                                            target_preview ||
                    state.phase ==
                                    battle_scene_phase::
                                            target_confirmation ?
                            state.player.target_preview.error :
                            state.player.action_selection_error);
    output.last_resolved_action_id =
            last_resolved_action_id;
    output.background_chunk_index =
            static_cast<std::uint32_t>(
                    background.chunk_index());
    output.background_chunk_count =
            static_cast<std::uint32_t>(
                    background.chunk_count());
    output.selected_action_kind =
            static_cast<std::uint32_t>(
                    state.player.selected_action_kind);
    output.selected_action_tool_slot =
            static_cast<std::uint32_t>(
                    state.player.selected_action_tool_slot);
    output.result_participant_count =
            static_cast<std::uint32_t>(
                    result.participant_count);
    const battle_result_participant* participant =
            result.participant_count > 0 ?
            &result.participants[0] :
            nullptr;
    output.result_mission_experience =
            participant ?
            static_cast<std::uint32_t>(
                    participant->mission_experience) :
            0;
    output.result_battle_experience =
            participant ?
            static_cast<std::uint32_t>(
                    participant->battle_experience) :
            0;
    output.result_round_bonus_experience =
            participant ?
            static_cast<std::uint32_t>(
                    participant->round_bonus_experience) :
            0;
    output.result_total_experience =
            participant ?
            static_cast<std::uint32_t>(
                    participant->total_experience) :
            0;
    output.result_level_before =
            participant ?
            static_cast<std::uint32_t>(
                    participant->before.level) :
            0;
    output.result_level_after =
            participant ?
            static_cast<std::uint32_t>(
                    participant->after.level) :
            0;
    output.result_experience_after =
            participant ?
            static_cast<std::uint32_t>(
                    participant->after.experience) :
            0;
    output.result_hp_growth =
            participant ?
            static_cast<std::uint32_t>(
                    participant->stat_growth.max_hp) :
            0;
    output.script_phase =
            static_cast<std::uint32_t>(
                    state.script.phase);
    output.script_selector =
            static_cast<std::uint32_t>(
                    state.script.selector);
    output.script_command_index =
            static_cast<std::uint32_t>(
                    state.script.command_index);
    output.script_text_address =
            state.script.text_address;
    output.script_message_window_visible =
            state.script.message_window_visible ? 1U : 0U;
    const battle_presentation_portrait_snapshot&
            portrait_0 = state.script.portraits[0];
    output.script_portrait_0_visible =
            portrait_0.visible ? 1U : 0U;
    output.script_portrait_0_focused =
            portrait_0.focused ? 1U : 0U;
    output.script_portrait_0_id =
            portrait_0.portrait_id;
    output.script_portrait_0_expression =
            portrait_0.expression_id;
    output.script_portrait_0_motion =
            portrait_0.motion_mode;
    const battle_presentation_portrait_snapshot&
            portrait_1 = state.script.portraits[1];
    output.script_portrait_1_visible =
            portrait_1.visible ? 1U : 0U;
    output.script_portrait_1_focused =
            portrait_1.focused ? 1U : 0U;
    output.script_portrait_1_id =
            portrait_1.portrait_id;
    output.script_portrait_1_expression =
            portrait_1.expression_id;
    output.script_portrait_1_motion =
            portrait_1.motion_mode;
    output.magic =
            battle_runtime_scene_telemetry::magic_value;
}

[[nodiscard]] int world_x(grid_point point)
{
    return point.x * cell_width +
            cell_width / 2 - map_center_x;
}

[[nodiscard]] int world_y(grid_point point)
{
    return point.y * cell_height +
            cell_height / 2 - map_center_y;
}

[[nodiscard]] int clamp_camera(
        int value,
        int active_size,
        int viewport_size)
{
    const int minimum =
            -map_center_x + viewport_size / 2;
    const int maximum =
            -map_center_x + active_size -
            viewport_size / 2;
    if(maximum < minimum)
    {
        return (minimum + maximum) / 2;
    }
    if(value < minimum)
    {
        return minimum;
    }
    if(value > maximum)
    {
        return maximum;
    }
    return value;
}

[[nodiscard]] int camera_x(
        grid_point point,
        const battle_runtime_scene_config& config)
{
    return clamp_camera(
            world_x(point),
            config.map_pixel_width,
            screen_width);
}

[[nodiscard]] int camera_y(
        grid_point point,
        const battle_runtime_scene_config& config)
{
    return battle_camera_focus_y(
            point,
            config.map_pixel_height,
            screen_height);
}

[[nodiscard]] bool prepare_background_stream(
        const battle_runtime_scene_config& config,
        battle_background_stream& stream)
{
    if(config.map_chunk_count == 0 ||
            config.map_chunk_count >
                    config.map_items.size())
    {
        return false;
    }
    for(std::size_t index = 0;
            index < config.map_chunk_count;
            ++index)
    {
        if(! config.map_items[index])
        {
            return false;
        }
    }
    return stream.prepare(
                   config.map_pixel_width,
                   screen_width,
                   config.map_chunk_origins,
                   config.map_chunk_count)
            .success();
}

void update_background_stream(
        int camera_world_x,
        const battle_runtime_scene_config& config,
        battle_background_stream& stream,
        bn::regular_bg_ptr& map)
{
    const battle_background_stream_update update =
            stream.update(
                    camera_world_x + map_center_x);
    if(update.changed)
    {
        map.set_item(
                *config.map_items[
                        update.chunk_index]);
        map.set_x(stream.chunk_origin());
    }
}

[[nodiscard]] const char* phase_name(
        battle_scene_phase phase)
{
    switch(phase)
    {
    case battle_scene_phase::script_blocked:
        return "SCRIPT";
    case battle_scene_phase::unit_selection:
        return "SELECT UNIT";
    case battle_scene_phase::move_selection:
        return "MOVE";
    case battle_scene_phase::command_selection:
        return "COMMAND";
    case battle_scene_phase::chakra_selection:
        return "CHAKRA";
    case battle_scene_phase::rest_confirmation:
        return "REST";
    case battle_scene_phase::action_selection:
        return "ACTION";
    case battle_scene_phase::combination_decision:
        return "COMBO?";
    case battle_scene_phase::target_selection:
        return "TARGET";
    case battle_scene_phase::target_preview:
        return "TARGET PREVIEW";
    case battle_scene_phase::target_confirmation:
        return "CONFIRM TARGET";
    case battle_scene_phase::facing_selection:
        return "FACING";
    case battle_scene_phase::defense_decision:
        return "A:NONE B:DEFENSE";
    case battle_scene_phase::defense_selection:
        return "DEFENSE";
    case battle_scene_phase::enemy_turn:
        return "ENEMY TURN";
    case battle_scene_phase::outcome:
        return "BATTLE COMPLETE";
    case battle_scene_phase::result:
        return "RESULT";
    case battle_scene_phase::level_up:
        return "LEVEL UP";
    case battle_scene_phase::training:
        return "TRAINING";
    case battle_scene_phase::complete:
        return "COMPLETE";
    case battle_scene_phase::error:
        return "RUNTIME ERROR";
    default:
        return "PREPARING";
    }
}

[[nodiscard]] const battle_scene_unit_view*
selected_unit(const battle_scene_snapshot<12>& state)
{
    for(std::size_t index = 0;
            index < state.unit_count; ++index)
    {
        if(state.units[index].id == state.selected_unit)
        {
            return &state.units[index];
        }
    }
    return nullptr;
}

[[nodiscard]] const battle_action_menu_view*
selected_action(const battle_scene_snapshot<12>& state)
{
    const int action_index = state.player.action_index;
    return action_index >= 0 &&
                   action_index < state.player.action_count &&
                   action_index <
                           static_cast<int>(
                                   state.player.action_entries.size()) ?
            &state.player.action_entries[
                    static_cast<std::size_t>(action_index)] :
            nullptr;
}

void append_unit_identity(
        const battle_scene_unit_view& unit,
        bn::string<96>& output)
{
    const battle_identity_record* identity =
            battle_unit_identity(unit.character_id);
    if(identity)
    {
        output += identity->display_name;
        if(! identity->exact)
        {
            output += "?";
        }
    }
    else
    {
        output += "CHAR #";
        output += bn::to_string<4>(unit.character_id);
    }
}

void append_action_identity(
        battle_action_source_kind kind,
        ability_id action_id,
        bn::string<96>& output)
{
    if(kind == battle_action_source_kind::direct_attack)
    {
        output += "DIRECT ATTACK";
        return;
    }
    const battle_identity_record* identity = nullptr;
    if(kind ==
            battle_action_source_kind::active_action)
    {
        identity = battle_active_action_identity(action_id);
    }
    else if(kind ==
            battle_action_source_kind::ninja_tool)
    {
        identity = battle_ninja_tool_identity(action_id);
    }
    if(identity)
    {
        output += identity->display_name;
        if(! identity->exact)
        {
            output += "?";
        }
        return;
    }
    if(kind ==
            battle_action_source_kind::active_action)
    {
        output += "ACTION #";
    }
    else if(kind ==
            battle_action_source_kind::ninja_tool)
    {
        output += "TOOL #";
    }
    else
    {
        output += "DIRECT ATTACK";
        return;
    }
    output += bn::to_string<4>(action_id);
}

void append_action_identity(
        const battle_action_menu_view& entry,
        bn::string<96>& output)
{
    append_action_identity(
            entry.kind,
            entry.action_id,
            output);
}

void append_action_cost(
        const battle_action_menu_view& entry,
        bn::string<96>& output)
{
    switch(entry.cost_kind)
    {
    case action_cost_kind::none:
        output += "FREE";
        return;
    case action_cost_kind::current_chakra:
        output += "CK";
        break;
    case action_cost_kind::current_hp:
        output += "HP";
        break;
    case action_cost_kind::
            battle_local_ninja_tool_slot:
        output += "TOOL";
        break;
    default:
        output += "SPECIAL";
        return;
    }
    output += bn::to_string<4>(
            entry.cost_scalar);
}

[[nodiscard]] const battle_scene_unit_view*
combatant_view(
        const battle_scene_snapshot<12>& state,
        battle_unit_id unit_id)
{
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        if(state.units[index].id == unit_id)
        {
            return &state.units[index];
        }
    }
    return nullptr;
}

void append_combatant_hp(
        int hp,
        int max_hp,
        bn::string<96>& output)
{
    output += bn::to_string<4>(hp);
    output += "/";
    output += bn::to_string<4>(max_hp);
}

class battle_ui_runtime_renderer
{
public:
    void reset()
    {
        _sprites.clear();
        _palette.reset();
        _status_panel_palette.reset();
        _bar_palette.reset();
        _action_icon_palette.reset();
        _result_panel.reset();
        _result_background.reset();
        _result_participants.clear();
        _level_up_panel.reset();
        _level_up_portrait_palette.reset();
        _training_panel.reset();
        _training_text.reset();
        _training_rendered_page = 0xFF;
        _turn_banner_palette.reset();
    }

    [[gnu::noinline]] void update(
            const battle_ui_model& model,
            const battle_scene_snapshot<12>& state,
            const battle_result& result,
            const battle_scene_presentation& presentation)
    {
        _sprites.clear();
        if(model.layer == battle_ui_layer::hidden ||
                (presentation.busy() &&
                 presentation.combat().busy() &&
                 ! presentation.combat().map_visible()))
        {
            return;
        }
        if(model.layer == battle_ui_layer::action_menu)
        {
            _add_action_icons(state);
            return;
        }
        if(model.show_result_panel &&
                state.phase == battle_scene_phase::result)
        {
            _add_result_background();
            _update_result_participants(result);
            return;
        }
        if(model.layer == battle_ui_layer::level_up)
        {
            _add_level_up_ui(state, result);
            return;
        }
        if(model.layer == battle_ui_layer::training &&
                state.training_summary_active)
        {
            _add_training_ui(state);
            return;
        }
        _result_participants.clear();
        _result_panel.reset();
        _result_background.reset();
        _ensure_palette();

        if(model.show_result_panel)
        {
            for(int row = 0; row < 4; ++row)
            {
                _add_horizontal_panel(
                        -48 + row * 32);
            }
            return;
        }

        const battle_scene_unit_view* status_unit =
                combatant_view(
                        state, model.status_unit_id);
        const bool expanded_target_status =
                state.phase ==
                                battle_scene_phase::
                                        target_preview ||
                state.phase ==
                                battle_scene_phase::
                                        target_confirmation;
        if(model.show_status_panel && status_unit)
        {
            if(! expanded_target_status)
            {
                _add_horizontal_panel(64);
            }
            if(model.layer != battle_ui_layer::action_menu)
            {
                if(expanded_target_status)
                {
                    _add_bar(
                            64,
                            44,
                            status_unit->hp,
                            status_unit->max_hp,
                            2);
                    _add_bar(
                            64,
                            52,
                            status_unit->chakra,
                            status_unit->max_chakra,
                            1,
                            3);
                }
                else
                {
                    _add_bar(
                            64,
                            60,
                            status_unit->hp,
                            status_unit->max_hp,
                            2);
                    _add_bar(
                            64,
                            68,
                            status_unit->chakra,
                            status_unit->max_chakra,
                            1);
                }
            }
        }
        else if(model.show_instruction_panel)
        {
            _add_horizontal_panel(64);
        }
        if(model.show_round_badge)
        {
            _add_panel(88, -64, 0);
        }
        if(model.show_dialog_panel)
        {
            _add_dialog_panel();
            if(state.phase ==
                            battle_scene_phase::
                                    target_confirmation ||
                    state.phase ==
                            battle_scene_phase::
                                    end_confirmation)
            {
                _add_confirmation_cursor(
                        state.phase ==
                                        battle_scene_phase::
                                                target_confirmation ?
                                state.target_confirmation_yes :
                                state.end_confirmation_yes);
            }
        }
        if(model.show_large_dialog_panel)
        {
            _add_large_dialog_panel();
        }
        if(model.show_menu_panel)
        {
            if(model.layer == battle_ui_layer::command_menu)
            {
                // The map overlay owns the original BG3 command shell.
            }
            else
            {
                _add_menu_column(-88);
            }
        }
        if(model.layer == battle_ui_layer::turn_banner)
        {
            _add_turn_banner();
        }
    }

private:
    void _add_action_icons(
            const battle_scene_snapshot<12>& state)
    {
        if(! _action_icon_palette)
        {
            _action_icon_palette =
                    bn::sprite_items::battle_ui_action_icon
                            .palette_item()
                            .create_palette();
        }
        const int page_start =
                battle_action_ui_page_start(
                        state.player.action_index,
                        state.player.action_count);
        constexpr int page_size = 4;
        for(int row = 0; row < page_size; ++row)
        {
            const int action_index = page_start + row;
            if(action_index >= state.player.action_count ||
                    action_index >=
                            static_cast<int>(
                                    state.player
                                            .action_entries
                                            .size()))
            {
                break;
            }
            const battle_action_menu_view& action =
                    state.player.action_entries[
                            static_cast<std::size_t>(
                                    action_index)];
            _add_action_icon(
                    -32,
                    -32 + row * 16,
                    battle_action_ui_category_icon(action));
            _add_action_icon(
                    -16,
                    -32 + row * 16,
                    battle_action_ui_effect_icon(action));
        }
    }

    void _add_action_icon(
            int x,
            int y,
            battle_action_ui_icon_frame frame)
    {
        if(_sprites.full())
        {
            return;
        }
        bn::sprite_ptr sprite = bn::sprite_ptr::create(
                x,
                y,
                bn::sprite_items::battle_ui_action_icon
                        .shape_size(),
                bn::sprite_items::battle_ui_action_icon
                        .tiles_item()
                        .create_tiles(
                                static_cast<int>(frame)),
                *_action_icon_palette);
        sprite.set_bg_priority(0);
        sprite.set_z_order(0);
        _sprites.push_back(
                static_cast<bn::sprite_ptr&&>(sprite));
    }

    void _add_result_background()
    {
        if(! _result_background)
        {
            _result_background =
                    bn::regular_bg_items::
                            battle_ui_result_background
                                    .create_bg(0, 0);
            _result_background->set_priority(2);
        }
        if(! _result_panel)
        {
            _result_panel =
                    bn::regular_bg_items::
                            battle_ui_result_panel
                                    .create_bg(0, 0);
            _result_panel->set_priority(1);
        }
    }

    void _update_result_participants(
            const battle_result& result)
    {
        _result_participants.clear();
        constexpr int participant_x[] = {
            -20, 36, 92,
        };
        for(std::size_t index = 0;
                index < result.participant_count &&
                index < 3;
                ++index)
        {
            const bn::sprite_item* item = nullptr;
            switch(result.participants[index].character_id)
            {
            case 1:
                item = &bn::sprite_items::
                        battle_ui_result_naruto;
                break;
            case 2:
                item = &bn::sprite_items::
                        battle_ui_result_sasuke;
                break;
            case 3:
                item = &bn::sprite_items::
                        battle_ui_result_sakura;
                break;
            default:
            {
                const battle_unit_idle_visual visual =
                        battle_unit_idle_visual_for(
                                result.participants[index]
                                        .character_id);
                item = visual.item;
                break;
            }
            }
            if(! item)
            {
                continue;
            }
            bn::sprite_ptr sprite =
                    item->create_sprite(
                            participant_x[index], -8);
            sprite.set_bg_priority(0);
            sprite.set_z_order(0);
            _result_participants.push_back(
                    static_cast<bn::sprite_ptr&&>(sprite));
        }
    }

    [[nodiscard]] static int _level_up_value_frame(
            int value)
    {
        switch(value)
        {
        case 0:
            return 0;
        case 1:
            return 1;
        case 14:
            return 2;
        case 15:
            return 3;
        default:
            return 0;
        }
    }

    void _add_level_up_sprite(
            const bn::sprite_item& item,
            const bn::sprite_palette_ptr& palette,
            int x,
            int y,
            int graphics_index)
    {
        if(_sprites.full())
        {
            return;
        }
        bn::sprite_ptr sprite = bn::sprite_ptr::create(
                x,
                y,
                item.shape_size(),
                item.tiles_item().create_tiles(
                        graphics_index),
                palette);
        sprite.set_bg_priority(0);
        sprite.set_z_order(0);
        _sprites.push_back(
                static_cast<bn::sprite_ptr&&>(sprite));
    }

    void _add_level_up_ui(
            const battle_scene_snapshot<12>& state,
            const battle_result& result)
    {
        if(state.result_participant_index >=
                result.participant_count)
        {
            return;
        }
        const battle_result_participant& participant =
                result.participants[state.result_participant_index];
        if(participant.character_id < 1 ||
                participant.character_id > 3)
        {
            return;
        }
        if(! _level_up_panel)
        {
            _level_up_panel =
                    bn::regular_bg_items::
                            battle_ui_level_up_panel
                                    .create_bg(0, 0);
            _level_up_panel->set_priority(1);
        }
        if(! _level_up_portrait_palette)
        {
            _level_up_portrait_palette =
                    bn::sprite_items::
                            battle_ui_level_up_portrait_64x64
                                    .palette_item()
                                    .create_palette();
        }

        const int character_index =
                participant.character_id - 1;
        const int page =
                state.level_up_detail_page ? 1 : 0;
        const int title_frame =
                (character_index * 2 + page) * 2;
        _add_level_up_sprite(
                bn::sprite_items::battle_ui_level_up_title,
                *_level_up_portrait_palette,
                -88,
                -40,
                title_frame);
        _add_level_up_sprite(
                bn::sprite_items::battle_ui_level_up_title,
                *_level_up_portrait_palette,
                -24,
                -40,
                title_frame + 1);

        const int growth[] = {
            participant.stat_growth.max_hp,
            participant.stat_growth.chakra_capacity,
            participant.stat_growth.attack,
            participant.stat_growth.defense,
            participant.stat_growth.agility,
            participant.stat_growth.movement,
            participant.stat_growth.ninja_tool_capacity,
        };
        for(int row = 0; row < 7; ++row)
        {
            _add_level_up_sprite(
                    bn::sprite_items::
                            battle_ui_level_up_value,
                    *_level_up_portrait_palette,
                    64,
                    -32 + row * 16,
                    _level_up_value_frame(growth[row]));
        }

        _add_level_up_sprite(
                bn::sprite_items::
                        battle_ui_level_up_portrait_64x64,
                *_level_up_portrait_palette,
                -72,
                -8,
                character_index);
        _add_level_up_sprite(
                bn::sprite_items::
                        battle_ui_level_up_portrait_16x32,
                *_level_up_portrait_palette,
                -32,
                -24,
                character_index * 2);
        _add_level_up_sprite(
                bn::sprite_items::
                        battle_ui_level_up_portrait_16x32,
                *_level_up_portrait_palette,
                -32,
                8,
                character_index * 2 + 1);
        _add_level_up_sprite(
                bn::sprite_items::
                        battle_ui_level_up_portrait_32x16,
                *_level_up_portrait_palette,
                -88,
                32,
                character_index * 2);
        _add_level_up_sprite(
                bn::sprite_items::
                        battle_ui_level_up_portrait_32x16,
                *_level_up_portrait_palette,
                -56,
                32,
                character_index * 2 + 1);
        _add_level_up_sprite(
                bn::sprite_items::
                        battle_ui_level_up_portrait_16x16,
                *_level_up_portrait_palette,
                -32,
                32,
                character_index);

        if(! _sprites.full())
        {
            _add_level_up_sprite(
                    bn::sprite_items::
                            battle_ui_level_up_eye,
                    *_level_up_portrait_palette,
                    104,
                    -64,
                    0);
        }
    }

    void _add_training_ui(
            const battle_scene_snapshot<12>& state)
    {
        if(! _training_panel)
        {
            _training_panel =
                    bn::regular_bg_items::
                            battle_ui_training_panel
                                    .create_bg(0, 0);
            _training_panel->set_priority(2);
        }
        const std::uint8_t page =
                state.training_detail_page < 6 ?
                        state.training_detail_page :
                        5;
        if(! _training_text ||
                _training_rendered_page != page)
        {
            _training_text.reset();
            const bn::regular_bg_item* item = nullptr;
            switch(page)
            {
            case 0:
                item = &bn::regular_bg_items::
                        battle_ui_training_text_0;
                break;
            case 1:
                item = &bn::regular_bg_items::
                        battle_ui_training_text_1;
                break;
            case 2:
                item = &bn::regular_bg_items::
                        battle_ui_training_text_2;
                break;
            case 3:
                item = &bn::regular_bg_items::
                        battle_ui_training_text_3;
                break;
            case 4:
                item = &bn::regular_bg_items::
                        battle_ui_training_text_4;
                break;
            default:
                item = &bn::regular_bg_items::
                        battle_ui_training_text_5;
                break;
            }
            _training_text = item->create_bg(0, 0);
            _training_text->set_priority(1);
            _training_rendered_page = page;
        }
        if(! _sprites.full())
        {
            bn::sprite_ptr eye =
                    bn::sprite_items::
                            battle_ui_level_up_eye
                                    .create_sprite(
                                            104,
                                            page % 2 == 0 ?
                                                    -48 :
                                                    64);
            eye.set_bg_priority(0);
            eye.set_z_order(0);
            _sprites.push_back(
                    static_cast<bn::sprite_ptr&&>(eye));
        }
    }

    void _ensure_palette()
    {
        if(! _palette)
        {
            _palette =
                    bn::sprite_items::battle_ui_panel
                            .palette_item()
                            .create_palette();
        }
        if(! _bar_palette)
        {
            _bar_palette =
                    bn::sprite_items::battle_ui_bar
                            .palette_item()
                            .create_palette();
        }
        if(! _status_panel_palette)
        {
            _status_panel_palette =
                    bn::sprite_items::
                            battle_ui_status_panel
                                    .palette_item()
                                    .create_palette();
        }
    }

    [[nodiscard]] bn::sprite_ptr
    _create_status_panel_sprite(
            int x,
            int y,
            int graphics_index)
    {
        return bn::sprite_ptr::create(
                x,
                y,
                bn::sprite_items::
                        battle_ui_status_panel
                                .shape_size(),
                bn::sprite_items::
                        battle_ui_status_panel
                                .tiles_item()
                                .create_tiles(
                                        graphics_index),
                *_status_panel_palette);
    }

    [[nodiscard]] bn::sprite_ptr _create_bar_sprite(
            int x,
            int y,
            int graphics_index)
    {
        return bn::sprite_ptr::create(
                x,
                y,
                bn::sprite_items::battle_ui_bar.shape_size(),
                bn::sprite_items::battle_ui_bar
                        .tiles_item()
                        .create_tiles(graphics_index),
                *_bar_palette);
    }

    [[nodiscard]] bn::sprite_ptr _create_sprite(
            const bn::sprite_item& item,
            int x,
            int y,
            int graphics_index)
    {
        return bn::sprite_ptr::create(
                x,
                y,
                item.shape_size(),
                item.tiles_item().create_tiles(
                        graphics_index),
                *_palette);
    }

    void _add_panel(
            int x,
            int y,
            int graphics_index,
            bool horizontal_flip = false,
            bool vertical_flip = false)
    {
        if(_sprites.full())
        {
            return;
        }
        bn::sprite_ptr sprite = _create_sprite(
                bn::sprite_items::battle_ui_panel,
                x,
                y,
                graphics_index);
        sprite.set_bg_priority(0);
        sprite.set_z_order(20);
        sprite.set_horizontal_flip(horizontal_flip);
        sprite.set_vertical_flip(vertical_flip);
        _sprites.push_back(
                static_cast<bn::sprite_ptr&&>(sprite));
    }

    // The round banner of the original (S49 original frame 15).  The panel
    // measures 80x48, which is larger than any 4bpp sprite, so the asset is
    // a strip of six 32x32 pieces and the words are already baked into them.
    void _add_turn_banner()
    {
        if(! _turn_banner_palette)
        {
            _turn_banner_palette =
                    bn::sprite_items::battle_ui_turn_banner_panel
                            .palette_item()
                            .create_palette();
        }
        constexpr int piece_x[] = { -32, 0, 32, -32, 0, 32, };
        constexpr int piece_y[] = { -24, -24, -24, 8, 8, 8, };
        for(int index = 0; index < 6; ++index)
        {
            if(_sprites.full())
            {
                return;
            }
            bn::sprite_ptr sprite = bn::sprite_ptr::create(
                    piece_x[index],
                    piece_y[index],
                    bn::sprite_items::battle_ui_turn_banner_panel
                            .shape_size(),
                    bn::sprite_items::battle_ui_turn_banner_panel
                            .tiles_item()
                            .create_tiles(index),
                    *_turn_banner_palette);
            sprite.set_bg_priority(0);
            sprite.set_z_order(20);
            _sprites.push_back(
                    static_cast<bn::sprite_ptr&&>(sprite));
        }
    }

    void _add_horizontal_panel(int y)
    {
        _add_status_panel(-88, y, 0);
        _add_status_panel(-24, y, 1);
        _add_status_panel(40, y, 2);
        _add_status_panel(104, y, 3);
    }

    void _add_status_panel(
            int x,
            int y,
            int graphics_index)
    {
        if(_sprites.full())
        {
            return;
        }
        bn::sprite_ptr sprite =
                _create_status_panel_sprite(
                        x, y, graphics_index);
        sprite.set_bg_priority(0);
        sprite.set_z_order(20);
        _sprites.push_back(
                static_cast<bn::sprite_ptr&&>(sprite));
    }

    void _add_dialog_panel()
    {
        _add_dialog_slice(-32, 0);
        _add_dialog_slice(0, 1);
        _add_dialog_slice(32, 2);
    }

    void _add_confirmation_cursor(bool confirmation_yes)
    {
        if(_sprites.full())
        {
            return;
        }
        bn::sprite_ptr sprite =
                bn::sprite_items::
                        battle_ui_confirmation_cursor
                                .create_sprite(
                                        -12,
                                        confirmation_yes ?
                                                -24 :
                                                -8);
        sprite.set_bg_priority(0);
        sprite.set_z_order(0);
        _sprites.push_back(
                static_cast<bn::sprite_ptr&&>(sprite));
    }

    void _add_large_dialog_panel()
    {
        _add_large_dialog_slice(-28, -24, 0);
        _add_large_dialog_slice(28, -24, 1);
        _add_large_dialog_slice(-28, 16, 2);
        _add_large_dialog_slice(28, 16, 3);
    }

    void _add_large_dialog_slice(
            int x,
            int y,
            int graphics_index)
    {
        if(_sprites.full())
        {
            return;
        }
        bn::sprite_ptr sprite = _create_sprite(
                bn::sprite_items::
                        battle_ui_large_dialog_panel,
                x,
                y,
                graphics_index);
        sprite.set_bg_priority(0);
        sprite.set_z_order(20);
        _sprites.push_back(
                static_cast<bn::sprite_ptr&&>(sprite));
    }

    void _add_dialog_slice(int x, int graphics_index)
    {
        if(_sprites.full())
        {
            return;
        }
        bn::sprite_ptr sprite = _create_sprite(
                bn::sprite_items::
                        battle_ui_dialog_panel,
                x,
                -24,
                graphics_index);
        sprite.set_bg_priority(0);
        sprite.set_z_order(20);
        _sprites.push_back(
                static_cast<bn::sprite_ptr&&>(sprite));
    }

    void _add_menu_column(int x)
    {
        _add_panel(x, -48, 2);
        _add_panel(x, -16, 3);
        _add_panel(x, 16, 2, false, true);
    }

    void _add_bar(
            int x,
            int y,
            int value,
            int maximum,
            int fill_graphics,
            int track_graphics = 0)
    {
        if(_sprites.full())
        {
            return;
        }
        bn::sprite_ptr track = _create_bar_sprite(
                x, y, track_graphics);
        track.set_bg_priority(0);
        track.set_z_order(10);
        _sprites.push_back(
                static_cast<bn::sprite_ptr&&>(track));
        if(value <= 0 || maximum <= 0 || _sprites.full())
        {
            return;
        }
        if(value > maximum)
        {
            value = maximum;
        }
        const bn::fixed scale =
                bn::fixed(value) / maximum;
        bn::sprite_ptr fill =
                _create_bar_sprite(x, y, fill_graphics);
        fill.set_horizontal_scale(scale);
        fill.set_x(x - 16 + scale * 16);
        fill.set_bg_priority(0);
        fill.set_z_order(5);
        _sprites.push_back(
                static_cast<bn::sprite_ptr&&>(fill));
    }

    bn::vector<
            bn::sprite_ptr,
            battle_runtime_scene_sprite_budget::
                    maximum_ui_sprites> _sprites;
    bn::optional<bn::sprite_palette_ptr> _palette;
    bn::optional<bn::sprite_palette_ptr> _status_panel_palette;
    bn::optional<bn::sprite_palette_ptr> _bar_palette;
    bn::optional<bn::sprite_palette_ptr> _action_icon_palette;
    bn::optional<bn::regular_bg_ptr> _result_panel;
    bn::optional<bn::regular_bg_ptr> _result_background;
    bn::vector<bn::sprite_ptr, 3> _result_participants;
    bn::optional<bn::regular_bg_ptr> _level_up_panel;
    bn::optional<bn::sprite_palette_ptr>
            _level_up_portrait_palette;
    bn::optional<bn::regular_bg_ptr> _training_panel;
    bn::optional<bn::regular_bg_ptr> _training_text;
    std::uint8_t _training_rendered_page = 0xFF;
    bn::optional<bn::sprite_palette_ptr> _turn_banner_palette;
};

class battle_range_overlay
{
public:
    static constexpr int columns = 32;
    static constexpr int rows = 32;

    battle_range_overlay() :
        _map_item(_cells[0], bn::size(columns, rows)),
        _status_map_item(
                _status_cells[0],
                bn::size(columns, rows))
    {
    }

    void reset()
    {
        _status_map.reset();
        _status_bg.reset();
        _restore_action_palette();
        _map.reset();
        _bg.reset();
    }

    [[gnu::noinline]] void update(
            const battle_scene_snapshot<12>& state,
            bool presentation_busy,
            const bn::camera_ptr& camera,
            const bn::regular_bg_ptr& map_bg)
    {
        const bool move =
                state.phase ==
                battle_scene_phase::move_selection;
        const bool target_selection =
                state.phase ==
                        battle_scene_phase::target_selection;
        const bool target_status =
                state.phase ==
                                battle_scene_phase::
                                        target_preview ||
                state.phase ==
                                battle_scene_phase::
                                        target_confirmation;
        const bool target =
                target_selection || target_status;
        const bool action =
                state.phase ==
                battle_scene_phase::action_selection;
        const bool command =
                state.phase ==
                battle_scene_phase::command_selection;
        const bool panel = action || command;
        if(presentation_busy ||
                (! panel && ! move && ! target) ||
                (! panel &&
                 (state.overlay_width <= 0 ||
                  state.overlay_height <= 0)))
        {
            reset();
            return;
        }
        if(_map && _map->palette() != map_bg.palette())
        {
            reset();
        }

        if(! _bg)
        {
            bn::bg_tiles::set_allow_offset(false);
            _prepare_tiles(map_bg.palette());
            const bn::regular_bg_tiles_item tiles_item(
                    bn::span<const bn::tile>(
                            _tiles.data(),
                            _tiles.size()),
                    bn::bpp_mode::BPP_8);
            bn::regular_bg_map_ptr overlay_map =
                    _map_item.create_map(
                            tiles_item.create_tiles(false),
                            map_bg.palette());
            _bg = bn::regular_bg_ptr::create(
                    0, 0, overlay_map);
            _map = overlay_map;
            bn::bg_tiles::set_allow_offset(true);
        }

        _bg->set_priority(panel ? 0 : 2);
        _bg->set_blending_enabled(! panel);
        _begin_action_palette(map_bg.palette());
        if(action)
        {
            _status_map.reset();
            _status_bg.reset();
            _populate_action_cells();
            _map->reload_cells_ref();
            return;
        }
        if(command)
        {
            _status_map.reset();
            _status_bg.reset();
            _populate_command_cells(
                    state.player.command_count);
            _map->reload_cells_ref();
            return;
        }

        const bn::fixed range_blend_weight =
                bn::fixed(
                        battle_range_ui_blend_numerator) /
                battle_range_ui_blend_denominator;
        bn::blending::set_transparency_weights(
                range_blend_weight,
                range_blend_weight);
        _cells.fill(0);
        const int overlay_height =
                state.overlay_height < 32 ?
                state.overlay_height : 32;
        const int overlay_width =
                state.overlay_width < 32 ?
                state.overlay_width : 32;
        for(int y = 0; y < overlay_height; ++y)
        {
            const std::uint32_t move_row =
                    state.move_overlay_rows[
                            static_cast<std::size_t>(y)];
            const std::uint32_t range_row =
                    state.range_overlay_rows[
                            static_cast<std::size_t>(y)];
            const std::uint32_t target_row =
                    state.target_overlay_rows[
                            static_cast<std::size_t>(y)];
            const std::uint32_t blocked_row =
                    state.blocked_overlay_rows[
                            static_cast<std::size_t>(y)];
            for(int x = 0; x < overlay_width; ++x)
            {
                const std::uint32_t bit =
                        std::uint32_t(1) << x;
                const bool in_move_range =
                        (move_row & bit) != 0;
                const bool in_range =
                        (range_row & bit) != 0;
                const bool legal_target =
                        (target_row & bit) != 0;
                const bool blocked =
                        (blocked_row & bit) != 0;
                const grid_point point = { x, y };
                const battle_range_ui_tile_kind tile_kind =
                        battle_range_ui_cell_kind(
                                move,
                                point == state.cursor,
                                in_move_range,
                                in_range,
                                legal_target,
                                blocked);
                const int screen_x =
                        (world_x(point) - camera.x())
                                .integer();
                const int screen_y =
                        (world_y(point) - camera.y())
                                .integer();
                const int first_column =
                        (screen_x + 112) / 8;
                const int first_row =
                        (screen_y + 120) / 8;
                for(int tile_y = 0; tile_y < 2; ++tile_y)
                {
                    const int row =
                            first_row + tile_y;
                    if(row < 0 || row >= rows)
                    {
                        continue;
                    }
                    for(int tile_x = 0;
                            tile_x < 4;
                            ++tile_x)
                    {
                        const int column =
                                first_column +
                                tile_x;
                        if(column < 0 ||
                                column >= columns)
                        {
                            continue;
                        }
                        _cells[
                                static_cast<std::size_t>(
                                        row * columns +
                                        column)] =
                                static_cast<
                                        bn::regular_bg_map_cell>(
                                                battle_range_ui_tile_index(
                                                        tile_kind,
                                                        tile_x,
                                                        tile_y));
                    }
                }
            }
        }
        _map->reload_cells_ref();
        if(target_status)
        {
            if(! _status_bg)
            {
                bn::regular_bg_map_ptr status_map =
                        _status_map_item.create_map(
                                _map->tiles(),
                                map_bg.palette());
                _status_bg =
                        bn::regular_bg_ptr::create(
                                0, 0, status_map);
                _status_map = status_map;
            }
            _status_bg->set_priority(0);
            _status_bg->set_blending_enabled(false);
            _populate_target_status_cells();
            _status_map->reload_cells_ref();
        }
        else
        {
            _status_map.reset();
            _status_bg.reset();
        }
    }

private:
    static constexpr int range_palette_first_color = 224;
    static constexpr int action_palette_first_color = 240;

    [[gnu::noinline]] void _begin_action_palette(
            bn::bg_palette_ptr palette)
    {
        if(_action_palette &&
                *_action_palette == palette)
        {
            return;
        }
        if(! _action_palette ||
                *_action_palette != palette)
        {
            _restore_action_palette();
            const bn::span<const bn::color> colors =
                    palette.colors();
            BN_ASSERT(
                    colors.size() >=
                            action_palette_first_color + 16,
                    "Battle overlays require an 8BPP map palette");
            for(int index = 0; index < 32; ++index)
            {
                _saved_action_colors[
                        static_cast<std::size_t>(index)] =
                        colors[
                                range_palette_first_color +
                                index];
            }
            _action_palette = palette;
        }

        constexpr auto range_color =
                [](battle_range_ui_rgb5 color)
        {
            return bn::color(
                    color.red,
                    color.green,
                    color.blue);
        };
        constexpr std::array<bn::color, 16>
                range_colors = {
            bn::color(0, 0, 0),
            range_color(
                    battle_range_ui_grid_secondary_color),
            range_color(
                    battle_range_ui_move_primary_color),
            range_color(
                    battle_range_ui_move_secondary_color),
            range_color(
                    battle_range_ui_attack_primary_color),
            range_color(
                    battle_range_ui_attack_secondary_color),
            range_color(
                    battle_range_ui_cursor_primary_color),
            range_color(
                    battle_range_ui_cursor_secondary_color),
            range_color(
                    battle_range_ui_target_primary_color),
            range_color(
                    battle_range_ui_target_secondary_color),
            range_color(
                    battle_range_ui_blocked_primary_color),
            range_color(
                    battle_range_ui_blocked_secondary_color),
            bn::color(0, 0, 0),
            bn::color(0, 0, 0),
            bn::color(0, 0, 0),
            bn::color(0, 0, 0),
        };
        constexpr std::array<bn::color, 16>
                panel_colors = {
            bn::color(0, 0, 0),
            range_color(
                    battle_range_ui_move_primary_color),
            range_color(
                    battle_range_ui_move_secondary_color),
            range_color(
                    battle_range_ui_attack_primary_color),
            range_color(
                    battle_range_ui_attack_secondary_color),
            range_color(
                    battle_range_ui_cursor_primary_color),
            range_color(
                    battle_range_ui_cursor_secondary_color),
            bn::color(0, 0, 0),
            bn::color(0, 0, 0),
            bn::color(28, 30, 26),
            bn::color(7, 8, 7),
            bn::color(12, 23, 14),
            bn::color(13, 19, 11),
            bn::color(12, 14, 11),
            bn::color(28, 26, 12),
            bn::color(31, 31, 31),
        };
        for(int index = 0; index < 16; ++index)
        {
            palette.set_color(
                    range_palette_first_color + index,
                    range_colors[
                            static_cast<std::size_t>(
                                    index)]);
            palette.set_color(
                    action_palette_first_color + index,
                    panel_colors[
                            static_cast<std::size_t>(
                                    index)]);
        }
    }

    [[gnu::noinline]] void _restore_action_palette()
    {
        if(! _action_palette)
        {
            return;
        }
        for(int index = 0; index < 32; ++index)
        {
            _action_palette->set_color(
                    range_palette_first_color + index,
                    _saved_action_colors[
                            static_cast<std::size_t>(
                                    index)]);
        }
        _action_palette.reset();
    }

    [[gnu::noinline]] void _populate_action_cells()
    {
        constexpr int visible_first_column = 1;
        constexpr int visible_first_row = 6;
        constexpr int visible_columns = 30;
        constexpr int visible_rows = 20;
        _cells.fill(0);
        for(int y = 0; y < visible_rows; ++y)
        {
            for(int x = 0; x < visible_columns; ++x)
            {
                const battle_action_ui_map_cell
                        projection =
                                battle_action_ui_map_cell_for(
                                        { x, y });
                bn::regular_bg_map_cell_info cell;
                cell.set_tile_index(
                        static_cast<int>(
                                projection.tile));
                cell.set_horizontal_flip(
                        projection.horizontal_flip);
                cell.set_vertical_flip(
                        projection.vertical_flip);
                _cells[
                        static_cast<std::size_t>(
                                (visible_first_row + y) *
                                        columns +
                                visible_first_column + x)] =
                        cell.cell();
            }
        }
    }

    [[gnu::noinline]] void _populate_command_cells(
            int command_count)
    {
        constexpr int visible_first_column = 1;
        constexpr int visible_first_row = 6;
        constexpr int visible_columns = 30;
        constexpr int visible_rows = 20;
        _cells.fill(0);
        for(int y = 0; y < visible_rows; ++y)
        {
            for(int x = 0; x < visible_columns; ++x)
            {
                const battle_action_ui_map_cell
                        projection =
                                battle_command_ui_map_cell_for(
                                        { x, y },
                                        command_count);
                bn::regular_bg_map_cell_info cell;
                cell.set_tile_index(
                        static_cast<int>(
                                projection.tile));
                cell.set_horizontal_flip(
                        projection.horizontal_flip);
                cell.set_vertical_flip(
                        projection.vertical_flip);
                _cells[
                        static_cast<std::size_t>(
                                (visible_first_row + y) *
                                        columns +
                                visible_first_column + x)] =
                        cell.cell();
            }
        }
    }

    [[gnu::noinline]] void _populate_target_status_cells()
    {
        constexpr int visible_first_column = 1;
        constexpr int visible_first_row = 20;
        constexpr int visible_columns = 30;
        constexpr int visible_rows = 6;
        _status_cells.fill(0);
        for(int y = 0; y < visible_rows; ++y)
        {
            for(int x = 0; x < visible_columns; ++x)
            {
                const battle_action_ui_map_cell
                        projection =
                                battle_target_status_ui_map_cell_for(
                                        { x, y });
                bn::regular_bg_map_cell_info cell;
                cell.set_tile_index(
                        static_cast<int>(
                                projection.tile));
                cell.set_horizontal_flip(
                        projection.horizontal_flip);
                cell.set_vertical_flip(
                        projection.vertical_flip);
                _status_cells[
                        static_cast<std::size_t>(
                                (visible_first_row + y) *
                                        columns +
                                visible_first_column + x)] =
                        cell.cell();
            }
        }
    }

    [[gnu::noinline]] void _prepare_tiles(
            const bn::bg_palette_ptr&)
    {
        _tiles = {};
        std::uint8_t* pixels =
                reinterpret_cast<std::uint8_t*>(
                        _tiles.data());
        for(int kind_index = 0;
                kind_index <
                        battle_range_ui_range_kind_count;
                ++kind_index)
        {
            const battle_range_ui_tile_kind kind =
                    static_cast<
                            battle_range_ui_tile_kind>(
                                    kind_index);
            for(int tile_y = 0;
                    tile_y <
                            battle_range_ui_tiles_per_cell_y;
                    ++tile_y)
            {
                for(int tile_x = 0;
                        tile_x <
                                battle_range_ui_tiles_per_cell_x;
                        ++tile_x)
                {
                    const int tile_index =
                            battle_range_ui_tile_index(
                                    kind,
                                    tile_x,
                                    tile_y);
                    for(int y = 0; y < 8; ++y)
                    {
                        for(int x = 0; x < 8; ++x)
                        {
                            pixels[
                                    tile_index * 64 +
                                    y * 8 + x] =
                                    static_cast<std::uint8_t>(
                                            battle_range_ui_pixel_index(
                                                    kind,
                                                    tile_x,
                                                    tile_y,
                                                    x,
                                                    y));
                        }
                    }
                }
            }
        }

        for(int tile_index =
                    battle_range_ui_action_first_tile;
                tile_index <
                        battle_range_ui_action_end_tile;
                ++tile_index)
        {
            for(int y = 0; y < 8; ++y)
            {
                for(int x = 0; x < 8; ++x)
                {
                    pixels[tile_index * 64 +
                           y * 8 + x] =
                            static_cast<std::uint8_t>(
                                    action_palette_first_color +
                                    battle_action_ui_original_pixel(
                                            static_cast<
                                                    battle_action_ui_map_tile>(
                                                    tile_index),
                                            x,
                                            y));
                }
            }
        }
    }

    alignas(int) std::array<
            bn::regular_bg_map_cell,
            columns * rows> _cells = {};
    alignas(int) std::array<
            bn::regular_bg_map_cell,
            columns * rows> _status_cells = {};
    // In 8BPP mode each logical 8x8 tile occupies two 32-byte
    // bn::tile storage units.
    alignas(int) std::array<
            bn::tile,
            battle_range_ui_storage_tile_count> _tiles = {};
    bn::regular_bg_map_item _map_item;
    bn::regular_bg_map_item _status_map_item;
    bn::optional<bn::regular_bg_ptr> _bg;
    bn::optional<bn::regular_bg_map_ptr> _map;
    bn::optional<bn::regular_bg_ptr> _status_bg;
    bn::optional<bn::regular_bg_map_ptr> _status_map;
    bn::optional<bn::bg_palette_ptr> _action_palette;
    std::array<bn::color, 32>
            _saved_action_colors = {};
};

void update_range_overlay(
        const battle_scene_snapshot<12>& state,
        bool presentation_busy,
        const bn::camera_ptr& camera,
        const bn::regular_bg_ptr& map,
        battle_range_overlay& overlay)
{
    overlay.update(
            state,
            presentation_busy,
            camera,
            map);
}

void render_duel_resource_value(
        int panel_screen_x,
        int y,
        int value,
        int maximum,
        bn::sprite_text_generator& generator,
        bn::vector<
                bn::sprite_ptr,
                battle_runtime_scene_sprite_budget::
                        maximum_text_sprites>& sprites)
{
    bn::string<8> value_text =
            bn::to_string<8>(value);
    bn::string<8> maximum_text =
            bn::to_string<8>(maximum);
    const int current_right =
            panel_screen_x - 40;
    const int maximum_right =
            panel_screen_x - 8;
    generator.set_right_alignment();
    generator.generate(
            current_right, y, value_text, sprites);
    generator.set_left_alignment();
    generator.generate(
            current_right, y, "/", sprites);
    generator.set_right_alignment();
    generator.generate(
            maximum_right, y, maximum_text, sprites);
}

void render_text(
        const battle_scene_snapshot<12>& state,
        const battle_training_snapshot&
                training,
        const battle_result& result,
        const battle_runtime_scene_config& config,
        bool rejected,
        const battle_scene_presentation& presentation,
        bn::sprite_text_generator& generator,
        bn::sprite_text_generator& action_generator,
        bn::sprite_text_generator& duel_status_generator,
        bn::vector<
                bn::sprite_ptr,
                battle_runtime_scene_sprite_budget::
                        maximum_text_sprites>& sprites)
{
    sprites.clear();
    const bool presentation_busy =
            presentation.busy();
    if(state.phase ==
                    battle_scene_phase::script_blocked &&
            ! presentation_busy)
    {
        return;
    }
    generator.set_left_alignment();

    const battle_combat_presentation& combat =
            presentation.combat();
    if(combat.resource() ==
                    battle_combat_presentation_resource::
                            action_16_fire_movie_components ||
            combat.resource() ==
                    battle_combat_presentation_resource::
                            action_16_fire_cutin_components)
    {
        // The original component movie already owns its action title and
        // dialogue layers. Do not overlay the generic text presentation.
        return;
    }
    if(presentation_busy &&
            combat.busy() &&
            ! combat.map_visible())
    {
        if(combat.title_visible() ||
                combat.movie_visible() ||
                combat.hud_visible())
        {
            bn::string<96> action;
            append_action_identity(
                    presentation.event().direct_attack ?
                            battle_action_source_kind::
                                    direct_attack :
                    presentation.event().ninja_tool ?
                            battle_action_source_kind::
                                    ninja_tool :
                            battle_action_source_kind::
                                    active_action,
                    presentation.event().action_id,
                    action);
            action_generator.set_left_alignment();
            action_generator.set_palette_item(
                    bn::sprite_items::
                            battle_ui_panel
                                    .palette_item());
            action_generator.generate(
                    -104,
                    -64,
                    action,
                    sprites);
        }
        if(combat.hud_visible())
        {
            const battle_scene_unit_view* actor =
                    combatant_view(
                            state,
                            presentation.event().actor_id);
            const battle_scene_unit_view* target =
                    combatant_view(
                            state,
                            presentation.event().target_id);
            const battle_scene_unit_view* player = nullptr;
            const battle_scene_unit_view* enemy = nullptr;
            int player_hp = -1;
            int player_max_hp = -1;
            int enemy_hp = -1;
            int enemy_max_hp = -1;
            if(actor)
            {
                const int displayed_hp =
                        combat.displayed_actor_hp();
                const int displayed_max_hp =
                        combat.displayed_actor_max_hp();
                if(actor->side == battle_side::player)
                {
                    player = actor;
                    player_hp = displayed_hp >= 0 ?
                            displayed_hp : actor->hp;
                    player_max_hp = displayed_max_hp >= 0 ?
                            displayed_max_hp : actor->max_hp;
                }
                else
                {
                    enemy = actor;
                    enemy_hp = displayed_hp >= 0 ?
                            displayed_hp : actor->hp;
                    enemy_max_hp = displayed_max_hp >= 0 ?
                            displayed_max_hp : actor->max_hp;
                }
            }
            if(target)
            {
                const int displayed_hp =
                        combat.displayed_target_hp();
                const int displayed_max_hp =
                        combat.displayed_target_max_hp();
                if(target->side == battle_side::player)
                {
                    player = target;
                    player_hp = displayed_hp >= 0 ?
                            displayed_hp : target->hp;
                    player_max_hp = displayed_max_hp >= 0 ?
                            displayed_max_hp : target->max_hp;
                }
                else
                {
                    enemy = target;
                    enemy_hp = displayed_hp >= 0 ?
                            displayed_hp : target->hp;
                    enemy_max_hp = displayed_max_hp >= 0 ?
                            displayed_max_hp : target->max_hp;
                }
            }
            if(player)
            {
                bn::string<96> player_name;
                append_unit_identity(*player, player_name);
                action_generator.set_left_alignment();
                action_generator.set_palette_item(
                        bn::sprite_items::
                                battle_ui_panel
                                        .palette_item());
                if(combat.single_actor_stage())
                {
                    action_generator.generate(
                            16, 48, player_name, sprites);
                }
                else
                {
                    action_generator.generate(
                            -104, 48, player_name, sprites);
                }
                duel_status_generator.set_palette_item(
                        bn::sprite_items::
                                battle_ui_panel
                                        .palette_item());
                const int player_panel_screen_x =
                        combat.single_actor_stage() ?
                                120 : 0;
                render_duel_resource_value(
                        player_panel_screen_x,
                        64,
                        player_hp,
                        player_max_hp,
                        duel_status_generator,
                        sprites);
                render_duel_resource_value(
                        player_panel_screen_x,
                        72,
                        player->chakra,
                        player->max_chakra,
                        duel_status_generator,
                        sprites);
            }
            if(enemy)
            {
                bn::string<96> enemy_name;
                append_unit_identity(*enemy, enemy_name);
                action_generator.set_left_alignment();
                action_generator.set_palette_item(
                        bn::sprite_items::
                                battle_ui_panel
                                        .palette_item());
                action_generator.generate(
                        16, 48, enemy_name, sprites);
                duel_status_generator.set_palette_item(
                        bn::sprite_items::
                                battle_ui_panel
                                        .palette_item());
                render_duel_resource_value(
                        120,
                        64,
                        enemy_hp,
                        enemy_max_hp,
                        duel_status_generator,
                        sprites);
                render_duel_resource_value(
                        120,
                        72,
                        enemy->chakra,
                        enemy->max_chakra,
                        duel_status_generator,
                        sprites);
            }
        }
        return;
    }

    bn::string<48> header = config.title;
    header += " R";
    header += bn::to_string<4>(state.round);
    header += state.current_side == battle_side::player ?
            " P" : " E";
    generator.generate(-116, -72, header, sprites);

    bn::string<48> roster;
    roster += bn::to_string<4>(
            static_cast<int>(state.active_unit_count));
    roster += "/";
    roster += bn::to_string<4>(
            static_cast<int>(state.unit_count));
    roster += " ";
    roster += presentation_busy ? "RESOLVING" :
                                  phase_name(state.phase);
    generator.generate(-116, -60, roster, sprites);

    bn::string<96> detail;
    bn::string<96> detail_status;
    if(presentation_busy)
    {
        if(presentation.event().capture_count > 0)
        {
            detail = "CAT CAPTURED";
            detail_status = "CAPTURE +";
            detail_status += bn::to_string<4>(
                    presentation.event().capture_count);
        }
        else if(presentation.event().
                has_side_start_passive)
        {
            switch(presentation.event().passive_kind)
            {
            case battle_side_start_passive_kind::
                    nine_tail_chakra:
                detail = "NINE-TAIL CHAKRA";
                break;
            case battle_side_start_passive_kind::
                    berserk_symbol:
                detail = "BERSERK SYMBOL";
                break;
            case battle_side_start_passive_kind::
                    inner_sakura:
                detail = "INNER SAKURA";
                break;
            case battle_side_start_passive_kind::
                    battle_11_dual_boost:
                detail = "BATTLE 11 BOOST";
                break;
            default:
                detail = "PASSIVE ";
                detail += bn::to_string<4>(
                        presentation.event().
                                passive);
                break;
            }
            if(presentation.event().
                       resource_hp_delta != 0)
            {
                detail_status = "HP +";
                detail_status += bn::to_string<4>(
                        presentation.event().
                                resource_hp_delta);
            }
            if(presentation.event().
                       resource_chakra_delta != 0)
            {
                if(! detail_status.empty())
                {
                    detail_status += " ";
                }
                detail_status += "CK +";
                detail_status += bn::to_string<4>(
                        presentation.event().
                                resource_chakra_delta);
            }
            if(presentation.event().
                       passive_status_code != 0)
            {
                if(! detail_status.empty())
                {
                    detail_status += " ";
                }
                if(presentation.event().
                           passive_status_applied)
                {
                    detail_status += "ATK +";
                    detail_status += bn::to_string<4>(
                            presentation.event().
                                    passive_status_value);
                }
                else
                {
                    detail_status += "STATUS FULL";
                }
            }
            if(presentation.event().
                       passive_secondary_status_code != 0)
            {
                if(! detail_status.empty())
                {
                    detail_status += " ";
                }
                if(presentation.event().
                           passive_secondary_status_applied)
                {
                    detail_status += "AGI +";
                    detail_status += bn::to_string<4>(
                            presentation.event().
                                    passive_secondary_status_value);
                }
                else
                {
                    detail_status += "STATUS FULL";
                }
            }
        }
        else if(presentation.event().has_resource)
        {
            if(presentation.event().resource_type ==
                    battle_resource_command_type::
                            replenish_chakra)
            {
                detail = "CHAKRA +";
                detail += bn::to_string<4>(
                        presentation.event().
                                resource_chakra_delta);
                detail_status = "HP ";
                detail_status += bn::to_string<4>(
                        presentation.event().
                                resource_hp_delta);
            }
            else
            {
                detail = "REST HP +";
                detail += bn::to_string<4>(
                        presentation.event().
                                resource_hp_delta);
            }
        }
        else
        {
            if(combat.title_visible() ||
                    combat.movie_visible())
            {
                append_action_identity(
                        presentation.event().direct_attack ?
                                battle_action_source_kind::
                                        direct_attack :
                        presentation.event().ninja_tool ?
                                battle_action_source_kind::
                                        ninja_tool :
                                battle_action_source_kind::
                                        active_action,
                        presentation.event().action_id,
                        detail);
                detail_status =
                        combat.title_visible() ?
                                "TECHNIQUE" :
                                "ACTION";
            }
            else
            {
                detail = "ACTION RESOLVING";
            }
        }
    }
    else if(const battle_action_menu_view*
                    selected_combination_action =
                    selected_action(state);
            state.phase ==
                            battle_scene_phase::
                                    combination_decision &&
                    selected_combination_action)
    {
        detail = state.player
                         .combination_decision_selected ?
                "COMBO YES" :
                "COMBO NO";
        detail += " ";
        append_action_identity(
                *selected_combination_action, detail);
        detail_status = "UP/DOWN A:OK B:BACK";
    }
    else if(const battle_action_menu_view*
                    selected_menu_action =
                    selected_action(state);
            (state.phase ==
                        battle_scene_phase::action_selection ||
                state.phase ==
                        battle_scene_phase::target_selection ||
                state.phase ==
                        battle_scene_phase::target_preview ||
                state.phase ==
                        battle_scene_phase::
                                target_confirmation) &&
                    selected_menu_action)
    {
        if((state.phase ==
                         battle_scene_phase::
                                 target_selection ||
            state.phase ==
                    battle_scene_phase::
                            target_preview ||
            state.phase ==
                    battle_scene_phase::
                            target_confirmation) &&
                state.player.combination_result_action_id !=
                        no_ability)
        {
            append_action_identity(
                    battle_action_source_kind::
                            active_action,
                    state.player
                            .combination_result_action_id,
                    detail);
        }
        else
        {
            append_action_identity(
                    *selected_menu_action, detail);
        }
        detail += " ";
        detail += bn::to_string<4>(
                state.player.action_index + 1);
        detail += "/";
        detail += bn::to_string<4>(
                state.player.action_count);
        if(selected_menu_action->kind ==
                battle_action_source_kind::active_action)
        {
            detail += " LV";
            detail += bn::to_string<4>(
                    selected_menu_action->action_level);
        }

        if(state.phase ==
                        battle_scene_phase::
                                action_selection &&
                state.player.combination_component_count == 1)
        {
            detail_status = "COMBO 1/2 CK-";
            detail_status += bn::to_string<4>(
                    state.player
                            .combination_reserved_chakra);
            detail_status += " ";
            detail_status += "A:ADD B:CANCEL";
        }
        else
        {
            append_action_cost(
                    *selected_menu_action,
                    detail_status);
        }
        detail_status += " TG";
        detail_status += bn::to_string<4>(
                static_cast<int>(
                        selected_menu_action->target_kind));
        if(state.phase ==
                        battle_scene_phase::target_selection ||
                state.phase ==
                        battle_scene_phase::target_preview ||
                state.phase ==
                        battle_scene_phase::
                                target_confirmation)
        {
            detail_status += " @";
            detail_status += bn::to_string<4>(
                    state.cursor.x);
            detail_status += ",";
            detail_status += bn::to_string<4>(
                    state.cursor.y);
        }
        else if(! selected_menu_action->selectable())
        {
            detail_status += " E";
            detail_status += bn::to_string<4>(
                    static_cast<int>(
                            selected_menu_action->
                                    selection_error));
        }
    }
    else if(state.phase ==
                    battle_scene_phase::script_blocked)
    {
        detail = "SPEAKER ";
        detail += bn::to_string<4>(
                state.script.speaker);
        detail_status =
                state.script.phase ==
                                battle_presentation_script_phase::
                                        wait_for_input ?
                        "A:NEXT" : "WAIT";
    }
    else if(state.phase ==
                    battle_scene_phase::defense_selection &&
            state.player.selected_defense_action_id !=
                    no_ability)
    {
        const battle_action_source_kind kind =
                state.player.selected_defense_kind ==
                                defense_action_kind::
                                        ninja_tool ?
                        battle_action_source_kind::
                                ninja_tool :
                        battle_action_source_kind::
                                active_action;
        append_action_identity(
                kind,
                state.player.selected_defense_action_id,
                detail);
        detail += " ";
        detail += bn::to_string<4>(
                state.player.defense_action_index + 1);
        detail += "/";
        detail += bn::to_string<4>(
                state.player.defense_action_count);

        detail_status = "DEFENSE E";
        detail_status += bn::to_string<4>(
                static_cast<int>(
                        state.player
                                .defense_confirmation_error));
    }
    else if(state.phase == battle_scene_phase::enemy_turn)
    {
        int completed = 0;
        int total = 0;
        for(std::size_t index = 0;
                index < state.unit_count; ++index)
        {
            const battle_scene_unit_view& unit =
                    state.units[index];
            if(unit.active &&
                    unit.side == battle_side::enemy)
            {
                ++total;
                if(unit.completed)
                {
                    ++completed;
                }
            }
        }
        detail = "AI DONE ";
        detail += bn::to_string<4>(completed);
        detail += "/";
        detail += bn::to_string<4>(total);
    }
    else if(state.phase == battle_scene_phase::outcome)
    {
        detail = "OUTCOME ";
        detail += bn::to_string<4>(
                static_cast<int>(state.outcome));
    }
    else if(state.phase == battle_scene_phase::result &&
            result.participant_count > 0)
    {
        const battle_result_participant& participant =
                result.participants[0];
        detail = "M";
        detail += bn::to_string<8>(
                participant.mission_experience);
        detail += " B";
        detail += bn::to_string<8>(
                participant.battle_experience);
        detail += " X";
        detail += bn::to_string<8>(
                participant.round_bonus_experience);
        detail_status = "TOTAL ";
        detail_status += bn::to_string<8>(
                participant.total_experience);
        detail_status += " A:NEXT";
    }
    else if(state.phase == battle_scene_phase::level_up &&
            result.participant_count > 0)
    {
        const battle_result_participant& participant =
                result.participants[0];
        if(const battle_identity_record* identity =
                        battle_unit_identity(
                                participant.character_id))
        {
            detail = identity->display_name;
        }
        else
        {
            detail = "CHAR #";
            detail += bn::to_string<4>(
                    participant.character_id);
        }
        detail += " L";
        detail += bn::to_string<4>(
                participant.before.level);
        detail += ">";
        detail += bn::to_string<4>(
                participant.after.level);
        detail_status = "HP +";
        detail_status += bn::to_string<8>(
                participant.stat_growth.max_hp);
        detail_status += " AT +";
        detail_status += bn::to_string<4>(
                participant.stat_growth.attack);
        detail_status += " DF +";
        detail_status += bn::to_string<4>(
                participant.stat_growth.defense);
    }
    else if(state.phase == battle_scene_phase::training)
    {
        if(const battle_identity_record* identity =
                        battle_unit_identity(
                                training.character_id))
        {
            detail = identity->display_name;
        }
        else
        {
            detail = "CHAR #";
            detail += bn::to_string<4>(
                    training.character_id);
        }
        detail += " TP";
        detail += bn::to_string<4>(
                training.training_points);
        detail += " ";
        detail += bn::to_string<4>(
                static_cast<int>(
                        training.entry_index + 1));
        detail += "/";
        detail += bn::to_string<4>(
                static_cast<int>(
                        training.entry_count));

        if(training.entry_count == 0)
        {
            detail_status = "NO ACTIONS B:DONE";
        }
        else
        {
            if(training.selected_kind ==
                    battle_training_entry_kind::
                            secondary_passive)
            {
                detail_status += "PASSIVE #";
                detail_status += bn::to_string<4>(
                        training.selected_definition_id);
            }
            else
            {
                append_action_identity(
                        battle_action_source_kind::
                                active_action,
                        training.selected_action_id,
                        detail_status);
            }
            if(training.selected_level ==
                    locked_action_level)
            {
                detail_status += " LOCK";
            }
            else if(training.selected_level ==
                    unlocked_action_level)
            {
                detail_status += " NEW";
            }
            else if(training.selected_level >=
                    maximum_action_level)
            {
                detail_status += " MAX";
            }
            else
            {
                detail_status += " LV";
                detail_status += bn::to_string<4>(
                        training.selected_level);
            }
            if(training.last_error !=
                    action_training_error::none)
            {
                detail_status += " E";
                detail_status += bn::to_string<4>(
                        static_cast<int>(
                                training.last_error));
            }
            else if(training.selected_error ==
                    action_training_error::not_trainable)
            {
                detail_status += " FIXED";
            }
            detail_status += " A:TRAIN B:DONE L/R:CHAR";
        }
    }
    else if(state.phase == battle_scene_phase::complete)
    {
        detail = "A:EXIT";
    }
    else if(const battle_scene_unit_view* unit =
                    selected_unit(state))
    {
        append_unit_identity(*unit, detail);
        detail += " L";
        detail += bn::to_string<4>(unit->level);
        detail += " AT";
        detail += bn::to_string<4>(unit->attack);
        detail += " DF";
        detail += bn::to_string<4>(unit->defense);

        detail_status = "HP";
        detail_status += bn::to_string<8>(unit->hp);
        detail_status += "/";
        detail_status += bn::to_string<8>(
                unit->max_hp);
        detail_status += " CK";
        detail_status += bn::to_string<4>(
                unit->chakra);
        detail_status += "/";
        detail_status += bn::to_string<4>(
                unit->max_chakra);
        detail_status += " AG";
        detail_status += bn::to_string<4>(
                unit->agility);
        detail_status += " MV";
        detail_status += bn::to_string<4>(
                unit->movement);
        detail_status += " ST";
        detail_status += bn::to_string<4>(
                unit->status_count);
    }
    else
    {
        detail = "A:OK B:X";
    }
    if(rejected)
    {
        detail = "INVALID INPUT";
        detail_status.clear();
    }
    generator.generate(-116, 48, detail, sprites);
    if(! detail_status.empty())
    {
        generator.generate(
                -116, 64, detail_status, sprites);
    }
}

[[nodiscard]] const char* command_label(
        battle_command_type command)
{
    switch(command)
    {
    case battle_command_type::move:
        return "移动";
    case battle_command_type::ability:
        return "术・忍具";
    case battle_command_type::direct_attack:
        return "直接攻击";
    case battle_command_type::replenish_chakra:
        return "查克拉";
    case battle_command_type::rest:
        return "休息";
    case battle_command_type::end_action:
    default:
        return "行动结束";
    }
}

void render_status_panel_text(
        const battle_scene_snapshot<12>& state,
        const battle_ui_model& model,
        bn::sprite_text_generator& generator,
        bn::sprite_text_generator& target_status_generator,
        bn::sprite_text_generator& target_metrics_generator,
        bn::vector<
                bn::sprite_ptr,
                battle_runtime_scene_sprite_budget::
                        maximum_text_sprites>& sprites)
{
    const battle_scene_unit_view* unit =
            combatant_view(
                    state, model.status_unit_id);
    if(! model.show_status_panel || ! unit)
    {
        return;
    }

    bn::string<96> identity;
    append_unit_identity(*unit, identity);
    const bool expanded_target_status =
            state.phase ==
                            battle_scene_phase::
                                    target_preview ||
            state.phase ==
                            battle_scene_phase::
                                    target_confirmation;
    if(expanded_target_status)
    {
        target_status_generator.set_left_alignment();
        target_status_generator.set_palette_item(
                bn::sprite_palette_items::
                        battle_ui_text_warning_palette);
        target_status_generator.generate(
                -112, 48, identity, sprites);
        target_status_generator.generate(
                -16, 48, "待机", sprites);
        target_status_generator.set_palette_item(
                bn::sprite_items::battle_ui_panel
                                .palette_item());
        target_status_generator.generate(
                16, 48, "体力", sprites);
        target_status_generator.generate(
                16, 56, "查克拉", sprites);
        target_status_generator.set_right_alignment();
        target_status_generator.generate(
                112,
                48,
                bn::to_string<8>(unit->hp),
                sprites);
        target_status_generator.generate(
                112,
                56,
                bn::to_string<4>(unit->chakra),
                sprites);

        target_metrics_generator.set_left_alignment();
        target_metrics_generator.set_palette_item(
                bn::sprite_items::battle_ui_panel
                                .palette_item());
        target_metrics_generator.generate(
                -112, 64, "伤害", sprites);
        target_metrics_generator.generate(
                -40, 64, "成功率", sprites);
        target_metrics_generator.generate(
                24, 64, "攻", sprites);
        target_metrics_generator.generate(
                56, 64, "防", sprites);
        target_metrics_generator.generate(
                88, 64, "快", sprites);

        target_metrics_generator.set_right_alignment();
        target_metrics_generator.generate(
                -48,
                64,
                bn::to_string<8>(
                        state.player.target_preview
                                .damage_per_hit),
                sprites);
        bn::string<16> success =
                bn::to_string<4>(
                        state.player.target_preview
                                .success_rate_percent);
        success += "%";
        target_metrics_generator.generate(
                16, 64, success, sprites);
        target_metrics_generator.generate(
                48,
                64,
                bn::to_string<8>(unit->attack),
                sprites);
        target_metrics_generator.generate(
                80,
                64,
                bn::to_string<8>(unit->defense),
                sprites);
        target_metrics_generator.generate(
                112,
                64,
                bn::to_string<8>(unit->agility),
                sprites);
        target_metrics_generator.set_left_alignment();
        return;
    }

    generator.set_left_alignment();
    generator.set_palette_item(
            bn::sprite_palette_items::
                    battle_ui_text_accent_palette);
    generator.generate(-112, 64, identity, sprites);
    // The original shows 結束 only for a unit that already finished its
    // action and 待機 for a unit that is still waiting.  Deciding this by
    // phase instead put the red 結束 on the unit selection screen, where the
    // original shows the blue 待機 (S49 original frame 17).
    if(unit->completed)
    {
        if(! sprites.full())
        {
            bn::sprite_ptr status_end =
                    bn::sprite_items::
                            battle_ui_status_end
                                    .create_sprite(
                                            -8, 64);
            status_end.set_bg_priority(0);
            status_end.set_z_order(0);
            sprites.push_back(
                    static_cast<bn::sprite_ptr&&>(
                            status_end));
        }
    }
    else
    {
        generator.generate(-16, 64, "待机", sprites);
    }
    generator.set_palette_item(
            bn::sprite_items::battle_ui_panel
                    .palette_item());
    generator.generate(-48, 64, "本体", sprites);
    generator.generate(16, 64, "能力", sprites);
    generator.generate(16, 72, "查克拉", sprites);

    bn::string<16> hp = bn::to_string<8>(unit->hp);
    constexpr int status_value_x = 112;
    generator.set_right_alignment();
    generator.generate(
            status_value_x,
            64,
            hp,
            sprites);
    bn::string<16> chakra =
            bn::to_string<4>(unit->chakra);
    generator.generate(
            status_value_x,
            72,
            chakra,
            sprites);
    generator.set_left_alignment();
}

void render_round_badge_text(
        const battle_scene_snapshot<12>& state,
        const battle_ui_model& model,
        bn::sprite_text_generator& generator,
        bn::vector<
                bn::sprite_ptr,
                battle_runtime_scene_sprite_budget::
                        maximum_text_sprites>& sprites)
{
    if(! model.show_round_badge)
    {
        return;
    }
    bn::string<32> round = "ROUND ";
    round += bn::to_string<4>(state.round);
    generator.set_right_alignment();
    generator.generate(116, -70, round, sprites);
    generator.generate(
            116,
            -55,
            state.current_side == battle_side::player ?
                    "PLAYER" : "ENEMY",
            sprites);
}

void render_command_menu_text(
        const battle_scene_snapshot<12>& state,
        bn::sprite_text_generator& generator,
        bn::sprite_text_generator& action_generator,
        bn::vector<
                bn::sprite_ptr,
                battle_runtime_scene_sprite_budget::
                        maximum_text_sprites>& sprites)
{
    generator.set_left_alignment();
    const int count = state.player.command_count <
                    static_cast<int>(
                            state.player
                                    .command_entries.size()) ?
            state.player.command_count :
            static_cast<int>(
            state.player.command_entries.size());
    const int menu_y = -8 - count * 8;
    for(int index = 0; index < count; ++index)
    {
        const battle_command_menu_view& entry =
                state.player.command_entries[
                        static_cast<std::size_t>(index)];
        if(index == state.player.command_index)
        {
            if(! sprites.full())
            {
                // S49 original frame 18/20: the command-menu row marker is the
                // short four-row arrow (art rows 6..9), which is the tile this
                // project ships as `battle_ui_action_cursor`.
                bn::sprite_ptr cursor =
                        bn::sprite_items::battle_ui_action_cursor
                                .create_sprite(
                                        -108,
                                        menu_y + index * 16);
                cursor.set_bg_priority(0);
                cursor.set_z_order(0);
                sprites.push_back(bn::move(cursor));
            }
        }
        const char* label = command_label(entry.type);
        // S49 original frame 18 draws 查克拉 in the command menu at full
        // 16-row height, while the status HUD draws the same three characters
        // as 8-row compact glyphs.  The original therefore carries two sizes
        // for 查/克/拉, and the shared UI atlas cell can only be one of them:
        // the compact one, which the status HUD already matches pixel for
        // pixel.  The action-menu atlas already holds the full-height tiles,
        // byte for byte identical to the command menu's, so this one label is
        // drawn with that font instead of adding a third atlas.
        bn::sprite_text_generator& label_generator =
                entry.type == battle_command_type::replenish_chakra ?
                action_generator :
                generator;
        label_generator.set_left_alignment();
        label_generator.set_palette_item(
                bn::sprite_items::battle_ui_panel
                        .palette_item());
        label_generator.set_z_order(0);
        label_generator.generate(
                -104,
                menu_y + index * 16,
                label,
                sprites);
    }
}

[[nodiscard]] const char* battle_character_short_label(
        std::uint8_t character_id);

void render_action_menu_text(
        const battle_scene_snapshot<12>& state,
        bn::sprite_text_generator& generator,
        bn::sprite_text_generator& action_generator,
        bn::vector<
                bn::sprite_ptr,
                battle_runtime_scene_sprite_budget::
                        maximum_text_sprites>& sprites)
{
    const battle_action_menu_view* action =
            selected_action(state);
    if(! action)
    {
        return;
    }

    const battle_scene_unit_view* actor =
            selected_unit(state);
    generator.set_left_alignment();
    action_generator.set_left_alignment();
    action_generator.set_palette_item(
            bn::sprite_items::battle_ui_panel
                    .palette_item());
    if(actor)
    {
        generator.set_palette_item(
                bn::sprite_items::battle_ui_panel
                        .palette_item());
        if(const battle_identity_record* identity =
                        battle_unit_identity(actor->character_id))
        {
            action_generator.generate(
                    -104,
                    -64,
                    identity->display_name,
                    sprites);
        }
        generator.set_palette_item(
                bn::sprite_items::battle_ui_panel
                        .palette_item());
        if(! sprites.full())
        {
            bn::sprite_ptr actor_stats =
                    bn::sprite_items::battle_ui_action_actor_stats
                            .create_sprite(-24, -64);
            actor_stats.set_bg_priority(0);
            actor_stats.set_z_order(0);
            sprites.push_back(bn::move(actor_stats));
        }
        generator.set_right_alignment();
        generator.generate(
                24,
                -64,
                bn::to_string<8>(actor->hp),
                sprites);
        generator.generate(
                24,
                -56,
                bn::to_string<4>(actor->chakra),
                sprites);
        generator.set_left_alignment();
    }

    const int page_start =
            battle_action_ui_page_start(
                    state.player.action_index,
                    state.player.action_count);
    constexpr int page_size = 4;
    for(int row = 0; row < page_size; ++row)
    {
        const int action_index = page_start + row;
        if(action_index >= state.player.action_count ||
                action_index >=
                        static_cast<int>(
                                state.player
                                        .action_entries
                                        .size()))
        {
            break;
        }
        const battle_action_menu_view& entry =
                state.player.action_entries[
                        static_cast<std::size_t>(
                                action_index)];
        const int row_y = -32 + row * 16;
        if(action_index == state.player.action_index)
        {
            if(! sprites.full())
            {
                // S49 original frame 21: the action-menu row marker is the tall
                // eight-row arrow (art rows 4..11), which is the tile this
                // project ships as `battle_ui_confirmation_cursor`.
                bn::sprite_ptr cursor =
                        bn::sprite_items::battle_ui_confirmation_cursor
                                .create_sprite(-116, row_y);
                cursor.set_bg_priority(0);
                cursor.set_z_order(0);
                sprites.push_back(bn::move(cursor));
            }
        }
        bn::string<96> entry_name;
        append_action_identity(entry, entry_name);
        action_generator.generate(
                -112, row_y, entry_name, sprites);
    }

    bn::string<96> action_name;
    append_action_identity(*action, action_name);

    const action_definition* definition = nullptr;
    if(action->kind ==
                    battle_action_source_kind::active_action &&
            action->action_id <
                    active_action_definitions.size())
    {
        definition =
                &active_action_definitions[action->action_id];
    }
    else if(action->kind ==
                    battle_action_source_kind::ninja_tool &&
            action->action_id <
                    ninja_tool_action_definitions.size())
    {
        definition =
                &ninja_tool_action_definitions[
                        action->action_id];
    }

    const char* cost_label = "消耗查克拉";
    if(action->cost_kind ==
            action_cost_kind::current_hp)
    {
        cost_label = "消耗体力";
    }
    else if(action->cost_kind ==
            action_cost_kind::battle_local_ninja_tool_slot)
    {
        cost_label = "忍具数量";
    }
    action_generator.generate(40, -64, cost_label, sprites);
    if(definition && definition->effect.potency > 0)
    {
        action_generator.generate(40, -48, "攻击力", sprites);
    }
    action_generator.generate(40, -32, "距离", sprites);
    action_generator.generate(40, -16, "范围", sprites);
    action_generator.generate(40, 16, "成功率", sprites);
    action_generator.set_right_alignment();
    action_generator.generate(
            112,
            -64,
            bn::to_string<4>(action->cost_scalar),
            sprites);
    action_generator.set_left_alignment();
    if(definition)
    {
        if(definition->effect.potency > 0)
        {
            bn::string<16> attack =
                    bn::to_string<4>(
                            definition->effect.potency);
            attack += "X";
            attack += bn::to_string<4>(
                    definition->effect.base_hit_count);
            action_generator.generate(
                    72, -48, attack, sprites);
        }
        action_generator.generate(
                72,
                -32,
                bn::to_string<4>(
                        definition->range
                                .maximum_distance()),
                sprites);
        action_generator.generate(
                72,
                -16,
                bn::to_string<4>(
                        definition->range
                                .area_range_and_shape_flags &
                        0x7F),
                sprites);
        bn::string<16> success =
                bn::to_string<4>(
                        definition->effect
                                .success_rate_percent);
        success += "%";
        action_generator.generate(
                72, 16, success, sprites);
    }

    action_generator.generate(
            -112, 48, action_name, sprites);
    if(action->effect_code == 3 ||
            action->effect_code == 12)
    {
        action_generator.generate(
                -112,
                64,
                "用查克拉的力量进行瞬间移动",
                sprites);
    }
    else if(action->effect_code == 7)
    {
        action_generator.generate(
                -112,
                64,
                "用查克拉的力量进行分身",
                sprites);
    }
    else
    {
        action_generator.generate(
                -112,
                64,
                "攻击对象受到的伤害",
                sprites);
    }
    action_generator.set_palette_item(
            bn::sprite_palette_items::
                    battle_ui_text_warning_palette);
    if(! sprites.full())
    {
        bn::sprite_ptr start_hint =
                bn::sprite_items::battle_ui_action_start_hint
                        .create_sprite(48, 48);
        start_hint.set_bg_priority(0);
        start_hint.set_z_order(0);
        sprites.push_back(bn::move(start_hint));
    }
    action_generator.generate(
            56, 48, "攻击指令", sprites);
    if(! sprites.full())
    {
        bn::sprite_ptr back_hint =
                bn::sprite_items::battle_ui_action_back_hint
                        .create_sprite(88, 64);
        back_hint.set_bg_priority(0);
        back_hint.set_z_order(0);
        sprites.push_back(bn::move(back_hint));
    }
    action_generator.generate(
            96, 64, "返回", sprites);
}

void render_unit_cycle_hint(
        bn::sprite_text_generator& generator,
        bn::vector<
                bn::sprite_ptr,
                battle_runtime_scene_sprite_budget::
                        maximum_text_sprites>& sprites)
{
    // The original's hint is a small "SELECT詳細" in the top right corner.
    // It is not drawn with the UI font: the original uses a narrow ASCII and
    // 8x8 CJK cells, and the font atlases have neither, so the prompt is cut
    // out of the original's own frame and is pixel exact that way.
    // The region is 48 pixels wide, which no sprite can be, so the asset
    // holds it as two 32x32 graphics side by side.
    constexpr int prompt_piece_x[] = { 88, 120, };
    constexpr int prompt_piece_y[] = { -52, -52, };
    for(int piece = 0; piece < 2; ++piece)
    {
        if(sprites.full())
        {
            break;
        }
        bn::sprite_ptr prompt =
                bn::sprite_items::battle_ui_select_prompt
                        .create_sprite(
                                prompt_piece_x[piece],
                                prompt_piece_y[piece],
                                piece);
        prompt.set_bg_priority(0);
        prompt.set_z_order(0);
        sprites.push_back(
                static_cast<bn::sprite_ptr&&>(prompt));
    }
    generator.set_palette_item(
            bn::sprite_items::battle_ui_panel
                    .palette_item());
}

[[nodiscard]] const char* battle_character_short_label(
        std::uint8_t character_id)
{
    switch(character_id)
    {
    case 1:
        return "鸣人";
    case 2:
        return "佐助";
    case 3:
        return "小樱";
    default:
        if(const battle_identity_record* identity =
                        battle_unit_identity(character_id))
        {
            return identity->display_name;
        }
        return "";
    }
}

void render_battle_ui_text(
        const battle_ui_model& model,
        const battle_scene_snapshot<12>& state,
        const battle_training_snapshot& training,
        const battle_result& result,
        const battle_runtime_scene_config& config,
        bool rejected,
        const battle_scene_presentation& presentation,
        bn::sprite_text_generator& generator,
        bn::sprite_text_generator& action_menu_generator,
        bn::sprite_text_generator& duel_status_generator,
        bn::sprite_text_generator& target_status_generator,
        bn::sprite_text_generator& target_metrics_generator,
        bn::sprite_text_generator& result_text_generator,
        bn::sprite_text_generator& result_compact_text_generator,
        bn::vector<
                bn::sprite_ptr,
                battle_runtime_scene_sprite_budget::
                        maximum_text_sprites>& sprites)
{
    const battle_combat_presentation& combat =
            presentation.combat();
    generator.set_palette_item(
            bn::sprite_items::battle_ui_font
                    .palette_item());
    if(state.phase == battle_scene_phase::script_blocked ||
            (presentation.busy() &&
             combat.busy() &&
             ! combat.map_visible()))
    {
        render_text(
                state,
                training,
                result,
                config,
                rejected,
                presentation,
                generator,
                action_menu_generator,
                duel_status_generator,
                sprites);
        return;
    }

    sprites.clear();
    generator.set_left_alignment();
    generator.set_z_order(0);
    if(model.layer == battle_ui_layer::hidden)
    {
        return;
    }
    generator.set_palette_item(bn::sprite_items::battle_ui_panel.palette_item());

    if(model.layer != battle_ui_layer::action_menu)
    {
        render_status_panel_text(
                state,
                model,
                generator,
                target_status_generator,
                target_metrics_generator,
                sprites);
        render_round_badge_text(
                state,
                model,
                generator,
                sprites);
    }

    if(model.show_select_prompt)
    {
        render_unit_cycle_hint(generator, sprites);
    }
    else if(model.show_instruction_panel)
    {
        generator.set_left_alignment();
        generator.generate(
                -112,
                64,
                "请选择人物面对的方向",
                sprites);
    }

    if(presentation.busy())
    {
        bn::string<96> action;
        if(presentation.event().has_action)
        {
            append_action_identity(
                    presentation.event().direct_attack ?
                            battle_action_source_kind::
                                    direct_attack :
                    presentation.event().ninja_tool ?
                            battle_action_source_kind::
                                    ninja_tool :
                            battle_action_source_kind::
                                    active_action,
                    presentation.event().action_id,
                    action);
        }
        else if(presentation.event().has_resource)
        {
            action = "RESOURCE";
        }
        else if(presentation.event().
                        has_side_start_passive)
        {
            action = "PASSIVE";
        }
        if(! action.empty())
        {
            generator.set_center_alignment();
            generator.generate(0, -70, action, sprites);
        }
        return;
    }

    switch(model.layer)
    {
    case battle_ui_layer::command_menu:
        render_command_menu_text(
                state,
                generator,
                action_menu_generator,
                sprites);
        break;
    case battle_ui_layer::action_menu:
        render_action_menu_text(
                state,
                generator,
                action_menu_generator,
                sprites);
        break;
    case battle_ui_layer::target_select:
    {
        render_unit_cycle_hint(generator, sprites);
        break;
    }
    case battle_ui_layer::confirmation:
        if(state.phase ==
                        battle_scene_phase::
                                target_confirmation ||
                state.phase ==
                        battle_scene_phase::
                                end_confirmation)
        {
            generator.set_left_alignment();
            generator.generate(
                    -32, -40, "可以吗？", sprites);
            generator.generate(
                    -8, -24, "是", sprites);
            generator.generate(
                    -8, -8, "否", sprites);
        }
        else if(state.phase ==
                battle_scene_phase::defense_decision)
        {
            generator.set_left_alignment();
            generator.generate(
                    -48,
                    -40,
                    "使用防御・回避系的",
                    sprites);
            generator.generate(
                    -48,
                    -24,
                    "术・忍具吗？",
                    sprites);
            generator.generate(-8, -8, "是", sprites);
            generator.generate(-8, 8, "否", sprites);
            generator.generate(
                    -16,
                    state.defense_confirmation_yes ?
                            -8 :
                            8,
                    "→",
                    sprites);
        }
        else if(state.phase ==
                battle_scene_phase::chakra_selection)
        {
            generator.set_center_alignment();
            bn::string<64> prompt = "CHAKRA +";
            prompt += bn::to_string<4>(
                    state.player
                            .resource_preview.amount);
            prompt += "/";
            prompt += bn::to_string<4>(
                    state.player
                            .resource_preview
                            .maximum_amount);
            generator.generate(0, -7, prompt, sprites);
            generator.generate(
                    0, 9, "UP/DOWN  A OK  B BACK", sprites);
        }
        else if(state.phase ==
                battle_scene_phase::rest_confirmation)
        {
            bn::string<64> prompt = "REST HP +";
            prompt += bn::to_string<4>(
                    state.player
                            .resource_preview.hp_delta);
            generator.generate(0, -7, prompt, sprites);
            generator.generate(
                    0, 9, "A OK  B BACK", sprites);
        }
        else
        {
            generator.generate(
                    0,
                    -7,
                    state.player
                                    .combination_decision_selected ?
                            "COMBINE: YES" :
                            "COMBINE: NO",
                    sprites);
            generator.generate(
                    0, 9, "UP/DOWN A OK B BACK", sprites);
        }
        break;
    case battle_ui_layer::defense_menu:
    {
        generator.set_left_alignment();
        generator.generate(-116, -54, ">DEFENSE", sprites);
        bn::string<48> index = "OPTION ";
        index += bn::to_string<4>(
                state.player.defense_action_index + 1);
        index += "/";
        index += bn::to_string<4>(
                state.player.defense_action_count);
        generator.generate(-116, -37, index, sprites);
        bn::string<96> identity;
        append_action_identity(
                state.player.selected_defense_kind ==
                                defense_action_kind::
                                        ninja_tool ?
                        battle_action_source_kind::
                                ninja_tool :
                        battle_action_source_kind::
                                active_action,
                state.player.selected_defense_action_id,
                identity);
        generator.generate(-116, -20, identity, sprites);
        generator.generate(
                -116,
                -3,
                state.player.defense_confirmation_error ==
                                defense_preparation_error::
                                        none ?
                        "A OK  B BACK" : "LOCKED",
                sprites);
        break;
    }
    case battle_ui_layer::result:
        if(state.phase == battle_scene_phase::outcome)
        {
            generator.set_center_alignment();
            generator.generate(
                    0, -38, "BATTLE COMPLETE", sprites);
            generator.generate(
                    0, -6, "MISSION CLEARED", sprites);
        }
        else if(result.participant_count > 0)
        {
            result_text_generator.set_palette_item(
                    bn::sprite_items::
                            battle_ui_panel.palette_item());
            result_text_generator.set_left_alignment();
            result_text_generator.set_z_order(0);
            constexpr int participant_name_x[] = {
                -24, 32, 88,
            };
            for(std::size_t index = 0;
                    index < result.participant_count &&
                    index < 3;
                    ++index)
            {
                result_text_generator.generate(
                        participant_name_x[index],
                        -64,
                        battle_character_short_label(
                                result.participants[index]
                                        .character_id),
                        sprites);
            }

            constexpr int participant_value_x[] = {
                0, 56, 112,
            };
            result_compact_text_generator.set_palette_item(
                    bn::sprite_items::
                            battle_ui_panel.palette_item());
            result_compact_text_generator.set_right_alignment();
            result_compact_text_generator.set_z_order(0);
            for(std::size_t index = 0;
                    index < result.participant_count &&
                    index < 3;
                    ++index)
            {
                const battle_result_participant& participant =
                        result.participants[index];
                result_compact_text_generator.generate(
                        participant_value_x[index],
                        40,
                        bn::to_string<8>(
                                participant
                                        .mission_experience),
                        sprites);
                result_compact_text_generator.generate(
                        participant_value_x[index],
                        48,
                        bn::to_string<8>(
                                participant
                                        .battle_experience),
                        sprites);
                result_compact_text_generator.generate(
                        participant_value_x[index],
                        56,
                        bn::to_string<8>(
                                participant
                                        .round_bonus_experience),
                        sprites);
            }

            result_text_generator.set_palette_item(
                    bn::sprite_palette_items::
                            battle_ui_result_total_palette);
            result_text_generator.set_right_alignment();
            for(std::size_t index = 0;
                    index < result.participant_count &&
                    index < 3;
                    ++index)
            {
                result_text_generator.generate(
                        participant_value_x[index],
                        64,
                        bn::to_string<8>(
                                result.participants[index]
                                        .total_experience),
                        sprites);
            }
            result_text_generator.set_palette_item(
                    bn::sprite_items::
                            battle_ui_panel.palette_item());
        }
        break;
    case battle_ui_layer::level_up:
        break;
    case battle_ui_layer::training:
    {
        if(state.training_summary_active)
        {
            break;
        }
        generator.set_center_alignment();
        generator.generate(0, -51, "TRAINING", sprites);
        bn::string<64> points = "POINTS ";
        points += bn::to_string<4>(
                training.training_points);
        generator.generate(0, -30, points, sprites);
        bn::string<96> entry;
        if(training.selected_kind ==
                battle_training_entry_kind::
                        primary_action)
        {
            append_action_identity(
                    battle_action_source_kind::
                            active_action,
                    training.selected_action_id,
                    entry);
        }
        else
        {
            entry = "PASSIVE ";
            entry += bn::to_string<4>(
                    training.selected_definition_id);
        }
        generator.generate(0, -5, entry, sprites);
        generator.generate(
                0, 35, "A TRAIN  B DONE  L/R UNIT", sprites);
        break;
    }
    case battle_ui_layer::map_status:
        generator.set_left_alignment();
        switch(state.phase)
        {
        case battle_scene_phase::unit_selection:
            break;
        case battle_scene_phase::facing_selection:
            break;
        case battle_scene_phase::enemy_turn:
            generator.generate(
                    -116, -70, "ENEMY TURN", sprites);
            break;
        default:
            break;
        }
        break;
    default:
        break;
    }

    if(rejected)
    {
        generator.set_center_alignment();
        generator.generate(0, 35, "CANNOT SELECT", sprites);
    }
}

void render_script_glyphs(
        const battle_scene_snapshot<12>& state,
        bn::sprite_text_generator& story_text_generator,
        bn::vector<bn::sprite_ptr, 64>& sprites)
{
    sprites.clear();
    if(state.phase != battle_scene_phase::script_blocked ||
            state.script.phase !=
                    battle_presentation_script_phase::
                            wait_for_input ||
            state.script.text_length == 0 ||
            static_cast<std::size_t>(
                    state.script.text_offset) +
                    state.script.text_length >
                    battle_presentation_text.size())
    {
        return;
    }
    battle_presentation_text_layout<56> layout;
    if(layout.build(
               battle_presentation_text.data() +
                       state.script.text_offset,
               state.script.text_length) !=
            battle_presentation_text_layout_result::ok)
    {
        return;
    }
    const char* dialogue_name =
            battle_unit_dialogue_name(
                    state.script.speaker);
    // The original draws a small spiral shell at the bottom-right of the
    // dialogue box while the line waits for input; this path only runs in
    // exactly that state, so the icon lives here.  create_sprite takes the
    // centre, and the icon's ink starts at its cell's top left corner, so the
    // measured screen box (217,139)-(231,148) maps to (105, 67).
    bn::sprite_ptr advance_icon =
            bn::sprite_items::battle_ui_dialogue_advance_icon
                    .create_sprite(105, 67);
    advance_icon.set_bg_priority(0);
    sprites.push_back(
            static_cast<bn::sprite_ptr&&>(
                    advance_icon));
    const int dialogue_label_graphics_index =
            battle_unit_dialogue_label_graphics_index(
                    state.script.speaker);
    if(dialogue_label_graphics_index >= 0)
    {
        bn::sprite_ptr label =
                bn::sprite_items::
                        battle_ui_dialogue_speaker_label
                                .create_sprite(
                                        -88,
                                        32,
                                        dialogue_label_graphics_index);
        label.set_bg_priority(0);
        sprites.push_back(
                static_cast<bn::sprite_ptr&&>(
                        label));
    }
    else if(dialogue_name[0] != '\0')
    {
        story_text_generator.set_left_alignment();
        story_text_generator.set_palette_item(
                bn::sprite_palette_items::
                        battle_ui_dialogue_speaker_palette);
        story_text_generator.generate(
                -96,
                32,
                dialogue_name,
                sprites);
        story_text_generator.set_palette_item(
                bn::sprite_items::battle_preparation_font
                        .palette_item());
    }
    for(std::size_t index = 0;
            index < layout.glyph_count(); ++index)
    {
        const battle_presentation_glyph& glyph =
                *layout.glyph(index);
        const int graphics_index =
                battle_presentation_glyph_index(
                        glyph.code);
        if(graphics_index < 0)
        {
            sprites.clear();
            return;
        }
        bn::sprite_ptr sprite =
                bn::sprite_items::
                        battle_presentation_glyphs
                                .create_sprite(
                                        -92 +
                                                glyph.column *
                                                        8,
                                        glyph.row *
                                                        16 +
                                                48,
                                        graphics_index);
        sprite.set_bg_priority(0);
        sprite.set_palette(
                bn::sprite_palette_items::
                        battle_ui_dialogue_text_palette);
        sprites.push_back(
                static_cast<bn::sprite_ptr&&>(
                        sprite));
    }
}

struct battle_unit_sprite_state
{
    std::array<
            bn::optional<bn::sprite_ptr>,
            battle_unit_visual_max_components>
            components;
    std::uint8_t character_id = 0;
    std::uint8_t visual_slot = 0xFF;
    std::uint8_t frame_index = 0xFF;
    std::array<
            std::uint8_t,
            battle_unit_visual_max_components>
            asset_indices = {
                0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
            };

    void reset()
    {
        for(auto& component : components)
        {
            component.reset();
        }
        character_id = 0;
        visual_slot = 0xFF;
        frame_index = 0xFF;
        asset_indices = {
            0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
        };
    }
};

constexpr std::size_t
        battle_presentation_visible_portrait_slots = 2;
constexpr std::size_t
        battle_presentation_portrait_component_count =
                battle_presentation_portrait_components.size();
constexpr int battle_presentation_portrait_bytes = 6400;
constexpr int battle_presentation_portrait_palette_colors =
        128;

struct battle_presentation_portrait_slot_renderer
{
    std::array<
            bn::optional<bn::sprite_tiles_ptr>,
            battle_presentation_portrait_component_count>
            tiles;
    std::array<
            bn::optional<bn::sprite_ptr>,
            battle_presentation_portrait_component_count>
            sprites;
    std::uint8_t portrait_id = 0;
    std::uint8_t expression_id = 0;
    bool loaded = false;

    void reset()
    {
        for(auto& sprite : sprites)
        {
            sprite.reset();
        }
        for(auto& tile : tiles)
        {
            tile.reset();
        }
        portrait_id = 0;
        expression_id = 0;
        loaded = false;
    }
};

class battle_presentation_portrait_runtime_renderer
{
public:
    void reset()
    {
        for(auto& slot : _slots)
        {
            slot.reset();
        }
        _palette.reset();
    }

    void update(
            const std::array<
                    battle_presentation_portrait_snapshot,
                    3>& portraits,
            std::array<
                    std::uint8_t,
                    battle_presentation_portrait_bytes>&
                    scratch)
    {
        _update_palette(portraits);
        for(std::size_t slot_index = 0;
                slot_index <
                        battle_presentation_visible_portrait_slots;
                ++slot_index)
        {
            const battle_presentation_portrait_snapshot&
                    portrait =
                            portraits[slot_index];
            if(! portrait.visible || ! _palette)
            {
                _slots[slot_index].reset();
                continue;
            }
            const battle_presentation_portrait_resource*
                    resource =
                            battle_presentation_portrait_resource_for(
                                    portrait.portrait_id,
                                    portrait.expression_id);
            if(! resource)
            {
                _slots[slot_index].reset();
                continue;
            }
            battle_presentation_portrait_slot_renderer&
                    slot = _slots[slot_index];
            if(! slot.loaded ||
                    slot.portrait_id !=
                            portrait.portrait_id ||
                    slot.expression_id !=
                            portrait.expression_id)
            {
                _load_slot(
                        static_cast<std::uint8_t>(
                                slot_index),
                        *resource,
                        scratch,
                        slot);
            }
            _position_slot(
                    static_cast<std::uint8_t>(
                            slot_index),
                    portrait.motion_mode,
                    slot);
        }
    }

private:
    void _update_palette(
            const std::array<
                    battle_presentation_portrait_snapshot,
                    3>& portraits)
    {
        bool any_visible = false;
        bool any_focused = false;
        for(std::size_t slot_index = 0;
                slot_index <
                        battle_presentation_visible_portrait_slots;
                ++slot_index)
        {
            const battle_presentation_portrait_snapshot&
                    portrait =
                            portraits[slot_index];
            any_visible = any_visible ||
                    portrait.visible;
            any_focused = any_focused ||
                    (portrait.visible &&
                            portrait.focused);
        }
        if(! any_visible)
        {
            _palette.reset();
            return;
        }

        for(std::size_t slot_index = 0;
                slot_index <
                        battle_presentation_visible_portrait_slots;
                ++slot_index)
        {
            const battle_presentation_portrait_snapshot&
                    portrait =
                            portraits[slot_index];
            const battle_presentation_portrait_resource*
                    resource =
                            portrait.visible ?
                            battle_presentation_portrait_resource_for(
                                    portrait.portrait_id,
                                    portrait.expression_id) :
                            nullptr;
            for(int color_index = 0;
                    color_index < 64;
                    ++color_index)
            {
                std::uint16_t color = 0;
                if(resource)
                {
                    color =
                            battle_presentation_portrait_palettes[
                                    resource->palette_offset +
                                    color_index] &
                            0x7FFF;
                    if(any_focused &&
                            ! portrait.focused)
                    {
                        color =
                                dim_battle_presentation_portrait_color(
                                        color);
                    }
                }
                _palette_colors[
                        slot_index * 64 +
                        static_cast<std::size_t>(
                                color_index)] =
                        bn::color(color);
            }
        }

        const bn::span<const bn::color> colors(
                _palette_colors.data(),
                battle_presentation_portrait_palette_colors);
        if(_palette)
        {
            _palette->set_colors(colors);
        }
        else
        {
            _palette =
                    bn::sprite_palette_ptr::create(
                            bn::sprite_palette_item(
                                    colors,
                                    bn::bpp_mode::
                                            BPP_8));
        }
    }

    void _load_slot(
            std::uint8_t slot_index,
            const battle_presentation_portrait_resource&
                    resource,
            std::array<
                    std::uint8_t,
                    battle_presentation_portrait_bytes>&
                    scratch,
            battle_presentation_portrait_slot_renderer& slot)
    {
        slot.reset();
        bn::memory::decompress(
                bn::compression_type::LZ77,
                battle_presentation_portrait_compressed_gfx
                                .data() +
                        resource.gfx_offset,
                battle_presentation_portrait_bytes,
                scratch.data());
        if(slot_index != 0)
        {
            for(std::uint8_t& palette_index : scratch)
            {
                palette_index =
                        battle_presentation_portrait_palette_index(
                                palette_index,
                                slot_index);
            }
        }

        for(std::size_t component_index = 0;
                component_index <
                        battle_presentation_portrait_component_count;
                ++component_index)
        {
            const battle_presentation_portrait_component&
                    component =
                            battle_presentation_portrait_components[
                                    component_index];
            const bn::sprite_shape_size shape_size(
                    component.width,
                    component.height);
            const int tiles_count =
                    shape_size.tiles_count(
                            bn::bpp_mode::BPP_8);
            slot.tiles[component_index] =
                    bn::sprite_tiles_ptr::allocate(
                            tiles_count,
                            bn::bpp_mode::BPP_8);
            bn::span<bn::tile> vram =
                    *slot.tiles[component_index]->vram();
            const auto* source_tiles =
                    reinterpret_cast<const bn::tile*>(
                            scratch.data() +
                            component.source_offset);
            bn::memory::copy(
                    source_tiles[0],
                    tiles_count,
                    vram[0]);

            bn::sprite_ptr sprite =
                    bn::sprite_ptr::create(
                            shape_size,
                            *slot.tiles[component_index],
                            *_palette);
            sprite.set_bg_priority(1);
            slot.sprites[component_index] =
                    static_cast<bn::sprite_ptr&&>(
                            sprite);
        }
        slot.portrait_id = resource.portrait_id;
        slot.expression_id =
                resource.expression_id;
        slot.loaded = true;
    }

    static void _position_slot(
            std::uint8_t slot_index,
            std::uint8_t motion_mode,
            battle_presentation_portrait_slot_renderer& slot)
    {
        const int origin_x =
                battle_presentation_portrait_origin_x(
                        slot_index,
                        motion_mode);
        constexpr int origin_y = 8;
        for(std::size_t component_index = 0;
                component_index <
                        battle_presentation_portrait_component_count;
                ++component_index)
        {
            if(! slot.sprites[component_index])
            {
                continue;
            }
            const battle_presentation_portrait_component&
                    component =
                            battle_presentation_portrait_components[
                                    component_index];
            slot.sprites[component_index]->set_position(
                    origin_x + component.x +
                            component.width / 2 -
                            screen_width / 2,
                    origin_y + component.y +
                            component.height / 2 -
                            screen_height / 2);
        }
    }

    std::array<
            battle_presentation_portrait_slot_renderer,
            battle_presentation_visible_portrait_slots>
            _slots;
    alignas(4) std::array<
            bn::color,
            battle_presentation_portrait_palette_colors>
            _palette_colors;
    bn::optional<bn::sprite_palette_ptr> _palette;
};

class battle_dialogue_background_runtime_renderer
{
public:
    void update(
            bool visible,
            bn::optional<bn::regular_bg_ptr>& map)
    {
        if(! visible)
        {
            reset();
            return;
        }
        if(_background)
        {
            return;
        }

        // Selector 1 is an exclusive full-screen BG state in the original.
        // Release the map BG first so its 8bpp palette and tile blocks do not
        // overlap the exact dialogue background allocation.
        map.reset();
        bn::core::update();
        _background =
                bn::regular_bg_items::
                        battle_ui_dialogue_background
                                .create_bg(0, 0);
        _background->set_priority(3);
    }

    void reset()
    {
        _background.reset();
    }

private:
    bn::optional<bn::regular_bg_ptr> _background;
};

class battle_presentation_message_window_runtime_renderer
{
public:
    void update(bool visible)
    {
        if(! visible)
        {
            reset();
            return;
        }
        if(_sprites[0])
        {
            return;
        }
        for(std::size_t index = 0;
                index < _sprites.size();
                ++index)
        {
            bn::sprite_ptr black_bar =
                    bn::sprite_items::
                            battle_ui_message_black_bar
                                    .create_sprite(
                                            -90 +
                                                    static_cast<int>(
                                                            index) *
                                                            60,
                                            12);
            black_bar.set_bg_priority(2);
            black_bar.set_z_order(999);
            _black_bar_sprites[index] =
                    static_cast<bn::sprite_ptr&&>(
                            black_bar);
            bn::sprite_ptr sprite =
                    bn::sprite_items::
                            battle_ui_message_panel
                                    .create_sprite(
                                            -90 +
                                                    static_cast<int>(
                                                            index) *
                                                            60,
                                            48,
                                            static_cast<int>(
                                                    index));
            sprite.set_bg_priority(2);
            sprite.set_z_order(1000);
            _sprites[index] =
                    static_cast<bn::sprite_ptr&&>(
                            sprite);
        }
    }

    void reset()
    {
        for(auto& sprite : _black_bar_sprites)
        {
            sprite.reset();
        }
        for(auto& sprite : _sprites)
        {
            sprite.reset();
        }
    }

private:
    std::array<
            bn::optional<bn::sprite_ptr>,
            4> _black_bar_sprites;
    std::array<
            bn::optional<bn::sprite_ptr>,
            4> _sprites;
};

class battle_combat_stage_runtime_renderer
{
public:
    void reset()
    {
        _release_resources();
    }

    void update(
            const battle_scene_snapshot<12>& state,
            const battle_scene_presentation& presentation,
            bn::optional<bn::regular_bg_ptr>& map,
            const bn::regular_bg_item& map_item,
            int map_origin,
            const bn::camera_ptr& camera)
    {
        const battle_combat_presentation& combat =
                presentation.combat();
        if(! combat.busy() || combat.map_visible())
        {
            if(_duel_background_bound ||
                    _movie_background_bound ||
                    _cutin_background_bound ||
                    _duel_hud_background)
            {
                _release_resources();
                _restore_map(
                        map,
                        map_item,
                        map_origin,
                        camera);
            }
            return;
        }

        const bool action_16_movie =
                combat.effect_visible() &&
                combat.resource() ==
                        battle_combat_presentation_resource::
                                action_16_fire_movie_components;
        const bool action_16_cutin =
                combat.resource() ==
                        battle_combat_presentation_resource::
                                action_16_fire_cutin_components;
        if(action_16_cutin)
        {
            if(_movie_background_bound)
            {
                _release_action_16_movie_resources();
            }
            _bind_action_16_cutin(map);
            _set_visible(false);
            _hide_action_effect_sprites();
            _update_action_16_cutin(combat);
            return;
        }
        if(action_16_movie)
        {
            if(_cutin_background_bound)
            {
                _release_action_16_cutin_resources();
            }
            _bind_action_16_movie(map);
            _set_visible(false);
            _hide_action_effect_sprites();
            _update_action_16_movie(combat, *map);
            return;
        }
        if(_movie_background_bound)
        {
            _unbind_action_16_movie(map);
        }
        if(_cutin_background_bound)
        {
            _release_action_16_cutin_resources();
        }
        _bind_duel_background(map, true);
        _set_visible(true);
        _update_duel_hud(state, presentation);
        if(combat.effect_visible() &&
                combat.resource() ==
                        battle_combat_presentation_resource::
                                action_05_dust_sequence)
        {
            _update_effect_sequence(
                    combat,
                    battle_action_05_dust_sequence,
                    battle_action_05_dust_assets,
                    battle_action_05_dust_sprite_items);
        }
        else if(combat.effect_visible() &&
                combat.resource() ==
                        battle_combat_presentation_resource::
                                action_05_hit_sequence)
        {
            _update_effect_sequence(
                    combat,
                    battle_action_05_hit_sequence,
                    battle_action_05_hit_assets,
                    battle_action_05_hit_sprite_items);
        }
        else if(combat.effect_visible() &&
                combat.resource() ==
                        battle_combat_presentation_resource::
                                action_16_fire_hit_sequence)
        {
            _update_effect_sequence(
                    combat,
                    battle_action_16_fire_hit_sequence,
                    battle_action_16_fire_hit_assets,
                    battle_action_16_fire_hit_sprite_items);
        }
        else if(combat.effect_visible() &&
                combat.resource() ==
                        battle_combat_presentation_resource::
                                ninja_tool_bomb_projectile_sequence)
        {
            _update_effect_sequence(
                    combat,
                    battle_ninja_tool_bomb_projectile_sequence,
                    battle_ninja_tool_bomb_projectile_assets,
                    battle_ninja_tool_bomb_projectile_sprite_items);
        }
        else if(combat.effect_visible() &&
                combat.resource() ==
                        battle_combat_presentation_resource::
                                ninja_tool_bomb_smoke_sequence)
        {
            _update_effect_sequence(
                    combat,
                    battle_ninja_tool_bomb_smoke_sequence,
                    battle_ninja_tool_bomb_smoke_assets,
                    battle_ninja_tool_bomb_smoke_sprite_items);
        }
        else
        {
            _hide_action_effect_sprites();
        }
        if(combat.resource() ==
                        battle_combat_presentation_resource::
                                action_16_fire_hit_sequence &&
                combat.stage() ==
                        battle_combat_presentation_stage::impact)
        {
            const int frame = combat.stage_frame();
            const int fade_steps =
                    frame < 3 ? 16 :
                    frame < 18 ? 18 - frame : 0;
            const bn::fixed fade_intensity =
                    bn::fixed(fade_steps) / 16;
            bn::bg_palettes::set_fade(
                    bn::color(0x7FFF),
                    fade_intensity);
            bn::sprite_palettes::set_fade(
                    bn::color(0x7FFF),
                    fade_intensity);
        }
    }

private:
    void _release_background_before_bpp_transition(
            bn::optional<bn::regular_bg_ptr>& map)
    {
        _duel_hud_background.reset();
        map.reset();
        _duel_background_bound = false;
        // BPP8 palettes require the full BG palette bank.  Commit the
        // outgoing 4BPP duel/map backgrounds before creating a BPP8
        // cut-in or action movie, and vice versa.
        bn::core::update();
    }

    void _bind_duel_background(
            bn::optional<bn::regular_bg_ptr>& map,
            bool with_hud)
    {
        if(! _duel_background_bound)
        {
            _release_background_before_bpp_transition(map);
            map = bn::regular_bg_items::
                          battle_duel_forest
                                  .create_bg(8, 80);
            map->remove_camera();
            // Original BG0 scroll is VOFS=0x1E0.  On a 256px map this
            // presents rows 224..255, then wraps to row 0.
            map->set_position(8, 80);
            map->set_priority(3);
            map->set_visible(true);
            _duel_background_bound = true;
        }
        if(with_hud)
        {
            if(! _duel_hud_background)
            {
                _duel_hud_background =
                        bn::regular_bg_items::
                                battle_duel_hud_shell
                                        .create_bg(8, 48);
                _duel_hud_background->set_priority(0);
                _duel_hud_background->set_visible(false);
            }
        }
        else
        {
            _duel_hud_background.reset();
        }
    }

    void _bind_action_16_movie(
            bn::optional<bn::regular_bg_ptr>& map)
    {
        if(_movie_background_bound)
        {
            return;
        }

        _release_background_before_bpp_transition(map);
        map = bn::regular_bg_items::
                      battle_action_16_movie_streaks
                              .create_bg(8, 48);
        map->remove_camera();
        map->set_position(8, 48);
        map->set_priority(3);
        map->set_visible(false);

        _movie_actor_bg =
                bn::regular_bg_items::
                        battle_action_16_movie_actor
                                .create_bg(-120, 48);
        _movie_actor_bg->set_priority(2);
        _movie_actor_bg->set_visible(false);
        _movie_fire_bg =
                bn::regular_bg_items::
                        battle_action_16_movie_fire
                                .create_bg(-247, 48);
        _movie_fire_bg->set_priority(1);
        _movie_fire_bg->set_visible(false);
        _movie_dialogue_bg =
                bn::regular_bg_items::
                        battle_action_16_movie_dialogue
                                .create_bg(8, 48);
        _movie_dialogue_bg->set_priority(0);
        _movie_dialogue_bg->set_visible(false);
        _movie_palette = map->palette();
        _movie_actor_bg->set_palette(*_movie_palette);
        _movie_fire_bg->set_palette(*_movie_palette);
        _movie_dialogue_bg->set_palette(*_movie_palette);

        _bind_action_16_title_sprites();
        bn::bg_palettes::set_fade(
                bn::color(0x7FFF), 0);
        bn::sprite_palettes::set_fade(
                bn::color(0x7FFF), 0);
        _movie_background_bound = true;
        _duel_background_bound = false;
    }

    void _bind_action_16_title_sprites()
    {
        if(_movie_title_sprites[0])
        {
            return;
        }
        _movie_title_sprites[0] =
                bn::sprite_items::
                        battle_action_16_movie_title_0
                                .create_sprite(-20, -60);
        _movie_title_sprites[1] =
                bn::sprite_items::
                        battle_action_16_movie_title_1
                                .create_sprite(4, -60);
        _movie_title_sprites[2] =
                bn::sprite_items::
                        battle_action_16_movie_title_2
                                .create_sprite(28, -60);
        for(auto& sprite : _movie_title_sprites)
        {
            sprite->set_bg_priority(0);
            sprite->set_visible(false);
        }
    }

    void _bind_action_16_cutin(
            bn::optional<bn::regular_bg_ptr>& map)
    {
        if(_cutin_background_bound)
        {
            return;
        }
        _release_background_before_bpp_transition(map);
        _cutin_dialogue_bg =
                bn::regular_bg_items::
                        battle_action_16_cutin_dialogue
                                .create_bg(8, 48);
        _cutin_dialogue_bg->set_priority(0);
        _cutin_dialogue_bg->set_visible(false);
        _cutin_palette = _cutin_dialogue_bg->palette();
        for(std::size_t color_index = 0;
                color_index <
                        battle_action_16_cutin_palette.size();
                ++color_index)
        {
            _cutin_palette->set_color(
                    static_cast<int>(color_index),
                    bn::color(
                            battle_action_16_cutin_palette[
                                    color_index]));
        }
        _cutin_dialogue_bg->set_palette(
                *_cutin_palette);
        _cutin_portrait_bg =
                bn::regular_bg_items::
                        battle_action_16_cutin_portrait
                                .create_bg(8, 48);
        _cutin_portrait_bg->set_palette(
                *_cutin_palette);
        _cutin_portrait_bg->set_priority(1);
        _cutin_portrait_bg->set_visible(false);
        bn::rect_window cutin_fade_window =
                bn::rect_window::internal();
        _previous_cutin_window_boundaries =
                cutin_fade_window.boundaries();
        _previous_cutin_window_visible =
                cutin_fade_window.visible();
        _previous_cutin_window_blending =
                cutin_fade_window.show_blending();
        _previous_outside_window_blending =
                bn::window::outside().show_blending();
        _cutin_window_owned = true;
        _bind_action_16_title_sprites();
        _cutin_background_bound = true;
    }

    void _release_action_16_cutin_resources()
    {
        if(_cutin_portrait_bg)
        {
            _cutin_portrait_bg
                    ->set_blending_top_enabled(false);
        }
        bn::blending::set_fade_alpha(0);
        if(_cutin_window_owned)
        {
            bn::rect_window cutin_fade_window =
                    bn::rect_window::internal();
            cutin_fade_window.set_boundaries(
                    _previous_cutin_window_boundaries);
            cutin_fade_window.set_show_blending(
                    _previous_cutin_window_blending);
            cutin_fade_window.set_visible(
                    _previous_cutin_window_visible);
            bn::window::outside().set_show_blending(
                    _previous_outside_window_blending);
            _cutin_window_owned = false;
        }
        _cutin_portrait_bg.reset();
        _cutin_dialogue_bg.reset();
        _cutin_palette.reset();
        _cutin_background_bound = false;
    }

    void _update_action_16_cutin(
            const battle_combat_presentation& combat)
    {
        const int frame = combat.stage_frame();
        const bool cutin_visible = frame >= 2;
        const int portrait_scroll =
                frame < 2 ? 256 :
                frame >= 18 ? 0 :
                256 - (frame - 2) * 16;
        _cutin_portrait_bg->set_position(
                136 - portrait_scroll,
                48);
        _cutin_portrait_bg->set_visible(
                cutin_visible);
        _cutin_dialogue_bg->set_visible(
                cutin_visible);
        _movie_title_sprites[0]->set_visible(
                frame >= 34);
        _movie_title_sprites[1]->set_visible(
                frame >= 40);
        _movie_title_sprites[2]->set_visible(
                frame >= 46);
        int fade_steps =
                frame > 104 ? frame - 104 : 0;
        if(fade_steps > 16)
        {
            fade_steps = 16;
        }
        const bool fading = fade_steps > 0;
        _cutin_portrait_bg
                ->set_blending_top_enabled(fading);
        if(fading)
        {
            bn::rect_window cutin_fade_window =
                    bn::rect_window::internal();
            cutin_fade_window.set_boundaries(
                    -48, -120, 32, 120);
            cutin_fade_window.set_visible(true);
            cutin_fade_window.set_show_blending(true);
            bn::window::outside().set_show_blending(
                    false);
        }
        bn::blending::set_white_fade_color();
        bn::blending::set_fade_alpha(
                bn::fixed(fade_steps) / 16);
    }

    void _release_action_16_movie_resources()
    {
        for(auto& sprite : _movie_title_sprites)
        {
            sprite.reset();
        }
        _movie_actor_bg.reset();
        _movie_fire_bg.reset();
        _movie_dialogue_bg.reset();
        _movie_palette.reset();
        bn::bg_palettes::set_fade_intensity(0);
        bn::sprite_palettes::set_fade_intensity(0);
        bn::blending::set_transparency_weights(1, 0);
        _movie_background_bound = false;
    }

    void _unbind_action_16_movie(
            bn::optional<bn::regular_bg_ptr>& map)
    {
        _release_action_16_movie_resources();
        _bind_duel_background(map, true);
    }

    void _update_action_16_movie(
            const battle_combat_presentation& combat,
            bn::regular_bg_ptr& streaks)
    {
        static constexpr std::array<int, 30>
                actor_scroll_x = {{
                    248, 240, 233, 226, 219,
                    212, 206, 200, 194, 188,
                    183, 178, 173, 168, 164,
                    160, 156, 152, 149, 146,
                    143, 140, 138, 136, 134,
                    132, 131, 130, 129, 128,
                }};
        const int frame = combat.stage_frame();
        const bool action_visible = frame >= 5;
        const int actor_index =
                frame <= 5 ? 0 :
                frame >= 34 ? 29 :
                frame - 5;
        const int actor_scroll =
                actor_scroll_x[
                        static_cast<std::size_t>(
                                actor_index)];
        const int streak_scroll =
                frame < 5 ? 0 :
                (frame - 4) * 2;
        const int fire_scroll =
                511 -
                (frame <= 36 ? 0 :
                 (frame - 36) / 4);

        streaks.set_position(
                8 - (streak_scroll & 0xFF),
                48);
        streaks.set_visible(action_visible);
        _movie_actor_bg->set_position(
                8 - (actor_scroll & 0xFF),
                48);
        _movie_actor_bg->set_visible(action_visible);
        _movie_fire_bg->set_position(
                8 - (fire_scroll & 0xFF),
                48);
        _movie_fire_bg->set_visible(frame >= 36);
        _movie_dialogue_bg->set_visible(true);
        for(auto& sprite : _movie_title_sprites)
        {
            sprite->set_visible(frame >= 1);
        }

        BN_ASSERT(
                frame >= 0 &&
                        frame < static_cast<int>(
                                battle_action_16_movie_fire_palettes
                                        .size()),
                "Invalid action 16 movie frame: ",
                frame);
        const std::size_t timeline_index =
                static_cast<std::size_t>(frame);
        const auto& fire_palette =
                battle_action_16_movie_fire_palettes[
                        timeline_index];
        for(std::size_t color_index = 0;
                color_index < fire_palette.size();
                ++color_index)
        {
            _movie_palette->set_color(
                    64 + static_cast<int>(color_index),
                    bn::color(fire_palette[color_index]));
        }
        const bool transparency_visible =
                frame >= 36 && frame < 111;
        _movie_fire_bg->set_blending_top_enabled(
                transparency_visible);
        _movie_actor_bg->set_blending_bottom_enabled(
                transparency_visible);
        streaks.set_blending_bottom_enabled(
                transparency_visible);
        if(transparency_visible)
        {
            bn::blending::set_transparency_weights(
                    bn::fixed(
                            battle_action_16_movie_blend_top_weights[
                                    timeline_index]) / 16,
                    bn::fixed(
                            battle_action_16_movie_blend_bottom_weights[
                                    timeline_index]) / 16);
        }

        int fade_steps = 0;
        if(frame < 6)
        {
            fade_steps = 16;
        }
        else if(frame < 21)
        {
            fade_steps = 21 - frame;
        }
        else if(frame >= 111)
        {
            fade_steps = frame - 111;
            if(fade_steps > 16)
            {
                fade_steps = 16;
            }
        }
        const bn::fixed fade_intensity =
                bn::fixed(fade_steps) / 16;
        bn::bg_palettes::set_fade_intensity(
                fade_intensity);
        bn::sprite_palettes::set_fade_intensity(
                fade_intensity);
    }

    void _restore_map(
            bn::optional<bn::regular_bg_ptr>& map,
            const bn::regular_bg_item& map_item,
            int map_origin,
            const bn::camera_ptr& camera)
    {
        _release_background_before_bpp_transition(map);
        map = map_item.create_bg(map_origin, 0);
        map->set_position(map_origin, 0);
        map->set_camera(camera);
        map->set_priority(3);
        map->set_visible(true);
        _duel_background_bound = false;
        _movie_background_bound = false;
        _cutin_background_bound = false;
    }

    void _release_resources()
    {
        _set_effect_blending(false);
        _release_action_16_cutin_resources();
        _release_action_16_movie_resources();
        for(auto& sprite : _action_effect_sprites)
        {
            sprite.reset();
        }
        for(auto& sprite : _duel_bar_sprites)
        {
            sprite.reset();
        }
        _duel_hp_track_tiles.reset();
        _duel_hp_fill_tiles.reset();
        _duel_chakra_track_tiles.reset();
        _duel_chakra_fill_tiles.reset();
        _duel_bar_palette.reset();
        _duel_hud_background.reset();
        _action_effect_asset_indices.fill(0xFF);
    }

    void _update_duel_bar(
            int first_sprite,
            int x,
            int y,
            int value,
            int maximum,
            bool chakra,
            bool visible)
    {
        bn::optional<bn::sprite_ptr>& track =
                _duel_bar_sprites[
                        static_cast<std::size_t>(
                                first_sprite)];
        bn::optional<bn::sprite_ptr>& fill =
                _duel_bar_sprites[
                        static_cast<std::size_t>(
                                first_sprite + 1)];
        if(! _duel_bar_palette)
        {
            _duel_bar_palette =
                    bn::sprite_items::battle_ui_bar
                            .palette_item()
                            .create_palette();
            _duel_hp_track_tiles =
                    bn::sprite_items::battle_ui_bar
                            .tiles_item()
                            .create_tiles(0);
            _duel_chakra_fill_tiles =
                    bn::sprite_items::battle_ui_bar
                            .tiles_item()
                            .create_tiles(1);
            _duel_hp_fill_tiles =
                    bn::sprite_items::battle_ui_bar
                            .tiles_item()
                            .create_tiles(2);
            _duel_chakra_track_tiles =
                    bn::sprite_items::battle_ui_bar
                            .tiles_item()
                            .create_tiles(3);
        }
        if(! track)
        {
            track = bn::sprite_ptr::create(
                    x,
                    y,
                    bn::sprite_items::battle_ui_bar
                            .shape_size(),
                    chakra ?
                            *_duel_chakra_track_tiles :
                            *_duel_hp_track_tiles,
                    *_duel_bar_palette);
            track->set_bg_priority(0);
            track->set_z_order(10);
        }
        if(! fill)
        {
            fill = bn::sprite_ptr::create(
                    x,
                    y,
                    bn::sprite_items::battle_ui_bar
                            .shape_size(),
                    chakra ?
                            *_duel_chakra_fill_tiles :
                            *_duel_hp_fill_tiles,
                    *_duel_bar_palette);
            fill->set_bg_priority(0);
            fill->set_z_order(9);
            fill->set_remove_affine_mat_when_not_needed(
                    true);
        }
        track->set_visible(visible);
        if(! visible || value <= 0 || maximum <= 0)
        {
            fill->set_visible(false);
            return;
        }
        if(value > maximum)
        {
            value = maximum;
        }
        const bn::fixed scale =
                bn::fixed(value) / maximum;
        fill->set_horizontal_scale(scale);
        fill->set_x(x - 16 + scale * 16);
        fill->set_visible(true);
    }

    void _update_duel_hud(
            const battle_scene_snapshot<12>& state,
            const battle_scene_presentation& presentation)
    {
        const battle_combat_presentation& combat =
                presentation.combat();
        const bool visible = combat.hud_visible();
        if(_duel_hud_background)
        {
            _duel_hud_background->set_visible(visible);
        }

        const battle_scene_unit_view* actor =
                combatant_view(
                        state,
                        presentation.event().actor_id);
        const battle_scene_unit_view* target =
                combatant_view(
                        state,
                        presentation.event().target_id);
        const battle_scene_unit_view* player = nullptr;
        const battle_scene_unit_view* enemy = nullptr;
        int player_hp = 0;
        int player_max_hp = 0;
        int enemy_hp = 0;
        int enemy_max_hp = 0;
        if(actor)
        {
            const int displayed_hp =
                    combat.displayed_actor_hp();
            const int displayed_max_hp =
                    combat.displayed_actor_max_hp();
            if(actor->side == battle_side::player)
            {
                player = actor;
                player_hp = displayed_hp >= 0 ?
                        displayed_hp : actor->hp;
                player_max_hp = displayed_max_hp >= 0 ?
                        displayed_max_hp : actor->max_hp;
            }
            else
            {
                enemy = actor;
                enemy_hp = displayed_hp >= 0 ?
                        displayed_hp : actor->hp;
                enemy_max_hp = displayed_max_hp >= 0 ?
                        displayed_max_hp : actor->max_hp;
            }
        }
        if(target)
        {
            const int displayed_hp =
                    combat.displayed_target_hp();
            const int displayed_max_hp =
                    combat.displayed_target_max_hp();
            if(target->side == battle_side::player)
            {
                player = target;
                player_hp = displayed_hp >= 0 ?
                        displayed_hp : target->hp;
                player_max_hp = displayed_max_hp >= 0 ?
                        displayed_max_hp : target->max_hp;
            }
            else
            {
                enemy = target;
                enemy_hp = displayed_hp >= 0 ?
                        displayed_hp : target->hp;
                enemy_max_hp = displayed_max_hp >= 0 ?
                        displayed_max_hp : target->max_hp;
            }
        }
        const int player_bar_x =
                combat.single_actor_stage() ? 32 : -88;
        _update_duel_bar(
                0,
                player_bar_x,
                60,
                player_hp,
                player_max_hp,
                false,
                visible && player);
        _update_duel_bar(
                2,
                player_bar_x,
                68,
                player ? player->chakra : 0,
                player ? player->max_chakra : 0,
                true,
                visible && player);
        _update_duel_bar(
                4,
                32,
                60,
                enemy_hp,
                enemy_max_hp,
                false,
                visible && enemy);
        _update_duel_bar(
                6,
                32,
                68,
                enemy ? enemy->chakra : 0,
                enemy ? enemy->max_chakra : 0,
                true,
                visible && enemy);
    }

    template<std::size_t AssetCount>
    void _update_effect_sequence(
            const battle_combat_presentation& combat,
            const battle_effect_sequence& sequence,
            const std::array<
                    battle_effect_asset,
                    AssetCount>& assets,
            const std::array<
                    const bn::sprite_item*,
                    AssetCount>& items)
    {
        BN_ASSERT(
                sequence.total_duration() <=
                        combat.current_step().duration -
                                combat.current_step().
                                        resource_frame_offset,
                "Effect sequence exceeds stage: ",
                sequence.total_duration(),
                " > ",
                combat.current_step().duration -
                        combat.current_step().
                                resource_frame_offset);
        const battle_effect_frame* frame =
                sequence.frame_at(
                        combat.resource_frame());
        bool semi_transparent = false;
        if(frame)
        {
            for(std::size_t index = 0;
                    index < frame->component_count;
                    ++index)
            {
                semi_transparent =
                        semi_transparent ||
                        frame->components[index].
                                semi_transparent;
            }
        }
        _set_effect_blending(semi_transparent);
        for(std::size_t index = 0;
                index < _action_effect_sprites.size();
                ++index)
        {
            bn::optional<bn::sprite_ptr>& sprite =
                    _action_effect_sprites[index];
            if(! frame ||
                    index >= frame->component_count)
            {
                if(sprite)
                {
                    sprite->set_visible(false);
                }
                continue;
            }

            const battle_effect_component& component =
                    frame->components[index];
            BN_ASSERT(
                    component.asset_index <
                            assets.size(),
                    "Invalid effect asset: ",
                    component.asset_index);
            const battle_effect_asset& asset =
                    assets[
                            component.asset_index];
            const bn::sprite_item* item =
                    items[
                            component.asset_index];
            BN_ASSERT(item, "Missing effect item");
            // Original OAM stores top-left screen coordinates. Butano
            // stores sprite centers relative to the 240x160 viewport.
            const int x =
                    component.x + asset.width / 2 -
                    screen_width / 2;
            const int y =
                    component.y + asset.height / 2 -
                    screen_height / 2;
            if(! sprite)
            {
                sprite = item->create_sprite(x, y);
            }
            else if(_action_effect_asset_indices[index] !=
                    component.asset_index)
            {
                sprite->set_item(*item);
            }
            _action_effect_asset_indices[index] =
                    component.asset_index;
            sprite->set_position(x, y);
            sprite->set_bg_priority(component.priority);
            sprite->set_horizontal_flip(
                    component.horizontal_flip);
            sprite->set_vertical_flip(
                    component.vertical_flip);
            sprite->set_blending_enabled(
                    component.semi_transparent);
            sprite->set_visible(true);
        }
    }

    void _hide_action_effect_sprites()
    {
        _set_effect_blending(false);
        for(auto& sprite : _action_effect_sprites)
        {
            if(sprite)
            {
                sprite->set_visible(false);
            }
        }
    }

    void _set_effect_blending(bool enabled)
    {
        if(enabled && ! _effect_blending_owned)
        {
            _previous_effect_transparency_top_weight =
                    bn::blending::
                            transparency_top_weight();
            _previous_effect_transparency_bottom_weight =
                    bn::blending::
                            transparency_bottom_weight();
            bn::blending::set_transparency_weights(
                    1, 0.5);
            _effect_blending_owned = true;
        }
        else if(! enabled && _effect_blending_owned)
        {
            bn::blending::set_transparency_weights(
                    _previous_effect_transparency_top_weight,
                    _previous_effect_transparency_bottom_weight);
            _effect_blending_owned = false;
        }
    }

    void _set_visible(bool visible)
    {
        for(auto& sprite : _action_effect_sprites)
        {
            if(sprite)
            {
                sprite->set_visible(false);
            }
        }
        if(! visible)
        {
            if(_duel_hud_background)
            {
                _duel_hud_background->set_visible(false);
            }
            for(auto& sprite : _duel_bar_sprites)
            {
                if(sprite)
                {
                    sprite->set_visible(false);
                }
            }
        }
    }

    std::array<bn::optional<bn::sprite_ptr>, 3>
            _movie_title_sprites;
    std::array<
            bn::optional<bn::sprite_ptr>,
            battle_effect_maximum_components>
            _action_effect_sprites;
    std::array<bn::optional<bn::sprite_ptr>, 8>
            _duel_bar_sprites;
    std::array<
            std::uint8_t,
            battle_effect_maximum_components>
            _action_effect_asset_indices = {};
    bn::fixed _previous_effect_transparency_top_weight = 1;
    bn::fixed _previous_effect_transparency_bottom_weight = 0;
    bool _effect_blending_owned = false;
    bn::optional<bn::sprite_tiles_ptr>
            _duel_hp_track_tiles;
    bn::optional<bn::sprite_tiles_ptr>
            _duel_hp_fill_tiles;
    bn::optional<bn::sprite_tiles_ptr>
            _duel_chakra_track_tiles;
    bn::optional<bn::sprite_tiles_ptr>
            _duel_chakra_fill_tiles;
    bn::optional<bn::sprite_palette_ptr>
            _duel_bar_palette;
    bn::optional<bn::regular_bg_ptr>
            _duel_hud_background;
    bn::optional<bn::regular_bg_ptr> _movie_actor_bg;
    bn::optional<bn::regular_bg_ptr> _movie_fire_bg;
    bn::optional<bn::regular_bg_ptr>
            _movie_dialogue_bg;
    bn::optional<bn::bg_palette_ptr> _movie_palette;
    bn::optional<bn::regular_bg_ptr>
            _cutin_portrait_bg;
    bn::optional<bn::regular_bg_ptr>
            _cutin_dialogue_bg;
    bn::optional<bn::bg_palette_ptr> _cutin_palette;
    bn::fixed_rect _previous_cutin_window_boundaries;
    bool _previous_cutin_window_visible = true;
    bool _previous_cutin_window_blending = true;
    bool _previous_outside_window_blending = true;
    bool _cutin_window_owned = false;
    bool _duel_background_bound = false;
    bool _movie_background_bound = false;
    bool _cutin_background_bound = false;
};

void update_script_message_window(
        const battle_scene_snapshot<12>& state,
        bool presentation_busy,
        battle_presentation_message_window_runtime_renderer&
                renderer)
{
    renderer.update(
            state.phase ==
                            battle_scene_phase::
                                    script_blocked &&
                    ! presentation_busy &&
                    state.script.message_window_visible);
}

void update_script_portraits(
        const battle_scene_snapshot<12>& state,
        bool presentation_busy,
        battle_presentation_portrait_runtime_renderer&
                renderer,
        std::array<
                std::uint8_t,
                battle_presentation_portrait_bytes>& scratch)
{
    if(state.phase ==
                    battle_scene_phase::script_blocked &&
            ! presentation_busy)
    {
        renderer.update(
                state.script.portraits,
                scratch);
    }
    else
    {
        renderer.reset();
    }
}

[[nodiscard]] bool update_combat_portrait(
        const battle_scene_snapshot<12>& state,
        const battle_scene_presentation& presentation,
        battle_presentation_portrait_runtime_renderer&
                renderer,
        std::array<
                std::uint8_t,
                battle_presentation_portrait_bytes>& scratch)
{
    if(! presentation.combat().title_visible())
    {
        return false;
    }
    if(presentation.combat().resource() ==
            battle_combat_presentation_resource::
                    action_16_fire_cutin_components)
    {
        renderer.reset();
        return true;
    }

    const battle_scene_unit_view* actor = nullptr;
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        if(state.units[index].id ==
                presentation.event().actor_id)
        {
            actor = &state.units[index];
            break;
        }
    }
    if(! actor ||
            ! battle_presentation_portrait_resource_for(
                    actor->character_id,
                    0))
    {
        renderer.reset();
        return true;
    }

    std::array<
            battle_presentation_portrait_snapshot,
            3> portraits = {};
    portraits[0].visible = true;
    portraits[0].focused = true;
    portraits[0].portrait_id =
            actor->character_id;
    portraits[0].expression_id = 0;
    portraits[0].motion_mode = 2;
    renderer.update(portraits, scratch);
    return true;
}

void apply_visual_resource_transition(
        const battle_visual_resource_transition&
                transition,
        std::array<battle_unit_sprite_state, 12>&
                unit_sprites,
        bn::vector<bn::sprite_ptr, 2>&
                map_scenery_sprite,
        bn::optional<bn::sprite_ptr>& cursor_shadow,
        bn::optional<bn::sprite_ptr>& cursor,
        bn::optional<bn::sprite_ptr>&
                battlefield_object_expiry_sprite,
        bn::vector<
                bn::sprite_ptr,
                battle_runtime_scene_sprite_budget::
                        maximum_text_sprites>&
                text_sprites,
        bn::vector<bn::sprite_ptr, 64>&
                script_glyph_sprites,
        battle_ui_runtime_renderer& ui_renderer,
        battle_presentation_portrait_runtime_renderer&
                portrait_renderer,
        battle_presentation_message_window_runtime_renderer&
                message_window_renderer,
        battle_dialogue_background_runtime_renderer&
                dialogue_background_renderer,
        battle_combat_stage_runtime_renderer&
                combat_stage_renderer)
{
    if(! transition.changed)
    {
        return;
    }
    if(transition.release_map)
    {
        for(battle_unit_sprite_state& unit :
                unit_sprites)
        {
            unit.reset();
        }
        map_scenery_sprite.clear();
        cursor_shadow.reset();
        cursor.reset();
        battlefield_object_expiry_sprite.reset();
        text_sprites.clear();
        ui_renderer.reset();
        combat_stage_renderer.reset();
    }
    if(transition.release_script)
    {
        script_glyph_sprites.clear();
        message_window_renderer.reset();
        dialogue_background_renderer.reset();
        portrait_renderer.reset();
    }
    if(transition.release_portrait)
    {
        portrait_renderer.reset();
    }
    if(transition.commit_before_allocate)
    {
        // Butano only returns released OBJ tiles and palette banks to their
        // allocators at a core boundary.  All outgoing owners are released
        // above; incoming renderers run only after this single commit.
        bn::core::update();
    }
}

void ensure_battle_map_background(
        const battle_runtime_scene_config& config,
        const battle_background_stream& background,
        const bn::camera_ptr& camera,
        bn::optional<bn::regular_bg_ptr>& map)
{
    if(map)
    {
        return;
    }
    map = config.map_items[
                  background.chunk_index()]
                  ->create_bg(
                          background.chunk_origin(),
                          0);
    map->set_priority(3);
    map->set_camera(camera);
}

void ensure_map_scenery(
        const battle_runtime_scene_config& config,
        const bn::camera_ptr& camera,
        const battle_scene_object_snapshot& objects,
        bn::vector<bn::sprite_ptr, 2>& map_scenery_sprite)
{
    if(config.battle_id != 14)
    {
        map_scenery_sprite.clear();
        return;
    }
    int count = 0;
    for(std::size_t index = 0; index < objects.count; ++index)
    {
        const auto& object = objects.objects[index];
        if(object.type == 3 && object.payload_id == 2) ++count;
    }
    if(map_scenery_sprite.size() == count) return;
    map_scenery_sprite.clear();
    for(std::size_t index = 0; index < objects.count; ++index)
    {
        const auto& object = objects.objects[index];
        if(object.type != 3 || object.payload_id != 2) continue;
        auto sprite = bn::sprite_items::battle_scenario_49_chest.create_sprite(
                world_x(object.position), world_y(object.position) - 8);
        sprite.set_camera(camera);
        sprite.set_bg_priority(2);
        sprite.set_z_order(-object.position.y);
        map_scenery_sprite.push_back(bn::move(sprite));
    }
}

void ensure_map_cursor(
        const battle_scene_snapshot<12>& state,
        const bn::camera_ptr& camera,
        bn::optional<bn::sprite_ptr>& cursor_shadow,
        bn::optional<bn::sprite_ptr>& cursor)
{
    if(cursor_shadow && cursor)
    {
        return;
    }
    cursor_shadow.reset();
    cursor.reset();
    cursor_shadow =
            bn::sprite_items::scenario_41_cursor_shadow
                    .create_sprite(
                            world_x(state.cursor),
                            world_y(state.cursor) - 23);
    cursor =
            bn::sprite_items::scenario_41_cursor
                    .create_sprite(
                            world_x(state.cursor),
                            world_y(state.cursor) - 24);
    cursor_shadow->set_camera(camera);
    cursor->set_camera(camera);
    cursor_shadow->set_bg_priority(2);
    cursor->set_bg_priority(1);
}

struct battle_unit_visual_sample
{
    std::uint8_t slot = 0;
    std::uint8_t sequence = 0;
    std::uint8_t frame_index = 0;
    int elapsed_frames = 0;
    bool loop = true;
    bool horizontal_flip = false;
    bool explicit_frame = false;
    bool visible = true;
    bool has_screen_anchor = false;
    int screen_anchor_x = 0;
};

[[nodiscard]] battle_unit_visual_sample unit_visual_sample(
        const battle_scene_unit_view& unit,
        const battle_scene_presentation& presentation,
        std::uint32_t scene_frame)
{
    battle_unit_visual_sample result;
    result.sequence =
            battle_unit_visual_animation::idle_sequence(
                    unit.facing);
    result.elapsed_frames =
            static_cast<int>(
                    scene_frame & 0x7FFFFFFFU) +
            battle_unit_visual_animation::idle_phase_offset(
                                unit.id);
    if(! presentation.busy())
    {
        return result;
    }

    const battle_scene_presentation_event& event =
            presentation.event();
    const int frame = presentation.frame();
    if(unit.id == event.actor_id)
    {
        battle_facing facing =
                battle_unit_visual_animation::facing_toward(
                        event.origin,
                        event.destination,
                        unit.facing);
        if(frame < battle_scene_presentation::movement_frame_count)
        {
            if(event.origin != event.destination)
            {
                result.sequence =
                        battle_unit_visual_animation::
                                departure_sequence(facing);
                result.elapsed_frames = frame;
                result.loop = false;
            }
            return result;
        }
        if(! event.has_action)
        {
            return result;
        }

        const battle_combat_presentation& combat =
                presentation.combat();
        if(combat.busy())
        {
            // The original duel stage is faction-stable: player units stay
            // on the left and enemy units stay on the right, regardless of
            // which side initiated combat.
            facing = battle_duel_facing(unit.side);
            const battle_combat_presentation_stage stage =
                    combat.stage();
            const battle_actor_choreography_sample
                    choreography =
                            battle_actor_choreography_for(
                                    event.action_id,
                                    stage,
                                    combat.stage_frame());
            if(choreography.overrides_default)
            {
                result.slot =
                        choreography.visual_slot;
                result.frame_index =
                        choreography.frame_index;
                result.explicit_frame = true;
                result.visible =
                        choreography.visible;
                result.has_screen_anchor = true;
                result.screen_anchor_x =
                        choreography.screen_anchor_x;
                return result;
            }
            if(stage ==
                            battle_combat_presentation_stage::
                                    actor_prep ||
                    stage ==
                            battle_combat_presentation_stage::
                                    action_movie)
            {
                const battle_unit_combat_motion motion =
                        battle_unit_visual_animation::
                                motion_for(
                                        event.ninja_tool,
                                        event.animation_family,
                                        event.targets_opponent);
                const bool facing_left =
                        facing == battle_facing::left;
                const std::uint8_t explicit_left_slot =
                        static_cast<std::uint8_t>(
                                static_cast<std::uint8_t>(
                                        motion) +
                                4);
                const bool explicit_left_available =
                        facing_left &&
                        static_cast<bool>(
                                battle_unit_visual_slot_for(
                                        unit.character_id,
                                        explicit_left_slot));
                const battle_unit_combat_visual visual =
                        battle_unit_visual_animation::combat(
                                motion,
                                facing_left,
                                explicit_left_available);
                result.slot = visual.slot;
                result.sequence = 0;
                result.elapsed_frames =
                        combat.stage_frame();
                result.loop = false;
                result.horizontal_flip =
                        visual.horizontal_flip;
                return result;
            }
            result.sequence =
                    battle_unit_visual_animation::
                            idle_sequence(facing);
            result.elapsed_frames =
                    combat.stage_frame();
            return result;
        }

        const int action_frame =
                frame -
                battle_scene_presentation::movement_frame_count;
        facing =
                battle_unit_visual_animation::facing_toward(
                        event.destination,
                        event.target,
                        facing);
        const battle_action_animation_stage stage =
                battle_action_animation::pose(
                        action_frame,
                        event.destination,
                        event.target,
                        event.actor_lunges,
                        event.impact_count)
                        .stage;
        if(stage == battle_action_animation_stage::returning)
        {
            result.sequence =
                    battle_unit_visual_animation::
                            arrival_sequence(facing);
            result.elapsed_frames =
                    action_frame -
                    battle_action_animation::
                            return_start_frame(
                                    event.impact_count);
            result.loop = false;
            return result;
        }
        if(stage == battle_action_animation_stage::settle)
        {
            result.sequence =
                    battle_unit_visual_animation::idle_sequence(
                            facing);
            result.elapsed_frames =
                    action_frame -
                    battle_action_animation::
                            settle_start_frame(
                                    event.impact_count);
            return result;
        }

        const battle_unit_combat_motion motion =
                battle_unit_visual_animation::motion_for(
                        event.ninja_tool,
                        event.animation_family,
                        event.targets_opponent);
        const bool facing_left =
                facing == battle_facing::left;
        const std::uint8_t explicit_left_slot =
                static_cast<std::uint8_t>(
                        static_cast<std::uint8_t>(motion) + 4);
        const bool explicit_left_available =
                facing_left &&
                static_cast<bool>(
                        battle_unit_visual_slot_for(
                                unit.character_id,
                                explicit_left_slot));
        const battle_unit_combat_visual combat_visual =
                battle_unit_visual_animation::combat(
                        motion,
                        facing_left,
                        explicit_left_available);
        result.slot = combat_visual.slot;
        result.sequence = 0;
        result.elapsed_frames = action_frame;
        result.horizontal_flip =
                combat_visual.horizontal_flip;
        return result;
    }

    if(event.has_action &&
            event.targets_opponent &&
            presentation.affects(unit.id) &&
            frame >=
                    battle_scene_presentation::
                            movement_frame_count)
    {
        const battle_combat_presentation& combat =
                presentation.combat();
        if(combat.busy())
        {
            result.sequence =
                            battle_unit_visual_animation::
                                    idle_sequence(
                                    battle_duel_facing(
                                            unit.side));
            result.elapsed_frames =
                    combat.stage_frame();
            if(combat.stage() ==
                    battle_combat_presentation_stage::
                            impact)
            {
                const battle_facing facing =
                        battle_duel_facing(
                                unit.side);
                const bool facing_left =
                        facing == battle_facing::left;
                const bool explicit_left_available =
                        facing_left &&
                        static_cast<bool>(
                                battle_unit_visual_slot_for(
                                        unit.character_id,
                                        8));
                const battle_unit_combat_visual hit =
                        battle_unit_visual_animation::combat(
                                battle_unit_combat_motion::hit,
                                facing_left,
                                explicit_left_available);
                result.slot = hit.slot;
                result.sequence = 0;
                result.elapsed_frames =
                        combat.stage_frame();
                result.horizontal_flip =
                        hit.horizontal_flip;
            }
            return result;
        }
        const int action_frame =
                frame -
                battle_scene_presentation::movement_frame_count;
        const battle_action_animation_stage stage =
                battle_action_animation::pose(
                        action_frame,
                        event.destination,
                        event.target,
                        event.actor_lunges,
                        event.impact_count)
                        .stage;
        if(stage == battle_action_animation_stage::impact)
        {
            const battle_facing facing =
                    battle_unit_visual_animation::facing_toward(
                            event.target,
                            event.destination,
                            unit.facing);
            const bool facing_left =
                    facing == battle_facing::left;
            const bool explicit_left_available =
                    facing_left &&
                    static_cast<bool>(
                            battle_unit_visual_slot_for(
                                    unit.character_id,
                                    8));
            const battle_unit_combat_visual hit =
                    battle_unit_visual_animation::combat(
                            battle_unit_combat_motion::hit,
                            facing_left,
                            explicit_left_available);
            result.slot = hit.slot;
            result.sequence = 0;
            result.elapsed_frames = action_frame - 24;
            result.horizontal_flip =
                    hit.horizontal_flip;
        }
    }
    return result;
}

void update_battlefield_object_expiry_sprite(
        const battle_scene_presentation& presentation,
        const bn::camera_ptr& camera,
        bn::optional<bn::sprite_ptr>& expiry_sprite)
{
    const bool active =
            presentation.busy() &&
            presentation.event().has_battlefield_object &&
            presentation.event().battlefield_object_kind ==
                    battlefield_object_tick_kind::
                            type_2_expired &&
            presentation.event().
                            battlefield_object_effect_sequence ==
                    7;
    if(! active)
    {
        if(expiry_sprite)
        {
            expiry_sprite->set_visible(false);
        }
        return;
    }

    const int graphics_index =
            bn::min(
                    presentation.frame() /
                            battle_scene_presentation::
                                    battlefield_object_expiry_frame_hold,
                    battle_scene_presentation::
                                    battlefield_object_expiry_graphics_frame_count -
                            1);
    const grid_point target =
            presentation.event().target;
    if(! expiry_sprite)
    {
        expiry_sprite =
                bn::sprite_items::
                        battlefield_object_type_2_expiry
                                .create_sprite(
                                        world_x(target),
                                        world_y(target),
                                        graphics_index);
        expiry_sprite->set_camera(camera);
        expiry_sprite->set_bg_priority(1);
    }
    else
    {
        expiry_sprite->set_tiles(
                bn::sprite_items::
                        battlefield_object_type_2_expiry
                                .tiles_item(),
                graphics_index);
    }
    expiry_sprite->set_position(
            world_x(target), world_y(target));
    expiry_sprite->set_visible(true);
}

// The greyscale palette the original ROM puts on a unit that is not acting.
// It is the ROM's OBJ palette bank 3, read out of the original's palette RAM
// with tools/butano/capture_s49_gpu_state.py, with index 0 replaced by the
// remake's transparent magenta: the original never renders that entry, while
// the remake's unit art uses index 0 for about half of every sprite, so a grey
// there would paint a grey box around every dimmed unit.
[[nodiscard]] const bn::sprite_palette_ptr& dimmed_unit_palette()
{
    static bn::sprite_palette_ptr palette =
            bn::sprite_palette_items::
                    battle_unit_dimmed_palette.create_palette();
    return palette;
}

void update_unit_sprites(
        const battle_scene_snapshot<12>& state,
        const battle_scene_presentation& presentation,
        std::uint32_t scene_frame,
        const bn::camera_ptr& camera,
        std::array<
                battle_unit_sprite_state,
                12>& sprites,
        bool force_rebind = false,
        const battle_map_movement* movement = nullptr,
        bool dim_inactive_units = false)
{
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        const battle_scene_unit_view& unit =
                state.units[index];
        battle_unit_sprite_state& sprite_state =
                sprites[index];
        const battle_combat_presentation& combat =
                presentation.combat();
        const bool combat_actor =
                combat.busy() &&
                unit.id == presentation.event().actor_id;
        const bool combat_target =
                combat.busy() &&
                presentation.affects(unit.id);
        const bool combat_stage =
                combat.busy() &&
                ! combat.map_visible();
        const bool combat_unit_visible =
                (combat_actor &&
                 combat.actor_visible()) ||
                (combat_target &&
                 combat.target_visible());
        if(combat_stage && ! combat_unit_visible)
        {
            sprite_state.reset();
            continue;
        }
        const bool presentation_target =
                presentation.busy() &&
                presentation.event().has_action &&
                presentation.affects(unit.id);
        if(! unit.active && ! presentation_target)
        {
            sprite_state.reset();
            continue;
        }
        std::uint8_t visual_character_id =
                unit.character_id;
        if(visual_character_id == 0 &&
                presentation_target)
        {
            const battle_scene_presentation_event& event =
                    presentation.event();
            for(int affected_index = 0;
                    affected_index <
                            event.affected_unit_count;
                    ++affected_index)
            {
                const std::size_t affected_offset =
                        static_cast<std::size_t>(
                                affected_index);
                if(event.affected_unit_ids[
                           affected_offset] == unit.id)
                {
                    visual_character_id =
                            event.affected_character_ids[
                                    affected_offset];
                    break;
                }
            }
        }
        battle_scene_unit_view visual_unit = unit;
        visual_unit.character_id =
                visual_character_id;
        const grid_point map_visual_position =
                battle_map_visual_position(
                        state, unit);
        visual_unit.position =
                map_visual_position;
        visual_unit.facing =
                battle_map_visual_facing(
                        state, unit);
        battle_unit_visual_sample sample = unit_visual_sample(
                visual_unit, presentation, scene_frame);
        const battle_map_movement_sample movement_pose = movement ?
                movement->sample(unit.id) : battle_map_movement_sample{};
        if(movement_pose.moving && ! presentation.busy())
        {
            sample.sequence = movement_pose.sequence;
            sample.elapsed_frames = movement_pose.elapsed_frames;
            sample.loop = false;
        }
        const battle_unit_visual_slot visual =
                battle_unit_visual_slot_for(
                        visual_character_id,
                        sample.slot);
        BN_ASSERT(
                visual,
                "Missing battle unit visual: ",
                visual_character_id,
                " slot ",
                sample.slot);
        const std::uint8_t sequence_index =
                sample.sequence < visual.sequence_count ?
                        sample.sequence :
                        0;
        const battle_unit_visual_sequence& sequence =
                visual.sequences[sequence_index];
        const std::uint8_t frame_index =
                sample.explicit_frame ?
                        sample.frame_index :
                        battle_unit_visual_animation::frame_at(
                                visual.steps +
                                        sequence.first_step,
                                sequence.step_count,
                                sample.elapsed_frames,
                                sample.loop);
        BN_ASSERT(
                frame_index < visual.frame_count,
                "Invalid battle unit frame: ",
                frame_index);
        const battle_unit_visual_frame& frame =
                visual.frames[frame_index];
        const bool binding_changed =
                force_rebind ||
                sprite_state.character_id !=
                        visual_character_id ||
                sprite_state.visual_slot != sample.slot;
        // The selected unit keeps the unit art's own palette.  The original
        // never paints a cyan outline on it: the 25 frames of the original
        // S49 walk contain zero pixels of the outline colour, and the one
        // place the original does show it is the battle entry, where it is
        // already gone four frames later.
        const bool acting_unit =
                ! combat_stage &&
                state.selected_unit == unit.id;
        const battle_scene_unit_pose scene_pose =
                presentation.pose(
                        unit.id, map_visual_position);        const int default_combat_x =
                combat.single_actor_stage() &&
                        combat_actor ?
                        36 :
                        battle_duel_screen_x(unit.side);

        for(int component_index = 0;
                component_index <
                        battle_unit_visual_max_components;
                ++component_index)
        {
            bn::optional<bn::sprite_ptr>& sprite =
                    sprite_state.components[
                            static_cast<std::size_t>(
                                    component_index)];
            const battle_unit_visual_component_pose&
                    component_pose =
                            frame.components[component_index];
            if(! component_pose.visible)
            {
                if(sprite)
                {
                    sprite->set_visible(false);
                }
                continue;
            }
            BN_ASSERT(
                    component_pose.asset_index <
                            visual.asset_count,
                    "Invalid battle unit asset: ",
                    component_pose.asset_index);
            const bn::sprite_item* item =
                    visual.component_items[
                            component_pose.asset_index];
            BN_ASSERT(item, "Missing component item");
            const int graphics_index =
                    component_pose.graphics_index;
            constexpr int combat_sprite_scale = 1;
            const int component_x =
                    sample.horizontal_flip ?
                            -component_pose.center_offset_x :
                            component_pose.center_offset_x;
            const int base_x =
                    combat_stage ?
                            camera.x().integer() +
                                    (combat_actor &&
                                     sample.
                                             has_screen_anchor ?
                             sample.screen_anchor_x -
                                     screen_width /
                                             2 :
                             default_combat_x) :
                    world_x(map_visual_position);
            const int base_y =
                    combat_stage ?
                            camera.y().integer() + 8 :
                            world_y(map_visual_position);
            const int x =
                    base_x +
                    component_x *
                            combat_sprite_scale +
                    scene_pose.offset_x + movement_pose.offset_x;
            const int y =
                    base_y +
                    component_pose.center_offset_y *
                            combat_sprite_scale +
                    scene_pose.offset_y + movement_pose.offset_y;
            if(! sprite)
            {
                sprite = item->create_sprite(
                        x, y, graphics_index);
                sprite->set_camera(camera);
                sprite->set_bg_priority(2);
            }
            else if(binding_changed ||
                    sprite_state.asset_indices[
                            static_cast<std::size_t>(
                                    component_index)] !=
                            component_pose.asset_index)
            {
                sprite->set_item(*item, graphics_index);
            }
            else if(sprite_state.frame_index !=
                    frame_index)
            {
                sprite->set_tiles(
                        item->tiles_item(),
                        graphics_index);
            }
            // S49 original frame 18: the unit that is not acting is drawn with
            // a greyscale OBJ palette (the ROM's palette bank 3, which is the
            // index-for-index twin of the unit's own colour bank).  The
            // dimmed palette is a shared item, so it is created once per
            // scene rather than per unit.
            // The original keeps every unit in colour while the player is
            // choosing where to move one (S49 frame 16), and greyscales the
            // inactive ones only once the unit has taken its action phase
            // (frames 17, 18, 20).  The remake runs the move grid inside the
            // command-menu layer, so the phase is what separates the two.
            const bool dimmed =
                    dim_inactive_units &&
                    ! acting_unit &&
                    state.phase != battle_scene_phase::unit_selection &&
                    state.phase != battle_scene_phase::move_selection;
            if(dimmed)
            {
                sprite->set_palette(
                        dimmed_unit_palette());
            }
            else if(binding_changed)
            {
                sprite->set_palette(
                        item->palette_item());
            }
            sprite->set_position(x, y);
            sprite->set_z_order(
                    combat_stage ?
                            0 :
                            battle_map_unit_z_order(
                                    map_visual_position));
            sprite->set_scale(
                    combat_sprite_scale);
            sprite->set_remove_affine_mat_when_not_needed(
                    true);
            sprite->set_horizontal_flip(
                    sample.horizontal_flip);
            sprite->set_visible(
                    scene_pose.visible &&
                    sample.visible &&
                    component_pose.visible);
            sprite_state.asset_indices[
                    static_cast<std::size_t>(
                            component_index)] =
                    component_pose.asset_index;
        }
        sprite_state.character_id = visual_character_id;
        sprite_state.visual_slot = sample.slot;
        sprite_state.frame_index = frame_index;
    }
}

void capture_deployment_telemetry(
        const battle_deployment_flow& deployment,
        const battle_runtime_scene_config& config,
        std::uint32_t scene_frame,
        const battle_background_stream& background)
{
    volatile battle_runtime_scene_telemetry& output =
            konoha_battle_runtime_telemetry;
    const battle_deployment_entry* entry =
            deployment.current_entry();
    output.magic = 0;
    output.battle_id =
            static_cast<std::uint32_t>(config.battle_id);
    output.phase =
            deployment.phase() ==
                            battle_deployment_phase::
                                    unit_confirmation ?
                    battle_runtime_scene_telemetry::
                            deployment_unit_phase_value :
                    battle_runtime_scene_telemetry::
                            deployment_start_phase_value;
    output.round = 0;
    output.current_side = entry ?
            static_cast<std::uint32_t>(entry->side) :
            0;
    output.selected_unit = entry ?
            static_cast<std::uint32_t>(
                    entry->record_id + 1) :
            0;
    output.active_unit_count =
            static_cast<std::uint32_t>(
                    deployment.entry_count());
    output.unit_count = output.active_unit_count;
    output.selected_command = 0;
    output.player_completed = 0;
    output.enemy_completed = 0;
    output.scene_frame = scene_frame;
    output.cursor_x = entry ?
            static_cast<std::uint32_t>(
                    entry->position.x) :
            0;
    output.cursor_y = entry ?
            static_cast<std::uint32_t>(
                    entry->position.y) :
            0;
    output.last_control_error = 0;
    output.last_player_error = 0;
    output.render_stage = 0;
    output.presentation_busy = 0;
    output.selected_character_id = entry ?
            static_cast<std::uint32_t>(
                    entry->character_id) :
            0xFFFFFFFFU;
    output.action_count = 0;
    output.action_index = 0;
    output.selected_action_id = no_ability;
    output.selected_action_error = 0;
    output.last_resolved_action_id = no_ability;
    output.background_chunk_index =
            static_cast<std::uint32_t>(
                    background.chunk_index());
    output.background_chunk_count =
            static_cast<std::uint32_t>(
                    background.chunk_count());
    output.script_phase = 0;
    output.script_selector = 0;
    output.script_command_index = 0;
    output.script_text_address = 0;
    output.script_message_window_visible = 0;
    output.script_portrait_0_visible = 0;
    output.script_portrait_0_focused = 0;
    output.script_portrait_0_id = 0;
    output.script_portrait_0_expression = 0;
    output.script_portrait_0_motion = 0;
    output.script_portrait_1_visible = 0;
    output.script_portrait_1_focused = 0;
    output.script_portrait_1_id = 0;
    output.script_portrait_1_expression = 0;
    output.script_portrait_1_motion = 0;
    output.presentation_resource_resolved = 0;
    output.presentation_resource_type = 0;
    output.presentation_resource_amount = 0;
    output.presentation_resource_hp_delta = 0;
    output.presentation_resource_chakra_delta = 0;
    output.ai_secondary_planned = 0;
    output.ai_defense_kind = 0;
    output.ai_defense_action_id = no_ability;
    output.ai_defense_tool_slot = no_tool_slot;
    output.ai_defense_score = 0;
    output.battlefield_object_count = 0;
    output.presentation_battlefield_object = 0;
    output.presentation_battlefield_object_kind = 0;
    output.presentation_battlefield_object_slot = 0;
    output.presentation_battlefield_object_damage = 0;
    output.presentation_combat_schema_version = 1;
    output.presentation_combat_stage =
            static_cast<std::uint32_t>(
                    battle_combat_presentation_stage::
                            complete);
    output.presentation_combat_stage_frame = 0;
    output.presentation_combat_impact_index =
            0xFFFFFFFFU;
    output.presentation_combat_tracks = 0;
    output.presentation_combat_resource = 0;
    output.selected_unit_hp = 0xFFFFFFFFU;
    output.selected_unit_max_hp = 0xFFFFFFFFU;
    output.magic =
            battle_runtime_scene_telemetry::magic_value;
}

void render_deployment_text(
        const battle_deployment_flow& deployment,
        const battle_runtime_scene_config& config,
        bn::sprite_text_generator& generator,
        bn::vector<
                bn::sprite_ptr,
                battle_runtime_scene_sprite_budget::
                        maximum_text_sprites>& sprites)
{
    sprites.clear();
    generator.set_left_alignment();

    bn::string<48> header = config.title;
    header += " DEPLOY";
    generator.generate(-116, -72, header, sprites);

    bn::string<48> progress;
    const battle_deployment_entry* entry =
            deployment.current_entry();
    if(entry)
    {
        progress = "UNIT ";
        progress += bn::to_string<4>(
                entry->record_id + 1);
        progress += "/";
        progress += bn::to_string<4>(
                static_cast<int>(
                        deployment.entry_count()));
    }
    else
    {
        progress = "START";
    }
    generator.generate(-116, -60, progress, sprites);

    bn::string<96> detail;
    if(entry)
    {
        const battle_identity_record* identity =
                battle_unit_identity(
                        entry->character_id);
        if(identity)
        {
            detail = identity->display_name;
            if(! identity->exact)
            {
                detail += "?";
            }
        }
        else
        {
            detail = "CHAR #";
            detail += bn::to_string<4>(
                    entry->character_id);
        }
        detail += entry->side ==
                          battle_side::player ?
                " PLAYER" : " ENEMY";
    }
    else
    {
        detail = "READY";
    }
    generator.generate(-116, 48, detail, sprites);
    generator.generate(
            -116, 64, "A:OK B:BACK", sprites);
}

enum class deployment_scene_result : std::uint8_t
{
    complete,
    back,
};

void wait_for_deployment_release(
        const battle_deployment_flow& deployment,
        const battle_runtime_scene_config& config,
        std::uint32_t& scene_frame,
        const battle_background_stream& background)
{
    while(bn::keypad::a_held() ||
            bn::keypad::b_held())
    {
        ++scene_frame;
        capture_deployment_telemetry(
                deployment,
                config,
                scene_frame,
                background);
        bn::core::update();
    }
    // Give the next controller one neutral frame so the deployment
    // confirmation edge cannot become its first command.
    ++scene_frame;
    capture_deployment_telemetry(
            deployment,
            config,
            scene_frame,
            background);
    bn::core::update();
}

[[nodiscard]] deployment_scene_result
run_deployment_confirmation(
        battle_deployment_flow& deployment,
        const battle_runtime_scene_config& config)
{
    const battle_deployment_entry* first =
            deployment.current_entry();
    if(! first)
    {
        return deployment_scene_result::back;
    }

    battle_background_stream background;
    if(! prepare_background_stream(
               config, background))
    {
        return deployment_scene_result::back;
    }
    const int first_camera_x =
            camera_x(first->position, config);
    (void) background.update(
            first_camera_x + map_center_x);
    bn::camera_ptr camera = bn::camera_ptr::create(
            first_camera_x,
            camera_y(first->position, config));
    bn::regular_bg_ptr map =
            config.map_items[
                    background.chunk_index()]
                    ->create_bg(
                            background.chunk_origin(),
                            0);
    map.set_priority(3);
    map.set_camera(camera);

    battle_scene_snapshot<12> deployment_state;
    deployment_state.unit_count =
            deployment.entry_count();
    for(int index = 0;
            index <
                    static_cast<int>(
                            deployment.entry_count());
            ++index)
    {
        const battle_deployment_entry& unit =
                *deployment.entry(index);
        battle_scene_unit_view& view =
                deployment_state.units[
                        static_cast<std::size_t>(index)];
        view.id = static_cast<battle_unit_id>(
                unit.record_id + 1);
        view.character_id = unit.character_id;
        view.side = unit.side;
        view.position = unit.position;
        view.facing = unit.facing;
        view.active = true;
        ++deployment_state.active_unit_count;
    }
    std::array<battle_unit_sprite_state, 12>
            unit_sprites;
    battle_scene_presentation idle_presentation;
    std::uint32_t scene_frame = 0;
    update_unit_sprites(
            deployment_state,
            idle_presentation,
            scene_frame,
            camera,
            unit_sprites);

    bn::sprite_ptr cursor_shadow =
            bn::sprite_items::
                    scenario_41_cursor_shadow
                            .create_sprite(
                                    world_x(first->position),
                                    world_y(first->position) -
                                            23);
    bn::sprite_ptr cursor =
            bn::sprite_items::scenario_41_cursor
                    .create_sprite(
                            world_x(first->position),
                            world_y(first->position) - 24);
    cursor_shadow.set_camera(camera);
    cursor.set_camera(camera);
    cursor_shadow.set_bg_priority(2);
    cursor.set_bg_priority(1);

    bn::sprite_text_generator text_generator(
            battle_ui_sprite_font);
    text_generator.set_bg_priority(0);
    bn::vector<
            bn::sprite_ptr,
            battle_runtime_scene_sprite_budget::
                    maximum_text_sprites> text_sprites;
    render_deployment_text(
            deployment,
            config,
            text_generator,
            text_sprites);

    grid_point focus = first->position;
    capture_deployment_telemetry(
            deployment,
            config,
            scene_frame,
            background);
    while(true)
    {
        if(bn::keypad::start_pressed())
        {
            return deployment_scene_result::back;
        }

        bool handled = false;
        if(bn::keypad::a_pressed())
        {
            (void) deployment.confirm();
            handled = true;
        }
        else if(bn::keypad::b_pressed())
        {
            (void) deployment.cancel();
            handled = true;
        }

        if(deployment.cancelled())
        {
            return deployment_scene_result::back;
        }
        if(deployment.complete())
        {
            wait_for_deployment_release(
                    deployment,
                    config,
                    scene_frame,
                    background);
            return deployment_scene_result::complete;
        }
        if(handled)
        {
            if(const battle_deployment_entry* entry =
                            deployment.current_entry())
            {
                focus = entry->position;
                cursor.set_position(
                        world_x(focus),
                        world_y(focus) - 24);
                cursor_shadow.set_position(
                        world_x(focus),
                        world_y(focus) - 23);
                cursor.set_visible(true);
                cursor_shadow.set_visible(true);
            }
            else
            {
                cursor.set_visible(false);
                cursor_shadow.set_visible(false);
            }
            const int next_camera_x =
                    camera_x(focus, config);
            camera.set_x(next_camera_x);
            camera.set_y(camera_y(focus, config));
            update_background_stream(
                    next_camera_x,
                    config,
                    background,
                    map);
            render_deployment_text(
                    deployment,
                    config,
                    text_generator,
                    text_sprites);
        }

        ++scene_frame;
        update_unit_sprites(
                deployment_state,
                idle_presentation,
                scene_frame,
                camera,
                unit_sprites);
        capture_deployment_telemetry(
                deployment,
                config,
                scene_frame,
                background);
        bn::core::update();
    }
}

[[nodiscard]] battle_runtime_scene_exit
run_visible_battle_scene(
        const battle_runtime_scene_config& base_config)
{
    BN_DATA_EWRAM static
            battle_runtime_scene_config config;
    config = base_config;
    const battle_content_entry content =
            generated_battle_content_entry(
                    config.battle_id,
                    config.variant);
    const battle_background_content_entry*
            background_content =
                    generated_battle_background_entry(
                            config.battle_id);
    const bool config_valid =
            content.valid() &&
            content.kind !=
                    battle_content_entry_kind::empty &&
            background_content &&
            background_content->valid() &&
            background_content->battle_id ==
                    config.battle_id;
    if(! config_valid)
    {
        return battle_runtime_scene_exit::aborted;
    }

    const battle_scenario_definition& scenario =
            *content.scenario;
    const battle_map_definition& map_definition =
            *content.map;
    if(scenario.grid_width != map_definition.width ||
            scenario.grid_height !=
                    map_definition.height ||
            background_content->pixel_width !=
                    scenario.grid_width * cell_width ||
            background_content->pixel_height !=
                    scenario.grid_height * cell_height ||
            map_definition.width >
                    battle_runtime_grid_width ||
            map_definition.height >
                    battle_runtime_grid_height)
    {
        return battle_runtime_scene_exit::aborted;
    }
    config.map_pixel_width =
            background_content->pixel_width;
    config.map_pixel_height =
            background_content->pixel_height;
    config.map_items = background_content->items;
    config.map_chunk_origins =
            background_content->origins;
    config.map_chunk_count =
            background_content->chunk_count;

    BN_DATA_EWRAM static
            std::array<battle_unit_sprite_state, 12>
                    unit_sprites;
    BN_DATA_EWRAM_BSS static
            bn::optional<bn::sprite_ptr>
                    battlefield_object_expiry_sprite;
    BN_DATA_EWRAM_BSS static
            bn::vector<
            bn::sprite_ptr,
            battle_runtime_scene_sprite_budget::
                    maximum_text_sprites> text_sprites;
    BN_DATA_EWRAM_BSS static
            bn::vector<bn::sprite_ptr, 64>
                    script_glyph_sprites;
    unit_sprites = {};
    battlefield_object_expiry_sprite = bn::nullopt;
    text_sprites.clear();
    script_glyph_sprites.clear();
    // These caches live in EWRAM to keep the visible-scene stack safe,
    // so returning from the previous battle does not destroy their sprite
    // handles. Release them before the next deployment allocates its own
    // units and text, then let Butano reclaim the freed VRAM blocks.
    bn::core::update();

    BN_DATA_EWRAM static
            battle_deployment_flow deployment;
    deployment = {};
    const battle_audio_director audio_director;
    dispatch_battle_audio(
            audio_director,
            battle_audio_event::preparation_opened);
    if(! deployment.prepare(
                    scenario,
                    static_cast<std::uint8_t>(
                            config.variant),
                    config.load_policy).success() ||
            run_deployment_confirmation(
                    deployment, config) !=
                    deployment_scene_result::complete)
    {
        return battle_runtime_scene_exit::aborted;
    }
    BN_DATA_EWRAM_BSS static
            battle_runtime_controller controller;
    if(! controller.load(
               scenario,
               map_definition,
               battle_map_cells,
               static_cast<std::uint8_t>(config.variant),
               config.load_policy,
               *content.conditions,
               config.rng_seed,
               config.progression_roster,
               true,
               battle_mission_rules_for(
                       config.battle_id,
                       config.variant), config.initial_inventory).success())
    {
        return battle_runtime_scene_exit::aborted;
    }
    if(! controller.start().success())
    {
        return battle_runtime_scene_exit::aborted;
    }
    dispatch_battle_audio(
            audio_director,
            battle_audio_event::battle_opened);
    const auto finish_scene =
            [&](battle_runtime_scene_exit exit)
    {
        if(config.materials_output)
        {
            *config.materials_output = controller.inventory().materials;
        }
        if(config.progression_output)
        {
            *config.progression_output =
                    controller.progression_roster();
        }
        if(config.equipped_tools_output)
        {
            *config.equipped_tools_output =
                    controller.equipped_tools_roster();
        }
        return exit;
    };

    BN_DATA_EWRAM static
            battle_scene_snapshot<12> state;
    state = controller.snapshot();
    battle_map_movement map_movement;
    map_movement.observe(state);
    const grid_point initial_camera_focus =
            state.phase ==
                    battle_scene_phase::script_blocked ?
                    grid_point{} :
                    state.cursor;
    BN_DATA_EWRAM static
            battle_training_snapshot
                    training_state;
    training_state = controller.training_snapshot();
    BN_DATA_EWRAM static
            battle_scene_object_snapshot object_state;
    object_state = controller.object_snapshot();
    battle_background_stream background;
    if(! prepare_background_stream(
               config, background))
    {
        return finish_scene(
                battle_runtime_scene_exit::aborted);
    }
    const int initial_camera_x =
            camera_x(initial_camera_focus, config);
    (void) background.update(
            initial_camera_x + map_center_x);
    BN_DATA_EWRAM_BSS static
            std::uint32_t scene_frame;
    scene_frame = 0;
    BN_DATA_EWRAM_BSS static
            std::uint32_t last_control_error;
    last_control_error = 0;
    BN_DATA_EWRAM_BSS static
            std::uint32_t last_player_error;
    last_player_error = 0;
    BN_DATA_EWRAM_BSS static
            std::uint32_t last_resolved_action_id;
    last_resolved_action_id = no_ability;
    BN_DATA_EWRAM static
            battle_ai_secondary_command
                    last_ai_secondary;
    last_ai_secondary = {};
    BN_DATA_EWRAM static
            battlefield_object_telemetry_latch
                    object_telemetry;
    object_telemetry = {};
    capture_telemetry(
            state,
            training_state,
            controller.result_snapshot(),
            config,
            scene_frame,
            last_control_error,
            last_player_error,
            last_resolved_action_id,
            last_ai_secondary,
            false,
            nullptr,
            nullptr,
            object_state,
            object_telemetry,
            background);
    bn::camera_ptr camera = bn::camera_ptr::create(
            initial_camera_x,
            camera_y(initial_camera_focus, config));
    bn::optional<bn::regular_bg_ptr> map =
            config.map_items[
                    background.chunk_index()]
                    ->create_bg(
                            background.chunk_origin(),
                            0);
    map->set_priority(3);
    map->set_camera(camera);
    konoha_battle_runtime_telemetry.render_stage = 100;
    // Butano reclaims released sprite tile blocks during the
    // next core update. Commit the previous scene teardown
    // before allocating the new cursor and portraits.
    bn::core::update();
    BN_DATA_EWRAM_BSS alignas(4) static
            std::array<
                    std::uint8_t,
                    battle_presentation_portrait_bytes>
                    portrait_scratch;
    battle_presentation_portrait_runtime_renderer
            portrait_renderer;
    battle_presentation_message_window_runtime_renderer
            message_window_renderer;
    battle_dialogue_background_runtime_renderer
            dialogue_background_renderer;
    battle_combat_stage_runtime_renderer
            combat_stage_renderer;
    bn::optional<bn::sprite_ptr> cursor_shadow;
    bn::optional<bn::sprite_ptr> cursor;
    bn::vector<bn::sprite_ptr, 2> map_scenery_sprite;
    konoha_battle_runtime_telemetry.render_stage = 101;
    bn::sprite_text_generator text_generator(
            battle_ui_sprite_font);
    text_generator.set_bg_priority(0);
    bn::sprite_text_generator action_menu_text_generator(
            battle_action_menu_sprite_font);
    action_menu_text_generator.set_bg_priority(0);
    bn::sprite_text_generator duel_status_text_generator(
            battle_duel_status_sprite_font);
    duel_status_text_generator.set_bg_priority(0);
    bn::sprite_text_generator story_text_generator(
            battle_preparation_sprite_font);
    story_text_generator.set_bg_priority(0);
    bn::sprite_text_generator target_status_text_generator(
            battle_target_status_sprite_font);
    target_status_text_generator.set_bg_priority(0);
    bn::sprite_text_generator target_metrics_text_generator(
            battle_target_metrics_sprite_font);
    target_metrics_text_generator.set_bg_priority(0);
    bn::sprite_text_generator result_text_generator(
            battle_result_sprite_font);
    result_text_generator.set_bg_priority(0);
    bn::sprite_text_generator result_compact_text_generator(
            battle_result_compact_sprite_font);
    result_compact_text_generator.set_bg_priority(0);
    battle_ui_rejection_latch rejection;
    int automatic_frames = 0;
    battle_combat_presentation_stage observed_combat_stage =
            battle_combat_presentation_stage::complete;
    battle_scene_phase observed_audio_phase =
            state.phase;
    bool presentation_special_combination = false;
    BN_DATA_EWRAM static
            battle_scene_presentation presentation;
    presentation = {};
    BN_DATA_EWRAM static
            battle_ui_runtime_renderer ui_renderer;
    ui_renderer.reset();
    BN_DATA_EWRAM static battle_range_overlay
            range_overlay;
    range_overlay.reset();
    battle_ui_model initial_ui_model =
            make_battle_ui_model(
                    state, presentation.busy());
    battle_ui_layer observed_ui_layer =
            initial_ui_model.layer;
    battle_visual_resource_coordinator
            resource_coordinator;
    grid_point camera_focus = initial_camera_focus;
    BN_DATA_EWRAM static
            battle_scene_control_result result;
    const bool initial_dialogue_background_requested =
            config.battle_id == 14 &&
            state.phase ==
                    battle_scene_phase::script_blocked &&
            state.script.selector == 1 &&
            ! presentation.busy();
    const battle_visual_resource_transition
            initial_resource_transition =
                    resource_coordinator.transition_to(
                            select_battle_visual_resource_cohort(
                                    state.phase ==
                                            battle_scene_phase::
                                                    script_blocked &&
                                            ! presentation.busy(),
                                    presentation.combat()
                                            .title_visible()));
    apply_visual_resource_transition(
            initial_resource_transition,
            unit_sprites,
            map_scenery_sprite,
            cursor_shadow,
            cursor,
            battlefield_object_expiry_sprite,
            text_sprites,
            script_glyph_sprites,
            ui_renderer,
            portrait_renderer,
            message_window_renderer,
            dialogue_background_renderer,
            combat_stage_renderer);
    dialogue_background_renderer.update(
            initial_dialogue_background_requested,
            map);
    if(resource_coordinator.current() ==
            battle_visual_resource_cohort::map)
    {
        ensure_battle_map_background(
                config,
                background,
                camera,
                map);
        ensure_map_scenery(
                config,
                camera,
                object_state,
                map_scenery_sprite);
        ensure_map_cursor(
                state,
                camera,
                cursor_shadow,
                cursor);
    }
    ui_renderer.update(
            initial_ui_model,
            state,
            controller.result_snapshot(),
            presentation);
    render_battle_ui_text(
            initial_ui_model,
            state,
            training_state,
            controller.result_snapshot(),
            config,
            false,
            presentation,
            text_generator,
            action_menu_text_generator,
            duel_status_text_generator,
            target_status_text_generator,
            target_metrics_text_generator,
            result_text_generator,
            result_compact_text_generator,
            text_sprites);
    konoha_battle_runtime_telemetry.render_stage = 102;
    render_script_glyphs(
            state,
            story_text_generator,
            script_glyph_sprites);
    konoha_battle_runtime_telemetry.render_stage = 103;
    update_script_message_window(
            state,
            presentation.busy(),
            message_window_renderer);
    konoha_battle_runtime_telemetry.render_stage = 104;
    if(! update_combat_portrait(
               state,
               presentation,
               portrait_renderer,
               portrait_scratch))
    {
        update_script_portraits(
                state,
                presentation.busy(),
                portrait_renderer,
                portrait_scratch);
    }
    combat_stage_renderer.update(
            state,
            presentation,
            map,
            *config.map_items[
                    background.chunk_index()],
            background.chunk_origin(),
            camera);
    konoha_battle_runtime_telemetry.render_stage = 105;
    if(state.phase !=
            battle_scene_phase::script_blocked)
    {
        update_unit_sprites(
                state,
                presentation,
                scene_frame,
                camera,
                unit_sprites, false, &map_movement,
                initial_ui_model.layer ==
                        battle_ui_layer::command_menu ||
                initial_ui_model.layer ==
                        battle_ui_layer::action_menu);
        update_battlefield_object_expiry_sprite(
                presentation,
                camera,
                battlefield_object_expiry_sprite);
    }
    else
    {
        if(cursor)
        {
            cursor->set_visible(false);
        }
        if(cursor_shadow)
        {
            cursor_shadow->set_visible(false);
        }
    }

    bn::vector<bn::sprite_ptr, 8> pickup_text_sprites;
    std::uint32_t observed_pickup = 0;
    int pickup_text_frames = 0;
    // The stable 44-frame cycle is measured; entry/menu stall phase is still
    // being compared. Keep this map clock independent of combat/UI scene time.
    int destination_cursor_phase = 16;
    const bool original_destination_cursor =
            config.battle_id == 14 && config.variant == 0;
    bool script_confirmation_latched =
            bn::keypad::a_held();
    while(true)
    {
        if(! bn::keypad::a_held())
        {
            script_confirmation_latched = false;
        }
        const bool map_controls_enabled =
                ! presentation.busy() && ! map_movement.busy() &&
                presentation.combat().
                        map_controls_enabled();
        const bool map_movement_frame = map_movement.busy();
        if(map_controls_enabled &&
                bn::keypad::start_pressed())
        {
            return finish_scene(
                    battle_runtime_scene_exit::aborted);
        }

        result = {};
        bool handled = false;
        bool audio_input = false;
        bool action_confirmation_input = false;
        battle_audio_event input_audio_event =
                battle_audio_event::ui_navigated;
        bool rejection_changed = false;
        const bool presentation_frame =
                presentation.busy();
        const bool script_waiting_for_input =
                ! presentation_frame &&
                state.phase ==
                        battle_scene_phase::
                                script_blocked &&
                state.script.phase ==
                        battle_presentation_script_phase::
                                wait_for_input;
        const battle_scene_presentation_event
                presentation_event =
                        ! presentation_frame &&
                        ! script_waiting_for_input ?
                                controller
                                        .take_presentation_event() :
                                battle_scene_presentation_event{};
        if(script_waiting_for_input)
        {
            // Script input has priority over queued map
            // presentation events.  Otherwise a dialogue can keep
            // reporting wait_for_input while its confirmation is
            // starved by a presentation queued on the same boundary.
            if(! script_confirmation_latched &&
                    bn::keypad::a_held())
            {
                script_confirmation_latched = true;
                result = controller.confirm();
                handled = true;
                audio_input = true;
                input_audio_event =
                        battle_audio_event::ui_confirmed;
            }
        }
        else if(presentation_frame)
        {
            presentation.advance();
        }
        else if(map_movement.busy())
        {
            map_movement.advance();
        }
        else if(presentation_event.valid)
        {
            camera_focus = presentation_event.origin;
            const bool presentation_started =
                    presentation.begin(
                            presentation_event);
            if(presentation_started)
            {
                presentation_special_combination =
                        presentation_event
                                .special_combination;
            }
            if(presentation_started &&
                    presentation_event
                            .has_battlefield_object)
            {
                object_telemetry.presented = true;
                object_telemetry.kind =
                        presentation_event
                                .battlefield_object_kind;
                object_telemetry.slot =
                        presentation_event
                                .battlefield_object_slot;
                object_telemetry.damage =
                        presentation_event
                                .battlefield_object_damage;
            }
            if(presentation_event.action_id !=
                    no_ability)
            {
                last_resolved_action_id =
                        presentation_event.action_id;
            }
        }
        else if(state.phase ==
                        battle_scene_phase::
                                script_blocked &&
                state.script.phase ==
                        battle_presentation_script_phase::
                                wait_frames)
        {
            result = controller.tick();
            handled = true;
        }
        else if(state.phase ==
                battle_scene_phase::enemy_turn)
        {
            ++automatic_frames;
            if(automatic_frames >= 15)
            {
                result = controller.tick();
                automatic_frames = 0;
                handled = true;
            }
        }
        else if(presentation.combat().
                        map_controls_enabled())
        {
            automatic_frames = 0;
            if(bn::keypad::l_pressed())
            {
                result = controller.cycle_unit(-1);
                handled = true;
                audio_input = true;
                input_audio_event =
                        battle_audio_event::ui_navigated;
            }
            else if(bn::keypad::r_pressed())
            {
                result = controller.cycle_unit(1);
                handled = true;
                audio_input = true;
                input_audio_event =
                        battle_audio_event::ui_navigated;
            }
            else if(bn::keypad::a_pressed())
            {
                script_confirmation_latched = true;
                action_confirmation_input =
                        state.phase ==
                                battle_scene_phase::
                                        target_confirmation;
                result = controller.confirm();
                handled = true;
                audio_input = true;
                input_audio_event =
                        battle_audio_event::ui_confirmed;
            }
            else if(bn::keypad::b_pressed())
            {
                result = controller.cancel();
                handled = true;
                audio_input = true;
                input_audio_event =
                        battle_audio_event::ui_cancelled;
            }
            else if(bn::keypad::left_pressed())
            {
                result = controller.move_cursor(-1, 0);
                handled = true;
                audio_input = true;
                input_audio_event =
                        battle_audio_event::ui_navigated;
            }
            else if(bn::keypad::right_pressed())
            {
                result = controller.move_cursor(1, 0);
                handled = true;
                audio_input = true;
                input_audio_event =
                        battle_audio_event::ui_navigated;
            }
            else if(bn::keypad::up_pressed())
            {
                result = controller.move_cursor(0, -1);
                handled = true;
                audio_input = true;
                input_audio_event =
                        battle_audio_event::ui_navigated;
            }
            else if(bn::keypad::down_pressed())
            {
                result = controller.move_cursor(0, 1);
                handled = true;
                audio_input = true;
                input_audio_event =
                        battle_audio_event::ui_navigated;
            }
        }

        if(handled)
        {
            last_control_error =
                    static_cast<std::uint32_t>(
                            result.error);
            last_player_error =
                    static_cast<std::uint32_t>(
                            result.player.error);
            if(result.success() &&
                    result.ai.secondary_planned)
            {
                last_ai_secondary = {
                    result.ai.secondary_planned,
                    result.ai.defense_kind,
                    result.ai.defense_action_id,
                    result.ai.defense_tool_slot,
                    result.ai.defense_score,
                };
            }
        }
        if(audio_input)
        {
            if(result.success())
            {
                dispatch_battle_audio(
                        audio_director,
                        input_audio_event);
                if(action_confirmation_input)
                {
                    dispatch_battle_audio(
                            audio_director,
                            battle_audio_event::
                                    action_confirmed);
                }
            }
            else
            {
                dispatch_battle_audio(
                        audio_director,
                        battle_audio_event::
                                input_rejected);
            }
        }
        rejection_changed =
                rejection.update(
                        handled, result.success());
        state = controller.snapshot();
        object_state = controller.object_snapshot();
        map_movement.observe(state);
        if(state.phase == battle_scene_phase::complete)
        {
            pickup_text_sprites.clear();
            pickup_text_frames = 0;
            // The controller keeps a terminal phase so campaign write-back
            // remains transactional, but it is not a player-facing page.
            // The original flow leaves the result/growth sequence directly
            // for the task menu.
            range_overlay.reset();
            for(battle_unit_sprite_state& unit_sprite :
                    unit_sprites)
            {
                unit_sprite.reset();
            }
            cursor_shadow.reset();
            cursor.reset();
            map_scenery_sprite.clear();
            battlefield_object_expiry_sprite.reset();
            text_sprites.clear();
            script_glyph_sprites.clear();
            ui_renderer.reset();
            portrait_renderer.reset();
            message_window_renderer.reset();
            dialogue_background_renderer.reset();
            combat_stage_renderer.reset();
            map.reset();
            // Commit released BG/OBJ owners before the preparation scene
            // allocates its task-menu background and glyph sprites.
            bn::core::update();
            return finish_scene(
                    battle_runtime_exit_for_outcome(
                            state.outcome));
        }
        if(battle_phase_uses_full_screen_result(
                   state.phase) &&
                map)
        {
            pickup_text_sprites.clear();
            pickup_text_frames = 0;
            // Postbattle pages form a full-screen visual cohort. Releasing
            // the map, its palette and map-unit OBJ owners before the first
            // outcome page prevents later result/level-up allocations from
            // restoring an invisible 8bpp map underneath a 4bpp result BG.
            range_overlay.reset();
            for(battle_unit_sprite_state& unit_sprite :
                    unit_sprites)
            {
                unit_sprite.reset();
            }
            cursor_shadow.reset();
            cursor.reset();
            map_scenery_sprite.clear();
            battlefield_object_expiry_sprite.reset();
            combat_stage_renderer.reset();
            map.reset();
            bn::core::update();
        }
        const bool dialogue_background_requested =
                config.battle_id == 14 &&
                state.phase ==
                        battle_scene_phase::
                                script_blocked &&
                state.script.selector == 1 &&
                ! presentation.busy();
        const battle_visual_resource_transition
                resource_transition =
                        resource_coordinator
                                .transition_to(
                                        select_battle_visual_resource_cohort(
                                                state.phase ==
                                                        battle_scene_phase::
                                                                script_blocked &&
                                                        ! presentation.busy(),
                                                presentation.combat()
                                                        .title_visible()));
        if(resource_transition.changed)
        {
            pickup_text_sprites.clear();
            pickup_text_frames = 0;
        }
        apply_visual_resource_transition(
                resource_transition,
               unit_sprites,
                map_scenery_sprite,
                cursor_shadow,
                cursor,
                battlefield_object_expiry_sprite,
                text_sprites,
                script_glyph_sprites,
                ui_renderer,
                portrait_renderer,
                message_window_renderer,
                dialogue_background_renderer,
                combat_stage_renderer);
        bool visual_resources_committed =
                resource_transition.commit_before_allocate;
        dialogue_background_renderer.update(
                dialogue_background_requested,
                map);
        if(resource_coordinator.current() ==
                        battle_visual_resource_cohort::map &&
                ! battle_phase_uses_full_screen_result(
                        state.phase))
        {
            ensure_battle_map_background(
                    config,
                    background,
                    camera,
                    map);
            ensure_map_scenery(
                    config,
                    camera,
                    object_state,
                    map_scenery_sprite);
            ensure_map_cursor(
                    state,
                    camera,
                    cursor_shadow,
                    cursor);
        }
        if(! presentation.busy() &&
                ! controller.presentation_pending())
        {
            dispatch_battle_phase_audio(
                    audio_director,
                    observed_audio_phase,
                    state);
            observed_audio_phase = state.phase;
        }
        const battle_combat_presentation_stage
                current_combat_stage =
                        presentation.combat().busy() ?
                                presentation.combat()
                                        .stage() :
                                battle_combat_presentation_stage::
                                        complete;
        if(current_combat_stage !=
                observed_combat_stage)
        {
            dispatch_battle_combat_stage_audio(
                    audio_director,
                    current_combat_stage,
                    presentation_special_combination);
            observed_combat_stage =
                    current_combat_stage;
            if(current_combat_stage ==
                    battle_combat_presentation_stage::
                            complete)
            {
                presentation_special_combination =
                        false;
            }
        }
        training_state = controller.training_snapshot();
        object_state = controller.object_snapshot();
        ++scene_frame;
        konoha_battle_runtime_telemetry.render_stage = 1;
        update_script_message_window(
                state,
                presentation.busy(),
                message_window_renderer);
        if(! update_combat_portrait(
                   state,
                   presentation,
                   portrait_renderer,
                   portrait_scratch))
        {
            update_script_portraits(
                    state,
                    presentation.busy(),
                    portrait_renderer,
                    portrait_scratch);
        }
        combat_stage_renderer.update(
                state,
                presentation,
                map,
                *config.map_items[
                        background.chunk_index()],
                background.chunk_origin(),
                camera);
        if(map)
        {
            if(state.phase !=
                            battle_scene_phase::
                                    script_blocked ||
                    presentation.busy())
            {
                update_unit_sprites(
                        state,
                        presentation,
                        scene_frame,
                        camera,
                        unit_sprites, false, &map_movement,
                        // S49 original frame 18: the unit that is not acting is
                        // greyscale while the command and action menus are up.
                        // The layer of the current frame is computed later in
                        // this loop, so the previously observed one is used; a
                        // menu stays up for many frames, so the lag is not
                        // observable.
                        observed_ui_layer ==
                                battle_ui_layer::command_menu ||
                        observed_ui_layer ==
                                battle_ui_layer::action_menu);
            }
            update_battlefield_object_expiry_sprite(
                    presentation,
                    camera,
                    battlefield_object_expiry_sprite);
        }
        if(! presentation.busy() &&
                state.phase !=
                        battle_scene_phase::enemy_turn &&
                state.phase !=
                        battle_scene_phase::script_blocked)
        {
            camera_focus = state.cursor;
        }
        if(cursor)
        {
            cursor->set_tiles(
                    bn::sprite_items::
                            scenario_41_cursor
                                    .tiles_item(),
                    battle_facing_indicator_graphics_index(
                            battle_map_cursor_facing(
                                    state),
                            scene_frame));
        }
        if(cursor_shadow && original_destination_cursor)
        {
            const bool ground_visible = battle_ui_ground_cursor_visible(
                    state, presentation.busy(), map_movement.busy());
            cursor_shadow->set_item(
                    bn::sprite_items::battle_scenario_49_destination_cursor,
                    battle_ui_destination_cursor_frame(destination_cursor_phase));
            cursor_shadow->set_position(world_x(state.cursor), world_y(state.cursor));
            cursor_shadow->set_visible(ground_visible);
            if(ground_visible)
            {
                destination_cursor_phase = (destination_cursor_phase + 1) % 44;
            }
        }
        if(handled || rejection_changed ||
                presentation_frame ||
                map_movement_frame || map_movement.busy() ||
                presentation.busy())
        {
            konoha_battle_runtime_telemetry.render_stage = 3;
            if(cursor)
            {
                cursor->set_position(
                        world_x(state.cursor),
                        world_y(state.cursor) - 24);
            }
            if(cursor_shadow && ! original_destination_cursor)
            {
                cursor_shadow->set_position(
                        world_x(state.cursor),
                        world_y(state.cursor) - 23);
            }
            const bool cursor_visible =
                    ! presentation.busy() && ! map_movement.busy() &&
                    battle_ui_map_cursor_visible(state);
            if(cursor)
            {
                cursor->set_visible(cursor_visible);
            }
            if(cursor_shadow && ! original_destination_cursor)
            {
                cursor_shadow->set_visible(
                        cursor_visible);
            }
            konoha_battle_runtime_telemetry.render_stage = 4;
            const int next_camera_x =
                    camera_x(camera_focus, config);
            camera.set_x(next_camera_x);
            camera.set_y(camera_y(camera_focus, config));
            if(map)
            {
                update_background_stream(
                        next_camera_x,
                        config,
                        background,
                        *map);
                // The confirmed destination is already in command_selection,
                // but the original keeps the movement grid until arrival.
                if(! map_movement.busy())
                {
                    update_range_overlay(
                            state,
                            presentation.busy(),
                            camera,
                            *map,
                            range_overlay);
                }
            }
            konoha_battle_runtime_telemetry.render_stage = 5;
            const battle_ui_model next_ui_model =
                    make_battle_ui_model(
                            state,
                            presentation.busy(), map_movement.busy());
            const bool ui_layer_changed =
                    next_ui_model.layer !=
                            observed_ui_layer;
            if(handled || rejection_changed ||
                    ui_layer_changed)
            {
                // Text glyph tile blocks become reusable only after a core
                // update. Commit the outgoing text after each input-driven
                // redraw so browsing a menu cannot exhaust OBJ VRAM.
                text_sprites.clear();
                if(ui_layer_changed)
                {
                    ui_renderer.reset();
                }
                if(! visual_resources_committed)
                {
                    bn::core::update();
                    visual_resources_committed = true;
                }
            }
            if(next_ui_model.layer != observed_ui_layer)
            {
                observed_ui_layer = next_ui_model.layer;
            }
            ui_renderer.update(
                    next_ui_model,
                    state,
                    controller.result_snapshot(),
                    presentation);
            render_battle_ui_text(
                    next_ui_model,
                    state,
                    training_state,
                    controller.result_snapshot(),
                    config,
                    rejection.visible,
                    presentation,
                    text_generator,
                    action_menu_text_generator,
                    duel_status_text_generator,
                    target_status_text_generator,
                    target_metrics_text_generator,
                    result_text_generator,
                    result_compact_text_generator,
                    text_sprites);
            if(presentation.busy())
            {
                script_glyph_sprites.clear();
            }
            else
            {
                render_script_glyphs(
                        state,
                        story_text_generator,
                        script_glyph_sprites);
            }
            konoha_battle_runtime_telemetry.render_stage = 6;
        }
        capture_telemetry(
                state,
                training_state,
                controller.result_snapshot(),
                config,
                scene_frame,
                last_control_error,
                last_player_error,
                last_resolved_action_id,
                last_ai_secondary,
                presentation.busy() || map_movement.busy(),
                presentation.busy() ?
                        &presentation.event() :
                        nullptr,
                presentation.combat().busy() ?
                        &presentation.combat() :
                        nullptr,
                object_state,
                object_telemetry,
                background);
        const auto pickup = controller.last_pickup();
        if(pickup.sequence != observed_pickup)
        {
            pickup_text_sprites.clear();
            observed_pickup = pickup.sequence;
            pickup_text_frames = 0;
            if(resource_coordinator.current() == battle_visual_resource_cohort::map &&
                    ! battle_phase_uses_full_screen_result(state.phase))
            {
                bn::string<32> message = pickup.material_id == 3 ? "钢石" : "毒草";
                message += pickup.added ? " +1" : " 99";
                text_generator.generate(-100, -68, message, pickup_text_sprites);
                pickup_text_frames = 120;
            }
        }
        else if(pickup_text_frames > 0 && --pickup_text_frames == 0)
        {
            pickup_text_sprites.clear();
        }
        const auto move_sample = map_movement.sample(state.selected_unit);
        konoha_battle_runtime_telemetry.map_movement_active = move_sample.moving;
        konoha_battle_runtime_telemetry.map_movement_sequence = move_sample.sequence;
        konoha_battle_runtime_telemetry.map_movement_elapsed = move_sample.elapsed_frames;
        konoha_battle_runtime_telemetry.map_movement_offset_x = move_sample.offset_x;
        konoha_battle_runtime_telemetry.map_movement_offset_y = move_sample.offset_y;
        konoha_battle_runtime_telemetry.map_visual_facing = static_cast<unsigned>(state.selected_facing);
        for(std::size_t index = 0; index < state.unit_count; ++index)
        {
            if(state.units[index].id == state.selected_unit)
                konoha_battle_runtime_telemetry.map_graphics_frame = unit_sprites[index].frame_index;
        }
        konoha_battle_runtime_telemetry.pickup_sequence = controller.last_pickup().sequence;
        konoha_battle_runtime_telemetry.material_3 = controller.inventory().materials[3];
        konoha_battle_runtime_telemetry.material_4 = controller.inventory().materials[4];
        konoha_battle_runtime_telemetry.render_stage = 7;
        if(! visual_resources_committed)
        {
            bn::core::update();
        }
        konoha_battle_runtime_telemetry.render_stage = 0;
    }
}

}

battle_runtime_scene_exit run_battle_scene(
        const battle_runtime_scene_request& request)
{
    BN_DATA_EWRAM static
            battle_campaign_scene_progression
                    scene_progression;
    BN_DATA_EWRAM static
            battle_runtime_scene_config config;
    scene_progression = {};
    config = {};
    config.battle_id = request.battle_id;
    config.variant = request.variant;
    config.rng_seed = request.rng_seed;
    config.title = request.title;
    config.load_policy = request.load_policy;
    if(request.arena_roster)
    {
        if(request.campaign ||
                apply_battle_arena_scene_policy(
                        *request.arena_roster,
                        config.load_policy) !=
                        battle_arena_roster_error::none)
        {
            return battle_runtime_scene_exit::aborted;
        }
    }
    if(request.campaign)
    {
        if(scene_progression.begin(*request.campaign) !=
                battle_campaign_error::none)
        {
            return battle_runtime_scene_exit::aborted;
        }
        if(apply_battle_campaign_scene_policy(
                   *request.campaign,
                   config.load_policy) !=
                battle_campaign_error::none)
        {
            return battle_runtime_scene_exit::aborted;
        }
        config.initial_inventory = request.campaign->inventory;
        config.materials_output = &scene_progression.materials();
        config.progression_roster =
                scene_progression.records();
        config.progression_output =
                &scene_progression.records();
        config.equipped_tools_output =
                &scene_progression.equipped_tools();
    }
    else
    {
        config.progression_roster =
                request.progression_roster;
    }
    const battle_runtime_scene_exit exit =
            run_visible_battle_scene(config);
    if(request.campaign &&
            battle_runtime_exit_commits_campaign(exit) &&
            scene_progression.commit(*request.campaign) !=
                    battle_campaign_error::none)
    {
        return battle_runtime_scene_exit::aborted;
    }
    return exit;
}

battle_runtime_scene_exit run_battle_campaign_stage(
        battle_campaign_state& campaign)
{
    const battle_campaign_stage_result resolved =
            battle_campaign_stage_for(
                    campaign.chapter_id);
    if(! resolved.success() || resolved.complete)
    {
        return battle_runtime_scene_exit::aborted;
    }
    const battle_campaign_stage_definition* stage =
            resolved.stage;
    battle_runtime_scene_request request;
    request.battle_id = stage->battle_id;
    request.variant = stage->variant;
    request.rng_seed = campaign.chapter_id;
    request.title = stage->title;
    request.load_policy.preserve_empty_unit_slots =
            true;
    request.campaign = &campaign;
    return run_battle_scene(request);
}

battle_runtime_scene_exit run_battle_43_scene()
{
    battle_runtime_scene_request request;
    request.battle_id = 43;
    request.variant = 0;
    request.rng_seed = 0x43U;
    request.title = "S43";
    request.load_policy.preserve_empty_unit_slots = true;
    return run_battle_scene(request);
}

battle_runtime_scene_exit run_battle_41_scene()
{
    battle_runtime_scene_request request;
    request.battle_id = 41;
    request.variant = 0;
    request.rng_seed = 0x41U;
    request.title = "S41";
    request.load_policy.preserve_empty_unit_slots = true;
    request.load_policy.character_equipped_tools[1][0] = 67;
    request.load_policy.character_equipped_tools[1][1] = 11;
    request.load_policy.character_equipped_tools[1][2] = 37;
    request.progression_roster =
            scenario_41_initial_roster();
    return run_battle_scene(request);
}

battle_runtime_scene_exit run_battle_41_scene(
        battle_campaign_state& campaign)
{
    battle_runtime_scene_request request;
    request.battle_id = 41;
    request.variant = 0;
    request.rng_seed = 0x41U;
    request.title = "S41";
    request.load_policy.preserve_empty_unit_slots = true;
    request.campaign = &campaign;
    return run_battle_scene(request);
}

battle_runtime_scene_exit run_battle_09_scene()
{
    battle_runtime_scene_request request;
    request.battle_id = 9;
    request.variant = 0;
    request.rng_seed = 0x09U;
    request.title = "B09 3V5";
    request.load_policy.preserve_empty_unit_slots = true;
    request.load_policy.character_equipped_tools[1][0] = 1;
    request.load_policy.character_equipped_tools[2][0] = 49;
    return run_battle_scene(request);
}

battle_runtime_scene_exit run_battle_11_scene()
{
    battle_runtime_scene_request request;
    request.battle_id = 11;
    request.variant = 0;
    request.rng_seed = 0x11U;
    request.title = "B11 STREAM";
    request.load_policy.preserve_empty_unit_slots = true;
    return run_battle_scene(request);
}

battle_runtime_scene_exit
run_battle_32_arena_fixture_scene()
{
    BN_DATA_EWRAM static
            battle_arena_match_roster roster;
    roster = {};
    const auto make_combatant = [](
            std::uint8_t character_id,
            int level,
            ninja_tool_id first_tool)
    {
        battle_arena_combatant result;
        result.progression.character_id =
                character_id;
        result.progression.level = level;
        result.progression.active = true;
        if(! initialize_character_action_progression(
                   result.progression,
                   unit_definitions[character_id]))
        {
            return battle_arena_combatant{};
        }
        result.equipped_tools[0] = first_tool;
        return result;
    };
    roster.player[0] = make_combatant(1, 10, 1);
    roster.player[1] = make_combatant(2, 12, 17);
    roster.player[2] = make_combatant(3, 11, 46);
    roster.opponent[0] = make_combatant(12, 18, 93);
    roster.opponent[1] = make_combatant(35, 15, 11);
    roster.opponent[2] = make_combatant(1, 20, 67);

    battle_runtime_scene_request request;
    request.battle_id = 32;
    request.variant = 0;
    request.rng_seed = 0x32U;
    request.title = "B32 ARENA 3V3";
    request.arena_roster = &roster;
    request.load_policy.preserve_empty_unit_slots = true;
    return run_battle_scene(request);
}

}
