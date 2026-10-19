#include "konoha/battle_campaign_save.h"
#include "konoha/battle_campaign_scene_progression.h"
#include "konoha/battle_preparation_flow.h"
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
    assert(activate_battle_campaign_character(
            campaign, active_character(1)));
    assert(activate_battle_campaign_character(
            campaign, active_character(2)));
    assert(activate_battle_campaign_character(
            campaign, active_character(3)));
    assert(set_battle_campaign_party(
            campaign, { 1, 2, 3 }));
    campaign.inventory.ninja_tools[1] = 1;

    battle_preparation_flow preparation;
    assert(preparation.load(campaign, 1));
    assert(preparation.confirm());
    assert(preparation.snapshot().phase ==
           battle_preparation_phase::equipment_root);
    assert(preparation.switch_character(1));
    assert(preparation.snapshot().character_id == 2);
    assert(preparation.snapshot().equipment_option ==
           battle_preparation_equipment_option::equip);
    assert(preparation.confirm());
    assert(preparation.snapshot().phase ==
           battle_preparation_phase::equip);
    assert(preparation.snapshot().equipment_tool_id == 1);
    assert(preparation.confirm());
    assert(preparation.snapshot()
                   .last_equipment_succeeded);
    assert(preparation.confirm());
    assert(preparation.snapshot().phase ==
           battle_preparation_phase::equipment_root);

    battle_campaign_save_slot saved;
    assert(encode_battle_campaign_slot(
                   campaign, 1, saved) ==
           battle_campaign_save_error::none);
    const battle_campaign_save_decode_result decoded =
            decode_battle_campaign_slot(saved);
    assert(decoded.valid());
    assert(decoded.campaign.characters[1]
                   .equipped_tools[0] ==
           no_ninja_tool);
    assert(decoded.campaign.characters[2]
                   .equipped_tools[0] == 1);
    assert(decoded.campaign.inventory.ninja_tools[1] == 1);
    assert(available_campaign_ninja_tool_count(
                   decoded.campaign, 1) == 0);

    battle_scenario_load_policy policy;
    assert(apply_battle_campaign_scene_policy(
                   decoded.campaign, policy) ==
           battle_campaign_error::none);
    const battle_campaign_party_result projected =
            project_battle_campaign_party(
                    decoded.campaign);
    assert(projected.success());
    battle_session<12> session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[1],
                   2,
                   policy,
                   session,
                   projected.progression.data(),
                   projected.progression.size())
                   .error ==
           battle_scenario_load_error::none);
    assert(session.unit_at(0)->original_character_id == 1);
    assert(session.unit_at(0)->equipped_tools[0] ==
           no_ninja_tool);
    assert(session.unit_at(1)->original_character_id == 2);
    assert(session.unit_at(1)->equipped_tools[0] == 1);
}
