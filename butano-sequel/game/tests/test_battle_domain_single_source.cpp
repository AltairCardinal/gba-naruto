#include "konoha/battle_action_system.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        battle_control control,
        grid_point position)
{
    battle_unit_instance result = {
        id,
        side,
        control,
        position,
        battle_facing::down,
        40,
        40,
        10,
        10,
        3,
        true,
        {},
    };
    result.attack = 20;
    result.defense = 0;
    result.agility = 10;
    return result;
}

action_definition combo()
{
    action_definition result;
    result.id = 5;
    result.cost = {
        action_cost_kind::current_chakra,
        3,
        no_tool_slot,
    };
    result.effect = { 0x01, 0, 8, 2, 100, 0 };
    result.target = {
        target_policy_kind::opponent_unit,
        0,
    };
    result.range = { 1, 1 };
    return result;
}

}

int main()
{
    battle_session<2> session;
    assert(session.add_unit(unit(
            1,
            battle_side::player,
            battle_control::player,
            { 1, 1 })));
    assert(session.add_unit(unit(
            2,
            battle_side::enemy,
            battle_control::ai,
            { 2, 1 })));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);

    const action_definition action = combo();
    const battle_session<2> before_preview = session;
    const action_preview preview =
            battle_action_resolver::preview(
                    session,
                    2,
                    no_battle_unit,
                    action,
                    { 2, 1 });
    assert(preview.legal());
    assert(preview.hit_count == 2);
    assert(session == before_preview);

    deterministic_rng rng(7);
    const action_result resolved =
            battle_action_resolver::resolve_draft(
                    session,
                    2,
                    no_battle_unit,
                    action,
                    { 2, 1 },
                    rng);
    assert(resolved.success());
    assert(resolved.generated_hits == 2);
    assert(resolved.effective_hits == 2);
    assert(session.unit(1)->chakra == 7);
    assert(session.unit(1)->ledger.acted);
    assert(session.unit(2)->hp < 40);
    assert(session.lifecycle() ==
           battle_lifecycle::effects_resolved);

    battle_session<2> rejected;
    battle_unit_instance exhausted = unit(
            1,
            battle_side::player,
            battle_control::player,
            { 1, 1 });
    exhausted.chakra = 2;
    assert(rejected.add_unit(exhausted));
    assert(rejected.add_unit(unit(
            2,
            battle_side::enemy,
            battle_control::ai,
            { 2, 1 })));
    assert(rejected.start_round() ==
           battle_transition::unit_selection_opened);
    assert(rejected.select_unit(1) ==
           battle_transition::action_draft_opened);
    const battle_session<2> before_rejection = rejected;
    deterministic_rng rejected_rng(7);
    const action_result rejected_result =
            battle_action_resolver::resolve_draft(
                    rejected,
                    2,
                    no_battle_unit,
                    action,
                    { 2, 1 },
                    rejected_rng);
    assert(rejected_result.error ==
           action_error::insufficient_chakra);
    assert(rejected == before_rejection);
}
