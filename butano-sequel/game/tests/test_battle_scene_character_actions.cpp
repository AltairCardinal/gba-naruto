#include "konoha/battle_scene_controller.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_identity_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>
#include <string_view>

using namespace konoha;

namespace
{

using controller_type =
        battle_scene_controller<12, 16, 32>;
using snapshot_type = battle_scene_snapshot<12>;

[[nodiscard]] const battle_scene_unit_view& unit(
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

void move_cursor_to(
        controller_type& controller,
        grid_point target)
{
    grid_point cursor = controller.snapshot().cursor;
    while(cursor.x != target.x)
    {
        const int direction =
                cursor.x < target.x ? 1 : -1;
        assert(controller.move_cursor(
                   direction, 0)
                       .success());
        cursor = controller.snapshot().cursor;
    }
    while(cursor.y != target.y)
    {
        const int direction =
                cursor.y < target.y ? 1 : -1;
        assert(controller.move_cursor(
                   0, direction)
                       .success());
        cursor = controller.snapshot().cursor;
    }
}

[[nodiscard]] battle_scene_presentation_event
execute_action_to(
        controller_type& controller,
        battle_unit_id actor_id,
        ability_id action_id,
        grid_point move_destination,
        grid_point target)
{
    snapshot_type state = controller.snapshot();
    assert(state.phase == battle_scene_phase::unit_selection);
    assert(state.selected_unit == actor_id);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);

    move_cursor_to(controller, move_destination);
    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(state.phase ==
           battle_scene_phase::command_selection);
    assert(state.player.selected_command ==
           battle_command_type::ability);
    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(state.phase ==
           battle_scene_phase::action_selection);
    assert(state.player.action_count == 3);

    for(int index = 0;
            index < state.player.action_count &&
            state.player.selected_action_id != action_id;
            ++index)
    {
        assert(controller.move_cursor(0, 1).success());
        state = controller.snapshot();
    }
    assert(state.player.selected_action_id == action_id);
    const battle_action_menu_view& selected =
            state.player.action_entries[
                    static_cast<std::size_t>(
                            state.player.action_index)];
    assert(selected.action_id == action_id);
    assert(selected.selectable());

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_selection);
    move_cursor_to(controller, target);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::facing_selection);

    battle_scene_presentation_event event;
    for(int index = 0; index < 16; ++index)
    {
        const battle_scene_presentation_event candidate =
                controller.take_presentation_event();
        if(! candidate.valid)
        {
            break;
        }
        if(candidate.has_action &&
                candidate.actor_id == actor_id &&
                candidate.action_id == action_id)
        {
            event = candidate;
            break;
        }
    }
    assert(event.valid);
    assert(event.has_action);
    assert(event.actor_id == actor_id);
    assert(event.action_id == action_id);
    assert(event.target == target);
    return event;
}

void finish_action(controller_type& controller)
{
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::defense_decision);
    assert(controller.confirm().success());
}

[[nodiscard]] snapshot_type action_snapshot_for(
        battle_unit_id actor_id)
{
    battle_scenario_load_policy fixed_pool;
    fixed_pool.preserve_empty_unit_slots = true;
    controller_type controller;
    assert(controller.load(
                   battle_scenario_definitions[9],
                   battle_map_definitions[9],
                   battle_map_cells,
                   0,
                   fixed_pool,
                   battle_condition_variants[9][0],
                   0x09U)
                   .success());
    assert(controller.start().success());
    while(controller.snapshot().selected_unit != actor_id)
    {
        assert(controller.cycle_unit(1).success());
    }
    assert(controller.confirm().success());
    assert(controller.confirm().success());
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::action_selection);
    return controller.snapshot();
}

void assert_action_ids(
        const snapshot_type& state,
        std::array<ability_id, 3> expected)
{
    assert(state.player.action_count ==
           static_cast<int>(expected.size()));
    for(std::size_t index = 0;
            index < expected.size(); ++index)
    {
        assert(state.player.action_entries[index].kind ==
               battle_action_source_kind::active_action);
        assert(state.player.action_entries[index].action_id ==
               expected[index]);
    }
}

}

