#include "konoha/battle_map_visual_projection.h"
#include "konoha/battle_map_movement.h"
#include "konoha/generated_battle_scenario_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_condition_content.h"
#include <cassert>

using namespace konoha;

int main()
{
    battle_scene_controller<12, 9, 22> controller;
    assert(controller.load(battle_scenario_definitions[43],
            battle_map_definitions[43], battle_map_cells, 0, {},
            battle_condition_variants[43][0], 0x43U).success());
    assert(controller.start().success());
    assert(controller.confirm().success());
    const auto origin = controller.snapshot().units[0].position;
    battle_map_movement movement;
    movement.observe(controller.snapshot());
    assert(! movement.busy());
    assert(controller.move_cursor(0, -1).success());
    movement.observe(controller.snapshot());
    assert(! movement.busy());
    auto state = controller.snapshot();
    assert(battle_map_visual_position(state, state.units[0]) == origin);
    assert(battle_map_visual_facing(state, state.units[0]) == battle_facing::up);
    assert(controller.move_cursor(0, 1).success());
    state = controller.snapshot();
    assert(battle_map_visual_facing(state, state.units[0]) == battle_facing::down);
    assert(battle_map_cursor_facing(state) == battle_facing::down);
    assert(controller.move_cursor(0, -1).success());
    movement.observe(controller.snapshot());
    assert(! movement.busy());
    assert(controller.confirm().success());
    movement.observe(controller.snapshot());
    assert(movement.busy());
    auto pose = movement.sample(1);
    assert(pose.sequence == 5);  // original north departure
    assert(pose.offset_y == 16); // begins at old cell, not a teleport
    movement.advance();
    movement.advance();
    assert(movement.sample(1).elapsed_frames == 2);
    assert(movement.sample(1).offset_y == 16); // sprite resource owns departure motion
    movement.observe(controller.snapshot()); // redraw cannot restart the sequence
    assert(movement.sample(1).elapsed_frames == 2);
    for(int i = 2; i < 12; ++i) movement.advance();
    pose = movement.sample(1);
    assert(pose.sequence == 9);  // original north arrival
    assert(pose.offset_y == 0);
    for(int i = 0; i < 14; ++i) movement.advance();
    assert(! movement.busy());
    assert(! movement.sample(2).moving);
    state = controller.snapshot();
    assert(state.units[0].position == origin);
    assert(battle_map_visual_facing(state, state.units[0]) == battle_facing::up);
    auto confirmation = state;
    confirmation.phase = battle_scene_phase::end_confirmation;
    confirmation.player.move_position.y -= 1;
    assert(battle_map_visual_position(confirmation, confirmation.units[0]) == confirmation.player.move_position);
    assert(battle_map_visual_facing(confirmation, confirmation.units[0]) == battle_facing::up);

    // Cancelling a draft clears its visual motion and authoritative position.
    assert(controller.cancel().success());
    assert(controller.cancel().success());
    movement.observe(controller.snapshot());
    assert(! movement.busy());
    assert(controller.snapshot().units[0].position == origin);
}

