#include "konoha/battle_campaign.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

character_progression_record active_character(
        std::uint8_t character_id,
        int level,
        int experience,
        int training_points)
{
    character_progression_record result = {
        character_id,
        level,
        experience,
        training_points,
        true,
    };
    assert(initialize_character_action_progression(
            result,
            unit_definitions[character_id]));
    return result;
}

}

int main()
{
    battle_campaign_state campaign =
            empty_battle_campaign();
    assert(campaign.characters.size() == 63);
    for(std::size_t index = 0;
            index < campaign.characters.size();
            ++index)
    {
        assert(
                campaign.characters[index]
                        .progression.character_id ==
                index);
        assert(! campaign.characters[index]
                         .progression.active);
    }

    const character_progression_record naruto =
            active_character(1, 1, 100, 0);
    const character_progression_record sasuke =
            active_character(2, 3, 20, 2);
    const character_progression_record sakura =
            active_character(3, 2, 10, 1);
    assert(activate_battle_campaign_character(
            campaign, naruto));
    assert(activate_battle_campaign_character(
            campaign, sasuke));
    assert(activate_battle_campaign_character(
            campaign, sakura));
    assert(set_battle_campaign_party(
            campaign, { 1, 2, 3 }));

    const battle_campaign_party_result projected =
            project_battle_campaign_party(campaign);
    assert(projected.error ==
           battle_campaign_error::none);
    assert(projected.progression[0] == naruto);
    assert(projected.progression[1] == sasuke);
    assert(projected.progression[2] == sakura);

    const battle_campaign_state before_merge =
            campaign;
    std::array<character_progression_record, 3>
            settled = projected.progression;
    settled[0].level = 2;
    settled[0].experience = 25;
    settled[0].training_points = 0;
    settled[0].primary_action_levels[6] = 1;
    assert(merge_battle_campaign_party_progression(
            campaign, settled) ==
           battle_campaign_error::none);
    assert(campaign.characters[1].progression ==
           settled[0]);
    for(std::size_t index = 0;
            index < campaign.characters.size();
            ++index)
    {
        if(index != 1)
        {
            assert(
                    campaign.characters[index] ==
                    before_merge.characters[index]);
        }
    }

    battle_campaign_state invalid_party = campaign;
    const battle_campaign_state before_invalid_party =
            invalid_party;
    assert(! set_battle_campaign_party(
            invalid_party, { 1, 1, 3 }));
    assert(invalid_party == before_invalid_party);
    assert(! set_battle_campaign_party(
            invalid_party, { 1, 4, 3 }));
    assert(invalid_party == before_invalid_party);
    assert(! set_battle_campaign_party(
            invalid_party, { 1, 63, 3 }));
    assert(invalid_party == before_invalid_party);

    battle_campaign_state missing_character = campaign;
    missing_character.party = { 1, 4, 3 };
    const battle_campaign_party_result missing =
            project_battle_campaign_party(
                    missing_character);
    assert(missing.error ==
           battle_campaign_error::inactive_character);

    std::array<character_progression_record, 3>
            wrong_identity = settled;
    wrong_identity[1].character_id = 5;
    const battle_campaign_state before_wrong_identity =
            campaign;
    assert(merge_battle_campaign_party_progression(
                   campaign,
                   wrong_identity) ==
           battle_campaign_error::party_mismatch);
    assert(campaign == before_wrong_identity);

    character_progression_record inactive = {};
    inactive.character_id = 5;
    const battle_campaign_state before_inactive =
            campaign;
    assert(! activate_battle_campaign_character(
            campaign, inactive));
    assert(campaign == before_inactive);

    character_progression_record invalid_character =
            naruto;
    invalid_character.character_id = 63;
    assert(! activate_battle_campaign_character(
            campaign, invalid_character));
    assert(campaign == before_inactive);

    battle_campaign_state invalid_tool_campaign =
            campaign;
    const battle_campaign_state
            before_invalid_tool_campaign =
                    invalid_tool_campaign;
    battle_campaign_party_equipment invalid_equipment = {};
    invalid_equipment[0][0] = 94;
    assert(merge_battle_campaign_party_state(
                   invalid_tool_campaign,
                   project_battle_campaign_party(
                           invalid_tool_campaign)
                           .progression,
                   invalid_equipment) ==
           battle_campaign_error::invalid_tool);
    assert(invalid_tool_campaign ==
           before_invalid_tool_campaign);
}
