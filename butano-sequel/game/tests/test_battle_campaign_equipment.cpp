#include "konoha/battle_campaign_equipment_service.h"

#include <cassert>

using namespace konoha;

namespace
{

character_progression_record active_character(
        std::uint8_t character_id,
        int level = 1)
{
    character_progression_record result = {
        character_id,
        level,
        0,
        0,
        true,
    };
    assert(initialize_character_action_progression(
            result,
            unit_definitions[character_id]));
    return result;
}

battle_campaign_state campaign_fixture()
{
    battle_campaign_state result =
            empty_battle_campaign();
    assert(activate_battle_campaign_character(
            result, active_character(1)));
    assert(activate_battle_campaign_character(
            result, active_character(2)));
    return result;
}

}

int main()
{
    battle_campaign_state campaign =
            campaign_fixture();
    campaign.inventory.ninja_tools[1] = 2;

    assert(equip_campaign_ninja_tool(
                   campaign, 1, 1) ==
           battle_campaign_equipment_error::none);
    assert(campaign.characters[1]
                   .equipped_tools[0] == 1);
    assert(campaign.inventory.ninja_tools[1] == 2);
    assert(equip_campaign_ninja_tool(
                   campaign, 1, 1) ==
           battle_campaign_equipment_error::none);
    assert(campaign.characters[1]
                   .equipped_tools[1] == 1);
    const battle_campaign_state before_unavailable =
            campaign;
    assert(equip_campaign_ninja_tool(
                   campaign, 2, 1) ==
           battle_campaign_equipment_error::
                   no_available_copy);
    assert(campaign == before_unavailable);

    assert(unequip_campaign_ninja_tool(
                   campaign, 1, 0) ==
           battle_campaign_equipment_error::none);
    assert(campaign.characters[1]
                   .equipped_tools[0] == 0);
    assert(campaign.characters[1]
                   .equipped_tools[1] == 1);
    assert(campaign.inventory.ninja_tools[1] == 2);
    assert(equip_campaign_ninja_tool(
                   campaign, 2, 1) ==
           battle_campaign_equipment_error::none);
    assert(campaign.characters[2]
                   .equipped_tools[0] == 1);

    const battle_campaign_state before_empty =
            campaign;
    assert(unequip_campaign_ninja_tool(
                   campaign, 1, 0) ==
           battle_campaign_equipment_error::empty_slot);
    assert(campaign == before_empty);

    battle_campaign_state capacity =
            campaign_fixture();
    capacity.inventory.ninja_tools[1] = 5;
    capacity.characters[1].equipped_tools =
            { 1, 1, 1, 1, 1, 0, 0, 0, 0 };
    const battle_campaign_state before_capacity =
            capacity;
    assert(equip_campaign_ninja_tool(
                   capacity, 1, 1) ==
           battle_campaign_equipment_error::
                   capacity_reached);
    assert(capacity == before_capacity);

    battle_campaign_state trained_capacity =
            campaign_fixture();
    battle_campaign_character_record& trained_naruto =
            trained_capacity.characters[1];
    trained_naruto.progression.level = 16;
    assert(synchronize_character_action_unlocks(
            trained_naruto.progression,
            unit_definitions[1]));
    assert(
            trained_naruto.progression
                    .secondary_action_levels[6] ==
            unlocked_action_level);
    trained_naruto.progression
            .secondary_action_levels[6] = 1;
    trained_capacity.inventory.ninja_tools[1] = 9;
    const int untrained_capacity =
            character_stats_at_level(
                    unit_definitions[1],
                    character_growth_definitions[1],
                    trained_naruto.progression.level)
                    .ninja_tool_capacity;
    for(int index = 0; index <= untrained_capacity; ++index)
    {
        assert(equip_campaign_ninja_tool(
                       trained_capacity, 1, 1) ==
               battle_campaign_equipment_error::none);
    }
    assert(
            trained_naruto.equipped_tools[
                    static_cast<std::size_t>(
                            untrained_capacity)] == 1);

    battle_campaign_state restricted =
            campaign_fixture();
    restricted.inventory.ninja_tools[14] = 1;
    const battle_campaign_state before_restricted =
            restricted;
    assert(equip_campaign_ninja_tool(
                   restricted, 1, 14) ==
           battle_campaign_equipment_error::
                   character_not_eligible);
    assert(restricted == before_restricted);

    assert(activate_battle_campaign_character(
            restricted, active_character(13)));
    assert(equip_campaign_ninja_tool(
                   restricted, 13, 14) ==
           battle_campaign_equipment_error::none);
    assert(restricted.characters[13]
                   .equipped_tools[0] == 14);

    battle_campaign_state invalid =
            campaign_fixture();
    invalid.inventory.ninja_tools[1] = 1;
    const battle_campaign_state before_invalid =
            invalid;
    assert(equip_campaign_ninja_tool(
                   invalid, 0, 1) ==
           battle_campaign_equipment_error::
                   invalid_character);
    assert(equip_campaign_ninja_tool(
                   invalid, 63, 1) ==
           battle_campaign_equipment_error::
                   invalid_character);
    assert(equip_campaign_ninja_tool(
                   invalid, 3, 1) ==
           battle_campaign_equipment_error::
                   inactive_character);
    assert(equip_campaign_ninja_tool(
                   invalid, 1, 0) ==
           battle_campaign_equipment_error::invalid_tool);
    assert(equip_campaign_ninja_tool(
                   invalid, 1, 94) ==
           battle_campaign_equipment_error::invalid_tool);
    assert(unequip_campaign_ninja_tool(
                   invalid, 1, 9) ==
           battle_campaign_equipment_error::invalid_slot);
    assert(invalid == before_invalid);
}
