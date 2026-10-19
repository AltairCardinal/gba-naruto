#include "konoha/battle_ai.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        grid_point position)
{
    battle_unit_instance result = {
        id,
        side,
        battle_control::ai,
        position,
        battle_facing::down,
        100,
        100,
        5,
        5,
        0,
        true,
        {},
    };
    result.attack = 10;
    return result;
}

}

int main()
{
    grid_map<7, 7> map;
    const battle_unit_instance actor =
            unit(1, battle_side::enemy, { 0, 0 });
    const std::array<battle_unit_instance, 3> units = {
        actor,
        unit(2, battle_side::player, { 2, 1 }),
        unit(3, battle_side::player, { 2, 2 }),
    };
    const std::array<action_definition, 1> actions = {
        action_definition{
            90,
            { action_cost_kind::current_chakra, 1, no_tool_slot },
            {},
            { 0x01, 0, 10, 1, 100, 0 },
            { target_policy_kind::opponent_unit, 0 },
            { 3, 2 },
            {},
        },
    };
    deterministic_rng plan_rng(9);
    const ai_plan plan = battle_ai::plan(
            map,
            actor,
            units,
            actions,
            actions.size(),
            {},
            plan_rng);
    assert(plan.error == ai_error::none);
    assert(plan.action == ai_action::ability);
    assert(plan.ability == 90);
    assert(plan.target_count == 2);
    assert((plan.target_position == grid_point{ 2, 1 }) ||
           (plan.target_position == grid_point{ 2, 2 }));

    battle_session<3> session;
    for(const battle_unit_instance& item : units)
    {
        assert(session.add_unit(item));
    }
    assert(session.start_round() == battle_transition::unit_selection_opened);
    // The host session starts with the player side, so use an equivalent
    // player-controlled actor to exercise the shared area resolver.
    battle_session<3> resolving_session;
    battle_unit_instance resolving_actor = actor;
    resolving_actor.side = battle_side::player;
    resolving_actor.control = battle_control::player;
    battle_unit_instance target_2 = units[1];
    target_2.side = battle_side::enemy;
    battle_unit_instance target_3 = units[2];
    target_3.side = battle_side::enemy;
    assert(resolving_session.add_unit(resolving_actor));
    assert(resolving_session.add_unit(target_2));
    assert(resolving_session.add_unit(target_3));
    assert(resolving_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(resolving_session.select_unit(1) ==
           battle_transition::action_draft_opened);
    deterministic_rng resolve_rng(1);
    const action_result result =
            battle_action_resolver::resolve_area_draft(
                    resolving_session,
                    actions[0],
                    plan.target_position,
                    resolve_rng);
    assert(result.success());
    assert(result.target_count == 2);
    assert(resolving_session.unit(2)->hp < 100);
    assert(resolving_session.unit(3)->hp < 100);
    assert(resolving_session.unit(1)->chakra == 4);
}
