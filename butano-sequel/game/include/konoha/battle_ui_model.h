#ifndef KONOHA_BATTLE_UI_MODEL_H
#define KONOHA_BATTLE_UI_MODEL_H

#include "konoha/battle_scene_controller.h"

#include <cstdint>

namespace konoha
{

enum class battle_ui_layer : std::uint8_t
{
    hidden,
    map_status,
    command_menu,
    action_menu,
    target_select,
    confirmation,
    defense_menu,
    result,
    level_up,
    training,
    presentation,
    turn_banner,
};

struct battle_ui_model
{
    battle_ui_layer layer = battle_ui_layer::hidden;
    battle_unit_id status_unit_id = no_battle_unit;
    int menu_count = 0;
    int menu_index = 0;
    battle_command_type selected_command =
            battle_command_type::end_action;
    ability_id action_id = no_ability;
    bool action_selectable = false;
    bool show_status_panel = false;
    bool show_round_badge = false;
    bool show_menu_panel = false;
    bool show_action_detail = false;
    bool show_move_prompt = false;
    bool show_target_prompt = false;
    // The original's small "SELECT詳細" hint in the top right corner.  It is
    // shown while the player picks a unit, while they pick a destination and
    // while they pick a target, and it is hidden behind every menu.
    bool show_select_prompt = false;
    bool show_facing_prompt = false;
    bool show_instruction_panel = false;
    bool show_dialog_panel = false;
    bool show_large_dialog_panel = false;
    bool show_result_panel = false;
    grid_point move_position = {};
    int move_cost = 0;
    battle_facing selected_facing = battle_facing::up;
};

struct battle_ui_rejection_latch
{
    static constexpr int display_frames = 60;

    [[nodiscard]] constexpr bool update(
            bool input_handled,
            bool input_success)
    {
        if(input_handled)
        {
            if(input_success)
            {
                const bool changed = visible;
                visible = false;
                remaining_frames = 0;
                return changed;
            }

            const bool changed = ! visible;
            visible = true;
            remaining_frames = display_frames;
            return changed;
        }

        if(visible && remaining_frames > 0)
        {
            --remaining_frames;
            if(remaining_frames == 0)
            {
                visible = false;
                return true;
            }
        }
        return false;
    }

