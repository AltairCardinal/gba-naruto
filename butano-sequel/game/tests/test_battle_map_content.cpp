#include "konoha/battle_map_topology_distance.h"
#include "konoha/generated_battle_map_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    static_assert(battle_map_definitions.size() == 47);
    static_assert(battle_map_cells.size() == 12151);
    static_assert(battle_map_distance_records.size() == 47 * 8);

    const battle_map_definition* scenario_41 =
            battle_map_definition_for(41);
    assert(scenario_41);
    assert(scenario_41->width == 9);
    assert(scenario_41->height == 22);
    assert(scenario_41->cell_count == 198);
    assert(! battle_map_definition_for(47));

    const battle_map_cell* border =
            battle_map_cell_at(*scenario_41, 0, 0);
    const battle_map_cell* class_one =
            battle_map_cell_at(*scenario_41, 1, 13);
    const battle_map_cell* class_three =
            battle_map_cell_at(*scenario_41, 5, 8);
    assert(border);
    assert(border->raw_attributes == 0x000F);
    assert(border->fully_blocked());
    assert(class_one);
    assert(class_one->terrain_class() ==
           battle_map_terrain_class_one);
    assert(! class_one->fully_blocked());
    assert(class_three);
    assert(class_three->terrain_class() ==
           battle_map_terrain_class_three);
    assert(! battle_map_cell_at(*scenario_41, -1, 0));
    assert(! battle_map_cell_at(*scenario_41, 9, 0));

    const battle_map_distance_record* scenario_16_records =
            battle_map_distance_records_for(16);
    assert(scenario_16_records);
    assert(scenario_16_records[0].bytes[0] == 2);
    assert(scenario_16_records[0].bytes[1] == 9);
    assert(battle_map_topology_distance(
                   16, { 4, 8 }, { 4, 10 }) == 8);
    assert(battle_map_topology_distance(
                   16, { 4, 10 }, { 4, 8 }) == 8);
    assert(battle_map_topology_distance(
                   0, { 4, 8 }, { 4, 10 }) == 2);
    assert(battle_map_topology_distance(
                   27, { 3, 5 }, { 5, 5 }) == 10);
    assert(battle_map_topology_distance(
                   5, { 7, 7 }, { 7, 8 }) == 7);
    assert(battle_map_topology_distance(
                   23, { 13, 3 }, { 12, 9 }) == 1);
    assert(battle_map_topology_distance(
                   24, { 1, 8 }, { 7, 8 }) == 8);
    assert(battle_map_topology_distance(
                   17, { 8, 2 }, { 10, 5 }) == 1);
    assert(! battle_map_distance_records_for(47));

    for(const battle_map_definition& definition :
            battle_map_definitions)
    {
        for(int first_y = 0;
                first_y < definition.height;
                ++first_y)
        {
            for(int first_x = 0;
                    first_x < definition.width;
                    ++first_x)
            {
                for(int second_y = 0;
                        second_y < definition.height;
                        ++second_y)
                {
                    for(int second_x = 0;
                            second_x < definition.width;
                            ++second_x)
                    {
                        const grid_point first = {
                            first_x,
                            first_y,
                        };
                        const grid_point second = {
                            second_x,
                            second_y,
                        };
                        assert(battle_map_topology_distance(
                                       definition.battle_id,
                                       first,
                                       second) ==
                               battle_map_topology_distance(
                                       definition.battle_id,
                                       second,
                                       first));
                    }
                }
            }
        }
    }

    const battle_map_definition* scenario_43 =
            battle_map_definition_for(43);
    assert(scenario_43);
    for(int y = 0; y < scenario_41->height; ++y)
    {
        for(int x = 0; x < scenario_41->width; ++x)
        {
            assert(*battle_map_cell_at(*scenario_41, x, y) ==
                   *battle_map_cell_at(*scenario_43, x, y));
        }
    }
}
