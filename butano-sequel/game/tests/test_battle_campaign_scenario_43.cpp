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

using scenario_43_controller =
        battle_scene_controller<12, 9, 22>;
using scenario_43_snapshot =
        battle_scene_snapshot<12>;

void drain_presentations(
        scenario_43_controller& controller)
{
    while(controller.take_presentation_event().valid)
    {
    }
}

void finish_scripts(
        scenario_43_controller& controller)
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

const battle_scene_unit_view& unit(
        const scenario_43_snapshot& state,
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

const battle_scene_unit_view* nearest_enemy(
        const scenario_43_snapshot& state,
        grid_point origin)
{
    const battle_scene_unit_view* result = nullptr;
    int result_distance = 9 + 22;
    for(const battle_scene_unit_view& candidate :
            state.units)
    {
        if(! candidate.active ||
                candidate.side != battle_side::enemy)
        {
            continue;
        }
        const int distance =
                (candidate.position.x > origin.x ?
                         candidate.position.x - origin.x :
                         origin.x - candidate.position.x) +
                (candidate.position.y > origin.y ?
                         candidate.position.y - origin.y :
                         origin.y - candidate.position.y);
        if(distance < result_distance)
        {
            result = &candidate;
            result_distance = distance;
        }
    }
    return result;
}

void set_cursor(
        scenario_43_controller& controller,
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
        scenario_43_controller& controller,
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
        scenario_43_controller& controller)
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
        scenario_43_controller& controller)
{
    for(int step = 0;
            step < 128 &&
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

void finish_side_transitions(
        scenario_43_controller& controller)
{
    complete_facing_and_defense(controller);
    finish_scripts(controller);
    finish_enemy_side(controller);
    finish_scripts(controller);
}

void create_shadow_clone(
        scenario_43_controller& controller)
{
    const scenario_43_snapshot before =
            controller.snapshot();
    assert(before.phase ==
           battle_scene_phase::unit_selection);
    assert(before.selected_unit == 1);
    assert(unit(before, 1).chakra == 5);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    select_command(
            controller,
            battle_command_type::ability);
    for(int step = 0;
            step < 16 &&
            controller.snapshot().player
                            .selected_action_id != 7;
            ++step)
    {
        assert(controller.move_cursor(0, 1).success());
    }
    assert(controller.snapshot().player
                   .selected_action_id == 7);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_selection);
    set_cursor(controller, { 4, 16 });
    assert(controller.confirm().success());
    drain_presentations(controller);

    const scenario_43_snapshot after =
            controller.snapshot();
    assert(unit(after, 1).chakra == 2);
    assert(unit(after, 5).active);
    assert(unit(after, 5).side ==
           battle_side::player);
    assert(unit(after, 5).character_id == 1);
    assert(unit(after, 5).summoner == 1);
    assert(unit(after, 5).position ==
           grid_point({ 4, 16 }));
    finish_side_transitions(controller);
}

void end_selected_action(
        scenario_43_controller& controller)
{
    const scenario_43_snapshot before =
            controller.snapshot();
    assert(before.phase ==
           battle_scene_phase::unit_selection);
    const battle_scene_unit_view& selected =
            unit(before, before.selected_unit);
    assert(selected.active);
    assert(selected.side == battle_side::player);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);
    set_cursor(controller, selected.position);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    select_command(
            controller,
            battle_command_type::end_action);
    finish_side_transitions(controller);
}

bool move_adjacent_to_enemy(
        scenario_43_controller& controller,
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
        scenario_43_controller& controller)
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

void attack_with_selected_unit(
        scenario_43_controller& controller)
{
    const scenario_43_snapshot before =
            controller.snapshot();
    assert(before.phase ==
           battle_scene_phase::unit_selection);
    const battle_scene_unit_view& selected =
            unit(before, before.selected_unit);
    const battle_scene_unit_view* enemy =
            nearest_enemy(before, selected.position);
    assert(enemy);
    const grid_point enemy_position =
            enemy->position;

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);
    if(move_adjacent_to_enemy(
               controller, enemy_position))
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
    finish_side_transitions(controller);
}

