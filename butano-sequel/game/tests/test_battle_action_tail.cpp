#include "konoha/battle_action_system.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        grid_point position)
{
    return {
        id,
        side,
        side == battle_side::player ?
                battle_control::player : battle_control::ai,
        position,
        battle_facing::down,
        100,
        100,
        5,
        5,
        3,
        true,
        {},
    };
}

action_definition attack()
{
    action_definition result;
    result.id = 1;
    result.cost = { action_cost_kind::current_chakra, 1, no_tool_slot };
    result.effect = { 0x01, 0, 10, 1, 100, 0 };
    result.target = { target_policy_kind::opponent_unit, 0 };
    result.range = { 2, 1 };
    return result;
}

}

int main()
{
    battle_session<2> session;
    assert(session.add_unit(unit(
            1, battle_side::player, { 1, 1 })));
    assert(session.add_unit(unit(
            2, battle_side::enemy, { 2, 1 })));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);
    assert(session.preview_move({ 1, 2 }) ==
           battle_transition::move_previewed);

    deterministic_rng rng(1);
    const action_result resolved = battle_action_resolver::resolve_draft(
            session,
            2,
            no_battle_unit,
            attack(),
            { 2, 1 },
            rng);
    assert(resolved.success());
    assert(session.lifecycle() == battle_lifecycle::effects_resolved);
    assert((session.unit(1)->position == grid_point{ 1, 2 }));
    assert(session.unit(1)->chakra == 4);
    assert(session.unit(1)->ledger.moved);
    assert(session.unit(1)->ledger.acted);
    assert(! session.unit(1)->ledger.completed);
    assert(session.unit(2)->hp < 100);
    assert(session.current_side() == battle_side::player);
    assert(session.draft().active);

    const battle_session<2> committed_effects = session;
    assert(session.preview_move({ 2, 2 }) == battle_transition::invalid);
    assert(session == committed_effects);
    assert(session.cancel_action() == battle_transition::invalid);
    assert(session == committed_effects);
    assert(session.select_facing(battle_facing::right) ==
           battle_transition::invalid);
    assert(session == committed_effects);
    const action_result duplicate = battle_action_resolver::resolve_draft(
            session,
            2,
            no_battle_unit,
            attack(),
            { 2, 1 },
            rng);
    assert(duplicate.error == action_error::invalid_source);
    assert(session == committed_effects);

    assert(session.open_facing_selection() ==
           battle_transition::facing_selection_opened);
    assert(session.lifecycle() == battle_lifecycle::facing_select);
    assert(session.select_facing(battle_facing::right) ==
           battle_transition::defense_selection_opened);
    assert(session.lifecycle() == battle_lifecycle::defense_select);
    assert(session.unit(1)->facing == battle_facing::right);
    assert(session.complete_action(7) == battle_transition::side_changed);
    assert(session.unit(1)->ledger.completed);
    assert(session.unit(1)->ledger.defense_ability == 7);
    assert(session.current_side() == battle_side::enemy);
    assert(session.lifecycle() == battle_lifecycle::unit_select);
    assert(! session.draft().active);
}
