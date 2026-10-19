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

}

int main()
{
    battle_campaign_state campaign = campaign_fixture();
    battle_preparation_flow flow;
    assert(flow.load(campaign, 1));

    battle_preparation_snapshot state = flow.snapshot();
    assert(state.phase == battle_preparation_phase::root);
    assert(state.root_option ==
           battle_preparation_root_option::party_equipment);

    assert(flow.confirm());
    state = flow.snapshot();
    assert(state.phase ==
           battle_preparation_phase::equipment_root);
    assert(state.equipment_option ==
           battle_preparation_equipment_option::equip);
    assert(flow.cancel());
    assert(flow.snapshot().phase ==
           battle_preparation_phase::root);

    assert(flow.move(1));
    assert(flow.snapshot().root_option ==
           battle_preparation_root_option::inspect_map);
    assert(flow.confirm());
    assert(flow.snapshot().phase ==
           battle_preparation_phase::map_preview);
    assert(flow.cancel());
    assert(flow.snapshot().phase ==
           battle_preparation_phase::root);

    assert(flow.move(1));
    assert(flow.snapshot().root_option ==
           battle_preparation_root_option::start_battle);
    assert(flow.confirm());
    assert(flow.snapshot().phase ==
           battle_preparation_phase::start_confirmation);
    assert(flow.snapshot().start_confirmation_yes);
    assert(flow.cancel());
    assert(flow.snapshot().phase ==
           battle_preparation_phase::root);

    assert(flow.move(1));
    assert(flow.snapshot().root_option ==
           battle_preparation_root_option::save);
    const battle_campaign_state before_save = campaign;
    assert(flow.confirm());
    assert(flow.snapshot().phase ==
           battle_preparation_phase::save_requested);
    assert(campaign == before_save);
}
