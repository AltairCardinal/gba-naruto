#ifndef KONOHA_BATTLE_ACTION_COMBINATIONS_H
#define KONOHA_BATTLE_ACTION_COMBINATIONS_H

#include "konoha/battle_action_execution.h"
#include "konoha/generated_battle_action_content.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_action_component_kind : std::uint8_t
{
    active_action,
    ninja_tool,
};

struct battle_action_component
{
    battle_action_component_kind kind =
            battle_action_component_kind::active_action;
    ability_id id = no_ability;
    std::uint8_t tool_slot = no_tool_slot;

    constexpr bool operator==(
            const battle_action_component&) const = default;
};

struct battle_action_combination_recipe
{
    ability_id first_action_id = no_ability;
    ability_id second_action_id = no_ability;
    ability_id result_action_id = no_ability;
    bool second_is_shuriken_tool = false;
};

struct battle_combination_action
{
    std::array<battle_action_component, 2> components = {};
    std::array<action_definition, 2> component_actions = {};
    action_definition result = {};
    bool composed = false;

    [[nodiscard]] constexpr bool valid() const
    {
        return composed;
    }

    [[nodiscard]] constexpr bool special() const
    {
        return result.id != no_ability &&
                result.effect.code != 0;
    }
};

class battle_action_combinations
{
public:
    inline static constexpr std::array<
            battle_action_combination_recipe, 5> recipes = {{
        { 9, 8, 10, false },
        { 9, 5, 11, false },
        { 12, 12, 13, false },
        { 16, 16, 17, false },
        { 16, no_ability, 18, true },
    }};

    [[nodiscard]] static constexpr bool can_start(
            battle_action_component component,
            const action_definition& action)
    {
        return component.kind ==
                        battle_action_component_kind::
                                active_action &&
                component.id == action.id &&
                (action.target.flags & 0x18) != 0;
    }

    [[nodiscard]] static constexpr bool requires_follow(
            battle_action_component component,
            const action_definition& action)
    {
        return can_start(component, action) &&
                (action.target.flags & 0x10) != 0;
    }

    [[nodiscard]] static bool can_follow(
            battle_action_component component,
            const action_definition& action)
    {
        return component.id == action.id &&
                (component.kind ==
                                battle_action_component_kind::
                                        active_action ||
                 component.kind ==
                                battle_action_component_kind::
                                        ninja_tool) &&
                effect_resolver_registry::handler_for(
                        action.effect.code) ==
                        effect_handler_kind::damage;
    }

    [[nodiscard]] static constexpr ability_id result_for(
            battle_action_component first,
            battle_action_component second)
    {
        if(first.kind !=
                battle_action_component_kind::active_action)
        {
            return no_ability;
        }
        for(const battle_action_combination_recipe& recipe :
                recipes)
        {
            if(first.id != recipe.first_action_id)
            {
                continue;
            }
            if(recipe.second_is_shuriken_tool)
            {
                if(second.kind ==
                                battle_action_component_kind::
                                        ninja_tool &&
                        second.id >= 1 && second.id <= 17)
                {
                    return recipe.result_action_id;
                }
            }
            else if(second.kind ==
                                battle_action_component_kind::
                                        active_action &&
                    second.id == recipe.second_action_id)
            {
                return recipe.result_action_id;
            }
        }
        return no_ability;
    }

    [[nodiscard]] static battle_combination_action compose(
            battle_action_component first,
            const action_definition& first_action,
            battle_action_component second,
            const action_definition& second_action)
    {
        battle_combination_action result;
        const ability_id result_id =
                result_for(first, second);
        if(first_action.id != first.id ||
                second_action.id != second.id ||
                ! can_start(first, first_action) ||
                ! can_follow(second, second_action))
        {
            return result;
        }

        result.components = { first, second };
        result.component_actions = {
            first_action,
            second_action,
        };
        result.composed = true;
        if(result_id == no_ability)
        {
            return result;
        }
        if(result_id >= active_action_definitions.size())
        {
            return {};
        }
        result.result =
                active_action_definitions[result_id];
        result.result.cost = {
            action_cost_kind::none,
            0,
            no_tool_slot,
        };

        const std::uint8_t first_distance =
                first_action.range.distance_and_line_flags &
                0x1F;
        const std::uint8_t second_distance =
                second_action.range.distance_and_line_flags &
                0x1F;
        result.result.range.distance_and_line_flags =
                second_distance > first_distance ?
                second_action.range.distance_and_line_flags :
                first_action.range.distance_and_line_flags;
        return result;
    }

