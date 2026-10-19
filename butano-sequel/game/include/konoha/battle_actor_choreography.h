#ifndef KONOHA_BATTLE_ACTOR_CHOREOGRAPHY_H
#define KONOHA_BATTLE_ACTOR_CHOREOGRAPHY_H

#include "konoha/battle_combat_presentation.h"

#include <array>
#include <cstdint>

namespace konoha
{

struct battle_actor_choreography_sample
{
    bool overrides_default = false;
    bool visible = true;
    std::uint8_t visual_slot = 0;
    std::uint8_t frame_index = 0;
    std::int16_t screen_anchor_x = 0;
};

struct battle_actor_choreography_step
{
    battle_combat_presentation_stage stage =
            battle_combat_presentation_stage::complete;
    std::uint8_t first_frame = 0;
    std::uint8_t duration = 0;
    bool visible = true;
    std::uint8_t visual_slot = 0;
    std::uint8_t frame_index = 0;
    std::int16_t screen_anchor_x = 0;

    [[nodiscard]] constexpr bool contains(
            battle_combat_presentation_stage query_stage,
            int query_frame) const
    {
        return stage == query_stage &&
                query_frame >= first_frame &&
                query_frame <
                        static_cast<int>(first_frame) +
                                duration;
    }
};

namespace detail
{

// Action 5 (忍者组合拳) original frame mapping:
// movie 0 is original frame 77, movie 70 is frame 147, and impact
// 0..15 is frame 148..163.  Slots and frame indices reference each
// combatant's ROM-derived battle unit visual catalog; this table owns
// choreography only, never character pixels or battle resolution.
inline constexpr std::array<
        battle_actor_choreography_step,
        14> action_05_actor_choreography = {{
    { battle_combat_presentation_stage::action_movie,
      0, 4, true, 0, 16, 68 },
    { battle_combat_presentation_stage::action_movie,
      4, 2, true, 0, 16, 72 },
    { battle_combat_presentation_stage::action_movie,
      6, 54, false, 0, 0, 0 },
    { battle_combat_presentation_stage::action_movie,
      60, 8, true, 3, 0, 148 },
    { battle_combat_presentation_stage::action_movie,
      68, 3, true, 3, 1, 148 },
    { battle_combat_presentation_stage::impact,
      0, 8, true, 3, 2, 148 },
    { battle_combat_presentation_stage::impact,
      8, 2, true, 3, 3, 148 },
    { battle_combat_presentation_stage::impact,
      10, 1, true, 3, 3, 140 },
    { battle_combat_presentation_stage::impact,
      11, 1, true, 3, 3, 132 },
    { battle_combat_presentation_stage::impact,
      12, 1, true, 3, 3, 124 },
    { battle_combat_presentation_stage::impact,
      13, 1, true, 3, 3, 116 },
    { battle_combat_presentation_stage::impact,
      14, 1, true, 3, 3, 112 },
    { battle_combat_presentation_stage::impact,
      15, 1, true, 3, 4, 113 },
    { battle_combat_presentation_stage::result,
      0, 18, true, 3, 4, 106 },
}};

}

[[nodiscard]] inline constexpr battle_actor_choreography_sample
battle_actor_choreography_for(
        ability_id action_id,
        battle_combat_presentation_stage stage,
        int frame)
{
    if(action_id != 5)
    {
        return {};
    }
    for(const battle_actor_choreography_step& step :
            detail::action_05_actor_choreography)
    {
        if(step.contains(stage, frame))
        {
            return {
                true,
                step.visible,
                step.visual_slot,
                step.frame_index,
                step.screen_anchor_x,
            };
        }
    }
    return {};
}

}

#endif
