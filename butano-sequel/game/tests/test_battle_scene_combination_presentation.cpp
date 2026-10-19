#include "konoha/battle_scene_controller.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

using controller_type =
        battle_scene_controller<2, 4, 4>;
using snapshot_type = battle_scene_snapshot<2>;

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
    battle_scenario_definition scenario;
    scenario.battle_id = 0xFE;
    scenario.grid_width = 4;
    scenario.grid_height = 4;
    scenario.variants[0][0] = {
        true,
        scenario_selector_kind::fixed_character,
        1,
        battle_side::player,
        { 1, 1 },
        battle_facing::right,
        0,
    };
    scenario.variants[0][1] = {
        true,
        scenario_selector_kind::fixed_character,
        35,
        battle_side::enemy,
        { 2, 1 },
        battle_facing::left,
        0,
    };
    const battle_map_definition map = {
        0xFE,
        4,
        4,
        0,
        16,
    };
    const std::array<battle_map_cell, 16> cells = {};
    battle_scenario_load_policy policy;
    policy.character_levels[1] = 50;
    policy.character_levels[35] = 50;
    battle_condition_variant conditions;
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
                   scenario,
                   map,
                   cells,
                   0,
                   policy,
                   conditions,
                   0xFE09U,
                   roster)
                   .success());
    assert(controller.start().success());
    assert(controller.confirm().success());
    assert(controller.confirm().success());
    assert(controller.confirm().success());

    select_action(controller, 9);
    assert(controller.confirm().success());
    select_action(controller, 5);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_selection);
    assert(controller.move_cursor(1, 0).success());
    const snapshot_type before =
            controller.snapshot();
    const battle_scene_control_result resolved =
            controller.confirm();
    assert(resolved.success());
    assert(resolved.player.impact_count == 5);

    const battle_scene_presentation_event event =
            controller.take_presentation_event();
    assert(event.valid);
    assert(event.has_action);
    assert(event.special_combination);
    assert(event.actor_id == 1);
    assert(event.action_id == 11);
    assert(event.target == grid_point({ 2, 1 }));
    assert(event.impact_count == 5);
    assert(event.has_combatant_vitals);
    assert(event.actor_hp ==
           controller.snapshot().units[0].hp);
    assert(event.actor_max_hp ==
           controller.snapshot().units[0].max_hp);
    assert(event.target_hp_before ==
           before.units[1].hp);
    assert(event.target_hp_after ==
           controller.snapshot().units[1].hp);
    assert(event.target_max_hp ==
           before.units[1].max_hp);
}
