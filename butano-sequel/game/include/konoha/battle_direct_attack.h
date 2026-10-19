#ifndef KONOHA_BATTLE_DIRECT_ATTACK_H
#define KONOHA_BATTLE_DIRECT_ATTACK_H

#include "konoha/battle_action_system.h"

namespace konoha
{

inline constexpr ability_id direct_attack_ability_id = 0xFE;

inline constexpr action_definition direct_attack_definition = {
    direct_attack_ability_id,
    cost_policy{
        action_cost_kind::none,
        0,
        no_tool_slot,
    },
    presentation_binding{ 1 },
    effect_descriptor{
        0x01,
        0,
        10,
        1,
        98,
        0,
    },
    target_policy{
        target_policy_kind::opponent_unit,
        0,
    },
    range_shape{ 1, 1 },
    upgrade_rule{ 0, 0 },
    battle_action_source_kind::direct_attack,
};

}

#endif
