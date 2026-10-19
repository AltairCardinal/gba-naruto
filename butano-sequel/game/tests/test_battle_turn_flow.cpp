#include "konoha/battle_action_system.h"
#include "konoha/battle_mission_rules.h"
#include "konoha/battle_turn_flow.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        grid_point position,
        int hp)
{
    battle_unit_instance result = {
        id,
        side,
        side == battle_side::player ?
                battle_control::player : battle_control::ai,
        position,
        battle_facing::down,
        hp,
        hp,
        10,
        10,
        3,
        true,
        {},
    };
    result.attack = 20;
    result.character_id = id;
    result.original_character_id = id;
    return result;
}

action_definition damage_action(int damage)
{
    return {
        19,
        { action_cost_kind::current_chakra, 1, no_tool_slot },
        { 1 },
        { 1, 0, static_cast<std::uint8_t>(damage), 1, 100, 0 },
        { target_policy_kind::opponent_unit, 0 },
        { 1, 0 },
        {},
    };
}

action_definition restraint_action()
{
    return {
        80,
        { action_cost_kind::current_chakra, 1, no_tool_slot },
        { 5 },
        { 0x3F, 0, 0, 1, 100, 2 },
        { target_policy_kind::opponent_unit, 0 },
        { 4, 1 },
        {},
    };
}

battle_condition_variant defeat_all_enemies()
{
    battle_condition_variant result;
    result.win[0] = {
        battle_condition_type::no_valid_unit_for_side,
        1,
        0,
        0,
    };
    return result;
}

}

