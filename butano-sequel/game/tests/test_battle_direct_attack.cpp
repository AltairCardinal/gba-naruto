#include "konoha/battle_player_action_flow.h"
#include "konoha/battle_scene_controller.h"
#include "konoha/battle_unit_content.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_session<2> adjacent_session()
{
    battle_unit_instance player = instantiate_unit(
            unit_definitions[1],
            1,
            battle_side::player,
            battle_control::player,
            { 1, 1 },
            battle_facing::right,
            3);
    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::ai,
            { 2, 1 },
            battle_facing::left,
            3);
    enemy.hp = 100;
    enemy.max_hp = 100;

    battle_session<2> result;
    assert(result.add_unit(player));
    assert(result.add_unit(enemy));
    assert(result.start_round() ==
           battle_transition::unit_selection_opened);
    assert(result.select_unit(1) ==
           battle_transition::action_draft_opened);
    return result;
}

}

int main()
{
    battle_session<2> session = adjacent_session();
    battle_player_action_flow<2> flow;
    assert(flow.begin(session).success());
    assert(flow.select_command(
                   battle_command_type::direct_attack)
                   .success());
    assert(flow.open_direct_attack_targeting(
                   session)
                   .success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::target_selection);
    assert(flow.snapshot().selected_action_kind ==
           battle_action_source_kind::direct_attack);
    assert(flow.snapshot().selected_action_id ==
           direct_attack_ability_id);

    deterministic_rng rng(7);
    const int hp_before = session.unit(2)->hp;
    const battle_player_action_flow_result attacked =
            flow.confirm_target_in_place(
                    session,
                    { 2, 1 },
                    rng,
                    {});
    assert(attacked.success());
    assert(! attacked.ends_battle);
    assert(session.unit(2)->hp < hp_before);
    assert(flow.snapshot().phase ==
           battle_player_action_phase::facing_selection);

    battle_session<2> restricted_session =
            adjacent_session();
    battle_player_action_flow<2> restricted_flow;
    assert(restricted_flow.begin(
                   restricted_session)
                   .success());
    assert(restricted_flow.select_command(
                   battle_command_type::direct_attack)
                   .success());
    const int restricted_hp_before =
            restricted_session.unit(2)->hp;
    battle_action_access_policy restricted;
    restricted.allow_direct_attack = false;
    const battle_player_action_flow_result rejected =
            restricted_flow.open_direct_attack_targeting(
                    restricted_session,
                    restricted);
    assert(rejected.error ==
           battle_player_action_flow_error::action_rejected);
    assert(rejected.action_rejection ==
           action_error::mission_restricted);
    assert(restricted_flow.snapshot().phase ==
           battle_player_action_phase::command_selection);
    assert(restricted_session.unit(2)->hp ==
           restricted_hp_before);

    battle_scenario_definition adjacent_scenario =
            battle_scenario_definitions[45];
    adjacent_scenario.variants[0][3].position = { 4, 6 };
    battle_scene_controller<12, 9, 22> controller;
    assert(controller.load(
                   adjacent_scenario,
                   battle_map_definitions[45],
                   battle_map_cells,
                   0,
                   {},
                   battle_condition_variants[45][0],
                   7)
                   .success());
    assert(controller.start().success());
    assert(controller.snapshot().selected_unit == 1);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::move_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    for(int step = 0;
            step < 8 &&
            controller.snapshot().player.selected_command !=
                    battle_command_type::direct_attack;
            ++step)
    {
        assert(controller.move_cursor(0, 1).success());
    }
    assert(controller.snapshot().player.selected_command ==
           battle_command_type::direct_attack);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_selection);
    assert(controller.move_cursor(0, 1).success());
    assert(controller.snapshot().cursor ==
           grid_point({ 4, 6 }));
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::facing_selection);
    battle_scene_presentation_event event;
    for(int index = 0; index < 8; ++index)
    {
        const battle_scene_presentation_event candidate =
                controller.take_presentation_event();
        if(! candidate.valid)
        {
            break;
        }
        if(candidate.has_action)
        {
            event = candidate;
            break;
        }
    }
    assert(event.valid);
    assert(event.has_action);
    assert(event.direct_attack);
    assert(! event.ninja_tool);
    assert(event.action_id == direct_attack_ability_id);
    assert(event.target_id == 4);
}
