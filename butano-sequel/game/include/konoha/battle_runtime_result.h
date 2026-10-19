#ifndef KONOHA_BATTLE_RUNTIME_RESULT_H
#define KONOHA_BATTLE_RUNTIME_RESULT_H

#include "konoha/battle_conditions.h"

#include <cstdint>

namespace konoha
{

enum class battle_runtime_scene_exit : std::uint8_t
{
    aborted,
    victory,
    defeat,
    draw,
};

[[nodiscard]] constexpr battle_runtime_scene_exit
battle_runtime_exit_for_outcome(
        battle_condition_outcome outcome)
{
    switch(outcome)
    {
    case battle_condition_outcome::win:
        return battle_runtime_scene_exit::victory;
    case battle_condition_outcome::loss:
        return battle_runtime_scene_exit::defeat;
    case battle_condition_outcome::equal_slot_result:
        return battle_runtime_scene_exit::draw;
    case battle_condition_outcome::none:
        return battle_runtime_scene_exit::aborted;
    }
    return battle_runtime_scene_exit::aborted;
}

[[nodiscard]] constexpr bool battle_runtime_exit_resolved(
        battle_runtime_scene_exit exit)
{
    return exit != battle_runtime_scene_exit::aborted;
}

[[nodiscard]] constexpr bool
battle_runtime_exit_commits_campaign(
        battle_runtime_scene_exit exit)
{
    return exit == battle_runtime_scene_exit::victory;
}

[[nodiscard]] constexpr bool
battle_runtime_exit_advances_campaign(
        battle_runtime_scene_exit exit)
{
    return exit == battle_runtime_scene_exit::victory;
}

}

#endif
