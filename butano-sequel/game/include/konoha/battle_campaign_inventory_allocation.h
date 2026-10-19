#ifndef KONOHA_BATTLE_CAMPAIGN_INVENTORY_ALLOCATION_H
#define KONOHA_BATTLE_CAMPAIGN_INVENTORY_ALLOCATION_H

#include "konoha/battle_campaign.h"

#include <cstddef>

namespace konoha
{

[[nodiscard]] constexpr std::size_t
equipped_campaign_ninja_tool_count(
        const battle_campaign_state& campaign,
        ninja_tool_id tool_id)
{
    std::size_t result = 0;
    for(const battle_campaign_character_record& character :
            campaign.characters)
    {
        for(const ninja_tool_id equipped :
                character.equipped_tools)
        {
            if(equipped == tool_id)
            {
                ++result;
            }
        }
    }
    return result;
}

[[nodiscard]] constexpr std::size_t
available_campaign_ninja_tool_count(
        const battle_campaign_state& campaign,
        ninja_tool_id tool_id)
{
    if(tool_id == 0 ||
            tool_id >=
                    battle_campaign_ninja_tool_quantity_capacity)
    {
        return 0;
    }
    const std::size_t owned =
            campaign.inventory.ninja_tools[tool_id];
    const std::size_t equipped =
            equipped_campaign_ninja_tool_count(
                    campaign, tool_id);
    return owned > equipped ? owned - equipped : 0;
}

}

#endif
