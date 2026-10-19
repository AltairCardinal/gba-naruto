#ifndef KONOHA_BATTLE_AI_TARGET_INDEX_H
#define KONOHA_BATTLE_AI_TARGET_INDEX_H

#include "konoha/battle_attributes.h"
#include "konoha/battle_map_topology_distance.h"
#include "konoha/battle_session.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace konoha
{

enum class ai_target_selector : std::uint8_t
{
    hp_ratio = 0,
    max_hp = 1,
    attack = 2,
    defense = 3,
    agility = 4,
    movement = 5,
    map_distance = 6,
};

inline constexpr std::size_t ai_target_selector_count = 7;

struct ai_target_bank
{
    std::array<battle_unit_id, ai_target_selector_count> units = {
        no_battle_unit,
        no_battle_unit,
        no_battle_unit,
        no_battle_unit,
        no_battle_unit,
        no_battle_unit,
        no_battle_unit,
    };

    [[nodiscard]] constexpr battle_unit_id operator[](ai_target_selector selector) const
    {
        return units[static_cast<std::size_t>(selector)];
    }
};

struct ai_target_index
{
    ai_target_bank same_side;
    ai_target_bank opposite_side;
};

class battle_ai_target_index_builder
{
public:
    template<
            int Width,
            int Height,
            std::size_t UnitCount>
    [[nodiscard]] static ai_target_index build(
            const grid_map<Width, Height>& map,
            const battle_unit_instance& actor,
            const std::array<
                    battle_unit_instance,
                    UnitCount>& units)
    {
        return build(
                actor,
                units,
                [&map](
                        const battle_unit_instance& first,
                        const battle_unit_instance& second)
                {
                    return battle_map_topology_distance(
                            map.battle_id(),
                            first.position,
                            second.position);
                });
    }

    template<std::size_t UnitCount, typename DistanceFunction>
    [[nodiscard]] static ai_target_index build(
            const battle_unit_instance& actor,
            const std::array<battle_unit_instance, UnitCount>& units,
            DistanceFunction distance)
    {
        static_assert(UnitCount > 0);
        ai_target_index result;
        std::array<int, ai_target_selector_count> same_metrics;
        std::array<int, ai_target_selector_count> opposite_metrics;
        same_metrics.fill(std::numeric_limits<int>::max());
        opposite_metrics.fill(std::numeric_limits<int>::max());

        for(const battle_unit_instance& candidate : units)
        {
            if(! candidate.active)
            {
                continue;
            }
            ai_target_bank& bank = candidate.side == actor.side ?
                    result.same_side : result.opposite_side;
            std::array<int, ai_target_selector_count>& metrics =
                    candidate.side == actor.side ? same_metrics : opposite_metrics;
            _consider(actor, candidate, distance, bank, metrics);
        }
        for(const battle_unit_instance& candidate : units)
        {
            if(candidate.active && candidate.side != actor.side &&
                    _forced_opponent(candidate, units))
            {
                result.opposite_side.units.fill(candidate.id);
                break;
            }
        }
        return result;
    }

private:
    template<std::size_t UnitCount>
    [[nodiscard]] static bool _forced_opponent(
            const battle_unit_instance& candidate,
            const std::array<battle_unit_instance, UnitCount>& units)
    {
        if(candidate.ai_role != 2 || candidate.ai_linked_unit == no_battle_unit)
        {
            return false;
        }
        for(const battle_unit_instance& linked : units)
        {
            if(linked.id == candidate.ai_linked_unit)
            {
                return linked.ai_role == 0;
            }
        }
        return false;
    }

    template<typename DistanceFunction>
    static void _consider(
            const battle_unit_instance& actor,
            const battle_unit_instance& candidate,
            DistanceFunction distance,
            ai_target_bank& bank,
            std::array<int, ai_target_selector_count>& best_metrics)
    {
        const battle_attribute_view attributes = battle_attribute_system::view(candidate);
        const int hp_ratio = attributes.max_hp > 0 ?
                candidate.hp * 1000 / attributes.max_hp :
                std::numeric_limits<int>::max();
        const std::array<int, ai_target_selector_count> metrics = {
            hp_ratio,
            attributes.max_hp,
            attributes.attack,
            attributes.defense,
            attributes.agility,
            attributes.move_range,
            distance(actor, candidate),
        };
        for(std::size_t selector = 0; selector < metrics.size(); ++selector)
        {
            if(metrics[selector] < best_metrics[selector])
            {
                best_metrics[selector] = metrics[selector];
                bank.units[selector] = candidate.id;
            }
        }
    }

};

}

#endif
