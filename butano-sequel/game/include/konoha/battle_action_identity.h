#ifndef KONOHA_BATTLE_ACTION_IDENTITY_H
#define KONOHA_BATTLE_ACTION_IDENTITY_H

#include <cstdint>

namespace konoha
{

enum class battle_action_source_kind : std::uint8_t
{
    active_action,
    ninja_tool,
    direct_attack,
};

}

#endif
