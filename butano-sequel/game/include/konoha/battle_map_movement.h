#ifndef KONOHA_BATTLE_MAP_MOVEMENT_H
#define KONOHA_BATTLE_MAP_MOVEMENT_H

#include "konoha/battle_map_visual_projection.h"
#include "konoha/battle_unit_visual_animation.h"

namespace konoha
{

struct battle_map_movement_sample
{
    bool moving = false;
    int offset_x = 0;
    int offset_y = 0;
    std::uint8_t sequence = 0;
    int elapsed_frames = 0;
};

// Presentation of a confirmed move. Tile selection only
// changes the cursor and facing. This never writes the unit or draft.
// S49's player slot-0 timelines use 12 departure and 14 arrival frames.
class battle_map_movement
{
public:
    static constexpr int departure_frames = 12;
    static constexpr int arrival_frames = 14;

    template<std::size_t MaxUnits>
    void observe(const battle_scene_snapshot<MaxUnits>& state)
    {
        if(state.phase != battle_scene_phase::move_selection &&
                state.phase != battle_scene_phase::command_selection)
        {
            _tracking = false;
            _active = false;
            return;
        }
        const battle_scene_unit_view* actor = nullptr;
        for(std::size_t index = 0; index < state.unit_count; ++index)
        {
            if(state.units[index].id == state.selected_unit)
            {
                actor = &state.units[index];
                break;
            }
        }
        if(! actor)
        {
            _tracking = false;
            _active = false;
            return;
        }
        const grid_point destination = battle_map_visual_position(state, *actor);
        if(! _tracking || _actor != state.selected_unit)
        {
            _actor = state.selected_unit;
            _destination = destination;
            _tracking = true;
            _active = false;
            _previous_phase = state.phase;
            return;
        }
        if(destination != _destination)
        {
            _origin = _destination;
            _destination = destination;
            _facing = battle_unit_visual_animation::facing_toward(
                    _origin, _destination, state.selected_facing);
            _frame = 0;
            _active = _previous_phase == battle_scene_phase::move_selection &&
                    state.phase == battle_scene_phase::command_selection;
        }
        _previous_phase = state.phase;
    }

    [[nodiscard]] bool busy() const { return _active; }

    void advance()
    {
        if(_active && ++_frame >= departure_frames + arrival_frames)
        {
            _active = false;
        }
    }

    [[nodiscard]] battle_map_movement_sample sample(battle_unit_id actor) const
    {
        if(! _active || actor != _actor)
        {
            return {};
        }
        battle_map_movement_sample result;
        result.moving = true;
        if(_frame < departure_frames)
        {
            result.sequence = battle_unit_visual_animation::departure_sequence(_facing);
            result.elapsed_frames = _frame;
            // Original departure frames already contain the displacement.
            // Anchor at the old cell instead of adding a second interpolation.
            result.offset_x = (_origin.x - _destination.x) * 32;
            result.offset_y = (_origin.y - _destination.y) * 16;
        }
        else
        {
            result.sequence = battle_unit_visual_animation::arrival_sequence(_facing);
            result.elapsed_frames = _frame - departure_frames;
        }
        return result;
    }

private:
    battle_unit_id _actor = no_battle_unit;
    grid_point _origin = {};
    grid_point _destination = {};
    battle_facing _facing = battle_facing::up;
    battle_scene_phase _previous_phase = battle_scene_phase::preparation;
    int _frame = 0;
    bool _tracking = false;
    bool _active = false;
};

}
#endif
