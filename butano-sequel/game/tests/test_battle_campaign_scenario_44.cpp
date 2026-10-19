#include "konoha/battle_campaign_route.h"
#include "konoha/battle_campaign_scene_progression.h"
#include "konoha/battle_mission_rules.h"
#include "konoha/battle_scene_controller.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

using controller_type =
        battle_scene_controller<12, 9, 22>;
using snapshot_type = battle_scene_snapshot<12>;

const battle_scene_unit_view& unit(
        const snapshot_type& state,
        battle_unit_id id)
{
    for(std::size_t index = 0;
            index < state.unit_count; ++index)
    {
        if(state.units[index].id == id)
        {
            return state.units[index];
        }
    }
    assert(false);
    return state.units[0];
}

const battle_scene_unit_view* active_enemy(
        const snapshot_type& state)
{
    for(const battle_scene_unit_view& candidate :
            state.units)
    {
        if(candidate.active &&
                candidate.side == battle_side::enemy)
        {
            return &candidate;
        }
    }
    return nullptr;
}

void drain_presentations(controller_type& controller)
{
    while(controller.take_presentation_event().valid)
    {
    }
}

void set_cursor(
        controller_type& controller,
        grid_point target)
{
    while(controller.snapshot().cursor.x != target.x)
    {
        assert(controller.move_cursor(
                           controller.snapshot().cursor.x <
                                           target.x ?
                                   1 :
                                   -1,
                           0)
                       .success());
    }
    while(controller.snapshot().cursor.y != target.y)
    {
        assert(controller.move_cursor(
                           0,
                           controller.snapshot().cursor.y <
                                           target.y ?
                                   1 :
                                   -1)
                       .success());
    }
}

void select_command(
        controller_type& controller,
        battle_command_type command)
{
    for(int step = 0;
            step < 8 &&
            controller.snapshot().player.selected_command !=
                    command;
            ++step)
    {
        assert(controller.move_cursor(0, 1).success());
    }
    assert(controller.snapshot().player.selected_command ==
           command);
    assert(controller.confirm().success());
}

void finish_enemy_side(controller_type& controller)
{
    for(int step = 0;
            step < 64 &&
            controller.snapshot().phase ==
                    battle_scene_phase::enemy_turn;
            ++step)
    {
        drain_presentations(controller);
        assert(controller.tick().success());
    }
    drain_presentations(controller);
    assert(controller.snapshot().phase !=
           battle_scene_phase::enemy_turn);
}

void finish_facing_and_turn(
        controller_type& controller,
        battle_facing facing = battle_facing::up)
{
    if(controller.snapshot().phase ==
            battle_scene_phase::facing_selection)
    {
        switch(facing)
        {
        case battle_facing::up:
            assert(controller.move_cursor(0, -1).success());
            break;
        case battle_facing::right:
            assert(controller.move_cursor(1, 0).success());
            break;
        case battle_facing::down:
            assert(controller.move_cursor(0, 1).success());
            break;
        case battle_facing::left:
            assert(controller.move_cursor(-1, 0).success());
            break;
        }
        assert(controller.confirm().success());
    }
    if(controller.snapshot().phase ==
            battle_scene_phase::defense_decision)
    {
        assert(controller.confirm().success());
    }
    finish_enemy_side(controller);
}

bool move_adjacent_to(
        controller_type& controller,
        grid_point target)
{
    for(int distance = 1; distance < 9 + 22; ++distance)
    {
        for(int y = 0; y < 22; ++y)
        {
            for(int x = 0; x < 9; ++x)
            {
                const int candidate_distance =
                        (x > target.x ?
                                 x - target.x :
                                 target.x - x) +
                        (y > target.y ?
                                 y - target.y :
                                 target.y - y);
                if(candidate_distance != distance)
                {
                    continue;
                }
                set_cursor(controller, { x, y });
                if(controller.confirm().success())
                {
                    assert(controller.snapshot().phase ==
                           battle_scene_phase::
                                   command_selection);
                    return distance == 1;
                }
            }
        }
    }
    assert(false);
    return false;
}

