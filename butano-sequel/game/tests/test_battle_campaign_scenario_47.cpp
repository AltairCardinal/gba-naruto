#include "konoha/battle_campaign_route.h"
#include "konoha/battle_campaign_scene_progression.h"
#include "konoha/battle_mission_rules.h"
#include "konoha/battle_scene_controller.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <array>
#include <cassert>
#include <cstddef>

using namespace konoha;

namespace
{

using controller_type =
        battle_scene_controller<12, 13, 21>;
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

const battle_scene_unit_view* unit_at_cursor(
        const snapshot_type& state)
{
    for(std::size_t index = 0;
            index < state.unit_count; ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(candidate.active &&
                candidate.position == state.cursor)
        {
            return &candidate;
        }
    }
    return nullptr;
}

const battle_scene_unit_view* closest_enemy(
        const snapshot_type& state,
        grid_point origin)
{
    const battle_scene_unit_view* result = nullptr;
    int best_distance = 13 + 21;
    for(std::size_t index = 0;
            index < state.unit_count; ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(! candidate.active ||
                candidate.side != battle_side::enemy)
        {
            continue;
        }
        const int dx =
                candidate.position.x > origin.x ?
                        candidate.position.x - origin.x :
                        origin.x - candidate.position.x;
        const int dy =
                candidate.position.y > origin.y ?
                        candidate.position.y - origin.y :
                        origin.y - candidate.position.y;
        const int candidate_distance = dx + dy;
        if(! result ||
                candidate_distance < best_distance)
        {
            result = &candidate;
            best_distance = candidate_distance;
        }
    }
    return result;
}

int active_enemy_count(const snapshot_type& state)
{
    int result = 0;
    for(std::size_t index = 0;
            index < state.unit_count; ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(candidate.active &&
                candidate.side == battle_side::enemy)
        {
            ++result;
        }
    }
    return result;
}

int distance(grid_point left, grid_point right)
{
    const int dx = left.x > right.x ?
            left.x - right.x :
            right.x - left.x;
    const int dy = left.y > right.y ?
            left.y - right.y :
            right.y - left.y;
    return dx + dy;
}

bool occupied(
        const snapshot_type& state,
        grid_point point,
        battle_unit_id moving_unit)
{
    for(std::size_t index = 0;
            index < state.unit_count; ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(candidate.active &&
                candidate.id != moving_unit &&
                candidate.position == point)
        {
            return true;
        }
    }
    return false;
}

bool player_can_enter(grid_point point)
{
    const battle_map_definition& map =
            battle_map_definitions[13];
    if(! map.contains(point.x, point.y))
    {
        return false;
    }
    return battle_map_cells[
                   map.cell_offset +
                   point.y * map.width +
                   point.x]
                   .terrain_class() == 0;
}

grid_point planned_move(
        const snapshot_type& state,
        const battle_scene_unit_view& actor,
        grid_point target,
        int target_distance)
{
    constexpr int width = 13;
    constexpr int height = 21;
    constexpr int cell_count = width * height;
    const auto point_index =
            [](grid_point point)
            {
                return point.y * width + point.x;
            };
    const auto index_point =
            [](int index)
            {
                return grid_point({
                    index % width,
                    index / width,
                });
            };

    std::array<int, cell_count> parents;
    std::array<int, cell_count> costs;
    std::array<int, cell_count> queue = {};
    parents.fill(-2);
    costs.fill(-1);
    const int start = point_index(actor.position);
    parents[static_cast<std::size_t>(start)] = -1;
    costs[static_cast<std::size_t>(start)] = 0;
    int queue_begin = 0;
    int queue_end = 0;
    queue[static_cast<std::size_t>(queue_end++)] = start;
    int found = -1;
    constexpr std::array<grid_point, 4> directions = {{
        { -1, 0 },
        { 0, -1 },
        { 1, 0 },
        { 0, 1 },
    }};

    while(queue_begin < queue_end)
    {
        const int current =
                queue[static_cast<std::size_t>(
                        queue_begin++)];
        const grid_point point = index_point(current);
        if(distance(point, target) == target_distance)
        {
            found = current;
            break;
        }
        for(const grid_point direction : directions)
        {
            const grid_point next = {
                point.x + direction.x,
                point.y + direction.y,
            };
            if(! player_can_enter(next) ||
                    occupied(state, next, actor.id))
            {
                continue;
            }
            const int next_index = point_index(next);
            if(parents[
                       static_cast<std::size_t>(
                               next_index)] != -2)
            {
                continue;
            }
            parents[static_cast<std::size_t>(next_index)] =
                    current;
            costs[static_cast<std::size_t>(next_index)] =
                    costs[static_cast<std::size_t>(current)] +
                    1;
            queue[static_cast<std::size_t>(queue_end++)] =
                    next_index;
        }
    }

    if(found < 0)
    {
        return actor.position;
    }
    int selected = found;
    while(costs[static_cast<std::size_t>(selected)] >
            actor.movement)
    {
        selected =
                parents[static_cast<std::size_t>(selected)];
    }
    return index_point(selected);
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

void drain_presentations(controller_type& controller)
{
    while(controller.take_presentation_event().valid)
    {
    }
}

void finish_scripts(controller_type& controller)
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

void select_command(
        controller_type& controller,
        battle_command_type command)
{
    for(int step = 0;
            step < 10 &&
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

void finish_turn(controller_type& controller)
{
    drain_presentations(controller);
    finish_scripts(controller);
    if(controller.snapshot().phase ==
            battle_scene_phase::outcome)
    {
        return;
    }
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
    finish_scripts(controller);
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
    drain_presentations(controller);
    finish_scripts(controller);
    assert(controller.snapshot().phase !=
           battle_scene_phase::enemy_turn);
}

void move_actor(
        controller_type& controller,
        grid_point destination,
        int target_distance)
{
    const snapshot_type before = controller.snapshot();
    const battle_scene_unit_view* actor =
            unit_at_cursor(before);
    assert(actor);
    const grid_point selected =
            planned_move(
                    before,
                    *actor,
                    destination,
                    target_distance);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);
    set_cursor(controller, selected);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::command_selection);
}

bool select_active_action(
        controller_type& controller,
        ability_id action)
{
    select_command(
            controller,
            battle_command_type::ability);
    for(int step = 0; step < 24; ++step)
    {
        const battle_player_action_flow_snapshot& state =
                controller.snapshot().player;
        const battle_action_menu_view& selected =
                state.action_entries[
                        static_cast<std::size_t>(
                                state.action_index)];
        if(selected.kind ==
                        battle_action_source_kind::
                                active_action &&
                selected.action_id == action)
        {
            if(! selected.selectable())
            {
                assert(controller.cancel().success());
                return false;
            }
            assert(controller.confirm().success());
            if(controller.snapshot().phase ==
                    battle_scene_phase::
                            combination_decision)
            {
                assert(controller.move_cursor(0, 1).success());
                assert(controller.confirm().success());
            }
            assert(controller.snapshot().phase ==
                   battle_scene_phase::target_selection);
            return true;
        }
        assert(controller.move_cursor(0, 1).success());
    }
    assert(false);
    return false;
}

bool create_shadow_clone(
        controller_type& controller,
        const battle_scene_unit_view& actor)
{
    if(actor.character_id != 1 ||
            actor.chakra < 3 ||
            ! select_active_action(controller, 7))
    {
        return false;
    }
    constexpr std::array<grid_point, 4> directions = {{
        { -1, 0 },
        { 0, -1 },
        { 1, 0 },
        { 0, 1 },
    }};
    const snapshot_type state = controller.snapshot();
    for(const grid_point direction : directions)
    {
        const grid_point target = {
            actor.position.x + direction.x,
            actor.position.y + direction.y,
        };
        if(player_can_enter(target) &&
                ! occupied(state, target, actor.id))
        {
            set_cursor(controller, target);
            if(controller.confirm().success())
            {
                bool found_clone = false;
                const snapshot_type after =
                        controller.snapshot();
                for(std::size_t index = 0;
                        index < after.unit_count;
                        ++index)
                {
                    const battle_scene_unit_view& candidate =
                            after.units[index];
                    if(candidate.active &&
                            candidate.side ==
                                    battle_side::player &&
                            candidate.character_id == 1 &&
                            candidate.summoner == actor.id)
                    {
                        found_clone = true;
                        break;
                    }
                }
                assert(found_clone);
                return true;
            }
        }
    }
    assert(false);
    return false;
}

character_progression_record progression(
        std::uint8_t character_id,
        int level,
        int experience,
        int training_points)
{
    character_progression_record result = {
        character_id,
        static_cast<std::uint8_t>(level),
        static_cast<std::uint16_t>(experience),
        static_cast<std::uint8_t>(training_points),
        true,
    };
    assert(initialize_character_action_progression(
            result,
            unit_definitions[character_id]));
    return result;
}

battle_campaign_state campaign_after_scenario_46()
{
    battle_campaign_state result =
            empty_battle_campaign();
    result.chapter_id = 47;
    assert(activate_battle_campaign_character(
            result,
            progression(1, 4, 180, 3)));
    assert(activate_battle_campaign_character(
            result,
            progression(2, 3, 185, 2)));
    assert(activate_battle_campaign_character(
            result,
            progression(3, 4, 35, 3)));
    assert(set_battle_campaign_party(
            result, { 1, 2, 3 }));
    assert(prepare_battle_campaign_stage(result)
                   .success());
    return result;
}

}

int main()
{
    const battle_campaign_stage_result stage =
            battle_campaign_stage_for(47);
    assert(stage.success());
    assert(stage.stage);
    assert(stage.stage->battle_id == 13);
    assert(stage.stage->variant == 0);
    assert(stage.stage->next_scenario_id == 49);

    battle_campaign_state campaign =
            campaign_after_scenario_46();
    battle_campaign_scene_progression progression_state;
    assert(progression_state.begin(campaign) ==
           battle_campaign_error::none);
    battle_scenario_load_policy policy;
    policy.preserve_empty_unit_slots = true;
    assert(apply_battle_campaign_scene_policy(
                   campaign, policy) ==
           battle_campaign_error::none);

    controller_type controller;
    assert(controller.load(
                   battle_scenario_definitions[13],
                   battle_map_definitions[13],
                   battle_map_cells,
                   0,
                   policy,
                   battle_condition_variants[13][0],
                   47U,
                   progression_state.records(),
                   true,
                   battle_mission_rules_for(13, 0))
                   .success());
    assert(controller.start().success());
    finish_scripts(controller);

    const snapshot_type initial = controller.snapshot();
    assert(initial.phase ==
           battle_scene_phase::unit_selection);
    assert(initial.round == 1);
    assert(initial.active_unit_count == 8);
    assert(unit(initial, 1).character_id == 1);
    assert(unit(initial, 1).position ==
           grid_point({ 6, 3 }));
    assert(unit(initial, 2).character_id == 2);
    assert(unit(initial, 2).position ==
           grid_point({ 4, 3 }));
    assert(unit(initial, 3).character_id == 3);
    assert(unit(initial, 3).position ==
           grid_point({ 8, 3 }));
    constexpr std::array<grid_point, 5>
            enemy_positions = {{
                { 1, 10 },
                { 3, 14 },
                { 6, 16 },
                { 9, 14 },
                { 11, 10 },
            }};
    for(battle_unit_id id = 4; id <= 8; ++id)
    {
        assert(unit(initial, id).character_id == 33);
        assert(unit(initial, id).position ==
               enemy_positions[
                       static_cast<std::size_t>(id - 4)]);
        assert(unit(initial, id).hp == 80);
    }

    bool rested = false;
    bool created_clone = false;
    int defeated_enemies = 0;
    int previous_enemy_count = 5;
    for(int turn = 0;
            turn < 320 &&
            controller.snapshot().phase !=
                    battle_scene_phase::outcome;
            ++turn)
    {
        finish_scripts(controller);
        const snapshot_type before =
                controller.snapshot();
        assert(before.phase ==
               battle_scene_phase::unit_selection);
        const battle_scene_unit_view* actor =
                unit_at_cursor(before);
        assert(actor);
        assert(actor->active);
        assert(actor->side == battle_side::player);
        const battle_scene_unit_view* enemy =
                closest_enemy(before, actor->position);
        assert(enemy);

        if(! rested &&
                before.round >= 4 &&
                actor->hp < actor->max_hp)
        {
            const int hp_before = actor->hp;
            move_actor(
                    controller,
                    actor->position,
                    0);
            select_command(
                    controller,
                    battle_command_type::rest);
            assert(controller.snapshot().phase ==
                   battle_scene_phase::
                           rest_confirmation);
            assert(controller.confirm().success());
            assert(unit(controller.snapshot(), actor->id).hp >
                   hp_before);
            rested = true;
            finish_turn(controller);
            continue;
        }

        const grid_point enemy_position =
                enemy->position;
        move_actor(
                controller,
                enemy_position,
                1);
        const snapshot_type after_move =
                controller.snapshot();
        const battle_scene_unit_view& moved_actor =
                unit(after_move, actor->id);
        if(! created_clone &&
                before.round >= 6 &&
                moved_actor.character_id == 1 &&
                create_shadow_clone(
                        controller, moved_actor))
        {
            created_clone = true;
        }
        else if(distance(
                        moved_actor.position,
                        enemy_position) == 1 &&
                select_active_action(controller, 5))
        {
            set_cursor(controller, enemy_position);
            assert(controller.confirm().success());
        }
        else
        {
            select_command(
                    controller,
                    battle_command_type::end_action);
        }
        finish_turn(controller);

        const int current_enemy_count =
                active_enemy_count(controller.snapshot());
        assert(current_enemy_count <=
               previous_enemy_count);
        defeated_enemies +=
                previous_enemy_count -
                current_enemy_count;
        previous_enemy_count = current_enemy_count;
    }

    assert(rested);
    assert(created_clone);
    assert(defeated_enemies == 5);
    const snapshot_type outcome = controller.snapshot();
    assert(outcome.phase ==
           battle_scene_phase::outcome);
    assert(outcome.outcome ==
           battle_condition_outcome::win);
    for(battle_unit_id id = 4; id <= 8; ++id)
    {
        assert(! unit(outcome, id).active);
    }

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::result);
    const battle_result& result =
            controller.result_snapshot();
    assert(result.participant_count == 3);
    int battle_experience = 0;
    for(std::size_t index = 0;
            index < result.participant_count;
            ++index)
    {
        assert(result.participants[index]
                       .mission_experience == 125);
        assert(result.participants[index]
                       .round_bonus_experience == 0);
        battle_experience +=
                result.participants[index]
                        .battle_experience;
    }
    assert(battle_experience == 375);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::level_up);
    assert(controller.progression_roster()[0].level == 5);
    assert(controller.progression_roster()[1].level == 5);
    assert(controller.progression_roster()[2].level == 5);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::training);
    assert(controller.cancel().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::complete);

    progression_state.records() =
            controller.progression_roster();
    progression_state.equipped_tools() =
            controller.equipped_tools_roster();
    assert(progression_state.commit(campaign) ==
           battle_campaign_error::none);
    assert(advance_battle_campaign_stage(
                   campaign,
                   battle_runtime_scene_exit::victory)
                   .success());
    assert(campaign.chapter_id == 49);
}
