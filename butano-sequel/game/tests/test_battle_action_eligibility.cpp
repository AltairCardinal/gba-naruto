#include "konoha/battle_action_eligibility.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit()
{
    return {
        1,
        battle_side::player,
        battle_control::player,
        { 1, 1 },
        battle_facing::down,
        100,
        100,
        10,
        10,
        3,
        true,
        {},
    };
}

void set_stage(battle_unit_instance& value, std::uint16_t stage)
{
    assert(value.statuses.upsert({ 0x13, 0, 0, 0, 0, 0, stage }));
}

}

int main()
{
    battle_unit_instance actor = unit();
    assert(battle_action_eligibility::query(actor, 43).available());
    const action_requirement second_missing =
            battle_action_eligibility::query(actor, 44);
    assert(! second_missing.available());
    assert(second_missing.reason_code == 10);
    assert(battle_action_eligibility::query(actor, 48).reason_code == 18);
    assert(battle_action_eligibility::query(actor, 49).reason_code == 20);
    assert(battle_action_eligibility::query(
                   actor,
                   49,
                   battle_action_source_kind::ninja_tool).available());

    set_stage(actor, 1);
    assert(battle_action_eligibility::query(actor, 43).reason_code == 9);
    assert(battle_action_eligibility::query(actor, 44).available());
    assert(battle_action_eligibility::query(actor, 45).reason_code == 12);
    assert(battle_action_eligibility::query(actor, 48).available());
    assert(battle_action_eligibility::query(actor, 49).reason_code == 20);

    set_stage(actor, 3);
    assert(battle_action_eligibility::query(actor, 44).reason_code == 11);
    assert(battle_action_eligibility::query(actor, 46).available());
    assert(battle_action_eligibility::query(actor, 47).reason_code == 16);
    assert(battle_action_eligibility::query(actor, 48).reason_code == 19);
    assert(battle_action_eligibility::query(actor, 49).available());

    assert(battle_action_eligibility::query(actor, 42).available());
    assert(battle_action_eligibility::query(actor, 50).available());
}
