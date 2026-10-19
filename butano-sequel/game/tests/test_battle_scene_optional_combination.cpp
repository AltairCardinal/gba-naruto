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
    policy.character_levels[2] = 50;

    controller_type controller;
    assert(controller.load(
                   battle_scenario_definitions[9],
                   battle_map_definitions[9],
                   battle_map_cells,
                   0,
                   policy,
                   battle_condition_variants[9][0],
                   0x0910U)
                   .success());
    assert(controller.start().success());
    while(controller.snapshot().selected_unit != 2)
    {
        assert(controller.cycle_unit(1).success());
    }
    assert(controller.confirm().success());
    assert(controller.confirm().success());
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::action_selection);

    select_action(controller, 16);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::combination_decision);
    assert(controller.snapshot().player
                   .combination_decision_selected);

    assert(controller.cancel().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::action_selection);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::combination_decision);
    assert(controller.move_cursor(0, 1).success());
    assert(! controller.snapshot().player
                    .combination_decision_selected);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_selection);
    assert(controller.snapshot().player
                   .combination_component_count == 0);

    assert(controller.cancel().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::action_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::combination_decision);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::action_selection);
    assert(controller.snapshot().player
                   .combination_component_count == 1);
    assert(controller.snapshot().player
                   .combination_first_action_id == 16);

    select_action(controller, 5);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_selection);
    assert(controller.snapshot().player
                   .combination_component_count == 2);
    assert(controller.snapshot().player
                   .combination_result_action_id == no_ability);
}
