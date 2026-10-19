#ifndef KONOHA_BATTLE_AUDIO_RUNTIME_H
#define KONOHA_BATTLE_AUDIO_RUNTIME_H

#include "bn_assert.h"
#include "bn_music_items.h"

#include "konoha/battle_audio_director.h"

#include <cstddef>

namespace konoha
{

inline void play_battle_music(int cue)
{
    switch(cue)
    {
    case 2:
        bn::music_items::sound_002.play();
        break;
    case 5:
        bn::music_items::sound_005.play();
        break;
    case 8:
        bn::music_items::sound_008.play();
        break;
    case 14:
        bn::music_items::sound_014.play();
        break;
    case 15:
        bn::music_items::sound_015.play();
        break;
    default:
        BN_ERROR("Unknown battle music cue: ", cue);
        break;
    }
}

inline void play_battle_sound(int cue)
{
    // The imported WAV SFX currently corrupt Maxmod's mixer state
    // after repeated playback. Keep the semantic cue boundary here
    // so stable assets can be restored without touching battle flow.
    (void) cue;
}

inline void apply_battle_audio_commands(
        const battle_audio_command_batch& batch)
{
    for(std::size_t index = 0;
            index < batch.count; ++index)
    {
        const battle_audio_command& command =
                batch.commands[index];
        if(command.kind ==
                battle_audio_command_kind::play_music)
        {
            play_battle_music(command.cue);
        }
        else
        {
            play_battle_sound(command.cue);
        }
    }
}

inline void dispatch_battle_audio(
        const battle_audio_director& director,
        battle_audio_event event,
        bool special_combination = false)
{
    apply_battle_audio_commands(
            director.dispatch(
                    event, special_combination));
}

}

#endif
