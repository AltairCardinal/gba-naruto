#ifndef KONOHA_NINJA_TOOL_UPGRADE_SERVICE_H
#define KONOHA_NINJA_TOOL_UPGRADE_SERVICE_H

#include "konoha/battle_campaign.h"
#include "konoha/battle_campaign_inventory_allocation.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/ninja_tool_eligibility.h"

#include <cstddef>
#include <cstdint>
#include <limits>

namespace konoha
{

enum class ninja_tool_upgrade_error : std::uint8_t
{
    none,
    invalid_output_tool,
    no_recipe,
    missing_parent_tool,
    missing_material,
    output_full,
    invalid_character,
    inactive_character,
    parent_not_equipped,
    character_not_eligible,
    parent_copy_equipped,
};

[[nodiscard]] inline ninja_tool_upgrade_error
upgrade_ninja_tool(
        battle_campaign_state& campaign,
        ninja_tool_id output_tool_id,
        std::uint8_t equipped_character_id = 0)
{
    const std::size_t output_index = output_tool_id;
    if(output_index == 0 ||
            output_index >=
                    ninja_tool_upgrade_recipes.size())
    {
        return ninja_tool_upgrade_error::
                invalid_output_tool;
    }

    const ninja_tool_upgrade_recipe& recipe =
            ninja_tool_upgrade_recipes[output_index];
    const std::size_t parent_index =
            recipe.parent_tool_id;
    const std::size_t material_index =
            recipe.required_material_id;
    if(recipe.output_tool_id != output_tool_id ||
            parent_index == 0 ||
            parent_index >=
                    battle_campaign_ninja_tool_quantity_capacity ||
            material_index == 0 ||
            material_index >=
                    battle_campaign_material_quantity_capacity)
    {
        return ninja_tool_upgrade_error::no_recipe;
    }
    if(campaign.inventory.ninja_tools[parent_index] == 0)
    {
        return ninja_tool_upgrade_error::
                missing_parent_tool;
    }
    if(campaign.inventory.materials[material_index] == 0)
    {
        return ninja_tool_upgrade_error::
                missing_material;
    }
    if(campaign.inventory.ninja_tools[output_index] ==
            std::numeric_limits<std::uint8_t>::max())
    {
        return ninja_tool_upgrade_error::output_full;
    }
    const std::size_t equipped_parent_count =
            equipped_campaign_ninja_tool_count(
                    campaign,
                    recipe.parent_tool_id);
    if(campaign.inventory.ninja_tools[parent_index] <
                    equipped_parent_count ||
            (equipped_character_id == 0 &&
             campaign.inventory.ninja_tools[
                     parent_index] ==
                     equipped_parent_count))
    {
        return ninja_tool_upgrade_error::
                parent_copy_equipped;
    }

    std::size_t equipped_slot =
            battle_campaign_equipped_tool_capacity;
    if(equipped_character_id != 0)
    {
        if(equipped_character_id >=
                battle_campaign_character_capacity)
        {
            return ninja_tool_upgrade_error::
                    invalid_character;
        }
        battle_campaign_character_record& character =
                campaign.characters[equipped_character_id];
        if(! character.progression.active ||
                character.progression.character_id !=
                        equipped_character_id)
        {
            return ninja_tool_upgrade_error::
                    inactive_character;
        }
        if(! character_is_eligible(
                   recipe,
                   equipped_character_id))
        {
            return ninja_tool_upgrade_error::
                    character_not_eligible;
        }
        for(std::size_t index = 0;
                index < character.equipped_tools.size();
                ++index)
        {
            if(character.equipped_tools[index] ==
                    recipe.parent_tool_id)
            {
                equipped_slot = index;
                break;
            }
        }
        if(equipped_slot ==
                battle_campaign_equipped_tool_capacity)
        {
            return ninja_tool_upgrade_error::
                    parent_not_equipped;
        }
    }

    battle_campaign_state draft = campaign;
    --draft.inventory.ninja_tools[parent_index];
    --draft.inventory.materials[material_index];
    ++draft.inventory.ninja_tools[output_index];
    if(equipped_character_id != 0)
    {
        draft.characters[equipped_character_id]
                .equipped_tools[equipped_slot] =
                        output_tool_id;
    }
    campaign = draft;
    return ninja_tool_upgrade_error::none;
}

}

#endif
