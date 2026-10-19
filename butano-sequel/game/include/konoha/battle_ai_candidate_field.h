#ifndef KONOHA_BATTLE_AI_CANDIDATE_FIELD_H
#define KONOHA_BATTLE_AI_CANDIDATE_FIELD_H

#include "konoha/battle_action_catalog.h"
#include "konoha/battle_terrain_traversal.h"
#include "konoha/grid_pathfinder.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr std::uint8_t ai_candidate_threatened = 0x01;
inline constexpr std::uint8_t ai_candidate_source_below = 0x10;
inline constexpr std::uint8_t ai_candidate_source_left = 0x20;
inline constexpr std::uint8_t ai_candidate_source_above = 0x40;
inline constexpr std::uint8_t ai_candidate_source_right = 0x80;

template<int Width, int Height>
class ai_candidate_field
{
public:
    void clear()
    {
        _flags.fill(0);
    }

    [[nodiscard]] std::uint8_t flags(grid_point point) const
    {
        if(point.x < 0 || point.x >= Width ||
                point.y < 0 || point.y >= Height)
        {
            return 0;
        }
        return _flags[static_cast<std::size_t>(
                point.y * Width + point.x)];
    }

    void mark(grid_point source, grid_point target)
    {
        if(target.x < 0 || target.x >= Width ||
                target.y < 0 || target.y >= Height)
        {
            return;
        }
        std::uint8_t& value = _flags[static_cast<std::size_t>(
                target.y * Width + target.x)];
        value |= ai_candidate_threatened;
        if(source.x == target.x)
        {
            if(source.y > target.y)
            {
                value |= ai_candidate_source_below;
            }
            else if(source.y < target.y)
            {
                value |= ai_candidate_source_above;
            }
        }
        else if(source.y == target.y)
        {
            if(source.x < target.x)
            {
                value |= ai_candidate_source_left;
            }
            else
            {
                value |= ai_candidate_source_right;
            }
        }
    }

private:
    std::array<std::uint8_t, Width * Height> _flags = {};
};

class battle_ai_candidate_field_builder
{
public:
    template<int Width, int Height, std::size_t UnitCount>
    [[nodiscard]] static bool build(
            const grid_map<Width, Height>& map,
            const battle_unit_instance& perspective,
            const std::array<battle_unit_instance, UnitCount>& units,
            ai_candidate_field<Width, Height>& result,
            reachable_cost_result<Width, Height>& reachable)
    {
        result.clear();
        for(const battle_unit_instance& source_unit : units)
        {
            if(! source_unit.active ||
                    source_unit.side == perspective.side)
            {
                continue;
            }
            const battle_action_catalog_result catalog =
                    battle_action_catalog::build(source_unit);
            if(catalog.error != battle_action_catalog_error::none)
            {
                continue;
            }
            reachable = compute_reachable_costs(
                    map,
                    source_unit.position,
                    source_unit.move_range,
                    battle_terrain_traversal_limits(
                            source_unit.passives));
            if(! reachable.valid)
            {
                continue;
            }
            for(int source_index = 0;
                    source_index < Width * Height;
                    ++source_index)
            {
                const grid_point source =
                        map.from_index(source_index);
                if(reachable.cost(source) < 0)
                {
                    continue;
                }
                for(std::size_t action_index = 0;
                        action_index < catalog.count;
                        ++action_index)
                {
                    const battle_action_catalog_entry& entry =
                            catalog.entries[action_index];
                    if(! _is_available_hostile_action(
                               source_unit,
                               entry))
                    {
                        continue;
                    }
                    _mark_action(
                            map,
                            source,
                            entry.action,
                            result);
                }
            }
        }
        return true;
    }

private:
    [[nodiscard]] static bool _is_available_hostile_action(
            const battle_unit_instance& source,
            const battle_action_catalog_entry& entry)
    {
        const action_definition& action = entry.action;
        if(effect_resolver_registry::handler_for(
                   action.effect.code) !=
                effect_handler_kind::damage)
        {
            return false;
        }
        if(action.target.kind !=
                   target_policy_kind::opponent_unit &&
                action.target.kind !=
                   target_policy_kind::occupied_unit)
        {
            return false;
        }
        if(! battle_action_eligibility::query(
                    source,
                    action.id,
                    action.source_kind).available())
        {
            return false;
        }
        return battle_action_cost_policy::validate(
                       source,
                       action.cost,
                       entry.action_id) ==
                action_error::none;
    }

