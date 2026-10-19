#include "konoha/battle_audio_director.h"

#include <cassert>

using namespace konoha;

namespace
{

void assert_single(
        const battle_audio_command_batch& batch,
        battle_audio_command_kind kind,
        int cue)
{
    assert(batch.count == 1);
    assert(batch.commands[0].kind == kind);
    assert(batch.commands[0].cue == cue);
}

}

int main()
{
    battle_audio_director director;

    assert_single(
            director.dispatch(
                    battle_audio_event::preparation_opened),
            battle_audio_command_kind::play_music,
            5);

    const battle_audio_command_batch battle =
            director.dispatch(
                    battle_audio_event::battle_opened);
    assert(battle.count == 2);
    assert(battle.commands[0] ==
           battle_audio_command({
                   battle_audio_command_kind::play_music,
                   14,
           }));
    assert(battle.commands[1] ==
           battle_audio_command({
                   battle_audio_command_kind::play_sound,
                   126,
           }));

    assert_single(
            director.dispatch(
                    battle_audio_event::ui_confirmed),
            battle_audio_command_kind::play_sound,
            102);
    assert_single(
            director.dispatch(
                    battle_audio_event::ui_cancelled),
            battle_audio_command_kind::play_sound,
            103);
    assert_single(
            director.dispatch(
                    battle_audio_event::ui_navigated),
            battle_audio_command_kind::play_sound,
            104);
    assert_single(
            director.dispatch(
                    battle_audio_event::input_rejected),
            battle_audio_command_kind::play_sound,
            105);
    assert_single(
            director.dispatch(
                    battle_audio_event::action_confirmed),
            battle_audio_command_kind::play_sound,
            117);

    assert(director.dispatch(
                    battle_audio_event::technique_title,
                    false).count == 0);
    assert_single(
            director.dispatch(
                    battle_audio_event::technique_title,
                    true),
            battle_audio_command_kind::play_music,
            15);
    assert_single(
            director.dispatch(
                    battle_audio_event::action_movie),
            battle_audio_command_kind::play_sound,
            116);
    assert_single(
            director.dispatch(
                    battle_audio_event::impact),
            battle_audio_command_kind::play_sound,
            138);

    const battle_audio_command_batch popup =
            director.dispatch(
                    battle_audio_event::combat_popup);
    assert_single(
            popup,
            battle_audio_command_kind::play_sound,
            149);
    const battle_audio_command_batch
            special_combination_popup =
                    director.dispatch(
                            battle_audio_event::
                                    combat_popup,
                            true);
    assert(special_combination_popup.count == 2);
    assert(special_combination_popup.commands[0] ==
           battle_audio_command({
                   battle_audio_command_kind::play_music,
                   14,
           }));
    assert(special_combination_popup.commands[1] ==
           battle_audio_command({
                   battle_audio_command_kind::play_sound,
                   149,
           }));

    const battle_audio_command_batch victory =
            director.dispatch(
                    battle_audio_event::victory_shown);
    assert(victory.count == 1);
    assert(victory.commands[0] ==
           battle_audio_command({
                   battle_audio_command_kind::play_sound,
                   158,
           }));

    const battle_audio_command_batch result =
            director.dispatch(
                    battle_audio_event::result_shown);
    assert(result.count == 2);
    assert(result.commands[0].cue == 157);
    assert(result.commands[1].cue == 112);

    assert(director.dispatch(
                   battle_audio_event::level_up_shown)
                   .count == 0);
    assert_single(
            director.dispatch(
                    battle_audio_event::
                            postbattle_dialogue_opened),
            battle_audio_command_kind::play_music,
            8);
    assert_single(
            director.dispatch(
                    battle_audio_event::postbattle_opened),
            battle_audio_command_kind::play_music,
            2);
}
