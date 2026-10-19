#ifndef KONOHA_BATTLE_CAMPAIGN_H
#define KONOHA_BATTLE_CAMPAIGN_H

#include "konoha/battle_campaign_inventory.h"
#include "konoha/battle_progression.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr std::size_t
        battle_campaign_character_capacity =
                unit_definitions.size();
inline constexpr std::size_t
        battle_campaign_party_capacity = 3;
inline constexpr std::size_t
        battle_campaign_equipped_tool_capacity = 9;
using battle_campaign_party_equipment = std::array<
        std::array<
                ninja_tool_id,
                battle_campaign_equipped_tool_capacity>,
        battle_campaign_party_capacity>;

struct battle_campaign_character_record
{
    character_progression_record progression = {};
    std::array<
            std::uint8_t,
            battle_campaign_equipped_tool_capacity>
            equipped_tools = {};

    constexpr bool operator==(
            const battle_campaign_character_record&) const =
                    default;
};

struct battle_campaign_state
{
    std::uint16_t chapter_id = 0;
    std::uint32_t flags = 0;
    std::array<
            battle_campaign_character_record,
            battle_campaign_character_capacity>
            characters = {};
    std::array<
            std::uint8_t,
            battle_campaign_party_capacity>
            party = {};
    battle_campaign_inventory inventory = {};

    constexpr bool operator==(
            const battle_campaign_state&) const = default;
};

enum class battle_campaign_error : std::uint8_t
{
    none,
    invalid_character,
    inactive_character,
    duplicate_character,
    party_mismatch,
    invalid_tool,
    inventory_mismatch,
};

struct battle_campaign_party_result
{
    battle_campaign_error error =
            battle_campaign_error::none;
    std::array<
            character_progression_record,
            battle_campaign_party_capacity>
            progression = {};

    [[nodiscard]] constexpr bool success() const
    {
        return error == battle_campaign_error::none;
    }
};

[[nodiscard]] constexpr battle_campaign_state
empty_battle_campaign()
{
    battle_campaign_state result;
    for(std::size_t index = 0;
            index < result.characters.size();
            ++index)
    {
        result.characters[index]
                .progression.character_id =
                        static_cast<std::uint8_t>(index);
    }
    return result;
}

[[nodiscard]] inline bool
activate_battle_campaign_character(
        battle_campaign_state& campaign,
        const character_progression_record& progression)
{
    const std::size_t character_id =
            progression.character_id;
    if(! progression.active ||
            progression.level < 1 ||
            progression.level > 50 ||
            character_id == 0 ||
            character_id >=
                    battle_campaign_character_capacity ||
            ! unit_definitions[character_id].active)
    {
        return false;
    }

    character_progression_record initialized =
            progression;
    if(! initialized.action_states_initialized &&
            ! initialize_character_action_progression(
                    initialized,
                    unit_definitions[character_id]))
    {
        return false;
    }
    campaign.characters[character_id].progression =
            initialized;
    return true;
}

[[nodiscard]] constexpr bool
set_battle_campaign_party(
        battle_campaign_state& campaign,
        const std::array<
                std::uint8_t,
                battle_campaign_party_capacity>& party)
{
    bool saw_empty = false;
    for(std::size_t index = 0; index < party.size(); ++index)
    {
        const std::size_t character_id = party[index];
        if(character_id == 0)
        {
            saw_empty = true;
            continue;
        }
        if(saw_empty ||
                character_id >=
                        battle_campaign_character_capacity ||
                ! campaign.characters[character_id]
                           .progression.active)
        {
            return false;
        }
        for(std::size_t previous = 0;
                previous < index;
                ++previous)
        {
            if(party[previous] == character_id)
            {
                return false;
            }
        }
    }
    campaign.party = party;
    return true;
}

[[nodiscard]] constexpr battle_campaign_party_result
project_battle_campaign_party(
        const battle_campaign_state& campaign)
{
    battle_campaign_party_result result;
    for(std::size_t index = 0;
            index < campaign.party.size();
            ++index)
    {
        const std::size_t character_id =
                campaign.party[index];
        if(character_id == 0)
        {
            continue;
        }
        if(character_id >=
                battle_campaign_character_capacity)
        {
            result.error =
                    battle_campaign_error::
                            invalid_character;
            return result;
        }
        const character_progression_record& progression =
                campaign.characters[character_id]
                        .progression;
        if(! progression.active)
        {
            result.error =
                    battle_campaign_error::
                            inactive_character;
            return result;
        }
        if(progression.character_id != character_id)
        {
            result.error =
                    battle_campaign_error::
                            party_mismatch;
            return result;
        }
        for(std::size_t previous = 0;
                previous < index;
                ++previous)
        {
            if(campaign.party[previous] == character_id)
            {
                result.error =
                        battle_campaign_error::
                                duplicate_character;
                return result;
            }
        }
        result.progression[index] = progression;
    }
    return result;
}

[[nodiscard]] constexpr battle_campaign_error
merge_battle_campaign_party_progression(
        battle_campaign_state& campaign,
        const std::array<
                character_progression_record,
                battle_campaign_party_capacity>&
                progression)
{
    for(std::size_t index = 0;
            index < campaign.party.size();
            ++index)
    {
        const std::size_t character_id =
                campaign.party[index];
        if(character_id == 0)
        {
            if(progression[index].active)
            {
                return battle_campaign_error::
                        party_mismatch;
            }
            continue;
        }
        if(character_id >=
                battle_campaign_character_capacity)
        {
            return battle_campaign_error::
                    invalid_character;
        }
        if(! progression[index].active)
        {
            return battle_campaign_error::
                    inactive_character;
        }
        if(progression[index].character_id !=
                character_id)
        {
            return battle_campaign_error::
                    party_mismatch;
        }
    }

    for(std::size_t index = 0;
            index < campaign.party.size();
            ++index)
    {
        const std::size_t character_id =
                campaign.party[index];
        if(character_id != 0)
        {
            campaign.characters[character_id]
                    .progression = progression[index];
        }
    }
    return battle_campaign_error::none;
}

[[nodiscard]] constexpr battle_campaign_error
merge_battle_campaign_party_state(
        battle_campaign_state& campaign,
        const std::array<
                character_progression_record,
                battle_campaign_party_capacity>&
                progression,
        const battle_campaign_party_equipment& equipment)
{
    battle_campaign_state draft = campaign;
    const battle_campaign_error progression_error =
            merge_battle_campaign_party_progression(
                    draft, progression);
    if(progression_error != battle_campaign_error::none)
    {
        return progression_error;
    }

    for(std::size_t index = 0;
            index < draft.party.size();
            ++index)
    {
        const std::size_t character_id =
                draft.party[index];
        if(character_id == 0)
        {
            for(const ninja_tool_id tool : equipment[index])
            {
                if(tool != no_ninja_tool)
                {
                    return battle_campaign_error::
                            party_mismatch;
                }
            }
            continue;
        }
        for(const ninja_tool_id tool : equipment[index])
        {
            if(tool >= ninja_tool_action_definitions.size())
            {
                return battle_campaign_error::
                        invalid_tool;
            }
        }
        draft.characters[character_id].equipped_tools =
                equipment[index];
    }

    campaign = draft;
    return battle_campaign_error::none;
}

}

#endif
