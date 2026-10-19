#ifndef BN_BG_PALETTE_ITEMS_BATTLE_ACTION_16_CUTIN_SHARED_PALETTE_H
#define BN_BG_PALETTE_ITEMS_BATTLE_ACTION_16_CUTIN_SHARED_PALETTE_H

#include "bn_bg_palette_item.h"
#include "bn_span.h"
#include "konoha/generated_battle_action_16_movie_runtime_content.h"

namespace bn::bg_palette_items
{

inline constexpr bg_palette_item battle_action_16_cutin_shared_palette(
        bn::span<const bn::color>(
                konoha::battle_action_16_cutin_palette.data(),
                konoha::battle_action_16_cutin_palette.size()),
        bn::bpp_mode::BPP_8);

}

#endif
