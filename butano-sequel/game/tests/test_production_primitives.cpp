#include "konoha/battle_action_system.h"
#include "konoha/grid_pathfinder.h"

#include <array>
#include <cassert>

int main()
{
    konoha::grid_map<3, 3> map;
    const auto path = konoha::find_path<3, 3, 8>(map, { 0, 0 }, { 2, 0 }, 2);
    assert(path.found && path.total_cost == 2);
    const auto costs = konoha::compute_reachable_costs(map, konoha::grid_point{ 0, 0 }, 2);
    assert(costs.valid);
    assert(costs.cost({ 2, 0 }) == 2);
    assert(costs.cost({ 2, 2 }) == -1);

    konoha::grid_map<3, 3> terrain_map;
    assert(terrain_map.set_terrain_class(
            { 1, 1 }, konoha::grid_terrain_class_one));
    assert(terrain_map.terrain_class({ 1, 1 }) ==
           konoha::grid_terrain_class_one);
    // Physical adjacency remains separate from the ROM terrain-class
    // traversal budget. Class 1 is not a generic wall, but a unit without
    // the matching passive cannot include the tile in a movement path.
    assert(terrain_map.can_step({ 1, 0 }, { 1, 1 }));
    assert(terrain_map.can_step({ 1, 1 }, { 1, 0 }));
    const auto untrained_terrain_path =
            konoha::find_path<3, 3, 8>(
                    terrain_map, { 1, 0 }, { 1, 1 }, 1);
    assert(! untrained_terrain_path.found);
    konoha::grid_terrain_traversal_limits class_one_training;
    class_one_training.class_one = 1;
    const auto trained_terrain_path =
            konoha::find_path<3, 3, 8>(
                    terrain_map,
                    { 1, 0 },
                    { 1, 1 },
                    1,
                    class_one_training);
    assert(trained_terrain_path.found);
    assert(trained_terrain_path.total_cost == 1);

    assert(terrain_map.set_terrain_class(
            { 2, 2 }, konoha::grid_fully_closed));
    assert(! terrain_map.can_step({ 2, 1 }, { 2, 2 }));
    terrain_map.set_occupied({ 0, 1 }, true);
    assert(! terrain_map.can_step({ 0, 0 }, { 0, 1 }));

    konoha::battle_unit_instance source = {
        1,
        konoha::battle_side::player,
        konoha::battle_control::player,
        { 0, 0 },
        konoha::battle_facing::right,
        20,
        20,
        4,
        4,
        2,
        true,
        {},
    };
    source.attack = 20;
    konoha::battle_unit_instance target = {
        2,
        konoha::battle_side::enemy,
        konoha::battle_control::ai,
        { 1, 0 },
        konoha::battle_facing::left,
        10,
        10,
        0,
        0,
        2,
        true,
        {},
    };
    konoha::battle_session<2> battle;
    assert(battle.add_unit(source));
    assert(battle.add_unit(target));
    assert(battle.start_round() ==
           konoha::battle_transition::unit_selection_opened);
    assert(battle.select_unit(1) ==
           konoha::battle_transition::action_draft_opened);
    konoha::action_definition strike;
    strike.id = 5;
    strike.effect = { 0x01, 0, 10, 1, 100, 0 };
    strike.target = {
        konoha::target_policy_kind::opponent_unit,
        0,
    };
    strike.range = { 1, 1 };
    konoha::deterministic_rng rng(1);
    const konoha::action_result result =
            konoha::battle_action_resolver::resolve_draft(
                    battle,
                    2,
                    konoha::no_battle_unit,
                    strike,
                    { 1, 0 },
                    rng);
    assert(result.success());
    assert(battle.unit(2)->hp == 0);
}
