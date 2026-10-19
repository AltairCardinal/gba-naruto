#include "konoha/battle_scene_controller.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>

using namespace konoha;

namespace
{

using controller_type =
        battle_scene_controller<12, 16, 32>;
using snapshot_type = battle_scene_snapshot<12>;

void select_action(
        controller_type& controller,
        ability_id action_id)
{
    snapshot_type state = controller.snapshot();
    assert(state.phase ==
           battle_scene_phase::action_selection);
    for(int index = 0;
            index < state.player.action_count &&
            state.player.selected_action_id != action_id;
            ++index)
    {
        assert(controller.move_cursor(0, 1).success());
        state = controller.snapshot();
    }
    assert(state.player.selected_action_id == action_id);
}

}

int main()
{
    battle_scenario_load_policy policy;
    policy.preserve_empty_unit_slots = true;
    policy.character_levels[1] = 50;
    std::array<character_progression_record, 3> roster = {{
        { 1, 50, 0, 0, true },
        {},
        {},
    }};
    assert(initialize_character_action_progression(
            roster[0], unit_definitions[1]));
    roster[0].primary_action_levels[7] = 1;

    controller_type controller;
    assert(controller.load(
                   battle_scenario_definitions[9],
                   battle_map_definitions[9],
                   battle_map_cells,
                   0,
                   policy,
                   battle_condition_variants[9][0],
                   0x0905U,
                   roster)
                   .success());
    assert(controller.start().success());

    assert(controller.snapshot().selected_unit == 1);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::action_selection);

    select_action(controller, 9);
    const snapshot_type before_first_component =
            controller.snapshot();
    assert(controller.confirm().success());

    snapshot_type state = controller.snapshot();
    assert(state.phase ==
           battle_scene_phase::action_selection);
    assert(state.player.phase ==
           battle_player_action_phase::action_selection);
    assert(state.player.combination_component_count == 1);
    assert(state.player.combination_first_action_id == 9);
    assert(state.round == before_first_component.round);
    assert(state.units[0].hp ==
           before_first_component.units[0].hp);
    assert(state.units[0].chakra ==
           before_first_component.units[0].chakra);
    assert(state.units[0].position ==
           before_first_component.units[0].position);

    assert(controller.cancel().success());
    state = controller.snapshot();
    assert(state.phase ==
           battle_scene_phase::action_selection);
    assert(state.player.combination_component_count == 0);

    select_action(controller, 9);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::action_selection);

    select_action(controller, 5);
    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(state.phase ==
           battle_scene_phase::target_selection);
    assert(state.player.phase ==
           battle_player_action_phase::target_selection);
    assert(state.player.combination_component_count == 2);
    assert(state.player.combination_result_action_id == 11);
}
