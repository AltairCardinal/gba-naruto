#include "konoha/battle_ai_target_index.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        grid_point position,
        int hp,
        int max_hp,
        int attack,
        int defense,
        int agility,
        int movement)
{
    battle_unit_instance result = {
        id,
        side,
        battle_control::ai,
        position,
        battle_facing::down,
        hp,
        max_hp,
        10,
        10,
        movement,
        true,
        {},
    };
    result.attack = attack;
    result.defense = defense;
    result.agility = agility;
    return result;
}

int distance(grid_point first, grid_point second)
{
    const int dx = first.x > second.x ? first.x - second.x : second.x - first.x;
    const int dy = first.y > second.y ? first.y - second.y : second.y - first.y;
    return dx + dy;
}

}

int main()
{
    std::array units = {
        unit(1, battle_side::enemy, { 0, 0 }, 90, 100, 50, 50, 50, 5),
        unit(2, battle_side::enemy, { 1, 0 }, 20, 200, 40, 60, 60, 6),
        unit(3, battle_side::enemy, { 2, 0 }, 50, 50, 10, 20, 30, 2),
        unit(4, battle_side::player, { 5, 0 }, 10, 100, 30, 40, 50, 5),
        unit(5, battle_side::player, { 2, 0 }, 60, 60, 5, 10, 20, 1),
        unit(6, battle_side::player, { 2, 0 }, 60, 60, 5, 10, 20, 1),
    };

    const ai_target_index index = battle_ai_target_index_builder::build(
            units[0],
            units,
            [](const battle_unit_instance& actor, const battle_unit_instance& candidate)
            {
                return distance(actor.position, candidate.position);
            });

    assert(index.same_side[ai_target_selector::hp_ratio] == 2);
    assert(index.same_side[ai_target_selector::max_hp] == 3);
    assert(index.same_side[ai_target_selector::attack] == 3);
    assert(index.same_side[ai_target_selector::defense] == 3);
    assert(index.same_side[ai_target_selector::agility] == 3);
    assert(index.same_side[ai_target_selector::movement] == 3);
    assert(index.same_side[ai_target_selector::map_distance] == 1);

    assert(index.opposite_side[ai_target_selector::hp_ratio] == 4);
    assert(index.opposite_side[ai_target_selector::max_hp] == 5);
    assert(index.opposite_side[ai_target_selector::attack] == 5);
    assert(index.opposite_side[ai_target_selector::defense] == 5);
    assert(index.opposite_side[ai_target_selector::agility] == 5);
    assert(index.opposite_side[ai_target_selector::movement] == 5);
    assert(index.opposite_side[ai_target_selector::map_distance] == 5);

    // Equal metrics preserve the first unit-slot scan result.
    assert(index.opposite_side[ai_target_selector::attack] != 6);

    units[0].ai_role = 0;
    units[5].ai_role = 2;
    units[5].ai_linked_unit = units[0].id;
    const ai_target_index forced = battle_ai_target_index_builder::build(
            units[0],
            units,
            [](const battle_unit_instance& actor, const battle_unit_instance& candidate)
            {
                return distance(actor.position, candidate.position);
            });
    for(std::size_t selector = 0; selector < ai_target_selector_count; ++selector)
    {
        assert(forced.opposite_side.units[selector] == 6);
    }

    units[5].active = false;
    const ai_target_index inactive_override = battle_ai_target_index_builder::build(
            units[0],
            units,
            [](const battle_unit_instance& actor, const battle_unit_instance& candidate)
            {
                return distance(actor.position, candidate.position);
            });
    assert(inactive_override.opposite_side[ai_target_selector::attack] == 5);

    grid_map<9, 20> topology_map;
    assert(topology_map.set_active_dimensions(9, 20));
    assert(topology_map.set_battle_id(16));
    std::array topology_units = {
        unit(10, battle_side::enemy, { 4, 8 }, 100, 100, 10, 10, 10, 3),
        unit(11, battle_side::player, { 4, 10 }, 100, 100, 10, 10, 10, 3),
        unit(12, battle_side::player, { 7, 10 }, 100, 100, 10, 10, 10, 3),
    };
    const ai_target_index topology_index =
            battle_ai_target_index_builder::build(
                    topology_map,
                    topology_units[0],
                    topology_units);
    assert(topology_index.opposite_side[
                   ai_target_selector::map_distance] == 12);
}
