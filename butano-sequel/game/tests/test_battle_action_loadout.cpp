#include "konoha/battle_action_loadout.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    const primary_action_state_array naruto_level_one_states =
            initialize_primary_action_states(
                    unit_definitions[1], 1);
    const action_loadout<15> naruto_level_one = build_primary_action_loadout(
            unit_definitions[1], naruto_level_one_states);
    assert(naruto_level_one.count == 3);
    assert(naruto_level_one.ids[0] == 2);
    assert(naruto_level_one.ids[1] == 5);
    assert(naruto_level_one.ids[2] == 7);
    assert(naruto_level_one.levels[0] == 1);
    assert(naruto_level_one.levels[1] == 1);
    assert(naruto_level_one.levels[2] == 1);

    const primary_action_state_array naruto_level_four_states =
            initialize_primary_action_states(
                    unit_definitions[1], 4);
    const action_loadout<15> naruto_level_four = build_primary_action_loadout(
            unit_definitions[1], naruto_level_four_states);
    assert(naruto_level_four.count == 3);
    assert(! naruto_level_four.contains(3));
    assert(! naruto_level_four.contains(4));
    assert(! naruto_level_four.contains(8));
    assert(naruto_level_four_states[1] == unlocked_action_level);
    assert(naruto_level_four_states[2] == unlocked_action_level);
    assert(naruto_level_four_states[6] == unlocked_action_level);

    const primary_action_state_array scenario_enemy_states =
            initialize_primary_action_states(
                    unit_definitions[30], 1);
    const action_loadout<15> scenario_enemy = build_primary_action_loadout(
            unit_definitions[30], scenario_enemy_states);
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

    primary_action_state_array trained_naruto_states =
            naruto_level_one_states;
    trained_naruto_states[3] = 2;
    const action_definition_set<15> trained_naruto_actions =
            materialize_action_loadout(
                    build_primary_action_loadout(
                            unit_definitions[1],
                            trained_naruto_states),
                    active_action_definitions);
    assert(trained_naruto_actions.count == 3);
    assert(trained_naruto_actions.values[1].id == 5);
    assert(trained_naruto_actions.values[1].effect.potency == 15);

    const action_loadout<15> restricted = filter_action_loadout(
            naruto_level_one, [](ability_id id) { return id == 5; });
    assert(restricted.count == 1);
    assert(restricted.ids[0] == 5);
    assert(restricted.levels[0] == 1);
}
