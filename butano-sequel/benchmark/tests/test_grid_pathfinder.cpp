#include "konoha_bench/grid_pathfinder.h"

#include <cassert>

using namespace konoha_bench;

int main()
{
    grid_map<5, 5> map;
    const auto direct = find_path<5, 5, 8>(map, { 0, 0 }, { 2, 0 }, 2);
    assert(direct.found && ! direct.overflow);
    assert(direct.total_cost == 2);
    assert(direct.length == 3);
    assert((direct.points[1] == point{ 1, 0 }));

    map.set_cost({ 1, 0 }, 0);
    const auto around_wall = find_path<5, 5, 8>(map, { 0, 0 }, { 2, 0 }, 6);
    assert(around_wall.found);
    assert(around_wall.total_cost == 4);
    assert((around_wall.points[1] == point{ 0, 1 }));

    map.set_cost({ 1, 0 }, 9);
    const auto around_cost = find_path<5, 5, 8>(map, { 0, 0 }, { 2, 0 }, 20);
    assert(around_cost.found);
    assert(around_cost.total_cost == 4);

    const auto over_budget = find_path<5, 5, 8>(map, { 0, 0 }, { 2, 0 }, 3);
    assert(! over_budget.found);

    map.set_occupied({ 2, 0 }, true);
    assert((! find_path<5, 5, 8>(map, { 0, 0 }, { 2, 0 }, 20).found));
    map.set_occupied({ 2, 0 }, false);

    grid_map<3, 3> tie_map;
    const auto stable = find_path<3, 3, 8>(tie_map, { 1, 1 }, { 2, 2 }, 2);
    assert(stable.found);
    assert((stable.points[1] == point{ 2, 1 }));

    tie_map.set_cost({ 2, 1 }, 0);
    tie_map.set_cost({ 1, 2 }, 0);
    assert((! find_path<3, 3, 8>(tie_map, { 1, 1 }, { 2, 2 }, 8).found));

    grid_map<4, 1> narrow_map;
    const auto overflow = find_path<4, 1, 2>(narrow_map, { 0, 0 }, { 3, 0 }, 3);
    assert(! overflow.found);
    assert(overflow.overflow);

    grid_map<2, 1> occupied_start;
    occupied_start.set_occupied({ 0, 0 }, true);
    assert((find_path<2, 1, 2>(occupied_start, { 0, 0 }, { 1, 0 }, 1).found));
}
