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
        battle_scene_controller<12, 16, 32>;
using snapshot_type = battle_scene_snapshot<12>;

void set_cursor(
        controller_type& controller,
        grid_point target);

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

const battle_scene_unit_view* active_cat(
        const snapshot_type& state)
{
    for(std::size_t index = 0;
            index < state.unit_count; ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(candidate.active &&
                candidate.side == battle_side::enemy &&
                candidate.character_id == 41)
        {
            return &candidate;
        }
    }
    return nullptr;
}

const battle_scene_unit_view* adjacent_cat(
        const snapshot_type& state,
        grid_point actor_position)
{
    for(std::size_t index = 0;
            index < state.unit_count; ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(! candidate.active ||
                candidate.side != battle_side::enemy ||
                candidate.character_id != 41)
        {
            continue;
        }
        const int dx =
                candidate.position.x > actor_position.x ?
                        candidate.position.x -
                                actor_position.x :
                        actor_position.x -
                                candidate.position.x;
        const int dy =
                candidate.position.y > actor_position.y ?
                        candidate.position.y -
                                actor_position.y :
                        actor_position.y -
                                candidate.position.y;
        if(dx + dy == 1)
        {
            return &candidate;
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

const battle_scene_unit_view* closest_cat(
        const snapshot_type& state,
        grid_point position)
{
    const battle_scene_unit_view* result = nullptr;
    int best_distance = 16 * 32;
    for(std::size_t index = 0;
            index < state.unit_count; ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(! candidate.active ||
                candidate.side != battle_side::enemy ||
                candidate.character_id != 41)
        {
            continue;
        }
        const int candidate_distance =
                distance(position, candidate.position);
        if(! result || candidate_distance < best_distance)
        {
            result = &candidate;
            best_distance = candidate_distance;
        }
    }
    return result;
}

bool occupied_by_active_unit(
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
            battle_map_definitions[9];
    if(! map.contains(point.x, point.y))
    {
        return false;
    }
    const battle_map_cell& cell =
            battle_map_cells[
                    map.cell_offset +
                    point.y * map.width +
                    point.x];
    return cell.terrain_class() == 0;
}

grid_point planned_move_destination(
        const snapshot_type& state,
        const battle_scene_unit_view& actor,
        grid_point target,
        int target_distance)
{
    constexpr int width = 16;
    constexpr int height = 32;
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
        const grid_point point =
                index_point(current);
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
                    occupied_by_active_unit(
                            state, next, actor.id))
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

void move_toward(
        controller_type& controller,
        grid_point destination,
        int target_distance = 1)
{
    const snapshot_type before = controller.snapshot();
    const battle_scene_unit_view* actor =
            unit_at_cursor(before);
    assert(actor);
    const grid_point selected =
            planned_move_destination(
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

void drain_presentations(
        controller_type& controller,
        int& capture_count)
{
    while(true)
    {
        const battle_scene_presentation_event event =
                controller.take_presentation_event();
        if(! event.valid)
        {
            return;
        }
        if(event.capture_count > 0)
        {
            assert(event.affected_unit_count > 0);
            for(int index = 0;
                    index < event.affected_unit_count;
                    ++index)
            {
                assert(event.affected_character_ids[
                               static_cast<std::size_t>(
                                       index)] == 41);
            }
        }
        capture_count += event.capture_count;
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

bool select_action(
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
                assert(controller.snapshot().phase ==
                       battle_scene_phase::
                               command_selection);
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

void finish_enemy_side(
        controller_type& controller,
        int& capture_count)
{
    for(int step = 0;
            step < 96 &&
            controller.snapshot().phase ==
                    battle_scene_phase::enemy_turn;
            ++step)
    {
        drain_presentations(
                controller, capture_count);
        assert(controller.tick().success());
    }
    drain_presentations(controller, capture_count);
    assert(controller.snapshot().phase !=
           battle_scene_phase::enemy_turn);
}

void finish_action(
        controller_type& controller,
        int& capture_count)
{
    drain_presentations(controller, capture_count);
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
    finish_enemy_side(controller, capture_count);
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

battle_campaign_state campaign_after_scenario_45()
{
    battle_campaign_state result =
            empty_battle_campaign();
    result.chapter_id = 46;
    assert(activate_battle_campaign_character(
            result,
            progression(1, 3, 275, 2)));
    assert(activate_battle_campaign_character(
            result,
            progression(2, 3, 0, 2)));
    assert(activate_battle_campaign_character(
            result,
            progression(3, 3, 60, 2)));
    assert(set_battle_campaign_party(
            result, { 1, 2, 3 }));
    assert(prepare_battle_campaign_stage(result)
                   .success());
    return result;
}

controller_type load_controller(
        const battle_campaign_state& campaign,
        const battle_campaign_scene_progression&
                progression_state)
{
    battle_scenario_load_policy policy;
    policy.preserve_empty_unit_slots = true;
    assert(apply_battle_campaign_scene_policy(
                   campaign, policy) ==
           battle_campaign_error::none);
    controller_type result;
    assert(result.load(
                   battle_scenario_definitions[9],
                   battle_map_definitions[9],
                   battle_map_cells,
                   0,
                   policy,
                   battle_condition_variants[9][0],
                   46U,
                   progression_state.records(),
                   false,
                   battle_mission_rules_for(9, 0))
                   .success());
    assert(result.start().success());
    return result;
}

}

int main()
{
    battle_campaign_state campaign =
            campaign_after_scenario_45();
    battle_campaign_scene_progression progression_state;
    assert(progression_state.begin(campaign) ==
           battle_campaign_error::none);
    {
        controller_type exact_controller =
                load_controller(
                        campaign, progression_state);
        const snapshot_type initial =
                exact_controller.snapshot();
        assert(initial.phase ==
               battle_scene_phase::unit_selection);
        assert(initial.round == 1);
        assert(initial.active_unit_count == 8);
        assert(unit(initial, 1).position ==
               grid_point({ 11, 15 }));
        assert(unit(initial, 2).position ==
               grid_point({ 9, 15 }));
        assert(unit(initial, 3).position ==
               grid_point({ 13, 15 }));
        for(battle_unit_id id = 4; id <= 8; ++id)
        {
            assert(unit(initial, id).character_id == 41);
            assert(unit(initial, id).hp == 1);
        }
    }

    controller_type controller =
            load_controller(campaign, progression_state);
    std::array<int, 4> captures_by_character = {};
    int presented_captures = 0;
    for(int turn = 0;
            turn < 600 &&
            active_cat(controller.snapshot());
            ++turn)
    {
        const snapshot_type before =
                controller.snapshot();
        assert(before.phase ==
               battle_scene_phase::unit_selection);
        const battle_scene_unit_view* actor =
                unit_at_cursor(before);
        assert(actor);
        assert(actor->side == battle_side::player);

        const int total_captures =
                captures_by_character[1] +
                captures_by_character[2] +
                captures_by_character[3];
        const std::uint8_t designated_character =
                total_captures < 2 ? 2 :
                total_captures < 4 ? 1 : 3;
        const int capture_chakra_cost =
                designated_character == 2 ? 2 :
                designated_character == 1 ? 3 : 0;
        if(actor->character_id ==
                        designated_character &&
                actor->chakra < capture_chakra_cost)
        {
            move_toward(
                    controller,
                    actor->position,
                    0);
            select_command(
                    controller,
                    battle_command_type::
                            replenish_chakra);
            assert(controller.confirm().success());
            finish_action(
                    controller, presented_captures);
            continue;
        }
        grid_point designated_position = actor->position;
        for(std::size_t index = 0;
                index < before.unit_count; ++index)
        {
            const battle_scene_unit_view& candidate =
                    before.units[index];
            if(candidate.active &&
                    candidate.character_id ==
                            designated_character)
            {
                designated_position =
                        candidate.position;
                break;
            }
        }
        const battle_scene_unit_view* target =
                closest_cat(before, designated_position);
        assert(target);
        grid_point movement_target = target->position;
        int target_distance = 1;
        if(total_captures >= 3 &&
                target->position.y >= 22)
        {
            if(actor->character_id ==
                    designated_character &&
                    actor->position !=
                            grid_point({ 8, 27 }))
            {
                movement_target = { 8, 27 };
                target_distance = 0;
            }
            else if(actor->character_id !=
                    designated_character)
            {
                const bool first_blocker =
                        designated_character == 1 ?
                                actor->character_id == 2 :
                                actor->character_id == 1;
                movement_target =
                        first_blocker ?
                                grid_point({ 10, 27 }) :
                                grid_point({ 10, 26 });
                target_distance = 0;
            }
        }
        else if(total_captures >= 4 &&
                target->position.y <= 13)
        {
            if(actor->character_id == 1)
            {
                movement_target = {
                    14,
                    target->position.y < 13 ?
                            target->position.y + 1 :
                            14,
                };
                target_distance = 0;
            }
            else if(actor->character_id == 2)
            {
                movement_target = { 13, 4 };
                target_distance = 0;
            }
        }
        move_toward(
                controller,
                movement_target,
                target_distance);

        const bool designated =
                actor->character_id ==
                designated_character;
        const snapshot_type after_move =
                controller.snapshot();
        const battle_scene_unit_view* cat =
                adjacent_cat(
                        after_move,
                        after_move.player.move_position);
        if(designated && cat)
        {
            const grid_point cat_position =
                    cat->position;
            const ability_id action =
                    actor->character_id == 2 ?
                            16 :
                    actor->character_id == 1 ?
                            7 :
                            5;
            const bool selected_action =
                    select_action(controller, action);
            if(! selected_action)
            {
                select_command(
                        controller,
                        battle_command_type::
                                replenish_chakra);
                assert(controller.confirm().success());
                finish_action(
                        controller,
                        presented_captures);
                continue;
            }
            set_cursor(controller, cat_position);
            const int before_presented =
                    presented_captures;
            assert(controller.confirm().success());
            drain_presentations(
                    controller, presented_captures);
            if(presented_captures >
                    before_presented)
            {
                ++captures_by_character[
                        actor->character_id];
            }
        }
        else
        {
            select_command(
                    controller,
                    battle_command_type::end_action);
        }
        finish_action(
                controller, presented_captures);
    }

    assert(captures_by_character[1] == 2);
    assert(captures_by_character[2] == 2);
    assert(captures_by_character[3] == 1);
    assert(presented_captures == 5);
    assert(! active_cat(controller.snapshot()));
    assert(controller.snapshot().phase ==
           battle_scene_phase::outcome);
    assert(controller.snapshot().outcome ==
           battle_condition_outcome::win);
    for(battle_unit_id id = 4; id <= 8; ++id)
    {
        assert(! unit(controller.snapshot(), id).active);
        assert(unit(controller.snapshot(), id)
                       .character_id == 0);
    }

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
        const battle_result_participant& participant =
                result.participants[index];
        assert(participant.mission_experience == 125);
        assert(participant.round_bonus_experience == 0);
        assert(participant.battle_experience ==
               (participant.character_id == 3 ? 30 : 60));
        assert(participant.total_experience ==
               (participant.character_id == 3 ? 155 : 185));
    }

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::level_up);
    assert(controller.progression_roster()[0].level == 4);
    assert(controller.progression_roster()[0].experience == 180);
    assert(controller.progression_roster()[0].training_points == 3);
    assert(controller.progression_roster()[1].level == 3);
    assert(controller.progression_roster()[1].experience == 185);
    assert(controller.progression_roster()[1].training_points == 2);
    assert(controller.progression_roster()[2].level == 4);
    assert(controller.progression_roster()[2].experience == 35);
    assert(controller.progression_roster()[2].training_points == 3);

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
    assert(campaign.chapter_id == 47);
}
