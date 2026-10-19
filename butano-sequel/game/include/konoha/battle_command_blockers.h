#ifndef KONOHA_BATTLE_COMMAND_BLOCKERS_H
#define KONOHA_BATTLE_COMMAND_BLOCKERS_H

#include "konoha/battle_status_store.h"

#include <array>
#include <cstdint>

namespace konoha
{

inline constexpr std::array<std::uint8_t, 6>
        battle_command_blocker_status_codes = {
            0x3F, 0x3E, 0x3D, 0x0F, 0x11, 0x15,
        };

[[nodiscard]] inline bool battle_commands_blocked(
        const battle_status_store& statuses)
{
    for(const std::uint8_t status_code :
            battle_command_blocker_status_codes)
    {
        if(statuses.find(status_code) != no_status_slot)
        {
            return true;
        }
    }
    return false;
}

}

#endif
