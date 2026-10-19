#include "konoha/battle_campaign_route.h"
#include "konoha/battle_campaign_scene_progression.h"
#include "konoha/battle_mission_rules.h"
#include "konoha/battle_scene_controller.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <array>
#include <cassert>
#include <cstdint>

using namespace konoha;

namespace
{

using scenario_42_controller =
        battle_scene_controller<12, 9, 22>;

void drain_presentations(
        scenario_42_controller& controller)
{
    while(controller.take_presentation_event().valid)
    {
    }
}

void finish_scripts(
        scenario_42_controller& controller)
{
    for(int step = 0;
            step < 4096 &&
            controller.snapshot().phase ==
                    battle_scene_phase::script_blocked;
            ++step)
    {
        drain_presentations(controller);
        if(controller.snapshot().script.phase ==
                battle_presentation_script_phase::
                        wait_frames)
        {
            assert(controller.tick().success());
        }
        else
        {
            assert(controller.confirm().success());
        }
    }
    assert(controller.snapshot().phase !=
           battle_scene_phase::script_blocked);
}

const battle_scene_unit_view* active_enemy(
        const battle_scene_snapshot<12>& state)
{
    for(const battle_scene_unit_view& unit : state.units)
    {
        if(unit.active &&
                unit.side == battle_side::enemy)
        {
            return &unit;
        }
    }
    return nullptr;
}

void set_cursor(
        scenario_42_controller& controller,
        grid_point target)
{
    while(controller.snapshot().cursor.x != target.x)
    {
        const int direction =
                controller.snapshot().cursor.x <
                                target.x ?
                        1 :
                        -1;
        assert(controller.move_cursor(
                           direction, 0)
                       .success());
    }
    while(controller.snapshot().cursor.y != target.y)
    {
        const int direction =
                controller.snapshot().cursor.y <
                                target.y ?
                        1 :
                        -1;
        assert(controller.move_cursor(
                           0, direction)
                       .success());
    }
}

void select_command(
        scenario_42_controller& controller,
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

void complete_facing_and_defense(
        scenario_42_controller& controller)
{
    if(controller.snapshot().phase ==
            battle_scene_phase::facing_selection)
    {
        assert(controller.confirm().success());
    }
    if(controller.snapshot().phase ==
            battle_scene_phase::defense_decision)
    {
        assert(controller.confirm().success());
    }
}

void finish_enemy_side(
        scenario_42_controller& controller)
{
    for(int step = 0;
            step < 64 &&
            controller.snapshot().phase ==
                    battle_scene_phase::enemy_turn;
            ++step)
    {
        drain_presentations(controller);
        assert(controller.tick().success());
        finish_scripts(controller);
    }
    assert(controller.snapshot().phase !=
           battle_scene_phase::enemy_turn);
}

void wait_without_attacking(
        scenario_42_controller& controller,
        grid_point destination)
{
    assert(controller.snapshot().phase ==
           battle_scene_phase::unit_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);
    set_cursor(controller, destination);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    select_command(
            controller,
            battle_command_type::end_action);
    complete_facing_and_defense(controller);
    finish_enemy_side(controller);
    finish_scripts(controller);
}

bool move_toward_enemy(
        scenario_42_controller& controller,
        grid_point enemy)
{
    for(int distance = 1;
            distance < 9 + 22;
            ++distance)
    {
        for(int y = 0; y < 22; ++y)
        {
            for(int x = 0; x < 9; ++x)
            {
                const int candidate_distance =
                        (x > enemy.x ?
                                 x - enemy.x :
                                 enemy.x - x) +
                        (y > enemy.y ?
                                 y - enemy.y :
                                 enemy.y - y);
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

void select_action_five(
        scenario_42_controller& controller)
{
    select_command(
            controller,
            battle_command_type::ability);
    assert(controller.snapshot().phase ==
           battle_scene_phase::action_selection);
    for(int step = 0;
            step < 16 &&
            controller.snapshot().player
                            .selected_action_id != 5;
            ++step)
    {
        assert(controller.move_cursor(0, 1).success());
    }
    assert(controller.snapshot().player
                   .selected_action_kind ==
           battle_action_source_kind::active_action);
    assert(controller.snapshot().player
                   .selected_action_id == 5);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_selection);
}

void attack_training_dummy(
        scenario_42_controller& controller)
{
    const battle_scene_snapshot<12> before =
            controller.snapshot();
    const battle_scene_unit_view* enemy =
            active_enemy(before);
    assert(enemy);
    const grid_point enemy_position = enemy->position;

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);
    const bool in_range =
            move_toward_enemy(
                    controller, enemy_position);
    if(in_range)
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
    complete_facing_and_defense(controller);
    finish_enemy_side(controller);
    finish_scripts(controller);
}

character_progression_record scenario_42_naruto()
{
    character_progression_record result = {
        1,
        2,
        0,
        1,
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
    campaign.chapter_id = 42;
    assert(activate_battle_campaign_character(
            campaign, scenario_42_naruto()));
    assert(set_battle_campaign_party(
            campaign, { 1, 0, 0 }));

    const battle_campaign_stage_result stage =
            battle_campaign_stage_for(
                    campaign.chapter_id);
    assert(stage.success());
    assert(stage.stage);
    assert(stage.stage->battle_id == 42);
    assert(stage.stage->variant == 0);
    assert(stage.stage->next_scenario_id == 43);

    battle_campaign_scene_progression progression;
    assert(progression.begin(campaign) ==
           battle_campaign_error::none);
    battle_scenario_load_policy policy;
    policy.preserve_empty_unit_slots = true;
    assert(apply_battle_campaign_scene_policy(
                   campaign, policy) ==
           battle_campaign_error::none);

    scenario_42_controller controller;
    assert(controller.load(
                   battle_scenario_definitions[42],
                   battle_map_definitions[42],
                   battle_map_cells,
                   0,
                   policy,
                   battle_condition_variants[42][0],
                   42U,
                   progression.records(),
                   true,
                   battle_mission_rules_for(42, 0))
                   .success());
    assert(controller.start().success());
    finish_scripts(controller);

    const battle_scene_snapshot<12> initial =
            controller.snapshot();
    assert(initial.phase ==
           battle_scene_phase::unit_selection);
    assert(initial.round == 1);
    assert(initial.active_unit_count == 2);
    assert(initial.units[0].character_id == 1);
    assert(initial.units[0].position ==
           grid_point({ 2, 8 }));
    assert(initial.units[1].character_id == 35);
    assert(initial.units[1].position ==
           grid_point({ 6, 8 }));

    wait_without_attacking(
            controller, { 4, 7 });
    while(controller.snapshot().round <= 3)
    {
        const grid_point current =
                controller.snapshot().units[0].position;
        wait_without_attacking(controller, current);
    }
    for(int turn = 0;
            turn < 16 &&
            controller.snapshot().phase !=
                    battle_scene_phase::outcome;
            ++turn)
    {
        attack_training_dummy(controller);
    }
    const battle_scene_snapshot<12> outcome =
            controller.snapshot();
    assert(outcome.phase ==
           battle_scene_phase::outcome);
    assert(outcome.outcome ==
           battle_condition_outcome::win);
    assert(outcome.round > 3);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::result);
    const battle_result& result =
            controller.result_snapshot();
    assert(result.participant_count == 1);
    assert(result.participants[0].character_id == 1);
    assert(result.participants[0].mission_experience == 100);
    assert(result.participants[0].round_bonus_experience == 0);
    assert(result.participants[0].battle_experience == 10);
    assert(result.participants[0].total_experience == 110);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::training);
    assert(controller.cancel().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::complete);
    assert(controller.progression_roster()[0].level == 2);
    assert(controller.progression_roster()[0].experience == 110);
    assert(controller.progression_roster()[0].training_points == 1);

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
    assert(campaign.chapter_id == 43);
    assert(campaign.characters[1].progression.level == 2);
    assert(campaign.characters[1].progression.experience == 110);
    assert(campaign.characters[1]
                   .progression.training_points == 1);
    assert(campaign.characters[1]
                   .progression.primary_action_levels[6] == 0);
}
