#include "konoha_bench/battle_domain.h"

#include <cassert>

using namespace konoha_bench;

namespace
{

battle_unit_instance unit(
        std::uint8_t id,
        battle_side side,
        battle_control control,
        int chakra)
{
    battle_unit_instance result = {
        id,
        side,
        control,
        side == battle_side::player ?
                konoha::grid_point{ 0, 0 } :
                konoha::grid_point{ 1, 0 },
        battle_facing::right,
        30,
        30,
        chakra,
        10,
        2,
        true,
        {},
    };
    result.attack = 20;
    return result;
}

action_definition strike()
{
    action_definition result;
    result.id = 5;
    result.cost = {
        action_cost_kind::current_chakra,
        3,
        no_tool_slot,
    };
    result.effect = { 0x01, 0, 8, 1, 100, 0 };
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
    battle_session<2> battle;
    assert(battle.add_unit(unit(
            1,
            battle_side::player,
            battle_control::player,
            10)));
    assert(battle.add_unit(unit(
            2,
            battle_side::enemy,
            battle_control::ai,
            0)));
    assert(battle.start_round() ==
           battle_transition::unit_selection_opened);
    assert(battle.select_unit(1) ==
           battle_transition::action_draft_opened);
    deterministic_rng rng(7);
    const konoha::action_result applied =
            battle_action_resolver::resolve_draft(
                    battle,
                    2,
                    no_battle_unit,
                    strike(),
                    { 1, 0 },
                    rng);
    assert(applied.success());
    assert(battle.unit(1)->chakra == 7);
    assert(battle.unit(2)->hp < 30);

    battle_session<2> rejected;
    assert(rejected.add_unit(unit(
            1,
            battle_side::player,
            battle_control::player,
            2)));
    assert(rejected.add_unit(unit(
            2,
            battle_side::enemy,
            battle_control::ai,
            0)));
    assert(rejected.start_round() ==
           battle_transition::unit_selection_opened);
    assert(rejected.select_unit(1) ==
           battle_transition::action_draft_opened);
    const battle_session<2> before = rejected;
    deterministic_rng rejected_rng(7);
    const konoha::action_result failure =
            battle_action_resolver::resolve_draft(
                    rejected,
                    2,
                    no_battle_unit,
                    strike(),
                    { 1, 0 },
                    rejected_rng);
    assert(failure.error ==
           action_error::insufficient_chakra);
    assert(rejected == before);
}
