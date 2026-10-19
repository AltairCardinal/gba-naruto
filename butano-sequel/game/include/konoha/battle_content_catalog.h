#ifndef KONOHA_BATTLE_CONTENT_CATALOG_H
#define KONOHA_BATTLE_CONTENT_CATALOG_H

#include "konoha/battle_action_system.h"
#include "konoha/battle_conditions.h"
#include "konoha/battle_map_content.h"
#include "konoha/battle_passives.h"
#include "konoha/battle_scenario_content.h"
#include "konoha/battle_unit_content.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_passive_content.h"
#include "konoha/generated_battle_scenario_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_content_catalog_error : std::uint8_t
{
    none,
    invalid_battle_id,
    invalid_map_dimensions,
    map_content_out_of_bounds,
    unit_out_of_bounds,
    unit_on_blocked_cell,
    duplicate_unit_position,
    invalid_selector,
    invalid_character,
    inactive_character,
    invalid_active_action,
    unsupported_active_action,
    invalid_ninja_tool,
    unsupported_ninja_tool,
    invalid_passive,
    unsupported_condition,
    invalid_condition_argument,
};

struct battle_content_catalog_result
{
    battle_content_catalog_error error =
            battle_content_catalog_error::none;
    int battle_id = -1;
    int variant = -1;
    int slot = -1;
    int character_id = -1;
    int scenario_count = 0;
    int variant_count = 0;
    int playable_variant_count = 0;
    int deployment_variant_count = 0;
    int fixed_unit_record_count = 0;
    int placeholder_record_count = 0;
    int active_character_count = 0;
    int active_action_count = 0;
    int ninja_tool_action_count = 0;
    int passive_count = 0;

    [[nodiscard]] constexpr bool success() const
    {
        return error == battle_content_catalog_error::none;
    }
};

enum class battle_content_entry_kind : std::uint8_t
{
    empty,
    fixed_roster,
    deployment_required,
};

struct battle_content_entry
{
    const battle_scenario_definition* scenario = nullptr;
    const battle_map_definition* map = nullptr;
    const battle_condition_variant* conditions = nullptr;
    battle_content_entry_kind kind =
            battle_content_entry_kind::empty;
    std::uint8_t variant = 0;

    [[nodiscard]] constexpr bool valid() const
    {
        return scenario && map && conditions;
    }
};

namespace battle_content_catalog_detail
{

[[nodiscard]] constexpr battle_content_catalog_result fail(
        battle_content_catalog_result result,
        battle_content_catalog_error error,
        int battle_id = -1,
        int variant = -1,
        int slot = -1,
        int character_id = -1)
{
    result.error = error;
    result.battle_id = battle_id;
    result.variant = variant;
    result.slot = slot;
    result.character_id = character_id;
    return result;
}

[[nodiscard]] constexpr bool valid_condition_type(
        battle_condition_type type)
{
    switch(type)
    {
    case battle_condition_type::empty:
    case battle_condition_type::no_valid_unit_for_side:
    case battle_condition_type::round_limit_reached:
    case battle_condition_type::no_valid_character_for_side:
    case battle_condition_type::object_slot_inactive:
    case battle_condition_type::side_hp_sum_greater:
    case battle_condition_type::side_unit_count_greater:
    case battle_condition_type::
            side_resolved_object_count_greater:
        return true;
    case battle_condition_type::unused_4:
    case battle_condition_type::unused_5:
        return false;
    default:
        break;
    }
    return false;
}

[[nodiscard]] constexpr bool valid_condition_arguments(
        const battle_condition_predicate& predicate,
        std::size_t character_count)
{
    switch(predicate.type)
    {
    case battle_condition_type::empty:
    case battle_condition_type::round_limit_reached:
        return true;
    case battle_condition_type::object_slot_inactive:
        return predicate.arg0 < 31;
    case battle_condition_type::no_valid_character_for_side:
        return predicate.arg0 < 2 &&
                predicate.arg1 < character_count;
    case battle_condition_type::no_valid_unit_for_side:
    case battle_condition_type::side_hp_sum_greater:
    case battle_condition_type::side_unit_count_greater:
    case battle_condition_type::
            side_resolved_object_count_greater:
        return predicate.arg0 < 2;
    case battle_condition_type::unused_4:
    case battle_condition_type::unused_5:
        return false;
    default:
        break;
    }
    return false;
}

}

