#include "konoha/battle_arena_roster.h"
#include "konoha/battle_content_catalog.h"
#include "konoha/battle_runtime_grid.h"

#include <cassert>

using namespace konoha;

namespace
{

void end_selected_player_turn(
        battle_runtime_controller& controller)
{
    assert(controller.snapshot().phase ==
           battle_scene_phase::unit_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::command_selection);

    for(int index = 0;
            index < 8 &&
            controller.snapshot().player.selected_command !=
                    battle_command_type::end_action;
            ++index)
    {
        assert(controller.move_cursor(0, 1).success());
    }
    assert(controller.snapshot().player.selected_command ==
           battle_command_type::end_action);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::facing_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::defense_decision);
    assert(controller.confirm().success());
}

battle_arena_combatant combatant(
        std::uint8_t character_id,
        int level,
        ninja_tool_id tool)
{
    battle_arena_combatant result;
    result.progression.character_id = character_id;
    result.progression.level = level;
    result.progression.active = true;
    assert(initialize_character_action_progression(
            result.progression,
            unit_definitions[character_id]));
    result.equipped_tools[0] = tool;
    return result;
}

}

int main()
{
    const battle_content_entry content =
            generated_battle_content_entry(32, 0);
    assert(content.valid());
    assert(content.kind ==
           battle_content_entry_kind::deployment_required);

    battle_scenario_load_policy policy;
    battle_arena_match_roster roster;
    roster.player[0] = combatant(1, 10, 1);
    roster.player[1] = combatant(2, 12, 17);
    roster.player[2] = combatant(3, 11, 46);
    roster.opponent[0] = combatant(12, 18, 93);
    roster.opponent[1] = combatant(35, 15, 11);
    roster.opponent[2] = combatant(1, 20, 67);
    assert(apply_battle_arena_scene_policy(
                   roster, policy) ==
           battle_arena_roster_error::none);
    policy.preserve_empty_unit_slots = true;

    static battle_runtime_controller controller;
    assert(controller.load(
                   *content.scenario,
                   *content.map,
                   battle_map_cells,
                   0,
                   policy,
                   *content.conditions,
                   0x32U)
                   .success());
    assert(controller.start().success());
    assert(controller.snapshot().active_unit_count == 6);
    assert(controller.snapshot().units[0].level == 10);
    assert(controller.snapshot().units[3].level == 18);
    assert(controller.snapshot().units[5].character_id == 1);
    assert(controller.snapshot().units[5].level == 20);

    assert(controller.confirm().success());
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::action_selection);
    assert(controller.snapshot().player.selected_action_id == 2);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_selection);
    assert(controller.move_cursor(0, -1).success());
    assert((controller.snapshot().cursor ==
            grid_point{ 2, 5 }));
    const battle_scene_control_result blocked_teleport =
            controller.confirm();
    assert(! blocked_teleport.success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_selection);
    assert(controller.cancel().success());
    assert(controller.cancel().success());
    assert(controller.cancel().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::unit_selection);

    end_selected_player_turn(controller);
    end_selected_player_turn(controller);
    end_selected_player_turn(controller);
    assert(controller.snapshot().phase ==
           battle_scene_phase::enemy_turn);

    for(int enemy = 0; enemy < 3; ++enemy)
    {
        const battle_scene_control_result result =
                controller.tick();
        assert(result.success());
    }

    const battle_scene_snapshot<12> state =
            controller.snapshot();
    assert(state.round == 2);
    assert(state.current_side == battle_side::player);
    assert(state.phase == battle_scene_phase::unit_selection);
    assert(state.active_unit_count == 7);
    int summoned_unit_count = 0;
    for(const battle_scene_unit_view& value : state.units)
    {
        if(value.active && value.summoner != no_battle_unit)
        {
            ++summoned_unit_count;
        }
    }
    assert(summoned_unit_count == 1);
}
