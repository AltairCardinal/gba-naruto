#include "konoha/battle_campaign_scene_progression.h"
#include "konoha/battle_campaign_save.h"
#include "konoha/battle_scene_controller.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"
#include "konoha/scenario_41_definition.h"

#include <cassert>

using namespace konoha;

namespace
{

using controller_type = battle_scene_controller<12, 16, 32>;

void move_to(controller_type& controller, grid_point target)
{
    grid_point cursor = controller.snapshot().cursor;
    while(cursor.x != target.x)
    {
        assert(controller.move_cursor(
                   cursor.x < target.x ? 1 : -1, 0)
                       .success());
        cursor = controller.snapshot().cursor;
    }
    while(cursor.y != target.y)
    {
        assert(controller.move_cursor(
                   0, cursor.y < target.y ? 1 : -1)
                       .success());
        cursor = controller.snapshot().cursor;
    }
}

grid_point active_position(
        const controller_type& controller,
        battle_side side)
{
    const battle_scene_snapshot<12> state =
            controller.snapshot();
    for(std::size_t index = 0;
            index < state.unit_count; ++index)
    {
        if(state.units[index].side == side &&
                state.units[index].active)
        {
            return state.units[index].position;
        }
    }
    assert(false);
    return {};
}

void finish_without_action(
        controller_type& controller,
        grid_point destination)
{
    assert(controller.snapshot().phase ==
           battle_scene_phase::unit_selection);
    assert(controller.confirm().success());
    move_to(controller, destination);
    assert(controller.confirm().success());
    while(controller.snapshot().player.selected_command !=
            battle_command_type::end_action)
    {
        assert(controller.move_cursor(0, 1).success());
    }
    assert(controller.confirm().success());
    assert(controller.confirm().success());
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::enemy_turn);
    assert(controller.tick().success());
}

}

