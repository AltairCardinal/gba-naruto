#include "konoha/battle_arena_roster.h"
#include "konoha/battle_deployment_flow.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>
#include <cstdint>

using namespace konoha;

namespace
{

battle_arena_combatant combatant(
        std::uint8_t character_id,
        int level,
        ninja_tool_id tool)
{
    battle_arena_combatant result;
    result.progression.character_id = character_id;
    result.progression.level = level;
    result.progression.active = true;
    assert(initialize_character_action_progression(
            result.progression,
            unit_definitions[character_id]));
    result.equipped_tools[0] = tool;
    return result;
}

}

int main()
{
    battle_arena_match_roster roster;
    roster.player[0] = combatant(1, 10, 1);
    roster.player[1] = combatant(2, 12, 17);
    roster.opponent[0] = combatant(1, 25, 93);
    roster.opponent[1] = combatant(12, 30, 46);

    battle_scenario_load_policy policy;
    policy.preserve_empty_unit_slots = true;
    assert(apply_battle_arena_scene_policy(
                   roster, policy) ==
           battle_arena_roster_error::none);

    assert((policy.placeholder_characters ==
           std::array<std::uint8_t, 6>{
                   1,
                   2,
                   no_scenario_character,
                   1,
                   12,
                   no_scenario_character,
           }));
    assert((policy.placeholder_enabled_overridden ==
           std::array<bool, 6>{
                   true, true, true, true, true, true,
           }));
    assert((policy.placeholder_enabled ==
           std::array<bool, 6>{
                   true, true, false, true, true, false,
           }));
    assert(policy.placeholder_progression[0]);
    assert(policy.placeholder_progression[0]->level == 10);
    assert(policy.placeholder_progression[3]->level == 25);
    assert(policy.placeholder_equipped_tools[0]);
    assert((*policy.placeholder_equipped_tools[0])[0] == 1);
    assert((*policy.placeholder_equipped_tools[3])[0] == 93);

    battle_deployment_flow deployment;
    const battle_deployment_result prepared =
            deployment.prepare(
                    battle_scenario_definitions[32],
                    0,
                    policy);
    assert(prepared.success());
    assert(deployment.entry_count() == 4);
    assert(deployment.entry(0)->record_id == 0);
    assert(deployment.entry(1)->record_id == 1);
    assert(deployment.entry(2)->record_id == 3);
    assert(deployment.entry(3)->record_id == 4);

    battle_session<12> session;
    const battle_scenario_load_result loaded =
            load_battle_scenario(
                    battle_scenario_definitions[32],
                    0,
                    policy,
                    session);
    assert(loaded.error ==
           battle_scenario_load_error::none);
    assert(loaded.loaded_unit_count == 4);
    assert(session.unit_count() == 12);

    const battle_unit_instance* player_naruto =
            session.unit(1);
    const battle_unit_instance* player_sasuke =
            session.unit(2);
    const battle_unit_instance* disabled_player =
            session.unit(3);
    const battle_unit_instance* enemy_naruto =
            session.unit(4);
    const battle_unit_instance* enemy_kakashi =
            session.unit(5);
    const battle_unit_instance* disabled_enemy =
            session.unit(6);
    assert(player_naruto && player_naruto->active);
    assert(player_naruto->character_id == 1);
    assert(player_naruto->level == 10);
    assert(player_naruto->equipped_tools[0] == 1);
    assert(player_naruto->control ==
           battle_control::player);
    assert(player_sasuke && player_sasuke->active);
    assert(player_sasuke->level == 12);
    assert(disabled_player && ! disabled_player->active);
    assert(enemy_naruto && enemy_naruto->active);
    assert(enemy_naruto->character_id == 1);
    assert(enemy_naruto->level == 25);
    assert(enemy_naruto->equipped_tools[0] == 93);
    assert(enemy_naruto->control == battle_control::ai);
    assert(enemy_kakashi && enemy_kakashi->active);
    assert(enemy_kakashi->character_id == 12);
    assert(enemy_kakashi->level == 30);
    assert(disabled_enemy && ! disabled_enemy->active);

    battle_arena_match_roster invalid = roster;
    invalid.opponent[0].equipped_tools[0] = 0xFF;
    battle_scenario_load_policy unchanged;
    unchanged.placeholder_characters[5] = 42;
    const battle_scenario_load_policy before = unchanged;
    assert(apply_battle_arena_scene_policy(
                   invalid, unchanged) ==
           battle_arena_roster_error::
                   invalid_ninja_tool);
    assert(unchanged.placeholder_characters ==
           before.placeholder_characters);
    assert(unchanged.placeholder_enabled ==
           before.placeholder_enabled);
    assert(unchanged.placeholder_progression ==
           before.placeholder_progression);

    battle_arena_match_roster missing_side;
    missing_side.player[0] = combatant(1, 1, 0);
    assert(apply_battle_arena_scene_policy(
                   missing_side, unchanged) ==
           battle_arena_roster_error::empty_opponent);
    assert(unchanged.placeholder_characters ==
           before.placeholder_characters);
}
