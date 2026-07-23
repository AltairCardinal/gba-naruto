#include "konoha/battle_ai.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id, battle_side side, grid_point position, int move_range)
{
    return {
        id,
        side,
        battle_control::ai,
        position,
        battle_facing::down,
        30,
        30,
        10,
        10,
        move_range,
        true,
        {},
    };
}

ability_definition<2> strike()
{
    ability_definition<2> result;
    result.id = 4;
    result.target = target_rule::enemy_unit;
    result.minimum_range = 1;
    result.maximum_range = 1;
    result.effects[0] = { effect_node_kind::damage, 8, 0 };
    result.effect_count = 1;
    return result;
}

action_definition data_driven_strike()
{
    action_definition result;
    result.id = 5;
    result.cost = { action_cost_kind::current_hp, 0, no_tool_slot };
    result.presentation = { 1 };
    result.effect = { 1, 0, 10, 1, 98, 0 };
    result.target = { target_policy_kind::opponent_unit, 0 };
    result.range = { 1, 1 };
    return result;
}

}

int main()
{
    grid_map<5, 5> map;
    std::array units = {
        unit(1, battle_side::enemy, { 0, 2 }, 5),
        unit(2, battle_side::player, { 4, 2 }, 3),
        unit(3, battle_side::enemy, { 1, 2 }, 0),
    };
    for(const battle_unit_instance& value : units)
    {
        assert(map.set_occupied(value.position, value.active));
    }
    const ability_definition<2> ability = strike();
    const ai_objective attack_target{ true, { 4, 2 }, 2, no_battle_unit };
    deterministic_rng rng(11);
    const ai_plan plan = battle_ai::plan(map, units[0], units, &ability, attack_target, rng);
    assert(plan.error == ai_error::none);
    assert(plan.action == ai_action::ability);
    assert(plan.ability == ability.id);
    assert(plan.target_unit == 2);
    assert(plan.destination != units[2].position);
    assert((find_path<5, 5, 25>(
                   map, units[0].position, plan.destination, units[0].move_range).found));

    battle_unit_instance moved_source = units[0];
    moved_source.position = plan.destination;
    assert(ability_resolver::preview(
                   moved_source, &units[1], nullptr, ability, units[1].position).legal());

    const action_definition action = data_driven_strike();
    const ai_plan data_driven_plan = battle_ai::plan(
            map, units[0], units, &action, attack_target, rng);
    assert(data_driven_plan.error == ai_error::none);
    assert(data_driven_plan.action == ai_action::ability);
    assert(data_driven_plan.ability == action.id);
    moved_source.position = data_driven_plan.destination;
    assert(battle_action_resolver::preview_units(
                   moved_source, &units[1], nullptr, true, action, units[1].position).legal());

    action_definition stronger_action = action;
    stronger_action.id = 6;
    stronger_action.effect.potency = 20;
    const std::array action_choices = { action, stronger_action };
    const ai_plan best_action_plan = battle_ai::plan(
            map, units[0], units, action_choices, action_choices.size(), attack_target, rng);
    assert(best_action_plan.error == ai_error::none);
    assert(best_action_plan.action == ai_action::ability);
    assert(best_action_plan.ability == stronger_action.id);

    const ai_objective missing_protected{ true, { 4, 2 }, 2, 99 };
    const ai_plan invalid_protected = battle_ai::plan(
            map, units[0], units, &action, missing_protected, rng);
    assert(invalid_protected.error == ai_error::invalid_objective);

    grid_map<5, 5> open_map;
    assert(open_map.set_occupied(units[0].position, true));
    const ai_objective escort_left{ true, { 0, 4 }, no_battle_unit, 3 };
    const ai_plan escort_plan =
            battle_ai::plan(open_map, units[0], units, nullptr, escort_left, rng);
    assert(escort_plan.action == ai_action::move);
    const int before_distance = 2;
    const int after_distance = escort_plan.destination.x +
            (escort_plan.destination.y > 4 ? escort_plan.destination.y - 4 :
                                             4 - escort_plan.destination.y);
    assert(after_distance < before_distance);

    battle_unit_instance trapped = unit(7, battle_side::enemy, { 2, 2 }, 0);
    trapped.ledger.moved = true;
    const std::array trapped_roster = { trapped };
    grid_map<5, 5> trapped_map;
    assert(trapped_map.set_occupied(trapped.position, true));
    const ai_plan safe_end = battle_ai::plan(
            trapped_map, trapped, trapped_roster, nullptr, {}, rng);
    assert(safe_end.error == ai_error::none);
    assert(safe_end.action == ai_action::end_action);
}
