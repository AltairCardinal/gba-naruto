#ifndef KONOHA_BATTLE_AI_TURN_FLOW_H
#define KONOHA_BATTLE_AI_TURN_FLOW_H

#include "konoha/battle_action_browser.h"
#include "konoha/battle_action_combinations.h"
#include "konoha/battle_action_execution.h"
#include "konoha/battle_ai.h"
#include "konoha/battle_ai_secondary_command.h"
#include "konoha/battle_turn_flow.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr std::size_t
        battle_ai_action_option_capacity =
                64;

struct battle_ai_action_option_source
{
    std::uint8_t browser_entry_index = 0xFF;
    std::uint8_t first_component_entry_index = 0xFF;

    [[nodiscard]] constexpr bool combination() const
    {
        return first_component_entry_index != 0xFF;
    }
};

enum class battle_ai_turn_flow_error : std::uint8_t
{
    none,
    invalid_phase,
    invalid_actor,
    action_browser_failed,
    planning_failed,
    execution_failed,
    turn_flow_failed,
};

struct battle_ai_turn_flow_result
{
    battle_ai_turn_flow_error error =
            battle_ai_turn_flow_error::none;
    battle_action_browser_error browser_error =
            battle_action_browser_error::none;
    ai_error planning_error = ai_error::none;
    action_error action_rejection = action_error::none;
    ai_plan plan = {};
    battle_turn_flow_result turn = {};
    battle_action_source_kind action_kind =
            battle_action_source_kind::active_action;
    ability_id action_id = no_ability;
    std::uint8_t tool_slot = no_tool_slot;
    bool action_resolved = false;
    bool combination_resolved = false;
    ability_id combination_first_action_id =
            no_ability;
    ability_id combination_second_action_id =
            no_ability;
    ability_id combination_result_action_id =
            no_ability;
    battle_resource_command_type resource_type =
            battle_resource_command_type::replenish_chakra;
    int resource_amount = 0;
    int resource_hp_delta = 0;
    int resource_chakra_delta = 0;
    bool resource_resolved = false;
    std::uint8_t animation_family = 0;
    std::uint8_t effect_code = 0;
    bool targets_opponent = false;
    battle_unit_id target_id = no_battle_unit;
    std::array<battle_unit_id, 12> affected_unit_ids = {};
    int affected_unit_count = 0;
    bool affected_units_truncated = false;
    int impact_count = 0;
    bool secondary_planned = false;
    defense_action_kind defense_kind =
            defense_action_kind::none;
    ability_id defense_action_id = no_ability;
    std::uint8_t defense_tool_slot = no_tool_slot;
    int defense_score = 0;

    [[nodiscard]] constexpr bool success() const
    {
        return error == battle_ai_turn_flow_error::none;
    }
};

template<std::size_t MaxUnits, int Width, int Height>
struct battle_ai_turn_workspace
{
    battle_session<MaxUnits> next_session;
    battle_action_browser_result browser;
    std::array<
            action_definition,
            battle_ai_action_option_capacity> actions = {};
    std::array<
            battle_ai_action_option_source,
            battle_ai_action_option_capacity> action_sources = {};
    std::array<battle_unit_instance, MaxUnits> roster = {};
    battle_ai_plan_workspace<MaxUnits, Width, Height>
            planner;
};

class battle_ai_turn_flow
{
public:
    template<
            int Width,
            int Height,
            std::size_t MaxUnits>
    [[nodiscard]] static battle_ai_turn_flow_result execute(
            battle_session<MaxUnits>& session,
            const grid_map<Width, Height>& map,
            battle_unit_id actor_id,
            ai_objective objective,
            const battle_condition_variant& conditions,
            deterministic_rng& rng)
    {
        battle_ai_turn_workspace<MaxUnits, Width, Height>
                workspace;
        return execute(
                session,
                map,
                actor_id,
                objective,
                conditions,
                rng,
                workspace);
    }

