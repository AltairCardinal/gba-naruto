#include "konoha/battle_action_catalog.h"
#include "konoha/battle_action_execution.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/battle_results.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>

using namespace konoha;

static_assert(
        action_slot_definition{ 1, 2, 3, 4 } ==
        action_slot_definition{ 1, 2, 3, 4 });
static_assert(
        action_slot_definition{ 1, 2, 3, 4 } !=
        action_slot_definition{ 1, 2, 3, 5 });

int main()
{
    battle_scenario_load_policy escort_policy;
    escort_policy.scripted_characters[30] = true;
    escort_policy.character_levels[1] = 9;
    escort_policy.character_equipped_tools[1] = { 1, 17, 73, 93 };

    battle_session<21> escort_session;
    const battle_scenario_load_result escort_result = load_battle_scenario(
            battle_scenario_definitions[15],
            0,
            escort_policy,
            escort_session);
    assert(escort_result.error == battle_scenario_load_error::none);
    assert(escort_result.loaded_unit_count == 9);
    assert(escort_session.battle_id() == 15);
    assert(escort_session.unit_count() == 9);
    assert(escort_session.unit_at(0)->id == 1);
    assert(escort_session.unit_at(0)->character_id == 1);
    assert(escort_session.unit_at(0)->level == 9);
    const character_stat_values expected_level_nine =
            character_stats_at_level(1, 9);
    assert(
            escort_session.unit_at(0)->max_hp ==
            expected_level_nine.max_hp);
    assert(
            escort_session.unit_at(0)->hp ==
            expected_level_nine.max_hp);
    assert(
            escort_session.unit_at(0)->max_chakra ==
            expected_level_nine.chakra_capacity);
    assert(
            escort_session.unit_at(0)->chakra ==
            expected_level_nine.chakra_capacity);
    assert(
            escort_session.unit_at(0)->attack ==
            expected_level_nine.attack);
    assert(
            escort_session.unit_at(0)->base_attack ==
            expected_level_nine.attack);
    assert(
            escort_session.unit_at(0)->defense ==
            expected_level_nine.defense);
    assert(
            escort_session.unit_at(0)->base_defense ==
            expected_level_nine.defense);
    assert(
            escort_session.unit_at(0)->agility ==
            expected_level_nine.agility);
    assert(
            escort_session.unit_at(0)->base_agility ==
            expected_level_nine.agility);
    assert(
            escort_session.unit_at(0)->move_range ==
            expected_level_nine.movement);
    assert(
            escort_session.unit_at(0)->base_move_range ==
            expected_level_nine.movement);
    assert(
            escort_session.unit_at(0)->ninja_tool_capacity ==
            expected_level_nine.ninja_tool_capacity);
    const std::array<ninja_tool_id, 9> expected_tools = {
        1, 17, 73, 93, 0, 0, 0, 0, 0
    };
    assert(
            escort_session.unit_at(0)->equipped_tools ==
            expected_tools);
    assert(escort_session.unit_at(0)->position == grid_point({ 1, 9 }));
    assert(escort_session.unit_at(3)->id == 4);
    assert(escort_session.unit_at(3)->character_id == 30);
    assert(escort_session.unit_at(3)->level == 3);
    assert(escort_session.unit_at(3)->control == battle_control::scripted);
    assert(escort_session.unit_at(3)->formation_unit_parameter == 2);
    assert(escort_session.unit_at(3)->ai_config_id == 2);
    assert(escort_session.unit_at(8)->id == 9);
    assert(escort_session.unit_at(8)->character_id == 35);
    assert(escort_session.unit_at(8)->side == battle_side::enemy);
    assert(escort_session.unit_at(8)->control == battle_control::ai);
    assert(escort_session.unit_at(8)->formation_unit_parameter == 1);
    assert(escort_session.unit_at(8)->ai_config_id == 1);

    battle_session<12> specified_action_rule_session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[1],
                   0,
                   {},
                   specified_action_rule_session)
                   .error == battle_scenario_load_error::none);
    assert(specified_action_rule_session.unit(5)->character_id == 25);
    assert(specified_action_rule_session.unit(5)->control == battle_control::ai);
    assert(specified_action_rule_session.unit(5)->formation_unit_parameter == 3);
    assert(specified_action_rule_session.unit(5)->ai_config_id == 3);
    assert(specified_action_rule_session.unit(6)->character_id == 26);
    assert(specified_action_rule_session.unit(6)->ai_config_id == 3);

    battle_session<12> terrain_rule_session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[20],
                   0,
                   {},
                   terrain_rule_session)
                   .error == battle_scenario_load_error::none);
    assert(terrain_rule_session.unit(4)->character_id == 4);
    assert(terrain_rule_session.unit(4)->control == battle_control::ai);
    assert(terrain_rule_session.unit(4)->formation_unit_parameter == 7);
    assert(terrain_rule_session.unit(4)->ai_config_id == 7);

    battle_scenario_load_policy fixed_pool_policy;
    fixed_pool_policy.preserve_empty_unit_slots = true;
    battle_session<12> fixed_pool;
    const battle_scenario_load_result fixed_pool_result =
            load_battle_scenario(
                    battle_scenario_definitions[43],
                    0,
                    fixed_pool_policy,
                    fixed_pool);
    assert(fixed_pool_result.error ==
           battle_scenario_load_error::none);
    assert(fixed_pool_result.loaded_unit_count == 4);
    assert(fixed_pool.unit_count() == 12);
    for(battle_unit_id id = 1; id <= 4; ++id)
    {
        assert(fixed_pool.unit(id));
        assert(fixed_pool.unit(id)->active);
    }
    for(battle_unit_id id = 5; id <= 12; ++id)
    {
        assert(fixed_pool.unit(id));
        assert(! fixed_pool.unit(id)->active);
    }

    battle_session<11> fixed_pool_too_small;
    const battle_session<11> fixed_pool_too_small_before =
            fixed_pool_too_small;
    const battle_scenario_load_result fixed_pool_capacity_error =
            load_battle_scenario(
                    battle_scenario_definitions[43],
                    0,
                    fixed_pool_policy,
                    fixed_pool_too_small);
    assert(fixed_pool_capacity_error.error ==
           battle_scenario_load_error::capacity_exceeded);
    assert(fixed_pool_too_small ==
           fixed_pool_too_small_before);

    battle_session<21> unresolved_session;
    const battle_session<21> unresolved_before = unresolved_session;
    const battle_scenario_load_result unresolved = load_battle_scenario(
            battle_scenario_definitions[32],
            0,
            {},
            unresolved_session);
    assert(
            unresolved.error ==
            battle_scenario_load_error::unresolved_deployment_placeholder);
    assert(unresolved.record_id == 0);
    assert(unresolved_session == unresolved_before);

    battle_scenario_load_policy deployment_policy;
    deployment_policy.placeholder_characters = { 1, 2, 3, 35, 35, 35 };
    battle_session<21> deployment_session;
    const battle_scenario_load_result deployment = load_battle_scenario(
            battle_scenario_definitions[32],
            0,
            deployment_policy,
            deployment_session);
    assert(deployment.error == battle_scenario_load_error::none);
    assert(deployment.loaded_unit_count == 6);
    assert(deployment_session.unit_at(0)->character_id == 1);
    assert(deployment_session.unit_at(1)->character_id == 2);
    assert(deployment_session.unit_at(2)->character_id == 3);
    assert(deployment_session.unit_at(3)->character_id == 35);
    assert(deployment_session.unit_at(3)->control == battle_control::ai);
    assert(deployment_session.unit_at(3)->ai_config_id == 1);
    assert(deployment_session.unit_at(5)->character_id == 35);
    assert(deployment_session.unit_at(5)->ai_config_id == 1);

    battle_scenario_load_policy mirror_policy;
    battle_session<12> mirror_session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[10],
                   0,
                   mirror_policy,
                   mirror_session)
                   .error == battle_scenario_load_error::none);
    assert(mirror_session.battle_id() == 10);
    const battle_unit_instance* enemy_naruto =
            mirror_session.unit(3);
    assert(enemy_naruto);
    assert(enemy_naruto->side == battle_side::enemy);
    assert(enemy_naruto->character_id == 1);
    assert(enemy_naruto->level == 20);
    assert(
            enemy_naruto->max_hp ==
            character_stats_at_level(1, 20).max_hp);
    assert(
            enemy_naruto->attack ==
            character_stats_at_level(1, 20).attack);
    assert(enemy_naruto->primary_action_ids[0] == 1);
    assert(enemy_naruto->primary_action_ids[1] == 2);
    assert(enemy_naruto->primary_action_ids[2] == 5);
    assert(enemy_naruto->primary_action_levels[0] == 2);
    assert(enemy_naruto->primary_action_levels[1] == 2);
    assert(enemy_naruto->primary_action_levels[2] == 2);
    assert(enemy_naruto->passives.slot(0) ==
           (passive_slot_state{ 6, 1 }));
    assert(enemy_naruto->passives.slot(1) ==
           (passive_slot_state{ 5, 3 }));
    assert(enemy_naruto->passives.slot(2) ==
           (passive_slot_state{ 2, 2 }));
    assert(
            enemy_naruto->equipped_tools ==
            (std::array<ninja_tool_id, 9>{
                1, 19, 41, 41, 41, 0, 0, 0, 0
            }));
    const battle_action_catalog_result enemy_naruto_catalog =
            battle_action_catalog::build(*enemy_naruto);
    assert(enemy_naruto_catalog.error ==
           battle_action_catalog_error::none);
    assert(enemy_naruto_catalog.count == 8);
    assert(enemy_naruto_catalog.entries[0].action_id == 1);
    assert(enemy_naruto_catalog.entries[1].action_id == 2);
    assert(enemy_naruto_catalog.entries[2].action_id == 5);
    assert(enemy_naruto_catalog.entries[3].kind ==
           battle_action_source_kind::ninja_tool);
    assert(enemy_naruto_catalog.entries[7].tool_slot == 4);

    battle_session<12> hidden_mist_session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[8],
                   0,
                   {},
                   hidden_mist_session)
                   .error == battle_scenario_load_error::none);
    const battle_unit_instance* zabuza =
            hidden_mist_session.unit(2);
    assert(zabuza);
    assert(zabuza->side == battle_side::enemy);
    assert(zabuza->character_id == 20);
    assert(zabuza->level == 25);
    assert(zabuza->primary_action_ids[4] == 62);
    assert(zabuza->primary_action_levels[4] == 3);
    const battle_action_catalog_result zabuza_catalog =
            battle_action_catalog::build(*zabuza);
    assert(zabuza_catalog.error ==
           battle_action_catalog_error::none);
    bool hidden_mist_found = false;
    for(std::size_t index = 0;
            index < zabuza_catalog.count;
            ++index)
    {
        const battle_action_catalog_entry& entry =
                zabuza_catalog.entries[index];
        if(entry.kind ==
                        battle_action_source_kind::
                                active_action &&
                entry.action_id == 62)
        {
            hidden_mist_found = true;
            assert(entry.action_level == 3);
            assert(entry.action.effect.code == 0x0D);
            assert(entry.action.cost.kind ==
                   action_cost_kind::current_chakra);
            assert(entry.action.cost.scalar == 2);
            assert(entry.action.target.kind ==
                   target_policy_kind::
                           self_or_implicit_actor);
            assert(entry.action.effect.duration_turns == 5);
        }
    }
    assert(hidden_mist_found);
    assert(hidden_mist_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(hidden_mist_session.select_unit(1) ==
           battle_transition::action_draft_opened);
    assert(hidden_mist_session.commit_action(
                   battle_facing::left,
                   no_ability) ==
           battle_transition::side_changed);
    assert(hidden_mist_session.select_unit(2) ==
           battle_transition::action_draft_opened);
    const int zabuza_chakra_before =
            hidden_mist_session.unit(2)->chakra;
    deterministic_rng hidden_mist_rng(8U);
    const action_result hidden_mist =
            battle_action_execution::resolve(
                    hidden_mist_session,
                    active_action_definitions[62],
                    zabuza->position,
                    hidden_mist_rng);
    assert(hidden_mist.success());
    assert(hidden_mist_session.unit(2)->chakra ==
           zabuza_chakra_before - 2);
    const std::uint8_t hidden_mist_slot =
            hidden_mist_session.unit(2)->statuses.find(0x0D);
    assert(hidden_mist_slot != no_status_slot);
    const status_record* hidden_mist_status =
            hidden_mist_session.unit(2)->statuses.active(
                    hidden_mist_slot);
    assert(hidden_mist_status);
    assert(hidden_mist_status->duration_ticks == 10);

    battle_scenario_load_policy clear_tools_policy;
    clear_tools_policy.character_equipped_tools_overridden[1] =
            true;
    battle_session<12> clear_tools_session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[10],
                   0,
                   clear_tools_policy,
                   clear_tools_session)
                   .error == battle_scenario_load_error::none);
    assert(
            clear_tools_session.unit(3)->equipped_tools ==
            (std::array<ninja_tool_id, 9>{}));

    battle_scenario_definition battle_11_passive_scenario;
    battle_11_passive_scenario.battle_id = 11;
    battle_11_passive_scenario.grid_width = 8;
    battle_11_passive_scenario.grid_height = 8;
    battle_scenario_unit_slot&
            battle_11_passive_unit =
                    battle_11_passive_scenario.
                            variants[0][0];
    battle_11_passive_unit.enabled = true;
    battle_11_passive_unit.selector = 12;
    battle_11_passive_unit.position = { 2, 2 };
    battle_11_passive_unit.runtime_config.
            embedded_character_config = true;
    battle_11_passive_unit.runtime_config.level = 30;
    battle_11_passive_unit.runtime_config.
            primary_action_slots[0] = { 5, 1, 0, 0 };
    battle_11_passive_unit.runtime_config.
            secondary_action_slots[0] = { 35, 2, 0, 0 };
    battle_session<1> battle_11_passive_session;
    assert(load_battle_scenario(
                   battle_11_passive_scenario,
                   0,
                   {},
                   battle_11_passive_session)
                   .error ==
           battle_scenario_load_error::none);
    assert(battle_11_passive_session.battle_id() == 11);
    assert(battle_11_passive_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(
            battle_11_passive_session.
                    side_start_event_count() == 1);
    const battle_side_start_passive_event*
            loaded_dual_boost =
                    battle_11_passive_session.
                            side_start_event_at(0);
    assert(loaded_dual_boost);
    assert(loaded_dual_boost->passive == 35);
    assert(loaded_dual_boost->status_code == 0x1E);
    assert(loaded_dual_boost->secondary_status_code == 0x22);
    assert(
            battle_11_passive_session.unit(1)->
                    statuses.active_count() == 2);

    battle_session<8> too_small;
    const battle_session<8> too_small_before = too_small;
    const battle_scenario_load_result capacity_error = load_battle_scenario(
            battle_scenario_definitions[15],
            0,
            escort_policy,
            too_small);
    assert(capacity_error.error == battle_scenario_load_error::capacity_exceeded);
    assert(too_small == too_small_before);

    const battle_scenario_load_result invalid_variant = load_battle_scenario(
            battle_scenario_definitions[15],
            3,
            escort_policy,
            escort_session);
    assert(invalid_variant.error == battle_scenario_load_error::invalid_variant);

    battle_scenario_load_policy invalid_tool_policy = escort_policy;
    invalid_tool_policy.character_equipped_tools[1][0] = 94;
    const battle_session<21> invalid_tool_before = escort_session;
    const battle_scenario_load_result invalid_tool =
            load_battle_scenario(
                    battle_scenario_definitions[15],
                    0,
                    invalid_tool_policy,
                    escort_session);
    assert(
            invalid_tool.error ==
            battle_scenario_load_error::invalid_ninja_tool);
    assert(invalid_tool.record_id == 0);
    assert(escort_session == invalid_tool_before);
}
