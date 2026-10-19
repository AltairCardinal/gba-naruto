#include "konoha/battle_action_catalog.h"
#include "konoha/battle_action_progression.h"
#include "konoha/battle_results.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/generated_battle_passive_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <array>
#include <cassert>

using namespace konoha;

int main()
{
    character_progression_record naruto = {
        1, 1, 100, 0, true,
    };
    assert(initialize_character_action_progression(
            naruto, unit_definitions[1]));
    assert(naruto.action_states_initialized);
    assert(naruto.primary_action_levels[0] == 1);
    assert(naruto.primary_action_levels[1] == locked_action_level);
    assert(naruto.primary_action_levels[2] == locked_action_level);
    assert(naruto.primary_action_levels[3] == 1);
    assert(naruto.primary_action_levels[6] == locked_action_level);

    const level_settlement level_two =
            settle_character_progression(naruto, 150);
    assert(level_two.after.level == 2);
    assert(level_two.after.training_points == 1);
    assert(
            level_two.after.primary_action_levels[6] ==
            unlocked_action_level);
    assert(
            level_two.after.primary_action_levels[1] ==
            locked_action_level);
    assert(
            level_two.after.primary_action_levels[2] ==
            locked_action_level);

    character_progression_record trained = level_two.after;
    const action_training_result learned =
            train_primary_action(trained, 6);
    assert(learned.error == action_training_error::none);
    assert(learned.action_id == 8);
    assert(learned.before_level == unlocked_action_level);
    assert(learned.after_level == 1);
    assert(trained.training_points == 0);
    assert(trained.primary_action_levels[6] == 1);

    trained.training_points = 2;
    const action_training_result rank_two =
            train_primary_action(trained, 3);
    assert(rank_two.error == action_training_error::none);
    assert(rank_two.action_id == 5);
    assert(rank_two.before_level == 1);
    assert(rank_two.after_level == 2);
    assert(trained.training_points == 1);
    assert(
            train_primary_action(trained, 3).error ==
            action_training_error::none);
    assert(trained.primary_action_levels[3] == 3);
    trained.training_points = 1;
    assert(
            train_primary_action(trained, 3).error ==
            action_training_error::maximum_level);
    assert(trained.training_points == 1);

    character_progression_record locked = level_two.after;
    locked.training_points = 1;
    assert(
            train_primary_action(locked, 1).error ==
            action_training_error::locked);
    assert(locked.training_points == 1);
    assert(
            train_primary_action(locked, 8).error ==
            action_training_error::empty_slot);
    assert(
            train_primary_action(locked, 99).error ==
            action_training_error::invalid_slot);

    character_progression_record kiba = {
        4, 1, 0, 1, true,
    };
    assert(initialize_character_action_progression(
            kiba, unit_definitions[4]));
    assert(
            kiba.primary_action_levels[6] ==
            unlocked_action_level);
    const action_training_result learned_character_action =
            train_primary_action(kiba, 6);
    assert(learned_character_action.success());
    assert(learned_character_action.action_id == 23);

    struct no_growth_training_case
    {
        std::uint8_t character_id;
        std::size_t slot_index;
        ability_id action_id;
    };
    constexpr std::array<
            no_growth_training_case,
            3> no_growth_training_cases = {{
        { 2, 8, 15 },
        { 14, 5, 51 },
        { 16, 7, 56 },
    }};
    for(const no_growth_training_case& test_case :
            no_growth_training_cases)
    {
        character_progression_record record = {
            test_case.character_id,
            50,
            0,
            1,
            true,
        };
        const unit_definition& definition =
                unit_definitions[
                        test_case.character_id];
        assert(initialize_character_action_progression(
                record, definition));
        assert(
                definition.primary_slots[
                        test_case.slot_index]
                        .action ==
                test_case.action_id);
        assert(
                record.primary_action_levels[
                        test_case.slot_index] ==
                unlocked_action_level);

        const action_training_result learned_no_growth =
                train_primary_action(
                        record,
                        test_case.slot_index);
        assert(learned_no_growth.success());
        assert(learned_no_growth.action_id ==
               test_case.action_id);
        assert(learned_no_growth.before_level ==
               unlocked_action_level);
        assert(learned_no_growth.after_level == 1);
        assert(record.training_points == 0);

        battle_unit_instance battle_unit =
                instantiate_unit(
                        definition,
                        test_case.character_id,
                        battle_side::player,
                        battle_control::player,
                        { 1, 1 },
                        battle_facing::right,
                        record.level);
        assert(apply_character_action_progression(
                record, definition, battle_unit));
        const battle_action_catalog_result
                no_growth_catalog =
                        battle_action_catalog::build(
                                battle_unit);
        assert(no_growth_catalog.find(
                battle_action_source_kind::
                        active_action,
                test_case.action_id));
    }

    character_progression_record sasuke = {
        2, 50, 0, 1, true,
    };
    assert(initialize_character_action_progression(
            sasuke, unit_definitions[2]));
    assert(
            sasuke.primary_action_levels[10] ==
            locked_action_level);
    const character_progression_record sasuke_before_wrong_scenario =
            sasuke;
    assert(synchronize_scenario_action_unlocks(
            sasuke,
            unit_definitions[2],
            30,
            0));
    assert(sasuke == sasuke_before_wrong_scenario);
    assert(synchronize_scenario_action_unlocks(
            sasuke,
            unit_definitions[2],
            31,
            1));
    assert(sasuke == sasuke_before_wrong_scenario);
    assert(synchronize_scenario_action_unlocks(
            sasuke,
            unit_definitions[2],
            31,
            0));
    assert(
            sasuke.primary_action_levels[10] ==
            unlocked_action_level);
    const action_training_result learned_lion_barrage =
            train_primary_action(sasuke, 10);
    assert(learned_lion_barrage.success());
    assert(learned_lion_barrage.action_id == 19);
    assert(learned_lion_barrage.before_level ==
           unlocked_action_level);
    assert(learned_lion_barrage.after_level == 1);
    assert(sasuke.training_points == 0);

    character_progression_record sakura = {
        3, 5, 0, 1, true,
    };
    assert(initialize_character_action_progression(
            sakura, unit_definitions[3]));
    assert(sakura.secondary_action_levels[13] ==
           unlocked_action_level);
    const character_progression_record sakura_before_invalid =
            sakura;
    assert(
            train_secondary_passive(sakura, 99).error ==
            action_training_error::invalid_slot);
    assert(sakura == sakura_before_invalid);

    const action_training_result learned_passive =
            train_secondary_passive(sakura, 13);
    assert(learned_passive.success());
    assert(learned_passive.trained_passive_id == 15);
    assert(learned_passive.before_level ==
           unlocked_action_level);
    assert(learned_passive.after_level == 1);
    assert(sakura.training_points == 0);
    assert(sakura.secondary_action_levels[13] == 1);

    const character_progression_record sakura_before_no_points =
            sakura;
    assert(
            train_secondary_passive(sakura, 13).error ==
            action_training_error::no_training_points);
    assert(sakura == sakura_before_no_points);

    sakura.training_points = 2;
    assert(train_secondary_passive(sakura, 13).success());
    assert(train_secondary_passive(sakura, 13).success());
    assert(sakura.secondary_action_levels[13] ==
           maximum_action_level);
    sakura.training_points = 1;
    const character_progression_record sakura_before_maximum =
            sakura;
    assert(
            train_secondary_passive(sakura, 13).error ==
            action_training_error::maximum_level);
    assert(sakura == sakura_before_maximum);

    character_progression_record locked_passive = {
        3, 4, 0, 1, true,
    };
    assert(initialize_character_action_progression(
            locked_passive, unit_definitions[3]));
    assert(locked_passive.secondary_action_levels[13] ==
           locked_action_level);
    const character_progression_record locked_passive_before =
            locked_passive;
    assert(
            train_secondary_passive(
                    locked_passive, 13).error ==
            action_training_error::locked);
    assert(locked_passive == locked_passive_before);

    sakura.secondary_action_levels[13] = 1;
    battle_unit_instance battle_sakura = instantiate_unit(
            unit_definitions[3],
            4,
            battle_side::player,
            battle_control::player,
            { 2, 2 },
            battle_facing::right,
            sakura.level);
    assert(apply_character_action_progression(
            sakura, unit_definitions[3], battle_sakura));
    const passive_query_result restoration =
            battle_sakura.passives.query(
                    hp_restoration_passive_target,
                    passive_definitions);
    assert(restoration.found);
    assert(restoration.slot_index == 13);
    assert(restoration.id == 15);
    assert(restoration.stored_level == 1);
    assert(restoration.value_a == 30);

    character_progression_record trained_max_hp = {
        1, 9, 0, 0, true,
    };
    assert(initialize_character_action_progression(
            trained_max_hp, unit_definitions[1]));
    assert(
            trained_max_hp.secondary_action_levels[0] ==
            unlocked_action_level);
    trained_max_hp.secondary_action_levels[0] = 1;
    std::array<character_progression_record, 1>
            trained_max_hp_roster = {{ trained_max_hp }};
    battle_scenario_load_policy trained_max_hp_policy;
    battle_session<2> trained_max_hp_session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[41],
                   0,
                   trained_max_hp_policy,
                   trained_max_hp_session,
                   trained_max_hp_roster.data(),
                   trained_max_hp_roster.size())
                   .error == battle_scenario_load_error::none);
    const character_stat_values untrained_level_nine =
            character_stats_at_level(1, 9);
    assert(
            trained_max_hp_session.unit(1)->max_hp ==
            untrained_level_nine.max_hp + 30);
    assert(
            trained_max_hp_session.unit(1)->hp ==
            trained_max_hp_session.unit(1)->max_hp);
    assert(
            trained_max_hp_session.unit(1)->base_max_hp ==
            trained_max_hp_session.unit(1)->max_hp);

    battle_unit_instance battle_kiba = instantiate_unit(
            unit_definitions[4],
            3,
            battle_side::player,
            battle_control::player,
            { 1, 1 },
            battle_facing::right,
            1);
    assert(apply_character_action_progression(
            kiba, unit_definitions[4], battle_kiba));
    const battle_action_catalog_result kiba_catalog =
            battle_action_catalog::build(battle_kiba);
    assert(kiba_catalog.find(
            battle_action_source_kind::active_action,
            23));

    std::array<character_progression_record, 3> roster = {{
        trained,
        {},
        {},
    }};
    battle_scenario_load_policy policy;
    policy.character_levels[1] =
            static_cast<std::uint8_t>(trained.level);
    battle_session<2> session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[41],
                   0,
                   policy,
                   session,
                   roster.data(),
                   roster.size())
                   .error == battle_scenario_load_error::none);
    const battle_unit_instance* battle_naruto = session.unit(1);
    assert(battle_naruto);
    const character_stat_values trained_stats =
            character_stats_at_level(
                    trained.character_id,
                    trained.level);
    assert(battle_naruto->level == trained.level);
    assert(battle_naruto->max_hp == trained_stats.max_hp);
    assert(battle_naruto->hp == trained_stats.max_hp);
    assert(battle_naruto->attack == trained_stats.attack);
    assert(battle_naruto->base_attack == trained_stats.attack);
    assert(battle_naruto->defense == trained_stats.defense);
    assert(battle_naruto->base_defense == trained_stats.defense);
    assert(battle_naruto->agility == trained_stats.agility);
    assert(battle_naruto->base_agility == trained_stats.agility);
    assert(
            battle_naruto->ninja_tool_capacity ==
            trained_stats.ninja_tool_capacity);
    assert(battle_naruto->primary_action_levels[3] == 3);
    assert(battle_naruto->primary_action_levels[6] == 1);

    const battle_action_catalog_result catalog =
            battle_action_catalog::build(*battle_naruto);
    assert(catalog.error == battle_action_catalog_error::none);
    assert(catalog.count == 4);
    const battle_action_catalog_entry* combo =
            catalog.find(
                    battle_action_source_kind::active_action,
                    5);
    assert(combo);
    assert(combo->action_level == 3);
    assert(combo->action.effect.potency == 20);
    const battle_unit_instance* loaded_enemy =
            session.unit(2);
    assert(loaded_enemy);
    battle_unit_instance adjacent_enemy =
            *loaded_enemy;
    adjacent_enemy.position = {
        battle_naruto->position.x + 1,
        battle_naruto->position.y,
    };
    adjacent_enemy.defense = 0;
    adjacent_enemy.base_defense = 0;
    battle_unit_instance normalized_naruto =
            *battle_naruto;
    normalized_naruto.attack = 10;
    normalized_naruto.base_attack = 10;
    const action_preview rank_one_preview =
            battle_action_resolver::preview_units(
                    normalized_naruto,
                    &adjacent_enemy,
                    nullptr,
                    true,
                    action_definition_at_level(
                            active_action_definitions[5],
                            1),
                    adjacent_enemy.position);
    const action_preview rank_three_preview =
            battle_action_resolver::preview_units(
                    normalized_naruto,
                    &adjacent_enemy,
                    nullptr,
                    true,
                    combo->action,
                    adjacent_enemy.position);
    assert(rank_one_preview.legal());
    assert(rank_three_preview.legal());
    assert(
            rank_three_preview.damage_per_hit ==
            rank_one_preview.damage_per_hit + 10);
    const battle_action_catalog_entry* barrage =
            catalog.find(
                    battle_action_source_kind::active_action,
                    8);
    assert(barrage);
    assert(barrage->action_level == 1);
}
