#include "konoha/scenario_41_battle.h"
#include "scenario_41_test_support.h"

#include <cassert>

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
    for(int index = 0; index < 3; ++index)
    {
        assert(battle.dispatch({ command_kind::move_cursor, 0, -1 }) ==
               battle_event::cursor_moved);
    }
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::move_previewed);
    assert(battle.dispatch({ command_kind::move_cursor, 0, 1 }) == battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::end_confirmation_opened);
    assert(battle.dispatch({ command_kind::move_cursor, 0, -1 }) == battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::facing_opened);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::defense_opened);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::waited);

    assert(battle.snapshot().naruto.hp == 80);
    assert(battle.dispatch({ command_kind::tick }) == battle_event::tutorial_opened);
    assert((battle.snapshot().konoha_maru.position == grid_point{ 4, 6 }));
    assert(battle.snapshot().naruto.hp == 75);
}
