#ifndef KONOHA_BATTLE_ACTION_ANIMATION_H
#define KONOHA_BATTLE_ACTION_ANIMATION_H

#include "konoha/grid_pathfinder.h"

#include <cstdint>

namespace konoha
{

enum class battle_action_animation_stage : std::uint8_t
{
    windup,
    approach,
    impact,
    returning,
    settle,
};

struct battle_action_animation_pose
{
    battle_action_animation_stage stage = battle_action_animation_stage::settle;
    int actor_offset_x = 0;
    int actor_offset_y = 0;
    int target_offset_x = 0;
    int target_offset_y = 0;
    int hit_index = -1;
    bool target_visible = true;
    bool play_hit_cue = false;
};

class battle_action_animation
{
public:
    static constexpr int windup_frame_count = 12;
    static constexpr int approach_frame_count = 12;
    static constexpr int impact_frame_count = 16;
    static constexpr int returning_frame_count = 12;
    static constexpr int settle_frame_count = 12;
    static constexpr int default_impact_count = 3;
    static constexpr int maximum_impact_count = 32;
    static constexpr int frame_count = 96;

    [[nodiscard]] static constexpr int return_start_frame(
            int impact_count)
    {
        return windup_frame_count +
                approach_frame_count +
                _clamp_impact_count(impact_count) *
                        impact_frame_count;
    }

    [[nodiscard]] static constexpr int settle_start_frame(
            int impact_count)
    {
        return return_start_frame(impact_count) +
                returning_frame_count;
    }

    [[nodiscard]] static constexpr int total_frame_count(
            int impact_count)
    {
        return settle_start_frame(impact_count) +
                settle_frame_count;
    }

    [[nodiscard]] static constexpr battle_action_animation_pose pose(
            int frame,
            grid_point actor,
            grid_point target,
            bool actor_lunges = true,
            int impact_count = default_impact_count)
    {
        impact_count = _clamp_impact_count(impact_count);
        const int target_dx = (target.x - actor.x) * 32;
        const int target_dy = (target.y - actor.y) * 16;
        const int lunge_x = target_dx * 3 / 4;
        const int lunge_y = target_dy * 3 / 4;
        const int impact_end =
                windup_frame_count +
                approach_frame_count +
                impact_count * impact_frame_count;
        const int return_end =
                impact_end + returning_frame_count;
        battle_action_animation_pose result;

        if(frame < windup_frame_count)
        {
            result.stage = battle_action_animation_stage::windup;
            const int recoil = 1 + frame / 4;
            if(actor_lunges)
            {
                result.actor_offset_x =
                        -_sign(target_dx) * recoil;
                result.actor_offset_y =
                        -_sign(target_dy) * recoil;
            }
            return result;
        }
        if(frame <
                windup_frame_count +
                        approach_frame_count)
        {
            result.stage = battle_action_animation_stage::approach;
            const int progress =
                    frame - windup_frame_count + 1;
            if(actor_lunges)
            {
                result.actor_offset_x =
                        lunge_x * progress /
                        approach_frame_count;
                result.actor_offset_y =
                        lunge_y * progress /
                        approach_frame_count;
            }
            return result;
        }
        if(frame < impact_end)
        {
            result.stage = battle_action_animation_stage::impact;
            if(actor_lunges)
            {
                result.actor_offset_x = lunge_x;
                result.actor_offset_y = lunge_y;
            }
            const int impact_frame =
                    frame -
                    windup_frame_count -
                    approach_frame_count;
            result.hit_index =
                    impact_frame / impact_frame_count;
            const int local_frame =
                    impact_frame % impact_frame_count;
            const int shake = local_frame % 4 < 2 ? -2 : 2;
            if(_absolute(target_dx) >= _absolute(target_dy))
            {
                result.target_offset_y = shake;
            }
            else
            {
                result.target_offset_x = shake;
            }
            result.target_visible = local_frame >= 2;
            result.play_hit_cue = local_frame == 0;
            return result;
        }
        if(frame < return_end)
        {
            result.stage = battle_action_animation_stage::returning;
            const int remaining = return_end - 1 - frame;
            if(actor_lunges)
            {
                result.actor_offset_x =
                        lunge_x * remaining /
                        returning_frame_count;
                result.actor_offset_y =
                        lunge_y * remaining /
                        returning_frame_count;
            }
            return result;
        }
        return result;
    }

private:
    [[nodiscard]] static constexpr int _clamp_impact_count(
            int impact_count)
    {
        return impact_count < 0 ?
                0 :
                impact_count > maximum_impact_count ?
                        maximum_impact_count :
                        impact_count;
    }

    [[nodiscard]] static constexpr int _sign(int value)
    {
        return value < 0 ? -1 : value > 0 ? 1 : 0;
    }

    [[nodiscard]] static constexpr int _absolute(int value)
    {
        return value < 0 ? -value : value;
    }
};

}

#endif
