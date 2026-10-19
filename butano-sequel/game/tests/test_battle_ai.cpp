#include "konoha/battle_ai.h"
#include "konoha/battle_unit_content.h"

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

action_definition data_driven_strike()
{
    action_definition result;
    result.id = 5;
    result.cost = {
        action_cost_kind::current_chakra,
        0,
        no_tool_slot,
    };
    result.presentation = { 1 };
    result.effect = { 1, 0, 10, 1, 98, 0 };
    result.target = { target_policy_kind::opponent_unit, 0 };
    result.range = { 1, 1 };
    return result;
}

int distance(grid_point first, grid_point second)
{
    const int dx = first.x > second.x ? first.x - second.x : second.x - first.x;
    const int dy = first.y > second.y ? first.y - second.y : second.y - first.y;
    return dx + dy;
}

}

int main()
{
    static_assert(
            battle_ai::resource_candidate_kind(
                    battle_resource_command_type::replenish_chakra) ==
            ai_candidate_kind::replenish_chakra);
    static_assert(
            battle_ai::resource_candidate_kind(
                    battle_resource_command_type::rest) ==
            ai_candidate_kind::rest);

    grid_map<5, 5> map;
    const grid_search_bounds edge_bounds =
            battle_ai::candidate_tile_bounds(
                    map, { 0, 4 }, 3);
    assert(edge_bounds.minimum_x == 0);
    assert(edge_bounds.maximum_x == 3);
    assert(edge_bounds.minimum_y == 1);
    assert(edge_bounds.maximum_y == 4);

    std::array units = {
        unit(1, battle_side::enemy, { 0, 2 }, 5),
        unit(2, battle_side::player, { 4, 2 }, 3),
        unit(3, battle_side::enemy, { 1, 2 }, 0),
    };
    for(const battle_unit_instance& value : units)
    {
        assert(map.set_occupied(value.position, value.active));
    }
    const ai_objective attack_target{ true, { 4, 2 }, 2, no_battle_unit };
    deterministic_rng rng(11);
    const action_definition action = data_driven_strike();
    const ai_plan data_driven_plan = battle_ai::plan(
            map, units[0], units, &action, attack_target, rng);
    assert(data_driven_plan.error == ai_error::none);
    assert(data_driven_plan.action == ai_action::ability);
    assert(data_driven_plan.ability == action.id);
    assert(data_driven_plan.target_unit == 2);
    assert(data_driven_plan.facing ==
           battle_ai_candidate_scorer::facing_toward(
                   data_driven_plan.destination,
                   units[1].position,
                   units[0].facing));
    assert(data_driven_plan.destination !=
           units[2].position);
    assert((find_path<5, 5, 25>(
                   map,
                   units[0].position,
                   data_driven_plan.destination,
                   units[0].move_range)
                   .found));
    battle_unit_instance moved_source = units[0];
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

    action_definition duplicate_id_active = action;
    duplicate_id_active.cost.kind =
            action_cost_kind::current_hp;
    action_definition duplicate_id_tool =
            duplicate_id_active;
    duplicate_id_tool.cost = {
        action_cost_kind::battle_local_ninja_tool_slot,
        0,
        2,
    };
    duplicate_id_tool.effect.potency = 30;
    const std::array duplicate_id_choices = {
        duplicate_id_active,
        duplicate_id_tool,
    };
    std::array tool_units = units;
    tool_units[0].move_range = 0;
    tool_units[0].position = { 3, 2 };
    tool_units[0].equipped_tools[2] =
            action.id;
    grid_map<5, 5> tool_map;
    for(const battle_unit_instance& value :
            tool_units)
    {
        assert(tool_map.set_occupied(
                value.position,
                value.active));
    }
    const ai_plan tool_plan = battle_ai::plan(
            tool_map,
            tool_units[0],
            tool_units,
            duplicate_id_choices,
            duplicate_id_choices.size(),
            attack_target,
            rng);
    assert(tool_plan.error == ai_error::none);
    assert(tool_plan.action == ai_action::ability);
    assert(tool_plan.ability == action.id);
    assert(tool_plan.action_kind ==
           battle_action_source_kind::ninja_tool);
    assert(tool_plan.tool_slot == 2);

    std::array autonomous_units = {
        unit(1, battle_side::enemy, { 2, 2 }, 0),
        unit(2, battle_side::player, { 4, 2 }, 3),
        unit(3, battle_side::enemy, { 1, 2 }, 0),
        unit(4, battle_side::player, { 2, 4 }, 3),
    };
    autonomous_units[1].hp = 30;
    autonomous_units[1].max_hp = 30;
    autonomous_units[1].attack = 30;
    autonomous_units[1].defense = 30;
    autonomous_units[1].agility = 30;
    autonomous_units[3].hp = 5;
    autonomous_units[3].max_hp = 5;
    autonomous_units[3].attack = 5;
    autonomous_units[3].defense = 5;
    autonomous_units[3].agility = 5;
    autonomous_units[3].move_range = 1;
    grid_map<5, 5> autonomous_map;
    for(const battle_unit_instance& value : autonomous_units)
    {
        assert(autonomous_map.set_occupied(value.position, value.active));
    }
    action_definition runtime_kind_2_action =
            action;
    runtime_kind_2_action.cost.kind =
            action_cost_kind::current_hp;
    runtime_kind_2_action.range = { 2, 1 };
    action_definition stronger_runtime_kind_2_action =
            stronger_action;
    stronger_runtime_kind_2_action.cost.kind =
            action_cost_kind::current_hp;
    stronger_runtime_kind_2_action.range = { 2, 1 };
    const std::array runtime_kind_2_choices = {
        runtime_kind_2_action,
        stronger_runtime_kind_2_action,
    };
    const ai_plan autonomous_plan = battle_ai::plan(
            autonomous_map,
            autonomous_units[0],
            autonomous_units,
            runtime_kind_2_choices,
            runtime_kind_2_choices.size(),
            {},
            rng);
    assert(autonomous_plan.error == ai_error::none);
    assert(autonomous_plan.action == ai_action::ability);
    // Runtime kind 2 remains a legal selected-action candidate even though it
    // does not enter the kind-1 aggregate damage component.
    assert(autonomous_plan.target_unit == 2 ||
           autonomous_plan.target_unit == 4);
    assert(autonomous_plan.ability ==
                   runtime_kind_2_action.id ||
           autonomous_plan.ability ==
                   stronger_runtime_kind_2_action.id);

    action_definition healing_action = action;
    healing_action.id = 9;
    healing_action.effect = { 0x06, 0, 10, 1, 100, 0 };
    healing_action.target = { target_policy_kind::friendly_unit_policy_1, 0 };
    std::array support_units = {
        unit(10, battle_side::enemy, { 1, 1 }, 1),
        unit(11, battle_side::enemy, { 2, 1 }, 0),
        unit(12, battle_side::player, { 4, 4 }, 0),
    };
    support_units[0].hp = 30;
    support_units[0].max_hp = 30;
    support_units[1].hp = 1;
    support_units[1].max_hp = 20;
    grid_map<5, 5> support_map;
    for(const battle_unit_instance& value : support_units)
    {
        assert(support_map.set_occupied(value.position, value.active));
    }
    const ai_plan support_plan = battle_ai::plan(
            support_map, support_units[0], support_units, &healing_action, {}, rng);
    assert(support_plan.error == ai_error::none);
    assert(support_plan.action == ai_action::ability);
    // Effect low 3 == 6 enables neither target-selector bank in the original
    // scorer. Only healing the acting unit changes its actor projection, so
    // the old per-event friendly-selector heuristic was not ROM-equivalent.
    assert(support_plan.target_unit == 10);

    action_definition restore_action = action;
    restore_action.id = 28;
    restore_action.cost = {
        action_cost_kind::current_hp,
        0,
        no_tool_slot,
    };
    restore_action.effect = { 0x11, 0, 4, 1, 100, 0 };
    restore_action.target = {
        target_policy_kind::self_or_implicit_actor,
        0,
    };
    restore_action.range = { 0, 0 };
    battle_unit_instance restore_actor = instantiate_unit(
            unit_definitions[30],
            13,
            battle_side::enemy,
            battle_control::ai,
            { 4, 10 },
            battle_facing::down);
    restore_actor.move_range = 0;
    restore_actor.hp = restore_actor.max_hp / 2;
    restore_actor.chakra = restore_actor.max_chakra;
    restore_actor.ledger.moved = true;
    battle_unit_instance threat_source = instantiate_unit(
            unit_definitions[1],
            14,
            battle_side::player,
            battle_control::player,
            { 4, 14 },
            battle_facing::up);
    std::array threatened_restore_units = {
        restore_actor,
        threat_source,
    };
    grid_map<9, 22> threatened_restore_map;
    for(const battle_unit_instance& value : threatened_restore_units)
    {
        assert(threatened_restore_map.set_occupied(
                value.position,
                value.active));
    }
    deterministic_rng threatened_plan_rng(211);
    const ai_plan threatened_restore_plan = battle_ai::plan(
            threatened_restore_map,
            threatened_restore_units[0],
            threatened_restore_units,
            &restore_action,
            {},
            threatened_plan_rng);
    assert(threatened_restore_plan.error == ai_error::none);
    assert(threatened_restore_plan.action == ai_action::ability);
    assert(threatened_restore_plan.ability == restore_action.id);

    ai_candidate_field<9, 22> restore_field;
    reachable_cost_result<9, 22> restore_reachable;
    assert(battle_ai_candidate_field_builder::build(
            threatened_restore_map,
            threatened_restore_units[0],
            threatened_restore_units,
            restore_field,
            restore_reachable));
    assert((restore_field.flags(restore_actor.position) &
            ai_candidate_threatened) != 0);

    action_definition neutral_self_action = restore_action;
    neutral_self_action.id = 31;
    neutral_self_action.effect = { 0x21, 0, 4, 1, 100, 3 };
    deterministic_rng neutral_plan_rng(211);
    const ai_plan neutral_self_plan = battle_ai::plan(
            threatened_restore_map,
            threatened_restore_units[0],
            threatened_restore_units,
            &neutral_self_action,
            {},
            neutral_plan_rng);
    assert(neutral_self_plan.error == ai_error::none);
    assert(neutral_self_plan.action == ai_action::ability);
    assert(neutral_self_plan.ability == neutral_self_action.id);
    assert(neutral_self_plan.score > threatened_restore_plan.score);

    battle_unit_instance summon_bonus_actor =
            unit(15, battle_side::enemy, { 0, 0 }, 0);
    summon_bonus_actor.ledger.moved = true;
    summon_bonus_actor.chakra = 10;
    summon_bonus_actor.max_chakra = 10;
    battle_unit_instance summon_bonus_slot =
            unit(16, battle_side::enemy, { 0, 0 }, 0);
    summon_bonus_slot.active = false;
    summon_bonus_slot.hp = 0;
    std::array summon_bonus_units = {
        summon_bonus_actor,
        summon_bonus_slot,
    };
    grid_map<2, 1> summon_bonus_map;
    assert(summon_bonus_map.set_occupied(
            summon_bonus_actor.position,
            true));
    action_definition safe_summon_action;
    safe_summon_action.id = 7;
    safe_summon_action.cost = {
        action_cost_kind::current_chakra,
        3,
        no_tool_slot,
    };
    safe_summon_action.presentation = { 5 };
    safe_summon_action.effect = { 0x07, 0, 0, 1, 100, 0 };
    safe_summon_action.target = {
        target_policy_kind::empty_tile,
        0,
    };
    safe_summon_action.range = { 1, 1 };
    deterministic_rng summon_bonus_rng(313);
    const ai_plan summon_bonus_plan = battle_ai::plan(
            summon_bonus_map,
            summon_bonus_units[0],
            summon_bonus_units,
            &safe_summon_action,
            {},
            summon_bonus_rng);
    assert(summon_bonus_plan.error == ai_error::none);
    assert(summon_bonus_plan.action == ai_action::ability);
    assert(summon_bonus_plan.ability == safe_summon_action.id);
    assert((summon_bonus_plan.target_position == grid_point{ 1, 0 }));
    assert(summon_bonus_plan.score > 6000);

    std::array rule_units = {
        unit(20, battle_side::enemy, { 0, 2 }, 5),
        unit(21, battle_side::player, { 4, 2 }, 0),
    };
    rule_units[0].ai_config_id = 2;
    grid_map<5, 5> rule_map;
    for(const battle_unit_instance& value : rule_units)
    {
        assert(rule_map.set_occupied(value.position, value.active));
    }
    const ai_plan rule_plan = battle_ai::plan(
            rule_map,
            rule_units[0],
            rule_units,
            &action,
            { false, {}, 21, no_battle_unit },
            rng);
    assert(rule_plan.error == ai_error::none);
    assert(rule_plan.action == ai_action::move);
    assert(distance(
                   rule_plan.destination,
                   rule_units[1].position) >
           distance(
                   rule_units[0].position,
                   rule_units[1].position));
    assert(rule_plan.score < 10000);

    std::array move_only_rule_units = {
        unit(24, battle_side::enemy, { 0, 2 }, 5),
        unit(25, battle_side::player, { 4, 2 }, 0),
    };
    move_only_rule_units[0].ai_config_id = 2;
    move_only_rule_units[0].facing =
            battle_facing::right;
    grid_map<5, 5> move_only_rule_map;
    for(const battle_unit_instance& value :
            move_only_rule_units)
    {
        assert(move_only_rule_map.set_occupied(
                value.position,
                value.active));
    }
    deterministic_rng move_only_rule_rng(11);
    const ai_plan move_only_rule_plan =
            battle_ai::plan(
                    move_only_rule_map,
                    move_only_rule_units[0],
                    move_only_rule_units,
                    nullptr,
                    {},
                    move_only_rule_rng);
    assert(move_only_rule_plan.error == ai_error::none);
    assert(move_only_rule_plan.action == ai_action::move);
    assert(distance(
                   move_only_rule_plan.destination,
                   move_only_rule_units[1].position) >
           distance(
                   move_only_rule_units[0].position,
                   move_only_rule_units[1].position));
    assert(move_only_rule_plan.facing ==
           battle_ai_candidate_scorer::facing_toward(
                   move_only_rule_units[0].position,
                   move_only_rule_plan.destination,
                   move_only_rule_units[0].facing));
    grid_map<5, 5> move_only_flag_map =
            move_only_rule_map;
    for(int tile = 0; tile < 25; ++tile)
    {
        assert(move_only_flag_map.set_flags(
                move_only_flag_map.from_index(tile),
                0xF1));
    }
    deterministic_rng move_only_flag_rng(11);
    const ai_plan move_only_flag_plan =
            battle_ai::plan(
                    move_only_flag_map,
                    move_only_rule_units[0],
                    move_only_rule_units,
                    nullptr,
                    {},
                    move_only_flag_rng);
    assert(move_only_flag_plan.error ==
           ai_error::none);
    assert(move_only_flag_plan.action ==
           ai_action::move);
    assert(move_only_flag_plan.destination ==
           move_only_rule_plan.destination);
    assert(move_only_flag_plan.score ==
           move_only_rule_plan.score);

    std::array terrain_units = {
        unit(22, battle_side::enemy, { 0, 2 }, 5),
        unit(23, battle_side::player, { 4, 2 }, 0),
    };
    terrain_units[0].character_id = 30;
    terrain_units[0].original_character_id = 30;
    terrain_units[1].character_id = 1;
    terrain_units[1].original_character_id = 1;
    terrain_units[0].facing = battle_facing::down;
    grid_map<5, 5> terrain_map;
    for(const battle_unit_instance& value : terrain_units)
    {
        assert(terrain_map.set_occupied(
                value.position,
                value.active));
    }
    grid_map<5, 5> unrelated_flag_map = terrain_map;
    for(int tile = 0; tile < 25; ++tile)
    {
        assert(unrelated_flag_map.set_flags(
                unrelated_flag_map.from_index(tile),
                0xF1));
    }
    action_definition ranged_action = action;
    ranged_action.range = { 3, 1 };
    deterministic_rng terrain_rng(41);
    const ai_plan terrain_plan = battle_ai::plan(
            terrain_map,
            terrain_units[0],
            terrain_units,
            &ranged_action,
            { true, { 4, 2 }, 23, no_battle_unit },
            terrain_rng);
    deterministic_rng unrelated_flag_rng(41);
    const ai_plan unrelated_flag_plan = battle_ai::plan(
            unrelated_flag_map,
            terrain_units[0],
            terrain_units,
            &ranged_action,
            { true, { 4, 2 }, 23, no_battle_unit },
            unrelated_flag_rng);
    assert(terrain_plan.error == ai_error::none);
    assert(terrain_plan.action == ai_action::ability);
    assert(distance(
                   terrain_plan.destination,
                   terrain_units[1].position) > 1);
    assert(unrelated_flag_plan.destination ==
           terrain_plan.destination);
    assert(unrelated_flag_plan.score == terrain_plan.score);
    assert(terrain_plan.scoring_position ==
           terrain_plan.destination);

    action_definition summon_action = action;
    summon_action.id = 20;
    summon_action.effect = { 0x02, 0, 0, 1, 100, 0 };
    summon_action.target = { target_policy_kind::empty_tile, 0 };
    summon_action.range = { 3, 0 };
    std::array summon_units = {
        unit(30, battle_side::player, { 1, 1 }, 0),
        unit(31, battle_side::enemy, { 4, 4 }, 0),
        unit(32, battle_side::player, { 0, 0 }, 0),
    };
    summon_units[0].ai_config_id = 5;
    summon_units[0].ai_linked_unit = 0;
    summon_units[2].active = false;
    summon_units[2].hp = 0;
    grid_map<5, 5> summon_map;
    assert(summon_map.set_occupied(summon_units[0].position, true));
    assert(summon_map.set_occupied(summon_units[1].position, true));
    const ai_plan summon_plan = battle_ai::plan(
            summon_map,
            summon_units[0],
            summon_units,
            &summon_action,
            {},
            rng);
    assert(summon_plan.error == ai_error::none);
    assert(summon_plan.action == ai_action::ability);
    assert(summon_plan.target_unit == no_battle_unit);
    assert(summon_plan.summon_unit == 32);
    assert(summon_plan.facing ==
           battle_ai_candidate_scorer::facing_toward(
                   summon_plan.destination,
                   summon_plan.target_position,
                   summon_units[0].facing));
    assert(! summon_map.occupied(summon_plan.target_position));
    assert(distance(summon_plan.destination, summon_plan.target_position) <= 3);

    battle_session<3> summon_session;
    for(const battle_unit_instance& value : summon_units)
    {
        assert(summon_session.add_unit(value));
    }
    assert(summon_session.start_round() == battle_transition::unit_selection_opened);
    assert(summon_session.select_unit(30) == battle_transition::action_draft_opened);
    assert(summon_session.preview_move(summon_plan.destination) ==
            battle_transition::move_previewed);
    deterministic_rng summon_rng(13);
    const action_result summoned = battle_action_resolver::resolve_draft(
            summon_session,
            summon_plan.target_unit,
            summon_plan.summon_unit,
            summon_action,
            summon_plan.target_position,
            summon_rng);
    assert(summoned.success());
    assert(summoned.summoned);
    assert(summon_session.unit(32)->active);
    assert(summon_session.unit(32)->position == summon_plan.target_position);

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

    std::array resource_units = {
        unit(40, battle_side::enemy, { 2, 2 }, 3),
        unit(41, battle_side::player, { 4, 4 }, 0),
    };
    resource_units[0].hp = 100;
    resource_units[0].max_hp = 100;
    resource_units[0].chakra = 0;
    resource_units[0].max_chakra = 10;
    resource_units[0].hand_seals = 1;
    resource_units[0].move_range = 0;
    grid_map<5, 5> resource_map;
    for(const battle_unit_instance& value : resource_units)
    {
        assert(resource_map.set_occupied(
                value.position,
                value.active));
    }
    const std::array<action_definition, 1>
            no_actions = {};
    deterministic_rng chakra_rng(101);
    const ai_plan replenish_plan = battle_ai::plan(
            resource_map,
            resource_units[0],
            resource_units,
            no_actions,
            0,
            {},
            chakra_rng);
    assert(replenish_plan.error == ai_error::none);
    assert(replenish_plan.action ==
           ai_action::replenish_chakra);
    assert(replenish_plan.resource_amount == 10);
    assert(replenish_plan.destination ==
           resource_units[0].position);

    resource_units[0].hp = 10;
    resource_units[0].chakra = 10;
    deterministic_rng rest_rng(102);
    const ai_plan rest_plan = battle_ai::plan(
            resource_map,
            resource_units[0],
            resource_units,
            no_actions,
            0,
            {},
            rest_rng);
    assert(rest_plan.error == ai_error::none);
    assert(rest_plan.action == ai_action::rest);
    assert(rest_plan.resource_amount == 1);
    assert(rest_plan.destination ==
           resource_units[0].position);

    resource_units[0].hp = 100;
    deterministic_rng full_rng(103);
    const ai_plan full_resource_plan = battle_ai::plan(
            resource_map,
            resource_units[0],
            resource_units,
            no_actions,
            0,
            {},
            full_rng);
    assert(full_resource_plan.error == ai_error::none);
    assert(full_resource_plan.action ==
           ai_action::end_action);

    resource_units[0].chakra = 0;
    action_definition decisive_strike =
            data_driven_strike();
    decisive_strike.effect.potency = 100;
    decisive_strike.range = { 4, 1 };
    deterministic_rng attack_over_resource_rng(104);
    const ai_plan attack_over_resource =
            battle_ai::plan(
                    resource_map,
                    resource_units[0],
                    resource_units,
                    &decisive_strike,
                    { false, {}, 41, no_battle_unit },
                    attack_over_resource_rng);
    assert(attack_over_resource.error ==
           ai_error::none);
    // Runtime kind 2 does not receive the kind-1 damage aggregate. Replenish
    // Chakra replenishment is outer candidate kind 2 and therefore receives
    // the proven resource-candidate bias plus the actor chakra-gain component.
    assert(attack_over_resource.action ==
           ai_action::replenish_chakra);
}
