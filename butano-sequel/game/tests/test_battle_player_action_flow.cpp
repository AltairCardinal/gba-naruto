#include "konoha/battle_player_action_flow.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/generated_battle_scenario_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_unit_instance command_player = instantiate_unit(
            unit_definitions[1],
            1,
            battle_side::player,
            battle_control::player,
            { 1, 1 },
            battle_facing::right,
            6);
    command_player.hp = 100;
    command_player.max_hp = 152;
    command_player.base_max_hp = 152;
    command_player.chakra = 1;
    command_player.max_chakra = 5;
    battle_unit_instance command_enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::ai,
            { 5, 1 },
            battle_facing::left,
            5);
    battle_session<2> command_session;
    assert(command_session.add_unit(command_player));
    assert(command_session.add_unit(command_enemy));
    assert(command_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(command_session.select_unit(1) ==
           battle_transition::action_draft_opened);
    battle_player_action_flow<2> command_flow;
    assert(command_flow.begin(command_session).success());
    assert(command_flow.snapshot().command_count == 6);
    assert(command_flow.snapshot().selected_command ==
           battle_command_type::move);
    const battle_session<2> before_wrong_command =
            command_session;
    assert(command_flow.open_action_selection(
                   command_session)
                   .error ==
           battle_player_action_flow_error::invalid_phase);
    assert(command_flow.end_without_action(
                   command_session)
                   .error ==
           battle_player_action_flow_error::invalid_phase);
    assert(command_session == before_wrong_command);
    grid_map<8, 8> command_map;
    command_map.set_occupied({ 1, 1 }, true);
    command_map.set_occupied({ 5, 1 }, true);

    battle_session<2> zero_move_session = command_session;
    battle_player_action_flow<2> zero_move_flow;
    assert(zero_move_flow.begin(zero_move_session).success());
    assert(zero_move_flow.open_move_selection(
                   zero_move_session)
                   .success());
    assert(zero_move_flow.preview_move(
                   zero_move_session,
                   command_map,
                   { 1, 1 })
                   .success());
    assert(zero_move_flow.confirm_move_selection(
                   zero_move_session)
                   .success());
    assert(zero_move_flow.select_command(
                   battle_command_type::move)
                   .success());
    assert(zero_move_flow.reopen_move_selection(
                   zero_move_session)
                   .success());
    assert(zero_move_flow.snapshot().phase ==
           battle_player_action_phase::move_selection);
    assert(zero_move_flow.snapshot().move_position ==
           grid_point({ 1, 1 }));
    assert(zero_move_flow.snapshot().move_cost == 0);

    battle_command_access_policy move_only;
    move_only.allow_ability = false;
    move_only.allow_replenish_chakra = false;
    move_only.allow_rest = false;
    move_only.allow_end_action = false;
    battle_session<2> move_only_session =
            command_session;
    battle_player_action_flow<2> move_only_flow;
    assert(move_only_flow.begin(
                   move_only_session, move_only)
                   .success());
    assert(move_only_flow.open_move_selection(
                   move_only_session)
                   .success());
    assert(move_only_flow.preview_move(
                   move_only_session,
                   command_map,
                   { 3, 1 })
                   .success());
    const battle_session<2> before_empty_policy_confirm =
            move_only_session;
    const battle_player_action_flow_snapshot
            before_empty_policy_snapshot =
                    move_only_flow.snapshot();
    assert(move_only_flow.confirm_move_selection(
                   move_only_session)
                   .error ==
           battle_player_action_flow_error::
                   command_browser_failed);
    assert(move_only_session == before_empty_policy_confirm);
    assert(move_only_flow.snapshot().phase ==
           before_empty_policy_snapshot.phase);
    assert(move_only_flow.snapshot().command_count ==
           before_empty_policy_snapshot.command_count);
    assert(move_only_flow.snapshot().selected_command ==
           before_empty_policy_snapshot.selected_command);
    assert(move_only_flow.snapshot().move_position ==
           before_empty_policy_snapshot.move_position);
    assert(move_only_flow.cancel_unit_action(
                   move_only_session)
                   .success());

    assert(command_flow.open_move_selection(
                   command_session)
                   .success());
    assert(command_flow.snapshot().phase ==
           battle_player_action_phase::move_selection);
    const battle_unit_instance before_move_unit =
            *command_session.unit(1);
    assert(command_flow.preview_move(
                   command_session,
                   command_map,
                   { 3, 1 })
                   .success());
    assert(command_session.unit(1)->position ==
           before_move_unit.position);
    assert(command_session.draft().preview_position ==
           grid_point({ 3, 1 }));
    assert(command_flow.cancel_move_selection(
                   command_session)
                   .success());
    assert(command_session.draft().preview_position ==
           grid_point({ 1, 1 }));
    assert(command_flow.open_move_selection(
                   command_session)
                   .success());
    assert(command_flow.preview_move(
                   command_session,
                   command_map,
                   { 3, 1 })
                   .success());
    assert(command_flow.confirm_move_selection(
                   command_session)
                   .success());
    assert(command_flow.snapshot().phase ==
           battle_player_action_phase::command_selection);
    assert(command_flow.snapshot().command_count == 2);
    assert(command_flow.snapshot().selected_command ==
           battle_command_type::ability);
    assert(command_session.unit(1)->position ==
           before_move_unit.position);

    battle_session<2> rest_session;
    command_player.hp = 24;
    command_player.max_hp = 89;
    command_player.base_max_hp = 89;
    command_player.chakra = 4;
    command_player.max_chakra = 5;
    assert(rest_session.add_unit(command_player));
    assert(rest_session.add_unit(command_enemy));
    assert(rest_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(rest_session.select_unit(1) ==
           battle_transition::action_draft_opened);
    battle_player_action_flow<2> rest_flow;
    assert(rest_flow.begin(rest_session).success());
    assert(rest_flow.select_command(
                   battle_command_type::rest)
                   .success());
    assert(rest_flow.open_rest_confirmation(
                   rest_session)
                   .success());
    assert(rest_flow.snapshot().resource_preview.hp_delta ==
           17);
    const battle_session<2> before_rest_cancel =
            rest_session;
    assert(rest_flow.cancel_rest_confirmation().success());
    assert(rest_session == before_rest_cancel);
    assert(rest_flow.open_rest_confirmation(
                   rest_session)
                   .success());
    battle_condition_variant invalid_resource_conditions;
    invalid_resource_conditions.win[0].type =
            battle_condition_type::unused_4;
    const battle_session<2> before_invalid_condition =
            rest_session;
    const battle_player_action_flow_result invalid_condition =
            rest_flow.confirm_rest(
                    rest_session,
                    invalid_resource_conditions);
    assert(invalid_condition.error ==
           battle_player_action_flow_error::
                   turn_flow_failed);
    assert(invalid_condition.turn_flow_error ==
           battle_turn_flow_error::condition_error);
    assert(rest_session == before_invalid_condition);
    assert(rest_flow.snapshot().phase ==
           battle_player_action_phase::rest_confirmation);
    battle_condition_variant no_command_conditions;
    battle_condition_variant resource_win;
    resource_win.win[0] = {
        battle_condition_type::
                no_valid_character_for_side,
        1,
        99,
        0,
    };
    const battle_player_action_flow_result rested =
            rest_flow.confirm_rest(
                    rest_session,
                    resource_win);
    assert(rested.success());
    assert(rested.outcome ==
           battle_condition_outcome::win);
    assert(rested.ends_battle);
    assert(rest_session.unit(1)->hp == 41);
    assert(! rest_session.unit(1)->ledger.completed);
    assert(rest_flow.snapshot().phase ==
           battle_player_action_phase::outcome);
    assert(rest_session.current_side() ==
           battle_side::player);

    battle_session<2> chakra_command_session;
    command_player.hp = 31;
    command_player.max_hp = 89;
    command_player.base_max_hp = 89;
    command_player.chakra = 1;
    command_player.max_chakra = 5;
    assert(chakra_command_session.add_unit(command_player));
    assert(chakra_command_session.add_unit(command_enemy));
    assert(chakra_command_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(chakra_command_session.select_unit(1) ==
           battle_transition::action_draft_opened);
    battle_player_action_flow<2> chakra_flow;
    assert(chakra_flow.begin(chakra_command_session).success());
    assert(chakra_flow.select_command(
                   battle_command_type::replenish_chakra)
                   .success());
    assert(chakra_flow.open_chakra_selection(
                   chakra_command_session)
                   .success());
    assert(chakra_flow.snapshot().resource_preview.maximum_amount ==
           2);
    assert(chakra_flow.cycle_chakra_amount(
                   chakra_command_session, 1)
                   .success());
    assert(chakra_flow.snapshot().resource_preview.amount == 2);
    const battle_player_action_flow_result replenished =
            chakra_flow.confirm_chakra_in_place(
                    chakra_command_session,
                    no_command_conditions);
    assert(replenished.success());
    assert(chakra_command_session.unit(1)->hp == 1);
    assert(chakra_command_session.unit(1)->chakra == 3);
    assert(! chakra_command_session.unit(1)->ledger.completed);
    assert(chakra_command_session.lifecycle() ==
           battle_lifecycle::facing_select);
    assert(chakra_flow.snapshot().phase ==
           battle_player_action_phase::facing_selection);
    assert(chakra_flow.select_facing(
                   chakra_command_session,
                   battle_facing::right)
                   .success());
    assert(chakra_flow.complete_without_defense(
                   chakra_command_session,
                   no_command_conditions)
                   .success());
    assert(chakra_command_session.unit(1)->ledger.completed);

    battle_scenario_load_policy fixed_pool;
    fixed_pool.preserve_empty_unit_slots = true;
    battle_session<12> session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[43],
                   0,
                   fixed_pool,
                   session)
                   .error == battle_scenario_load_error::none);
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);

    battle_player_action_flow<12> flow;
    assert(flow.begin(session).success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::command_selection);
    assert(battle_action_browser::build(session).count == 3);
    assert(flow.select_command(
                   battle_command_type::ability)
                   .success());

    battle_action_access_policy tutorial;
    tutorial.restrict_active_actions = true;
    tutorial.allowed_active_actions[0] = 7;
    tutorial.allowed_active_action_count = 1;
    tutorial.allow_ninja_tools = false;
    assert(flow.open_action_selection(
                   session, tutorial, 7)
                   .success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::action_selection);
    assert(flow.snapshot().action_count == 1);
    assert(flow.snapshot().action_entries[0].kind ==
           battle_action_source_kind::active_action);
    assert(flow.snapshot().action_entries[0].action_id == 7);
    assert(flow.snapshot().action_entries[0].action_level == 1);
    assert(flow.snapshot().action_entries[0].tool_slot ==
           no_tool_slot);
    assert(flow.snapshot().action_entries[0].action_id ==
           active_action_definitions[7].id);
    assert(flow.snapshot().action_entries[0].cost_kind ==
           active_action_definitions[7].cost.kind);
    assert(flow.snapshot().action_entries[0].cost_scalar ==
           active_action_definitions[7].cost.scalar);
    assert(flow.snapshot().action_entries[0].target_kind ==
           active_action_definitions[7].target.kind);
    assert(flow.snapshot().action_entries[0].effect_code ==
           active_action_definitions[7].effect.code);
    assert(flow.snapshot().action_entries[0].animation_family ==
           active_action_definitions[7].presentation.animation_family);
    assert(flow.snapshot().action_entries[0].selection_error ==
           action_error::none);
    assert(flow.snapshot().action_entries[0].selectable());
    assert(flow.snapshot().selected_action_id == 7);
    assert(flow.confirm_action_selection(session).success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::target_selection);

    const battle_session<12> before_preview = session;
    const battle_player_action_flow_result invalid_target =
            flow.preview_target(session, { 2, 11 });
    assert(invalid_target.error ==
           battle_player_action_flow_error::action_rejected);
    assert(invalid_target.action_rejection ==
           action_error::occupied_target_tile);
    assert(flow.snapshot().phase ==
           battle_player_action_phase::target_selection);
    assert(session == before_preview);
    assert(flow.cancel_target_selection().success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::action_selection);
    assert(flow.cancel_action_selection().success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::command_selection);
    assert(flow.open_action_selection(
                   session, tutorial, 7)
                   .success());
    assert(flow.confirm_action_selection(session).success());

    assert(flow.preview_target(session, { 4, 16 }).success());
    assert(flow.snapshot().target_preview.legal());
    assert(session == before_preview);

    deterministic_rng rng(7);
    battle_condition_variant no_conditions;
    const battle_player_action_flow_result confirmed =
            flow.confirm_target(
                    session,
                    { 4, 16 },
                    rng,
                    no_conditions);
    assert(confirmed.success());
    assert(confirmed.affected_unit_count == 1);
    assert(confirmed.affected_unit_ids[0] == 5);
    assert(confirmed.impact_count == 0);
    assert(flow.snapshot().phase ==
           battle_player_action_phase::facing_selection);
    assert(session.lifecycle() == battle_lifecycle::facing_select);
    assert(session.unit(5)->active);
    assert(session.unit(5)->summoner == 1);

    assert(flow.select_facing(
                   session, battle_facing::up)
                   .success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::defense_decision);
    battlefield_object_record expiring_visual;
    expiring_visual.type = 2;
    expiring_visual.x = 3;
    expiring_visual.y = 3;
    expiring_visual.payload_id = 37;
    expiring_visual.duration_ticks = 1;
    assert(session.objects().allocate(expiring_visual) == 1);
    deterministic_rng boundary_rng(11);
    const battle_player_action_flow_result completed =
            flow.complete_without_defense_in_place(
                    session,
                    no_conditions,
                    boundary_rng);
    assert(completed.success());
    assert(completed.object_event_count == 1);
    assert(completed.object_effects.total_damage == 0);
    assert(flow.snapshot().phase ==
           battle_player_action_phase::completed);
    assert(session.current_side() == battle_side::enemy);

    battle_unit_instance sasuke = instantiate_unit(
            unit_definitions[2],
            1,
            battle_side::player,
            battle_control::player,
            { 1, 1 },
            battle_facing::right,
            14);
    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::ai,
            { 2, 1 },
            battle_facing::left,
            1);
    // Level-gated slots become trainable at their threshold, but they do not
    // enter the battle catalog until a training point raises them to level 1.
    sasuke.primary_action_levels[8] = 1;
    battle_session<2> defense_session;
    assert(defense_session.add_unit(sasuke));
    assert(defense_session.add_unit(enemy));
    assert(defense_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(defense_session.select_unit(1) ==
           battle_transition::action_draft_opened);

    battle_player_action_flow<2> defense_flow;
    assert(defense_flow.begin(defense_session).success());
    assert(defense_flow.select_command(
                   battle_command_type::end_action)
                   .success());
    assert(defense_flow.end_without_action(
                   defense_session)
                   .success());
    assert(defense_flow.select_facing(
                   defense_session,
                   battle_facing::right)
                   .success());
    assert(defense_flow.open_defense_selection(
                   defense_session)
                   .success());
    assert(defense_flow.snapshot().defense_action_count == 4);
    const battle_session<2> before_rejected_defense =
            defense_session;
    const battle_player_action_flow_result rejected_defense =
            defense_flow.confirm_defense_action(
                    defense_session, no_conditions);
    assert(rejected_defense.error ==
           battle_player_action_flow_error::defense_rejected);
    assert(defense_session == before_rejected_defense);
    assert(defense_flow.snapshot().phase ==
           battle_player_action_phase::defense_selection);
    for(int index = 0;
            index < defense_flow.snapshot().defense_action_count &&
            defense_flow.snapshot().selected_defense_action_id != 15;
            ++index)
    {
        assert(defense_flow.cycle_defense_action(1).success());
    }
    assert(defense_flow.snapshot().selected_defense_action_id == 15);
    assert(defense_flow.snapshot().defense_confirmation_error ==
           defense_preparation_error::none);
    assert(defense_flow.cancel_defense_selection().success());
    assert(defense_flow.snapshot().phase ==
           battle_player_action_phase::defense_decision);
    assert(defense_flow.open_defense_selection(
                   defense_session)
                   .success());
    while(defense_flow.snapshot().selected_defense_action_id != 15)
    {
        assert(defense_flow.cycle_defense_action(1).success());
    }
    assert(defense_flow.confirm_defense_action_in_place(
                   defense_session, no_conditions)
                   .success());
    assert(defense_session.unit(1)->statuses.find(0x10) !=
           no_status_slot);
    assert(defense_flow.snapshot().phase ==
           battle_player_action_phase::completed);

    battle_unit_instance forced_buff_actor =
            instantiate_unit(
                    unit_definitions[1],
                    1,
                    battle_side::player,
                    battle_control::player,
                    { 1, 1 },
                    battle_facing::right,
                    20);
    forced_buff_actor.primary_action_ids = {};
    forced_buff_actor.primary_action_levels = {};
    forced_buff_actor.primary_action_ids[0] = 14;
    forced_buff_actor.primary_action_levels[0] = 1;
    forced_buff_actor.primary_action_ids[1] = 5;
    forced_buff_actor.primary_action_levels[1] = 1;
    forced_buff_actor.chakra = 9;
    forced_buff_actor.max_chakra = 9;
    battle_session<2> forced_buff_session;
    assert(forced_buff_session.add_unit(forced_buff_actor));
    assert(forced_buff_session.add_unit(enemy));
    assert(forced_buff_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(forced_buff_session.select_unit(1) ==
           battle_transition::action_draft_opened);
    battle_player_action_flow<2> forced_buff_flow;
    assert(forced_buff_flow.begin(
                   forced_buff_session).success());
    assert(forced_buff_flow.select_command(
                   battle_command_type::ability).success());
    assert(forced_buff_flow.open_action_selection(
                   forced_buff_session, {}, 14).success());
    assert(forced_buff_flow.confirm_action_selection(
                   forced_buff_session).success());
    assert(forced_buff_flow.snapshot().phase ==
           battle_player_action_phase::action_selection);
    assert(forced_buff_flow.snapshot().
                   combination_component_count == 1);
    assert(forced_buff_flow.snapshot().
                   combination_first_action_id == 14);
}
