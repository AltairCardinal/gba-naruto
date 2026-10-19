#ifndef KONOHA_BATTLE_ACTION_LOADOUT_H
#define KONOHA_BATTLE_ACTION_LOADOUT_H

#include "konoha/battle_action_system.h"
#include "konoha/battle_unit_content.h"

#include <array>
#include <cstddef>

namespace konoha
{

template<std::size_t Capacity>
struct action_loadout
{
    std::array<ability_id, Capacity> ids = {};
    std::array<std::uint8_t, Capacity> levels = {};
    std::size_t count = 0;

    [[nodiscard]] constexpr bool contains(ability_id id) const
    {
        for(std::size_t index = 0; index < count; ++index)
        {
            if(ids[index] == id)
            {
                return true;
            }
        }
        return false;
    }

    [[nodiscard]] constexpr bool add(
            ability_id id, std::uint8_t level = 1)
    {
        if(id == 0 || id == no_ability ||
                level == unlocked_action_level ||
                level == locked_action_level ||
                count == Capacity || contains(id))
        {
            return false;
        }
        ids[count] = id;
        levels[count] = level;
        ++count;
        return true;
    }
};

template<std::size_t Capacity>
struct action_definition_set
{
    std::array<action_definition, Capacity> values = {};
    std::size_t count = 0;
    bool valid = true;
};

[[nodiscard]] constexpr bool action_slot_available(
        const action_slot_definition& slot,
        std::uint8_t action_level)
{
    return slot.action != 0 &&
           slot.action != no_ability &&
           action_level != unlocked_action_level &&
           action_level != locked_action_level;
}

[[nodiscard]] constexpr action_loadout<15> build_primary_action_loadout(
        const std::array<ability_id, 15>& action_ids,
        const primary_action_state_array& action_levels)
{
    action_loadout<15> result;
    for(std::size_t index = 0;
            index < action_ids.size();
            ++index)
    {
        const ability_id action_id = action_ids[index];
        const std::uint8_t action_level = action_levels[index];
        if(action_id != 0 && action_id != no_ability &&
                action_level != unlocked_action_level &&
                action_level != locked_action_level)
        {
            (void) result.add(action_id, action_level);
        }
    }
    return result;
}

[[nodiscard]] constexpr action_loadout<15> build_primary_action_loadout(
        const unit_definition& unit,
        const primary_action_state_array& action_levels)
{
    std::array<ability_id, 15> action_ids = {};
    for(std::size_t index = 0;
            index < unit.primary_slots.size();
            ++index)
    {
        action_ids[index] = unit.primary_slots[index].action;
    }
    return build_primary_action_loadout(
            action_ids, action_levels);
}

template<std::size_t Capacity, typename Predicate>
[[nodiscard]] constexpr action_loadout<Capacity> filter_action_loadout(
        const action_loadout<Capacity>& source, Predicate predicate)
{
    action_loadout<Capacity> result;
    for(std::size_t index = 0; index < source.count; ++index)
    {
        const ability_id id = source.ids[index];
        if(predicate(id))
        {
            (void) result.add(id, source.levels[index]);
        }
    }
    return result;
}

template<std::size_t DefinitionCount>
[[nodiscard]] constexpr action_definition
apply_persistent_passive_action_modifiers(
        const action_definition& base,
        const battle_passive_state& passives,
        const std::array<
                passive_definition,
                DefinitionCount>& definitions)
{
    action_definition result = base;
    const auto definition_for_slot =
            [&passives, &definitions](
                    std::size_t index)
                    -> const passive_definition*
            {
                const passive_slot_state& slot =
                        passives.slot(index);
                if(slot.id == no_passive ||
                        slot.stored_level == 0 ||
                        slot.stored_level ==
                                unlearned_passive_level ||
                        slot.id >= DefinitionCount)
                {
                    return nullptr;
                }
                const passive_definition& definition =
                        definitions[slot.id];
                return definition.id == slot.id ?
                        &definition :
                        nullptr;
            };
    const auto value_a =
            [&passives](
                    std::size_t index,
                    const passive_definition& definition)
            {
                return static_cast<int>(definition.base_a) +
                        static_cast<int>(
                                definition.per_level_a) *
                                (static_cast<int>(
                                         passives.slot(index)
                                                 .stored_level) -
                                 1);
            };
    const auto header_matches =
            [](const action_definition& action,
                    action_cost_kind cost,
                    std::uint8_t animation_family)
            {
                return action.cost.kind == cost &&
                        action.presentation.animation_family ==
                                animation_family;
            };
    const auto physical_potency_eligible =
            [&header_matches](
                    const action_definition& action)
            {
                return (
                               header_matches(
                                       action,
                                       action_cost_kind::
                                               current_hp,
                                       1) &&
                               action.effect.code != 0x21) ||
                        action.effect.code == 0x0A;
            };
    const auto increase_potency_percentage =
            [](std::uint8_t current, int percentage)
            {
                const int modified =
                        static_cast<int>(current) +
                        static_cast<int>(current) *
                                percentage /
                                100;
                return static_cast<std::uint8_t>(
                        modified > 99 ? 99 : modified);
            };
    const auto add_potency =
            [](std::uint8_t current, int addition)
            {
                const int modified =
                        static_cast<int>(current) + addition;
                return static_cast<std::uint8_t>(
                        modified > 99 ? 99 : modified);
            };

    // The original applies both percentage families across all 24 slots
    // before starting the fixed-addition pass.
    for(std::size_t index = 0;
            index < battle_passive_state::capacity;
            ++index)
    {
        const passive_definition* definition =
                definition_for_slot(index);
        if(! definition)
        {
            continue;
        }
        const int value = value_a(index, *definition);
        switch(definition->target_type)
        {
        case 14:
            if(physical_potency_eligible(result))
            {
                result.effect.potency =
                        increase_potency_percentage(
                                result.effect.potency,
                                value);
            }
            break;
        case 16:
            if(header_matches(
                       result,
                       action_cost_kind::current_chakra,
                       1))
            {
                result.effect.potency =
                        increase_potency_percentage(
                                result.effect.potency,
                                value);
            }
            break;
        default:
            break;
        }
    }

    for(std::size_t index = 0;
            index < battle_passive_state::capacity;
            ++index)
    {
        const passive_definition* definition =
                definition_for_slot(index);
        if(! definition)
        {
            continue;
        }
        const int value = value_a(index, *definition);
        switch(definition->target_type)
        {
        case 13:
            if(physical_potency_eligible(result))
            {
                result.effect.potency =
                        add_potency(
                                result.effect.potency,
                                value);
            }
            break;
        case 15:
            if(header_matches(
                       result,
                       action_cost_kind::current_chakra,
                       1))
            {
                result.effect.potency =
                        add_potency(
                                result.effect.potency,
                                value);
            }
            break;
        case 17:
            if(header_matches(
                       result,
                       action_cost_kind::
                               battle_local_ninja_tool_slot,
                       1))
            {
                result.effect.potency =
                        add_potency(
                                result.effect.potency,
                                value);
            }
            break;
        case 18:
            if(result.effect.code == 0x1A)
            {
                result.effect.potency =
                        static_cast<std::uint8_t>(
                                static_cast<int>(
                                        result.effect.potency) +
                                value);
            }
            break;
        case 19:
        {
            int modified =
                    static_cast<int>(
                            result.effect
                                    .success_rate_percent) +
                    value;
            if(modified > 999)
            {
                modified = 999;
            }
            result.effect.success_rate_percent =
                    static_cast<std::uint8_t>(modified);
            break;
        }
        default:
            break;
        }
    }
    return result;
}

[[nodiscard]] constexpr action_definition action_definition_at_level(
        const action_definition& base, std::uint8_t action_level)
{
    action_definition result = base;
    if(action_level == unlocked_action_level ||
            action_level == locked_action_level)
    {
        return result;
    }
    const std::uint32_t increment =
            static_cast<std::uint32_t>(
                    action_level - 1) *
            result.upgrade.per_level_growth;
    const auto grow_byte =
            [increment](std::uint8_t value)
            {
                return static_cast<std::uint8_t>(
                        static_cast<std::uint32_t>(value) +
                        increment);
            };
    switch(result.upgrade.target_type)
    {
    case 1:
        result.effect.potency =
                grow_byte(result.effect.potency);
        break;
    case 2:
        result.effect.base_hit_count =
                grow_byte(result.effect.base_hit_count);
        break;
    case 3:
        result.effect.success_rate_percent =
                grow_byte(
                        result.effect.success_rate_percent);
        break;
    case 4:
        result.range.distance_and_line_flags =
                grow_byte(
                        result.range.distance_and_line_flags);
        break;
    case 5:
        result.range.area_range_and_shape_flags =
                grow_byte(
                        result.range.area_range_and_shape_flags);
        break;
    case 6:
        result.effect.duration_turns =
                grow_byte(result.effect.duration_turns);
        break;
    default:
        break;
    }
    return result;
}

template<std::size_t Capacity, std::size_t CatalogSize>
[[nodiscard]] constexpr action_definition_set<Capacity> materialize_action_loadout(
        const action_loadout<Capacity>& loadout,
        const std::array<action_definition, CatalogSize>& catalog)
{
    action_definition_set<Capacity> result;
    for(std::size_t index = 0; index < loadout.count; ++index)
    {
        const ability_id id = loadout.ids[index];
        if(id >= CatalogSize || catalog[id].id != id)
        {
            result.valid = false;
            result.count = 0;
            return result;
        }
        result.values[result.count] =
                action_definition_at_level(
                        catalog[id],
                        loadout.levels[index]);
        ++result.count;
    }
    return result;
}

}

#endif