template<
        std::size_t ScenarioCount,
        std::size_t CellCount,
        std::size_t UnitCount,
        std::size_t ActiveActionCount,
        std::size_t NinjaToolCount,
        std::size_t PassiveCount>
[[nodiscard]] constexpr battle_content_catalog_result
validate_battle_content_catalog(
        const std::array<
                battle_scenario_definition,
                ScenarioCount>& scenarios,
        const std::array<
                battle_map_definition,
                ScenarioCount>& maps,
        const std::array<battle_map_cell, CellCount>& cells,
        const std::array<
                std::array<battle_condition_variant, 3>,
                ScenarioCount>& conditions,
        const std::array<unit_definition, UnitCount>& units,
        const std::array<
                action_definition,
                ActiveActionCount>& active_actions,
        const std::array<
                action_definition,
                NinjaToolCount>& ninja_tools,
        const std::array<
                passive_definition,
                PassiveCount>& passives)
{
    battle_content_catalog_result result;
    result.scenario_count =
            static_cast<int>(ScenarioCount);
    result.variant_count =
            static_cast<int>(ScenarioCount * 3);

    for(std::size_t index = 0;
            index < ActiveActionCount; ++index)
    {
        const action_definition& action =
                active_actions[index];
        if(action.id != index)
        {
            return battle_content_catalog_detail::fail(
                    result,
                    battle_content_catalog_error::
                            invalid_active_action,
                    -1,
                    -1,
                    static_cast<int>(index));
        }
        if(action.effect.code == 0)
        {
            continue;
        }
        if(effect_resolver_registry::handler_for(
                   action.effect.code) ==
                effect_handler_kind::unimplemented)
        {
            return battle_content_catalog_detail::fail(
                    result,
                    battle_content_catalog_error::
                            unsupported_active_action,
                    -1,
                    -1,
                    static_cast<int>(index));
        }
        ++result.active_action_count;
    }

    for(std::size_t index = 0;
            index < NinjaToolCount; ++index)
    {
        const action_definition& action =
                ninja_tools[index];
        if(action.id != index)
        {
            return battle_content_catalog_detail::fail(
                    result,
                    battle_content_catalog_error::
                            invalid_ninja_tool,
                    -1,
                    -1,
                    static_cast<int>(index));
        }
        if(action.effect.code == 0)
        {
            continue;
        }
        if(effect_resolver_registry::handler_for(
                   action.effect.code) ==
                effect_handler_kind::unimplemented)
        {
            return battle_content_catalog_detail::fail(
                    result,
                    battle_content_catalog_error::
                            unsupported_ninja_tool,
                    -1,
                    -1,
                    static_cast<int>(index));
        }
        ++result.ninja_tool_action_count;
    }

    for(std::size_t index = 0;
            index < PassiveCount; ++index)
    {
        if(passives[index].id != index)
        {
            return battle_content_catalog_detail::fail(
                    result,
                    battle_content_catalog_error::
                            invalid_passive,
                    -1,
                    -1,
                    static_cast<int>(index));
        }
        if(index != no_passive)
        {
            ++result.passive_count;
        }
    }

    for(std::size_t index = 0; index < UnitCount; ++index)
    {
        const unit_definition& unit = units[index];
        if(unit.character_id != index)
        {
            return battle_content_catalog_detail::fail(
                    result,
                    battle_content_catalog_error::
                            invalid_character,
                    -1,
                    -1,
                    -1,
                    static_cast<int>(index));
        }
        if(unit.active)
        {
            ++result.active_character_count;
        }
        for(std::size_t slot = 0;
                slot < unit.primary_slots.size(); ++slot)
        {
            const ability_id action =
                    unit.primary_slots[slot].action;
            if(action != no_ability &&
                    (action >= ActiveActionCount ||
                     active_actions[action].id != action))
            {
                return battle_content_catalog_detail::fail(
                        result,
                        battle_content_catalog_error::
                                invalid_active_action,
                        -1,
                        -1,
                        static_cast<int>(slot),
                        static_cast<int>(index));
            }
        }
        for(std::size_t slot = 0;
                slot < unit.secondary_slots.size(); ++slot)
        {
            const passive_id passive =
                    unit.secondary_slots[slot].action;
            if(passive != no_passive &&
                    (passive >= PassiveCount ||
                     passives[passive].id != passive))
            {
                return battle_content_catalog_detail::fail(
                        result,
                        battle_content_catalog_error::
                                invalid_passive,
                        -1,
                        -1,
                        static_cast<int>(slot),
                        static_cast<int>(index));
            }
        }
    }

    for(std::size_t battle_index = 0;
            battle_index < ScenarioCount;
            ++battle_index)
    {
        const battle_scenario_definition& scenario =
                scenarios[battle_index];
        const battle_map_definition& map =
                maps[battle_index];
        const int battle_id =
                static_cast<int>(battle_index);
        if(scenario.battle_id != battle_index ||
                map.battle_id != battle_index)
        {
            return battle_content_catalog_detail::fail(
                    result,
                    battle_content_catalog_error::
                            invalid_battle_id,
                    battle_id);
        }
        if(scenario.grid_width == 0 ||
                scenario.grid_height == 0 ||
                scenario.grid_width != map.width ||
                scenario.grid_height != map.height ||
                map.cell_count !=
                        static_cast<std::size_t>(
                                map.width * map.height))
        {
            return battle_content_catalog_detail::fail(
                    result,
                    battle_content_catalog_error::
                            invalid_map_dimensions,
                    battle_id);
        }
        const std::size_t first = map.cell_offset;
        const std::size_t count = map.cell_count;
        if(first > CellCount ||
                count > CellCount - first)
        {
            return battle_content_catalog_detail::fail(
                    result,
                    battle_content_catalog_error::
                            map_content_out_of_bounds,
                    battle_id);
        }

        for(std::size_t variant = 0;
                variant < scenario.variants.size();
                ++variant)
        {
            bool any_unit = false;
            bool needs_deployment = false;
            const auto& slots =
                    scenario.variants[variant];
            for(std::size_t slot = 0;
                    slot < slots.size(); ++slot)
            {
                const battle_scenario_unit_slot& unit =
                        slots[slot];
                if(! unit.enabled)
                {
                    continue;
                }
                any_unit = true;
                if(! map.contains(
                           unit.position.x,
                           unit.position.y))
                {
                    return battle_content_catalog_detail::fail(
                            result,
                            battle_content_catalog_error::
                                    unit_out_of_bounds,
                            battle_id,
                            static_cast<int>(variant),
                            static_cast<int>(slot));
                }
                const std::size_t cell =
                        first +
                        static_cast<std::size_t>(
                                unit.position.y *
                                        map.width +
                                unit.position.x);
                if(cells[cell].fully_blocked())
                {
                    return battle_content_catalog_detail::fail(
                            result,
                            battle_content_catalog_error::
                                    unit_on_blocked_cell,
                            battle_id,
                            static_cast<int>(variant),
                            static_cast<int>(slot));
                }
                for(std::size_t previous = 0;
                        previous < slot; ++previous)
                {
                    if(slots[previous].enabled &&
                            slots[previous].position ==
                                    unit.position)
                    {
                        return battle_content_catalog_detail::fail(
                                result,
                                battle_content_catalog_error::
                                        duplicate_unit_position,
                                battle_id,
                                static_cast<int>(variant),
                                static_cast<int>(slot));
                    }
                }

                if(unit.selector_kind ==
                        scenario_selector_kind::
                                fixed_character)
                {
                    ++result.fixed_unit_record_count;
                    if(unit.selector >= UnitCount)
                    {
                        return battle_content_catalog_detail::fail(
                                result,
                                battle_content_catalog_error::
                                        invalid_character,
                                battle_id,
                                static_cast<int>(variant),
                                static_cast<int>(slot),
                                unit.selector);
                    }
                    if(! units[unit.selector].active)
                    {
                        return battle_content_catalog_detail::fail(
                                result,
                                battle_content_catalog_error::
                                        inactive_character,
                                battle_id,
                                static_cast<int>(variant),
                                static_cast<int>(slot),
                                unit.selector);
                    }
                }
                else if(unit.selector_kind ==
                        scenario_selector_kind::
                                deployment_placeholder)
                {
                    if(unit.selector < 0xFA)
                    {
                        return battle_content_catalog_detail::fail(
                                result,
                                battle_content_catalog_error::
                                        invalid_selector,
                                battle_id,
                                static_cast<int>(variant),
                                static_cast<int>(slot));
                    }
                    needs_deployment = true;
                    ++result.placeholder_record_count;
                }
                else
                {
                    return battle_content_catalog_detail::fail(
                            result,
                            battle_content_catalog_error::
                                    invalid_selector,
                            battle_id,
                            static_cast<int>(variant),
                            static_cast<int>(slot));
                }
            }
            if(any_unit)
            {
                ++result.playable_variant_count;
            }
            if(needs_deployment)
            {
                ++result.deployment_variant_count;
            }

            const battle_condition_variant& condition =
                    conditions[battle_index][variant];
            for(int group = 0; group < 2; ++group)
            {
                const auto& predicates =
                        group == 0 ?
                        condition.win :
                        condition.lose;
                for(std::size_t slot = 0;
                        slot < predicates.size(); ++slot)
                {
                    const battle_condition_predicate&
                            predicate =
                                    predicates[slot];
                    if(! battle_content_catalog_detail::
                                   valid_condition_type(
                                           predicate.type))
                    {
                        return battle_content_catalog_detail::fail(
                                result,
                                battle_content_catalog_error::
                                        unsupported_condition,
                                battle_id,
                                static_cast<int>(variant),
                                static_cast<int>(
                                        group *
                                                predicates.size() +
                                        slot));
                    }
                    if(! battle_content_catalog_detail::
                                   valid_condition_arguments(
                                           predicate,
                                           UnitCount))
                    {
                        return battle_content_catalog_detail::fail(
                                result,
                                battle_content_catalog_error::
                                        invalid_condition_argument,
                                battle_id,
                                static_cast<int>(variant),
                                static_cast<int>(
                                        group *
                                                predicates.size() +
                                        slot));
                    }
                }
            }
        }
    }
    return result;
}

