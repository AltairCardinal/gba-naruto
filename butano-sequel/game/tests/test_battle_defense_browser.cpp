#include "konoha/battle_defense_browser.h"
#include "konoha/battle_turn_flow.h"
#include "konoha/generated_battle_unit_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_unit_instance sasuke = instantiate_unit(
            unit_definitions[2],
            1,
            battle_side::player,
            battle_control::player,
            { 1, 1 },
            battle_facing::right,
            14);
    sasuke.primary_action_levels[8] = 1;
    sasuke.equipped_tools[0] = 46;
    sasuke.equipped_tools[1] = 1;
    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::ai,
            { 2, 1 },
            battle_facing::left,
            1);

    battle_session<2> session;
    assert(session.add_unit(sasuke));
    assert(session.add_unit(enemy));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);
    assert(session.open_facing_selection() ==
           battle_transition::facing_selection_opened);
    assert(session.select_facing(battle_facing::right) ==
           battle_transition::defense_selection_opened);

    const battle_session<2> before = session;
    const battle_defense_browser_result browser =
            battle_defense_browser::build(session);
    assert(browser.error == battle_defense_browser_error::none);
    assert(browser.count == 6);
    assert(session == before);

    const battle_defense_browser_entry* offensive =
            browser.find(defense_action_kind::active_action, 2);
    assert(offensive);
    assert(offensive->confirmation_error ==
           defense_preparation_error::unsupported_category);

    const battle_defense_browser_entry* sharingan =
            browser.find(defense_action_kind::active_action, 15);
    assert(sharingan);
    assert(sharingan->confirmation_error ==
           defense_preparation_error::none);
    assert(sharingan->tool_slot == no_tool_slot);

    const battle_defense_browser_entry* fire_bomb =
            browser.find(defense_action_kind::ninja_tool, 46, 0);
    assert(fire_bomb);
    assert(fire_bomb->confirmation_error ==
           defense_preparation_error::none);
    assert(fire_bomb->action.cost.tool_slot == 0);

    const battle_defense_browser_entry* ordinary_tool =
            browser.find(defense_action_kind::ninja_tool, 1, 1);
    assert(ordinary_tool);
    assert(ordinary_tool->confirmation_error ==
           defense_preparation_error::unsupported_category);

    battle_condition_variant no_conditions;
    const battle_turn_flow_result completed =
            battle_turn_flow::complete_defense(
                    session,
                    sharingan->action,
                    no_conditions);
    assert(completed.error == battle_turn_flow_error::none);
    assert(session.unit(1)->chakra ==
           unit_definitions[2].chakra_capacity - 2);
    assert(session.unit(1)->statuses.find(0x10) !=
           no_status_slot);
}
