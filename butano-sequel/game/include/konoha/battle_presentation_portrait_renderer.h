#ifndef KONOHA_BATTLE_PRESENTATION_PORTRAIT_RENDERER_H
#define KONOHA_BATTLE_PRESENTATION_PORTRAIT_RENDERER_H

#include "konoha/battle_presentation_content.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

struct battle_presentation_portrait_component
{
    int x = 0;
    int y = 0;
    int width = 0;
    int height = 0;
    std::size_t source_offset = 0;
    std::size_t source_bytes = 0;
};

inline constexpr std::array<
        battle_presentation_portrait_component,
        6> battle_presentation_portrait_components = {{
    { 64, 64, 16, 16, 0, 256 },
    { 64, 32, 16, 32, 256, 512 },
    { 64, 0, 16, 32, 768, 512 },
    { 32, 64, 32, 16, 1280, 512 },
    { 0, 64, 32, 16, 1792, 512 },
    { 0, 0, 64, 64, 2304, 4096 },
}};

[[nodiscard]] inline constexpr int
battle_presentation_portrait_origin_x(
        std::uint8_t slot,
        std::uint8_t motion_mode)
{
    switch(motion_mode)
    {
    case 2:
        return 80;
    case 3:
        return slot == 0 ? 64 : 96;
    case 4:
        return slot == 0 ? 16 : 144;
    default:
        return slot == 0 ? 16 : 144;
    }
}

[[nodiscard]] inline constexpr std::uint8_t
battle_presentation_portrait_palette_index(
        std::uint8_t source_index,
        std::uint8_t slot)
{
    return source_index == 0 ?
            0 :
            static_cast<std::uint8_t>(
                    source_index + slot * 64);
}

[[nodiscard]] inline constexpr std::uint16_t
dim_battle_presentation_portrait_color(
        std::uint16_t color)
{
    return static_cast<std::uint16_t>(
            ((color & 0x7BDE) >> 1) +
            ((color & 0x739C) >> 2));
}

}

#endif
