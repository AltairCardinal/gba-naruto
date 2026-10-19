#ifndef KONOHA_BATTLE_MAP_TOPOLOGY_DISTANCE_H
#define KONOHA_BATTLE_MAP_TOPOLOGY_DISTANCE_H

#include "konoha/generated_battle_map_content.h"
#include "konoha/grid_pathfinder.h"

#include <cstddef>
#include <cstdint>

namespace konoha
{

namespace battle_map_topology_distance_detail
{

[[nodiscard]] inline int absolute_difference(int first, int second)
{
    return first > second ? first - second : second - first;
}

[[nodiscard]] inline int manhattan(grid_point first, grid_point second)
{
    return absolute_difference(first.x, second.x) +
            absolute_difference(first.y, second.y);
}

inline void swap(grid_point& first, grid_point& second)
{
    const grid_point temporary = first;
    first = second;
    second = temporary;
}

inline void adjust_gap_coordinate(
        int& coordinate,
        const battle_map_distance_record& record)
{
    const std::array<std::uint8_t, 16>& bytes = record.bytes;
    const int breakpoint_count = bytes[3];
    for(int index = 0; index + 1 < breakpoint_count; ++index)
    {
        const int current_offset = 4 + index * 2;
        const int next_offset = current_offset + 2;
        const int current_length = bytes[current_offset + 1];
        const int current_end =
                bytes[current_offset] + current_length;
        const int next_start = bytes[next_offset];
        if(coordinate < current_end || coordinate >= next_start)
        {
            continue;
        }
        if(current_length == 0)
        {
            coordinate = next_start;
        }
        else if(bytes[next_offset + 1] == 0)
        {
            coordinate = current_end - 1;
        }
        else if(coordinate - current_end <
                next_start - coordinate - 1)
        {
            coordinate = current_end - 1;
        }
        else
        {
            coordinate = next_start;
        }
        return;
    }
}

inline void apply_vertical_barrier(
        const battle_map_distance_record& record,
        grid_point& first,
        grid_point& second,
        std::uint16_t& distance,
        int& route_state)
{
    if(first.x > second.x)
    {
        swap(first, second);
    }
    const grid_point original = first;
    const int barrier_start = record.bytes[1];
    const int barrier_end =
            barrier_start + record.bytes[2] - 1;
    if(first.x >= barrier_start || second.x <= barrier_end)
    {
        route_state = 2;
        return;
    }
    first.x = barrier_start - 1;
    adjust_gap_coordinate(first.y, record);
    distance = static_cast<std::uint16_t>(
            distance + manhattan(original, first));
    route_state = 1;
}

inline void apply_horizontal_barrier(
        const battle_map_distance_record& record,
        grid_point& first,
        grid_point& second,
        std::uint16_t& distance,
        int& route_state)
{
    if(first.y > second.y)
    {
        swap(first, second);
    }
    const grid_point original = first;
    const int barrier_start = record.bytes[1];
    const int barrier_end =
            barrier_start + record.bytes[2] - 1;
    if(first.y >= barrier_start || second.y <= barrier_end)
    {
        route_state = 2;
        return;
    }
    first.y = barrier_start - 1;
    adjust_gap_coordinate(first.x, record);
    distance = static_cast<std::uint16_t>(
            distance + manhattan(original, first));
    route_state = 1;
}

[[nodiscard]] inline std::uint16_t signed_lookup(
        const std::uint8_t* values,
        int width,
        grid_point point)
{
    const std::int8_t value = static_cast<std::int8_t>(
            values[point.y * width + point.x]);
    return static_cast<std::uint16_t>(
            static_cast<std::int16_t>(value));
}

[[nodiscard]] inline bool in_map_24_center(grid_point point)
{
    return point.x >= 3 && point.x <= 9 &&
            point.y >= 6 && point.y <= 11;
}

}

[[nodiscard]] inline int battle_map_topology_distance(
        int battle_id,
        grid_point first,
        grid_point second)
{
    using namespace battle_map_topology_distance_detail;

    const battle_map_distance_record* records =
            battle_map_distance_records_for(battle_id);
    if(! records)
    {
        return manhattan(first, second);
    }

    std::uint16_t distance = 0;
    int route_state = 1;
    for(int record_index = 0; record_index < 8; ++record_index)
    {
        const battle_map_distance_record& record =
                records[record_index];
        switch(record.bytes[0])
        {
        case 0:
            if(route_state != 0)
            {
                distance = static_cast<std::uint16_t>(
                        distance + manhattan(first, second));
            }
            return distance;
        case 1:
            apply_vertical_barrier(
                    record,
                    first,
                    second,
                    distance,
                    route_state);
            break;
        case 2:
            apply_horizontal_barrier(
                    record,
                    first,
                    second,
                    distance,
                    route_state);
            break;
        case 3:
            if(route_state != 2)
            {
                break;
            }
            if(first.x == 7 && first.y == 7 &&
                    second.y > 7)
            {
                if(second.x <= 5)
                {
                    distance = static_cast<std::uint16_t>(
                            distance + 3);
                }
                else if(second.x == 6)
                {
                    distance = static_cast<std::uint16_t>(
                            distance + 4);
                }
                else if(second.x == 7)
                {
                    distance = static_cast<std::uint16_t>(
                            distance + 6);
                }
            }
            if(second.x == 7 && second.y == 7 &&
                    first.y > 7)
            {
                if(first.x <= 5)
                {
                    distance = static_cast<std::uint16_t>(
                            distance + 3);
                }
                else if(first.x == 6)
                {
                    distance = static_cast<std::uint16_t>(
                            distance + 4);
                }
                else if(first.x == 7)
                {
                    distance = static_cast<std::uint16_t>(
                            distance + 6);
                }
            }
            break;
        case 4:
        {
            const std::uint16_t first_value = signed_lookup(
                    battle_map_23_distance_lookup.data(),
                    15,
                    first);
            const std::uint16_t second_value = signed_lookup(
                    battle_map_23_distance_lookup.data(),
                    15,
                    second);
            if(first_value > 9 && second_value > 9)
            {
                break;
            }
            distance = static_cast<std::uint16_t>(
                    absolute_difference(
                            first_value,
                            second_value));
            if(first.x == 12 && first.y == 9)
            {
                distance = static_cast<std::uint16_t>(
                        distance + 1);
            }
            if(second.x == 12 && second.y == 9)
            {
                distance = static_cast<std::uint16_t>(
                        distance + 1);
            }
            route_state = 0;
            break;
        }
        case 5:
        {
            if(route_state != 2)
            {
                break;
            }
            const bool first_center =
                    in_map_24_center(first);
            const bool second_center =
                    in_map_24_center(second);
            if(first_center == second_center)
            {
                break;
            }
            const std::uint16_t direct = static_cast<std::uint16_t>(
                    signed_lookup(
                            battle_map_24_distance_lookup.data(),
                            13,
                            first) +
                    signed_lookup(
                            battle_map_24_distance_lookup.data(),
                            13,
                            second));
            const grid_point mirrored_first = {
                12 - first.x,
                first.y,
            };
            const grid_point mirrored_second = {
                12 - second.x,
                second.y,
            };
            const std::uint16_t mirrored = static_cast<std::uint16_t>(
                    signed_lookup(
                            battle_map_24_distance_lookup.data(),
                            13,
                            mirrored_first) +
                    signed_lookup(
                            battle_map_24_distance_lookup.data(),
                            13,
                            mirrored_second));
            distance = direct < mirrored ? direct : mirrored;
            route_state = 0;
            break;
        }
        case 6:
            if(route_state != 2)
            {
                break;
            }
            if(first.x == 8 &&
                    first.y >= 2 && first.y <= 6 &&
                    second.x > 8 && second.y > 4)
            {
                if(second.y <= 10)
                {
                    distance = static_cast<std::uint16_t>(
                            second.x - first.x - 4 +
                            second.y);
                    distance = static_cast<std::uint16_t>(
                            distance +
                            (first.y == 3 ?
                                    1 :
                                    first.y - 4));
                    route_state = 0;
                }
                else
                {
                    distance = static_cast<std::uint16_t>(
                            distance +
                            (second.y == 11 ? 3 : 2));
                    route_state = 1;
                }
            }
            else if(second.x == 8 &&
                    second.y >= 2 && second.y <= 6 &&
                    first.x > 8 && first.y > 4)
            {
                if(first.y <= 10)
                {
                    distance = static_cast<std::uint16_t>(
                            first.x - second.x - 4 +
                            first.y);
                    distance = static_cast<std::uint16_t>(
                            distance +
                            (second.y == 3 ?
                                    1 :
                                    second.y - 4));
                    route_state = 0;
                }
                else
                {
                    distance = static_cast<std::uint16_t>(
                            first.y == 11 ? 4 : 2);
                    route_state = 1;
                }
            }
            break;
        default:
            return distance;
        }
    }
    return distance;
}

}

#endif
