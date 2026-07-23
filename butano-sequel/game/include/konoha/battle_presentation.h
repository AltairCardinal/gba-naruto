#ifndef KONOHA_BATTLE_PRESENTATION_H
#define KONOHA_BATTLE_PRESENTATION_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class presentation_cue : std::uint8_t
{
    none,
    player_appearance,
    enemy_appearance,
    start_title,
    black,
    entrance_dialogue,
    shuriken_transition,
};

enum class presentation_mode : std::uint8_t
{
    automatic,
    wait_for_input,
};

struct presentation_step
{
    presentation_cue cue = presentation_cue::none;
    presentation_mode mode = presentation_mode::automatic;
    int remaining_frames = 0;
    bool visible = false;

    constexpr bool operator==(const presentation_step&) const = default;
};

template<std::size_t Capacity>
class presentation_queue
{
    static_assert(Capacity > 0);

public:
    [[nodiscard]] bool push_automatic(presentation_cue cue, int duration_frames)
    {
        if(duration_frames <= 0 || _size == Capacity)
        {
            return false;
        }
        _push({
            cue,
            presentation_mode::automatic,
            duration_frames,
            cue != presentation_cue::black,
        });
        return true;
    }

    [[nodiscard]] bool push_wait_for_input(presentation_cue cue, bool visible)
    {
        if(! visible || _size == Capacity)
        {
            return false;
        }
        _push({ cue, presentation_mode::wait_for_input, 0, true });
        return true;
    }

    [[nodiscard]] bool tick()
    {
        presentation_step* step = _current();
        if(! step || step->mode != presentation_mode::automatic)
        {
            return false;
        }
        --step->remaining_frames;
        if(step->remaining_frames == 0)
        {
            _pop();
        }
        return true;
    }

    [[nodiscard]] bool confirm()
    {
        const presentation_step* step = current();
        if(! step || step->mode != presentation_mode::wait_for_input || ! step->visible)
        {
            return false;
        }
        _pop();
        return true;
    }

    [[nodiscard]] const presentation_step* current() const
    {
        return _size ? &_steps[_head] : nullptr;
    }

    [[nodiscard]] std::size_t size() const
    {
        return _size;
    }

    [[nodiscard]] bool empty() const
    {
        return _size == 0;
    }

private:
    void _push(presentation_step step)
    {
        const std::size_t index = (_head + _size) % Capacity;
        _steps[index] = step;
        ++_size;
    }

    void _pop()
    {
        _steps[_head] = {};
        _head = (_head + 1) % Capacity;
        --_size;
    }

    [[nodiscard]] presentation_step* _current()
    {
        return _size ? &_steps[_head] : nullptr;
    }

    std::array<presentation_step, Capacity> _steps = {};
    std::size_t _head = 0;
    std::size_t _size = 0;
};

}

#endif
