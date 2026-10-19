#ifndef KONOHA_BATTLE_RESULT_POLICY_H
#define KONOHA_BATTLE_RESULT_POLICY_H

namespace konoha
{

struct battle_result_policy
{
    bool award_battle_experience = true;

    constexpr bool operator==(
            const battle_result_policy&) const = default;
};

}

#endif
