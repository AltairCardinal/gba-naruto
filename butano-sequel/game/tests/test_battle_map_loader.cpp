#include "konoha/battle_map_loader.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    grid_map<9, 22> scenario_41_map;
    grid_map<9, 22> scenario_43_map;
    assert(materialize_battle_map(
                   battle_map_definitions[41],
                   battle_map_cells,
                   scenario_41_map) ==
           battle_map_load_error::none);
    assert(materialize_battle_map(
                   battle_map_definitions[43],
                   battle_map_cells,
                   scenario_43_map) ==
           battle_map_load_error::none);
    assert(scenario_41_map.battle_id() == 41);
    assert(scenario_43_map.battle_id() == 43);
    for(int y = 0; y < 22; ++y)
    {
        for(int x = 0; x < 9; ++x)
        {
            const grid_point point{ x, y };
            assert(scenario_41_map.cost(point) ==
                   scenario_43_map.cost(point));
            assert(scenario_41_map.terrain_class(point) ==
                   scenario_43_map.terrain_class(point));
            assert(! scenario_41_map.occupied(point));
            assert(! scenario_43_map.occupied(point));
        }
    }
    assert(scenario_41_map.cost({ 0, 0 }) == 0);
    assert(scenario_41_map.terrain_class({ 3, 8 }) == 7);
    assert(scenario_41_map.cost({ 3, 8 }) == 1);

    battle_session<12> scenario_41_session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[41],
                   0,
                   {},
                   scenario_41_session)
                   .error == battle_scenario_load_error::none);
    battle_scenario_load_policy fixed_pool_policy;
    fixed_pool_policy.preserve_empty_unit_slots = true;
    battle_session<12> scenario_43_session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[43],
                   0,
                   fixed_pool_policy,
                   scenario_43_session)
                   .error == battle_scenario_load_error::none);

    assert(apply_battle_occupancy(
                   scenario_41_session,
                   scenario_41_map) ==
           battle_map_load_error::none);
    assert(apply_battle_occupancy(
                   scenario_43_session,
                   scenario_43_map) ==
           battle_map_load_error::none);
    assert(scenario_41_map.occupied({ 4, 10 }));
    assert(scenario_41_map.occupied({ 4, 4 }));
    assert(! scenario_41_map.occupied({ 3, 10 }));
    assert(scenario_43_map.occupied(
            scenario_43_session.unit(1)->position));
    assert(! scenario_43_map.occupied({ 0, 0 }));

    battle_map_definition wrong_dimensions =
            battle_map_definitions[41];
    wrong_dimensions.width = 8;
    const grid_map<9, 22> before_wrong_dimensions =
            scenario_41_map;
    assert(materialize_battle_map(
                   wrong_dimensions,
                   battle_map_cells,
                   scenario_41_map) ==
           battle_map_load_error::dimension_mismatch);
    assert(scenario_41_map == before_wrong_dimensions);

    battle_map_definition invalid_range =
            battle_map_definitions[41];
    invalid_range.cell_offset =
            static_cast<std::uint16_t>(
                    battle_map_cells.size());
    assert(materialize_battle_map(
                   invalid_range,
                   battle_map_cells,
                   scenario_41_map) ==
           battle_map_load_error::content_out_of_bounds);
    assert(scenario_41_map == before_wrong_dimensions);

    battle_unit_instance invalid_unit =
            *scenario_41_session.unit(1);
    invalid_unit.id = 8;
    invalid_unit.position = { 0, 0 };
    battle_session<1> blocked_session;
    assert(blocked_session.add_unit(invalid_unit));
    const grid_map<9, 22> before_blocked =
            scenario_41_map;
    assert(apply_battle_occupancy(
                   blocked_session,
                   scenario_41_map) ==
           battle_map_load_error::unit_on_blocked_cell);
    assert(scenario_41_map == before_blocked);

    invalid_unit.position = { 9, 0 };
    battle_session<1> out_of_bounds_session;
    assert(out_of_bounds_session.add_unit(invalid_unit));
    assert(apply_battle_occupancy(
                   out_of_bounds_session,
                   scenario_41_map) ==
           battle_map_load_error::unit_out_of_bounds);
    assert(scenario_41_map == before_blocked);

    battle_unit_instance duplicate_a =
            *scenario_41_session.unit(1);
    duplicate_a.id = 9;
    duplicate_a.position = { 4, 10 };
    battle_unit_instance duplicate_b = duplicate_a;
    duplicate_b.id = 10;
    battle_session<2> duplicate_session;
    assert(duplicate_session.add_unit(duplicate_a));
    assert(duplicate_session.add_unit(duplicate_b));
    assert(apply_battle_occupancy(
                   duplicate_session,
                   scenario_41_map) ==
           battle_map_load_error::duplicate_unit_position);
    assert(scenario_41_map == before_blocked);

    duplicate_a.unit_state_code = 0x06;
    duplicate_a.ai_linked_unit = duplicate_b.id;
    duplicate_b.unit_state_code = 0x06;
    duplicate_b.ai_linked_unit = duplicate_a.id;
    battle_session<2> linked_pair_session;
    assert(linked_pair_session.add_unit(duplicate_a));
    assert(linked_pair_session.add_unit(duplicate_b));
    grid_map<9, 22> linked_pair_map = before_blocked;
    assert(apply_battle_occupancy(
                   linked_pair_session,
                   linked_pair_map) ==
           battle_map_load_error::none);
    assert(linked_pair_map.occupied({ 4, 10 }));
}