    bool visible = false;
    int remaining_frames = 0;
};

template<std::size_t MaxUnits>
[[nodiscard]] constexpr battle_unit_id
battle_ui_unit_at_cursor(
        const battle_scene_snapshot<MaxUnits>& state)
{
    for(std::size_t index = 0;
            index < state.unit_count &&
            index < state.units.size();
            ++index)
    {
        const battle_scene_unit_view& unit =
                state.units[index];
        if(unit.active && unit.position == state.cursor)
        {
            return unit.id;
        }
    }
    return no_battle_unit;
}

template<std::size_t MaxUnits>
[[nodiscard]] constexpr bool battle_ui_map_cursor_visible(
        const battle_scene_snapshot<MaxUnits>& state)
{
    switch(state.phase)
    {
    case battle_scene_phase::move_selection:
        return battle_ui_unit_at_cursor(state) != no_battle_unit;
    case battle_scene_phase::unit_selection:
    case battle_scene_phase::command_selection:
    case battle_scene_phase::target_selection:
    case battle_scene_phase::target_preview:
    case battle_scene_phase::target_confirmation:
    case battle_scene_phase::facing_selection:
        return true;
    default:
        return false;
    }
}

template<std::size_t MaxUnits>
[[nodiscard]] constexpr bool battle_ui_ground_cursor_visible(
        const battle_scene_snapshot<MaxUnits>& state,
        bool presentation_busy, bool map_moving)
{
    return ! presentation_busy &&
            (map_moving || state.phase == battle_scene_phase::move_selection ||
             battle_ui_map_cursor_visible(state));
}

[[nodiscard]] constexpr int battle_ui_destination_cursor_frame(int phase)
{
    phase %= 44;
    return phase < 4 ? 3 : phase < 9 ? 2 : phase < 16 ? 1 :
            phase < 31 ? 0 : phase < 39 ? 1 : 2;
}

template<std::size_t MaxUnits>
[[nodiscard]] constexpr battle_ui_model make_battle_ui_model(
        const battle_scene_snapshot<MaxUnits>& state,
        bool presentation_busy,
        bool map_moving = false)
{
    battle_ui_model result;
    if(map_moving)
    {
        return result;
    }
    result.status_unit_id = state.selected_unit;
    result.show_round_badge = false;
    result.show_status_panel =
            state.selected_unit != no_battle_unit;

    if(presentation_busy)
    {
        result.layer = battle_ui_layer::presentation;
        return result;
    }

    switch(state.phase)
    {
    case battle_scene_phase::turn_banner:
        // The original keeps the status bar up behind the round banner, so
        // the panel is drawn over the battlefield instead of replacing it.
        result.layer = battle_ui_layer::turn_banner;
        break;
    case battle_scene_phase::unit_selection:
        result.layer = battle_ui_layer::map_status;
        result.show_select_prompt = true;
        break;
    case battle_scene_phase::enemy_turn:
        result.layer = battle_ui_layer::map_status;
        break;
    case battle_scene_phase::facing_selection:
        result.layer = battle_ui_layer::map_status;
        result.show_status_panel = false;
        result.show_facing_prompt = true;
        result.show_instruction_panel = true;
        result.selected_facing = state.selected_facing;
        break;
    case battle_scene_phase::move_selection:
        result.layer = battle_ui_layer::map_status;
        result.status_unit_id = battle_ui_unit_at_cursor(state);
        result.show_status_panel = result.status_unit_id != no_battle_unit;
        result.show_move_prompt = result.show_status_panel;
        result.show_select_prompt = true;
        result.move_position =
                state.player.move_position;
        result.move_cost = state.player.move_cost;
        break;
    case battle_scene_phase::chakra_selection:
    case battle_scene_phase::rest_confirmation:
    case battle_scene_phase::combination_decision:
        result.layer = battle_ui_layer::confirmation;
        result.show_dialog_panel = true;
        break;
    case battle_scene_phase::command_selection:
        result.layer = battle_ui_layer::command_menu;
        result.show_menu_panel = true;
        result.menu_count = state.player.command_count;
        result.menu_index = state.player.command_index;
        result.selected_command =
                state.player.selected_command;
        if(result.menu_index >= 0 &&
                result.menu_index < result.menu_count &&
                result.menu_index <
                        static_cast<int>(
                                state.player
                                        .command_entries.size()))
        {
            result.selected_command =
                    state.player.command_entries[
                            static_cast<std::size_t>(
                                    result.menu_index)]
                            .type;
        }
        break;
    case battle_scene_phase::action_selection:
        result.layer = battle_ui_layer::action_menu;
        result.show_round_badge = false;
        result.show_menu_panel = true;
        result.show_action_detail = true;
        result.menu_count = state.player.action_count;
        result.menu_index = state.player.action_index;
        if(result.menu_index >= 0 &&
                result.menu_index < result.menu_count &&
                result.menu_index <
                        static_cast<int>(
                                state.player
                                        .action_entries.size()))
        {
            const battle_action_menu_view& action =
                    state.player.action_entries[
                            static_cast<std::size_t>(
                                    result.menu_index)];
            result.action_id = action.action_id;
            result.action_selectable = action.selectable();
        }
        break;
    case battle_scene_phase::target_selection:
    {
        result.layer = battle_ui_layer::target_select;
        result.show_target_prompt = true;
        result.show_select_prompt = true;
        break;
    }
    case battle_scene_phase::target_preview:
        result.layer = battle_ui_layer::map_status;
        result.status_unit_id =
                battle_ui_unit_at_cursor(state);
        result.show_status_panel =
                result.status_unit_id != no_battle_unit;
        break;
    case battle_scene_phase::target_confirmation:
        result.layer = battle_ui_layer::confirmation;
        result.status_unit_id =
                battle_ui_unit_at_cursor(state);
        result.show_status_panel =
                result.status_unit_id != no_battle_unit;
        result.show_dialog_panel = true;
        break;
    case battle_scene_phase::end_confirmation:
        result.layer = battle_ui_layer::confirmation;
        result.show_dialog_panel = true;
        break;
    case battle_scene_phase::defense_decision:
        result.layer = battle_ui_layer::confirmation;
        result.show_large_dialog_panel = true;
        break;
    case battle_scene_phase::defense_selection:
        result.layer = battle_ui_layer::defense_menu;
        result.show_menu_panel = true;
        result.menu_count =
                state.player.defense_action_count;
        result.menu_index =
                state.player.defense_action_index;
        break;
    case battle_scene_phase::result:
    case battle_scene_phase::outcome:
    case battle_scene_phase::complete:
        result.layer = battle_ui_layer::result;
        result.show_status_panel = false;
        result.show_round_badge = false;
        result.show_result_panel = true;
        break;
    case battle_scene_phase::level_up:
        result.layer = battle_ui_layer::level_up;
        result.show_status_panel = false;
        result.show_round_badge = false;
        result.show_result_panel = true;
        break;
    case battle_scene_phase::training:
        result.layer = battle_ui_layer::training;
        result.show_status_panel = false;
        result.show_round_badge = false;
        result.show_result_panel = true;
        break;
    case battle_scene_phase::script_blocked:
    case battle_scene_phase::preparation:
    case battle_scene_phase::error:
    default:
        result.layer = battle_ui_layer::hidden;
        result.show_status_panel = false;
        result.show_round_badge = false;
        break;
    }
    return result;
}

}

#endif
