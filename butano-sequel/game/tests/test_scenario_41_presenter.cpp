#include "konoha/scenario_41_presenter.h"
#include "scenario_41_test_support.h"

#include <cassert>
#include <string_view>

using namespace konoha;

int main()
{
    scenario_41_battle battle;
    assert(battle.dispatch({ command_kind::move_cursor, 0, 1 }) == battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::move_cursor, 0, 1 }) == battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) ==
           battle_event::prebattle_confirmation_opened);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::intro_opened);
    complete_scenario_41_entrance(battle);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::unit_selected);
    assert(battle.dispatch({ command_kind::move_cursor, 0, -1 }) == battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::move_previewed);

    const battle_presentation action_menu =
            present_scenario_41(battle.snapshot(), battle_event::none);
    assert(std::string_view(action_menu.line1) == "ACTION");
    assert(std::string_view(action_menu.line2) == "> TECHNIQUE");
    assert(std::string_view(action_menu.line3) == "  END ACTION");

    assert(battle.dispatch({ command_kind::confirm }) ==
           battle_event::technique_menu_opened);
    const battle_presentation technique =
            present_scenario_41(battle.snapshot(), battle_event::none);
    assert(std::string_view(technique.line1) == "TECHNIQUE");
    assert(std::string_view(technique.line2) == "> COMBO #5");
    assert(std::string_view(technique.line4) == "A:SELECT  B:BACK");
}
