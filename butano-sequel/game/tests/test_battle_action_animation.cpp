#include "konoha/battle_action_animation.h"

#include <cassert>

using namespace konoha;

int main()
{
    const grid_point actor = { 4, 5 };
    const grid_point target = { 4, 4 };

    const battle_action_animation_pose windup =
            battle_action_animation::pose(0, actor, target);
    assert(windup.stage == battle_action_animation_stage::windup);
    assert(windup.actor_offset_y > 0);
    assert(windup.target_visible);

    const battle_action_animation_pose approach =
            battle_action_animation::pose(18, actor, target);
    assert(approach.stage == battle_action_animation_stage::approach);
    assert(approach.actor_offset_y < 0);

    const battle_action_animation_pose first_hit =
            battle_action_animation::pose(24, actor, target);
    assert(first_hit.stage == battle_action_animation_stage::impact);
    assert(first_hit.hit_index == 0);
    assert(! first_hit.target_visible);
    assert(first_hit.play_hit_cue);

    const battle_action_animation_pose second_hit =
            battle_action_animation::pose(40, actor, target);
    assert(second_hit.stage == battle_action_animation_stage::impact);
    assert(second_hit.hit_index == 1);
    assert(second_hit.play_hit_cue);

    const battle_action_animation_pose third_hit =
            battle_action_animation::pose(56, actor, target);
    assert(third_hit.stage == battle_action_animation_stage::impact);
    assert(third_hit.hit_index == 2);
    assert(third_hit.play_hit_cue);

    const battle_action_animation_pose returning =
            battle_action_animation::pose(78, actor, target);
    assert(returning.stage == battle_action_animation_stage::returning);

    const battle_action_animation_pose settled =
            battle_action_animation::pose(
                    battle_action_animation::frame_count - 1, actor, target);
    assert(settled.stage == battle_action_animation_stage::settle);
    assert(settled.actor_offset_x == 0);
    assert(settled.actor_offset_y == 0);
    assert(settled.target_offset_x == 0);
    assert(settled.target_offset_y == 0);
    assert(settled.target_visible);

    const battle_action_animation_pose horizontal =
            battle_action_animation::pose(28, { 1, 1 }, { 2, 1 });
    assert(horizontal.actor_offset_x > 0);
    assert(horizontal.target_offset_y != 0);

    const battle_action_animation_pose ranged_windup =
            battle_action_animation::pose(
                    0, actor, target, false);
    assert(ranged_windup.stage ==
            battle_action_animation_stage::windup);
    assert(ranged_windup.actor_offset_x == 0);
    assert(ranged_windup.actor_offset_y == 0);

    const battle_action_animation_pose ranged_impact =
            battle_action_animation::pose(
                    24, actor, target, false);
    assert(ranged_impact.stage ==
            battle_action_animation_stage::impact);
    assert(ranged_impact.actor_offset_x == 0);
    assert(ranged_impact.actor_offset_y == 0);
    assert(ranged_impact.play_hit_cue);

    assert(battle_action_animation::total_frame_count(0) == 48);
    assert(battle_action_animation::total_frame_count(1) == 64);
    assert(battle_action_animation::total_frame_count(3) ==
            battle_action_animation::frame_count);

    const battle_action_animation_pose no_phantom_hit =
            battle_action_animation::pose(
                    24, actor, target, false, 0);
    assert(no_phantom_hit.stage ==
            battle_action_animation_stage::returning);
    assert(no_phantom_hit.hit_index == -1);
    assert(! no_phantom_hit.play_hit_cue);

    const battle_action_animation_pose after_single_hit =
            battle_action_animation::pose(
                    40, actor, target, true, 1);
    assert(after_single_hit.stage ==
            battle_action_animation_stage::returning);
    assert(after_single_hit.hit_index == -1);
}
