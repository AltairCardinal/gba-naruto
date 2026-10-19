#ifndef KONOHA_BATTLE_RESULT_CONTENT_H
#define KONOHA_BATTLE_RESULT_CONTENT_H

#include <array>
#include <cstdint>

namespace konoha
{

inline constexpr std::uint8_t no_battle_reward_record = 0xFF;

struct battle_reward_definition
{
    int mission_experience = 0;
    int round_bonus_experience = 0;
    int round_limit = 0;
    std::array<std::uint16_t, 9> postbattle_words = {};

    constexpr bool operator==(const battle_reward_definition&) const =
            default;
};

}

#endif
