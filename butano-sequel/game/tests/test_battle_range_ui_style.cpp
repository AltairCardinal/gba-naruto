#include "konoha/battle_range_ui_style.h"

#include <cassert>

using namespace konoha;

int main()
{
    // Original battle-14 BG2 has six independent 32x16 cell roles:
    // transparent grid, move, attack, current destination, legal target
    // and blocked terrain.  Each role uses eight 8x8 tiles.
    static_assert(battle_range_ui_action_first_tile == 25);
    static_assert(battle_range_ui_action_end_tile == 53);
    static_assert(battle_range_ui_logical_tile_count == 77);
    static_assert(battle_range_ui_storage_tile_count == 154);
    static_assert(battle_range_ui_blend_numerator == 10);
    static_assert(battle_range_ui_blend_denominator == 16);
    static_assert(
            battle_range_ui_grid_secondary_color ==
            battle_range_ui_rgb5{ 8, 13, 17 });
    static_assert(
            battle_range_ui_move_primary_color ==
            battle_range_ui_rgb5{ 3, 25, 31 });
    static_assert(
            battle_range_ui_move_secondary_color ==
            battle_range_ui_rgb5{ 1, 13, 21 });
    static_assert(
            battle_range_ui_attack_primary_color ==
            battle_range_ui_rgb5{ 31, 7, 0 });
    static_assert(
            battle_range_ui_attack_secondary_color ==
            battle_range_ui_rgb5{ 20, 5, 0 });
    static_assert(
            battle_range_ui_cursor_primary_color ==
            battle_range_ui_rgb5{ 31, 23, 0 });
    static_assert(
            battle_range_ui_cursor_secondary_color ==
            battle_range_ui_rgb5{ 18, 13, 0 });
    static_assert(
            battle_range_ui_target_primary_color ==
            battle_range_ui_rgb5{ 21, 31, 0 });
    static_assert(
            battle_range_ui_target_secondary_color ==
            battle_range_ui_rgb5{ 10, 16, 0 });
    static_assert(
            battle_range_ui_blocked_primary_color ==
            battle_range_ui_rgb5{ 9, 9, 9 });
    static_assert(
            battle_range_ui_blocked_secondary_color ==
            battle_range_ui_rgb5{ 4, 4, 4 });

    assert(battle_range_ui_tile_index(
                   battle_range_ui_tile_kind::grid,
                   0,
                   0) == 1);
    assert(battle_range_ui_tile_index(
                   battle_range_ui_tile_kind::grid,
                   3,
                   1) == 8);
    assert(battle_range_ui_tile_index(
                   battle_range_ui_tile_kind::move,
                   0,
                   0) == 9);
    assert(battle_range_ui_tile_index(
                   battle_range_ui_tile_kind::attack_range,
                   0,
                   0) == 17);
    assert(battle_range_ui_tile_index(
                   battle_range_ui_tile_kind::cursor,
                   0,
                   0) == 53);
    assert(battle_range_ui_tile_index(
                   battle_range_ui_tile_kind::target,
                   0,
                   0) == 61);
    assert(battle_range_ui_tile_index(
                   battle_range_ui_tile_kind::blocked,
                   0,
                   0) == 69);

    assert(battle_range_ui_pixel_index(
                   battle_range_ui_tile_kind::grid,
                   0,
                   0,
                   0,
                   0) == 0);
    assert(battle_range_ui_pixel_index(
                   battle_range_ui_tile_kind::grid,
                   3,
                   0,
                   7,
                   0) ==
           static_cast<int>(
                   battle_range_ui_palette_index::
                           grid_secondary));
    assert(battle_range_ui_pixel_index(
                   battle_range_ui_tile_kind::attack_range,
                   0,
                   1,
                   0,
                   7) ==
           static_cast<int>(
                   battle_range_ui_palette_index::
                           attack_secondary));
    assert(battle_range_ui_pixel_index(
                   battle_range_ui_tile_kind::target,
                   0,
                   0,
                   2,
                   2) ==
           static_cast<int>(
                   battle_range_ui_palette_index::
                           target_primary));
    assert(battle_range_ui_pixel_index(
                   battle_range_ui_tile_kind::blocked,
                   3,
                   1,
                   7,
                   7) ==
           static_cast<int>(
                   battle_range_ui_palette_index::
                           blocked_secondary));

    // The original map interaction always distinguishes the current
    // destination/target cell from the rest of its range.
    assert(battle_range_ui_cell_kind(
                   true,
                   true,
                   true,
                   false,
                   false,
                   false) ==
           battle_range_ui_tile_kind::attack_range);
    assert(battle_range_ui_cell_kind(
                   true,
                   false,
                   true,
                   false,
                   false,
                   false) ==
           battle_range_ui_tile_kind::move);
    assert(battle_range_ui_cell_kind(
                   false,
                   true,
                   true,
                   true,
                   true,
                   true) ==
           battle_range_ui_tile_kind::target);
    assert(battle_range_ui_cell_kind(
                   false,
                   false,
                   true,
                   true,
                   false,
                   false) ==
           battle_range_ui_tile_kind::attack_range);
    assert(battle_range_ui_cell_kind(
                   false,
                   false,
                   false,
                   false,
                   false,
                   true) ==
           battle_range_ui_tile_kind::blocked);
    assert(battle_range_ui_cell_kind(
                   false,
                   false,
                   false,
                   false,
                   false,
                   false) ==
           battle_range_ui_tile_kind::grid);
}