int main()
{
    assert(std::string_view(
                   battle_unit_identity(1)->display_name) ==
           "漩涡鸣人");
    assert(std::string_view(
                   battle_unit_identity(2)->display_name) ==
           "宇智波佐助");
    assert(std::string_view(
                   battle_unit_identity(3)->display_name) ==
           "春野樱");
    assert(std::string_view(
                   battle_active_action_identity(1)->
                           display_name) ==
           "分身术");
    assert(std::string_view(
                   battle_active_action_identity(2)->
                           display_name) ==
           "瞬身术");
    assert(std::string_view(
                   battle_ninja_tool_identity(1)->
                           display_name) ==
           "十字手里剑");
    assert(std::string_view(
                   battle_ninja_tool_identity(93)->
                           display_name) ==
           "超万能丸");
    assert_action_ids(
            action_snapshot_for(1), { 2, 5, 7 });
    assert_action_ids(
            action_snapshot_for(2), { 2, 5, 16 });
    assert_action_ids(
            action_snapshot_for(3), { 1, 2, 5 });

    battle_scenario_load_policy fixed_pool;
    fixed_pool.preserve_empty_unit_slots = true;
    battle_scenario_definition character_action_scenario =
            battle_scenario_definitions[9];
    character_action_scenario.variants[0][3].position = {
        7, 13
    };
    controller_type controller;
    assert(controller.load(
                   character_action_scenario,
                   battle_map_definitions[9],
                   battle_map_cells,
                   0,
                   fixed_pool,
                   battle_condition_variants[9][0],
                   0x09U)
                   .success());
    assert(controller.start().success());

    snapshot_type state = controller.snapshot();
    assert(state.selected_unit == 1);
    assert(state.active_unit_count == 8);
    assert(state.player.action_count == 0);
    const int naruto_chakra = unit(state, 1).chakra;

    const battle_scene_presentation_event teleport =
            execute_action_to(
                    controller,
                    1,
                    2,
                    { 11, 15 },
                    { 11, 14 });
    assert(teleport.origin == grid_point({ 11, 15 }));
    assert(unit(controller.snapshot(), 1).position ==
           grid_point({ 11, 14 }));
    assert(unit(controller.snapshot(), 1).chakra ==
           naruto_chakra - 1);
    assert(controller.snapshot().active_unit_count == 8);
    finish_action(controller);

    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::unit_selection);
    assert(state.selected_unit == 2);
    assert(controller.cycle_unit(1).success());
    assert(controller.snapshot().selected_unit == 3);
    const int sakura_chakra =
            unit(controller.snapshot(), 3).chakra;

    const battle_scene_presentation_event clone =
            execute_action_to(
                    controller,
                    3,
                    1,
                    { 13, 15 },
                    { 13, 14 });
    assert(clone.origin == grid_point({ 13, 15 }));
    state = controller.snapshot();
    assert(unit(state, 3).position ==
           grid_point({ 13, 15 }));
    assert(unit(state, 3).chakra ==
           sakura_chakra - 2);
    assert(state.active_unit_count == 9);
    assert(unit(state, 9).active);
    assert(unit(state, 9).character_id == 3);
    assert(unit(state, 9).summoner == 3);
    assert(unit(state, 9).position ==
           grid_point({ 13, 14 }));
    assert(unit(state, 9).completed);
    finish_action(controller);

    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::unit_selection);
    assert(state.selected_unit == 2);
    const grid_point sasuke_position = unit(state, 2).position;
    const grid_point action_05_position = { 7, 14 };
    const grid_point adjacent_enemy = { 7, 13 };
    const battle_unit_id adjacent_enemy_id = 4;
    const int target_hp_before =
            unit(state, adjacent_enemy_id).hp;
    const battle_scene_presentation_event action_05 =
            execute_action_to(
                    controller,
                    2,
                    5,
                    action_05_position,
                    adjacent_enemy);
    assert(action_05.origin == sasuke_position);
    assert(action_05.target == adjacent_enemy);
    assert(action_05.impact_count == 1);
    assert(unit(controller.snapshot(), 2).position ==
           action_05_position);
    assert(unit(controller.snapshot(), adjacent_enemy_id).hp <
           target_hp_before);
    finish_action(controller);

    assert(controller.snapshot().phase ==
           battle_scene_phase::enemy_turn);
    while(controller.snapshot().phase ==
            battle_scene_phase::enemy_turn)
    {
        assert(controller.tick().success());
    }
    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::unit_selection);
    assert(state.current_side == battle_side::player);
    assert(state.round == 2);
    assert(state.active_unit_count == 8);
    assert(state.selected_unit == 1);
    assert(unit(state, 1).position ==
           grid_point({ 11, 14 }));
    assert(unit(state, 9).active);
    assert(unit(state, 9).summoner == 3);
}
