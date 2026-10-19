#ifndef KONOHA_BATTLE_TERRAIN_TRAVERSAL_H
#define KONOHA_BATTLE_TERRAIN_TRAVERSAL_H

#include "konoha/generated_battle_passive_content.h"
#include "konoha/grid_pathfinder.h"

namespace konoha
{

inline constexpr std::uint8_t
        terrain_class_one_passive_target = 0x1A;
inline constexpr std::uint8_t
        terrain_class_seven_passive_target = 0x1B;
inline constexpr std::uint8_t
        terrain_class_three_passive_target = 0x1C;

[[nodiscard]] inline grid_terrain_traversal_limits
battle_terrain_traversal_limits(
        const battle_passive_state& passives)
{
    grid_terrain_traversal_limits result;
    const passive_query_result class_one =
            passives.query(
                    terrain_class_one_passive_target,
                    passive_definitions);
    const passive_query_result class_seven =
            passives.query(
                    terrain_class_seven_passive_target,
                    passive_definitions);
    const passive_query_result class_three =
            passives.query(
                    terrain_class_three_passive_target,
                    passive_definitions);
    if(class_one.found)
    {
        result.class_one = class_one.value_a;
    }
    if(class_seven.found)
    {
        result.class_seven = class_seven.value_a;
    }
    if(class_three.found)
    {
        result.class_three = class_three.value_a;
    }
    return result;
}

}

#endif
