#include "konoha/battle_campaign_route.h"
#include "konoha/battle_campaign_scene_progression.h"
#include "konoha/battle_mission_rules.h"
#include "konoha/battle_scene_controller.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <array>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstddef>

using namespace konoha;

namespace
{

using controller_type =
        battle_scene_controller<12, 15, 19>;
using snapshot_type = battle_scene_snapshot<12>;

void trace_scenario_49_state(
        const char* label,
        const snapshot_type& state)
{
    if(! std::getenv("KONOHA_TRACE_SCENARIO_49"))
    {
        return;
    }
    std::printf(
            "%s round=%d phase=%d selected=%d",
            label,
            state.round,
            static_cast<int>(state.phase),
            state.selected_unit);
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        const battle_scene_unit_view& unit =
                state.units[index];
        std::printf(
                " u%d=%d,%d,%d,%d,%d",
                unit.id,
                unit.active ? 1 : 0,
                unit.hp,
                unit.chakra,
                unit.position.x,
                unit.position.y);
    }
    std::printf("\n");
    std::fflush(stdout);
}

const battle_scene_unit_view& unit(
        const snapshot_type& state,
        battle_unit_id id)
{
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
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
            index < state.unit_count;
            ++index)
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

const battle_scene_unit_view* active_unit(
        const snapshot_type& state,
        battle_unit_id id)
{
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        if(state.units[index].id == id &&
                state.units[index].active)
        {
            return &state.units[index];
        }
    }
    return nullptr;
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

int active_enemy_count(const snapshot_type& state)
{
    int result = 0;
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        if(state.units[index].active &&
                state.units[index].side ==
                        battle_side::enemy)
        {
            ++result;
        }
    }
    return result;
}

const battle_scene_unit_view* weakest_enemy(
        const snapshot_type& state,
        const battle_scene_unit_view& actor,
        int action_range)
{
    const battle_scene_unit_view* result = nullptr;
    int best_hp = 0;
    int best_distance = 0;
    bool best_reachable = false;
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(! candidate.active ||
                candidate.side != battle_side::enemy)
        {
            continue;
        }
        const int candidate_distance =
                distance(actor.position, candidate.position);
        const bool candidate_reachable =
                candidate_distance <=
                        actor.movement + action_range;
        if(! result ||
                (candidate_reachable &&
                 ! best_reachable) ||
                (candidate_reachable ==
                         best_reachable &&
                 ((candidate_reachable &&
                   (candidate.hp < best_hp ||
                    (candidate.hp == best_hp &&
                     candidate_distance <
                             best_distance))) ||
                  (! candidate_reachable &&
                   (candidate_distance <
                            best_distance ||
                    (candidate_distance ==
                             best_distance &&
                     candidate.hp < best_hp))))))
        {
            result = &candidate;
            best_hp = candidate.hp;
            best_distance = candidate_distance;
            best_reachable = candidate_reachable;
        }
    }
    return result;
}

