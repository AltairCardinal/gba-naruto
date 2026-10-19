#ifndef KONOHA_BATTLE_RUNTIME_GRID_H
#define KONOHA_BATTLE_RUNTIME_GRID_H

#include "konoha/battle_scene_controller.h"

#include <cstddef>

namespace konoha
{

inline constexpr int battle_runtime_grid_width = 23;
inline constexpr int battle_runtime_grid_height = 32;
inline constexpr std::size_t battle_runtime_max_units = 12;

using battle_runtime_grid = grid_map<
        battle_runtime_grid_width,
        battle_runtime_grid_height>;
using battle_runtime_controller = battle_scene_controller<
        battle_runtime_max_units,
        battle_runtime_grid_width,
        battle_runtime_grid_height>;

}

#endif
