#include "konoha/battle_content_catalog.h"
#include "konoha/battle_runtime_grid.h"
#include "konoha/grid_pathfinder.h"

#include <cassert>
#include <cstddef>

using namespace konoha;

int main()
{
    battle_runtime_grid map;
    assert(map.active_width() ==
           battle_runtime_grid_width);
    assert(map.active_height() ==
           battle_runtime_grid_height);

    assert(materialize_battle_map(
                   battle_map_definitions[43],
                   battle_map_cells,
                   map) ==
           battle_map_load_error::none);
    assert(map.active_width() == 9);
    assert(map.active_height() == 22);
    assert(map.contains({ 8, 21 }));
    assert(! map.contains({ 9, 21 }));
    assert(! map.contains({ 8, 22 }));
    assert(map.cost({ 9, 21 }) == 0);
    assert(map.terrain_class({ 9, 21 }) ==
           grid_fully_closed);

    const battle_runtime_grid before_invalid = map;
    battle_map_definition invalid =
            battle_map_definitions[43];
    invalid.width =
            battle_runtime_grid_width + 1;
    assert(materialize_battle_map(
                   invalid,
                   battle_map_cells,
                   map) ==
           battle_map_load_error::dimension_mismatch);
    assert(map == before_invalid);

    assert(materialize_battle_map(
                   battle_map_definitions[9],
                   battle_map_cells,
                   map) ==
           battle_map_load_error::none);
    assert(map.active_width() == 16);
    assert(map.active_height() == 32);
    assert(map.contains({ 15, 31 }));
    assert(! map.contains({ 16, 31 }));

    grid_map<5, 5> bounded;
    assert(bounded.set_active_dimensions(2, 2));
    assert(bounded.contains({ 1, 1 }));
    assert(! bounded.contains({ 2, 1 }));
    const path_result<8> inside =
            find_path<5, 5, 8>(
                    bounded, { 0, 0 }, { 1, 1 }, 4);
    assert(inside.found);
    const path_result<8> padding =
            find_path<5, 5, 8>(
                    bounded, { 0, 0 }, { 2, 0 }, 4);
    assert(! padding.found);
    assert(! bounded.set_active_dimensions(0, 2));
    assert(bounded.active_width() == 2);
    assert(bounded.active_height() == 2);
    const grid_search_bounds ai_bounds =
            battle_ai::candidate_tile_bounds(
                    bounded, { 1, 1 }, 5);
    assert(ai_bounds.minimum_x == 0);
    assert(ai_bounds.maximum_x == 1);
    assert(ai_bounds.minimum_y == 0);
    assert(ai_bounds.maximum_y == 1);

    int map_count = 0;
    for(std::size_t battle_id = 0;
            battle_id < battle_map_definitions.size();
            ++battle_id)
    {
        const battle_map_definition& definition =
                battle_map_definitions[battle_id];
        assert(materialize_battle_map(
                       definition,
                       battle_map_cells,
                       map) ==
               battle_map_load_error::none);
        assert(map.active_width() == definition.width);
        assert(map.active_height() == definition.height);
        ++map_count;
    }
    assert(map_count == 47);

    battle_scenario_load_policy load_policy;
    load_policy.placeholder_characters =
            { 1, 2, 3, 35, 35, 35 };
    load_policy.preserve_empty_unit_slots = true;
    static battle_runtime_controller controller;
    int loaded_variant_count = 0;
    for(int battle_id = 0; battle_id < 47; ++battle_id)
    {
        for(int variant = 0; variant < 3; ++variant)
        {
            const battle_content_entry entry =
                    generated_battle_content_entry(
                            battle_id, variant);
            assert(entry.valid());
            if(entry.kind ==
                    battle_content_entry_kind::empty)
            {
                continue;
            }
            const battle_scene_control_result loaded =
                    controller.load(
                            *entry.scenario,
                            *entry.map,
                            battle_map_cells,
                            static_cast<std::uint8_t>(
                                    variant),
                            load_policy,
                            *entry.conditions,
                            static_cast<std::uint32_t>(
                                    battle_id * 3 +
                                    variant));
            assert(loaded.success());
            ++loaded_variant_count;
        }
    }
    assert(loaded_variant_count == 85);
}
