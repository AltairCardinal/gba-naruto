#ifndef KONOHA_BATTLE_CAMPAIGN_SCENE_PROGRESSION_H
#define KONOHA_BATTLE_CAMPAIGN_SCENE_PROGRESSION_H

#include "konoha/battle_campaign.h"
#include "konoha/battle_scenario_loader.h"

#include <array>
#include <cstdint>

namespace konoha
{

[[nodiscard]] constexpr battle_campaign_error
apply_battle_campaign_scene_policy(
        const battle_campaign_state& campaign,
        battle_scenario_load_policy& policy)
{
    const battle_campaign_party_result projected =
            project_battle_campaign_party(campaign);
    if(! projected.success())
    {
        return projected.error;
    }

    battle_scenario_load_policy draft = policy;
    for(std::size_t party_index = 0;
            party_index < campaign.party.size();
            ++party_index)
    {
        const std::uint8_t character_id =
                campaign.party[party_index];
        if(character_id == 0)
        {
            continue;
        }
        if(draft.placeholder_characters[party_index] ==
                no_scenario_character)
        {
            draft.placeholder_characters[party_index] =
                    character_id;
        }

        bool tools_overridden =
                draft.character_equipped_tools_overridden[
                        character_id];
        if(! tools_overridden)
        {
            for(const ninja_tool_id tool :
                    draft.character_equipped_tools[
                            character_id])
            {
                if(tool != no_ninja_tool)
                {
                    tools_overridden = true;
                    break;
                }
            }
        }
        if(! tools_overridden)
        {
            draft.character_equipped_tools_overridden[
                    character_id] = true;
            draft.character_equipped_tools[
                    character_id] =
                            campaign.characters[
                                    character_id]
                                    .equipped_tools;
        }
    }

    policy = draft;
    return battle_campaign_error::none;
}

class battle_campaign_scene_progression
{
public:
    [[nodiscard]] constexpr battle_campaign_error begin(
            const battle_campaign_state& campaign)
    {
        const battle_campaign_party_result projected =
                project_battle_campaign_party(campaign);
        if(! projected.success())
        {
            _active = false;
            return projected.error;
        }
        _materials = campaign.inventory.materials;
        _party = campaign.party;
        _records = projected.progression;
        _equipped_tools = {};
        for(std::size_t index = 0;
                index < _party.size();
                ++index)
        {
            const std::size_t character_id =
                    _party[index];
            if(character_id != 0)
            {
                _equipped_tools[index] =
                        campaign.characters[
                                character_id]
                                .equipped_tools;
            }
        }
        _initial_equipped_tools = _equipped_tools;
        _active = true;
        return battle_campaign_error::none;
    }

    [[nodiscard]] constexpr battle_campaign_error commit(
            battle_campaign_state& campaign) const
    {
        if(! _active || campaign.party != _party)
        {
            return battle_campaign_error::
                    party_mismatch;
        }
        battle_campaign_state draft = campaign;
        const battle_campaign_error merge_error =
                merge_battle_campaign_party_state(
                        draft,
                        _records,
                        _equipped_tools);
        if(merge_error != battle_campaign_error::none)
        {
            return merge_error;
        }

        std::array<
                std::size_t,
                battle_campaign_ninja_tool_quantity_capacity>
                initial_counts = {};
        std::array<
                std::size_t,
                battle_campaign_ninja_tool_quantity_capacity>
                final_counts = {};
        for(std::size_t party_index = 0;
                party_index < _party.size();
                ++party_index)
        {
            for(const ninja_tool_id tool_id :
                    _initial_equipped_tools[party_index])
            {
                if(tool_id >= initial_counts.size())
                {
                    return battle_campaign_error::
                            invalid_tool;
                }
                if(tool_id != no_ninja_tool)
                {
                    ++initial_counts[tool_id];
                }
            }
            for(const ninja_tool_id tool_id :
                    _equipped_tools[party_index])
            {
                if(tool_id >= final_counts.size())
                {
                    return battle_campaign_error::
                            invalid_tool;
                }
                if(tool_id != no_ninja_tool)
                {
                    ++final_counts[tool_id];
                }
            }
        }
        for(std::size_t tool_id = 1;
                tool_id < initial_counts.size();
                ++tool_id)
        {
            if(final_counts[tool_id] >
                    initial_counts[tool_id])
            {
                return battle_campaign_error::
                        inventory_mismatch;
            }
            const std::size_t consumed =
                    initial_counts[tool_id] -
                    final_counts[tool_id];
            if(consumed >
                    draft.inventory.ninja_tools[tool_id])
            {
                return battle_campaign_error::
                        inventory_mismatch;
            }
            draft.inventory.ninja_tools[tool_id] =
                    static_cast<std::uint8_t>(
                            draft.inventory.ninja_tools[
                                    tool_id] -
                            consumed);
        }

        for(const auto quantity : _materials)
        {
            if(quantity > 99) return battle_campaign_error::inventory_mismatch;
        }
        draft.inventory.materials = _materials;
        campaign = draft;
        return battle_campaign_error::none;
    }

    [[nodiscard]] constexpr const std::array<
            character_progression_record,
            battle_campaign_party_capacity>& records() const
    {
        return _records;
    }

    [[nodiscard]] constexpr std::array<
            character_progression_record,
            battle_campaign_party_capacity>& records()
    {
        return _records;
    }

    [[nodiscard]] constexpr bool active() const
    {
        return _active;
    }

    [[nodiscard]] constexpr const
    battle_campaign_party_equipment& equipped_tools() const
    {
        return _equipped_tools;
    }

    [[nodiscard]] constexpr
    battle_campaign_party_equipment& equipped_tools()
    {
        return _equipped_tools;
    }

    [[nodiscard]] constexpr auto& materials() { return _materials; }
    [[nodiscard]] constexpr const auto& materials() const { return _materials; }

private:
    std::array<std::uint8_t, battle_campaign_material_quantity_capacity> _materials = {};
    std::array<
            std::uint8_t,
            battle_campaign_party_capacity>
            _party = {};
    std::array<
            character_progression_record,
            battle_campaign_party_capacity>
            _records = {};
    battle_campaign_party_equipment _equipped_tools = {};
    battle_campaign_party_equipment
            _initial_equipped_tools = {};
    bool _active = false;
};

}

#endif
