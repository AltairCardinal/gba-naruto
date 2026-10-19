#include "konoha/battle_campaign_scene_progression.h"
#include "konoha/battle_deployment_flow.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>

using namespace konoha;

namespace
{

character_progression_record active_character(
        std::uint8_t character_id)
{
    character_progression_record result = {
        character_id,
        10,
        0,
        0,
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
    for(const std::uint8_t character_id :
            { std::uint8_t(1),
              std::uint8_t(2),
              std::uint8_t(3) })
    {
        assert(activate_battle_campaign_character(
                campaign,
                active_character(character_id)));
    }
    assert(set_battle_campaign_party(
            campaign, { 1, 2, 3 }));
    campaign.characters[1].equipped_tools =
            { 1, 17, 73 };
    campaign.characters[2].equipped_tools =
            { 46, 2 };

    battle_scenario_load_policy policy;
    policy.placeholder_characters[3] = 35;
    policy.character_equipped_tools_overridden[2] =
            true;
    policy.character_equipped_tools[2] = { 93 };

    assert(apply_battle_campaign_scene_policy(
                   campaign, policy) ==
           battle_campaign_error::none);
    assert(policy.placeholder_characters[0] == 1);
    assert(policy.placeholder_characters[1] == 2);
    assert(policy.placeholder_characters[2] == 3);
    assert(policy.placeholder_characters[3] == 35);
    assert(policy.placeholder_characters[4] ==
           no_scenario_character);
    assert(policy.placeholder_characters[5] ==
           no_scenario_character);
    assert(policy.character_equipped_tools_overridden[1]);
    assert(policy.character_equipped_tools[1] ==
           campaign.characters[1].equipped_tools);
    assert(policy.character_equipped_tools[2][0] == 93);
    assert(policy.character_equipped_tools[2][1] ==
           no_ninja_tool);
    assert(policy.character_equipped_tools_overridden[3]);
    assert(policy.character_equipped_tools[3] ==
           campaign.characters[3].equipped_tools);

    battle_deployment_flow deployment;
    assert(deployment.prepare(
                   battle_scenario_definitions[1],
                   2,
                   policy)
                   .success());
    assert(deployment.entry(0)->character_id == 1);
    assert(deployment.entry(1)->character_id == 2);
    assert(deployment.entry(2)->character_id == 3);

    const battle_campaign_party_result progression =
            project_battle_campaign_party(campaign);
    assert(progression.success());
    battle_session<12> session;
    const battle_scenario_load_result loaded =
            load_battle_scenario(
                    battle_scenario_definitions[1],
                    2,
                    policy,
                    session,
                    progression.progression.data(),
                    progression.progression.size());
    assert(loaded.error ==
           battle_scenario_load_error::none);
    assert(session.unit_at(0)->character_id == 1);
    assert(session.unit_at(1)->character_id == 2);
    assert(session.unit_at(2)->character_id == 3);
    assert(session.unit_at(0)->equipped_tools[0] == 1);
    assert(session.unit_at(0)->equipped_tools[1] == 17);
    assert(session.unit_at(0)->equipped_tools[2] == 73);
    assert(session.unit_at(1)->equipped_tools[0] == 93);
    assert(session.unit_at(2)->equipped_tools[0] ==
           no_ninja_tool);

    battle_campaign_state invalid = campaign;
    invalid.party = { 1, 4, 3 };
    battle_scenario_load_policy unchanged;
    unchanged.placeholder_characters[5] = 42;
    const battle_scenario_load_policy before = unchanged;
    assert(apply_battle_campaign_scene_policy(
                   invalid, unchanged) ==
           battle_campaign_error::inactive_character);
    assert(unchanged.placeholder_characters ==
           before.placeholder_characters);
    assert(unchanged.character_equipped_tools ==
           before.character_equipped_tools);
    assert(
            unchanged.character_equipped_tools_overridden ==
            before.character_equipped_tools_overridden);
}
