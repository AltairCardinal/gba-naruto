#ifndef KONOHA_BATTLE_RANGE_UI_STYLE_H
#define KONOHA_BATTLE_RANGE_UI_STYLE_H

#include <cstdint>

namespace konoha
{

enum class battle_range_ui_tile_kind : std::uint8_t
{
    grid,
    move,
    attack_range,
    cursor,
    target,
    blocked,
};

enum class battle_range_ui_palette_index : std::uint8_t
{
    grid_secondary = 225,
    move_primary = 226,
    move_secondary = 227,
    attack_primary = 228,
    attack_secondary = 229,
    cursor_primary = 230,
    cursor_secondary = 231,
    target_primary = 232,
    target_secondary = 233,
    blocked_primary = 234,
    blocked_secondary = 235,
};

struct battle_range_ui_rgb5
{
    int red = 0;
    int green = 0;
    int blue = 0;

    constexpr bool operator==(
            const battle_range_ui_rgb5&) const = default;
};

inline constexpr battle_range_ui_rgb5
        battle_range_ui_grid_secondary_color = {
    8, 13, 17,
};
inline constexpr battle_range_ui_rgb5
        battle_range_ui_move_primary_color = {
    3, 25, 31,
};
inline constexpr battle_range_ui_rgb5
        battle_range_ui_move_secondary_color = {
    1, 13, 21,
};
inline constexpr battle_range_ui_rgb5
        battle_range_ui_attack_primary_color = {
    31, 7, 0,
};
inline constexpr battle_range_ui_rgb5
        battle_range_ui_attack_secondary_color = {
    20, 5, 0,
};
inline constexpr battle_range_ui_rgb5
        battle_range_ui_cursor_primary_color = {
    31, 23, 0,
};
inline constexpr battle_range_ui_rgb5
        battle_range_ui_cursor_secondary_color = {
    18, 13, 0,
};
inline constexpr battle_range_ui_rgb5
        battle_range_ui_target_primary_color = {
    21, 31, 0,
};
inline constexpr battle_range_ui_rgb5
        battle_range_ui_target_secondary_color = {
    10, 16, 0,
};
inline constexpr battle_range_ui_rgb5
        battle_range_ui_blocked_primary_color = {
    9, 9, 9,
};
inline constexpr battle_range_ui_rgb5
        battle_range_ui_blocked_secondary_color = {
    4, 4, 4,
};

inline constexpr int battle_range_ui_tiles_per_cell_x = 4;
inline constexpr int battle_range_ui_tiles_per_cell_y = 2;
inline constexpr int battle_range_ui_tiles_per_kind =
        battle_range_ui_tiles_per_cell_x *
        battle_range_ui_tiles_per_cell_y;
inline constexpr int battle_range_ui_range_kind_count = 6;
inline constexpr int battle_range_ui_action_first_tile = 25;
inline constexpr int battle_range_ui_action_end_tile = 53;
// Original menu tiles occupy 25..52. Keep the three later range roles
// outside that upload; sharing these indices overwrites the cursor/grid.
inline constexpr int battle_range_ui_logical_tile_count = 77;
inline constexpr int battle_range_ui_storage_tile_count =
        battle_range_ui_logical_tile_count * 2;
inline constexpr int battle_range_ui_blend_numerator = 10;
inline constexpr int battle_range_ui_blend_denominator = 16;

[[nodiscard]] constexpr battle_range_ui_tile_kind
battle_range_ui_cell_kind(
        bool move_phase,
        bool cursor_cell,
        bool in_move_range,
        bool in_attack_range,
        bool legal_target,
        bool blocked)
{
    if(move_phase)
    {
        if(cursor_cell && in_move_range)
        {
            // Original S49 move-selection BG2 uses palette index 4 (orange)
            // at the destination; the yellow cursor role is a different tile.
            return battle_range_ui_tile_kind::attack_range;
        }
        if(in_move_range)
        {
            return battle_range_ui_tile_kind::move;
        }
    }
    else
    {
        if(legal_target)
        {
            return battle_range_ui_tile_kind::target;
        }
        if(in_attack_range)
        {
            return battle_range_ui_tile_kind::attack_range;
        }
    }
    return blocked ?
            battle_range_ui_tile_kind::blocked :
            battle_range_ui_tile_kind::grid;
}

[[nodiscard]] constexpr int battle_range_ui_tile_index(
        battle_range_ui_tile_kind kind,
        int cell_tile_x,
        int cell_tile_y)
{
    if(cell_tile_x < 0 ||
            cell_tile_x >= battle_range_ui_tiles_per_cell_x ||
            cell_tile_y < 0 ||
            cell_tile_y >= battle_range_ui_tiles_per_cell_y)
    {
        return 0;
    }
    int first_tile = 1;
    switch(kind)
    {
    case battle_range_ui_tile_kind::grid:
        first_tile = 1;
        break;
    case battle_range_ui_tile_kind::move:
        first_tile = 9;
        break;
    case battle_range_ui_tile_kind::attack_range:
        first_tile = 17;
        break;
    case battle_range_ui_tile_kind::cursor:
        first_tile = 53;
        break;
    case battle_range_ui_tile_kind::target:
        first_tile = 61;
        break;
    case battle_range_ui_tile_kind::blocked:
        first_tile = 69;
        break;
    }
    return first_tile +
           cell_tile_y *
                   battle_range_ui_tiles_per_cell_x +
           cell_tile_x;
}

[[nodiscard]] constexpr int
battle_range_ui_pixel_index(
        battle_range_ui_tile_kind kind,
        int cell_tile_x,
        int cell_tile_y,
        int pixel_x,
        int pixel_y)
{
    const int cell_x = cell_tile_x * 8 + pixel_x;
    const int cell_y = cell_tile_y * 8 + pixel_y;
    const bool boundary =
            cell_x == 31 || cell_y == 15;

    switch(kind)
    {
    case battle_range_ui_tile_kind::grid:
        return boundary ?
                static_cast<int>(
                        battle_range_ui_palette_index::
                                grid_secondary) :
                0;
    case battle_range_ui_tile_kind::move:
        return static_cast<int>(boundary ?
                battle_range_ui_palette_index::
                        move_secondary :
                battle_range_ui_palette_index::
                        move_primary);
    case battle_range_ui_tile_kind::attack_range:
        return static_cast<int>(boundary ?
                battle_range_ui_palette_index::
                        attack_secondary :
                battle_range_ui_palette_index::
                        attack_primary);
    case battle_range_ui_tile_kind::cursor:
        return static_cast<int>(boundary ?
                battle_range_ui_palette_index::
                        cursor_secondary :
                battle_range_ui_palette_index::
                        cursor_primary);
    case battle_range_ui_tile_kind::target:
        return static_cast<int>(boundary ?
                battle_range_ui_palette_index::
                        target_secondary :
                battle_range_ui_palette_index::
                        target_primary);
    case battle_range_ui_tile_kind::blocked:
        return static_cast<int>(boundary ?
                battle_range_ui_palette_index::
                        blocked_secondary :
                battle_range_ui_palette_index::
                        blocked_primary);
    }
    return 0;
}

}

#endif