    [[nodiscard]] static action_definition planning_action(
            const battle_combination_action& combination)
    {
        if(! combination.valid())
        {
            return {};
        }
        if(combination.special())
        {
            action_definition result = combination.result;
            result.id = combination.component_actions[1].id;
            result.cost = {};
            return result;
        }
        if(_augments_following_attack(combination))
        {
            action_definition result =
                    _augmented_action(combination);
            result.cost = {};
            return result;
        }
        return _sequence_planning_action(combination);
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_preview preview(
            const battle_session<MaxUnits>& session,
            const battle_combination_action& combination,
            grid_point target_position)
    {
        if(! combination.valid() ||
                session.lifecycle() !=
                        battle_lifecycle::action_drafting ||
                ! session.draft().active)
        {
            return { action_error::invalid_definition };
        }
        const battle_unit_instance* source =
                session.unit(session.draft().unit_id);
        if(! source)
        {
            return { action_error::invalid_source };
        }

        const action_error cost_error =
                _validate_costs(*source, combination);
        if(cost_error != action_error::none)
        {
            return { cost_error };
        }
        for(const action_definition& component :
                combination.component_actions)
        {
            const action_requirement requirement =
                    battle_action_eligibility::query(
                            *source, component.id);
            if(! requirement.available())
            {
                action_preview rejected = {
                    action_error::
                            action_requirement_not_met,
                };
                rejected.requirement_reason_code =
                        requirement.reason_code;
                return rejected;
            }
        }

        action_preview result;
        if(combination.special())
        {
            action_definition executable =
                    combination.result;
            // Derived actions are not character loadout entries.
            // Eligibility belongs to the selected components.
            executable.id =
                    combination.component_actions[1].id;
            result = battle_action_execution::preview(
                    session,
                    executable,
                    target_position);
        }
        else if(_augments_following_attack(combination))
        {
            action_definition executable =
                    _augmented_action(combination);
            executable.cost = {};
            result = battle_action_execution::preview(
                    session,
                    executable,
                    target_position);
        }
        else
        {
            result = _preview_sequence(
                    session,
                    combination,
                    target_position);
        }
        if(result.legal())
        {
            result.cost_kind =
                    action_cost_kind::current_chakra;
            result.scalar_cost =
                    _scalar_cost(
                            combination,
                            action_cost_kind::
                                    current_chakra);
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_result resolve(
            battle_session<MaxUnits>& session,
            const battle_combination_action& combination,
            grid_point target_position,
            deterministic_rng& rng)
    {
        const action_preview checked =
                preview(session, combination, target_position);
        if(! checked.legal())
        {
            return { checked.error };
        }

        battle_session<MaxUnits> next = session;
        deterministic_rng next_rng = rng;
        battle_unit_instance* source =
                next._find_unit(next.draft().unit_id);
        if(! source)
        {
            return { action_error::invalid_source };
        }
        _commit_costs(*source, combination);
        action_result result;
        if(combination.special())
        {
            action_definition executable =
                    combination.result;
            executable.id =
                    combination.component_actions[1].id;
            executable.cost = {};
            result = battle_action_execution::resolve_in_place(
                    next,
                    executable,
                    target_position,
                    next_rng);
        }
        else if(_augments_following_attack(combination))
        {
            action_definition executable =
                    _augmented_action(combination);
            executable.cost = {};
            result = battle_action_execution::resolve_in_place(
                    next,
                    executable,
                    target_position,
                    next_rng);
        }
        else
        {
            result = _resolve_sequence(
                    next,
                    combination,
                    target_position,
                    next_rng);
        }
        if(result.success())
        {
            session = next;
            rng = next_rng;
        }
        return result;
    }

private:
    [[nodiscard]] static bool _augments_following_attack(
            const battle_combination_action& combination)
    {
        return ! combination.special() &&
                combination.component_actions[0].effect.code ==
                        0x08;
    }

    [[nodiscard]] static action_definition _augmented_action(
            const battle_combination_action& combination)
    {
        action_definition result =
                combination.component_actions[1];
        result.effect.base_hit_count =
                static_cast<std::uint8_t>(
                        result.effect.base_hit_count +
                        combination.component_actions[0]
                                .effect.potency);
        return result;
    }

    [[nodiscard]] static action_definition
    _sequence_planning_action(
            const battle_combination_action& combination)
    {
        const action_definition& first =
                combination.component_actions[0];
        const action_definition& second =
                combination.component_actions[1];
        action_definition result = second;
        result.cost = {};

        const effect_handler_kind first_handler =
                effect_resolver_registry::handler_for(
                        first.effect.code);
        const effect_handler_kind second_handler =
                effect_resolver_registry::handler_for(
                        second.effect.code);
        if(first_handler == effect_handler_kind::damage &&
                second_handler ==
                        effect_handler_kind::damage)
        {
            const int total_potency =
                    first.effect.potency *
                            first.effect.base_hit_count +
                    second.effect.potency *
                            second.effect.base_hit_count;
            result.effect.potency =
                    static_cast<std::uint8_t>(
                            total_potency > 255 ?
                                    255 : total_potency);
            result.effect.base_hit_count = 1;
            if(first.effect.success_rate_percent <
                    result.effect.success_rate_percent)
            {
                result.effect.success_rate_percent =
                        first.effect.success_rate_percent;
            }
        }
        else if(second_handler ==
                            effect_handler_kind::damage &&
                (first.effect.code == 0x12 ||
                 first.effect.code == 0x1E))
        {
            const int boosted_potency =
                    second.effect.potency *
                            (100 + first.effect.potency) /
                    100;
            result.effect.potency =
                    static_cast<std::uint8_t>(
                            boosted_potency > 255 ?
                                    255 : boosted_potency);
        }

        if(first.target.kind == second.target.kind &&
                first.range.maximum_distance() <
                second.range.maximum_distance())
        {
            result.range = first.range;
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_preview _preview_sequence(
            const battle_session<MaxUnits>& session,
            const battle_combination_action& combination,
            grid_point target_position)
    {
        action_preview aggregate;
        aggregate.error = action_error::none;
        for(action_definition component :
                combination.component_actions)
        {
            component.cost = {};
            const action_preview item =
                    battle_action_execution::preview(
                            session,
                            component,
                            target_position);
            if(! item.legal())
            {
                return item;
            }
            aggregate.hit_count += item.hit_count;
            aggregate.total_damage += item.total_damage;
            aggregate.total_healing += item.total_healing;
            aggregate.target_count += item.target_count;
            if(item.damage_per_hit >
                    aggregate.damage_per_hit)
            {
                aggregate.damage_per_hit =
                        item.damage_per_hit;
            }
            if(item.success_rate_percent >
                    aggregate.success_rate_percent)
            {
                aggregate.success_rate_percent =
                        item.success_rate_percent;
            }
        }
        return aggregate;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_result _resolve_sequence(
            battle_session<MaxUnits>& session,
            const battle_combination_action& combination,
            grid_point target_position,
            deterministic_rng& rng)
    {
        action_result aggregate;
        for(std::size_t index = 0;
                index < combination.component_actions.size();
                ++index)
        {
            if(index != 0 &&
                    ! session.active_unit_at(target_position))
            {
                break;
            }
            action_definition component =
                    combination.component_actions[index];
            component.cost = {};
            action_result item =
                    battle_action_execution::resolve_in_place(
                            session,
                            component,
                            target_position,
                            rng);
            if(! item.success())
            {
                return item;
            }
            _merge_action_result(item, aggregate);
            if(index + 1 <
                    combination.component_actions.size())
            {
                battle_unit_instance* source =
                        session._find_unit(
                                session.draft().unit_id);
                if(! source)
                {
                    return {
                        action_error::invalid_source,
                    };
                }
                source->ledger.acted = false;
                session._lifecycle =
                        battle_lifecycle::action_drafting;
            }
        }
        return aggregate;
    }

    static void _record_affected(
            battle_unit_id unit_id,
            action_result& destination)
    {
        for(int index = 0;
                index < destination.affected_unit_count;
                ++index)
        {
            if(destination.affected_unit_ids[
                       static_cast<std::size_t>(index)] ==
                    unit_id)
            {
                return;
            }
        }
        if(destination.affected_unit_count <
                static_cast<int>(
                        destination.affected_unit_ids.size()))
        {
            destination.affected_unit_ids[
                    static_cast<std::size_t>(
                            destination.affected_unit_count)] =
                    unit_id;
            ++destination.affected_unit_count;
        }
        else
        {
            destination.affected_units_truncated = true;
        }
    }

    static void _merge_action_result(
            const action_result& source,
            action_result& destination)
    {
        destination.generated_hits += source.generated_hits;
        destination.effective_hits += source.effective_hits;
        destination.total_damage += source.total_damage;
        destination.total_healing += source.total_healing;
        destination.chakra_delta += source.chakra_delta;
        destination.applied_status_count +=
                source.applied_status_count;
        destination.target_count += source.target_count;
        destination.source_status_0x0d_consumed |=
                source.source_status_0x0d_consumed;
        destination.target_status_0x0d_consumed |=
                source.target_status_0x0d_consumed;
        destination.defeated |= source.defeated;
        destination.summoned |= source.summoned;
        destination.summon_count += source.summon_count;
        destination.reaction_state_changed |=
                source.reaction_state_changed;
        destination.moved |= source.moved;
        destination.identity_overridden |=
                source.identity_overridden;
        destination.linked_resolution_count +=
                source.linked_resolution_count;
        destination.damage_steps_truncated |=
                source.damage_steps_truncated;
        destination.affected_units_truncated |=
                source.affected_units_truncated;
        for(int index = 0;
                index < source.affected_unit_count;
                ++index)
        {
            _record_affected(
                    source.affected_unit_ids[
                            static_cast<std::size_t>(
                                    index)],
                    destination);
        }
        for(int index = 0;
                index < source.damage_step_count;
                ++index)
        {
            if(destination.damage_step_count <
                    static_cast<int>(
                            destination.damage_steps.size()))
            {
                destination.damage_steps[
                        static_cast<std::size_t>(
                                destination.damage_step_count)] =
                        source.damage_steps[
                                static_cast<std::size_t>(
                                        index)];
                ++destination.damage_step_count;
            }
            else
            {
                destination.damage_steps_truncated = true;
            }
        }
        if(source.reaction_event.triggered)
        {
            destination.reaction_event =
                    source.reaction_event;
            destination.reaction_code =
                    source.reaction_code;
            destination.reaction_action_id =
                    source.reaction_action_id;
            destination.reaction_hit_index =
                    source.reaction_hit_index;
        }
    }

    [[nodiscard]] static int _scalar_cost(
            const battle_combination_action& combination,
            action_cost_kind kind)
    {
        int result = 0;
        for(const action_definition& component :
                combination.component_actions)
        {
            if(component.cost.kind == kind)
            {
                result += component.cost.scalar;
            }
        }
        return result;
    }

    [[nodiscard]] static action_error _validate_costs(
            const battle_unit_instance& source,
            const battle_combination_action& combination)
    {
        const int chakra_cost = _scalar_cost(
                combination,
                action_cost_kind::current_chakra);
        if(chakra_cost > source.chakra)
        {
            return action_error::insufficient_chakra;
        }
        const int hp_cost = _scalar_cost(
                combination,
                action_cost_kind::current_hp);
        if(hp_cost > source.hp)
        {
            return action_error::insufficient_hp;
        }
        for(std::size_t index = 0;
                index < combination.component_actions.size();
                ++index)
        {
            const action_definition& component =
                    combination.component_actions[index];
            if(component.cost.kind !=
                    action_cost_kind::
                            battle_local_ninja_tool_slot)
            {
                continue;
            }
            const action_error error =
                    battle_action_cost_policy::validate(
                            source,
                            component.cost,
                            combination.components[index].id);
            if(error != action_error::none)
            {
                return error;
            }
        }
        return action_error::none;
    }

    static void _commit_costs(
            battle_unit_instance& source,
            const battle_combination_action& combination)
    {
        source.chakra -= _scalar_cost(
                combination,
                action_cost_kind::current_chakra);
        source.hp -= _scalar_cost(
                combination,
                action_cost_kind::current_hp);
        for(const action_definition& component :
                combination.component_actions)
        {
            if(component.cost.kind ==
                    action_cost_kind::
                            battle_local_ninja_tool_slot)
            {
                battle_action_cost_policy::commit(
                        source, component.cost);
            }
        }
    }
};

}

#endif
