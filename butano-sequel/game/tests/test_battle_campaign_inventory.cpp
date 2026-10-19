#include "konoha/ninja_tool_upgrade_service.h"

#include <cassert>
#include <cstdint>
#include <limits>

using namespace konoha;

namespace
{

character_progression_record active_character(
        std::uint8_t character_id)
{
    character_progression_record result = {
        character_id,
        1,
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
    return result;
}

}

int main()
{
    static_assert(
            battle_campaign_ninja_tool_quantity_capacity ==
            94);
    static_assert(
            battle_campaign_material_quantity_capacity ==
            18);

    battle_campaign_state bag_only =
            campaign_fixture();
    bag_only.inventory.ninja_tools[1] = 1;
    bag_only.inventory.materials[3] = 1;
    assert(upgrade_ninja_tool(
                   bag_only, 2, 0) ==
           ninja_tool_upgrade_error::none);
    assert(bag_only.inventory.ninja_tools[1] == 0);
    assert(bag_only.inventory.ninja_tools[2] == 1);
    assert(bag_only.inventory.materials[3] == 0);

    battle_campaign_state equipped =
            campaign_fixture();
    equipped.inventory.ninja_tools[1] = 2;
    equipped.inventory.materials[3] = 1;
    equipped.characters[1].equipped_tools =
            { 1, 0, 1, 0, 0, 0, 0, 0, 0 };
    assert(upgrade_ninja_tool(
                   equipped, 2, 1) ==
           ninja_tool_upgrade_error::none);
    assert(equipped.inventory.ninja_tools[1] == 1);
    assert(equipped.inventory.ninja_tools[2] == 1);
    assert(equipped.inventory.materials[3] == 0);
    assert(equipped.characters[1]
                   .equipped_tools[0] == 2);
    assert(equipped.characters[1]
                   .equipped_tools[2] == 1);

    auto rejects_without_mutation =
            [](battle_campaign_state value,
               ninja_tool_id output,
               std::uint8_t character,
               ninja_tool_upgrade_error expected) {
                const battle_campaign_state before =
                        value;
                assert(upgrade_ninja_tool(
                               value,
                               output,
                               character) == expected);
                assert(value == before);
            };

    rejects_without_mutation(
            campaign_fixture(),
            0,
            0,
            ninja_tool_upgrade_error::
                    invalid_output_tool);
    rejects_without_mutation(
            campaign_fixture(),
            1,
            0,
            ninja_tool_upgrade_error::no_recipe);

    battle_campaign_state missing_parent =
            campaign_fixture();
    missing_parent.inventory.materials[3] = 1;
    rejects_without_mutation(
            missing_parent,
            2,
            0,
            ninja_tool_upgrade_error::
                    missing_parent_tool);

    battle_campaign_state missing_material =
            campaign_fixture();
    missing_material.inventory.ninja_tools[1] = 1;
    rejects_without_mutation(
            missing_material,
            2,
            0,
            ninja_tool_upgrade_error::
                    missing_material);

    battle_campaign_state output_full =
            campaign_fixture();
    output_full.inventory.ninja_tools[1] = 1;
    output_full.inventory.ninja_tools[2] =
            std::numeric_limits<std::uint8_t>::max();
    output_full.inventory.materials[3] = 1;
    rejects_without_mutation(
            output_full,
            2,
            0,
            ninja_tool_upgrade_error::output_full);

    battle_campaign_state invalid_character =
            campaign_fixture();
    invalid_character.inventory.ninja_tools[1] = 1;
    invalid_character.inventory.materials[3] = 1;
    rejects_without_mutation(
            invalid_character,
            2,
            63,
            ninja_tool_upgrade_error::
                    invalid_character);
    rejects_without_mutation(
            invalid_character,
            2,
            2,
            ninja_tool_upgrade_error::
                    inactive_character);
    rejects_without_mutation(
            invalid_character,
            2,
            1,
            ninja_tool_upgrade_error::
                    parent_not_equipped);

    battle_campaign_state restricted =
            campaign_fixture();
    restricted.inventory.ninja_tools[14] = 1;
    restricted.inventory.materials[3] = 1;
    restricted.characters[1].equipped_tools[0] = 14;
    rejects_without_mutation(
            restricted,
            15,
            1,
            ninja_tool_upgrade_error::
                    character_not_eligible);

    battle_campaign_state allowed =
            empty_battle_campaign();
    assert(activate_battle_campaign_character(
            allowed, active_character(13)));
    allowed.inventory.ninja_tools[14] = 1;
    allowed.inventory.materials[3] = 1;
    allowed.characters[13].equipped_tools[0] = 14;
    assert(upgrade_ninja_tool(
                   allowed, 15, 13) ==
           ninja_tool_upgrade_error::none);
    assert(allowed.characters[13]
                   .equipped_tools[0] == 15);

    battle_campaign_state allocated_parent =
            campaign_fixture();
    allocated_parent.inventory.ninja_tools[1] = 1;
    allocated_parent.inventory.materials[3] = 1;
    allocated_parent.characters[1]
            .equipped_tools[0] = 1;
    rejects_without_mutation(
            allocated_parent,
            2,
            0,
            ninja_tool_upgrade_error::
                    parent_copy_equipped);
}
