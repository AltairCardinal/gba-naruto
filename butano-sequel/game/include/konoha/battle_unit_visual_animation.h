#ifndef KONOHA_BATTLE_UNIT_VISUAL_ANIMATION_H
#define KONOHA_BATTLE_UNIT_VISUAL_ANIMATION_H

#include "konoha/battle_session.h"

#include <cstdint>

namespace konoha
{

struct battle_unit_visual_timeline_step
{
    std::uint8_t frame_index = 0;
    std::uint8_t duration = 0;
};

enum class battle_unit_combat_motion : std::uint8_t
{
    cast = 1,
    throw_projectile = 2,
    melee = 3,
    hit = 4,
};

struct battle_unit_combat_visual
{
    std::uint8_t slot = 0;
    bool horizontal_flip = false;
};

class battle_unit_visual_animation
{
public:
    [[nodiscard]] static constexpr int idle_phase_offset(
            battle_unit_id unit_id)
    {
        // The original field tasks start alternating unit slots half an
        // idle cycle apart instead of making every actor bob in lockstep.
        // Unit IDs are one-based in the visible battle snapshot.
        return unit_id > 0 &&
                        ((unit_id - 1) & 1) ?
                16 :
                0;
    }

    [[nodiscard]] static constexpr battle_unit_combat_motion motion_for(
            bool ninja_tool,
            std::uint8_t animation_family,
            bool targets_opponent)
    {
        if(ninja_tool)
        {
            return battle_unit_combat_motion::throw_projectile;
        }
        if(animation_family == 1 && targets_opponent)
        {
            return battle_unit_combat_motion::melee;
        }
        return battle_unit_combat_motion::cast;
    }

    [[nodiscard]] static constexpr battle_facing facing_toward(
            grid_point origin,
            grid_point target,
            battle_facing fallback)
    {
        const int dx = target.x - origin.x;
        const int dy = target.y - origin.y;
        const int absolute_x = dx < 0 ? -dx : dx;
        const int absolute_y = dy < 0 ? -dy : dy;
        if(absolute_x == 0 && absolute_y == 0)
        {
            return fallback;
        }
        if(absolute_x >= absolute_y)
        {
            return dx < 0 ?
                    battle_facing::left :
                    battle_facing::right;
        }
        return dy < 0 ?
                battle_facing::up :
                battle_facing::down;
    }

    [[nodiscard]] static constexpr battle_unit_combat_visual combat(
            battle_unit_combat_motion motion,
            bool facing_left,
            bool explicit_left_slot_available)
    {
        const std::uint8_t base_slot =
                static_cast<std::uint8_t>(motion);
        if(! facing_left)
        {
            return { base_slot, false };
        }
        if(explicit_left_slot_available)
        {
            return {
                static_cast<std::uint8_t>(base_slot + 4),
                false,
            };
        }
        return { base_slot, true };
    }

    [[nodiscard]] static constexpr std::uint8_t idle_sequence(
            battle_facing facing)
    {
        switch(facing)
        {
        case battle_facing::down:
            return 0;
        case battle_facing::up:
            return 1;
        case battle_facing::right:
            return 2;
        case battle_facing::left:
            return 3;
        default:
            return 1;
        }
    }

    [[nodiscard]] static constexpr std::uint8_t departure_sequence(
            battle_facing facing)
    {
        return static_cast<std::uint8_t>(
                idle_sequence(facing) + 4);
    }

    [[nodiscard]] static constexpr std::uint8_t arrival_sequence(
            battle_facing facing)
    {
        return static_cast<std::uint8_t>(
                idle_sequence(facing) + 8);
    }

    [[nodiscard]] static constexpr std::uint8_t frame_at(
            const battle_unit_visual_timeline_step* steps,
            int step_count,
            int elapsed_frames,
            bool loop)
    {
        if(! steps || step_count <= 0)
        {
            return 0;
        }
        int total_duration = 0;
        for(int index = 0; index < step_count; ++index)
        {
            total_duration += steps[index].duration;
        }
        if(total_duration <= 0)
        {
            return steps[step_count - 1].frame_index;
        }
        int frame = elapsed_frames > 0 ? elapsed_frames : 0;
        if(loop)
        {
            frame %= total_duration;
        }
        else if(frame >= total_duration)
        {
            return steps[step_count - 1].frame_index;
        }
        for(int index = 0; index < step_count; ++index)
        {
            const int duration = steps[index].duration;
            if(frame < duration)
            {
                return steps[index].frame_index;
            }
            frame -= duration;
        }
        return steps[step_count - 1].frame_index;
    }
};

}

#endif
