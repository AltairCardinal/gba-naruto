#include "konoha/battle_preparation_flow.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_campaign_state campaign_fixture()
{
    battle_campaign_state result =
            empty_battle_campaign();
    character_progression_record naruto = {
        1,
        1,
        0,
        0,
        true,
    };
    assert(initialize_character_action_progression(
            naruto,
            unit_definitions[1]));
    assert(activate_battle_campaign_character(
            result, naruto));
    assert(set_battle_campaign_party(
            result, { 1, 0, 0 }));
    result.characters[1].equipped_tools[0] = 1;
    result.inventory.ninja_tools[1] = 1;
    result.inventory.ninja_tools[93] = 1;
    return result;
}

battle_campaign_state party_campaign_fixture()
{
    battle_campaign_state result =
            campaign_fixture();
    character_progression_record sasuke = {
        2,
        1,
        0,
        0,
        true,
    };
    assert(initialize_character_action_progression(
            sasuke,
            unit_definitions[2]));
    assert(activate_battle_campaign_character(
            result, sasuke));
    assert(set_battle_campaign_party(
            result, { 1, 2, 0 }));
    result.characters[1].equipped_tools = {};
    result.inventory.ninja_tools = {};
    result.inventory.ninja_tools[1] = 1;
    return result;
}

}

