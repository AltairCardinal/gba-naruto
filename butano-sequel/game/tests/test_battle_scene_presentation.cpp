#include "konoha/battle_scene_presentation.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_scene_presentation presentation;
    assert(! presentation.busy());

    battle_scene_presentation_event action = {
        true,
        true,
        2,
        5,
        { 1, 1 },
        { 3, 1 },
        { 4, 1 },
        false,
        1,
        true,
        1,
        true,
    };
    action.impact_count = 1;
    assert(presentation.begin(action));
    assert(presentation.busy());
    assert(presentation.frame() == 0);
    assert(presentation.event().actor_id == 2);
    assert(presentation.event().animation_family == 1);
    assert(presentation.event().targets_opponent);
    assert(presentation.affects(1));
    assert(! presentation.affects(4));

    const battle_scene_unit_pose movement_start =
            presentation.pose(2, { 3, 1 });
    assert(movement_start.offset_x == -64);
    assert(movement_start.offset_y == 0);
    assert(movement_start.visible);

    for(int frame = 0;
            frame < battle_scene_presentation::movement_frame_count;
            ++frame)
    {
        presentation.advance();
    }
    assert(presentation.frame() ==
            battle_scene_presentation::movement_frame_count);
    assert(presentation.combat().busy());
    assert(presentation.combat().stage() ==
           battle_combat_presentation_stage::
                   transition_in);
    const battle_scene_unit_pose duel_entry =
            presentation.pose(2, { 3, 1 });
    assert(duel_entry.offset_x == 0);
    assert(duel_entry.offset_y == 0);

    while(presentation.combat().stage() !=
            battle_combat_presentation_stage::impact)
    {
        presentation.advance();
    }
    const battle_scene_unit_pose impact_actor =
            presentation.pose(2, { 3, 1 });
    const battle_scene_unit_pose impact_target =
            presentation.pose(1, { 4, 1 });
    assert(impact_actor.offset_x == 0);
    assert(! impact_target.visible);
    assert(impact_target.play_hit_cue);

    const battle_scene_unit_pose wrong_target =
            presentation.pose(4, { 4, 1 });
    assert(wrong_target.visible);
    assert(! wrong_target.play_hit_cue);

    while(presentation.busy())
    {
        presentation.advance();
    }
    const battle_scene_unit_pose settled =
            presentation.pose(2, { 3, 1 });
    assert(settled.offset_x == 0);
    assert(settled.offset_y == 0);
    assert(settled.visible);

    const battle_scene_presentation_event movement_only = {
        true,
        false,
        3,
        no_ability,
        { 2, 3 },
        { 2, 1 },
        {},
    };
    assert(presentation.begin(movement_only));
    assert(presentation.pose(3, { 2, 1 }).offset_y == 32);
    for(int frame = 0;
            frame < battle_scene_presentation::movement_frame_count;
            ++frame)
    {
        presentation.advance();
    }
    assert(! presentation.busy());

    battle_scene_presentation_event cast = {
        true,
        true,
        2,
        9,
        { 1, 1 },
        { 3, 1 },
        { 4, 1 },
        false,
        5,
        true,
        1,
        false,
    };
    cast.impact_count = 0;
    assert(presentation.begin(cast));
    for(int frame = 0;
            frame <
                    battle_scene_presentation::
                            movement_frame_count;
            ++frame)
    {
        presentation.advance();
    }
    assert(presentation.combat().busy());
    bool saw_title = false;
    bool saw_movie = false;
    bool saw_single_actor_stage = false;
    while(presentation.busy())
    {
        saw_title = saw_title ||
                presentation.combat().title_visible();
        saw_movie = saw_movie ||
                presentation.combat().movie_visible();
        if(! presentation.combat().map_visible())
        {
            saw_single_actor_stage =
                    saw_single_actor_stage ||
                    presentation.combat().
                            single_actor_stage();
            assert(presentation.combat().
                    actor_visible());
            assert(! presentation.combat().
                    target_visible());
            assert(! presentation.combat().
                    versus_divider_visible());
        }
        presentation.advance();
    }
    assert(saw_title);
    assert(saw_movie);
    assert(saw_single_actor_stage);
    const battle_scene_unit_pose cast_actor =
            presentation.pose(2, { 3, 1 });
    assert(cast_actor.offset_x == 0);
    assert(cast_actor.offset_y == 0);
    assert(! presentation.pose(1, { 4, 1 }).play_hit_cue);

    battle_scene_presentation_event control = action;
    control.action_id = 24;
    control.animation_family =
            active_action_definitions[24]
                    .presentation.animation_family;
    control.impact_count = 1;
    assert(presentation.begin(control));
    for(int frame = 0;
            frame <
                    battle_scene_presentation::
                            movement_frame_count;
            ++frame)
    {
        presentation.advance();
    }
    assert(presentation.combat().definition().kind ==
           battle_combat_presentation_kind::
                   control_technique);
    bool saw_control_title = false;
    bool saw_control_duel = false;
    bool saw_control_impact = false;
    while(presentation.busy())
    {
        saw_control_title =
                saw_control_title ||
                presentation.combat().title_visible();
        saw_control_duel =
                saw_control_duel ||
                presentation.combat().
                        versus_divider_visible();
        saw_control_impact =
                saw_control_impact ||
                presentation.combat().stage() ==
                        battle_combat_presentation_stage::
                                impact;
        presentation.advance();
    }
    assert(saw_control_title);
    assert(saw_control_duel);
    assert(saw_control_impact);

    battle_scene_presentation_event bomb_tool = action;
    bomb_tool.action_id = 55;
    bomb_tool.ninja_tool = true;
    bomb_tool.animation_family =
            ninja_tool_action_definitions[55]
                    .presentation.animation_family;
    bomb_tool.impact_count = 1;
    assert(presentation.begin(bomb_tool));
    for(int frame = 0;
            frame <
                    battle_scene_presentation::
                            movement_frame_count;
            ++frame)
    {
        presentation.advance();
    }
    assert(presentation.combat().definition().kind ==
           battle_combat_presentation_kind::bomb_tool);
    bool saw_bomb_title = false;
    bool saw_bomb_duel = false;
    bool saw_bomb_impact = false;
    while(presentation.busy())
    {
        saw_bomb_title =
                saw_bomb_title ||
                presentation.combat().title_visible();
        saw_bomb_duel =
                saw_bomb_duel ||
                presentation.combat().
                        versus_divider_visible();
        saw_bomb_impact =
                saw_bomb_impact ||
                presentation.combat().stage() ==
                        battle_combat_presentation_stage::
                                impact;
        presentation.advance();
    }
    assert(saw_bomb_title);
    assert(saw_bomb_duel);
    assert(saw_bomb_impact);

    battle_scene_presentation_event resource;
    resource.valid = true;
    resource.actor_id = 2;
    resource.origin = { 3, 1 };
    resource.destination = { 3, 1 };
    resource.has_resource = true;
    resource.resource_type =
            battle_resource_command_type::
                    replenish_chakra;
    resource.resource_amount = 3;
    resource.resource_hp_delta = -15;
    resource.resource_chakra_delta = 3;
    assert(presentation.begin(resource));
    assert(presentation.event().has_resource);
    assert(presentation.event().resource_type ==
           battle_resource_command_type::
                   replenish_chakra);
    assert(presentation.event().resource_amount == 3);
    assert(presentation.event().resource_hp_delta == -15);
    assert(presentation.event().resource_chakra_delta == 3);
    for(int frame = 0;
            frame <
                    battle_scene_presentation::
                            movement_frame_count;
            ++frame)
    {
        presentation.advance();
    }
    assert(! presentation.busy());

    const battle_side_start_passive_event side_start = {
        true,
        battle_side_start_passive_kind::berserk_symbol,
        3,
        25,
        41,
        0,
        0x1E,
        30,
        encode_status_duration_ticks(5),
        true,
    };
    const battle_scene_presentation_event passive =
            make_side_start_presentation_event(
                    side_start, { 5, 6 });
    assert(passive.valid);
    assert(passive.has_side_start_passive);
    assert(passive.actor_id == 3);
    assert(passive.origin == grid_point({ 5, 6 }));
    assert(passive.destination == grid_point({ 5, 6 }));
    assert(passive.passive == 25);
    assert(passive.passive_kind ==
           battle_side_start_passive_kind::
                   berserk_symbol);
    assert(passive.resource_hp_delta == 41);
    assert(passive.passive_status_code == 0x1E);
    assert(passive.passive_status_value == 30);
    assert(passive.passive_status_duration_ticks ==
           encode_status_duration_ticks(5));
    assert(passive.passive_status_applied);
    assert(presentation.begin(passive));
    for(int frame = 0;
            frame <
                    battle_scene_presentation::
                            passive_frame_count - 1;
            ++frame)
    {
        presentation.advance();
    }
    assert(presentation.busy());
    presentation.advance();
    assert(! presentation.busy());

    battlefield_object_tick_event type_2_expiry;
    type_2_expiry.kind =
            battlefield_object_tick_kind::type_2_expired;
    type_2_expiry.slot = 4;
    type_2_expiry.object.type = 2;
    type_2_expiry.object.x = 6;
    type_2_expiry.object.y = 8;
    type_2_expiry.object.payload_id = 39;
    const battle_scene_presentation_event
            type_2_presentation =
                    make_battlefield_object_presentation_event(
                            type_2_expiry, {}, 0);
    assert(type_2_presentation.valid);
    assert(! type_2_presentation.has_action);
    assert(type_2_presentation.actor_id ==
           no_battle_unit);
    assert(type_2_presentation.action_id == 39);
    assert(type_2_presentation.target ==
           grid_point({ 6, 8 }));
    assert(type_2_presentation.has_battlefield_object);
    assert(type_2_presentation.battlefield_object_kind ==
           battlefield_object_tick_kind::
                   type_2_expired);
    assert(type_2_presentation.battlefield_object_slot == 4);
    assert(type_2_presentation.battlefield_object_damage == 0);
    assert(type_2_presentation
                   .battlefield_object_tile_index_start ==
           0x0300);
    assert(type_2_presentation
                   .battlefield_object_tile_index_end ==
           0x037F);
    assert(type_2_presentation
                   .battlefield_object_palette_bank_start ==
           12);
    assert(type_2_presentation
                   .battlefield_object_palette_bank_end ==
           14);
    assert(type_2_presentation
                   .battlefield_object_effect_sequence ==
           7);
    assert(presentation.begin(type_2_presentation));
    assert(presentation.busy());
    for(int frame = 0;
            frame <
                    battle_scene_presentation::
                            battlefield_object_expiry_frame_count -
                            1;
            ++frame)
    {
        presentation.advance();
    }
    assert(presentation.busy());
    presentation.advance();
    assert(! presentation.busy());

    battle_scene_presentation_queue<3> queue;
    assert(queue.empty());
    assert(queue.push(action));
    assert(queue.push(passive));
    assert(queue.count() == 2);
    const battle_scene_presentation_event first =
            queue.pop();
    assert(first.action_id == action.action_id);
    assert(queue.count() == 1);
    assert(queue.pop().passive == 25);
    assert(queue.empty());
    assert(! queue.pop().valid);
    assert(queue.push(action));
    assert(queue.push(passive));
    assert(queue.push(resource));
    assert(! queue.push(action));
    queue.clear();
    assert(queue.empty());

    assert(! presentation.begin({}));
}
