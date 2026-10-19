#include "konoha/battle_ai_candidate_score.h"

#include <cassert>

using namespace konoha;

int main()
{
    deterministic_rng open_rng(41);
    const ai_candidate_tile_score open =
            battle_ai_candidate_scorer::score_tile(
                    battle_facing::up,
                    battle_facing::up,
                    0,
                    open_rng);
    assert(open.facing == 50);
    assert(open.terrain == 200);
    assert(open.random == 0);
    assert(open.total() == 250);

    deterministic_rng open_control(41);
    assert(open_rng.next_u15() == open_control.next_u15());

    deterministic_rng directional_rng(41);
    deterministic_rng directional_control(41);
    const int expected_random =
            (directional_control.next_u15() * 50) >> 15;
    const ai_candidate_tile_score directional =
            battle_ai_candidate_scorer::score_tile(
                    battle_facing::up,
                    battle_facing::right,
                    1,
                    directional_rng);
    assert(directional.facing == 0);
    assert(directional.terrain == 100);
    assert(directional.random == expected_random);
    assert(directional.total() == 100 + expected_random);
    assert(directional_rng.next_u15() ==
           directional_control.next_u15());

    deterministic_rng blocked_rng(41);
    deterministic_rng blocked_control(41);
    const int expected_blocked_random =
            (blocked_control.next_u15() * 50) >> 15;
    const ai_candidate_tile_score blocked =
            battle_ai_candidate_scorer::score_tile(
                    battle_facing::up,
                    battle_facing::up,
                    1 | (1 << 4),
                    blocked_rng);
    assert(blocked.facing == 50);
    assert(blocked.terrain == 0);
    assert(blocked.random == expected_blocked_random);
    assert(blocked.total() == 50 + expected_blocked_random);

    assert(battle_ai_candidate_scorer::facing_toward(
                   { 2, 2 }, { 5, 3 }, battle_facing::up) ==
           battle_facing::right);
    assert(battle_ai_candidate_scorer::facing_toward(
                   { 2, 2 }, { 1, 5 }, battle_facing::up) ==
           battle_facing::down);
    assert(battle_ai_candidate_scorer::facing_toward(
                   { 2, 2 }, { 2, 2 }, battle_facing::left) ==
           battle_facing::left);
}
