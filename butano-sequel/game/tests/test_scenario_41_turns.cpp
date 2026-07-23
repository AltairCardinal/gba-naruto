#include "konoha/scenario_41_battle.h"
#include "scenario_41_test_support.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_command move(int dx, int dy)
{
    return { command_kind::move_cursor, dx, dy };
}

}

int main()
{
    scenario_41_battle battle;
    assert(battle.dispatch(move(0, 1)) == battle_event::cursor_moved);
    assert(battle.dispatch(move(0, 1)) == battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) ==
           battle_event::prebattle_confirmation_opened);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::intro_opened);
    complete_scenario_41_entrance(battle);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::unit_selected);
    assert(battle.dispatch(move(0, -1)) == battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::move_previewed);
    assert(battle.dispatch(move(0, 1)) == battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::end_confirmation_opened);
    assert(battle.dispatch(move(0, -1)) == battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::facing_opened);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::defense_opened);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::waited);
    assert((battle.snapshot().naruto.position == grid_point{ 4, 9 }));
    assert(battle.dispatch({ command_kind::tick }) == battle_event::tutorial_opened);
    assert(battle.snapshot().turn == 2);
    assert((battle.snapshot().konoha_maru.position == grid_point{ 4, 6 }));

    scenario_41_battle no_quick_wait;
    no_quick_wait.dispatch({ command_kind::confirm });
    const battle_snapshot before = no_quick_wait.snapshot();
    assert(no_quick_wait.dispatch({ command_kind::wait }) == battle_event::invalid);
    assert(no_quick_wait.snapshot() == before);
}