character_progression_record scenario_43_naruto()
{
    character_progression_record result = {
        1,
        2,
        110,
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
    campaign.chapter_id = 43;
    assert(activate_battle_campaign_character(
            campaign, scenario_43_naruto()));
    assert(set_battle_campaign_party(
            campaign, { 1, 0, 0 }));

    const battle_campaign_stage_result stage =
            battle_campaign_stage_for(
                    campaign.chapter_id);
    assert(stage.success());
    assert(stage.stage);
    assert(stage.stage->battle_id == 43);
    assert(stage.stage->variant == 0);
    assert(stage.stage->next_scenario_id == 44);

    battle_campaign_scene_progression progression;
    assert(progression.begin(campaign) ==
           battle_campaign_error::none);
    battle_scenario_load_policy policy;
    policy.preserve_empty_unit_slots = true;
    assert(apply_battle_campaign_scene_policy(
                   campaign, policy) ==
           battle_campaign_error::none);

    scenario_43_controller controller;
    assert(controller.load(
                   battle_scenario_definitions[43],
                   battle_map_definitions[43],
                   battle_map_cells,
                   0,
                   policy,
                   battle_condition_variants[43][0],
                   43U,
                   progression.records(),
                   true,
                   battle_mission_rules_for(43, 0))
                   .success());
    assert(controller.start().success());
    finish_scripts(controller);

    const scenario_43_snapshot initial =
            controller.snapshot();
    assert(initial.phase ==
           battle_scene_phase::unit_selection);
    assert(initial.round == 1);
    assert(initial.active_unit_count == 4);
    assert(unit(initial, 1).position ==
           grid_point({ 4, 17 }));
    assert(unit(initial, 1).level == 2);
    assert(unit(initial, 1).hp == 94);
    assert(unit(initial, 2).position ==
           grid_point({ 2, 11 }));
    assert(unit(initial, 2).hp == 50);
    assert(unit(initial, 3).position ==
           grid_point({ 4, 10 }));
    assert(unit(initial, 3).hp == 50);
    assert(unit(initial, 4).position ==
           grid_point({ 6, 11 }));
    assert(unit(initial, 4).hp == 50);
    assert(! unit(initial, 5).active);

    create_shadow_clone(controller);
    assert(controller.snapshot().round == 2);
    assert(controller.snapshot().active_unit_count == 5);

    while(controller.snapshot().round <= 5 &&
            controller.snapshot().phase !=
                    battle_scene_phase::outcome)
    {
        assert(controller.snapshot().phase ==
               battle_scene_phase::unit_selection);
        end_selected_action(controller);
    }
    assert(controller.snapshot().round > 5);

    for(int turn = 0;
            turn < 96 &&
            controller.snapshot().phase !=
                    battle_scene_phase::outcome;
            ++turn)
    {
        assert(controller.snapshot().phase ==
               battle_scene_phase::unit_selection);
        attack_with_selected_unit(controller);
    }

    const scenario_43_snapshot outcome =
            controller.snapshot();
    assert(outcome.phase ==
           battle_scene_phase::outcome);
    assert(outcome.outcome ==
           battle_condition_outcome::win);
    assert(outcome.round > 5);
    assert(! unit(outcome, 2).active);
    assert(! unit(outcome, 3).active);
    assert(! unit(outcome, 4).active);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::result);
    const battle_result& result =
            controller.result_snapshot();
    assert(result.participant_count == 1);
    assert(result.participants[0].character_id == 1);
    assert(result.participants[0].mission_experience == 125);
    assert(result.participants[0].round_bonus_experience == 0);
    assert(result.participants[0].battle_experience == 30);
    assert(result.participants[0].total_experience == 155);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::level_up);
    assert(controller.progression_roster()[0].level == 3);
    assert(controller.progression_roster()[0].experience == 0);
    assert(controller.progression_roster()[0].training_points == 2);
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
    assert(campaign.chapter_id == 44);
    assert(campaign.characters[1].progression.level == 3);
    assert(campaign.characters[1].progression.experience == 0);
    assert(campaign.characters[1]
                   .progression.training_points == 2);

    const battle_campaign_route_result prepared =
            prepare_battle_campaign_stage(campaign);
    assert(prepared.success());
    assert(! prepared.changed);
    assert(campaign.party ==
           (std::array<std::uint8_t, 3>{ 1, 2, 3 }));
    assert(campaign.characters[1].progression.level == 3);
    assert(campaign.characters[2].progression.active);
    assert(campaign.characters[3].progression.active);
}
