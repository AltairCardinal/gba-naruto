#ifndef KONOHA_BATTLE_AI_SCENARIO_RULES_H
#define KONOHA_BATTLE_AI_SCENARIO_RULES_H

#include "konoha/battle_ai_utility.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

struct ai_scenario_rule
{
    std::uint8_t kind = 0;
    std::uint8_t parameter = 0;
    int weight = 0;

    constexpr bool operator==(const ai_scenario_rule&) const = default;
};

struct ai_scenario_rule_config
{
    std::array<ai_scenario_rule, 4> rules = {};
};

inline constexpr std::array<ai_scenario_rule_config, 8> ai_scenario_rule_configs = {{
    {},
    {},
    { std::array<ai_scenario_rule, 4>{{
        { 1, 0, 10000 },
        {},
        {},
        {},
    }} },
    { std::array<ai_scenario_rule, 4>{{
        { 2, 31, 10000 },
        { 3, 74, 10000 },
        { 3, 75, 10000 },
        {},
    }} },
    { std::array<ai_scenario_rule, 4>{{
        { 2, 30, 10000 },
        {},
        {},
        {},
    }} },
    { std::array<ai_scenario_rule, 4>{{
        { 5, 0, 10000 },
        {},
        {},
        {},
    }} },
    { std::array<ai_scenario_rule, 4>{{
        { 5, 0, 10000 },
        {},
        {},
        {},
    }} },
    { std::array<ai_scenario_rule, 4>{{
        { 4, 0, 10000 },
        {},
        {},
        {},
    }} },
}};

struct ai_scenario_rule_context
{
    grid_point origin = {};
    grid_point destination = {};
    int move_range = 0;
    std::uint8_t tile_flags = 0;
    std::uint8_t tile_class = 0;
    battle_side tile_side = battle_side::player;
    battle_side active_side = battle_side::player;
    int battle_id = 0;
};

class battle_ai_scenario_rule_scorer
{
public:
    template<std::size_t UnitCount, std::size_t EventCapacity>
    [[nodiscard]] static ai_utility_components score(
            const battle_unit_instance& actor,
            const std::array<battle_unit_instance, UnitCount>& units,
            const std::array<ai_queued_event, EventCapacity>& events,
            std::size_t event_count,
            const ai_scenario_rule_config& config,
            const ai_scenario_rule_context& context)
    {
        static_assert(UnitCount > 0);
        static_assert(EventCapacity > 0);
        if(event_count > EventCapacity)
        {
            event_count = EventCapacity;
        }
        ai_utility_components result;
        for(const ai_scenario_rule& rule : config.rules)
        {
            switch(rule.kind)
            {
            case 0:
                break;
            case 1:
                result.component_sum +=
                        _opponent_progress(
                                actor, units, context, rule.weight);
                if((context.tile_flags & 1) == 0)
                {
                    result.component_sum += rule.weight;
                }
                result.component_count += 2;
                break;
            case 2:
                result.component_sum += _character_progress(
                        units, rule.parameter, context, rule.weight);
                for(std::size_t event_index = 0; event_index < event_count; ++event_index)
                {
                    const battle_unit_instance* target =
                            _find_unit(units, events[event_index].target_id);
                    if(target && target->character_id == rule.parameter &&
                            _damage_family(events[event_index].code()))
                    {
                        result.component_sum += rule.weight;
                    }
                }
                ++result.component_count;
                break;
            case 3:
                for(std::size_t event_index = 0; event_index < event_count; ++event_index)
                {
                    if(events[event_index].action_id == rule.parameter)
                    {
                        result.component_sum += rule.weight;
                    }
                }
                ++result.component_count;
                break;
            case 4:
                if(context.tile_class == 6 && context.tile_side == context.active_side)
                {
                    result.component_sum += rule.weight;
                }
                ++result.component_count;
                break;
            case 5:
                if(actor.ai_linked_unit == 0)
                {
                    for(std::size_t event_index = 0; event_index < event_count; ++event_index)
                    {
                        const std::uint8_t code = events[event_index].code();
                        if(code == 0x02 || code == 0x07 || code == 0x17)
                        {
                            result.component_sum += rule.weight;
                        }
                    }
                }
                ++result.component_count;
                break;
            default:
                break;
            }
        }
        return result;
    }

private:
    template<std::size_t UnitCount>
    [[nodiscard]] static int _opponent_progress(
            const battle_unit_instance& actor,
            const std::array<battle_unit_instance, UnitCount>& units,
            const ai_scenario_rule_context& context,
            int weight)
    {
        int total = 0;
        int count = 0;
        for(const battle_unit_instance& unit : units)
        {
            if(unit.active && unit.side != actor.side)
            {
                total += _away_progress(
                        unit.position,
                        context,
                        weight);
                ++count;
            }
        }
        return count > 0 ? total / count : 0;
    }

    template<std::size_t UnitCount>
    [[nodiscard]] static int _character_progress(
            const std::array<battle_unit_instance, UnitCount>& units,
            std::uint8_t character,
            const ai_scenario_rule_context& context,
            int weight)
    {
        for(const battle_unit_instance& unit : units)
        {
            if(unit.active && unit.character_id == character)
            {
                return _toward_progress(
                        unit.position,
                        context,
                        weight);
            }
        }
        return 0;
    }

    [[nodiscard]] static int _away_progress(
            grid_point target,
            const ai_scenario_rule_context& context,
            int weight)
    {
        if(context.move_range <= 0)
        {
            return 0;
        }
        const int origin_distance = _distance(
                context.origin,
                target,
                context.battle_id);
        const int destination_distance = _distance(
                context.destination,
                target,
                context.battle_id);
        int progress =
                destination_distance -
                origin_distance;
        if(progress <= 0)
        {
            return 0;
        }
        if(progress > context.move_range)
        {
            progress = context.move_range;
        }
        return progress * weight / context.move_range;
    }

    [[nodiscard]] static int _toward_progress(
            grid_point target,
            const ai_scenario_rule_context& context,
            int weight)
    {
        if(context.move_range <= 0)
        {
            return 0;
        }
        const int origin_distance = _distance(
                context.origin,
                target,
                context.battle_id);
        const int destination_distance = _distance(
                context.destination,
                target,
                context.battle_id);
        const int progress =
                origin_distance -
                destination_distance;
        if(progress <= 0)
        {
            return 0;
        }
        const int denominator =
                origin_distance < context.move_range ?
                origin_distance :
                context.move_range;
        return denominator > 0 ?
                progress * weight / denominator :
                0;
    }

    template<std::size_t UnitCount>
    [[nodiscard]] static const battle_unit_instance* _find_unit(
            const std::array<battle_unit_instance, UnitCount>& units,
            battle_unit_id id)
    {
        for(const battle_unit_instance& unit : units)
        {
            if(unit.id == id)
            {
                return &unit;
            }
        }
        return nullptr;
    }

    [[nodiscard]] static constexpr bool _damage_family(std::uint8_t code)
    {
        return code == 0x01 || code == 0x14 || code == 0x15;
    }

    [[nodiscard]] static int _distance(
            grid_point first,
            grid_point second,
            int battle_id)
    {
        return battle_map_topology_distance(
                battle_id, first, second);
    }
};

}

#endif
