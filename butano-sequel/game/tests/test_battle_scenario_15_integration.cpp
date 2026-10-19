#include "konoha/battle_action_system.h"
#include "konoha/battle_conditions.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/battle_turn_flow.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>

using namespace konoha;

namespace
{

action_definition lethal_enemy_attack()
{
    action_definition result;
    result.id = 1;
    result.effect = { 0x01, 0, 255, 1, 100, 0 };
    result.target = { target_policy_kind::opponent_unit, 0 };
    result.range = { 20, 1 };
    return result;
}

void complete_wait(
        battle_session<21>& session,
        battle_unit_id id,
        battle_transition expected)
{
    assert(session.select_unit(id) ==
           battle_transition::action_draft_opened);
    assert(session.open_facing_selection() ==
           battle_transition::facing_selection_opened);
    assert(session.select_facing(battle_facing::up) ==
           battle_transition::defense_selection_opened);
    const battle_turn_flow_result completed =
            battle_turn_flow::complete_defense(
                    session,
                    no_ability,
                    battle_condition_variants[15][0]);
    assert(completed.error == battle_turn_flow_error::none);
    assert(completed.outcome == battle_condition_outcome::none);
    assert(completed.transition == expected);
}

}

int main()
{
    battle_scenario_load_policy policy;
    policy.scripted_characters[30] = true;

    battle_session<21> session;
    const battle_scenario_load_result loaded = load_battle_scenario(
            battle_scenario_definitions[15], 0, policy, session);
    assert(loaded.error == battle_scenario_load_error::none);
    assert(session.unit_count() == 9);
    assert(session.start_round() == battle_transition::unit_selection_opened);
    assert(session.cycle_roster_unit(3, 1)->id == 4);
    assert(! session.can_issue_commands(4));
    assert(session.select_unit(4) == battle_transition::invalid);

    complete_wait(session, 1, battle_transition::unit_completed);
    complete_wait(session, 2, battle_transition::unit_completed);
    complete_wait(session, 3, battle_transition::side_changed);
    assert(session.current_side() == battle_side::enemy);

    assert(session.select_unit(5) == battle_transition::action_draft_opened);
    deterministic_rng rng(1);
    const action_result attacked = battle_action_resolver::resolve_draft(
            session,
            4,
            no_battle_unit,
            lethal_enemy_attack(),
            session.unit(4)->position,
            rng);
    assert(attacked.success());
    assert(! session.unit(4)->active);

    const battle_turn_flow_result loss =
            battle_turn_flow::after_effects(
                    session, battle_condition_variants[15][0]);
    assert(loss.error == battle_turn_flow_error::none);
    assert(loss.outcome == battle_condition_outcome::loss);
    assert(loss.ends_battle);
    assert(loss.transition == battle_transition::none);
    assert(session.lifecycle() == battle_lifecycle::effects_resolved);
    assert(! session.unit(5)->ledger.completed);
}
