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
    scenario_41_battle early;
    early.dispatch(move(0, 1));
    early.dispatch(move(0, 1));
    early.dispatch({ command_kind::confirm });
    early.dispatch({ command_kind::confirm });
    complete_scenario_41_entrance(early);
    early.dispatch({ command_kind::confirm });
    early.dispatch(move(0, -1));
    early.dispatch({ command_kind::confirm });
    assert(early.dispatch({ command_kind::confirm }) == battle_event::technique_menu_opened);
    assert(early.dispatch({ command_kind::confirm }) == battle_event::technique_selected);
    early.dispatch(move(0, -1));
    const battle_snapshot before = early.snapshot();
    assert(early.dispatch({ command_kind::confirm }) == battle_event::invalid);
    assert(early.snapshot() == before);

    battle_snapshot rewards = before;
    rewards.phase = battle_phase::result;
    assert(rewards.mission_exp == 100);
    assert(rewards.battle_exp == 50);
    assert(rewards.bonus_exp == 0);
    assert(rewards.total_exp == 150);
    assert(rewards.hp_growth == 14);
}
