#include "konoha/battle_action_browser.h"
#include "konoha/battle_action_catalog.h"
#include "konoha/battle_defense_browser.h"
#include "konoha/generated_battle_unit_content.h"
#include "konoha/scenario_41_definition.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_unit_instance naruto = instantiate_unit(
            unit_definitions[1],
            1,
            battle_side::player,
            battle_control::player,
            { 4, 17 },
            battle_facing::up,
            1);
    naruto.equipped_tools[2] = 1;

    const battle_action_catalog_result catalog =
            battle_action_catalog::build(naruto);
    assert(catalog.error == battle_action_catalog_error::none);
    assert(catalog.count == 4);
    assert(catalog.entries[0].kind ==
           battle_action_source_kind::active_action);
    assert(catalog.entries[0].action_id == 2);
    assert(catalog.entries[0].action_level == 1);
    assert(catalog.entries[1].action_id == 7);
    assert(catalog.entries[1].action_level == 1);
    assert(catalog.entries[2].action_id == 5);
    assert(catalog.entries[2].action_level == 1);
    assert(catalog.entries[3].kind ==
           battle_action_source_kind::ninja_tool);
    assert(catalog.entries[3].action_id == 1);
    assert(catalog.entries[3].action_level == 0);
    assert(catalog.entries[3].tool_slot == 2);
    assert(catalog.entries[3].action.cost.tool_slot == 2);
    const battle_action_catalog_entry* combo =
            catalog.find(
                    battle_action_source_kind::active_action,
                    5);
    assert(combo);
    assert(combo->action.effect.potency == 10);
    assert(scenario_41_tutorial_action(naruto).id == 5);

    battle_unit_instance full_catalog = instantiate_unit(
            unit_definitions[2],
            3,
            battle_side::player,
            battle_control::player,
            { 2, 2 },
            battle_facing::up,
            50);
    for(std::size_t slot = 0;
            slot < full_catalog.primary_action_levels.size();
            ++slot)
    {
        if(unit_definitions[2].primary_slots[slot].action !=
                no_ability)
        {
            full_catalog.primary_action_levels[slot] = 1;
        }
    }
    full_catalog.equipped_tools =
            std::array<ninja_tool_id, 9>{
                1, 1, 1, 1, 1, 1, 1, 1, 1
            };
    const battle_action_catalog_result complete_catalog =
            battle_action_catalog::build(full_catalog);
    assert(complete_catalog.error ==
           battle_action_catalog_error::none);
    assert(complete_catalog.count == 20);
    assert(complete_catalog.entries[19].kind ==
           battle_action_source_kind::ninja_tool);
    assert(complete_catalog.entries[19].tool_slot == 8);

    battle_unit_instance invalid_character = naruto;
    invalid_character.character_id = 63;
    assert(battle_action_catalog::build(invalid_character).error ==
           battle_action_catalog_error::invalid_character);

    battle_unit_instance invalid_tool = naruto;
    invalid_tool.equipped_tools[2] =
            static_cast<ninja_tool_id>(
                    ninja_tool_action_definitions.size());
    assert(battle_action_catalog::build(invalid_tool).error ==
           battle_action_catalog_error::invalid_action_reference);

    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::ai,
            { 4, 10 },
            battle_facing::down,
            1);
    battle_session<2> session;
    assert(session.add_unit(naruto));
    assert(session.add_unit(enemy));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);

    const battle_session<2> before = session;
    const battle_action_browser_result browser =
            battle_action_browser::build(session);
    assert(browser.error == battle_action_browser_error::none);
    assert(browser.count == 4);
    assert(browser.entries[0].selectable());
    assert(browser.entries[2].selectable());
    assert(browser.entries[3].selectable());
    assert(session == before);

    battle_unit_instance exhausted_naruto = naruto;
    exhausted_naruto.chakra = 0;
    battle_session<2> exhausted_session;
    assert(exhausted_session.add_unit(exhausted_naruto));
    assert(exhausted_session.add_unit(enemy));
    assert(exhausted_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(exhausted_session.select_unit(1) ==
           battle_transition::action_draft_opened);
    const battle_action_browser_result exhausted =
            battle_action_browser::build(exhausted_session);
    assert(exhausted.entries[0].selection_error ==
           action_error::insufficient_chakra);
    assert(exhausted.entries[1].selection_error ==
           action_error::insufficient_chakra);
    assert(exhausted.entries[2].selectable());

    assert(session.open_facing_selection() ==
           battle_transition::facing_selection_opened);
    assert(session.select_facing(battle_facing::up) ==
           battle_transition::defense_selection_opened);
    const battle_defense_browser_result defense =
            battle_defense_browser::build(session);
    assert(defense.error == battle_defense_browser_error::none);
    assert(defense.count == catalog.count);
    assert(defense.entries[0].action_id ==
           catalog.entries[0].action_id);
    assert(defense.entries[3].tool_slot ==
           catalog.entries[3].tool_slot);
}
