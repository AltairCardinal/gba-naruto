#include "konoha/battle_commands.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance ready_unit()
{
    return {
        1,
        battle_side::player,
        battle_control::player,
        { 2, 4 },
        battle_facing::down,
        40,
        80,
        10,
        40,
        3,
        true,
        {},
    };
}

}

int main()
{
    battle_unit_instance unit = ready_unit();
    assert(command_eligibility_service::query(unit, { battle_command_type::move }).available());

    unit.ledger.moved = true;
    command_availability move_after_move =
            command_eligibility_service::query(unit, { battle_command_type::move });
    assert(move_after_move.hidden());
    assert(move_after_move.reason == command_rejection::already_moved);

    unit = ready_unit();
    command_availability expensive = command_eligibility_service::query(
            unit, { battle_command_type::ability, 20, true });
    assert(expensive.disabled());
    assert(expensive.reason == command_rejection::insufficient_chakra);
    assert(command_eligibility_service::query(
                   unit, { battle_command_type::ability, 10, true }).available());
    command_availability no_item = command_eligibility_service::query(
            unit, { battle_command_type::ability, 0, false });
    assert(no_item.disabled());
    assert(no_item.reason == command_rejection::no_inventory);

    unit.ledger.acted = true;
    command_availability ability_after_action = command_eligibility_service::query(
            unit, { battle_command_type::ability, 0, true });
    assert(ability_after_action.hidden());
    assert(ability_after_action.reason == command_rejection::already_acted);
    assert(command_eligibility_service::query(
                   unit, { battle_command_type::end_action }).available());

    unit = ready_unit();
    assert(command_eligibility_service::query(
                   unit, { battle_command_type::replenish_chakra }).available());
    unit.chakra = unit.max_chakra;
    command_availability full_chakra = command_eligibility_service::query(
            unit, { battle_command_type::replenish_chakra });
    assert(full_chakra.disabled());
    assert(full_chakra.reason == command_rejection::full_chakra);

    unit = ready_unit();
    assert(command_eligibility_service::query(unit, { battle_command_type::rest }).available());
    unit.hp = unit.max_hp;
    command_availability full_health =
            command_eligibility_service::query(unit, { battle_command_type::rest });
    assert(full_health.disabled());
    assert(full_health.reason == command_rejection::full_health);

    unit = ready_unit();
    unit.active = false;
    command_availability inactive =
            command_eligibility_service::query(unit, { battle_command_type::end_action });
    assert(inactive.disabled());
    assert(inactive.reason == command_rejection::unit_inactive);

    unit = ready_unit();
    unit.ledger.completed = true;
    command_availability completed =
            command_eligibility_service::query(unit, { battle_command_type::end_action });
    assert(completed.hidden());
    assert(completed.reason == command_rejection::unit_completed);
}
