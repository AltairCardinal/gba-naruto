#include "konoha/battle_actor_choreography.h"

#include <cassert>

using namespace konoha;

int main()
{
    const battle_actor_choreography_sample launch =
            battle_actor_choreography_for(
                    5,
                    battle_combat_presentation_stage::action_movie,
                    0);
    assert(launch.overrides_default);
    assert(launch.visible);
    assert(launch.visual_slot == 0);
    assert(launch.frame_index == 16);
    assert(launch.screen_anchor_x == 68);

    const battle_actor_choreography_sample vanished =
            battle_actor_choreography_for(
                    5,
                    battle_combat_presentation_stage::action_movie,
                    20);
    assert(vanished.overrides_default);
    assert(! vanished.visible);

    const battle_actor_choreography_sample reentry =
            battle_actor_choreography_for(
                    5,
                    battle_combat_presentation_stage::action_movie,
                    60);
    assert(reentry.visible);
    assert(reentry.visual_slot == 3);
    assert(reentry.frame_index == 0);
    assert(reentry.screen_anchor_x == 148);

    const battle_actor_choreography_sample strike =
            battle_actor_choreography_for(
                    5,
                    battle_combat_presentation_stage::impact,
                    15);
    assert(strike.visible);
    assert(strike.visual_slot == 3);
    assert(strike.frame_index == 4);
    assert(strike.screen_anchor_x == 113);

    const battle_actor_choreography_sample settle =
            battle_actor_choreography_for(
                    5,
                    battle_combat_presentation_stage::result,
                    3);
    assert(settle.visible);
    assert(settle.visual_slot == 3);
    assert(settle.frame_index == 4);
    assert(settle.screen_anchor_x == 106);

    assert(! battle_actor_choreography_for(
                    16,
                    battle_combat_presentation_stage::action_movie,
                    0).overrides_default);
    assert(! battle_actor_choreography_for(
                    5,
                    battle_combat_presentation_stage::technique_title,
                    0).overrides_default);
    return 0;
}
