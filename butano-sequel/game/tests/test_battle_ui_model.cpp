#include "konoha/battle_ui_model.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_ui_rejection_latch rejection;
    assert(! rejection.visible);
    assert(rejection.update(true, false));
    assert(rejection.visible);
    assert(rejection.remaining_frames ==
           battle_ui_rejection_latch::display_frames);
    assert(rejection.update(true, true));
    assert(! rejection.visible);
    assert(rejection.remaining_frames == 0);

    battle_scene_snapshot<12> state;
    state.phase = battle_scene_phase::unit_selection;
    state.round = 1;
    state.current_side = battle_side::player;
    state.selected_unit = 1;
    state.cursor = { 2, 3 };
    state.unit_count = 2;
    state.units[0] = {
        1,
        1,
        battle_side::player,
        battle_control::player,
        { 2, 3 },
        battle_facing::right,
        5,
        18,
        17,
        12,
        4,
        138,
        138,
        5,
        5,
        0,
        true,
        false,
        no_battle_unit,
    };
    state.units[1] = {
        2,
        55,
        battle_side::enemy,
        battle_control::ai,
        { 4, 3 },
        battle_facing::left,
        1,
        8,
        4,
        6,
        3,
        25,
        25,
        0,
        0,
        0,
        true,
        false,
        no_battle_unit,
    };

    battle_ui_model model = make_battle_ui_model(state, false);
    assert(model.layer == battle_ui_layer::map_status);
    assert(model.status_unit_id == 1);
    assert(model.show_status_panel);
    assert(! model.show_round_badge);
    assert(! model.show_menu_panel);

    state.phase = battle_scene_phase::move_selection;
    state.player.move_position = { 3, 4 };
    state.player.move_cost = 2;
    model = make_battle_ui_model(state, false);
    assert(model.layer == battle_ui_layer::map_status);
    assert(model.show_move_prompt);
    assert(model.move_position == grid_point({ 3, 4 }));
    assert(model.move_cost == 2);

    // The round banner is the original's screen between the opening dialogue
    // and the first command (S49 original frame 15).  It is drawn over the
    // battlefield, so the status bar stays up behind it.
    state.phase = battle_scene_phase::turn_banner;
    model = make_battle_ui_model(state, false);
    assert(model.layer == battle_ui_layer::turn_banner);
    assert(model.show_status_panel);
    assert(! model.show_menu_panel);
    assert(! model.show_move_prompt);
    assert(! model.show_target_prompt);

    state.phase = battle_scene_phase::command_selection;
    state.player.command_count = 3;
    state.player.command_index = 1;
    state.player.command_entries[0].type =
            battle_command_type::move;
    state.player.command_entries[1].type =
            battle_command_type::ability;
    state.player.command_entries[2].type =
            battle_command_type::end_action;
    model = make_battle_ui_model(state, false);
    assert(model.layer == battle_ui_layer::command_menu);
    assert(model.show_menu_panel);
    assert(model.menu_count == 3);
    assert(model.menu_index == 1);
    assert(model.selected_command ==
           battle_command_type::ability);

    state.phase = battle_scene_phase::action_selection;
    state.player.action_count = 2;
    state.player.action_index = 1;
    state.player.action_entries[1].action_id = 7;
    state.player.action_entries[1].selection_error =
            action_error::none;
    model = make_battle_ui_model(state, false);
    assert(model.layer == battle_ui_layer::action_menu);
    assert(model.show_action_detail);
    assert(! model.show_round_badge);
    assert(model.menu_count == 2);
    assert(model.menu_index == 1);
    assert(model.action_id == 7);
    assert(model.action_selectable);

    state.phase = battle_scene_phase::target_selection;
    state.cursor = { 4, 3 };
    model = make_battle_ui_model(state, false);
    assert(model.layer == battle_ui_layer::target_select);
    assert(model.status_unit_id == 1);
    assert(model.show_target_prompt);

    state.phase = battle_scene_phase::target_preview;
    model = make_battle_ui_model(state, false);
    assert(model.layer == battle_ui_layer::map_status);
    assert(model.status_unit_id == 2);
    assert(model.show_status_panel);
    assert(! model.show_target_prompt);
    assert(! model.show_dialog_panel);

    state.phase = battle_scene_phase::target_confirmation;
    state.target_confirmation_yes = true;
    model = make_battle_ui_model(state, false);
    assert(model.layer == battle_ui_layer::confirmation);
    assert(model.status_unit_id == 2);
    assert(model.show_status_panel);
    assert(model.show_dialog_panel);
    assert(! model.show_large_dialog_panel);

    state.phase = battle_scene_phase::facing_selection;
    state.selected_facing = battle_facing::left;
    model = make_battle_ui_model(state, false);
    assert(model.layer == battle_ui_layer::map_status);
    assert(model.show_facing_prompt);
    assert(model.show_instruction_panel);
    assert(! model.show_status_panel);
    assert(model.selected_facing == battle_facing::left);

    state.phase = battle_scene_phase::end_confirmation;
    state.end_confirmation_yes = true;
    model = make_battle_ui_model(state, false);
    assert(model.layer == battle_ui_layer::confirmation);
    assert(model.show_dialog_panel);
    assert(! model.show_large_dialog_panel);

    state.phase = battle_scene_phase::defense_decision;
    state.defense_confirmation_yes = true;
    model = make_battle_ui_model(state, false);
    assert(model.layer == battle_ui_layer::confirmation);
    assert(! model.show_dialog_panel);
    assert(model.show_large_dialog_panel);

    state.phase = battle_scene_phase::result;
    model = make_battle_ui_model(state, false);
    assert(model.layer == battle_ui_layer::result);
    assert(model.show_result_panel);
    assert(! model.show_status_panel);

    state.phase = battle_scene_phase::command_selection;
    model = make_battle_ui_model(state, true);
    assert(model.layer == battle_ui_layer::presentation);
    assert(! model.show_menu_panel);
    assert(model.show_status_panel);
}
