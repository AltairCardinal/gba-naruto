#ifndef KONOHA_BATTLE_AI_CANDIDATE_SCORE_H
#define KONOHA_BATTLE_AI_CANDIDATE_SCORE_H

#include "konoha/battle_random.h"
#include "konoha/battle_session.h"

#include <cstdint>

namespace konoha
{

struct ai_candidate_tile_score
{
    int facing = 0;
    int terrain = 0;
    int random = 0;

    [[nodiscard]] constexpr int total() const
    {
        return facing + terrain + random;
    }
};

class battle_ai_candidate_scorer
{
public:
    [[nodiscard]] static ai_candidate_tile_score score_tile(
            battle_facing current_facing,
            battle_facing candidate_facing,
            std::uint8_t tile_flags,
            deterministic_rng& rng)
    {
        ai_candidate_tile_score result;
        if(current_facing == candidate_facing)
        {
            result.facing = 50;
        }
        if((tile_flags & 1) == 0)
        {
            result.terrain = 200;
            return result;
        }

        const int direction =
                static_cast<int>(current_facing);
        if(((tile_flags >> (direction + 4)) & 1) == 0)
        {
            result.terrain = 100;
        }
        result.random = (rng.next_u15() * 50) >> 15;
        return result;
    }

    [[nodiscard]] static constexpr battle_facing facing_toward(
            grid_point origin,
            grid_point target,
            battle_facing fallback)
    {
        const int dx = target.x - origin.x;
        const int dy = target.y - origin.y;
        if(dx == 0 && dy == 0)
        {
            return fallback;
        }
        const int absolute_x = dx < 0 ? -dx : dx;
        const int absolute_y = dy < 0 ? -dy : dy;
        if(absolute_x > absolute_y)
        {
            return dx > 0 ?
                    battle_facing::right :
                    battle_facing::left;
        }
        return dy > 0 ?
                battle_facing::down :
                battle_facing::up;
    }
};

}

#endif