    template<
            int Width,
            int Height,
            std::size_t MaxUnits>
    [[nodiscard]] static battle_ai_turn_flow_result execute(
            battle_session<MaxUnits>& session,
            const grid_map<Width, Height>& map,
            battle_unit_id actor_id,
            ai_objective objective,
            const battle_condition_variant& conditions,
            deterministic_rng& rng,
            battle_ai_turn_workspace<MaxUnits, Width, Height>&
                    workspace)
    {
        if(session.lifecycle() !=
                battle_lifecycle::unit_select)
        {
            return {
                battle_ai_turn_flow_error::invalid_phase,
            };
        }
        const battle_unit_instance* requested_actor =
                session.unit(actor_id);
        if(! requested_actor ||
                requested_actor->control !=
                        battle_control::ai ||
                requested_actor->side !=
                        session.current_side() ||
                ! session.can_issue_commands(actor_id))
        {
            return {
                battle_ai_turn_flow_error::invalid_actor,
            };
        }

        workspace.next_session = session;
        battle_session<MaxUnits>& next =
                workspace.next_session;
        if(! next.configure_battlefield(map))
        {
            return {
                battle_ai_turn_flow_error::
                        execution_failed,
            };
        }
        deterministic_rng next_rng = rng;
        if(next.select_unit(actor_id) !=
                battle_transition::action_draft_opened)
        {
            return {
                battle_ai_turn_flow_error::invalid_actor,
            };
        }

        workspace.browser =
                battle_action_browser::build(next);
        battle_action_browser_result& browser =
                workspace.browser;
        if(browser.error !=
                battle_action_browser_error::none)
        {
            battle_ai_turn_flow_result result;
            result.error =
                    battle_ai_turn_flow_error::
                            action_browser_failed;
            result.browser_error = browser.error;
            return result;
        }

        workspace.actions = {};
        std::array<
                action_definition,
                battle_ai_action_option_capacity>& actions =
                workspace.actions;
        workspace.action_sources = {};
        std::size_t action_count = 0;
        for(std::size_t index = 0;
                index < browser.count;
                ++index)
        {
            const battle_action_browser_entry& entry =
                    browser.entries[index];
            if(! entry.selectable())
            {
                continue;
            }
            const battle_action_component component = {
                entry.kind ==
                                battle_action_source_kind::
                                        active_action ?
                        battle_action_component_kind::
                                active_action :
                        battle_action_component_kind::
                                ninja_tool,
                entry.action_id,
                entry.tool_slot,
            };
            if(battle_action_combinations::
                       requires_follow(
                               component,
                               entry.action))
            {
                continue;
            }
            actions[action_count] = entry.action;
            workspace.action_sources[action_count] = {
                static_cast<std::uint8_t>(index),
                0xFF,
            };
            ++action_count;
        }
        for(std::size_t first_index = 0;
                first_index < browser.count;
                ++first_index)
        {
            const battle_action_browser_entry& first =
                    browser.entries[first_index];
            if(! first.selectable())
            {
                continue;
            }
            const battle_action_component first_component = {
                first.kind ==
                                battle_action_source_kind::
                                        active_action ?
                        battle_action_component_kind::
                                active_action :
                        battle_action_component_kind::
                                ninja_tool,
                first.action_id,
                first.tool_slot,
            };
            if(! battle_action_combinations::
                        can_start(
                                first_component,
                                first.action))
            {
                continue;
            }
            for(std::size_t second_index = 0;
                    second_index < browser.count;
                    ++second_index)
            {
                const battle_action_browser_entry& second =
                        browser.entries[second_index];
                if(! second.selectable())
                {
                    continue;
                }
                const battle_action_component second_component = {
                    second.kind ==
                                    battle_action_source_kind::
                                            active_action ?
                            battle_action_component_kind::
                                    active_action :
                            battle_action_component_kind::
                                    ninja_tool,
                    second.action_id,
                    second.tool_slot,
                };
                if(! battle_action_combinations::can_follow(
                           second_component,
                           second.action))
                {
                    continue;
                }
                const battle_combination_action combination =
                        battle_action_combinations::compose(
                                first_component,
                                first.action,
                                second_component,
                                second.action);
                action_definition planning_action =
                        battle_action_combinations::
                                planning_action(
                                        combination);
                if(planning_action.id == no_ability ||
                        action_count ==
                                actions.size())
                {
                    continue;
                }
                int chakra_cost = 0;
                for(const action_definition& component_action :
                        combination.component_actions)
                {
                    if(component_action.cost.kind ==
                            action_cost_kind::
                                    current_chakra)
                    {
                        chakra_cost +=
                                component_action.cost.scalar;
                    }
                }
                planning_action.cost = {
                    action_cost_kind::current_chakra,
                    static_cast<std::uint16_t>(
                            chakra_cost),
                    no_tool_slot,
                };
                actions[action_count] =
                        planning_action;
                workspace.action_sources[action_count] = {
                    static_cast<std::uint8_t>(
                            second_index),
                    static_cast<std::uint8_t>(
                            first_index),
                };
                ++action_count;
            }
        }

        workspace.roster = {};
        std::array<battle_unit_instance, MaxUnits>& roster =
                workspace.roster;
        for(std::size_t index = 0;
                index < next.unit_count();
                ++index)
        {
            roster[index] = *next.unit_at(index);
        }
        const battle_unit_instance* actor =
                next.unit(actor_id);
        if(! actor)
        {
            return {
                battle_ai_turn_flow_error::invalid_actor,
            };
        }

        ai_plan plan = battle_ai::plan(
                map,
                *actor,
                roster,
                actions,
                action_count,
                objective,
                next_rng,
                workspace.planner);
        if(plan.error != ai_error::none)
        {
            battle_ai_turn_flow_result result;
            result.error =
                    battle_ai_turn_flow_error::planning_failed;
            result.planning_error = plan.error;
            result.plan = plan;
            return result;
        }
        if(plan.action == ai_action::ability)
        {
            if(plan.action_index >= action_count)
            {
                battle_ai_turn_flow_result result;
                result.error =
                        battle_ai_turn_flow_error::
                                execution_failed;
                result.plan = plan;
                return result;
            }
            const battle_ai_action_option_source&
                    source =
                            workspace.action_sources[
                                    plan.action_index];
            if(source.browser_entry_index >=
                    browser.count)
            {
                battle_ai_turn_flow_result result;
                result.error =
                        battle_ai_turn_flow_error::
                                execution_failed;
                result.plan = plan;
                return result;
            }
            const battle_action_browser_entry& entry =
                    browser.entries[
                            source.browser_entry_index];
            plan.action_kind = entry.kind;
            plan.ability = entry.action_id;
            plan.tool_slot = entry.tool_slot;
        }

        if(plan.destination != actor->position &&
                next.preview_move(plan.destination) !=
                        battle_transition::move_previewed)
        {
            battle_ai_turn_flow_result result;
            result.error =
                    battle_ai_turn_flow_error::
                            execution_failed;
            result.plan = plan;
            return result;
        }

        battle_ai_turn_flow_result result;
        result.plan = plan;
        if(plan.action ==
                        ai_action::replenish_chakra ||
                plan.action == ai_action::rest)
        {
            const battle_resource_command_type type =
                    plan.action ==
                                    ai_action::
                                            replenish_chakra ?
                            battle_resource_command_type::
                                    replenish_chakra :
                            battle_resource_command_type::rest;
            const battle_resource_command_preview
                    resource =
                            battle_resource_commands::commit_in_place(
                                    next,
                                    type,
                                    plan.resource_amount);
            if(! resource.legal())
            {
                result.error =
                        battle_ai_turn_flow_error::
                                execution_failed;
                return result;
            }
            result.resource_type = type;
            result.resource_amount = resource.amount;
            result.resource_hp_delta =
                    resource.hp_delta;
            result.resource_chakra_delta =
                    resource.chakra_delta;
            result.resource_resolved = true;
            result.turn =
                    battle_turn_flow::
                            complete_non_target_action_in_place(
                                    next,
                                    conditions,
                                    next_rng);
            if(result.turn.error !=
                    battle_turn_flow_error::none)
            {
                result.error =
                        battle_ai_turn_flow_error::
                                turn_flow_failed;
                return result;
            }
            session = next;
            rng = next_rng;
            return result;
        }
        if(plan.action == ai_action::ability)
        {
            const battle_ai_action_option_source& source =
                    workspace.action_sources[
                            plan.action_index];
            const battle_action_browser_entry& selected =
                    browser.entries[
                            source.browser_entry_index];
            battle_combination_action combination;
            if(source.combination())
            {
                if(source.first_component_entry_index >=
                        browser.count)
                {
                    result.error =
                            battle_ai_turn_flow_error::
                                    execution_failed;
                    return result;
                }
                const battle_action_browser_entry& first =
                        browser.entries[
                                source.
                                        first_component_entry_index];
                combination =
                        battle_action_combinations::compose(
                                {
                                    first.kind ==
                                                    battle_action_source_kind::
                                                            active_action ?
                                            battle_action_component_kind::
                                                    active_action :
                                            battle_action_component_kind::
                                                    ninja_tool,
                                    first.action_id,
                                    first.tool_slot,
                                },
                                first.action,
                                {
                                    selected.kind ==
                                                    battle_action_source_kind::
                                                            active_action ?
                                            battle_action_component_kind::
                                                    active_action :
                                            battle_action_component_kind::
                                                    ninja_tool,
                                    selected.action_id,
                                    selected.tool_slot,
                                },
                                selected.action);
            }
            const action_definition& presentation_action =
                    actions[plan.action_index];
            const battle_unit_instance* presentation_target =
                    next.active_unit_at(
                            plan.target_position);
            const battle_unit_id presentation_target_id =
                    presentation_target ?
                            presentation_target->id :
                            no_battle_unit;
            const action_result resolved =
                    combination.valid() ?
                    battle_action_combinations::resolve(
                            next,
                            combination,
                            plan.target_position,
                            next_rng) :
                    battle_action_execution::resolve_in_place(
                            next,
                            selected.action,
                            plan.target_position,
                            next_rng);
            if(! resolved.success())
            {
                result.error =
                        battle_ai_turn_flow_error::
                                execution_failed;
                result.action_rejection =
                        resolved.error;
                return result;
            }
            result.action_kind = selected.kind;
            result.action_id =
                    combination.special() ?
                    combination.result.id :
                    selected.action_id;
            result.tool_slot = selected.tool_slot;
            result.action_resolved = true;
            result.combination_resolved =
                    combination.valid();
            if(combination.valid())
            {
                result.combination_first_action_id =
                        combination.components[0].id;
                result.combination_second_action_id =
                        combination.components[1].id;
                result.combination_result_action_id =
                        combination.result.id;
            }
            result.animation_family =
                    presentation_action.presentation.animation_family;
            result.effect_code =
                    presentation_action.effect.code;
            result.targets_opponent =
                    presentation_action.target.kind ==
                            target_policy_kind::opponent_unit;
            result.target_id = presentation_target_id;
            result.affected_unit_ids =
                    resolved.affected_unit_ids;
            result.affected_unit_count =
                    resolved.affected_unit_count;
            result.affected_units_truncated =
                    resolved.affected_units_truncated;
            result.impact_count = resolved.generated_hits;
            result.turn =
                    battle_turn_flow::after_effects_in_place(
                            next, conditions);
            if(result.turn.error !=
                    battle_turn_flow_error::none)
            {
                result.error =
                        battle_ai_turn_flow_error::
                                turn_flow_failed;
                return result;
            }
            if(result.turn.ends_battle)
            {
                session = next;
                rng = next_rng;
                return result;
            }
        }
        else if(next.open_facing_selection() !=
                battle_transition::
                        facing_selection_opened)
        {
            result.error =
                    battle_ai_turn_flow_error::
                            execution_failed;
            return result;
        }

        const battle_unit_instance* moved_actor =
                next.unit(actor_id);
        if(! moved_actor)
        {
            result.error =
                    battle_ai_turn_flow_error::invalid_actor;
            return result;
        }
        if(next.select_facing(
                   plan.facing) !=
                battle_transition::
                        defense_selection_opened)
        {
            result.error =
                    battle_ai_turn_flow_error::
                            execution_failed;
            return result;
        }
        const battle_defense_browser_result
                defense_browser =
                        battle_defense_browser::build(
                                next);
        if(defense_browser.error !=
                battle_defense_browser_error::none)
        {
            result.error =
                    battle_ai_turn_flow_error::
                            execution_failed;
            return result;
        }
        const battle_ai_secondary_command secondary =
                battle_ai_secondary_command_planner::plan(
                        next, defense_browser);
        result.secondary_planned = secondary.planned;
        result.defense_kind = secondary.defense_kind;
        result.defense_action_id =
                secondary.defense_action_id;
        result.defense_tool_slot =
                secondary.defense_tool_slot;
        result.defense_score = secondary.score;
        if(secondary.defense_kind ==
                defense_action_kind::none)
        {
            result.turn =
                    battle_turn_flow::complete_defense_in_place(
                            next,
                            no_ability,
                            conditions,
                            next_rng);
        }
        else
        {
            const battle_defense_browser_entry* selected =
                    defense_browser.find(
                            secondary.defense_kind,
                            secondary.defense_action_id,
                            secondary.defense_tool_slot);
            if(! selected || ! selected->confirmable())
            {
                result.error =
                        battle_ai_turn_flow_error::
                                execution_failed;
                return result;
            }
            result.turn =
                    battle_turn_flow::complete_defense_in_place(
                            next,
                            selected->action,
                            conditions,
                            next_rng);
        }
        if(result.turn.error !=
                battle_turn_flow_error::none)
        {
            result.error =
                    battle_ai_turn_flow_error::
                            turn_flow_failed;
            return result;
        }

        session = next;
        rng = next_rng;
        return result;
    }

};

}

#endif
