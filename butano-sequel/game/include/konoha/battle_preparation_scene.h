#ifndef KONOHA_BATTLE_PREPARATION_SCENE_H
#define KONOHA_BATTLE_PREPARATION_SCENE_H

#include "konoha/battle_campaign.h"

#include <cstdint>

namespace konoha
{

enum class battle_preparation_scene_exit : std::uint8_t
{
    ready,
    save_requested,
    invalid_campaign,
};

[[nodiscard]] battle_preparation_scene_exit
run_battle_preparation_scene(
        battle_campaign_state& campaign,
        bool show_overview = false);

}

#endif
