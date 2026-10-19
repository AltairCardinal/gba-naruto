#ifndef KONOHA_BATTLE_MAP_VISUAL_PROJECTION_H
#define KONOHA_BATTLE_MAP_VISUAL_PROJECTION_H

#include "konoha/battle_scene_controller.h"

namespace konoha
{

[[nodiscard]] constexpr int battle_map_unit_z_order(
        grid_point visual_position)
{
    // Butano draws higher z orders first, so a lower value is visually
    // in front. Units farther down the map must therefore use a lower
    // z order than units above them.
    return -visual_position.y;
}

template<std::size_t MaxUnits>
[[nodiscard]] constexpr grid_point battle_map_visual_position(
        const battle_scene_snapshot<MaxUnits>& state,
        const battle_scene_unit_view& unit)
{
    if(unit.id != state.selected_unit)
    {
        return unit.position;
    }

    switch(state.phase)
    {
    case battle_scene_phase::move_selection:
        return unit.position;
    case battle_scene_phase::command_selection:
    case battle_scene_phase::chakra_selection:
    case battle_scene_phase::rest_confirmation:
    case battle_scene_phase::end_confirmation:
    case battle_scene_phase::action_selection:
    case battle_scene_phase::combination_decision:
    case battle_scene_phase::target_selection:
    case battle_scene_phase::target_preview:
    case battle_scene_phase::target_confirmation:
    case battle_scene_phase::facing_selection:
    case battle_scene_phase::defense_decision:
    case battle_scene_phase::defense_selection:
        return state.player.move_position;
    default:
        return unit.position;
    }
}

template<std::size_t MaxUnits>
[[nodiscard]] constexpr battle_facing battle_map_visual_facing(
        const battle_scene_snapshot<MaxUnits>& state,
        const battle_scene_unit_view& unit)
{
    if(unit.id != state.selected_unit)
    {
        return unit.facing;
    }
    switch(state.phase)
    {
    case battle_scene_phase::move_selection:
    case battle_scene_phase::command_selection:
    case battle_scene_phase::chakra_selection:
    case battle_scene_phase::rest_confirmation:
    case battle_scene_phase::end_confirmation:
    case battle_scene_phase::action_selection:
    case battle_scene_phase::combination_decision:
    case battle_scene_phase::target_selection:
    case battle_scene_phase::target_preview:
    case battle_scene_phase::target_confirmation:
    case battle_scene_phase::facing_selection:
    case battle_scene_phase::defense_decision:
    case battle_scene_phase::defense_selection:
        return state.selected_facing;
    default:
        return unit.facing;
    }
}

template<std::size_t MaxUnits>
[[nodiscard]] constexpr battle_facing battle_map_cursor_facing(
        const battle_scene_snapshot<MaxUnits>& state)
{
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        const battle_scene_unit_view& unit =
                state.units[index];
        if(unit.id == state.selected_unit &&
                state.cursor ==
                        battle_map_visual_position(
                                state, unit))
        {
            return battle_map_visual_facing(
                    state, unit);
        }
    }
    return battle_facing::up;
}

}

#endif
