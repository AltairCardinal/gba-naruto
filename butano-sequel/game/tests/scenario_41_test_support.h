#ifndef KONOHA_SCENARIO_41_TEST_SUPPORT_H
#define KONOHA_SCENARIO_41_TEST_SUPPORT_H

#include "konoha/scenario_41_battle.h"

#include <cassert>

inline void complete_scenario_41_entrance(konoha::scenario_41_battle& battle)
{
    while(battle.snapshot().phase == konoha::battle_phase::intro)
    {
        const konoha::battle_snapshot state = battle.snapshot();
        const konoha::command_kind command =
                state.presentation_mode_value == konoha::presentation_mode::automatic ?
                        konoha::command_kind::tick : konoha::command_kind::confirm;
        assert(battle.dispatch({ command }) != konoha::battle_event::invalid);
    }
    assert(battle.snapshot().phase == konoha::battle_phase::unit_select);
    assert(battle.snapshot().last_event == konoha::battle_event::intro_dismissed);
}

#endif
