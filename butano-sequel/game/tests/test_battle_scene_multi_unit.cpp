#include "konoha/battle_scene_controller.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>

using namespace konoha;

static_assert(
        sizeof(pathfinder_workspace<16, 32>) == 8704);

namespace
{

void complete_selected_player(
        battle_scene_controller<12, 16, 32>& controller,
        battle_unit_id expected_unit,
        battle_scene_phase expected_phase)
{
    battle_scene_snapshot<12> state = controller.snapshot();
    assert(state.phase == battle_scene_phase::unit_selection);
    assert(state.selected_unit == expected_unit);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);

    // Move each player one visible cell to the right so the runtime
    // sample exercises collision, pathfinding, and presentation wiring.
    assert(controller.move_cursor(1, 0).success());
    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::command_selection);
    assert(state.player.selected_command ==
           battle_command_type::ability);

    // A zero-distance move keeps resource commands visible, so cycle
    // through the real browser instead of assuming a fixed index.
    for(int step = 0;
            step < state.player.command_count &&
            controller.snapshot().player.selected_command !=
                    battle_command_type::end_action;
            ++step)
    {
        assert(controller.move_cursor(0, 1).success());
    }
    state = controller.snapshot();
    assert(state.player.selected_command ==
           battle_command_type::end_action);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::facing_selection);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::defense_decision);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase == expected_phase);
}

}

int main()
{
    battle_scenario_load_policy fixed_pool;
    fixed_pool.preserve_empty_unit_slots = true;

    battle_scene_controller<12, 16, 32> controller;
    assert(controller.load(
                   battle_scenario_definitions[9],
                   battle_map_definitions[9],
                   battle_map_cells,
                   0,
                   fixed_pool,
                   battle_condition_variants[9][0],
                   0x09U)
                   .success());
    assert(controller.start().success());

    battle_scene_snapshot<12> state = controller.snapshot();
    assert(state.round == 1);
    assert(state.phase == battle_scene_phase::unit_selection);
    assert(state.current_side == battle_side::player);
    assert(state.unit_count == 12);
    assert(state.active_unit_count == 8);
    assert(state.selected_unit == 1);
    assert(state.units[0].character_id == 1);
    assert(state.units[0].level == 1);
    assert(state.units[0].attack == 14);
    assert(state.units[0].defense == 13);
    assert(state.units[0].agility == 8);
    assert(state.units[0].movement == 3);
    assert(state.units[1].character_id == 2);
    assert(state.units[1].level == 1);
    assert(state.units[1].attack == 12);
    assert(state.units[1].defense == 8);
    assert(state.units[1].agility == 12);
    assert(state.units[1].movement == 3);
    assert(state.units[2].character_id == 3);
    assert(state.units[2].level == 1);
    assert(state.units[2].attack == 7);
    assert(state.units[2].defense == 7);
    assert(state.units[2].agility == 10);
    assert(state.units[2].movement == 3);
    for(std::size_t index = 3; index < 8; ++index)
    {
        assert(state.units[index].character_id == 41);
        assert(state.units[index].side == battle_side::enemy);
    }
    for(std::size_t index = 8; index < 12; ++index)
    {
        assert(! state.units[index].active);
    }

    // Unit-selection directions navigate selectable units instead of
    // leaving the cursor on empty map cells.
    assert(controller.move_cursor(0, 1).success());
    state = controller.snapshot();
    assert(state.selected_unit == 2);
    assert(state.cursor == state.units[1].position);
    assert(controller.move_cursor(0, -1).success());
    state = controller.snapshot();
    assert(state.selected_unit == 1);
    assert(state.cursor == state.units[0].position);
    assert(controller.cancel().success());
    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::unit_selection);
    assert(state.selected_unit == 1);
    assert(state.cursor == state.units[0].position);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::action_selection);
    assert(state.player.action_count == 3);
    assert(state.player.action_entries[0].action_id == 2);
    assert(state.player.action_entries[1].action_id == 5);
    assert(state.player.action_entries[2].action_id == 7);
    assert(state.player.action_entries[0].action_id ==
           active_action_definitions[2].id);
    assert(state.player.action_entries[1].action_id ==
           active_action_definitions[5].id);
    assert(state.player.action_entries[2].action_id ==
           active_action_definitions[7].id);
    assert(state.player.action_entries[0].target_kind ==
           active_action_definitions[2].target.kind);
    assert(state.player.action_entries[1].effect_code ==
           active_action_definitions[5].effect.code);
    assert(state.player.action_entries[2].effect_code ==
           active_action_definitions[7].effect.code);
    assert(controller.cancel().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    assert(controller.cancel().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::unit_selection);
    assert(controller.snapshot().player.action_count == 0);

    assert(controller.cycle_unit(1).success());
    assert(controller.snapshot().selected_unit == 2);
    assert(controller.cycle_unit(1).success());
    assert(controller.snapshot().selected_unit == 3);
    assert(controller.cycle_unit(1).success());
    assert(controller.snapshot().selected_unit == 1);

    complete_selected_player(
            controller,
            1,
            battle_scene_phase::unit_selection);
    state = controller.snapshot();
    assert(state.current_side == battle_side::player);
    assert(state.units[0].completed);
    assert(state.selected_unit == 2);

    complete_selected_player(
            controller,
            2,
            battle_scene_phase::unit_selection);
    state = controller.snapshot();
    assert(state.current_side == battle_side::player);
    assert(state.units[1].completed);
    assert(state.selected_unit == 3);

    complete_selected_player(
            controller,
            3,
            battle_scene_phase::enemy_turn);
    state = controller.snapshot();
    assert(state.current_side == battle_side::enemy);
    assert(state.units[2].completed);

    for(battle_unit_id enemy_id = 4;
            enemy_id <= 8; ++enemy_id)
    {
        const battle_scene_control_result result =
                controller.tick();
        assert(result.success());
        state = controller.snapshot();
        if(enemy_id < 8)
        {
            assert(state.phase ==
                   battle_scene_phase::enemy_turn);
            assert(state.units[
                    static_cast<std::size_t>(
                            enemy_id - 1)].completed);
        }
    }

    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::unit_selection);
    assert(state.current_side == battle_side::player);
    assert(state.round == 2);
    assert(state.selected_unit == 1);
    assert(state.active_unit_count == 8);
    for(std::size_t index = 0; index < 8; ++index)
    {
        assert(! state.units[index].completed);
    }

    // The same snapped selection contract must survive the round
    // boundary; stale first-round UI state cannot strand the cursor.
    assert(controller.move_cursor(1, 0).success());
    state = controller.snapshot();
    assert(state.selected_unit == 2);
    assert(state.cursor == state.units[1].position);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);
}
