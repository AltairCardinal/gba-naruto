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

const battle_scene_unit_view* active_enemy(
        const snapshot_type& state)
{
    for(std::size_t index = 0;
            index < state.unit_count; ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
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

const battle_action_menu_view* action_entry(
        const battle_player_action_flow_snapshot& state,
        battle_action_source_kind kind,
        ability_id action)
{
    for(int index = 0; index < state.action_count; ++index)
    {
        const battle_action_menu_view& entry =
                state.action_entries[
                        static_cast<std::size_t>(index)];
        if(entry.kind == kind &&
                entry.action_id == action)
        {
            return &entry;
        }
    }
    return nullptr;
}

void select_action(
        controller_type& controller,
        battle_action_source_kind kind,
        ability_id action)
{
    select_command(
            controller,
            battle_command_type::ability);
    for(int step = 0; step < 24; ++step)
    {
        const battle_player_action_flow_snapshot& state =
                controller.snapshot().player;
        assert(state.action_index >= 0);
        assert(state.action_index < state.action_count);
        const battle_action_menu_view& selected =
                state.action_entries[
                        static_cast<std::size_t>(
                                state.action_index)];
        if(selected.kind == kind &&
                selected.action_id == action)
        {
            assert(selected.selectable());
            assert(controller.confirm().success());
            if(controller.snapshot().phase ==
                    battle_scene_phase::
                            combination_decision)
            {
                assert(controller.move_cursor(0, 1).success());
                assert(! controller.snapshot()
                                .player
                                .combination_decision_selected);
                assert(controller.confirm().success());
            }
            assert(controller.snapshot().phase ==
                   battle_scene_phase::target_selection);
            return;
        }
        assert(controller.move_cursor(0, 1).success());
    }
    assert(false);
}

int move_closest_to(
        controller_type& controller,
        grid_point target)
{
    for(int distance = 1; distance < 9 + 22; ++distance)
    {
        for(int y = 0; y < 22; ++y)
        {
            for(int x = 0; x < 9; ++x)
            {
                const int dx =
                        x > target.x ?
                                x - target.x :
                                target.x - x;
                const int dy =
                        y > target.y ?
                                y - target.y :
                                target.y - y;
                if(dx + dy != distance)
                {
                    continue;
                }
                set_cursor(controller, { x, y });
                if(controller.confirm().success())
                {
                    assert(controller.snapshot().phase ==
                           battle_scene_phase::
                                   command_selection);
                    return distance;
                }
            }
        }
    }
    assert(false);
    return 0;
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

void finish_action(controller_type& controller)
{
    if(controller.snapshot().phase ==
            battle_scene_phase::outcome)
    {
        return;
    }
    if(controller.snapshot().phase ==
            battle_scene_phase::facing_selection)
    {
        assert(controller.move_cursor(0, -1).success());
        assert(controller.confirm().success());
    }
    if(controller.snapshot().phase ==
            battle_scene_phase::defense_decision)
    {
        assert(controller.confirm().success());
    }
    finish_enemy_side(controller);
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

battle_campaign_state campaign_after_scenario_44()
{
    battle_campaign_state result =
            empty_battle_campaign();
    result.chapter_id = 45;
    assert(activate_battle_campaign_character(
            result,
            progression(1, 3, 125, 2)));
    assert(activate_battle_campaign_character(
            result,
            progression(2, 2, 45, 1)));
    assert(activate_battle_campaign_character(
            result,
            progression(3, 1, 125, 0)));
    result.characters[1].equipped_tools[0] = 1;
    result.inventory.ninja_tools[1] = 1;
    assert(set_battle_campaign_party(
            result, { 1, 2, 3 }));
    assert(prepare_battle_campaign_stage(result)
                   .success());
    return result;
}

battle_scenario_load_policy campaign_policy(
        const battle_campaign_state& campaign)
{
    battle_scenario_load_policy result;
    result.preserve_empty_unit_slots = true;
    assert(apply_battle_campaign_scene_policy(
                   campaign, result) ==
           battle_campaign_error::none);
    return result;
}

controller_type load_controller(
        const battle_campaign_state& campaign,
        const battle_campaign_scene_progression& progression_state)
{
    controller_type result;
    const battle_scenario_load_policy policy =
            campaign_policy(campaign);
    assert(result.load(
                   battle_scenario_definitions[45],
                   battle_map_definitions[45],
                   battle_map_cells,
                   0,
                   policy,
                   battle_condition_variants[45][0],
                   45U,
                   progression_state.records(),
                   false,
                   battle_mission_rules_for(45, 0))
                   .success());
    assert(result.start().success());
    return result;
}

void verify_character_catalog(
        const battle_campaign_state& campaign,
        const battle_campaign_scene_progression&
                progression_state,
        grid_point position,
        std::array<ability_id, 3> active_actions,
        bool expect_cross_shuriken)
{
    controller_type controller =
            load_controller(campaign, progression_state);
    set_cursor(controller, position);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    select_command(
            controller,
            battle_command_type::ability);

    const battle_player_action_flow_snapshot& catalog =
            controller.snapshot().player;
    for(const ability_id action : active_actions)
    {
        const battle_action_menu_view* entry =
                action_entry(
                        catalog,
                        battle_action_source_kind::
                                active_action,
                        action);
        assert(entry);
        assert(entry->selectable());
    }
    const battle_action_menu_view* cross_shuriken =
            action_entry(
                    catalog,
                    battle_action_source_kind::ninja_tool,
                    1);
    assert((cross_shuriken != nullptr) ==
           expect_cross_shuriken);
    if(cross_shuriken)
    {
        assert(cross_shuriken->selectable());
        assert(cross_shuriken->cost_kind ==
               action_cost_kind::
                       battle_local_ninja_tool_slot);
        assert(cross_shuriken->tool_slot == 0);
    }
}

}

int main()
{
    battle_campaign_state campaign =
            campaign_after_scenario_44();
    battle_campaign_scene_progression progression_state;
    assert(progression_state.begin(campaign) ==
           battle_campaign_error::none);

    verify_character_catalog(
            campaign,
            progression_state,
            { 4, 5 },
            { 2, 5, 7 },
            true);
    verify_character_catalog(
            campaign,
            progression_state,
            { 2, 6 },
            { 2, 5, 16 },
            false);
    verify_character_catalog(
            campaign,
            progression_state,
            { 6, 6 },
            { 1, 2, 5 },
            false);

    controller_type controller =
            load_controller(campaign, progression_state);
    const snapshot_type initial = controller.snapshot();
    assert(initial.phase ==
           battle_scene_phase::unit_selection);
    assert(initial.round == 1);
    assert(initial.active_unit_count == 4);
    assert(unit(initial, 1).character_id == 1);
    assert(unit(initial, 1).level == 3);
    assert(unit(initial, 1).position ==
           grid_point({ 4, 5 }));
    assert(unit(initial, 2).character_id == 2);
    assert(unit(initial, 2).level == 2);
    assert(unit(initial, 2).position ==
           grid_point({ 2, 6 }));
    assert(unit(initial, 3).character_id == 3);
    assert(unit(initial, 3).level == 1);
    assert(unit(initial, 3).position ==
           grid_point({ 6, 6 }));
    assert(unit(initial, 4).character_id == 7);
    assert(unit(initial, 4).level == 3);
    assert(unit(initial, 4).position ==
           grid_point({ 4, 12 }));
    assert(unit(initial, 4).hp == 100);

    bool cross_shuriken_used = false;
    bool sasuke_fire_used = false;
    for(int turn = 0;
            turn < 160 &&
            active_enemy(controller.snapshot());
            ++turn)
    {
        const snapshot_type before =
                controller.snapshot();
        assert(before.phase ==
               battle_scene_phase::unit_selection);
        const battle_scene_unit_view* actor =
                unit_at_cursor(before);
        const battle_scene_unit_view* enemy =
                active_enemy(before);
        assert(actor);
        assert(actor->side == battle_side::player);
        assert(enemy);
        const battle_unit_id actor_id = actor->id;
        const std::uint8_t character_id =
                actor->character_id;
        const int chakra_before = actor->chakra;
        const grid_point enemy_position =
                enemy->position;

        assert(controller.confirm().success());
        assert(controller.snapshot().phase ==
               battle_scene_phase::move_selection);

        // Prove Naruto's consumable route before other actors close
        // the narrow lanes.
        if(! cross_shuriken_used && character_id != 1)
        {
            assert(controller.confirm().success());
            select_command(
                    controller,
                    battle_command_type::end_action);
            finish_action(controller);
            continue;
        }

        // Then prove Sasuke's move-then-ninjutsu route.
        if(cross_shuriken_used &&
                ! sasuke_fire_used &&
                character_id != 2)
        {
            assert(controller.confirm().success());
            select_command(
                    controller,
                    battle_command_type::end_action);
            finish_action(controller);
            continue;
        }

        // The original battle completed after the round-5 bonus
        // boundary. Preserve that timing and reserve the defeat for
        // Sakura, who receives Kakashi's carried EXP.
        if(cross_shuriken_used &&
                sasuke_fire_used &&
                (before.round <= 5 ||
                 character_id != 3))
        {
            assert(controller.confirm().success());
            select_command(
                    controller,
                    battle_command_type::end_action);
            finish_action(controller);
            continue;
        }

        const int distance =
                move_closest_to(
                        controller, enemy_position);
        const bool in_preferred_range =
                character_id == 1 &&
                        ! cross_shuriken_used ?
                distance <= 3 :
                character_id == 2 &&
                        ! sasuke_fire_used ?
                distance <= 2 :
                distance == 1;
        if(in_preferred_range)
        {
            if(character_id == 1 &&
                    ! cross_shuriken_used)
            {
                select_action(
                        controller,
                        battle_action_source_kind::
                                ninja_tool,
                        1);
            }
            else if(character_id == 2 &&
                    ! sasuke_fire_used)
            {
                select_action(
                        controller,
                        battle_action_source_kind::
                                active_action,
                        16);
            }
            else
            {
                select_action(
                        controller,
                        battle_action_source_kind::
                                active_action,
                        5);
            }
            set_cursor(controller, enemy_position);
            assert(controller.confirm().success());
            drain_presentations(controller);

            if(character_id == 1 &&
                    ! cross_shuriken_used)
            {
                cross_shuriken_used = true;
                assert(controller
                               .equipped_tools_roster()[0][0] ==
                       0);
            }
            else if(character_id == 2 &&
                    ! sasuke_fire_used)
            {
                sasuke_fire_used = true;
                assert(unit(
                               controller.snapshot(),
                               actor_id)
                               .chakra ==
                       chakra_before - 2);
            }
        }
        else
        {
            select_command(
                    controller,
                    battle_command_type::end_action);
        }
        finish_action(controller);
    }

    assert(cross_shuriken_used);
    assert(sasuke_fire_used);
    assert(! active_enemy(controller.snapshot()));
    assert(controller.snapshot().phase ==
           battle_scene_phase::outcome);
    assert(controller.snapshot().outcome ==
           battle_condition_outcome::win);
    assert(controller.snapshot().round > 5);

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
                       .mission_experience == 150);
        assert(result.participants[index]
                       .round_bonus_experience == 0);
        const bool sakura =
                result.participants[index].character_id == 3;
        assert(result.participants[index]
                       .battle_experience ==
               (sakura ? 100 : 0));
        assert(result.participants[index]
                       .total_experience ==
               (sakura ? 250 : 150));
    }

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::level_up);
    assert(controller.progression_roster()[0].level == 3);
    assert(controller.progression_roster()[0].experience == 275);
    assert(controller.progression_roster()[0].training_points == 2);
    assert(controller.progression_roster()[1].level == 3);
    assert(controller.progression_roster()[1].experience == 0);
    assert(controller.progression_roster()[1].training_points == 2);
    assert(controller.progression_roster()[2].level == 3);
    assert(controller.progression_roster()[2].experience == 60);
    assert(controller.progression_roster()[2].training_points == 2);

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
    assert(campaign.inventory.ninja_tools[1] == 0);
    assert(campaign.characters[1].equipped_tools[0] == 0);
    assert(advance_battle_campaign_stage(
                   campaign,
                   battle_runtime_scene_exit::victory)
                   .success());
    assert(campaign.chapter_id == 46);
    assert(campaign.party ==
           (std::array<std::uint8_t, 3>{ 1, 2, 3 }));
}
