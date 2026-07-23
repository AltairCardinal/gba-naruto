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
    assert(battle.dispatch(move(0, 1)) == battle_event::cursor_moved);
    assert(battle.dispatch(move(0, 1)) == battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) ==
           battle_event::prebattle_confirmation_opened);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::intro_opened);
    complete_scenario_41_entrance(battle);
    return battle;
}

void finish_turn(scenario_41_battle& battle, int dx, int dy, int steps)
{
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::unit_selected);
    for(int step = 0; step < steps; ++step)
    {
        assert(battle.dispatch(move(dx, dy)) == battle_event::cursor_moved);
    }
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::move_previewed);
    assert(battle.dispatch(move(0, 1)) == battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::end_confirmation_opened);
    assert(battle.dispatch(move(0, -1)) == battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::facing_opened);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::defense_opened);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::waited);
    assert(battle.snapshot().phase == battle_phase::enemy_turn);
}

int distance(grid_point first, grid_point second)
{
    const int dx = first.x > second.x ? first.x - second.x : second.x - first.x;
    const int dy = first.y > second.y ? first.y - second.y : second.y - first.y;
    return dx + dy;
}

}

int main()
{
    scenario_41_battle upward = ready_battle();
    scenario_41_battle rightward = ready_battle();
    finish_turn(upward, 0, -1, 1);
    finish_turn(rightward, 1, 0, 3);

    const grid_point enemy_origin = upward.snapshot().konoha_maru.position;
    assert(enemy_origin == rightward.snapshot().konoha_maru.position);
    assert(upward.dispatch({ command_kind::tick }) == battle_event::tutorial_opened);
    assert(rightward.dispatch({ command_kind::tick }) == battle_event::tutorial_opened);

    const grid_point upward_destination = upward.snapshot().konoha_maru.position;
    const grid_point rightward_destination = rightward.snapshot().konoha_maru.position;
    assert(distance(enemy_origin, upward_destination) <= 2);
    assert(distance(enemy_origin, rightward_destination) <= 2);
    assert(upward_destination != rightward_destination);
}
