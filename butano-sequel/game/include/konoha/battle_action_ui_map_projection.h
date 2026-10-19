#ifndef KONOHA_BATTLE_ACTION_UI_MAP_PROJECTION_H
#define KONOHA_BATTLE_ACTION_UI_MAP_PROJECTION_H

#include "konoha/battle_player_action_flow.h"
#include "konoha/grid_pathfinder.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_action_ui_map_tile : std::uint8_t
{
    transparent = 0,
    fill = 25,
    horizontal_border = 26,
    vertical_border = 27,
    corner = 28,
};

struct battle_action_ui_map_cell
{
    battle_action_ui_map_tile tile =
            battle_action_ui_map_tile::transparent;
    bool horizontal_flip = false;
    bool vertical_flip = false;
};

enum class battle_action_ui_icon_frame : std::uint8_t
{
    ninjutsu = 0,
    taijutsu = 1,
    ninja_tool = 2,
    movement = 3,
    effect = 4,
    attack = 5,
};

[[nodiscard]] constexpr int battle_action_ui_page_start(
        int selected_index,
        int action_count)
{
    constexpr int page_size = 4;
    if(selected_index < 0 || selected_index >= action_count)
    {
        return 0;
    }
    return selected_index / page_size * page_size;
}

[[nodiscard]] constexpr battle_action_ui_icon_frame
battle_action_ui_category_icon(
        const battle_action_menu_view& action)
{
    if(action.kind == battle_action_source_kind::ninja_tool)
    {
        return battle_action_ui_icon_frame::ninja_tool;
    }
    if(action.cost_kind == action_cost_kind::current_hp)
    {
        return battle_action_ui_icon_frame::taijutsu;
    }
    return battle_action_ui_icon_frame::ninjutsu;
}

[[nodiscard]] constexpr battle_action_ui_icon_frame
battle_action_ui_effect_icon(
        const battle_action_menu_view& action)
{
    if(action.effect_code == 3 || action.effect_code == 12)
    {
        return battle_action_ui_icon_frame::movement;
    }
    if(action.effect_code == 1)
    {
        return battle_action_ui_icon_frame::attack;
    }
    return battle_action_ui_icon_frame::effect;
}

inline constexpr std::array<std::uint8_t, 64>
        battle_action_ui_original_horizontal_pixels = {{
    12, 12, 12, 12, 12, 12, 12, 12,
    11, 11, 11, 11, 11, 11, 11, 11,
    12, 11, 11, 12, 12, 13, 13, 13,
    13, 13, 12, 11, 11, 11, 12, 12,
    11, 12, 12, 12, 12, 12, 12, 11,
    11, 11, 11, 11, 11, 11, 11, 11,
    14, 14, 14, 14, 14, 14, 14, 14,
    9, 9, 9, 9, 9, 9, 9, 9,
}};

inline constexpr std::array<std::uint8_t, 64>
        battle_action_ui_original_vertical_pixels = {{
    12, 11, 13, 12, 11, 11, 14, 9,
    12, 11, 13, 12, 12, 11, 14, 9,
    12, 11, 13, 11, 12, 11, 14, 9,
    12, 11, 12, 11, 12, 11, 14, 9,
    12, 11, 12, 11, 12, 11, 14, 9,
    12, 11, 11, 12, 12, 11, 14, 9,
    12, 11, 11, 13, 12, 11, 14, 9,
    12, 11, 12, 13, 11, 11, 14, 9,
}};

inline constexpr std::array<std::uint8_t, 64>
        battle_action_ui_original_corner_pixels = {{
    12, 12, 12, 12, 12, 12, 12, 12,
    12, 11, 11, 11, 11, 11, 11, 11,
    12, 11, 13, 13, 12, 13, 12, 11,
    12, 11, 13, 11, 11, 12, 13, 13,
    12, 11, 12, 11, 11, 12, 12, 11,
    12, 11, 12, 12, 12, 11, 11, 11,
    12, 11, 11, 13, 12, 11, 14, 14,
    12, 11, 12, 13, 11, 11, 14, 9,
}};

[[nodiscard]] inline constexpr std::uint8_t
battle_action_ui_original_pixel(
        battle_action_ui_map_tile tile,
        int x,
        int y)
{
    if(x < 0 || x >= 8 || y < 0 || y >= 8)
    {
        return 0;
    }
    const std::size_t index =
            static_cast<std::size_t>(y * 8 + x);
    switch(tile)
    {
    case battle_action_ui_map_tile::fill:
        return 9;
    case battle_action_ui_map_tile::horizontal_border:
        return battle_action_ui_original_horizontal_pixels[
                index];
    case battle_action_ui_map_tile::vertical_border:
        return battle_action_ui_original_vertical_pixels[
                index];
    case battle_action_ui_map_tile::corner:
        return battle_action_ui_original_corner_pixels[
                index];
    case battle_action_ui_map_tile::transparent:
    default:
        return 0;
    }
}

