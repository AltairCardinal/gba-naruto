#ifndef KONOHA_BATTLE_AI_H
#define KONOHA_BATTLE_AI_H

#include "konoha/battle_action_catalog.h"
#include "konoha/battle_action_system.h"
#include "konoha/battle_ai_candidate_field.h"
#include "konoha/battle_ai_candidate_score.h"
#include "konoha/battle_ai_scenario_rules.h"
#include "konoha/battle_ai_utility.h"
#include "konoha/battle_commands.h"
#include "konoha/battle_resource_commands.h"
#include "konoha/battle_terrain_traversal.h"
#include "konoha/grid_pathfinder.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace konoha
{

enum class ai_action : std::uint8_t
{
    end_action,
    move,
    ability,
    replenish_chakra,
    rest,
};

enum class ai_error : std::uint8_t
{
    none,
    invalid_unit,
    invalid_objective,
};

struct ai_objective
{
    bool has_focus_position = false;
    grid_point focus_position = {};
    battle_unit_id target_unit = no_battle_unit;
    battle_unit_id protected_unit = no_battle_unit;
    int focus_position_weight = 1;
};

struct ai_candidate
{
    ai_action action = ai_action::end_action;
    grid_point destination = {};
    grid_point target_position = {};
    grid_point scoring_position = {};
    battle_facing facing = battle_facing::up;
    battle_unit_id target_unit = no_battle_unit;
    battle_unit_id summon_unit = no_battle_unit;
    ability_id ability = no_ability;
    battle_action_source_kind action_kind =
            battle_action_source_kind::active_action;
    std::uint8_t tool_slot = no_tool_slot;
    std::uint8_t action_index = 0xFF;
    int resource_amount = 0;
    int target_count = 0;
    int score = 0;
};

struct ai_plan : ai_candidate
{
    ai_error error = ai_error::none;
};

struct grid_search_bounds
{
    int minimum_x = 0;
    int maximum_x = 0;
    int minimum_y = 0;
    int maximum_y = 0;
};

template<std::size_t UnitCount, int Width, int Height>
struct battle_ai_plan_workspace
{
    reachable_cost_result<Width, Height> reachable;
    reachable_cost_result<Width, Height> threat_reachable;
    ai_candidate_field<Width, Height> candidate_field;
    std::array<battle_unit_instance, UnitCount> simulated_units = {};
    std::array<battle_unit_instance, UnitCount> projected_units = {};
    std::array<ai_queued_event, UnitCount> queued_events = {};
};

class battle_ai
{
public:
    [[nodiscard]] static constexpr ai_candidate_kind
    resource_candidate_kind(battle_resource_command_type type)
    {
        return type ==
                       battle_resource_command_type::
                               replenish_chakra ?
                ai_candidate_kind::replenish_chakra :
                ai_candidate_kind::rest;
    }

    template<int Width, int Height>
    [[nodiscard]] static constexpr grid_search_bounds
    candidate_tile_bounds(
            const grid_map<Width, Height>& map,
            grid_point origin,
            int maximum_distance)
    {
        grid_search_bounds result = {
            origin.x - maximum_distance,
            origin.x + maximum_distance,
            origin.y - maximum_distance,
            origin.y + maximum_distance,
        };
        if(result.minimum_x < 0)
        {
            result.minimum_x = 0;
        }
        if(result.maximum_x >= map.active_width())
        {
            result.maximum_x = map.active_width() - 1;
        }
        if(result.minimum_y < 0)
        {
            result.minimum_y = 0;
        }
        if(result.maximum_y >= map.active_height())
        {
            result.maximum_y = map.active_height() - 1;
        }
        return result;
    }

    template<int Width, int Height, std::size_t UnitCount>
    [[nodiscard]] static ai_plan plan(
            const grid_map<Width, Height>& map,
            const battle_unit_instance& acting_unit,
            const std::array<battle_unit_instance, UnitCount>& units,
            const action_definition* action,
            ai_objective objective,
            deterministic_rng& rng)
    {
        std::array<action_definition, 1> choices = {};
        std::size_t choice_count = 0;
        if(action)
        {
            choices[0] = *action;
            choice_count = 1;
        }
        return plan(map, acting_unit, units, choices, choice_count, objective, rng);
    }

    template<int Width, int Height, std::size_t UnitCount, std::size_t ActionCapacity>
    [[nodiscard, gnu::noinline]] static ai_plan plan(
            const grid_map<Width, Height>& map,
            const battle_unit_instance& acting_unit,
            const std::array<battle_unit_instance, UnitCount>& units,
            const std::array<action_definition, ActionCapacity>& actions,
            std::size_t action_count,
            ai_objective objective,
            deterministic_rng& rng)
    {
        battle_ai_plan_workspace<UnitCount, Width, Height>
                workspace;
        return plan(
                map,
                acting_unit,
                units,
                actions,
                action_count,
                objective,
                rng,
                workspace);
    }

    template<int Width, int Height, std::size_t UnitCount, std::size_t ActionCapacity>
    [[nodiscard, gnu::noinline]] static ai_plan plan(
            const grid_map<Width, Height>& map,
            const battle_unit_instance& acting_unit,
            const std::array<battle_unit_instance, UnitCount>& units,
            const std::array<action_definition, ActionCapacity>& actions,
            std::size_t action_count,
            ai_objective objective,
            deterministic_rng& rng,
            battle_ai_plan_workspace<UnitCount, Width, Height>&
                    workspace)
    {
        static_assert(UnitCount > 0);
        static_assert(ActionCapacity > 0);
        if(! acting_unit.active || acting_unit.ledger.completed)
        {
            ai_plan result;
            result.error = ai_error::invalid_unit;
            return result;
        }
        const battle_unit_instance* target = _find_unit(units, objective.target_unit);
        if(objective.target_unit != no_battle_unit && (! target || ! target->active))
        {
            ai_plan result;
            result.error = ai_error::invalid_objective;
            return result;
        }
        if(objective.protected_unit != no_battle_unit &&
                ! _find_unit(units, objective.protected_unit))
        {
            ai_plan result;
            result.error = ai_error::invalid_objective;
            return result;
        }
        if(action_count > ActionCapacity)
        {
            ai_plan result;
            result.error = ai_error::invalid_objective;
            return result;
        }
        if(acting_unit.ai_config_id >= ai_scenario_rule_configs.size())
        {
            ai_plan result;
            result.error = ai_error::invalid_objective;
            return result;
        }
        const ai_utility_policy& utility_policy =
                ai_utility_policies[acting_unit.ai_config_id];

        ai_plan best;
        best.destination = acting_unit.position;
        best.facing = acting_unit.facing;
        best.score = std::numeric_limits<int>::min();
        (void) battle_ai_candidate_field_builder::build(
                map,
                acting_unit,
                units,
                workspace.candidate_field,
                workspace.threat_reachable);
        workspace.reachable = compute_reachable_costs(
                map,
                acting_unit.position,
                acting_unit.move_range,
                battle_terrain_traversal_limits(
                        acting_unit.passives));
        const reachable_cost_result<Width, Height>& reachable =
                workspace.reachable;
        if(! reachable.valid)
        {
            best.error = ai_error::invalid_unit;
            return best;
        }
        const command_availability move_availability = command_eligibility_service::query(
                acting_unit, { battle_command_type::move });
        int maximum_action_range = 0;
        for(std::size_t action_index = 0; action_index < action_count; ++action_index)
        {
            if(actions[action_index].range.maximum_distance() > maximum_action_range)
            {
                maximum_action_range = actions[action_index].range.maximum_distance();
            }
        }
        for(int destination_index = 0; destination_index < Width * Height; ++destination_index)
        {
            const grid_point destination = map.from_index(destination_index);
            if(reachable.cost(destination) < 0 ||
                    (destination != acting_unit.position && ! move_availability.available()))
            {
                continue;
            }
            workspace.simulated_units = units;
            std::array<battle_unit_instance, UnitCount>&
                    simulated_units = workspace.simulated_units;
            const std::size_t actor_index = _find_unit_index(simulated_units, acting_unit.id);
            if(actor_index == UnitCount)
            {
                ai_plan result;
                result.error = ai_error::invalid_unit;
                return result;
            }
            battle_unit_instance& simulated = simulated_units[actor_index];
            simulated.position = destination;
            const int position_score = objective.has_focus_position ?
                    (100 - _distance(
                             map.battle_id(),
                             destination,
                             objective.focus_position)) *
                            objective.focus_position_weight :
                    0;
            ai_plan destination_best;
            destination_best.destination = destination;
            destination_best.scoring_position =
                    destination;
            destination_best.facing =
                    acting_unit.facing;
            destination_best.score =
                    std::numeric_limits<int>::min();
            const ai_target_index target_index = battle_ai_target_index_builder::build(
                    map,
                    simulated,
                    simulated_units);
            if(destination == acting_unit.position)
            {
                if(action_count == 0 &&
                        ! objective.has_focus_position &&
                        ! battle_resource_commands::preview(
                                   simulated,
                                   battle_resource_command_type::
                                           replenish_chakra,
                                   1)
                                   .legal() &&
                        ! battle_resource_commands::preview(
                                   simulated,
                                   battle_resource_command_type::
                                           rest)
                                   .legal())
                {
                    workspace.projected_units =
                            simulated_units;
                    const std::array<ai_queued_event, 1>
                            no_events = {};
                    const ai_actor_projection projection = {
                        simulated.hp,
                        simulated.hp,
                        simulated.max_hp,
                        simulated.chakra,
                        simulated.chakra,
                        simulated.max_chakra,
                        maximum_action_range,
                        (workspace.candidate_field.flags(
                                 destination) &
                         ai_candidate_threatened) != 0,
                        _has_active_scenario_rule(
                                ai_scenario_rule_configs[
                                        acting_unit.ai_config_id]),
                    };
                    const ai_scenario_rule_context
                            rule_context = {
                                acting_unit.position,
                                destination,
                                acting_unit.move_range,
                                workspace.candidate_field.flags(
                                        destination),
                                map.tile_class(destination),
                                map.tile_side(destination) == 0 ?
                                        battle_side::player :
                                        battle_side::enemy,
                                acting_unit.side,
                                map.battle_id(),
                            };
                    const ai_utility_components
                            scenario_rule_components =
                                    battle_ai_scenario_rule_scorer::
                                            score(
                                                    simulated,
                                                    workspace.
                                                            projected_units,
                                                    no_events,
                                                    0,
                                                    ai_scenario_rule_configs[
                                                            acting_unit.
                                                                    ai_config_id],
                                                    rule_context);
                    const ai_utility_score utility =
                            battle_ai_utility_scorer::score(
                                    simulated,
                                    projection,
                                    {
                                        false,
                                        0,
                                        0,
                                        ai_candidate_kind::none,
                                    },
                                    workspace.projected_units,
                                    target_index,
                                    no_events,
                                    0,
                                    utility_policy,
                                    rng,
                                    scenario_rule_components);
                    ai_candidate candidate;
                    candidate.action =
                            ai_action::end_action;
                    candidate.destination =
                            destination;
                    candidate.scoring_position =
                            destination;
                    candidate.facing =
                            acting_unit.facing;
                    candidate.score =
                            utility.score +
                            position_score;
                    _consider(candidate, destination_best);
                }

                const battle_resource_command_preview
                        first_replenish =
                                battle_resource_commands::
                                        preview(
                                                simulated,
                                                battle_resource_command_type::
                                                        replenish_chakra,
                                                1);
                if(first_replenish.legal())
                {
                    for(int amount = 1;
                            amount <=
                                    first_replenish.
                                            maximum_amount;
                            ++amount)
                    {
                        const battle_resource_command_preview
                                preview =
                                        battle_resource_commands::
                                                preview(
                                                        simulated,
                                                        battle_resource_command_type::
                                                                replenish_chakra,
                                                        amount);
                        if(! preview.legal())
                        {
                            continue;
                        }
                        const ai_scenario_rule_context
                                rule_context = {
                                    acting_unit.position,
                                    destination,
                                    acting_unit.move_range,
                                    workspace.candidate_field.flags(
                                            destination),
                                    map.tile_class(destination),
                                    map.tile_side(destination) ==
                                                    0 ?
                                            battle_side::
                                                    player :
                                            battle_side::
                                                    enemy,
                                    acting_unit.side,
                                    map.battle_id(),
                                };
                        ai_candidate candidate;
                        candidate.action =
                                ai_action::
                                        replenish_chakra;
                        candidate.destination =
                                destination;
                        candidate.scoring_position =
                                destination;
                        candidate.facing =
                                acting_unit.facing;
                        candidate.resource_amount =
                                amount;
                        candidate.score =
                                _score_resource(
                                        simulated,
                                        preview,
                                        battle_resource_command_type::
                                                replenish_chakra,
                                        simulated_units,
                                        workspace.projected_units,
                                        actor_index,
                                        target_index,
                                        maximum_action_range,
                                        utility_policy,
                                        ai_scenario_rule_configs[
                                                acting_unit.
                                                        ai_config_id],
                                        rule_context,
                                        rng) +
                                position_score;
                        _consider(
                                candidate,
                                destination_best);
                    }
                }

                const battle_resource_command_preview
                        rest_preview =
                                battle_resource_commands::
                                        preview(
                                                simulated,
                                                battle_resource_command_type::
                                                        rest);
                if(rest_preview.legal())
                {
                    const ai_scenario_rule_context
                            rule_context = {
                                acting_unit.position,
                                destination,
                                acting_unit.move_range,
                                workspace.candidate_field.flags(
                                        destination),
                                map.tile_class(destination),
                                map.tile_side(destination) == 0 ?
                                        battle_side::player :
                                        battle_side::enemy,
                                acting_unit.side,
                                map.battle_id(),
                            };
                    ai_candidate candidate;
                    candidate.action = ai_action::rest;
                    candidate.destination = destination;
                    candidate.scoring_position =
                            destination;
                    candidate.facing =
                            acting_unit.facing;
                    candidate.resource_amount = 1;
                    candidate.score =
                            _score_resource(
                                    simulated,
                                    rest_preview,
                                    battle_resource_command_type::rest,
                                    simulated_units,
                                    workspace.projected_units,
                                    actor_index,
                                    target_index,
                                    maximum_action_range,
                                    utility_policy,
                                    ai_scenario_rule_configs[
                                            acting_unit.
                                                    ai_config_id],
                                    rule_context,
                                    rng) +
                            position_score;
                    _consider(
                            candidate,
                            destination_best);
                }
            }
            for(std::size_t action_index = 0; action_index < action_count; ++action_index)
            {
                const action_definition& action = actions[action_index];
                const effect_handler_kind handler =
                        effect_resolver_registry::handler_for(action.effect.code);
                if(action.target.kind == target_policy_kind::empty_tile)
                {
                    const bool summons =
                            handler == effect_handler_kind::summon ||
                            handler == effect_handler_kind::summon_variant ||
                            handler == effect_handler_kind::summon_pair;
                    const std::size_t summon_index =
                            summons ?
                            _find_inactive_unit_index(simulated_units) : UnitCount;
                    if(summons && (summon_index == UnitCount ||
                            (handler == effect_handler_kind::summon_pair &&
                             _inactive_unit_count(simulated_units) < 2)))
                    {
                        continue;
                    }
                    const grid_search_bounds target_bounds =
                            candidate_tile_bounds(
                                    map,
                                    simulated.position,
                                    action.range.maximum_distance());
                    for(int target_y = target_bounds.minimum_y;
                        target_y <= target_bounds.maximum_y;
                        ++target_y)
                    {
                        for(int target_x = target_bounds.minimum_x;
                            target_x <= target_bounds.maximum_x;
                            ++target_x)
                        {
                            const grid_point target_position = {
                                target_x,
                                target_y,
                            };
                            if(map.cost(target_position) == 0 ||
                                    map.terrain_class(
                                            target_position) ==
                                            grid_fully_closed ||
                                    _occupied(
                                            simulated_units,
                                            target_position))
                            {
                                continue;
                            }
                            const battle_unit_instance* summon =
                                    summon_index == UnitCount ?
                                    nullptr : &simulated_units[summon_index];
                            const action_preview preview =
                                    battle_action_resolver::preview_units(
                                            simulated,
                                            nullptr,
                                            summon,
                                            false,
                                            action,
                                            target_position);
                            if(! preview.legal())
                            {
                                continue;
                            }
                            battle_unit_instance projected_actor = simulated;
                            _project_cost(projected_actor, action.cost);
                            if(handler == effect_handler_kind::move)
                            {
                                projected_actor.position = target_position;
                            }
                            workspace.projected_units =
                                    simulated_units;
                            std::array<battle_unit_instance, UnitCount>&
                                    projected_units =
                                            workspace.projected_units;
                            projected_units[actor_index] = projected_actor;
                            const std::array queued_events = {
                                ai_queued_event{
                                    action.id,
                                    static_cast<std::uint8_t>(
                                            action.effect.code | action.effect.flags),
                                    no_battle_unit,
                                    action.effect.potency,
                                    preview.hit_count,
                                    preview.success_rate_percent,
                                    _distance(
                                            map.battle_id(),
                                            simulated.position,
                                            target_position),
                                    (workspace.candidate_field.flags(
                                             target_position) &
                                     ai_candidate_threatened) != 0,
                                    false,
                                },
                            };
                            const ai_actor_projection projection = {
                                simulated.hp,
                                projected_actor.hp,
                                projected_actor.max_hp,
                                simulated.chakra,
                                projected_actor.chakra,
                                projected_actor.max_chakra,
                                maximum_action_range,
                                (workspace.candidate_field.flags(
                                         projected_actor.position) &
                                 ai_candidate_threatened) != 0,
                                _has_active_scenario_rule(
                                        ai_scenario_rule_configs[
                                                acting_unit.ai_config_id]),
                            };
                            const grid_point effective_position =
                                    handler == effect_handler_kind::move ?
                                    target_position : destination;
                            const int effective_position_score =
                                    objective.has_focus_position ?
                                    100 - _distance(
                                            map.battle_id(),
                                            effective_position,
                                            objective.focus_position) :
                                    0;
                            const ai_scenario_rule_context rule_context = {
                                acting_unit.position,
                                effective_position,
                                acting_unit.move_range,
                                workspace.candidate_field.flags(
                                        effective_position),
                                map.tile_class(effective_position),
                                map.tile_side(effective_position) == 0 ?
                                        battle_side::player : battle_side::enemy,
                                acting_unit.side,
                                map.battle_id(),
                            };
                            const ai_utility_components
                                    scenario_rule_components =
                                    battle_ai_scenario_rule_scorer::score(
                                            projected_actor,
                                            projected_units,
                                            queued_events,
                                            queued_events.size(),
                                            ai_scenario_rule_configs[
                                                    acting_unit.ai_config_id],
                                            rule_context);
                            const ai_utility_score utility =
                                    battle_ai_utility_scorer::score(
                                            projected_actor,
                                            projection,
                                            _action_projection(action),
                                            projected_units,
                                            target_index,
                                            queued_events,
                                            queued_events.size(),
                                            utility_policy,
                                            rng,
                                            scenario_rule_components);
                            ai_candidate candidate;
                            candidate.action = ai_action::ability;
                            candidate.destination = destination;
                            candidate.target_position = target_position;
                            candidate.scoring_position =
                                    effective_position;
                            candidate.facing =
                                    battle_ai_candidate_scorer::
                                            facing_toward(
                                                    destination,
                                                    target_position,
                                                    acting_unit.facing);
                            candidate.summon_unit = summon_index == UnitCount ?
                                    no_battle_unit : simulated_units[summon_index].id;
                            candidate.ability = action.id;
                            candidate.action_kind =
                                    _source_kind(action.cost);
                            candidate.tool_slot =
                                    action.cost.tool_slot;
                            candidate.action_index =
                                    static_cast<std::uint8_t>(
                                            action_index);
                            candidate.score =
                                    utility.score +
                                    effective_position_score;
                            _consider(
                                    candidate,
                                    destination_best);
                        }
                    }
                    continue;
                }
                for(std::size_t target_index_value = 0;
                    target_index_value < UnitCount;
                    ++target_index_value)
                {
                    battle_unit_instance* candidate_target =
                            &simulated_units[target_index_value];
                    if(! _target_matches(
                               simulated,
                               *candidate_target,
                               action.target.kind,
                               objective.target_unit))
                    {
                        continue;
                    }
                    const action_preview center_preview =
                            battle_action_resolver::preview_units(
                            simulated,
                            candidate_target,
                            nullptr,
                            true,
                            action,
                            candidate_target->position);
                    if(! center_preview.legal())
                    {
                        continue;
                    }

                    const battle_target_set<UnitCount> area_targets =
                            battle_action_targeting::collect(
                                    simulated,
                                    simulated_units,
                                    action.target,
                                    action.range,
                                    candidate_target->position);
                    if(area_targets.count == 0)
                    {
                        continue;
                    }
                    workspace.queued_events = {};
                    std::array<ai_queued_event, UnitCount>&
                            queued_events =
                                    workspace.queued_events;
                    std::size_t queued_event_count = 0;
                    action_definition per_target_action = action;
                    per_target_action.range.distance_and_line_flags = 0x7F;
                    battle_unit_instance projected_actor = simulated;
                    _project_cost(projected_actor, action.cost);
                    bool legal_area = true;
                    for(std::size_t area_index = 0;
                        area_index < area_targets.count;
                        ++area_index)
                    {
                        const std::size_t area_target_index = _find_unit_index(
                                simulated_units, area_targets.ids[area_index]);
                        battle_unit_instance* area_target =
                                &simulated_units[area_target_index];
                        const action_preview preview =
                                battle_action_resolver::preview_units(
                                        simulated,
                                        area_target,
                                        nullptr,
                                        true,
                                        per_target_action,
                                        area_target->position);
                        if(! preview.legal())
                        {
                            legal_area = false;
                            break;
                        }
                        if(handler == effect_handler_kind::heal_percent &&
                                area_target->id == simulated.id)
                        {
                            projected_actor.hp += preview.healing;
                            if(projected_actor.hp > projected_actor.max_hp)
                            {
                                projected_actor.hp = projected_actor.max_hp;
                            }
                        }
                        queued_events[queued_event_count] = {
                            action.id,
                            static_cast<std::uint8_t>(
                                    action.effect.code | action.effect.flags),
                            area_target->id,
                            handler == effect_handler_kind::damage ?
                                    preview.damage_per_hit :
                                    (handler == effect_handler_kind::heal_percent ?
                                     preview.healing : action.effect.potency),
                            preview.hit_count,
                            preview.success_rate_percent,
                            _distance(
                                    map.battle_id(),
                                    simulated.position,
                                    area_target->position),
                        };
                        ++queued_event_count;
                    }
                    if(! legal_area)
                    {
                        continue;
                    }
                    workspace.projected_units =
                            simulated_units;
                    std::array<battle_unit_instance, UnitCount>&
                            projected_units =
                                    workspace.projected_units;
                    projected_units[actor_index] = projected_actor;
                    const ai_actor_projection projection = {
                        simulated.hp,
                        projected_actor.hp,
                        projected_actor.max_hp,
                        simulated.chakra,
                        projected_actor.chakra,
                        projected_actor.max_chakra,
                        maximum_action_range,
                        (workspace.candidate_field.flags(
                                 projected_actor.position) &
                         ai_candidate_threatened) != 0,
                        _has_active_scenario_rule(
                                ai_scenario_rule_configs[
                                        acting_unit.ai_config_id]),
                    };
                    const ai_scenario_rule_context rule_context = {
                        acting_unit.position,
                        destination,
                        acting_unit.move_range,
                        workspace.candidate_field.flags(
                                destination),
                        map.tile_class(destination),
                        map.tile_side(destination) == 0 ?
                                battle_side::player : battle_side::enemy,
                        acting_unit.side,
                        map.battle_id(),
                    };
                    const ai_utility_components
                            scenario_rule_components =
                            battle_ai_scenario_rule_scorer::score(
                                    projected_actor,
                                    projected_units,
                                    queued_events,
                                    queued_event_count,
                                    ai_scenario_rule_configs[acting_unit.ai_config_id],
                                    rule_context);
                    const ai_utility_score utility =
                            battle_ai_utility_scorer::score(
                                    projected_actor,
                                    projection,
                                    _action_projection(action),
                                    projected_units,
                                    target_index,
                                    queued_events,
                                    queued_event_count,
                                    utility_policy,
                                    rng,
                                    scenario_rule_components);
                    ai_candidate candidate;
                    candidate.action = ai_action::ability;
                    candidate.destination = destination;
                    candidate.target_position = candidate_target->position;
                    candidate.scoring_position =
                            destination;
                    candidate.facing =
                            battle_ai_candidate_scorer::
                                    facing_toward(
                                            destination,
                                            candidate_target->position,
                                            acting_unit.facing);
                    candidate.target_unit = candidate_target->id;
                    candidate.ability = action.id;
                    candidate.action_kind =
                            _source_kind(action.cost);
                    candidate.tool_slot =
                            action.cost.tool_slot;
                    candidate.action_index =
                            static_cast<std::uint8_t>(
                                    action_index);
                    candidate.target_count =
                            static_cast<int>(area_targets.count);
                    candidate.score =
                            utility.score +
                            position_score;
                    _consider(candidate, destination_best);
                }
            }
            if(destination != acting_unit.position)
            {
                workspace.projected_units =
                        simulated_units;
                const std::array<ai_queued_event, 1>
                        no_events = {};
                const ai_actor_projection projection = {
                    simulated.hp,
                    simulated.hp,
                    simulated.max_hp,
                    simulated.chakra,
                    simulated.chakra,
                    simulated.max_chakra,
                    maximum_action_range,
                    (workspace.candidate_field.flags(
                             destination) &
                     ai_candidate_threatened) != 0,
                    _has_active_scenario_rule(
                            ai_scenario_rule_configs[
                                    acting_unit.ai_config_id]),
                };
                const ai_scenario_rule_context
                        rule_context = {
                            acting_unit.position,
                            destination,
                            acting_unit.move_range,
                            workspace.candidate_field.flags(
                                    destination),
                            map.tile_class(destination),
                            map.tile_side(destination) == 0 ?
                                    battle_side::player :
                                    battle_side::enemy,
                            acting_unit.side,
                            map.battle_id(),
                        };
                const ai_utility_components
                        scenario_rule_components =
                                battle_ai_scenario_rule_scorer::
                                        score(
                                                simulated,
                                                workspace.
                                                        projected_units,
                                                no_events,
                                                0,
                                                ai_scenario_rule_configs[
                                                        acting_unit.
                                                                ai_config_id],
                                                rule_context);
                const ai_utility_score utility =
                        battle_ai_utility_scorer::score(
                                simulated,
                                projection,
                                {
                                    false,
                                    0,
                                    0,
                                    ai_candidate_kind::move,
                                },
                                workspace.projected_units,
                                target_index,
                                no_events,
                                0,
                                utility_policy,
                                rng,
                                scenario_rule_components);
                ai_candidate candidate;
                candidate.action = ai_action::move;
                candidate.destination = destination;
                candidate.scoring_position =
                        destination;
                // S49 original frame 18: the unit that walked two cells east
                // ends up facing east, not facing its focus position.  A unit
                // that has only moved faces the way it moved; the focus
                // position steers where it goes, not where it looks.
                candidate.facing =
                        battle_ai_candidate_scorer::
                                facing_toward(
                                        acting_unit.position,
                                        destination,
                                        acting_unit.facing);
                candidate.score =
                        utility.score +
                        position_score;
                _consider(candidate, destination_best);
            }
            if(destination_best.score !=
                    std::numeric_limits<int>::min())
            {
                destination_best.score +=
                        battle_ai_candidate_scorer::
                                score_tile(
                                        acting_unit.facing,
                                        destination_best.facing,
                                        workspace.candidate_field.flags(
                                                destination_best.
                                                        scoring_position),
                                        rng)
                                .total();
                _consider(destination_best, best);
            }
        }
        if(best.score == std::numeric_limits<int>::min())
        {
            best.action = ai_action::end_action;
            best.destination = acting_unit.position;
            best.score = 0;
        }
        return best;
    }

private:
    template<std::size_t UnitCount>
    [[nodiscard]] static int _score_resource(
            const battle_unit_instance& actor,
            const battle_resource_command_preview& preview,
            battle_resource_command_type resource_type,
            const std::array<battle_unit_instance, UnitCount>&
                    units,
            std::array<battle_unit_instance, UnitCount>&
                    projected_units,
            std::size_t actor_index,
            const ai_target_index& target_index,
            int maximum_action_range,
            const ai_utility_policy& utility_policy,
            const ai_scenario_rule_config& rule_config,
            const ai_scenario_rule_context& rule_context,
            deterministic_rng& rng)
    {
        battle_unit_instance projected_actor = actor;
        projected_actor.hp += preview.hp_delta;
        projected_actor.chakra += preview.chakra_delta;
        projected_units = units;
        projected_units[actor_index] = projected_actor;
        const std::array<ai_queued_event, 1> no_events = {};
        const ai_actor_projection projection = {
            actor.hp,
            projected_actor.hp,
            projected_actor.max_hp,
            actor.chakra,
            projected_actor.chakra,
            projected_actor.max_chakra,
            maximum_action_range,
        };
        const ai_utility_components scenario_rule_components =
                battle_ai_scenario_rule_scorer::score(
                        projected_actor,
                        projected_units,
                        no_events,
                        0,
                        rule_config,
                        rule_context);
        return battle_ai_utility_scorer::score(
                       projected_actor,
                       projection,
                       {
                           false,
                           0,
                           0,
                           resource_candidate_kind(resource_type),
                       },
                       projected_units,
                       target_index,
                       no_events,
                       0,
                       utility_policy,
                       rng,
                       scenario_rule_components)
                .score;
    }

    [[nodiscard]] static constexpr battle_action_source_kind
    _source_kind(const cost_policy& cost)
    {
        return cost.kind ==
                       action_cost_kind::
                               battle_local_ninja_tool_slot ?
                battle_action_source_kind::ninja_tool :
                battle_action_source_kind::active_action;
    }

    [[nodiscard]] static constexpr bool
    _has_active_scenario_rule(
            const ai_scenario_rule_config& config)
    {
        for(const ai_scenario_rule& rule : config.rules)
        {
            if(rule.kind >= 1 && rule.kind <= 5)
            {
                return true;
            }
        }
        return false;
    }

    [[nodiscard]] static constexpr ai_action_projection
    _action_projection(const action_definition& action)
    {
        return {
            true,
            static_cast<std::uint8_t>(action.cost.kind),
            action.effect.code,
            ai_candidate_kind::selected_action,
        };
    }

    template<std::size_t UnitCount>
    [[nodiscard]] static std::size_t _find_unit_index(
            const std::array<battle_unit_instance, UnitCount>& units,
            battle_unit_id id)
    {
        for(std::size_t index = 0; index < UnitCount; ++index)
        {
            if(units[index].id == id)
            {
                return index;
            }
        }
        return UnitCount;
    }

    template<std::size_t UnitCount>
    [[nodiscard]] static std::size_t _find_inactive_unit_index(
            const std::array<battle_unit_instance, UnitCount>& units)
    {
        for(std::size_t index = 0; index < UnitCount; ++index)
        {
            if(! units[index].active)
            {
                return index;
            }
        }
        return UnitCount;
    }

    template<std::size_t UnitCount>
    [[nodiscard]] static std::size_t _inactive_unit_count(
            const std::array<battle_unit_instance, UnitCount>& units)
    {
        std::size_t result = 0;
        for(const battle_unit_instance& unit : units)
        {
            result += ! unit.active;
        }
        return result;
    }

    template<std::size_t UnitCount>
    [[nodiscard]] static bool _occupied(
            const std::array<battle_unit_instance, UnitCount>& units,
            grid_point position)
    {
        for(const battle_unit_instance& unit : units)
        {
            if(unit.active && unit.position == position)
            {
                return true;
            }
        }
        return false;
    }

    template<std::size_t UnitCount>
    [[nodiscard]] static const battle_unit_instance* _find_unit(
            const std::array<battle_unit_instance, UnitCount>& units,
            battle_unit_id id)
    {
        if(id == no_battle_unit)
        {
            return nullptr;
        }
        for(const battle_unit_instance& unit : units)
        {
            if(unit.id == id)
            {
                return &unit;
            }
        }
        return nullptr;
    }

    [[nodiscard]] static bool _target_matches(
            const battle_unit_instance& actor,
            const battle_unit_instance& target,
            target_policy_kind policy,
            battle_unit_id constrained_target)
    {
        if(! target.active ||
                (constrained_target != no_battle_unit && target.id != constrained_target))
        {
            return false;
        }
        switch(policy)
        {
        case target_policy_kind::self_or_implicit_actor:
            return target.id == actor.id;
        case target_policy_kind::friendly_unit_policy_1:
        case target_policy_kind::friendly_unit_policy_5:
            return target.side == actor.side;
        case target_policy_kind::opponent_unit:
            return target.side != actor.side;
        case target_policy_kind::occupied_unit:
            return true;
        case target_policy_kind::empty_tile:
            return false;
        default:
            break;
        }
        return false;
    }

    static void _project_cost(battle_unit_instance& actor, cost_policy cost)
    {
        switch(cost.kind)
        {
        case action_cost_kind::current_hp:
            actor.hp -= cost.scalar;
            break;
        case action_cost_kind::current_chakra:
            actor.chakra -= cost.scalar;
            break;
        case action_cost_kind::battle_local_ninja_tool_slot:
            if(cost.tool_slot < actor.equipped_tools.size())
            {
                actor.equipped_tools[cost.tool_slot] = no_ninja_tool;
            }
            break;
        default:
            break;
        }
    }

    static void _consider(const ai_candidate& candidate, ai_plan& best)
    {
        if(candidate.score > best.score)
        {
            static_cast<ai_candidate&>(best) = candidate;
        }
    }

    [[nodiscard]] static int _distance(
            int battle_id,
            grid_point first,
            grid_point second)
    {
        return battle_map_topology_distance(
                battle_id, first, second);
    }
};

}

#endif