void select_action_five(controller_type& controller)
{
    select_command(
            controller,
            battle_command_type::ability);
    for(int step = 0;
            step < 24 &&
            controller.snapshot().player
                            .selected_action_id != 5;
            ++step)
    {
        assert(controller.move_cursor(0, 1).success());
    }
    assert(controller.snapshot().player
                   .selected_action_id == 5);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_selection);
}

void attack_or_approach_kakashi(
        controller_type& controller)
{
    const snapshot_type before = controller.snapshot();
    assert(before.phase ==
           battle_scene_phase::unit_selection);
    const battle_scene_unit_view* enemy =
            active_enemy(before);
    assert(enemy);
    const grid_point enemy_position = enemy->position;

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);
    if(move_adjacent_to(controller, enemy_position))
    {
        select_action_five(controller);
        set_cursor(controller, enemy_position);
        assert(controller.confirm().success());
        drain_presentations(controller);
    }
    else
    {
        select_command(
                controller,
                battle_command_type::end_action);
    }
    finish_facing_and_turn(controller);
}

bool move_toward_bells(controller_type& controller)
{
    constexpr grid_point interaction = { 4, 3 };
    assert(controller.snapshot().phase ==
           battle_scene_phase::unit_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);

    for(int distance = 0; distance < 9 + 22; ++distance)
    {
        for(int y = 0; y < 22; ++y)
        {
            for(int x = 0; x < 9; ++x)
            {
                const int candidate_distance =
                        (x > interaction.x ?
                                 x - interaction.x :
                                 interaction.x - x) +
                        (y > interaction.y ?
                                 y - interaction.y :
                                 interaction.y - y);
                if(candidate_distance != distance)
                {
                    continue;
                }
                set_cursor(controller, { x, y });
                if(controller.confirm().success())
                {
                    select_command(
                            controller,
                            battle_command_type::
                                    end_action);
                    finish_facing_and_turn(
                            controller,
                            battle_facing::down);
                    return distance == 0;
                }
            }
        }
    }
    assert(false);
    return false;
}

character_progression_record naruto_after_scenario_43()
{
    character_progression_record result = {
        1,
        3,
        0,
        2,
        true,
    };
    assert(initialize_character_action_progression(
            result, unit_definitions[1]));
    return result;
}

}

