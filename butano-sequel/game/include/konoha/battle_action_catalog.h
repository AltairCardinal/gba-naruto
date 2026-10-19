#ifndef KONOHA_BATTLE_ACTION_CATALOG_H
#define KONOHA_BATTLE_ACTION_CATALOG_H

#include "konoha/battle_action_loadout.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_action_catalog_error : std::uint8_t
{
    none,
    invalid_character,
    invalid_action_reference,
    capacity_exhausted,
};

struct battle_action_catalog_entry
{
    battle_action_source_kind kind =
            battle_action_source_kind::active_action;
    ability_id action_id = no_ability;
    std::uint8_t action_level = 0;
    std::uint8_t tool_slot = no_tool_slot;
    action_definition action = {};
};

struct battle_action_catalog_result
{
    battle_action_catalog_error error =
            battle_action_catalog_error::none;
    std::array<
            battle_action_catalog_entry,
            battle_action_catalog_capacity> entries = {};
    std::size_t count = 0;

    [[nodiscard]] const battle_action_catalog_entry* find(
            battle_action_source_kind kind,
            ability_id action_id,
            std::uint8_t tool_slot = no_tool_slot) const
    {
        for(std::size_t index = 0; index < count; ++index)
        {
            const battle_action_catalog_entry& entry =
                    entries[index];
            if(entry.kind == kind &&
                    entry.action_id == action_id &&
                    (kind !=
                             battle_action_source_kind::ninja_tool ||
                     entry.tool_slot == tool_slot))
            {
                return &entry;
            }
        }
        return nullptr;
    }
};

class battle_action_catalog
{
public:
    [[nodiscard]] static battle_action_catalog_result build(
            const battle_unit_instance& actor)
    {
        if(actor.character_id >= unit_definitions.size() ||
                ! unit_definitions[actor.character_id].active)
        {
            return {
                battle_action_catalog_error::invalid_character,
            };
        }

        battle_action_catalog_result result;
        const action_loadout<15> active_actions =
                build_primary_action_loadout(
                        actor.primary_action_ids,
                        actor.primary_action_levels);
        for(std::size_t index = 0;
                index < active_actions.count;
                ++index)
        {
            const ability_id id = active_actions.ids[index];
            if(id >= active_action_definitions.size() ||
                    active_action_definitions[id].id != id)
            {
                return {
                    battle_action_catalog_error::
                            invalid_action_reference,
                };
            }
        }
        // The original browser groups chakra/ninjutsu entries before
        // HP-cost taijutsu entries, while preserving source-slot order
        // inside each group. Ninja tools are appended afterward.
        for(int group = 0; group < 2; ++group)
        {
            for(std::size_t index = 0;
                    index < active_actions.count;
                    ++index)
            {
                const ability_id id = active_actions.ids[index];
                const action_definition& base =
                        active_action_definitions[id];
                const bool taijutsu =
                        base.cost.kind ==
                        action_cost_kind::current_hp;
                if(taijutsu != (group == 1))
                {
                    continue;
                }
                if(! _add(
                           battle_action_source_kind::
                                   active_action,
                           id,
                           active_actions.levels[index],
                           no_tool_slot,
                           apply_persistent_passive_action_modifiers(
                                   action_definition_at_level(
                                           base,
                                           active_actions
                                                   .levels[index]),
                                   actor.passives,
                                   passive_definitions),
                           result))
                {
                    return {
                        battle_action_catalog_error::
                                capacity_exhausted,
                    };
                }
            }
        }

        for(std::size_t slot = 0;
                slot < actor.equipped_tools.size();
                ++slot)
        {
            const ninja_tool_id id = actor.equipped_tools[slot];
            if(id == no_ninja_tool)
            {
                continue;
            }
            if(id >= ninja_tool_action_definitions.size() ||
                    ninja_tool_action_definitions[id].id != id)
            {
                return {
                    battle_action_catalog_error::
                            invalid_action_reference,
                };
            }
            if(! _add(
                       battle_action_source_kind::ninja_tool,
                       id,
                       0,
                       static_cast<std::uint8_t>(slot),
                       apply_persistent_passive_action_modifiers(
                               ninja_tool_action_for_slot(
                                       id,
                                       static_cast<std::uint8_t>(
                                               slot)),
                               actor.passives,
                               passive_definitions),
                       result))
            {
                return {
                    battle_action_catalog_error::
                            capacity_exhausted,
                };
            }
        }
        return result;
    }

private:
    [[nodiscard]] static bool _add(
            battle_action_source_kind kind,
            ability_id action_id,
            std::uint8_t action_level,
            std::uint8_t tool_slot,
            const action_definition& action,
            battle_action_catalog_result& result)
    {
        if(result.count == result.entries.size())
        {
            return false;
        }
        result.entries[result.count] = {
            kind,
            action_id,
            action_level,
            tool_slot,
            action,
        };
        ++result.count;
        return true;
    }
};

}

#endif