inline constexpr battle_content_catalog_result
        generated_battle_content_catalog_validation =
                validate_battle_content_catalog(
                        battle_scenario_definitions,
                        battle_map_definitions,
                        battle_map_cells,
                        battle_condition_variants,
                        unit_definitions,
                        active_action_definitions,
                        ninja_tool_action_definitions,
                        passive_definitions);

static_assert(
        generated_battle_content_catalog_validation.success());

[[nodiscard]] inline constexpr
battle_content_catalog_result
validate_generated_battle_content_catalog()
{
    return generated_battle_content_catalog_validation;
}

[[nodiscard]] inline constexpr battle_content_entry
generated_battle_content_entry(int battle_id, int variant)
{
    if(battle_id < 0 ||
            battle_id >= static_cast<int>(
                    battle_scenario_definitions.size()) ||
            variant < 0 || variant >= 3)
    {
        return {};
    }
    const battle_scenario_definition& scenario =
            battle_scenario_definitions[
                    static_cast<std::size_t>(battle_id)];
    const auto& slots =
            scenario.variants[
                    static_cast<std::size_t>(variant)];
    bool any_unit = false;
    bool needs_deployment = false;
    for(const battle_scenario_unit_slot& slot : slots)
    {
        if(! slot.enabled)
        {
            continue;
        }
        any_unit = true;
        needs_deployment |=
                slot.selector_kind ==
                scenario_selector_kind::
                        deployment_placeholder;
    }
    const battle_content_entry_kind kind =
            ! any_unit ?
            battle_content_entry_kind::empty :
            (needs_deployment ?
                     battle_content_entry_kind::
                             deployment_required :
                     battle_content_entry_kind::
                             fixed_roster);
    return {
        &scenario,
        &battle_map_definitions[
                static_cast<std::size_t>(battle_id)],
        &battle_condition_variants[
                static_cast<std::size_t>(battle_id)]
                [static_cast<std::size_t>(variant)],
        kind,
        static_cast<std::uint8_t>(variant),
    };
}

}

#endif
