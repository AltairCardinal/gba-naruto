#ifndef KONOHA_BATTLE_RANGE_UI_STYLE_H
#define KONOHA_BATTLE_RANGE_UI_STYLE_H

#include "konoha/generated_battle_battlefield_overlay_content.h"

#include <array>
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

// ---------------------------------------------------------------------------
// The original's baked battlefield overlay (round 22, round 25).
//
// The original's BG2 is not "one extra grid layer": the game writes a whole
// battlefield layout map into its tilemap when the battle starts and the
// move-range screen merely enables BG2.  The layout covers a 16x16 grid of
// 16x16 px logical cells (2x2 of the original's 8x8 tiles each).
//
// The remake's grid point is 32x16 px, so it covers exactly two of those
// logical cells: the even column on the left, the odd column on the right,
// which is why the remake keeps writing 4x2 tiles per grid point.
//
// The two grids are related by a fixed offset (the map origin), derived from
// the original's BG2 scroll registers (240/24) and the fact that the
// original's move-range lens is centred on the selected unit, which the
// remake places at grid (6, 7) for S49.
// ---------------------------------------------------------------------------

inline constexpr int battle_range_ui_layout_logical_columns = 16;
inline constexpr int battle_range_ui_layout_logical_rows = 16;
inline constexpr int battle_range_ui_layout_col_base = 10;
inline constexpr int battle_range_ui_layout_row_base = -1;
inline constexpr int battle_range_ui_layout_tilemap_columns = 32;
inline constexpr int battle_range_ui_layout_tilemap_rows = 32;
inline constexpr int battle_range_ui_layout_tiles_per_cell = 8;

// The 4x2 tile block one remake grid point draws, in the original's own tile
// indices (256..287).  Index 0..3 is the top tile row, 4..7 the bottom one;
// within a row the left two tiles are the even original column and the right
// two the odd one.
struct battle_range_ui_layout_tiles
{
    std::uint16_t original[battle_range_ui_layout_tiles_per_cell] = {};
};

[[nodiscard]] constexpr int battle_range_ui_layout_wrap(int value, int count)
{
    const int wrapped = value % count;
    return wrapped < 0 ? wrapped + count : wrapped;
}

[[nodiscard]] constexpr int battle_range_ui_layout_original_tile(
        const std::array<
                std::uint16_t,
                battle_battlefield_overlay_tilemap_entries>& tilemap,
        int logical_row,
        int logical_col,
        int tile_dx,
        int tile_dy)
{
    const int tile_col =
            battle_range_ui_layout_wrap(
                    logical_col * 2 + tile_dx,
                    battle_range_ui_layout_tilemap_columns);
    const int tile_row =
            battle_range_ui_layout_wrap(
                    logical_row * 2 + tile_dy,
                    battle_range_ui_layout_tilemap_rows);
    return tilemap[
            static_cast<std::size_t>(
                    tile_row * battle_range_ui_layout_tilemap_columns +
                    tile_col)] &
            battle_battlefield_overlay_tile_mask;
}

[[nodiscard]] constexpr battle_range_ui_layout_tiles
battle_range_ui_layout_for_point(
        const std::array<
                std::uint16_t,
                battle_battlefield_overlay_tilemap_entries>& tilemap,
        int grid_x,
        int grid_y)
{
    const int logical_row =
            battle_range_ui_layout_wrap(
                    grid_y + battle_range_ui_layout_row_base,
                    battle_range_ui_layout_logical_rows);
    const int even_col =
            battle_range_ui_layout_wrap(
                    grid_x * 2 + battle_range_ui_layout_col_base,
                    battle_range_ui_layout_logical_columns);
    const int odd_col =
            battle_range_ui_layout_wrap(
                    even_col + 1,
                    battle_range_ui_layout_logical_columns);
    battle_range_ui_layout_tiles tiles;
    for(int tile_y = 0;
            tile_y < battle_range_ui_tiles_per_cell_y;
            ++tile_y)
    {
        for(int tile_x = 0;
                tile_x < battle_range_ui_tiles_per_cell_x;
                ++tile_x)
        {
            const int logical_col = tile_x < 2 ? even_col : odd_col;
            tiles.original[
                    static_cast<std::size_t>(
                            tile_y * battle_range_ui_tiles_per_cell_x +
                            tile_x)] =
                    static_cast<std::uint16_t>(
                            battle_range_ui_layout_original_tile(
                                    tilemap,
                                    logical_row,
                                    logical_col,
                                    tile_x % 2,
                                    tile_y));
        }
    }
    return tiles;
}

// The original's tile families, in the order the remake's own kinds use
// them: 256..261 the permanent grid web, 262..265 the move range, 266..269
// the attack range, 270..273 the cursor, 274..277 the legal targets and
// 278..281 the blocked area.
[[nodiscard]] constexpr battle_range_ui_tile_kind
battle_range_ui_layout_kind(int original_tile)
{
    if(original_tile >= 278)
    {
        return battle_range_ui_tile_kind::blocked;
    }
    if(original_tile >= 274)
    {
        return battle_range_ui_tile_kind::target;
    }
    if(original_tile >= 270)
    {
        return battle_range_ui_tile_kind::cursor;
    }
    if(original_tile >= 266)
    {
        return battle_range_ui_tile_kind::attack_range;
    }
    if(original_tile >= 262)
    {
        return battle_range_ui_tile_kind::move;
    }
    return battle_range_ui_tile_kind::grid;
}

[[nodiscard]] constexpr bool
battle_range_ui_kind_is_highlight(battle_range_ui_tile_kind kind)
{
    return kind == battle_range_ui_tile_kind::move ||
           kind == battle_range_ui_tile_kind::attack_range ||
           kind == battle_range_ui_tile_kind::cursor ||
           kind == battle_range_ui_tile_kind::target;
}

}

#endif
