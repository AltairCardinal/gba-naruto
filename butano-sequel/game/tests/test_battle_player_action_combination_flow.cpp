#include "konoha/battle_player_action_flow.h"
#include "konoha/generated_battle_unit_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_unit_instance naruto = instantiate_unit(
            unit_definitions[1],
            1,
            battle_side::player,
            battle_control::player,
            { 2, 2 },
            battle_facing::right,
            50);
    naruto.primary_action_levels[7] = 1;
    naruto.chakra = 20;
    naruto.max_chakra = 20;
    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::ai,
            { 3, 2 },
            battle_facing::left,
            1);
    enemy.hp = 500;
    enemy.max_hp = 500;

    battle_session<2> session;
    assert(session.add_unit(naruto));
    assert(session.add_unit(enemy));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);

    battle_player_action_flow<2> flow;
    assert(flow.begin(session).success());
    assert(flow.select_command(
                   battle_command_type::ability)
                   .success());

    battle_action_access_policy combination_only;
    combination_only.restrict_active_actions = true;
    combination_only.allowed_active_actions[0] = 9;
    combination_only.allowed_active_actions[1] = 5;
    combination_only.allowed_active_action_count = 2;
    combination_only.allow_ninja_tools = false;
    assert(flow.open_action_selection(
                   session,
                   combination_only,
                   9)
                   .success());

    const battle_session<2> before_first_component = session;
    assert(flow.confirm_action_selection(session).success());
    assert(session == before_first_component);
    assert(flow.snapshot().phase ==
           battle_player_action_phase::action_selection);
    assert(flow.snapshot().combination_component_count == 1);
    assert(flow.snapshot().combination_first_action_id == 9);
    assert(flow.snapshot().combination_reserved_chakra == 5);
    assert(flow.snapshot()
                   .action_entries[
                           static_cast<std::size_t>(
                                   flow.snapshot()
                                           .action_index)]
                   .selection_error ==
           action_error::invalid_definition);

    assert(flow.cycle_action(1).success());
    assert(flow.snapshot().selected_action_id == 5);
    assert(flow.snapshot()
                   .action_entries[
                           static_cast<std::size_t>(
                                   flow.snapshot()
                                           .action_index)]
                   .selectable());
    assert(flow.confirm_action_selection(session).success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::target_selection);
    assert(flow.snapshot().combination_component_count == 2);
    assert(flow.snapshot().combination_result_action_id == 11);
    assert(flow.preview_target(session, { 3, 2 }).success());
    assert(flow.snapshot().target_preview.hit_count == 5);

    deterministic_rng rng(7);
    battle_condition_variant no_conditions;
    const battle_player_action_flow_result resolved =
            flow.confirm_target(
                    session,
                    { 3, 2 },
                    rng,
                    no_conditions);
    assert(resolved.success());
    assert(resolved.impact_count == 5);
    assert(session.unit(1)->chakra == 15);
    assert(session.unit(1)->ledger.acted);
    assert(session.lifecycle() ==
           battle_lifecycle::facing_select);
}
