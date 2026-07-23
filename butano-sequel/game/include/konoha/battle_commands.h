#ifndef KONOHA_BATTLE_COMMANDS_H
#define KONOHA_BATTLE_COMMANDS_H

#include "konoha/battle_session.h"

#include <cstdint>

namespace konoha
{

enum class battle_command_type : std::uint8_t
{
    move,
    ability,
    replenish_chakra,
    rest,
    end_action,
};

enum class command_state : std::uint8_t
{
    available,
    disabled,
    hidden,
};

enum class command_rejection : std::uint8_t
{
    none,
    unit_inactive,
    unit_completed,
    already_moved,
    already_acted,
    insufficient_chakra,
    no_inventory,
    full_chakra,
    full_health,
};

struct battle_command_query
{
    battle_command_type type;
    int chakra_cost = 0;
    bool inventory_available = true;
};

struct command_availability
{
    command_state state;
    command_rejection reason;

    [[nodiscard]] constexpr bool available() const
    {
        return state == command_state::available;
    }

    [[nodiscard]] constexpr bool disabled() const
    {
        return state == command_state::disabled;
    }

    [[nodiscard]] constexpr bool hidden() const
    {
        return state == command_state::hidden;
    }
};

class command_eligibility_service
{
public:
    [[nodiscard]] static constexpr command_availability query(
            const battle_unit_instance& unit, battle_command_query command)
    {
        if(! unit.active)
        {
            return { command_state::disabled, command_rejection::unit_inactive };
        }
        if(unit.ledger.completed)
        {
            return { command_state::hidden, command_rejection::unit_completed };
        }

        switch(command.type)
        {
        case battle_command_type::move:
            if(unit.ledger.moved)
            {
                return { command_state::hidden, command_rejection::already_moved };
            }
            if(unit.ledger.acted)
            {
                return { command_state::hidden, command_rejection::already_acted };
            }
            break;

        case battle_command_type::ability:
            if(unit.ledger.acted)
            {
                return { command_state::hidden, command_rejection::already_acted };
            }
            if(! command.inventory_available)
            {
                return { command_state::disabled, command_rejection::no_inventory };
            }
            if(command.chakra_cost > unit.chakra)
            {
                return { command_state::disabled, command_rejection::insufficient_chakra };
            }
            break;

        case battle_command_type::replenish_chakra:
            if(unit.ledger.acted)
            {
                return { command_state::hidden, command_rejection::already_acted };
            }
            if(unit.chakra >= unit.max_chakra)
            {
                return { command_state::disabled, command_rejection::full_chakra };
            }
            break;

        case battle_command_type::rest:
            if(unit.ledger.acted)
            {
                return { command_state::hidden, command_rejection::already_acted };
            }
            if(unit.hp >= unit.max_hp)
            {
                return { command_state::disabled, command_rejection::full_health };
            }
            break;

        case battle_command_type::end_action:
            break;
        }

        return { command_state::available, command_rejection::none };
    }
};

}

#endif
