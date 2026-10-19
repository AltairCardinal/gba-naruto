#include "konoha/battle_action_ui_map_projection.h"

#include <array>
#include <cassert>

using namespace konoha;

int main()
{
    const battle_action_ui_map_cell top_left =
            battle_action_ui_map_cell_for({ 0, 0 });
    assert(top_left.tile ==
           battle_action_ui_map_tile::corner);
    assert(! top_left.horizontal_flip);
    assert(! top_left.vertical_flip);

    const battle_action_ui_map_cell top_right =
            battle_action_ui_map_cell_for({ 29, 0 });
    assert(top_right.tile ==
           battle_action_ui_map_tile::corner);
    assert(top_right.horizontal_flip);
    assert(! top_right.vertical_flip);

    const battle_action_ui_map_cell bottom_left =
            battle_action_ui_map_cell_for({ 0, 19 });
    assert(bottom_left.tile ==
           battle_action_ui_map_tile::corner);
    assert(! bottom_left.horizontal_flip);
    assert(bottom_left.vertical_flip);

    const battle_action_ui_map_cell bottom_right =
            battle_action_ui_map_cell_for({ 29, 19 });
    assert(bottom_right.tile ==
           battle_action_ui_map_tile::corner);
    assert(bottom_right.horizontal_flip);
    assert(bottom_right.vertical_flip);

    assert(battle_action_ui_map_cell_for({ 8, 0 }).tile ==
           battle_action_ui_map_tile::horizontal_border);
    assert(battle_action_ui_map_cell_for({ 0, 8 }).tile ==
           battle_action_ui_map_tile::vertical_border);
    assert(battle_action_ui_map_cell_for({ 8, 8 }).tile ==
           battle_action_ui_map_tile::fill);

    // Original stable boundary: the actor/list column ends with a right
    // frame at x=144, the statistics column starts with a left frame at
    // x=152, and y=112 opens a full-width description/help panel.
    assert(battle_action_ui_map_cell_for({ 8, 4 }).tile ==
           battle_action_ui_map_tile::horizontal_border);
    const battle_action_ui_map_cell left_column_right =
            battle_action_ui_map_cell_for({ 18, 8 });
    assert(left_column_right.tile ==
           battle_action_ui_map_tile::vertical_border);
    assert(left_column_right.horizontal_flip);
    const battle_action_ui_map_cell stats_column_left =
            battle_action_ui_map_cell_for({ 19, 8 });
    assert(stats_column_left.tile ==
           battle_action_ui_map_tile::vertical_border);
    assert(! stats_column_left.horizontal_flip);
    assert(battle_action_ui_map_cell_for({ 8, 14 }).tile ==
           battle_action_ui_map_tile::horizontal_border);
    assert(battle_action_ui_map_cell_for({ 18, 4 }).tile ==
           battle_action_ui_map_tile::corner);
    assert(battle_action_ui_map_cell_for({ 19, 4 }).tile ==
           battle_action_ui_map_tile::vertical_border);
    assert(battle_action_ui_map_cell_for({ 19, 14 }).tile ==
           battle_action_ui_map_tile::horizontal_border);
    const battle_action_ui_map_cell actor_bottom =
            battle_action_ui_map_cell_for({ 8, 3 });
    assert(actor_bottom.tile ==
           battle_action_ui_map_tile::horizontal_border);
    assert(actor_bottom.vertical_flip);
    assert(battle_action_ui_map_cell_for({ 20, 3 }).tile ==
           battle_action_ui_map_tile::fill);
    const battle_action_ui_map_cell list_bottom =
            battle_action_ui_map_cell_for({ 8, 13 });
    assert(list_bottom.tile ==
           battle_action_ui_map_tile::horizontal_border);
    assert(list_bottom.vertical_flip);
    const battle_action_ui_map_cell stats_bottom =
            battle_action_ui_map_cell_for({ 20, 13 });
    assert(stats_bottom.tile ==
           battle_action_ui_map_tile::horizontal_border);
    assert(stats_bottom.vertical_flip);

    const battle_action_ui_map_cell outside =
            battle_action_ui_map_cell_for({ 30, 20 });
    assert(outside.tile ==
           battle_action_ui_map_tile::transparent);

    // The original two-entry post-move command menu occupies screen tiles
    // x=1..6, y=5..10.  Its shell uses the same BG3 panel tiles as the
    // action browser, while text and selection remain dynamic.
    const battle_action_ui_map_cell command_top_left =
            battle_command_ui_map_cell_for({ 1, 5 }, 2);
    assert(command_top_left.tile ==
           battle_action_ui_map_tile::corner);
    assert(! command_top_left.horizontal_flip);
    assert(! command_top_left.vertical_flip);
    const battle_action_ui_map_cell command_top_right =
            battle_command_ui_map_cell_for({ 6, 5 }, 2);
    assert(command_top_right.tile ==
           battle_action_ui_map_tile::corner);
    assert(command_top_right.horizontal_flip);
    assert(! command_top_right.vertical_flip);
    const battle_action_ui_map_cell command_bottom_left =
            battle_command_ui_map_cell_for({ 1, 10 }, 2);
    assert(command_bottom_left.tile ==
           battle_action_ui_map_tile::corner);
    assert(! command_bottom_left.horizontal_flip);
    assert(command_bottom_left.vertical_flip);
    const battle_action_ui_map_cell command_bottom_right =
            battle_command_ui_map_cell_for({ 6, 10 }, 2);
    assert(command_bottom_right.tile ==
           battle_action_ui_map_tile::corner);
    assert(command_bottom_right.horizontal_flip);
    assert(command_bottom_right.vertical_flip);
    assert(battle_command_ui_map_cell_for({ 3, 5 }, 2)
                   .tile ==
           battle_action_ui_map_tile::horizontal_border);
    assert(battle_command_ui_map_cell_for({ 1, 7 }, 2)
                   .tile ==
           battle_action_ui_map_tile::vertical_border);
    assert(battle_command_ui_map_cell_for({ 3, 7 }, 2)
                   .tile ==
           battle_action_ui_map_tile::fill);
    assert(battle_command_ui_map_cell_for({ 0, 5 }, 2)
                   .tile ==
           battle_action_ui_map_tile::transparent);
    assert(battle_command_ui_map_cell_for({ 1, 4 }, 2)
                   .tile ==
           battle_action_ui_map_tile::transparent);

    // Target preview/confirmation keeps the original six-tile-high status
    // shell at screen y=112..159.  This is a state-free 30x6 BG panel,
    // not the shorter four-sprite map status bar.
    const battle_action_ui_map_cell status_top_left =
            battle_target_status_ui_map_cell_for({ 0, 0 });
    assert(status_top_left.tile ==
           battle_action_ui_map_tile::corner);
    assert(! status_top_left.horizontal_flip);
    assert(! status_top_left.vertical_flip);
    const battle_action_ui_map_cell status_top_right =
            battle_target_status_ui_map_cell_for({ 29, 0 });
    assert(status_top_right.tile ==
           battle_action_ui_map_tile::corner);
    assert(status_top_right.horizontal_flip);
    assert(! status_top_right.vertical_flip);
    assert(battle_target_status_ui_map_cell_for({ 12, 0 }).tile ==
           battle_action_ui_map_tile::horizontal_border);
    assert(battle_target_status_ui_map_cell_for({ 0, 3 }).tile ==
           battle_action_ui_map_tile::vertical_border);
    assert(battle_target_status_ui_map_cell_for({ 12, 3 }).tile ==
           battle_action_ui_map_tile::fill);
    const battle_action_ui_map_cell status_bottom_right =
            battle_target_status_ui_map_cell_for({ 29, 5 });
    assert(status_bottom_right.tile ==
           battle_action_ui_map_tile::corner);
    assert(status_bottom_right.horizontal_flip);
    assert(status_bottom_right.vertical_flip);
    assert(battle_target_status_ui_map_cell_for({ 30, 5 }).tile ==
           battle_action_ui_map_tile::transparent);
    assert(battle_target_status_ui_map_cell_for({ 0, 6 }).tile ==
           battle_action_ui_map_tile::transparent);

    // The unfiltered five-entry menu keeps the established full-height
    // command shell while using the same exact state-free tiles.
    assert(battle_command_ui_map_cell_for({ 1, 2 }, 5)
                   .tile ==
           battle_action_ui_map_tile::corner);
    const battle_action_ui_map_cell full_bottom =
            battle_command_ui_map_cell_for({ 6, 13 }, 5);
    assert(full_bottom.tile ==
           battle_action_ui_map_tile::corner);
    assert(full_bottom.horizontal_flip);
    assert(full_bottom.vertical_flip);

    // The state-free shell pixels come directly from battle 14's original
    // BG3 tiles 0x1C1/0x1C2/0x1C6/0x1C8.  Palette offsets are relative to
    // the 16-color action UI reservation in the shared 8BPP map palette.
    constexpr std::array<std::uint8_t, 64>
            expected_horizontal = {
        12, 12, 12, 12, 12, 12, 12, 12,
        11, 11, 11, 11, 11, 11, 11, 11,
        12, 11, 11, 12, 12, 13, 13, 13,
        13, 13, 12, 11, 11, 11, 12, 12,
        11, 12, 12, 12, 12, 12, 12, 11,
        11, 11, 11, 11, 11, 11, 11, 11,
        14, 14, 14, 14, 14, 14, 14, 14,
        9, 9, 9, 9, 9, 9, 9, 9,
    };
    constexpr std::array<std::uint8_t, 64>
            expected_vertical = {
        12, 11, 13, 12, 11, 11, 14, 9,
        12, 11, 13, 12, 12, 11, 14, 9,
        12, 11, 13, 11, 12, 11, 14, 9,
        12, 11, 12, 11, 12, 11, 14, 9,
        12, 11, 12, 11, 12, 11, 14, 9,
        12, 11, 11, 12, 12, 11, 14, 9,
        12, 11, 11, 13, 12, 11, 14, 9,
        12, 11, 12, 13, 11, 11, 14, 9,
    };
    constexpr std::array<std::uint8_t, 64>
            expected_corner = {
        12, 12, 12, 12, 12, 12, 12, 12,
        12, 11, 11, 11, 11, 11, 11, 11,
        12, 11, 13, 13, 12, 13, 12, 11,
        12, 11, 13, 11, 11, 12, 13, 13,
        12, 11, 12, 11, 11, 12, 12, 11,
        12, 11, 12, 12, 12, 11, 11, 11,
        12, 11, 11, 13, 12, 11, 14, 14,
        12, 11, 12, 13, 11, 11, 14, 9,
    };
    for(int y = 0; y < 8; ++y)
    {
        for(int x = 0; x < 8; ++x)
        {
            const std::size_t index =
                    static_cast<std::size_t>(y * 8 + x);
            assert(battle_action_ui_original_pixel(
                           battle_action_ui_map_tile::
                                   fill,
                           x,
                           y) == 9);
            assert(battle_action_ui_original_pixel(
                           battle_action_ui_map_tile::
                                   horizontal_border,
                           x,
                           y) ==
                   expected_horizontal[index]);
            assert(battle_action_ui_original_pixel(
                           battle_action_ui_map_tile::
                                   vertical_border,
                           x,
                           y) ==
                   expected_vertical[index]);
            assert(battle_action_ui_original_pixel(
                           battle_action_ui_map_tile::
                                   corner,
                           x,
                           y) ==
                   expected_corner[index]);
        }
    }

    // The original action browser pages four dynamic entries at a time.
    assert(battle_action_ui_page_start(0, 4) == 0);
    assert(battle_action_ui_page_start(3, 4) == 0);
    assert(battle_action_ui_page_start(4, 6) == 4);
    assert(battle_action_ui_page_start(9, 6) == 0);

    battle_action_menu_view instant_move;
    instant_move.action_id = 2;
    instant_move.effect_code = 3;
    instant_move.kind =
            battle_action_source_kind::active_action;
    instant_move.cost_kind =
            action_cost_kind::current_chakra;
    assert(battle_action_ui_category_icon(instant_move) ==
           battle_action_ui_icon_frame::ninjutsu);
    assert(battle_action_ui_effect_icon(instant_move) ==
           battle_action_ui_icon_frame::movement);

    battle_action_menu_view shadow_clone = instant_move;
    shadow_clone.action_id = 7;
    shadow_clone.effect_code = 7;
    assert(battle_action_ui_effect_icon(shadow_clone) ==
           battle_action_ui_icon_frame::effect);

    battle_action_menu_view combo = instant_move;
    combo.action_id = 5;
    combo.effect_code = 1;
    combo.cost_kind = action_cost_kind::current_hp;
    assert(battle_action_ui_category_icon(combo) ==
           battle_action_ui_icon_frame::taijutsu);
    assert(battle_action_ui_effect_icon(combo) ==
           battle_action_ui_icon_frame::attack);

    battle_action_menu_view tool = combo;
    tool.kind = battle_action_source_kind::ninja_tool;
    assert(battle_action_ui_category_icon(tool) ==
           battle_action_ui_icon_frame::ninja_tool);
}
