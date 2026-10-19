#ifndef KONOHA_BATTLE_RESOURCE_COMMANDS_H
#define KONOHA_BATTLE_RESOURCE_COMMANDS_H

#include "konoha/battle_commands.h"

#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_resource_command_type : std::uint8_t
{
    replenish_chakra,
    rest,
};

enum class battle_resource_command_error : std::uint8_t
{
    none,
    invalid_phase,
    invalid_unit,
    invalid_amount,
    already_moved,
    already_acted,
    full_chakra,
    full_health,
    insufficient_health,
};

struct battle_resource_command_preview
{
    battle_resource_command_error error =
            battle_resource_command_error::none;
    int amount = 0;
    int maximum_amount = 0;
    int hp_delta = 0;
    int chakra_delta = 0;

    [[nodiscard]] constexpr bool legal() const
    {
        return error == battle_resource_command_error::none;
    }
};

class battle_resource_commands
{
public:
    [[nodiscard]] static battle_resource_command_preview preview(
            const battle_unit_instance& unit,
            battle_resource_command_type type,
            int amount = 1,
            bool movement_previewed = false)
    {
        if(! unit.active || unit.hp <= 0)
        {
            return {
                battle_resource_command_error::invalid_unit,
            };
        }
        if(unit.ledger.moved || movement_previewed)
        {
            return {
                battle_resource_command_error::already_moved,
            };
        }
        if(unit.ledger.acted)
        {
            return {
                battle_resource_command_error::already_acted,
            };
        }

        if(type == battle_resource_command_type::rest)
        {
            if(amount != 1)
            {
                return {
                    battle_resource_command_error::invalid_amount,
                };
            }
            if(unit.hp >= unit.max_hp)
            {
                return {
                    battle_resource_command_error::full_health,
                };
            }
            int restored = unit.max_hp / 5;
            const int missing = unit.max_hp - unit.hp;
            if(restored > missing)
            {
                restored = missing;
            }
            return {
                battle_resource_command_error::none,
                1,
                1,
                restored,
                0,
            };
        }

        if(unit.chakra >= unit.max_chakra)
        {
            return {
                battle_resource_command_error::full_chakra,
            };
        }
        const int cost = unit.hand_seals > 0 ?
                unit.hand_seals : 0;
        const int chakra_room =
                unit.max_chakra - unit.chakra;
        const int health_limit = cost == 0 ?
                chakra_room : (unit.hp - 1) / cost;
        const int maximum = chakra_room < health_limit ?
                chakra_room : health_limit;
        if(maximum <= 0)
        {
            return {
                battle_resource_command_error::
                        insufficient_health,
            };
        }
        if(amount <= 0 || amount > maximum)
        {
            return {
                battle_resource_command_error::invalid_amount,
                amount,
                maximum,
            };
        }
        return {
            battle_resource_command_error::none,
            amount,
            maximum,
            -cost * amount,
            amount,
        };
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_resource_command_preview preview(
            const battle_session<MaxUnits>& session,
            battle_resource_command_type type,
            int amount = 1)
    {
        if(session.lifecycle() !=
                        battle_lifecycle::action_drafting ||
                ! session.draft().active)
        {
            return {
                battle_resource_command_error::invalid_phase,
            };
        }
        const battle_unit_instance* unit =
                session.unit(session.draft().unit_id);
        if(! unit || ! unit->active || unit->hp <= 0)
        {
            return {
                battle_resource_command_error::invalid_unit,
            };
        }
        return preview(
                *unit,
                type,
                amount,
                session.draft().move_previewed);
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_resource_command_preview commit(
            battle_session<MaxUnits>& session,
            battle_resource_command_type type,
            int amount = 1)
    {
        battle_session<MaxUnits> next = session;
        const battle_resource_command_preview result =
                commit_in_place(next, type, amount);
        if(result.legal())
        {
            session = next;
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_resource_command_preview
    commit_in_place(
            battle_session<MaxUnits>& session,
            battle_resource_command_type type,
            int amount = 1)
    {
        const battle_resource_command_preview result =
                preview(session, type, amount);
        if(! result.legal())
        {
            return result;
        }

        battle_unit_instance* unit =
                session._find_unit(session._draft.unit_id);
        if(! unit)
        {
            return {
                battle_resource_command_error::invalid_unit,
            };
        }
        unit->hp += result.hp_delta;
        unit->chakra += result.chakra_delta;
        unit->ledger.acted = true;
        return result;
    }
};

}

#endif