int main()
{
    battle_campaign_state campaign =
            empty_battle_campaign();
    const std::array<
            character_progression_record,
            3> initial_roster =
                    scenario_41_initial_roster();
    assert(activate_battle_campaign_character(
            campaign, initial_roster[0]));
    assert(set_battle_campaign_party(
            campaign, { 1, 0, 0 }));
    const battle_campaign_state campaign_before_battle =
            campaign;
    battle_campaign_scene_progression
            scene_progression;
    assert(scene_progression.begin(campaign) ==
           battle_campaign_error::none);

    battle_scenario_load_policy policy;
    policy.preserve_empty_unit_slots = true;
    controller_type controller;
    assert(controller.load(
                   battle_scenario_definitions[41],
                   battle_map_definitions[41],
                   battle_map_cells,
                   0,
                   policy,
                   battle_condition_variants[41][0],
                   0x41U,
                   scene_progression.records(),
                   false,
                   battle_mission_rules_for(41, 0))
                   .success());
    assert(controller.start().success());

    // Rounds 1–3: the first tutorial turn is stationary, then Naruto chases
    // Konohamaru through the shared move/AI turn flow.
    finish_without_action(controller, { 4, 10 });
    assert(controller.snapshot().round == 2);
    assert(active_position(
                   controller,
                   battle_side::enemy) !=
           grid_point({ 4, 4 }));
    finish_without_action(controller, { 4, 7 });
    assert(controller.snapshot().round == 3);
    assert(active_position(controller, battle_side::player) ==
           grid_point({ 4, 7 }));
    finish_without_action(controller, { 5, 6 });
    assert(controller.snapshot().round == 4);
    assert(active_position(controller, battle_side::player) ==
           grid_point({ 5, 6 }));

    // Round 4: move next to Konohamaru and use the only mission-legal
    // taijutsu action.
    const grid_point enemy_position =
            active_position(
                    controller,
                    battle_side::enemy);
    const grid_point adjacent_position = {
        enemy_position.x,
        enemy_position.y + 1,
    };
    assert(controller.confirm().success());
    move_to(controller, adjacent_position);
    assert(controller.confirm().success());
    assert(controller.confirm().success());
    assert(controller.snapshot().player.action_count == 1);
    assert(controller.snapshot().player.selected_action_id == 5);
    assert(controller.confirm().success());
    move_to(
            controller,
            active_position(controller, battle_side::enemy));
    assert(controller.confirm().success());
    assert(controller.snapshot().round == 4);
    assert(controller.snapshot().phase ==
           battle_scene_phase::outcome);

    assert(controller.confirm().success());
    battle_scene_snapshot<12> result = controller.snapshot();
    assert(result.phase == battle_scene_phase::result);
    assert(controller.result_snapshot().participant_count == 1);
    assert(controller.result_snapshot()
                   .participants[0]
                   .mission_experience == 100);
    assert(controller.result_snapshot()
                   .participants[0]
                   .battle_experience == 50);
    assert(controller.result_snapshot()
                   .participants[0]
                   .round_bonus_experience == 0);
    assert(controller.result_snapshot()
                   .participants[0]
                   .total_experience == 150);
    assert(controller.progression_roster()[0].level == 1);
    assert(controller.progression_roster()[0].experience == 100);
    assert(campaign == campaign_before_battle);

    assert(controller.confirm().success());
    result = controller.snapshot();
    assert(result.phase == battle_scene_phase::level_up);
    assert(result.result_participant_index == 0);
    assert(result.level_up_detail_page == 0);
    assert(controller.progression_roster()[0].level == 2);
    assert(controller.progression_roster()[0].experience == 0);
    assert(controller.progression_roster()[0].training_points == 1);
    assert(controller.result_snapshot()
                   .participants[0]
                   .stat_growth.max_hp == 14);

    assert(controller.confirm().success());
    result = controller.snapshot();
    assert(result.phase == battle_scene_phase::level_up);
    assert(result.result_participant_index == 0);
    assert(result.level_up_detail_page == 1);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::training);
    while(controller.training_snapshot()
                    .selected_action_id != 8)
    {
        assert(controller.move_cursor(0, 1).success());
    }
    assert(controller.training_snapshot()
                   .selected_level ==
           unlocked_action_level);
    assert(controller.confirm().success());
    assert(controller.progression_roster()[0]
                   .primary_action_levels[6] == 1);
    assert(controller.progression_roster()[0]
                   .training_points == 0);
    assert(controller.training_snapshot()
                   .selected_level == 1);
    while(controller.training_snapshot()
                    .selected_kind !=
            battle_training_entry_kind::
                    secondary_passive)
    {
        assert(controller.move_cursor(0, 1).success());
    }
    const battle_training_snapshot passive_training =
            controller.training_snapshot();
    assert(passive_training.selected_passive_id == 1);
    assert(passive_training.selected_slot_index == 0);
    assert(passive_training.selected_level ==
           locked_action_level);
    const character_progression_record
            before_locked_passive =
                    controller.progression_roster()[0];
    assert(controller.confirm().success());
    assert(controller.training_snapshot().last_error ==
           action_training_error::locked);
    assert(controller.progression_roster()[0] ==
           before_locked_passive);
    assert(controller.cancel().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::complete);

    scene_progression.records() =
            controller.progression_roster();
    assert(scene_progression.commit(campaign) ==
           battle_campaign_error::none);
    const character_progression_record& persisted =
            campaign.characters[1].progression;
    assert(persisted.level == 2);
    assert(persisted.experience == 0);
    assert(persisted.training_points == 0);
    assert(persisted.primary_action_levels[6] == 1);

    battle_campaign_state changed_party = campaign;
    assert(activate_battle_campaign_character(
            changed_party,
            character_progression_record{
                2, 1, 0, 0, true,
            }));
    assert(set_battle_campaign_party(
            changed_party, { 2, 0, 0 }));
    const battle_campaign_state before_rejected_commit =
            changed_party;
    assert(scene_progression.commit(changed_party) ==
           battle_campaign_error::party_mismatch);
    assert(changed_party == before_rejected_commit);

    battle_campaign_state sasuke_campaign =
            empty_battle_campaign();
    character_progression_record locked_sasuke = {
        2, 50, 0, 1, true,
    };
    assert(initialize_character_action_progression(
            locked_sasuke, unit_definitions[2]));
    assert(
            locked_sasuke.primary_action_levels[10] ==
            locked_action_level);
    assert(activate_battle_campaign_character(
            sasuke_campaign, locked_sasuke));
    assert(set_battle_campaign_party(
            sasuke_campaign, { 2, 0, 0 }));
    battle_campaign_scene_progression
            sasuke_scene_progression;
    assert(sasuke_scene_progression.begin(
                   sasuke_campaign) ==
           battle_campaign_error::none);

    battle_scene_controller<12, 11, 21>
            battle_31_controller;
    assert(battle_31_controller.load(
                   battle_scenario_definitions[31],
                   battle_map_definitions[31],
                   battle_map_cells,
                   0,
                   policy,
                   battle_condition_variants[31][0],
                   0x31U,
                   sasuke_scene_progression.records())
                   .success());
    assert(
            battle_31_controller.progression_roster()[0]
                    .primary_action_levels[10] ==
            unlocked_action_level);
    sasuke_scene_progression.records() =
            battle_31_controller.progression_roster();
    assert(sasuke_scene_progression.commit(
                   sasuke_campaign) ==
           battle_campaign_error::none);
    assert(sasuke_campaign.characters[2]
                   .progression.primary_action_levels[10] ==
           unlocked_action_level);

    battle_campaign_save_slot sasuke_slot;
    assert(encode_battle_campaign_slot(
                   sasuke_campaign, 1, sasuke_slot) ==
           battle_campaign_save_error::none);
    const battle_campaign_save_decode_result
            decoded_sasuke =
                    decode_battle_campaign_slot(
                            sasuke_slot);
    assert(decoded_sasuke.error ==
           battle_campaign_save_error::none);
    assert(decoded_sasuke.campaign.characters[2]
                   .progression.primary_action_levels[10] ==
           unlocked_action_level);

    battle_campaign_state tool_campaign =
            empty_battle_campaign();
    assert(activate_battle_campaign_character(
            tool_campaign, initial_roster[0]));
    assert(set_battle_campaign_party(
            tool_campaign, { 1, 0, 0 }));
    tool_campaign.characters[1].equipped_tools = {
        37,
        11,
    };
    tool_campaign.inventory.ninja_tools[37] = 1;
    tool_campaign.inventory.ninja_tools[11] = 1;
    battle_campaign_scene_progression
            tool_scene_progression;
    assert(tool_scene_progression.begin(tool_campaign) ==
           battle_campaign_error::none);
    battle_scenario_load_policy tool_policy;
    tool_policy.preserve_empty_unit_slots = true;
    assert(apply_battle_campaign_scene_policy(
                   tool_campaign, tool_policy) ==
           battle_campaign_error::none);
    controller_type tool_controller;
    assert(tool_controller.load(
                   battle_scenario_definitions[41],
                   battle_map_definitions[41],
                   battle_map_cells,
                   0,
                   tool_policy,
                   battle_condition_variants[41][0],
                   0x37U,
                   tool_scene_progression.records())
                   .success());
    assert(tool_controller.start().success());
    assert(tool_controller.confirm().success());
    assert(tool_controller.confirm().success());
    assert(tool_controller.confirm().success());
    while(
            tool_controller.snapshot()
                            .player.selected_action_kind !=
                    battle_action_source_kind::ninja_tool ||
            tool_controller.snapshot()
                            .player.selected_action_id != 37)
    {
        assert(tool_controller.move_cursor(0, 1).success());
    }
    assert(tool_controller.confirm().success());
    assert(tool_controller.move_cursor(0, -1).success());
    assert(tool_controller.confirm().success());
    const auto& settled_tools =
            tool_controller.equipped_tools_roster();
    assert(settled_tools[0][0] == no_ninja_tool);
    assert(settled_tools[0][1] == 11);

    tool_scene_progression.records() =
            tool_controller.progression_roster();
    tool_scene_progression.equipped_tools() =
            settled_tools;
    battle_campaign_state insufficient_inventory =
            tool_campaign;
    insufficient_inventory.inventory.ninja_tools[37] = 0;
    const battle_campaign_state before_inventory_failure =
            insufficient_inventory;
    assert(tool_scene_progression.commit(
                   insufficient_inventory) ==
           battle_campaign_error::inventory_mismatch);
    assert(insufficient_inventory ==
           before_inventory_failure);
    assert(tool_scene_progression.commit(tool_campaign) ==
           battle_campaign_error::none);
    assert(tool_campaign.characters[1]
                   .equipped_tools[0] ==
           no_ninja_tool);
    assert(tool_campaign.characters[1]
                   .equipped_tools[1] == 11);
    assert(tool_campaign.inventory.ninja_tools[37] == 0);
    assert(tool_campaign.inventory.ninja_tools[11] == 1);

    battle_campaign_save_slot tool_slot;
    assert(encode_battle_campaign_slot(
                   tool_campaign, 2, tool_slot) ==
           battle_campaign_save_error::none);
    const battle_campaign_save_decode_result
            decoded_tools =
                    decode_battle_campaign_slot(tool_slot);
    assert(decoded_tools.error ==
           battle_campaign_save_error::none);
    assert(decoded_tools.campaign.characters[1]
                   .equipped_tools ==
           tool_campaign.characters[1].equipped_tools);

    std::array<character_progression_record, 3>
            partially_deployed_roster = initial_roster;
    partially_deployed_roster[1] = {
        2, 1, 0, 0, true,
    };
    assert(initialize_character_action_progression(
            partially_deployed_roster[1],
            unit_definitions[2]));
    battle_scenario_load_policy
            partially_deployed_policy;
    partially_deployed_policy
            .preserve_empty_unit_slots = true;
    partially_deployed_policy
            .character_equipped_tools_overridden[1] =
                    true;
    partially_deployed_policy
            .character_equipped_tools[1] = { 37 };
    partially_deployed_policy
            .character_equipped_tools_overridden[2] =
                    true;
    partially_deployed_policy
            .character_equipped_tools[2] = { 93 };
    controller_type partially_deployed_controller;
    assert(partially_deployed_controller.load(
                   battle_scenario_definitions[41],
                   battle_map_definitions[41],
                   battle_map_cells,
                   0,
                   partially_deployed_policy,
                   battle_condition_variants[41][0],
                   0x93U,
                   partially_deployed_roster)
                   .success());
    const auto& preserved_tools =
            partially_deployed_controller
                    .equipped_tools_roster();
    assert(preserved_tools[0][0] == 37);
    assert(preserved_tools[1][0] == 93);
}
