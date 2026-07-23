#include "konoha/scenario_41_battle.h"
#include "scenario_41_test_support.h"

#include <cassert>

int main()
{
    konoha::scenario_41_battle battle;
    const konoha::battle_snapshot initial = battle.snapshot();
    assert(initial.phase == konoha::battle_phase::prebattle_menu);
    assert(initial.menu_index == 0);
    assert(initial.turn == 1);
    assert((initial.cursor == konoha::grid_point{ 4, 10 }));
    assert((initial.naruto.position == konoha::grid_point{ 4, 10 }));
    assert((initial.konoha_maru.position == konoha::grid_point{ 4, 4 }));
    assert(initial.konoha_maru.id == konoha::unit_id::konoha_maru);
    assert(initial.naruto.hp == 80 && initial.naruto.max_hp == 80);
    assert(initial.konoha_maru.hp == 10 && initial.konoha_maru.max_hp == 10);
    assert(initial.naruto.move_range == 3);
    assert(initial.konoha_maru.active);
    assert(! initial.victory);

    assert(battle.dispatch({ konoha::command_kind::move_cursor, 0, 1 }) ==
           konoha::battle_event::cursor_moved);
    assert(battle.dispatch({ konoha::command_kind::move_cursor, 0, 1 }) ==
           konoha::battle_event::cursor_moved);
    assert(battle.dispatch({ konoha::command_kind::confirm }) ==
           konoha::battle_event::prebattle_confirmation_opened);
    assert(battle.dispatch({ konoha::command_kind::confirm }) ==
           konoha::battle_event::intro_opened);
    complete_scenario_41_entrance(battle);
    const konoha::grid_point selected_before_cycle = battle.snapshot().cursor;
    assert(battle.dispatch({ konoha::command_kind::cycle_next_unit }) ==
           konoha::battle_event::cursor_moved);
    assert(battle.snapshot().cursor == selected_before_cycle);

    konoha::scenario_41_battle ignored_input;
    assert(ignored_input.dispatch({ konoha::command_kind::cancel }) ==
           konoha::battle_event::invalid);
    assert(ignored_input.snapshot() == initial);
}
