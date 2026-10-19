#ifndef KONOHA_BATTLE_MAP_CONTENT_H
#define KONOHA_BATTLE_MAP_CONTENT_H

#include <array>
#include <cstdint>

namespace konoha
{

inline constexpr std::uint8_t battle_map_terrain_class_one = 1;
inline constexpr std::uint8_t battle_map_terrain_class_three = 3;
inline constexpr std::uint8_t battle_map_terrain_class_seven = 7;
inline constexpr std::uint8_t battle_map_fully_closed = 15;

struct battle_map_cell
{
    std::uint16_t raw_attributes = 0;

    [[nodiscard]] constexpr std::uint8_t terrain_class() const
    {
        return static_cast<std::uint8_t>(
                raw_attributes & battle_map_fully_closed);
    }

    [[nodiscard]] constexpr bool fully_blocked() const
    {
        return terrain_class() == battle_map_fully_closed;
    }

    constexpr bool operator==(const battle_map_cell&) const = default;
};

struct battle_map_distance_record
{
    std::array<std::uint8_t, 16> bytes = {};

    constexpr bool operator==(const battle_map_distance_record&) const = default;
};

struct battle_map_definition
{
    std::uint8_t battle_id = 0;
    std::uint8_t width = 0;
    std::uint8_t height = 0;
    std::uint16_t cell_offset = 0;
    std::uint16_t cell_count = 0;

    [[nodiscard]] constexpr bool contains(int x, int y) const
    {
        return x >= 0 && x < width && y >= 0 && y < height;
    }

    constexpr bool operator==(const battle_map_definition&) const = default;
};

}

#endif