int main()
{
    battle_campaign_state campaign =
            empty_battle_campaign();
    campaign.chapter_id = 44;
    assert(activate_battle_campaign_character(
            campaign, naruto_after_scenario_43()));
    assert(set_battle_campaign_party(
            campaign, { 1, 0, 0 }));
    assert(prepare_battle_campaign_stage(campaign)
                   .success());
    assert(campaign.party ==
           (std::array<std::uint8_t, 3>{ 1, 2, 3 }));
    assert(campaign.characters[2]
                   .progression.level == 1);
    assert(campaign.characters[2]
                   .progression.experience == 100);
    assert(campaign.characters[3]
                   .progression.level == 1);
    assert(campaign.characters[3]
                   .progression.experience == 0);

    battle_campaign_scene_progression progression;
    assert(progression.begin(campaign) ==
           battle_campaign_error::none);
    battle_scenario_load_policy policy;
    policy.preserve_empty_unit_slots = true;
    assert(apply_battle_campaign_scene_policy(
                   campaign, policy) ==
           battle_campaign_error::none);

    controller_type controller;
    assert(controller.load(
                   battle_scenario_definitions[44],
                   battle_map_definitions[44],
                   battle_map_cells,
                   0,
                   policy,
                   battle_condition_variants[44][0],
                   44U,
                   progression.records(),
                   false,
                   battle_mission_rules_for(44, 0))
                   .success());

    const battle_scene_object_snapshot objects =
            controller.object_snapshot();
    assert(objects.count == 1);
    assert(objects.objects[0].slot == 1);
    assert(objects.objects[0].type == 3);
    assert(objects.objects[0].position ==
           grid_point({ 4, 4 }));

    assert(controller.start().success());
    const snapshot_type initial =
            controller.snapshot();
    assert(initial.phase ==
           battle_scene_phase::unit_selection);
    assert(initial.round == 1);
    assert(initial.active_unit_count == 4);
    assert(unit(initial, 1).character_id == 1);
    assert(unit(initial, 1).position ==
           grid_point({ 4, 17 }));
    assert(unit(initial, 2).character_id == 2);
    assert(unit(initial, 2).position ==
           grid_point({ 2, 17 }));
    assert(unit(initial, 3).character_id == 3);
    assert(unit(initial, 3).position ==
           grid_point({ 6, 17 }));
    assert(unit(initial, 4).character_id == 7);
    assert(unit(initial, 4).position ==
           grid_point({ 4, 6 }));
    assert(unit(initial, 4).hp == 100);

    // A normal completed action leaves the objective object active;
    // the generated slot-inactive condition must not win immediately.
    assert(controller.confirm().success());
    assert(controller.confirm().success());
    select_command(
            controller,
            battle_command_type::end_action);
    finish_facing_and_turn(controller);
    assert(controller.snapshot().phase !=
           battle_scene_phase::outcome);
    assert(controller.object_snapshot().count == 1);

    for(int turn = 0;
            turn < 96 &&
            active_enemy(controller.snapshot());
            ++turn)
    {
        assert(controller.snapshot().phase ==
               battle_scene_phase::unit_selection);
        attack_or_approach_kakashi(controller);
    }
    assert(! active_enemy(controller.snapshot()));
    assert(controller.snapshot().phase ==
           battle_scene_phase::unit_selection);
    assert(controller.object_snapshot().count == 1);

    for(int turn = 0;
            turn < 48 &&
            controller.snapshot().phase !=
                    battle_scene_phase::outcome;
            ++turn)
    {
        assert(controller.snapshot().phase ==
               battle_scene_phase::unit_selection);
        (void) move_toward_bells(controller);
    }

    const snapshot_type outcome = controller.snapshot();
    assert(outcome.phase ==
           battle_scene_phase::outcome);
    assert(outcome.outcome ==
           battle_condition_outcome::win);
    assert(controller.object_snapshot().count == 0);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::result);
    const battle_result& result =
            controller.result_snapshot();
    assert(result.participant_count == 3);
    for(std::size_t index = 0;
            index < result.participant_count;
            ++index)
    {
        assert(result.participants[index]
                       .mission_experience == 125);
        assert(result.participants[index]
                       .round_bonus_experience == 0);
        assert(result.participants[index]
                       .battle_experience == 0);
        assert(result.participants[index]
                       .total_experience == 125);
    }

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::level_up);
    assert(controller.progression_roster()[0].level == 3);
    assert(controller.progression_roster()[0].experience == 125);
    assert(controller.progression_roster()[0].training_points == 2);
    assert(controller.progression_roster()[1].level == 2);
    assert(controller.progression_roster()[1].experience == 45);
    assert(controller.progression_roster()[1].training_points == 1);
    assert(controller.progression_roster()[2].level == 1);
    assert(controller.progression_roster()[2].experience == 125);
    assert(controller.progression_roster()[2].training_points == 0);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::training);
    assert(controller.cancel().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::complete);

    progression.records() =
            controller.progression_roster();
    progression.equipped_tools() =
            controller.equipped_tools_roster();
    assert(progression.commit(campaign) ==
           battle_campaign_error::none);
    assert(advance_battle_campaign_stage(
                   campaign,
                   battle_runtime_scene_exit::victory)
                   .success());
    assert(campaign.chapter_id == 45);
    assert(campaign.party ==
           (std::array<std::uint8_t, 3>{ 1, 2, 3 }));
}