int main()
{
    battle_session<3> continuing;
    assert(continuing.add_unit(unit(
            1, battle_side::player, { 1, 1 }, 40)));
    assert(continuing.add_unit(unit(
            2, battle_side::player, { 1, 2 }, 40)));
    assert(continuing.add_unit(unit(
            3, battle_side::enemy, { 2, 1 }, 50)));
    assert(continuing.start_round() ==
           battle_transition::unit_selection_opened);
    assert(continuing.select_unit(1) ==
           battle_transition::action_draft_opened);
    deterministic_rng continuing_rng(1);
    assert(battle_action_resolver::resolve_draft(
                   continuing,
                   3,
                   no_battle_unit,
                   damage_action(10),
                   { 2, 1 },
                   continuing_rng).success());

    const battle_turn_flow_result after_nonlethal =
            battle_turn_flow::after_effects(
                    continuing, defeat_all_enemies());
    assert(after_nonlethal.error == battle_turn_flow_error::none);
    assert(after_nonlethal.outcome ==
           battle_condition_outcome::none);
    assert(after_nonlethal.transition ==
           battle_transition::facing_selection_opened);
    assert(continuing.lifecycle() == battle_lifecycle::facing_select);
    assert(continuing.select_facing(battle_facing::right) ==
           battle_transition::defense_selection_opened);

    const battle_turn_flow_result completed =
            battle_turn_flow::complete_defense(
                    continuing, 7, defeat_all_enemies());
    assert(completed.error == battle_turn_flow_error::none);
    assert(completed.outcome == battle_condition_outcome::none);
    assert(completed.transition == battle_transition::unit_completed);
    assert(continuing.current_side() == battle_side::player);
    assert(continuing.lifecycle() == battle_lifecycle::unit_select);
    assert(continuing.can_issue_commands(2));
    assert(continuing.unit(1)->ledger.defense_ability == 7);

    battle_session<2> interrupted;
    assert(interrupted.add_unit(unit(
            4, battle_side::player, { 1, 1 }, 40)));
    assert(interrupted.add_unit(unit(
            5, battle_side::enemy, { 2, 1 }, 10)));
    assert(interrupted.start_round() ==
           battle_transition::unit_selection_opened);
    assert(interrupted.select_unit(4) ==
           battle_transition::action_draft_opened);
    deterministic_rng lethal_rng(1);
    assert(battle_action_resolver::resolve_draft(
                   interrupted,
                   5,
                   no_battle_unit,
                   damage_action(10),
                   { 2, 1 },
                   lethal_rng).success());

    const battle_turn_flow_result after_lethal =
            battle_turn_flow::after_effects(
                    interrupted, defeat_all_enemies());
    assert(after_lethal.error == battle_turn_flow_error::none);
    assert(after_lethal.outcome == battle_condition_outcome::win);
    assert(after_lethal.ends_battle);
    assert(after_lethal.transition == battle_transition::none);
    assert(interrupted.lifecycle() ==
           battle_lifecycle::effects_resolved);
    assert(! interrupted.unit(4)->ledger.completed);

    battle_session<2> invalid_conditions;
    assert(invalid_conditions.add_unit(unit(
            6, battle_side::player, { 1, 1 }, 40)));
    assert(invalid_conditions.add_unit(unit(
            7, battle_side::enemy, { 2, 1 }, 50)));
    assert(invalid_conditions.start_round() ==
           battle_transition::unit_selection_opened);
    assert(invalid_conditions.select_unit(6) ==
           battle_transition::action_draft_opened);
    deterministic_rng invalid_rng(1);
    assert(battle_action_resolver::resolve_draft(
                   invalid_conditions,
                   7,
                   no_battle_unit,
                   damage_action(10),
                   { 2, 1 },
                   invalid_rng).success());
    battle_condition_variant no_conditions;
    assert(battle_turn_flow::after_effects(
                   invalid_conditions, no_conditions).transition ==
           battle_transition::facing_selection_opened);
    assert(invalid_conditions.select_facing(battle_facing::right) ==
           battle_transition::defense_selection_opened);
    battle_condition_variant unsupported;
    unsupported.win[0].type = battle_condition_type::unused_4;
    const battle_session<2> before_invalid = invalid_conditions;
    const battle_turn_flow_result invalid =
            battle_turn_flow::complete_defense(
                    invalid_conditions, no_ability, unsupported);
    assert(invalid.error == battle_turn_flow_error::condition_error);
    assert(invalid_conditions == before_invalid);

    battle_session<2> object_boundary;
    assert(object_boundary.add_unit(unit(
            8, battle_side::player, { 1, 1 }, 80)));
    battle_unit_instance passive_enemy = unit(
            9, battle_side::enemy, { 3, 2 }, 9);
    passive_enemy.max_hp = 80;
    passive_enemy.base_max_hp = 80;
    assert(passive_enemy.passives.set_slot(0, 24, 1));
    assert(object_boundary.add_unit(passive_enemy));
    battlefield_object_record explosive;
    explosive.type = 1;
    explosive.x = 3;
    explosive.y = 2;
    explosive.payload_id = 67;
    explosive.duration_ticks = 1;
    explosive.source_unit_id = 8;
    assert(object_boundary.objects().allocate(explosive) == 1);
    assert(object_boundary.start_round() ==
           battle_transition::unit_selection_opened);
    assert(object_boundary.select_unit(8) ==
           battle_transition::action_draft_opened);
    action_definition placed_visual = {
        37,
        {},
        { 5 },
        { 0x0C, 0, 0, 1, 100, 2 },
        { target_policy_kind::empty_tile, 0 },
        { 7, 1 },
        {},
    };
    deterministic_rng placement_rng(3);
    assert(battle_action_resolver::resolve_draft(
                   object_boundary,
                   no_battle_unit,
                   no_battle_unit,
                   placed_visual,
                   { 2, 2 },
                   placement_rng).success());
    battle_condition_variant no_enemy =
            defeat_all_enemies();
    assert(battle_turn_flow::after_effects(
                   object_boundary,
                   no_enemy).transition ==
           battle_transition::facing_selection_opened);
    assert(object_boundary.select_facing(
                   battle_facing::down) ==
           battle_transition::defense_selection_opened);
    deterministic_rng boundary_rng(5);
    const battle_turn_flow_result object_completed =
            battle_turn_flow::complete_defense(
                    object_boundary,
                    no_ability,
                    no_enemy,
                    boundary_rng);
    assert(object_completed.error ==
           battle_turn_flow_error::none);
    assert(object_completed.transition ==
           battle_transition::side_changed);
    assert(object_completed.object_event_count == 1);
    assert(object_completed.object_effects.total_damage == 9);
    assert(object_completed.object_effects.target_count == 1);
    assert(object_completed.object_effects
                   .battlefield_object_slot == 1);
    assert(object_completed.outcome ==
           battle_condition_outcome::win);
    assert(object_completed.ends_battle);
    assert(! object_boundary.unit(9)->active);
    assert(object_boundary.side_start_event_count() == 0);
    assert(object_boundary.objects().record(1)->type == 0);
    const battlefield_object_tick_event* resolved_object =
            object_boundary.object_tick_event_at(0);
    assert(resolved_object);
    assert(resolved_object->affected_unit_count == 1);
    assert(resolved_object->affected_unit_ids[0] == 9);
    assert(resolved_object->impact_count == 1);
    assert(resolved_object->total_damage == 9);

    battle_session<2> empty_player_side;
    assert(empty_player_side.add_unit(unit(
            30, battle_side::player, { 1, 1 }, 80)));
    assert(empty_player_side.add_unit(unit(
            31, battle_side::enemy, { 2, 1 }, 80)));
    assert(empty_player_side.start_round() ==
           battle_transition::unit_selection_opened);
    assert(empty_player_side.select_unit(30) ==
           battle_transition::action_draft_opened);
    deterministic_rng empty_side_rng(7);
    assert(battle_action_resolver::resolve_draft(
                   empty_player_side,
                   31,
                   no_battle_unit,
                   damage_action(1),
                   { 2, 1 },
                   empty_side_rng).success());
    assert(battle_turn_flow::after_effects(
                   empty_player_side,
                   no_conditions).transition ==
           battle_transition::facing_selection_opened);
    assert(empty_player_side.select_facing(
                   battle_facing::right) ==
           battle_transition::defense_selection_opened);
    const battle_turn_flow_result player_completed =
            battle_turn_flow::complete_defense(
                    empty_player_side,
                    no_ability,
                    no_conditions,
                    empty_side_rng);
    assert(player_completed.error ==
           battle_turn_flow_error::none);
    assert(player_completed.transition ==
           battle_transition::side_changed);
    assert(empty_player_side.current_side() ==
           battle_side::enemy);

    assert(empty_player_side.select_unit(31) ==
           battle_transition::action_draft_opened);
    assert(battle_action_resolver::resolve_draft(
                   empty_player_side,
                   30,
                   no_battle_unit,
                   restraint_action(),
                   { 1, 1 },
                   empty_side_rng).success());
    assert(battle_turn_flow::after_effects(
                   empty_player_side,
                   no_conditions).transition ==
           battle_transition::facing_selection_opened);
    assert(empty_player_side.select_facing(
                   battle_facing::left) ==
           battle_transition::defense_selection_opened);
    const battle_turn_flow_result enemy_completed =
            battle_turn_flow::complete_defense(
                    empty_player_side,
                    no_ability,
                    no_conditions,
                    empty_side_rng);
    assert(enemy_completed.error ==
           battle_turn_flow_error::none);
    assert(enemy_completed.transition ==
           battle_transition::round_advanced);
    assert(empty_player_side.current_side() ==
           battle_side::player);
    assert(! empty_player_side.can_issue_commands(30));
    const std::uint8_t restrained_slot =
            empty_player_side.unit(30)->statuses.find(0x3F);
    assert(restrained_slot != no_status_slot);
    assert(empty_player_side.unit(30)->statuses
                   .active(restrained_slot)->duration_ticks == 3);

    const battle_turn_flow_result player_skipped =
            battle_turn_flow::advance_empty_side(
                    empty_player_side,
                    no_conditions,
                    empty_side_rng);
    assert(player_skipped.error ==
           battle_turn_flow_error::none);
    assert(player_skipped.transition ==
           battle_transition::side_changed);
    assert(empty_player_side.current_side() ==
           battle_side::enemy);
    assert(empty_player_side.round_index() == 2);
    assert(empty_player_side.can_issue_commands(31));
    assert(empty_player_side.unit(30)->statuses
                   .active(restrained_slot)->duration_ticks == 2);

    const battle_session<2> before_invalid_skip =
            empty_player_side;
    deterministic_rng invalid_skip_rng = empty_side_rng;
    const battle_turn_flow_result invalid_skip =
            battle_turn_flow::advance_empty_side(
                    empty_player_side,
                    no_conditions,
                    empty_side_rng);
    assert(invalid_skip.error ==
           battle_turn_flow_error::invalid_phase);
    assert(empty_player_side == before_invalid_skip);
    assert(empty_side_rng.next_u15() ==
           invalid_skip_rng.next_u15());

    // Resource commands complete without opening a new facing chooser.
    // They still share the same mission-objective action boundary.
    battle_session<2> objective_resource;
    assert(objective_resource.add_unit(unit(
            40, battle_side::player, { 4, 3 }, 80)));
    battle_unit_instance inactive_enemy = unit(
            41, battle_side::enemy, { 4, 6 }, 80);
    inactive_enemy.active = false;
    assert(objective_resource.add_unit(inactive_enemy));
    const battle_mission_objective bells =
            battle_mission_rules_for(44, 0).objective;
    assert(battle_mission_objective_system::initialize(
                   objective_resource, bells) ==
           battle_mission_objective_error::none);
    assert(objective_resource.start_round() ==
           battle_transition::unit_selection_opened);
    assert(objective_resource.select_unit(40) ==
           battle_transition::action_draft_opened);
    const_cast<battle_unit_instance*>(
            objective_resource.unit(40))->hp = 40;
    assert(battle_resource_commands::commit_in_place(
                   objective_resource,
                   battle_resource_command_type::rest)
                   .legal());
    battle_condition_variant bells_condition;
    bells_condition.win[0] = {
        battle_condition_type::object_slot_inactive,
        0,
    };
    deterministic_rng objective_rng(9);
    const battle_turn_flow_result objective_completed =
            battle_turn_flow::complete_non_target_action(
                    objective_resource,
                    bells_condition,
                    objective_rng,
                    bells);
    assert(objective_completed.error ==
           battle_turn_flow_error::none);
    assert(objective_completed.ends_battle);
    assert(objective_completed.outcome ==
           battle_condition_outcome::win);
    assert(objective_resource.objects().record(1)->type == 0);
}
