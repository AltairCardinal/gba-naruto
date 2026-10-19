#ifndef KONOHA_BATTLE_MAP_LOADER_H
#define KONOHA_BATTLE_MAP_LOADER_H

#include "konoha/battle_map_content.h"
#include "konoha/battle_session.h"
#include "konoha/grid_pathfinder.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_map_load_error : std::uint8_t
{
    none,
    dimension_mismatch,
    content_out_of_bounds,
    unit_out_of_bounds,
    unit_on_blocked_cell,
    duplicate_unit_position,
};

[[nodiscard]] inline bool linked_units_share_occupancy(
        const battle_unit_instance& left,
        const battle_unit_instance& right)
{
    if(left.unit_state_code != 0x06 ||
            right.unit_state_code != 0x06)
    {
        return false;
    }
    return left.ai_linked_unit == right.id ||
            right.ai_linked_unit == left.id ||
            left.ai_secondary_linked_unit == right.id ||
            right.ai_secondary_linked_unit == left.id;
}

template<
        int Width,
        int Height,
        std::size_t CellCount>
[[nodiscard]] battle_map_load_error materialize_battle_map(
        const battle_map_definition& definition,
        const std::array<battle_map_cell, CellCount>& cells,
        grid_map<Width, Height>& destination)
{
    if(definition.width == 0 ||
            definition.width > Width ||
            definition.height == 0 ||
            definition.height > Height ||
            definition.cell_count !=
                    definition.width *
                            definition.height)
    {
        return battle_map_load_error::dimension_mismatch;
    }
    const std::size_t first = definition.cell_offset;
    const std::size_t count = definition.cell_count;
    if(first > cells.size() || count > cells.size() - first)
    {
        return battle_map_load_error::content_out_of_bounds;
    }

    grid_map<Width, Height> candidate;
    if(! candidate.set_active_dimensions(
               definition.width, definition.height))
    {
        return battle_map_load_error::dimension_mismatch;
    }
    if(! candidate.set_battle_id(definition.battle_id))
    {
        return battle_map_load_error::content_out_of_bounds;
    }
    for(int y = 0; y < definition.height; ++y)
    {
        for(int x = 0; x < definition.width; ++x)
        {
            const grid_point point{ x, y };
            const battle_map_cell& cell =
                    cells[first +
                            static_cast<std::size_t>(
                                    y *
                                            definition.width +
                                    x)];
            candidate.set_terrain_class(
                    point, cell.terrain_class());
            candidate.set_cost(
                    point,
                    cell.fully_blocked() ? 0 : 1);
        }
    }
    destination = candidate;
    return battle_map_load_error::none;
}

template<
        std::size_t MaxUnits,
        int Width,
        int Height>
[[nodiscard]] battle_map_load_error apply_battle_occupancy(
        const battle_session<MaxUnits>& session,
        grid_map<Width, Height>& destination)
{
    grid_map<Width, Height> candidate = destination;
    for(int y = 0;
            y < candidate.active_height(); ++y)
    {
        for(int x = 0;
                x < candidate.active_width(); ++x)
        {
            candidate.set_occupied({ x, y }, false);
        }
    }

    for(std::size_t index = 0;
            index < session.unit_count(); ++index)
    {
        const battle_unit_instance* unit =
                session.unit_at(index);
        if(! unit || ! unit->active)
        {
            continue;
        }
        if(! candidate.contains(unit->position))
        {
            return battle_map_load_error::unit_out_of_bounds;
        }
        if(candidate.cost(unit->position) == 0 ||
                candidate.terrain_class(unit->position) ==
                        grid_fully_closed)
        {
            return battle_map_load_error::
                    unit_on_blocked_cell;
        }
        if(candidate.occupied(unit->position))
        {
            bool linked_occupant_found = false;
            for(std::size_t occupant_index = 0;
                    occupant_index < index;
                    ++occupant_index)
            {
                const battle_unit_instance* occupant =
                        session.unit_at(occupant_index);
                if(occupant &&
                        occupant->active &&
                        occupant->position == unit->position &&
                        linked_units_share_occupancy(
                                *occupant, *unit))
                {
                    linked_occupant_found = true;
                    break;
                }
            }
            if(! linked_occupant_found)
            {
                return battle_map_load_error::
                        duplicate_unit_position;
            }
        }
        candidate.set_occupied(unit->position, true);
    }
    destination = candidate;
    return battle_map_load_error::none;
}

}

#endif
