#ifndef KONOHA_BATTLE_AUDIO_DIRECTOR_H
#define KONOHA_BATTLE_AUDIO_DIRECTOR_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_audio_event : std::uint8_t
{
    preparation_opened,
    battle_opened,
    ui_confirmed,
    ui_cancelled,
    ui_navigated,
    input_rejected,
    action_confirmed,
    technique_title,
    action_movie,
    impact,
    combat_popup,
    victory_shown,
    result_shown,
    level_up_shown,
    postbattle_dialogue_opened,
    postbattle_opened,
};

enum class battle_audio_command_kind : std::uint8_t
{
    play_music,
    play_sound,
};

struct battle_audio_command
{
    battle_audio_command_kind kind =
            battle_audio_command_kind::play_sound;
    int cue = 0;

    constexpr bool operator==(
            const battle_audio_command&) const = default;
};

struct battle_audio_command_batch
{
    std::array<battle_audio_command, 2> commands = {};
    std::size_t count = 0;
};

class battle_audio_director
{
public:
    [[nodiscard]] constexpr battle_audio_command_batch dispatch(
            battle_audio_event event,
            bool special_combination = false) const
    {
        using kind = battle_audio_command_kind;
        switch(event)
        {
        case battle_audio_event::preparation_opened:
            return _single(kind::play_music, 5);
        case battle_audio_event::battle_opened:
            return _pair(
                    { kind::play_music, 14 },
                    { kind::play_sound, 126 });
        case battle_audio_event::ui_confirmed:
            return _single(kind::play_sound, 102);
        case battle_audio_event::ui_cancelled:
            return _single(kind::play_sound, 103);
        case battle_audio_event::ui_navigated:
            return _single(kind::play_sound, 104);
        case battle_audio_event::input_rejected:
            return _single(kind::play_sound, 105);
        case battle_audio_event::action_confirmed:
            return _single(kind::play_sound, 117);
        case battle_audio_event::technique_title:
            return special_combination ?
                    _single(kind::play_music, 15) :
                    battle_audio_command_batch{};
        case battle_audio_event::action_movie:
            return _single(kind::play_sound, 116);
        case battle_audio_event::impact:
            return _single(kind::play_sound, 138);
        case battle_audio_event::combat_popup:
            return special_combination ?
                    _pair(
                            { kind::play_music, 14 },
                            { kind::play_sound, 149 }) :
                    _single(kind::play_sound, 149);
        case battle_audio_event::victory_shown:
            return _single(kind::play_sound, 158);
        case battle_audio_event::result_shown:
            return _pair(
                    { kind::play_sound, 157 },
                    { kind::play_sound, 112 });
        case battle_audio_event::level_up_shown:
            return {};
        case battle_audio_event::
                postbattle_dialogue_opened:
            return _single(kind::play_music, 8);
        case battle_audio_event::postbattle_opened:
            return _single(kind::play_music, 2);
        }
        return {};
    }

private:
    [[nodiscard]] static constexpr
    battle_audio_command_batch _single(
            battle_audio_command_kind kind,
            int cue)
    {
        return {
            {{
                { kind, cue },
                {},
            }},
            1,
        };
    }

    [[nodiscard]] static constexpr
    battle_audio_command_batch _pair(
            battle_audio_command first,
            battle_audio_command second)
    {
        return {
            {{ first, second }},
            2,
        };
    }
};

}

#endif
