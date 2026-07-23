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

scenario_41_battle ready_battle()
{
    scenario_41_battle battle;
    assert(battle.dispatch({ command_kind::move_cursor, 0, 1 }) ==
           battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::move_cursor, 0, 1 }) ==
           battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) ==
           battle_event::prebattle_confirmation_opened);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::intro_opened);
    complete_scenario_41_entrance(battle);
    return battle;
}

}

int main()
{
    scenario_41_battle bounded = ready_battle();
    for(int index = 0; index < 8; ++index)
    {
        bounded.dispatch(move(-1, 0));
    }
    assert((bounded.snapshot().cursor == grid_point{ 0, 10 }));
    const battle_snapshot at_left_edge = bounded.snapshot();
    assert(bounded.dispatch(move(-1, 0)) == battle_event::invalid);
    assert(bounded.snapshot() == at_left_edge);

    scenario_41_battle selection = ready_battle();
    assert(selection.dispatch(move(1, 0)) == battle_event::cursor_moved);
    assert(selection.dispatch({ command_kind::confirm }) == battle_event::invalid);
    assert(selection.dispatch(move(-1, 0)) == battle_event::cursor_moved);
    assert(selection.dispatch({ command_kind::confirm }) == battle_event::unit_selected);
    assert(selection.snapshot().phase == battle_phase::move_select);
    assert(selection.reachable({ 4, 7 }));
    assert(! selection.reachable({ 4, 6 }));
    assert(! selection.reachable({ 3, 9 }));
    assert(! selection.reachable(selection.snapshot().konoha_maru.position));

    const reachable_grid_points reachable = selection.reachable_points();
    assert(reachable.count <= 24);
    bool contains_three_steps_up = false;
    bool contains_blocked_tile = false;
    for(std::size_t index = 0; index < reachable.count; ++index)
    {
        const grid_point point = reachable.points[index];
        assert(selection.reachable(point));
        const int dx = point.x > 4 ? point.x - 4 : 4 - point.x;
        const int dy = point.y > 10 ? point.y - 10 : 10 - point.y;
        assert(dx + dy <= 3);
        contains_three_steps_up = contains_three_steps_up || point == grid_point{ 4, 7 };
        contains_blocked_tile = contains_blocked_tile || point == grid_point{ 3, 9 };
    }
    assert(contains_three_steps_up);
    assert(! contains_blocked_tile);

    assert(selection.dispatch(move(0, -1)) == battle_event::cursor_moved);
    assert(selection.dispatch(move(0, -1)) == battle_event::cursor_moved);
    assert(selection.dispatch(move(0, -1)) == battle_event::cursor_moved);
    assert(selection.dispatch({ command_kind::confirm }) == battle_event::move_previewed);
    battle_snapshot preview = selection.snapshot();
    assert(preview.phase == battle_phase::action_menu);
    assert((preview.preview_player_position == grid_point{ 4, 7 }));
    assert((preview.naruto.position == grid_point{ 4, 10 }));
    assert((preview.committed_player_position == grid_point{ 4, 10 }));

    assert(selection.dispatch({ command_kind::confirm }) == battle_event::technique_menu_opened);
    assert(selection.snapshot().phase == battle_phase::technique_menu);
    assert(selection.dispatch({ command_kind::confirm }) == battle_event::technique_selected);
    assert(selection.snapshot().phase == battle_phase::target_select);
    assert(selection.dispatch({ command_kind::cancel }) == battle_event::none);
    assert(selection.snapshot().phase == battle_phase::technique_menu);
    assert(selection.dispatch({ command_kind::cancel }) == battle_event::none);
    assert(selection.snapshot().phase == battle_phase::action_menu);
    assert(selection.dispatch({ command_kind::cancel }) == battle_event::none);
    assert(selection.snapshot().phase == battle_phase::move_select);
    assert((selection.snapshot().preview_player_position == grid_point{ 4, 10 }));
    assert(selection.dispatch({ command_kind::cancel }) == battle_event::none);
    assert(selection.snapshot().phase == battle_phase::unit_select);
    assert((selection.snapshot().cursor == grid_point{ 4, 10 }));
    assert((selection.snapshot().naruto.position == grid_point{ 4, 10 }));
    assert(selection.snapshot().turn == 1);
    assert(! selection.snapshot().victory);

    scenario_41_battle obstacle = ready_battle();
    assert(obstacle.dispatch({ command_kind::confirm }) == battle_event::unit_selected);
    obstacle.dispatch(move(-1, 0));
    obstacle.dispatch(move(0, -1));
    const battle_snapshot before_obstacle = obstacle.snapshot();
    assert(obstacle.dispatch({ command_kind::confirm }) == battle_event::invalid);
    assert(obstacle.snapshot() == before_obstacle);
}
