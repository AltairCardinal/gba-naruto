#ifndef KONOHA_BATTLE_CAMPAIGN_EQUIPMENT_SERVICE_H
#define KONOHA_BATTLE_CAMPAIGN_EQUIPMENT_SERVICE_H

#include "konoha/battle_campaign_inventory_allocation.h"
#include "konoha/generated_battle_passive_content.h"
#include "konoha/generated_battle_result_content.h"
#include "konoha/ninja_tool_eligibility.h"

#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_campaign_equipment_error : std::uint8_t
{
    none,
    invalid_character,
    inactive_character,
    invalid_tool,
    invalid_slot,
    character_not_eligible,
    no_available_copy,
    capacity_reached,
    no_empty_slot,
    empty_slot,
};

[[nodiscard]] inline bool
valid_battle_campaign_equipment(
        const battle_campaign_state& campaign)
{
    std::array<
            std::size_t,
            battle_campaign_ninja_tool_quantity_capacity>
            equipped_counts = {};
    for(std::size_t character_id = 0;
            character_id < campaign.characters.size();
            ++character_id)
    {
        const battle_campaign_character_record& character =
                campaign.characters[character_id];
        std::size_t character_equipped_count = 0;
        for(const ninja_tool_id tool_id :
                character.equipped_tools)
        {
            if(tool_id == no_ninja_tool)
            {
                continue;
            }
            if(tool_id >= equipped_counts.size() ||
                    ! character.progression.active ||
                    character.progression.character_id !=
                            character_id ||
                    ! character_is_eligible(
                            ninja_tool_upgrade_recipes[tool_id],
                            static_cast<std::uint8_t>(
                                    character_id)))
            {
                return false;
            }
            ++character_equipped_count;
            ++equipped_counts[tool_id];
        }
        if(character_equipped_count != 0)
        {
            const character_stat_values stats =
                    character_stats_at_progression(
                            character.progression,
                            unit_definitions[character_id],
                            character_growth_definitions[
                                    character_id],
                            passive_definitions)
                            .stats;
            if(character_equipped_count >
                    static_cast<std::size_t>(
                            stats.ninja_tool_capacity))
            {
                return false;
            }
        }
    }
    for(std::size_t tool_id = 1;
            tool_id < equipped_counts.size();
            ++tool_id)
    {
        if(equipped_counts[tool_id] >
                campaign.inventory.ninja_tools[tool_id])
        {
            return false;
        }
    }
    return true;
}

[[nodiscard]] inline battle_campaign_equipment_error
equip_campaign_ninja_tool(
        battle_campaign_state& campaign,
        std::uint8_t character_id,
        ninja_tool_id tool_id)
{
    if(character_id == 0 ||
            character_id >=
                    battle_campaign_character_capacity)
    {
        return battle_campaign_equipment_error::
                invalid_character;
    }
    battle_campaign_character_record& character =
            campaign.characters[character_id];
    if(! character.progression.active ||
            character.progression.character_id !=
                    character_id)
    {
        return battle_campaign_equipment_error::
                inactive_character;
    }
    if(tool_id == 0 ||
            tool_id >=
                    battle_campaign_ninja_tool_quantity_capacity)
    {
        return battle_campaign_equipment_error::
                invalid_tool;
    }
    if(! character_is_eligible(
               ninja_tool_upgrade_recipes[tool_id],
               character_id))
    {
        return battle_campaign_equipment_error::
                character_not_eligible;
    }

    std::size_t equipped_count = 0;
    std::size_t empty_slot =
            battle_campaign_equipped_tool_capacity;
    for(std::size_t index = 0;
            index < character.equipped_tools.size();
            ++index)
    {
        if(character.equipped_tools[index] == 0)
        {
            if(empty_slot ==
                    battle_campaign_equipped_tool_capacity)
            {
                empty_slot = index;
            }
        }
        else
        {
            ++equipped_count;
        }
    }
    const character_stat_values stats =
            character_stats_at_progression(
                    character.progression,
                    unit_definitions[character_id],
                    character_growth_definitions[
                            character_id],
                    passive_definitions)
                    .stats;
    if(equipped_count >=
            static_cast<std::size_t>(
                    stats.ninja_tool_capacity))
    {
        return battle_campaign_equipment_error::
                capacity_reached;
    }
    if(available_campaign_ninja_tool_count(
               campaign, tool_id) == 0)
    {
        return battle_campaign_equipment_error::
                no_available_copy;
    }
    if(empty_slot ==
            battle_campaign_equipped_tool_capacity)
    {
        return battle_campaign_equipment_error::
                no_empty_slot;
    }

    character.equipped_tools[empty_slot] = tool_id;
    return battle_campaign_equipment_error::none;
}

[[nodiscard]] inline battle_campaign_equipment_error
unequip_campaign_ninja_tool(
        battle_campaign_state& campaign,
        std::uint8_t character_id,
        std::size_t slot)
{
    if(character_id == 0 ||
            character_id >=
                    battle_campaign_character_capacity)
    {
        return battle_campaign_equipment_error::
                invalid_character;
    }
    battle_campaign_character_record& character =
            campaign.characters[character_id];
    if(! character.progression.active ||
            character.progression.character_id !=
                    character_id)
    {
        return battle_campaign_equipment_error::
                inactive_character;
    }
    if(slot >= character.equipped_tools.size())
    {
        return battle_campaign_equipment_error::
                invalid_slot;
    }
    if(character.equipped_tools[slot] == 0)
    {
        return battle_campaign_equipment_error::
                empty_slot;
    }
    character.equipped_tools[slot] = 0;
    return battle_campaign_equipment_error::none;
}

}

#endif
