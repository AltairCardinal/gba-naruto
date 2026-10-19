#include "konoha/battle_capture_policy.h"
#include "konoha/battle_action_execution.h"
#include "konoha/battle_encounter_runtime.h"
#include "konoha/battle_mission_rules.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_session<12> session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[9],
                   0,
                   {},
                   session)
                   .error == battle_scenario_load_error::none);
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(2) ==
           battle_transition::action_draft_opened);

    battle_unit_instance* cat =
            const_cast<battle_unit_instance*>(
                    session.unit(4));
    assert(cat);
    cat->position = { 9, 14 };
    assert(cat->character_id == 41);
    assert(cat->hp == 1);
    assert(! cat->captured);

    deterministic_rng rng(7);
    const action_result fire =
            battle_action_execution::resolve_in_place(
                    session,
                    active_action_definitions[16],
                    cat->position,
                    rng);
    assert(fire.success());
    assert(fire.defeated);
    assert(! cat->active);
    assert(! cat->captured);

    const battle_capture_policy policy = {
        true,
        battle_side::enemy,
        41,
        true,
        true,
        false,
    };
    const battle_capture_summary captured =
            battle_capture_system::apply(
                    session,
                    policy,
                    battle_action_source_kind::active_action,
                    fire);
    assert(captured.count == 1);
    assert(captured.unit_ids[0] == cat->id);
    assert(cat->captured);
    assert(cat->character_id == 0);
    assert(cat->original_character_id == 41);

    battle_session<12> direct_attack_session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[9],
                   0,
                   {},
                   direct_attack_session)
                   .error == battle_scenario_load_error::none);
    battle_unit_instance* direct_cat =
            const_cast<battle_unit_instance*>(
                    direct_attack_session.unit(4));
    assert(direct_cat);
    direct_cat->active = false;

    action_result direct_hit;
    direct_hit.damage_steps[0] = {
        direct_cat->id,
        1,
        0,
        false,
        true,
        1,
    };
    direct_hit.damage_step_count = 1;
    const battle_capture_summary rejected =
            battle_capture_system::apply(
                    direct_attack_session,
                    policy,
                    battle_action_source_kind::direct_attack,
                    direct_hit);
    assert(rejected.count == 0);
    assert(! direct_cat->captured);

    battle_session<12> combination_session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[9],
                   0,
                   {},
                   combination_session)
                   .error == battle_scenario_load_error::none);
    battle_unit_instance* combination_cat_a =
            const_cast<battle_unit_instance*>(
                    combination_session.unit(4));
    battle_unit_instance* combination_cat_b =
            const_cast<battle_unit_instance*>(
                    combination_session.unit(5));
    assert(combination_cat_a);
    assert(combination_cat_b);
    combination_cat_a->active = false;
    combination_cat_b->active = false;

    action_result combination_damage;
    combination_damage.damage_steps[0] = {
        combination_cat_a->id,
        1,
        0,
        false,
        true,
        1,
    };
    combination_damage.damage_steps[1] =
            combination_damage.damage_steps[0];
    combination_damage.damage_steps[2] = {
        combination_cat_b->id,
        1,
        0,
        false,
        true,
        1,
    };
    combination_damage.damage_step_count = 3;
    const battle_capture_source active_and_tool = {
        {
            battle_action_source_kind::active_action,
            battle_action_source_kind::ninja_tool,
        },
        2,
    };

    battle_capture_policy active_only_policy = policy;
    active_only_policy.allow_ninja_tools = false;
    assert(battle_capture_system::apply(
                   combination_session,
                   active_only_policy,
                   active_and_tool,
                   combination_damage)
                   .count == 0);
    assert(! combination_cat_a->captured);
    assert(! combination_cat_b->captured);

    battle_capture_policy tool_only_policy = policy;
    tool_only_policy.allow_active_actions = false;
    assert(battle_capture_system::apply(
                   combination_session,
                   tool_only_policy,
                   active_and_tool,
                   combination_damage)
                   .count == 0);
    assert(! combination_cat_a->captured);
    assert(! combination_cat_b->captured);

    const battle_capture_summary combination_captured =
            battle_capture_system::apply(
                    combination_session,
                    policy,
                    active_and_tool,
                    combination_damage);
    assert(combination_captured.count == 2);
    assert(combination_captured.unit_ids[0] ==
           combination_cat_a->id);
    assert(combination_captured.unit_ids[1] ==
           combination_cat_b->id);
    assert(combination_cat_a->captured);
    assert(combination_cat_b->captured);

    battle_encounter_runtime<12, 16, 32> encounter;
    assert(encounter.load(
                   battle_scenario_definitions[9],
                   battle_map_definitions[9],
                   battle_map_cells,
                   0,
                   {},
                   battle_condition_variants[9][0],
                   7,
                   nullptr,
                   0,
                   battle_mission_rules_for(9, 0))
                   .success());
    battle_session<12>& encounter_session =
            const_cast<battle_session<12>&>(
                    encounter.session());
    battle_unit_instance* encounter_cat =
            const_cast<battle_unit_instance*>(
                    encounter_session.unit(4));
    assert(encounter_cat);
    encounter_cat->position = { 9, 14 };
    assert(encounter.start() ==
           battle_transition::unit_selection_opened);
    assert(encounter.begin_player_unit(2).success());
    assert(encounter.select_command(
                   battle_command_type::ability)
                   .success());
    assert(encounter.open_action_selection(
                   {}, 16)
                   .success());
    assert(encounter.confirm_action_selection().success());
    if(encounter.player_snapshot().phase ==
            battle_player_action_phase::
                    combination_decision)
    {
        assert(encounter.cycle_combination_decision(1).success());
        assert(encounter.confirm_combination_decision().success());
    }
    assert(encounter.player_snapshot().phase ==
           battle_player_action_phase::target_selection);
    assert(encounter.preview_target({ 9, 14 }).success());
    const battle_player_action_flow_result integrated =
            encounter.confirm_target({ 9, 14 });
    assert(integrated.success());
    assert(integrated.capture_count == 1);
    assert(encounter.session().unit(4)->captured);
    assert(! encounter.session().unit(4)->active);
    assert(! integrated.ends_battle);

    battle_scenario_load_policy ninja_tool_load_policy;
    ninja_tool_load_policy
            .character_equipped_tools_overridden[1] = true;
    ninja_tool_load_policy
            .character_equipped_tools[1][0] = 1;
    battle_encounter_runtime<12, 16, 32>
            ninja_tool_encounter;
    assert(ninja_tool_encounter.load(
                   battle_scenario_definitions[9],
                   battle_map_definitions[9],
                   battle_map_cells,
                   0,
                   ninja_tool_load_policy,
                   battle_condition_variants[9][0],
                   7,
                   nullptr,
                   0,
                   battle_mission_rules_for(9, 0))
                   .success());
    battle_session<12>& ninja_tool_session =
            const_cast<battle_session<12>&>(
                    ninja_tool_encounter.session());
    battle_unit_instance* ninja_tool_cat =
            const_cast<battle_unit_instance*>(
                    ninja_tool_session.unit(4));
    assert(ninja_tool_cat);
    ninja_tool_cat->position = { 11, 14 };
    assert(ninja_tool_encounter.start() ==
           battle_transition::unit_selection_opened);
    assert(ninja_tool_encounter.begin_player_unit(1).success());
    assert(ninja_tool_encounter.select_command(
                   battle_command_type::ability)
                   .success());
    assert(ninja_tool_encounter
                   .open_action_selection()
                   .success());
    std::size_t ninja_tool_cycle_guard = 0;
    while((ninja_tool_encounter.player_snapshot()
                          .selected_action_kind !=
                                  battle_action_source_kind::
                                          ninja_tool ||
           ninja_tool_encounter.player_snapshot()
                           .selected_action_id != 1) &&
            ninja_tool_cycle_guard++ <
                    battle_action_catalog_capacity)
    {
        assert(ninja_tool_encounter.cycle_action(1).success());
    }
    assert(ninja_tool_encounter.player_snapshot()
                   .selected_action_kind ==
           battle_action_source_kind::ninja_tool);
    assert(ninja_tool_encounter.player_snapshot()
                   .selected_action_id == 1);
    assert(ninja_tool_encounter
                   .confirm_action_selection()
                   .success());
    assert(ninja_tool_encounter.player_snapshot().phase ==
           battle_player_action_phase::target_selection);
    assert(ninja_tool_encounter
                   .preview_target({ 11, 14 })
                   .success());
    const battle_player_action_flow_result
            ninja_tool_capture =
                    ninja_tool_encounter.confirm_target(
                            { 11, 14 });
    assert(ninja_tool_capture.success());
    assert(ninja_tool_capture.capture_count == 1);
    assert(ninja_tool_encounter.session().unit(4)->captured);
    assert(ninja_tool_encounter.session().unit(1)->
                   equipped_tools[0] == no_ninja_tool);

    battle_encounter_runtime<12, 16, 32>
            naruto_encounter;
    assert(naruto_encounter.load(
                   battle_scenario_definitions[9],
                   battle_map_definitions[9],
                   battle_map_cells,
                   0,
                   {},
                   battle_condition_variants[9][0],
                   7,
                   nullptr,
                   0,
                   battle_mission_rules_for(9, 0))
                   .success());
    battle_session<12>& naruto_session =
            const_cast<battle_session<12>&>(
                    naruto_encounter.session());
    battle_unit_instance* shadow_clone_cat =
            const_cast<battle_unit_instance*>(
                    naruto_session.unit(4));
    assert(shadow_clone_cat);
    shadow_clone_cat->position = { 11, 14 };
    assert(naruto_encounter.start() ==
           battle_transition::unit_selection_opened);
    assert(naruto_encounter.begin_player_unit(1).success());
    assert(naruto_encounter.select_command(
                   battle_command_type::ability)
                   .success());
    assert(naruto_encounter.open_action_selection(
                   {}, 7)
                   .success());
    const battle_player_action_flow_snapshot&
            capture_catalog =
                    naruto_encounter.player_snapshot();
    assert(capture_catalog.selected_action_id == 7);
    assert(capture_catalog.action_entries[
                   static_cast<std::size_t>(
                           capture_catalog.action_index)]
                   .effect_code == 1);
    assert(capture_catalog.action_entries[
                   static_cast<std::size_t>(
                           capture_catalog.action_index)]
                   .target_kind ==
           target_policy_kind::opponent_unit);
    assert(naruto_encounter
                   .confirm_action_selection()
                   .success());
    assert(naruto_encounter.player_snapshot().phase ==
           battle_player_action_phase::target_selection);
    assert(naruto_encounter
                   .preview_target({ 11, 14 })
                   .success());
    const battle_player_action_flow_result
            shadow_clone_capture =
                    naruto_encounter.confirm_target(
                            { 11, 14 });
    assert(shadow_clone_capture.success());
    assert(shadow_clone_capture.capture_count == 1);
    assert(naruto_encounter.session().unit(4)->captured);
    assert(naruto_encounter.session().unit(4)->character_id == 0);
}
