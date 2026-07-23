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

void select_and_move(scenario_41_battle& battle, int up_count, int right_count)
{
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::unit_selected);
    for(int index = 0; index < up_count; ++index)
    {
        assert(battle.dispatch(move(0, -1)) == battle_event::cursor_moved);
    }
    for(int index = 0; index < right_count; ++index)
    {
        assert(battle.dispatch(move(1, 0)) == battle_event::cursor_moved);
    }
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::move_previewed);
    assert(battle.snapshot().phase == battle_phase::action_menu);
}

void finish_without_attack(scenario_41_battle& battle)
{
    assert(battle.dispatch(move(0, 1)) == battle_event::cursor_moved);
    assert(battle.snapshot().menu_index == 1);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::end_confirmation_opened);
    assert(battle.snapshot().phase == battle_phase::end_confirmation);
    assert(battle.dispatch(move(0, -1)) == battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::facing_opened);
    assert(battle.snapshot().phase == battle_phase::facing_select);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::defense_opened);
    assert(battle.snapshot().phase == battle_phase::defense_confirmation);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::waited);
    assert(battle.snapshot().phase == battle_phase::enemy_turn);
}

int distance(grid_point first, grid_point second)
{
    const int dx = first.x > second.x ? first.x - second.x : second.x - first.x;
    const int dy = first.y > second.y ? first.y - second.y : second.y - first.y;
    return dx + dy;
}

void select_attack_position(scenario_41_battle& battle)
{
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::unit_selected);
    const battle_snapshot state = battle.snapshot();
    grid_point destination = state.naruto.position;
    if(distance(destination, state.konoha_maru.position) != 1)
    {
        const reachable_grid_points points = battle.reachable_points();
        bool found = false;
        for(std::size_t index = 0; index < points.count; ++index)
        {
            if(distance(points.points[index], state.konoha_maru.position) == 1)
            {
                destination = points.points[index];
                found = true;
                break;
            }
        }
        assert(found);
    }
    while(battle.snapshot().cursor.x != destination.x)
    {
        const int dx = battle.snapshot().cursor.x < destination.x ? 1 : -1;
        assert(battle.dispatch(move(dx, 0)) == battle_event::cursor_moved);
    }
    while(battle.snapshot().cursor.y != destination.y)
    {
        const int dy = battle.snapshot().cursor.y < destination.y ? 1 : -1;
        assert(battle.dispatch(move(0, dy)) == battle_event::cursor_moved);
    }
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::move_previewed);
}

}

int main()
{
    scenario_41_battle battle;
    assert(battle.snapshot().phase == battle_phase::prebattle_menu);
    assert(battle.snapshot().menu_index == 0);
    assert(battle.snapshot().konoha_maru.id == unit_id::konoha_maru);
    assert((battle.snapshot().konoha_maru.position == grid_point{ 4, 4 }));
    assert(battle.dispatch(move(0, 1)) == battle_event::cursor_moved);
    assert(battle.snapshot().menu_index == 1);
    assert(battle.dispatch(move(0, 1)) == battle_event::cursor_moved);
    assert(battle.snapshot().menu_index == 2);
    assert(battle.dispatch({ command_kind::confirm }) ==
           battle_event::prebattle_confirmation_opened);
    assert(battle.snapshot().phase == battle_phase::prebattle_confirmation);
    assert(battle.snapshot().confirmation_index == 0);
    assert(battle.dispatch({ command_kind::cancel }) == battle_event::prebattle_cancelled);
    assert(battle.snapshot().phase == battle_phase::prebattle_menu);
    assert(battle.snapshot().menu_index == 2);
    assert(battle.dispatch({ command_kind::confirm }) ==
           battle_event::prebattle_confirmation_opened);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::intro_opened);
    complete_scenario_41_entrance(battle);

    select_and_move(battle, 1, 0);
    finish_without_attack(battle);
    assert(battle.dispatch({ command_kind::tick }) == battle_event::tutorial_opened);
    assert(battle.snapshot().phase == battle_phase::tutorial_dialogue);
    for(int page = 0; page < 3; ++page)
    {
        assert(battle.dispatch({ command_kind::confirm }) == battle_event::dialogue_advanced);
        assert(battle.snapshot().phase == battle_phase::tutorial_dialogue);
    }
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::player_turn_started);
    assert(battle.snapshot().turn == 2);

    select_and_move(battle, 1, 0);
    finish_without_attack(battle);
    assert(battle.dispatch({ command_kind::tick }) == battle_event::player_turn_started);
    assert(battle.snapshot().turn == 3);

    select_and_move(battle, 2, 1);
    finish_without_attack(battle);
    assert(battle.dispatch({ command_kind::tick }) == battle_event::player_turn_started);
    assert(battle.snapshot().turn == 4);

    select_attack_position(battle);
    assert(distance(
                   battle.snapshot().preview_player_position,
                   battle.snapshot().konoha_maru.position) == 1);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::technique_menu_opened);
    assert(battle.snapshot().phase == battle_phase::technique_menu);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::technique_selected);
    assert(battle.snapshot().phase == battle_phase::target_select);
    const grid_point target = battle.snapshot().konoha_maru.position;
    while(battle.snapshot().cursor.x != target.x)
    {
        const int dx = battle.snapshot().cursor.x < target.x ? 1 : -1;
        assert(battle.dispatch(move(dx, 0)) == battle_event::cursor_moved);
    }
    while(battle.snapshot().cursor.y != target.y)
    {
        const int dy = battle.snapshot().cursor.y < target.y ? 1 : -1;
        assert(battle.dispatch(move(0, dy)) == battle_event::cursor_moved);
    }
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::attack_confirmation_opened);
    assert(battle.snapshot().phase == battle_phase::attack_confirmation);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::combat_animation_started);
    assert(battle.snapshot().phase == battle_phase::combat_animation);
    assert(! battle.snapshot().konoha_maru.active);
    assert(battle.snapshot().pending_outcome == battle_outcome::victory);
    for(int frame = 1; frame < 264; ++frame)
    {
        assert(battle.dispatch({ command_kind::tick }) == battle_event::combat_animation_advanced);
        assert(battle.snapshot().animation_frame == frame);
    }
    assert(battle.dispatch({ command_kind::tick }) == battle_event::combat_dialogue_opened);
    assert(battle.snapshot().phase == battle_phase::combat_dialogue);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::combat_popup_opened);
    assert(battle.snapshot().phase == battle_phase::combat_popup);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::victory_shown);
    assert(battle.snapshot().phase == battle_phase::victory);

    assert(battle.dispatch({ command_kind::confirm }) == battle_event::result_shown);
    assert(battle.snapshot().phase == battle_phase::result);
    assert(battle.snapshot().mission_exp == 100);
    assert(battle.snapshot().battle_exp == 50);
    assert(battle.snapshot().bonus_exp == 0);
    assert(battle.snapshot().total_exp == 150);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::level_up_shown);
    assert(battle.snapshot().phase == battle_phase::level_up);
    assert(battle.snapshot().naruto_level == 2);
    assert(battle.snapshot().hp_growth == 14);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::dialogue_advanced);
    assert(battle.snapshot().phase == battle_phase::level_up);
    assert(battle.snapshot().dialogue_page == 1);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::postbattle_dialogue_opened);
    assert(battle.snapshot().phase == battle_phase::postbattle_dialogue);
    for(int page = 0; page < 10; ++page)
    {
        assert(battle.dispatch({ command_kind::confirm }) == battle_event::dialogue_advanced);
    }
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::postbattle_opened);
    assert(battle.snapshot().phase == battle_phase::postbattle);
}
