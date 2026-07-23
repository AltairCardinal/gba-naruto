#include "konoha/battle_action_loadout.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    const action_loadout<15> naruto_level_one = build_primary_action_loadout(
            unit_definitions[1], 1);
    assert(naruto_level_one.count == 3);
    assert(naruto_level_one.ids[0] == 2);
    assert(naruto_level_one.ids[1] == 5);
    assert(naruto_level_one.ids[2] == 7);

    const action_loadout<15> naruto_level_four = build_primary_action_loadout(
            unit_definitions[1], 4);
    assert(naruto_level_four.count == 6);
    assert(naruto_level_four.contains(3));
    assert(naruto_level_four.contains(4));
    assert(naruto_level_four.contains(8));

    const action_loadout<15> scenario_enemy = build_primary_action_loadout(
            unit_definitions[30], 1);
    assert(scenario_enemy.count == 6);
    for(ability_id id = 1; id <= 6; ++id)
    {
        assert(scenario_enemy.contains(id));
    }
    const action_definition_set<15> enemy_actions = materialize_action_loadout(
            scenario_enemy, active_action_definitions);
    assert(enemy_actions.count == 6);
    assert(enemy_actions.values[0].id == 1);
    assert(enemy_actions.values[4].id == 5);

    const action_loadout<15> restricted = filter_action_loadout(
            naruto_level_one, [](ability_id id) { return id == 5; });
    assert(restricted.count == 1);
    assert(restricted.ids[0] == 5);
}
