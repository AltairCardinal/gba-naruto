#ifndef KONOHA_BATTLE_COMMAND_BROWSER_H
#define KONOHA_BATTLE_COMMAND_BROWSER_H

#include "konoha/battle_commands.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_command_browser_error : std::uint8_t
{
    none,
    invalid_phase,
    invalid_unit,
};

struct battle_command_access_policy
{
    bool allow_move = true;
    bool allow_ability = true;
    bool allow_direct_attack = true;
    bool allow_replenish_chakra = true;
    bool allow_rest = true;
    bool allow_end_action = true;
    bool confirm_move_consumes_movement = false;

    [[nodiscard]] constexpr bool allows(
            battle_command_type type) const
    {
        switch(type)
        {
        case battle_command_type::move:
            return allow_move;
        case battle_command_type::ability:
            return allow_ability;
        case battle_command_type::direct_attack:
            return allow_direct_attack;
        case battle_command_type::replenish_chakra:
            return allow_replenish_chakra;
        case battle_command_type::rest:
            return allow_rest;
        case battle_command_type::end_action:
            return allow_end_action;
        default:
            return false;
        }
    }
};

struct battle_command_browser_entry
{
    battle_command_type type =
            battle_command_type::end_action;
    command_availability availability = {
        command_state::hidden,
        command_rejection::unit_inactive,
    };

    [[nodiscard]] constexpr bool selectable() const
    {
        return availability.available();
    }
};

struct battle_command_browser_result
{
    battle_command_browser_error error =
            battle_command_browser_error::none;
    std::array<battle_command_browser_entry, 6> entries = {};
    std::size_t count = 0;
};

class battle_command_browser
{
public:
    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_command_browser_result build(
            const battle_session<MaxUnits>& session,
            const battle_command_access_policy& access = {},
            bool movement_committed = false)
    {
        if(session.lifecycle() !=
                        battle_lifecycle::action_drafting ||
                ! session.draft().active)
        {
            return {
                battle_command_browser_error::invalid_phase,
            };
        }
        const battle_unit_instance* unit =
                session.unit(session.draft().unit_id);
        if(! unit)
        {
            return {
                battle_command_browser_error::invalid_unit,
            };
        }

        battle_command_browser_result result;
        constexpr std::array<battle_command_type, 6> order = {
            battle_command_type::move,
            battle_command_type::ability,
            battle_command_type::direct_attack,
            battle_command_type::replenish_chakra,
            battle_command_type::rest,
            battle_command_type::end_action,
        };
        for(battle_command_type type : order)
        {
            if(! access.allows(type))
            {
                continue;
            }
            const command_availability availability =
                    command_eligibility_service::query(
                            *unit,
                            {
                                type,
                                0,
                                true,
                                session.draft().move_previewed ||
                                        movement_committed,
                            });
            if(availability.hidden())
            {
                continue;
            }
            result.entries[result.count] = {
                type,
                availability,
            };
            ++result.count;
        }
        return result;
    }
};

}

#endif
