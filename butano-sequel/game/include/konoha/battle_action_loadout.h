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

    [[nodiscard]] constexpr bool add(ability_id id)
    {
        if(id == no_ability || count == Capacity || contains(id))
        {
            return false;
        }
        ids[count] = id;
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
        const action_slot_definition& slot, int unit_level)
{
    if(slot.action == no_ability || slot.initial_state == 0)
    {
        return false;
    }
    if(slot.initial_state == 0xFF)
    {
        return slot.unlock_level > 0 && unit_level >= slot.unlock_level;
    }
    return unit_level >= slot.unlock_level;
}

[[nodiscard]] constexpr action_loadout<15> build_primary_action_loadout(
        const unit_definition& unit, int unit_level)
{
    action_loadout<15> result;
    for(const action_slot_definition& slot : unit.primary_slots)
    {
        if(action_slot_available(slot, unit_level))
        {
            (void) result.add(slot.action);
        }
    }
    return result;
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
            (void) result.add(id);
        }
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
        result.values[result.count] = catalog[id];
        ++result.count;
    }
    return result;
}

}

#endif
