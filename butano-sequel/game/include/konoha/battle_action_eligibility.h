#ifndef KONOHA_BATTLE_ACTION_ELIGIBILITY_H
#define KONOHA_BATTLE_ACTION_ELIGIBILITY_H

#include "konoha/battle_action_identity.h"
#include "konoha/battle_session.h"

#include <cstdint>

namespace konoha
{

struct action_requirement
{
    std::uint8_t reason_code = 0;

    [[nodiscard]] constexpr bool available() const
    {
        return reason_code == 0;
    }
};

class battle_action_eligibility
{
public:
    [[nodiscard]] static action_requirement query(
            const battle_unit_instance& actor,
            ability_id action_id,
            battle_action_source_kind source_kind =
                    battle_action_source_kind::active_action)
    {
        if(source_kind != battle_action_source_kind::active_action)
        {
            return {};
        }
        if(action_id < 43 || action_id > 49)
        {
            return {};
        }

        const std::uint8_t status_index = actor.statuses.find(0x13);
        const status_record* stage_status =
                status_index == no_status_slot ?
                nullptr : actor.statuses.active(status_index);
        const bool has_stage = stage_status != nullptr;
        const std::uint16_t stage =
                has_stage ? stage_status->value_u16 : 0;
        if(action_id == 43)
        {
            return { static_cast<std::uint8_t>(has_stage ? 9 : 0) };
        }
        if(action_id >= 44 && action_id <= 47)
        {
            const std::uint16_t required_stage =
                    static_cast<std::uint16_t>(action_id - 43);
            if(stage < required_stage)
            {
                return {
                    static_cast<std::uint8_t>(10 + (required_stage - 1) * 2),
                };
            }
            if(stage > required_stage)
            {
                return {
                    static_cast<std::uint8_t>(11 + (required_stage - 1) * 2),
                };
            }
            return {};
        }
        if(action_id == 48)
        {
            if(! has_stage)
            {
                return { 18 };
            }
            return { static_cast<std::uint8_t>(stage > 2 ? 19 : 0) };
        }
        return { static_cast<std::uint8_t>(! has_stage || stage <= 2 ? 20 : 0) };
    }
};

}

#endif
