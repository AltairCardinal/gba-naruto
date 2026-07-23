#include "konoha/scenario_41_battle.h"

#include <cassert>

using namespace konoha;

namespace
{

void drain_automatic_step(scenario_41_battle& battle, presentation_cue expected)
{
    battle_snapshot state = battle.snapshot();
    assert(state.phase == battle_phase::intro);
    assert(state.presentation == expected);
    assert(state.presentation_mode_value == presentation_mode::automatic);
    assert(state.presentation_remaining_frames > 0);
    const int frames = state.presentation_remaining_frames;
    for(int frame = 0; frame < frames; ++frame)
    {
        const battle_event event = battle.dispatch({ command_kind::tick });
        if(frame + 1 < frames)
        {
            assert(event == battle_event::intro_advanced);
        }
    }
}

}

int main()
{
    scenario_41_battle battle;
    assert(battle.dispatch({ command_kind::move_cursor, 0, 1 }) ==
           battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::move_cursor, 0, 1 }) ==
           battle_event::cursor_moved);
    assert(battle.dispatch({ command_kind::confirm }) ==
           battle_event::prebattle_confirmation_opened);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::intro_opened);

    battle_snapshot state = battle.snapshot();
    assert(state.phase == battle_phase::intro);
    assert(state.presentation == presentation_cue::player_appearance);
    assert(state.presentation_mode_value == presentation_mode::automatic);
    assert(state.presentation_visible);
    const battle_snapshot before_early_a = state;
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::invalid);
    assert(battle.snapshot() == before_early_a);

    drain_automatic_step(battle, presentation_cue::player_appearance);
    drain_automatic_step(battle, presentation_cue::enemy_appearance);
    drain_automatic_step(battle, presentation_cue::start_title);

    state = battle.snapshot();
    assert(state.presentation == presentation_cue::black);
    assert(state.presentation_mode_value == presentation_mode::automatic);
    assert(! state.presentation_visible);
    const battle_snapshot before_black_a = state;
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::invalid);
    assert(battle.snapshot() == before_black_a);
    drain_automatic_step(battle, presentation_cue::black);

    state = battle.snapshot();
    assert(state.presentation == presentation_cue::entrance_dialogue);
    assert(state.presentation_mode_value == presentation_mode::wait_for_input);
    assert(state.presentation_visible);
    const battle_snapshot before_dialogue_tick = state;
    assert(battle.dispatch({ command_kind::tick }) == battle_event::invalid);
    assert(battle.snapshot() == before_dialogue_tick);
    assert(battle.dispatch({ command_kind::confirm }) == battle_event::intro_advanced);

    drain_automatic_step(battle, presentation_cue::shuriken_transition);
    assert(battle.snapshot().phase == battle_phase::unit_select);
    assert(battle.snapshot().presentation == presentation_cue::none);
    assert(battle.snapshot().last_event == battle_event::intro_dismissed);
}