bool occupied(
        const snapshot_type& state,
        grid_point point,
        battle_unit_id moving_unit)
{
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
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
            battle_map_definitions[14];
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
    constexpr int width = 15;
    constexpr int height = 19;
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
            if(parents[static_cast<std::size_t>(
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
    if(controller.snapshot().phase ==
            battle_scene_phase::move_selection)
    {
        constexpr int width = 15;
        constexpr int height = 19;
        constexpr int cell_count = width * height;
        const snapshot_type state = controller.snapshot();
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
        std::array<int, cell_count> queue = {};
        parents.fill(-2);
        const int start = point_index(state.cursor);
        const int finish = point_index(target);
        parents[static_cast<std::size_t>(start)] = -1;
        int queue_begin = 0;
        int queue_end = 0;
        queue[static_cast<std::size_t>(queue_end++)] =
                start;
        constexpr std::array<grid_point, 4>
                directions = {{
            { -1, 0 },
            { 0, -1 },
            { 1, 0 },
            { 0, 1 },
        }};
        while(queue_begin < queue_end &&
                parents[static_cast<std::size_t>(
                                finish)] == -2)
        {
            const int current =
                    queue[static_cast<std::size_t>(
                            queue_begin++)];
            const grid_point point = index_point(current);
            for(const grid_point direction : directions)
            {
                const grid_point next = {
                    point.x + direction.x,
                    point.y + direction.y,
                };
                if(! player_can_enter(next) ||
                        occupied(
                                state,
                                next,
                                state.selected_unit))
                {
                    continue;
                }
                const int next_index = point_index(next);
                if(parents[static_cast<std::size_t>(
                                   next_index)] != -2)
                {
                    continue;
                }
                parents[static_cast<std::size_t>(
                        next_index)] = current;
                queue[static_cast<std::size_t>(
                        queue_end++)] = next_index;
            }
        }
        assert(parents[static_cast<std::size_t>(
                           finish)] != -2);
        std::array<grid_point, cell_count> reverse_path;
        int path_size = 0;
        for(int current = finish;
                current != start;
                current = parents[static_cast<std::size_t>(
                        current)])
        {
            reverse_path[static_cast<std::size_t>(
                    path_size++)] = index_point(current);
        }
        for(int index = path_size - 1; index >= 0; --index)
        {
            const grid_point current =
                    controller.snapshot().cursor;
            const grid_point next =
                    reverse_path[static_cast<std::size_t>(
                            index)];
            assert(controller.move_cursor(
                               next.x - current.x,
                               next.y - current.y)
                           .success());
        }
        assert(controller.snapshot().cursor == target);
        return;
    }

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
            battle_scene_phase::end_confirmation)
    {
        assert(controller.snapshot().end_confirmation_yes);
        assert(controller.confirm().success());
    }
    if(controller.snapshot().phase ==
            battle_scene_phase::facing_selection)
    {
        assert(controller.confirm().success());
    }
    if(controller.snapshot().phase ==
            battle_scene_phase::defense_decision)
    {
        assert(controller.snapshot().defense_confirmation_yes);
        assert(controller.move_cursor(0, 1).success());
        assert(! controller.snapshot().defense_confirmation_yes);
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
    const grid_point selected = planned_move(
            before,
            *actor,
            destination,
            target_distance);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    assert(controller.snapshot().player.selected_command == battle_command_type::move);
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
        const snapshot_type snapshot =
                controller.snapshot();
        const battle_player_action_flow_snapshot& state =
                snapshot.player;
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

void confirm_target(
        controller_type& controller,
        grid_point target)
{
    set_cursor(controller, target);
    const snapshot_type before = controller.snapshot();
    assert(before.selected_unit != no_battle_unit);
    const battle_scene_unit_view& actor_before =
            unit(before, before.selected_unit);
    const battle_scene_unit_view* target_before =
            unit_at_cursor(before);
    assert(target_before);
    const battle_unit_id target_id = target_before->id;

    assert(controller.confirm().success());

    const snapshot_type preview = controller.snapshot();
    assert(preview.phase ==
           battle_scene_phase::target_preview);
    assert(preview.overlay_width > 0);
    assert(preview.overlay_height > 0);
    assert(preview.range_overlay_rows ==
           before.range_overlay_rows);
    assert(preview.target_overlay_rows ==
           before.target_overlay_rows);
    assert(! controller.presentation_pending());
    assert(unit(preview, actor_before.id) == actor_before);
    assert(unit(preview, target_id) == *target_before);

    assert(controller.confirm().success());

    const snapshot_type confirmation = controller.snapshot();
    assert(confirmation.phase ==
           battle_scene_phase::target_confirmation);
    assert(confirmation.target_confirmation_yes);
    assert(confirmation.overlay_width ==
           preview.overlay_width);
    assert(confirmation.overlay_height ==
           preview.overlay_height);
    assert(confirmation.range_overlay_rows ==
           preview.range_overlay_rows);
    assert(confirmation.target_overlay_rows ==
           preview.target_overlay_rows);
    assert(! controller.presentation_pending());
    assert(unit(confirmation, actor_before.id) == actor_before);
    assert(unit(confirmation, target_id) == *target_before);

    assert(controller.confirm().success());
}

void end_actor(
        controller_type& controller,
        grid_point destination)
{
    move_actor(controller, destination, 0);
    select_command(
            controller,
            battle_command_type::end_action);
    finish_turn(controller);
}

void replenish_actor(
        controller_type& controller,
        grid_point position)
{
    assert(controller.snapshot().cursor == position);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase == battle_scene_phase::command_selection);
    select_command(
            controller,
            battle_command_type::replenish_chakra);
    const int maximum_amount =
            controller.snapshot()
                    .player.resource_preview.maximum_amount;
    while(controller.snapshot()
                  .player.resource_preview.amount <
            maximum_amount)
    {
        assert(controller.move_cursor(0, 1).success());
    }
    assert(controller.confirm().success());
    finish_turn(controller);
}

character_progression_record progression(
        std::uint8_t character_id,
        int level,
        int experience,
        int training_points)
{
    character_progression_record result = {
        character_id,
        level,
        experience,
        training_points,
        true,
    };
    assert(initialize_character_action_progression(
            result,
            unit_definitions[character_id]));
    return result;
}

battle_campaign_state campaign_after_scenario_47()
{
    battle_campaign_state result =
            empty_battle_campaign();
    result.chapter_id = 49;
    assert(activate_battle_campaign_character(
            result,
            progression(1, 5, 85, 4)));
    assert(activate_battle_campaign_character(
            result,
            progression(2, 4, 150, 3)));
    assert(activate_battle_campaign_character(
            result,
            progression(3, 5, 115, 4)));
    assert(set_battle_campaign_party(
            result,
            { 1, 2, 3 }));
    assert(prepare_battle_campaign_stage(result)
                   .success());
    return result;
}

controller_type load_controller(
        const battle_campaign_scene_progression&
                progression_state)
{
    battle_scenario_load_policy policy;
    policy.preserve_empty_unit_slots = true;
    battle_campaign_state campaign =
            campaign_after_scenario_47();
    assert(apply_battle_campaign_scene_policy(
                   campaign,
                   policy) ==
           battle_campaign_error::none);
    controller_type controller;
    assert(controller.load(
                   battle_scenario_definitions[14],
                   battle_map_definitions[14],
                   battle_map_cells,
                   0,
                   policy,
                   battle_condition_variants[14][0],
                   49U,
                   progression_state.records(),
                   true,
                   battle_mission_rules_for(14, 0))
                   .success());
    assert(controller.start().success());
    finish_scripts(controller);
    assert(controller.tick().success()); // opening escort precedes player input
    drain_presentations(controller);
    return controller;
}

}

int main()
{
    const battle_mission_rules mission_rules =
            battle_mission_rules_for(14, 0);
    assert(mission_rules.confirm_targets);

    const battle_campaign_stage_result stage =
            battle_campaign_stage_for(49);
    assert(stage.success());
    assert(stage.stage);
    assert(stage.stage->battle_id == 14);
    assert(stage.stage->variant == 0);
    assert(stage.stage->next_scenario_id == 50);

    battle_campaign_state campaign =
            campaign_after_scenario_47();
    battle_campaign_scene_progression progression_state;
    assert(progression_state.begin(campaign) ==
           battle_campaign_error::none);

    assert(battle_reward_record_for_scenario(14, 0) == 39);
    const battle_reward_definition& recorded_reward =
            battle_reward_definitions[39];
    assert(recorded_reward.mission_experience == 125);
    assert(recorded_reward.round_bonus_experience == 75);
    assert(recorded_reward.round_limit == 8);
    const level_settlement recorded_naruto =
            settle_character_progression(
                    progression(1, 5, 85, 4),
                    100 + 125 + 75);
    const level_settlement recorded_sasuke =
            settle_character_progression(
                    progression(2, 4, 150, 3),
                    150 + 125 + 75);
    const level_settlement recorded_sakura =
            settle_character_progression(
                    progression(3, 5, 115, 4),
                    125 + 75);
    assert(recorded_naruto.after.level == 6);
    assert(recorded_naruto.after.experience == 75);
    assert(recorded_naruto.after.training_points == 5);
    assert(recorded_sasuke.after.level == 6);
    assert(recorded_sasuke.after.experience == 35);
    assert(recorded_sasuke.after.training_points == 5);
    assert(recorded_sakura.after.level == 6);
    assert(recorded_sakura.after.experience == 105);
    assert(recorded_sakura.after.training_points == 5);

    controller_type failure_controller =
            load_controller(progression_state);
    const snapshot_type failure_initial =
            failure_controller.snapshot();
    const grid_point escort_initial_position =
            unit(failure_initial, 4).position;
    const int escort_initial_hp =
            unit(failure_initial, 4).hp;
    bool escort_moved = false;
    bool escort_damaged = false;
    bool escort_reached_observed_waypoint = false;
    for(int turn = 0;
            turn < 120 &&
            failure_controller.snapshot().phase !=
                    battle_scene_phase::outcome;
            ++turn)
    {
        const snapshot_type before =
                failure_controller.snapshot();
        trace_scenario_49_state("failure-loop", before);
        assert(before.phase ==
               battle_scene_phase::unit_selection);
        const battle_scene_unit_view* actor =
                unit_at_cursor(before);
        assert(actor);
        assert(actor->control ==
               battle_control::player);
        end_actor(
                failure_controller,
                actor->position);
        const snapshot_type after =
                failure_controller.snapshot();
        escort_moved =
                escort_moved ||
                unit(after, 4).position !=
                        escort_initial_position;
        escort_damaged =
                escort_damaged ||
                unit(after, 4).hp <
                        escort_initial_hp;
        escort_reached_observed_waypoint =
                escort_reached_observed_waypoint ||
                unit(after, 4).position ==
                        grid_point({ 12, 3 });
    }
    const snapshot_type failure_outcome =
            failure_controller.snapshot();
    assert(escort_moved);
    assert(escort_damaged);
    assert(escort_reached_observed_waypoint);
    assert(failure_outcome.phase ==
           battle_scene_phase::outcome);
    assert(failure_outcome.outcome ==
           battle_condition_outcome::loss);
    assert(! unit(failure_outcome, 4).active);
    assert(unit(failure_outcome, 1).active ||
           unit(failure_outcome, 2).active ||
           unit(failure_outcome, 3).active);

    controller_type controller =
            load_controller(progression_state);
    const snapshot_type initial = controller.snapshot();
    trace_scenario_49_state("initial", initial);
    assert(initial.phase ==
           battle_scene_phase::unit_selection);
    assert(initial.round == 1);
    assert(initial.active_unit_count == 9);
    constexpr std::array<grid_point, 9> positions = {{
        { 11, 6 },
        { 10, 14 },
        { 8, 14 },
        { 10, 7 },
        { 3, 4 },
        { 4, 8 },
        { 3, 11 },
        { 6, 6 },
        { 5, 13 },
    }};
    for(battle_unit_id id = 1; id <= 9; ++id)
    {
        assert(unit(initial, id).position ==
               positions[static_cast<std::size_t>(id - 1)]);
    }
    assert(unit(initial, 1).character_id == 1);
    assert(unit(initial, 1).level == 5);
    assert(unit(initial, 1).hp == 138);
    assert(unit(initial, 2).character_id == 2);
    assert(unit(initial, 2).level == 4);
    assert(unit(initial, 2).hp == 104);
    assert(unit(initial, 3).character_id == 3);
    assert(unit(initial, 3).level == 5);
    assert(unit(initial, 3).hp == 110);
    assert(unit(initial, 4).character_id == 30);
    assert(unit(initial, 4).level == 3);
    assert(unit(initial, 4).hp == 40);
    assert(unit(initial, 4).control ==
           battle_control::ai);
    for(battle_unit_id id = 5; id <= 9; ++id)
    {
        assert(unit(initial, id).character_id == 55);
        assert(unit(initial, id).level == 5);
        assert(unit(initial, id).hp == 25);
        assert(unit(initial, id).control ==
               battle_control::ai);
    }
    for(battle_unit_id id = 10; id <= 12; ++id)
    {
        const battle_scene_unit_view& reserve =
                unit(initial, id);
        assert(! reserve.active);
        assert(reserve.character_id == 0);
        assert(reserve.side == battle_side::player);
        assert(reserve.control == battle_control::player);
        assert(reserve.position == grid_point{});
        assert(reserve.hp == 0);
        assert(reserve.max_hp == 0);
        assert(reserve.chakra == 0);
        assert(reserve.max_chakra == 0);
        assert(reserve.movement == 0);
    }

    int naruto_kills = 0;
    int sasuke_kills = 0;
    int sakura_kills = 0;
    int defeated_enemies = 0;
    int previous_enemy_count = 5;
    bool used_fireball = false;
    bool replenished_sasuke = false;
    bool escort_took_damage = false;
    for(int turn = 0;
            turn < 120 &&
            controller.snapshot().phase !=
                    battle_scene_phase::outcome;
            ++turn)
    {
        finish_scripts(controller);
        const snapshot_type before = controller.snapshot();
        assert(before.phase ==
               battle_scene_phase::unit_selection);
        const battle_scene_unit_view* actor =
                unit_at_cursor(before);
        assert(actor);
        assert(actor->control ==
               battle_control::player);
        if(actor->character_id == 2 &&
                actor->chakra < 2 &&
                ! replenished_sasuke)
        {
            replenish_actor(
                    controller,
                    actor->position);
            replenished_sasuke = true;
            trace_scenario_49_state(
                    "after-replenish",
                    controller.snapshot());
            continue;
        }
        const ability_id action =
                actor->character_id == 2 &&
                        actor->chakra >= 2 ?
                        16 :
                        5;
        const int action_range =
                active_action_definitions[action]
                        .range.maximum_distance();
        const battle_scene_unit_view* enemy =
                actor->character_id == 3 &&
                        before.round >= 2
                ? active_unit(before, 5)
                : nullptr;
        if(! enemy)
        {
            enemy = weakest_enemy(
                    before,
                    *actor,
                    action_range);
        }
        assert(enemy);

        const grid_point enemy_position =
                enemy->position;
        move_actor(
                controller,
                enemy_position,
                action_range);
        const snapshot_type moved = controller.snapshot();
        if(distance(
                   moved.player.move_position,
                   enemy_position) > action_range)
        {
            select_command(
                    controller,
                    battle_command_type::end_action);
            finish_turn(controller);
            continue;
        }
        assert(select_active_action(
                controller,
                action));
        used_fireball =
                used_fireball || action == 16;
        confirm_target(controller, enemy_position);
        finish_turn(controller);
        trace_scenario_49_state(
                "after-turn",
                controller.snapshot());

        const int current_enemy_count =
                active_enemy_count(controller.snapshot());
        assert(current_enemy_count <=
               previous_enemy_count);
        const int new_kills =
                previous_enemy_count -
                current_enemy_count;
        if(actor->character_id == 1)
        {
            naruto_kills += new_kills;
        }
        else
        {
            if(actor->character_id == 2)
            {
                sasuke_kills += new_kills;
            }
            else
            {
                sakura_kills += new_kills;
            }
        }
        defeated_enemies += new_kills;
        previous_enemy_count = current_enemy_count;
        escort_took_damage =
                escort_took_damage ||
                unit(controller.snapshot(), 4).hp < 40;
    }

    const snapshot_type outcome = controller.snapshot();
    assert(used_fireball);
    assert(replenished_sasuke);
    assert(escort_took_damage);
    assert(defeated_enemies == 5);
    assert(naruto_kills +
                   sasuke_kills +
                   sakura_kills ==
           5);
    assert(naruto_kills == 3);
    assert(sasuke_kills == 1);
    assert(sakura_kills == 1);
    assert(outcome.phase ==
           battle_scene_phase::outcome);
    assert(outcome.outcome ==
           battle_condition_outcome::win);
    assert(unit(outcome, 4).active);
    assert(unit(outcome, 4).hp > 0);
    // The escort now occupies (10,7) before the first player route.
    // This fixed heuristic finishes on round 9, beyond the 8-round bonus.
    assert(outcome.round == 9);
    for(battle_unit_id id = 5; id <= 9; ++id)
    {
        assert(! unit(outcome, id).active);
    }

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::result);
    const battle_result& result =
            controller.result_snapshot();
    assert(result.participant_count == 3);
    assert(controller.snapshot().result_participant_index == 0);
    const auto progression_before_result_browse =
            controller.progression_roster();
    assert(controller.cycle_unit(1).success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::result);
    assert(controller.snapshot().result_participant_index == 1);
    assert(controller.progression_roster() ==
           progression_before_result_browse);
    assert(controller.cycle_unit(1).success());
    assert(controller.snapshot().result_participant_index == 2);
    assert(controller.cycle_unit(1).success());
    assert(controller.snapshot().result_participant_index == 0);
    assert(controller.cycle_unit(-1).success());
    assert(controller.snapshot().result_participant_index == 2);
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
    assert(battle_experience == 250);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::level_up);
    const auto& settled =
            controller.progression_roster();
    assert(settled[0].level == 6);
    assert(settled[0].experience == 50);
    assert(settled[0].training_points == 5);
    assert(settled[1].level == 5);
    assert(settled[1].experience == 100);
    assert(settled[1].training_points == 4);
    assert(settled[2].level == 6);
    assert(settled[2].experience == 80);
    assert(settled[2].training_points == 5);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::level_up);
    assert(controller.snapshot().result_participant_index == 0);
    assert(controller.snapshot().level_up_detail_page == 1);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::level_up);
    assert(controller.snapshot().result_participant_index == 1);
    assert(controller.snapshot().level_up_detail_page == 0);
    assert(controller.confirm().success());
    assert(controller.snapshot().level_up_detail_page == 1);
    assert(controller.confirm().success());
    assert(controller.snapshot().result_participant_index == 2);
    assert(controller.snapshot().level_up_detail_page == 0);
    assert(controller.confirm().success());
    assert(controller.snapshot().level_up_detail_page == 1);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::training);
    for(std::uint8_t page = 0; page < 6; ++page)
    {
        assert(controller.snapshot().phase ==
               battle_scene_phase::training);
        assert(controller.snapshot().training_detail_page ==
               page);
        assert(controller.confirm().success());
    }
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
    assert(campaign.chapter_id == 50);
}
