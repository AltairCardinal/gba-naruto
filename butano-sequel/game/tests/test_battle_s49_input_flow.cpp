#include "konoha/battle_runtime_grid.h"
#include "konoha/battle_scene_controller.h"
#include "konoha/battle_map_movement.h"
#include "konoha/battle_ui_model.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <array>
#include <cassert>

using namespace konoha;

int main()
{
    battle_runtime_controller controller;
    assert(controller.load(battle_scenario_definitions[14],
            battle_map_definitions[14], battle_map_cells, 0, {},
            battle_condition_variants[14][0], 49U, {}, false,
            battle_mission_rules_for(14, 0)).success());
    assert(controller.start().success());
    assert(controller.tick().success()); // opening escort turn
    const auto origin = controller.snapshot().units[0].position;
    assert(controller.confirm().success());
    auto state = controller.snapshot();
    // Original step-06-A: selecting an actor opens five commands first.
    assert(state.phase == battle_scene_phase::command_selection);
    assert(battle_map_visual_position(state, state.units[0]) == origin);
    constexpr std::array commands = {battle_command_type::move,
            battle_command_type::ability, battle_command_type::replenish_chakra,
            battle_command_type::rest, battle_command_type::end_action};
    assert(state.player.command_count == commands.size());
    for(std::size_t i = 0; i < commands.size(); ++i)
    {
        assert(state.player.command_entries[i].type == commands[i]);
    }
    assert(state.player.selected_command == battle_command_type::move);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase == battle_scene_phase::move_selection);
    assert(battle_ui_map_cursor_visible(controller.snapshot()));
    assert(controller.cancel().success());
    // Original move-B frame-063: one B returns to the command menu.
    assert(controller.snapshot().phase == battle_scene_phase::command_selection);
    assert(controller.snapshot().player.command_count == 5);
    assert(controller.snapshot().units[0].position == origin);
    assert(controller.confirm().success());
    assert(controller.confirm().success()); // confirm movement on the original cell
    state = controller.snapshot();
    // Original step-08-A: even a same-cell movement leaves exactly two commands.
    assert(state.phase == battle_scene_phase::command_selection);
    assert(state.player.command_count == 2);
    assert(battle_ui_map_cursor_visible(state));
    assert(state.player.command_entries[0].type == battle_command_type::ability);
    assert(state.player.command_entries[1].type == battle_command_type::end_action);
    assert(state.units[0].position == origin);
    assert(controller.cancel().success());
    // Original postmove-B: undo a same-cell confirmation to the five commands.
    assert(controller.snapshot().phase == battle_scene_phase::command_selection);
    assert(controller.snapshot().player.command_count == 5);
    assert(controller.confirm().success());
    battle_map_movement movement;
    movement.observe(controller.snapshot());
    assert(controller.move_cursor(1, 0).success());
    state = controller.snapshot();
    assert(battle_map_visual_position(state, state.units[0]) == origin);
    assert(battle_map_visual_facing(state, state.units[0]) == battle_facing::right);
    movement.observe(state);
    assert(! movement.busy()); // selecting a tile only turns the actor
    assert(! make_battle_ui_model(state, false).show_status_panel);
    assert(! make_battle_ui_model(state, false).show_move_prompt);
    assert(! battle_ui_map_cursor_visible(state));
    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(battle_map_visual_position(state, state.units[0]) == state.cursor);
    movement.observe(state);
    assert(movement.busy()); // movement starts at confirmation
    const auto moving_ui = make_battle_ui_model(state, false, movement.busy());
    assert(moving_ui.layer == battle_ui_layer::hidden);
    assert(! moving_ui.show_status_panel && ! moving_ui.show_menu_panel);
    assert(movement.sample(state.selected_unit).offset_x == -32);
    for(int frame = 0; frame < 26; ++frame)
    {
        movement.advance();
    }
    assert(! movement.busy());
    assert(controller.snapshot().player.command_count == 2);
    assert(controller.cancel().success());
    // Original right-A-B: undo the destination and return directly to commands.
    assert(controller.snapshot().phase == battle_scene_phase::command_selection);
    assert(controller.snapshot().player.command_count == 5);
    assert(controller.snapshot().cursor == origin);
    assert(controller.snapshot().units[0].position == origin);
    state = controller.snapshot();
    assert(battle_map_visual_facing(state, state.units[0]) == state.units[0].facing);
    movement.observe(controller.snapshot());
    assert(! movement.busy()); // original B returns instantly, with no reverse walk
    assert(controller.cancel().success());
    assert(controller.snapshot().phase == battle_scene_phase::unit_selection);
}
