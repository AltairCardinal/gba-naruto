#ifndef KONOHA_BATTLE_STATUS_POLICIES_H
#define KONOHA_BATTLE_STATUS_POLICIES_H

#include "konoha/battle_status_store.h"

#include <cstdint>

namespace konoha
{

struct status_consumption_result
{
    bool source_consumed = false;
    bool target_consumed = false;

    [[nodiscard]] constexpr int count() const
    {
        return int(source_consumed) + int(target_consumed);
    }
};

class status_consumption_policy
{
public:
    [[nodiscard]] static constexpr bool excluded(std::uint8_t event_type)
    {
        switch(event_type & 0x3F)
        {
        case 0x04:
        case 0x09:
        case 0x0A:
        case 0x10:
        case 0x16:
        case 0x19:
            return true;
        default:
            return false;
        }
    }

    template<typename Unit>
    [[nodiscard]] static status_consumption_result apply(
            Unit& source, Unit* target, std::uint8_t event_type)
    {
        status_consumption_result result;
        if(excluded(event_type))
        {
            return result;
        }
        result.source_consumed = source.statuses.remove(
                0x0D, status_remove_mode::consume_without_event);
        if(target)
        {
            result.target_consumed = target->statuses.remove(
                    0x0D, status_remove_mode::consume_without_event);
            if(result.target_consumed)
            {
                target->status_mask &= ~std::uint32_t(0x00000100U);
            }
        }
        return result;
    }
};

}

#endif
