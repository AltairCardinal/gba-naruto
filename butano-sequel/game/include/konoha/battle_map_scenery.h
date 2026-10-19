#ifndef KONOHA_BATTLE_MAP_SCENERY_H
#define KONOHA_BATTLE_MAP_SCENERY_H

namespace konoha
{

struct battle_map_scenery_record
{
    int battle_id = -1;
    int world_x = 0;
    int world_y = 0;
    int bg_priority = 2;
    int z_order = 0;
};

inline constexpr battle_map_scenery_record
        scenario_49_chest_scenery{
            14, 176, -176, 2, -4
        };

[[nodiscard]] constexpr const battle_map_scenery_record*
battle_map_scenery_for(int battle_id)
{
    return battle_id == scenario_49_chest_scenery.battle_id ?
            &scenario_49_chest_scenery :
            nullptr;
}

}

#endif