int main()
{
    battle_campaign_state overview_campaign =
            campaign_fixture();
    battle_preparation_flow overview_flow;
    assert(overview_flow.load(
            overview_campaign, 1, true));
    assert(overview_flow.snapshot().phase ==
           battle_preparation_phase::overview);
    assert(! overview_flow.move(1));
    assert(overview_flow.confirm());
    assert(overview_flow.snapshot().phase ==
           battle_preparation_phase::root);

    battle_campaign_state start_campaign =
            campaign_fixture();
    battle_preparation_flow start_flow;
    assert(start_flow.load(start_campaign, 1));
    battle_preparation_snapshot state =
            start_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::root);
    assert(state.root_option ==
           battle_preparation_root_option::
                   party_equipment);
    assert(start_flow.move(1));
    assert(start_flow.move(1));
    assert(start_flow.snapshot().root_option ==
           battle_preparation_root_option::
                   start_battle);
    assert(start_flow.confirm());
    state = start_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::
                   start_confirmation);
    assert(state.start_confirmation_yes);
    assert(start_flow.move(1));
    state = start_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::
                   start_confirmation);
    assert(! state.start_confirmation_yes);
    assert(start_flow.confirm());
    assert(start_flow.snapshot().phase ==
           battle_preparation_phase::root);
    assert(start_flow.confirm());
    assert(start_flow.snapshot().phase ==
           battle_preparation_phase::
                   start_confirmation);
    assert(start_flow.cancel());
    assert(start_flow.snapshot().phase ==
           battle_preparation_phase::root);
    assert(start_flow.confirm());
    assert(start_flow.snapshot().phase ==
           battle_preparation_phase::
                   start_confirmation);
    assert(start_flow.confirm());
    assert(start_flow.snapshot().phase ==
           battle_preparation_phase::ready);
    assert(start_campaign == campaign_fixture());

    battle_campaign_state party_campaign =
            party_campaign_fixture();
    battle_preparation_flow party_flow;
    assert(party_flow.load(party_campaign, 1));
    state = party_flow.snapshot();
    assert(state.party_count == 2);
    assert(state.party_index == 0);
    assert(state.character_id == 1);
    assert(! party_flow.switch_character(1));
    assert(party_flow.confirm());
    assert(party_flow.snapshot().phase ==
           battle_preparation_phase::equipment_root);
    assert(party_flow.switch_character(1));
    state = party_flow.snapshot();
    assert(state.party_index == 1);
    assert(state.character_id == 2);
    assert(party_flow.confirm());
    assert(party_flow.snapshot().phase ==
           battle_preparation_phase::equip);
    assert(party_flow.snapshot().equipment_tool_id == 1);
    assert(party_flow.confirm());
    assert(party_flow.snapshot()
                   .last_equipment_succeeded);
    assert(party_campaign.characters[1]
                   .equipped_tools[0] == 0);
    assert(party_campaign.characters[2]
                   .equipped_tools[0] == 1);
    assert(party_campaign.inventory.ninja_tools[1] == 1);
    assert(party_flow.confirm());
    assert(party_flow.snapshot().phase ==
           battle_preparation_phase::equipment_root);
    assert(party_flow.switch_character(-1));
    state = party_flow.snapshot();
    assert(state.party_index == 0);
    assert(state.character_id == 1);
    assert(! party_flow.switch_character(0));
    assert(party_flow.cancel());
    assert(party_flow.snapshot().phase ==
           battle_preparation_phase::root);

    battle_campaign_state equipment_campaign =
            campaign_fixture();
    battle_preparation_flow equipment_flow;
    assert(equipment_flow.load(equipment_campaign, 1));
    assert(equipment_flow.confirm());
    state = equipment_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::equipment_root);
    assert(state.equipment_option ==
           battle_preparation_equipment_option::equip);
    assert(equipment_flow.confirm());
    state = equipment_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::equip);
    assert(state.equipment_count == 1);
    assert(state.equipment_index == 0);
    assert(state.equipment_tool_id == 93);
    assert(state.equipment_owned_quantity == 1);
    assert(state.equipment_equipped_quantity == 0);
    assert(state.equipment_available_quantity == 1);
    assert(equipment_flow.confirm());
    state = equipment_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::feedback);
    assert(state.last_operation ==
           battle_preparation_operation::equip);
    assert(state.last_equipment_error ==
           battle_campaign_equipment_error::none);
    assert(state.last_equipment_succeeded);
    assert(equipment_campaign.characters[1]
                   .equipped_tools[1] == 93);
    assert(equipment_campaign.inventory.ninja_tools[93] ==
           1);
    assert(equipment_flow.confirm());
    assert(equipment_flow.snapshot().phase ==
           battle_preparation_phase::equipment_root);

    assert(equipment_flow.move(1));
    assert(equipment_flow.snapshot().equipment_option ==
           battle_preparation_equipment_option::unequip);
    assert(equipment_flow.confirm());
    state = equipment_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::unequip);
    assert(state.equipment_count == 2);
    assert(state.equipment_slot == 0);
    assert(state.equipment_tool_id == 1);
    assert(equipment_flow.confirm());
    state = equipment_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::feedback);
    assert(state.last_operation ==
           battle_preparation_operation::unequip);
    assert(state.last_equipment_succeeded);
    assert(equipment_campaign.characters[1]
                   .equipped_tools[0] == 0);
    assert(equipment_campaign.inventory.ninja_tools[1] ==
           1);
    assert(equipment_flow.confirm());
    state = equipment_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::unequip);
    assert(state.equipment_count == 1);
    assert(state.equipment_slot == 1);
    assert(state.equipment_tool_id == 93);
    assert(equipment_flow.cancel());
    assert(equipment_flow.snapshot().phase ==
           battle_preparation_phase::equipment_root);
    assert(equipment_flow.cancel());
    assert(equipment_flow.snapshot().phase ==
           battle_preparation_phase::root);

    battle_campaign_state upgrade_campaign =
            campaign_fixture();
    battle_preparation_flow upgrade_flow;
    assert(upgrade_flow.load(upgrade_campaign, 1));
    assert(upgrade_flow.confirm());
    assert(upgrade_flow.move(1));
    assert(upgrade_flow.move(1));
    assert(upgrade_flow.snapshot().equipment_option ==
           battle_preparation_equipment_option::upgrade);
    assert(upgrade_flow.confirm());
    state = upgrade_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::upgrade);
    assert(state.upgrade_count == 4);
    assert(state.output_tool_id == 2);
    assert(state.parent_tool_id == 1);
    assert(state.required_material_id == 3);
    assert(state.parent_quantity == 1);
    assert(state.material_quantity == 0);

    const battle_campaign_state before_failure =
            upgrade_campaign;
    assert(upgrade_flow.confirm());
    state = upgrade_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::feedback);
    assert(state.last_upgrade_error ==
           ninja_tool_upgrade_error::
                   missing_material);
    assert(! state.last_upgrade_succeeded);
    assert(upgrade_campaign == before_failure);

    upgrade_campaign.inventory.materials[3] = 1;
    assert(upgrade_flow.confirm());
    assert(upgrade_flow.snapshot().phase ==
           battle_preparation_phase::upgrade);
    assert(upgrade_flow.snapshot().output_tool_id == 2);
    assert(upgrade_flow.confirm());
    state = upgrade_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::feedback);
    assert(state.last_upgrade_error ==
           ninja_tool_upgrade_error::none);
    assert(state.last_upgrade_succeeded);
    assert(state.output_tool_id == 2);
    assert(upgrade_campaign.inventory.ninja_tools[1] ==
           0);
    assert(upgrade_campaign.inventory.ninja_tools[2] ==
           1);
    assert(upgrade_campaign.inventory.materials[3] ==
           0);
    assert(upgrade_campaign.characters[1]
                   .equipped_tools[0] == 2);

    assert(upgrade_flow.confirm());
    state = upgrade_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::upgrade);
    assert(state.output_tool_id == 3);
    assert(state.parent_tool_id == 2);
    assert(upgrade_flow.cancel());
    assert(upgrade_flow.snapshot().phase ==
           battle_preparation_phase::equipment_root);
    assert(upgrade_flow.cancel());
    assert(upgrade_flow.snapshot().phase ==
           battle_preparation_phase::root);

    battle_campaign_state empty_campaign =
            campaign_fixture();
    empty_campaign.characters[1].equipped_tools = {};
    empty_campaign.inventory.ninja_tools = {};
    battle_preparation_flow empty_flow;
    assert(empty_flow.load(empty_campaign, 1));
    assert(empty_flow.confirm());
    assert(empty_flow.confirm());
    state = empty_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::feedback);
    assert(state.last_operation ==
           battle_preparation_operation::equip);
    assert(state.last_equipment_error ==
           battle_campaign_equipment_error::
                   no_available_copy);
    assert(! state.last_equipment_succeeded);
    assert(empty_flow.cancel());
    assert(empty_flow.snapshot().phase ==
           battle_preparation_phase::equipment_root);

    assert(empty_flow.move(1));
    assert(empty_flow.confirm());
    state = empty_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::feedback);
    assert(state.last_operation ==
           battle_preparation_operation::unequip);
    assert(state.last_equipment_error ==
           battle_campaign_equipment_error::empty_slot);
    assert(! state.last_equipment_succeeded);
    assert(empty_flow.cancel());
    assert(empty_flow.snapshot().phase ==
           battle_preparation_phase::equipment_root);

    assert(empty_flow.move(1));
    assert(empty_flow.confirm());
    state = empty_flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::feedback);
    assert(state.last_operation ==
           battle_preparation_operation::upgrade);
    assert(state.last_upgrade_error ==
           ninja_tool_upgrade_error::no_recipe);
    assert(! state.last_upgrade_succeeded);
    assert(empty_flow.cancel());
    assert(empty_flow.snapshot().phase ==
           battle_preparation_phase::equipment_root);
    assert(empty_flow.cancel());
    assert(empty_flow.snapshot().phase ==
           battle_preparation_phase::root);

    battle_preparation_flow invalid_flow;
    assert(! invalid_flow.load(empty_campaign, 0));
    assert(! invalid_flow.load(empty_campaign, 63));
    assert(! invalid_flow.load(empty_campaign, 2));
    battle_campaign_state inactive_party =
            party_campaign_fixture();
    assert(activate_battle_campaign_character(
            inactive_party,
            {
                3,
                1,
                0,
                0,
                true,
            }));
    assert(! invalid_flow.load(inactive_party, 3));
}