    template<int Width, int Height>
    static void _mark_action(
            const grid_map<Width, Height>& map,
            grid_point source,
            const action_definition& action,
            ai_candidate_field<Width, Height>& result)
    {
        const int maximum_distance =
                action.range.maximum_distance();
        const int minimum_center_x = _maximum(
                0,
                source.x - maximum_distance);
        const int maximum_center_x = _minimum(
                map.active_width() - 1,
                source.x + maximum_distance);
        const int minimum_center_y = _maximum(
                0,
                source.y - maximum_distance);
        const int maximum_center_y = _minimum(
                map.active_height() - 1,
                source.y + maximum_distance);
        const int encoded_area_size =
                action.range.area_range_and_shape_flags &
                0x7F;
        const int area_radius =
                encoded_area_size > 0 ?
                encoded_area_size - 1 : 0;
        for(int center_y = minimum_center_y;
                center_y <= maximum_center_y;
                ++center_y)
        {
            for(int center_x = minimum_center_x;
                    center_x <= maximum_center_x;
                    ++center_x)
            {
                const grid_point center = {
                    center_x,
                    center_y,
                };
                if(! _target_center_in_range(
                           source,
                           center,
                           action.range))
                {
                    continue;
                }
                const int minimum_target_x = _maximum(
                        0,
                        center.x - area_radius);
                const int maximum_target_x = _minimum(
                        map.active_width() - 1,
                        center.x + area_radius);
                const int minimum_target_y = _maximum(
                        0,
                        center.y - area_radius);
                const int maximum_target_y = _minimum(
                        map.active_height() - 1,
                        center.y + area_radius);
                for(int target_y = minimum_target_y;
                        target_y <= maximum_target_y;
                        ++target_y)
                {
                    for(int target_x = minimum_target_x;
                            target_x <= maximum_target_x;
                            ++target_x)
                    {
                        const grid_point target = {
                            target_x,
                            target_y,
                        };
                        if(map.cost(target) != 0 &&
                                map.terrain_class(target) !=
                                        grid_fully_closed &&
                                _area_contains(
                                        center,
                                        target,
                                        action.range.
                                                area_range_and_shape_flags))
                        {
                            result.mark(source, target);
                        }
                    }
                }
            }
        }
    }

    [[nodiscard]] static constexpr bool
    _target_center_in_range(
            grid_point source,
            grid_point target,
            range_shape range)
    {
        const int dx = _absolute(target.x - source.x);
        const int dy = _absolute(target.y - source.y);
        if(dx + dy > range.maximum_distance())
        {
            return false;
        }
        return (range.distance_and_line_flags & 0x80) == 0 ||
                dx == 0 || dy == 0;
    }

    [[nodiscard]] static constexpr bool _area_contains(
            grid_point center,
            grid_point target,
            std::uint8_t encoded_shape)
    {
        const int dx = _absolute(target.x - center.x);
        const int dy = _absolute(target.y - center.y);
        const int encoded_size = encoded_shape & 0x7F;
        const int radius =
                encoded_size > 0 ? encoded_size - 1 : 0;
        if((encoded_shape & 0x80) != 0)
        {
            return (dx == 0 || dy == 0) &&
                    dx + dy <= radius;
        }
        return dx + dy <= radius;
    }

    [[nodiscard]] static constexpr int _absolute(int value)
    {
        return value < 0 ? -value : value;
    }

    [[nodiscard]] static constexpr int _minimum(
            int first,
            int second)
    {
        return first < second ? first : second;
    }

    [[nodiscard]] static constexpr int _maximum(
            int first,
            int second)
    {
        return first > second ? first : second;
    }
};

}

#endif