[[nodiscard]] constexpr battle_action_ui_map_cell
battle_action_ui_map_cell_for(grid_point point)
{
    constexpr int width = 30;
    constexpr int height = 20;
    if(point.x < 0 || point.x >= width ||
            point.y < 0 || point.y >= height)
    {
        return {};
    }

    const auto left_vertical = [] {
        return battle_action_ui_map_cell{
            battle_action_ui_map_tile::vertical_border,
            false,
            false,
        };
    };
    const auto right_vertical = [] {
        return battle_action_ui_map_cell{
            battle_action_ui_map_tile::vertical_border,
            true,
            false,
        };
    };
    const auto top_left = [] {
        return battle_action_ui_map_cell{
            battle_action_ui_map_tile::corner,
            false,
            false,
        };
    };
    const auto top_right = [] {
        return battle_action_ui_map_cell{
            battle_action_ui_map_tile::corner,
            true,
            false,
        };
    };
    const auto bottom_left = [] {
        return battle_action_ui_map_cell{
            battle_action_ui_map_tile::corner,
            false,
            true,
        };
    };
    const auto bottom_right = [] {
        return battle_action_ui_map_cell{
            battle_action_ui_map_tile::corner,
            true,
            true,
        };
    };

    if(point.y == 0)
    {
        if(point.x == 0 || point.x == 19)
        {
            return top_left();
        }
        if(point.x == 18 || point.x == 29)
        {
            return top_right();
        }
        return {
            battle_action_ui_map_tile::horizontal_border,
            false,
            false,
        };
    }
    if(point.y < 3)
    {
        if(point.x == 0 || point.x == 19)
        {
            return left_vertical();
        }
        if(point.x == 18 || point.x == 29)
        {
            return right_vertical();
        }
        return {
            battle_action_ui_map_tile::fill,
            false,
            false,
        };
    }
    if(point.y == 3)
    {
        if(point.x == 0)
        {
            return bottom_left();
        }
        if(point.x == 18)
        {
            return bottom_right();
        }
        if(point.x == 19)
        {
            return left_vertical();
        }
        if(point.x == 29)
        {
            return right_vertical();
        }
        return {
            point.x < 19 ?
                    battle_action_ui_map_tile::
                            horizontal_border :
                    battle_action_ui_map_tile::fill,
            false,
            point.x < 19,
        };
    }
    if(point.y == 4)
    {
        if(point.x == 0)
        {
            return top_left();
        }
        if(point.x == 18)
        {
            return top_right();
        }
        if(point.x == 19)
        {
            return left_vertical();
        }
        if(point.x == 29)
        {
            return right_vertical();
        }
        return {
            point.x < 19 ?
                    battle_action_ui_map_tile::
                            horizontal_border :
                    battle_action_ui_map_tile::fill,
            false,
            false,
        };
    }
    if(point.y < 13)
    {
        if(point.x == 0 || point.x == 19)
        {
            return left_vertical();
        }
        if(point.x == 18 || point.x == 29)
        {
            return right_vertical();
        }
        return {
            battle_action_ui_map_tile::fill,
            false,
            false,
        };
    }
    if(point.y == 13)
    {
        if(point.x == 0 || point.x == 19)
        {
            return bottom_left();
        }
        if(point.x == 18 || point.x == 29)
        {
            return bottom_right();
        }
        return {
            battle_action_ui_map_tile::horizontal_border,
            false,
            true,
        };
    }
    if(point.y == 14)
    {
        if(point.x == 0)
        {
            return top_left();
        }
        if(point.x == 29)
        {
            return top_right();
        }
        return {
            battle_action_ui_map_tile::horizontal_border,
            false,
            false,
        };
    }
    if(point.y < 19)
    {
        if(point.x == 0)
        {
            return left_vertical();
        }
        if(point.x == 29)
        {
            return right_vertical();
        }
        return {
            battle_action_ui_map_tile::fill,
            false,
            false,
        };
    }
    if(point.x == 0 || point.x == 29)
    {
        return {
            battle_action_ui_map_tile::corner,
            point.x == 29,
            true,
        };
    }
    return {
        battle_action_ui_map_tile::horizontal_border,
        false,
        true,
    };
}

[[nodiscard]] constexpr battle_action_ui_map_cell
battle_command_ui_map_cell_for(
        grid_point point,
        int command_count)
{
    if(command_count <= 0)
    {
        return {};
    }
    constexpr int left = 1;
    constexpr int right = 6;
    const int top = command_count == 2 ? 5 : 2;
    const int bottom = command_count == 2 ? 10 : 13;
    if(point.x < left || point.x > right ||
            point.y < top || point.y > bottom)
    {
        return {};
    }
    if(point.y == top)
    {
        if(point.x == left || point.x == right)
        {
            return {
                battle_action_ui_map_tile::corner,
                point.x == right,
                false,
            };
        }
        return {
            battle_action_ui_map_tile::horizontal_border,
            false,
            false,
        };
    }
    if(point.y == bottom)
    {
        if(point.x == left || point.x == right)
        {
            return {
                battle_action_ui_map_tile::corner,
                point.x == right,
                true,
            };
        }
        return {
            battle_action_ui_map_tile::horizontal_border,
            false,
            true,
        };
    }
    if(point.x == left || point.x == right)
    {
        return {
            battle_action_ui_map_tile::vertical_border,
            point.x == right,
            false,
        };
    }
    return {
        battle_action_ui_map_tile::fill,
        false,
        false,
    };
}

[[nodiscard]] constexpr battle_action_ui_map_cell
battle_target_status_ui_map_cell_for(grid_point point)
{
    constexpr int width = 30;
    constexpr int height = 6;
    if(point.x < 0 || point.x >= width ||
            point.y < 0 || point.y >= height)
    {
        return {};
    }
    if(point.y == 0 || point.y == height - 1)
    {
        if(point.x == 0 || point.x == width - 1)
        {
            return {
                battle_action_ui_map_tile::corner,
                point.x == width - 1,
                point.y == height - 1,
            };
        }
        return {
            battle_action_ui_map_tile::horizontal_border,
            false,
            point.y == height - 1,
        };
    }
    if(point.x == 0 || point.x == width - 1)
    {
        return {
            battle_action_ui_map_tile::vertical_border,
            point.x == width - 1,
            false,
        };
    }
    return {
        battle_action_ui_map_tile::fill,
        false,
        false,
    };
}

}

#endif
