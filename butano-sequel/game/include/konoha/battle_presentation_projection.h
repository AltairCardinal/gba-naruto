#ifndef KONOHA_BATTLE_PRESENTATION_PROJECTION_H
#define KONOHA_BATTLE_PRESENTATION_PROJECTION_H

#include "konoha/battle_session.h"

namespace konoha
{

[[nodiscard]] constexpr int battle_clamp_camera(
        int value,
        int active_size,
        int viewport_size,
        int map_center = 256)
{
    const int minimum =
            -map_center + viewport_size / 2;
    const int maximum =
            -map_center + active_size -
            viewport_size / 2;
    if(maximum < minimum)
    {
        return (minimum + maximum) / 2;
    }
    if(value < minimum)
    {
        return minimum;
    }
    if(value > maximum)
    {
        return maximum;
    }
    return value;
}

[[nodiscard]] constexpr int battle_camera_focus_y(
        grid_point point,
        int map_pixel_height,
        int viewport_height)
{
    return battle_clamp_camera(
            point.y * 16 + 8 - 256,
            map_pixel_height,
            viewport_height);
}

[[nodiscard]] constexpr int battle_duel_screen_x(
        battle_side side)
{
    return side == battle_side::player ? -56 : 56;
}

[[nodiscard]] constexpr battle_facing battle_duel_facing(
        battle_side side)
{
    return side == battle_side::player ?
            battle_facing::right :
            battle_facing::left;
}

[[nodiscard]] constexpr int battle_facing_indicator_angle(
        battle_facing facing)
{
    switch(facing)
    {
    case battle_facing::right:
        return 270;
    case battle_facing::down:
        return 180;
    case battle_facing::left:
        return 90;
    case battle_facing::up:
    default:
        return 0;
    }
}

[[nodiscard]] constexpr int
battle_facing_indicator_pulse_phase(int scene_frame)
{
    const int frame = scene_frame % 16;
    if(frame < 4)
    {
        return 1;
    }
    if(frame < 11)
    {
        return 2;
    }
    return 0;
}

[[nodiscard]] constexpr int
battle_facing_indicator_graphics_index(
        battle_facing facing,
        int scene_frame)
{
    return static_cast<int>(facing) * 3 +
            battle_facing_indicator_pulse_phase(
                    scene_frame);
}

}

#endif
