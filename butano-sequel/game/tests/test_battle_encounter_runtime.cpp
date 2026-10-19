#include "konoha/battle_encounter_runtime.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_encounter_runtime<2, 9, 22> scenario_41;
    const battle_encounter_load_result scenario_41_loaded =
            scenario_41.load(
                    battle_scenario_definitions[41],
                    battle_map_definitions[41],
                    battle_map_cells,
                    0,
                    {},
                    battle_condition_variants[9][0],
                    0x41U);
    assert(scenario_41_loaded.success());
    assert(scenario_41.loaded());
    assert(scenario_41.session().unit_count() == 2);
    assert(scenario_41.terrain().cost({ 0, 0 }) == 0);
    assert(scenario_41.terrain().cost({ 4, 17 }) == 1);
    assert(scenario_41.start() ==
           battle_transition::unit_selection_opened);

    grid_map<9, 22> scenario_41_movement;
    assert(scenario_41.movement_map(scenario_41_movement) ==
           battle_map_load_error::none);
    assert(scenario_41_movement.occupied(
            scenario_41.session().unit(1)->position));
    assert(scenario_41_movement.occupied(
            scenario_41.session().unit(2)->position));

    battle_scenario_load_policy fixed_pool;
    fixed_pool.preserve_empty_unit_slots = true;
    battle_encounter_runtime<12, 9, 22> scenario_43;
    const battle_encounter_load_result scenario_43_loaded =
            scenario_43.load(
                    battle_scenario_definitions[43],
                    battle_map_definitions[43],
                    battle_map_cells,
                    0,
                    fixed_pool,
                    battle_condition_variants[43][0],
                    0x43U);
    assert(scenario_43_loaded.success());
    assert(scenario_43.session().unit_count() == 12);
    assert(scenario_43.session().unit(1)->character_id == 1);
    assert(scenario_43.session().unit(1)->position ==
           grid_point({ 4, 17 }));
    assert(scenario_43.session().unit(2)->character_id == 35);
    assert(scenario_43.session().unit(2)->position ==
           grid_point({ 2, 11 }));
    assert(! scenario_43.session().unit(5)->active);
    assert(scenario_43.start() ==
           battle_transition::unit_selection_opened);

    assert(scenario_43.begin_player_unit(1).success());
    assert(scenario_43.open_move_selection().success());
    assert(scenario_43.preview_move({ 4, 17 }).success());
    assert(scenario_43.confirm_move_selection().success());
    assert(scenario_43.select_command(
                   battle_command_type::ability)
                   .success());

    battle_action_access_policy clone_only;
    clone_only.restrict_active_actions = true;
    clone_only.allowed_active_actions[0] = 7;
    clone_only.allowed_active_action_count = 1;
    clone_only.allow_ninja_tools = false;
    assert(scenario_43.open_action_selection(
                   clone_only, 7)
                   .success());
    assert(scenario_43.confirm_action_selection().success());

    const battle_session<12> before_clone_preview =
            scenario_43.session();
    assert(scenario_43.preview_target({ 4, 16 }).success());
    assert(scenario_43.session() == before_clone_preview);
    const battle_player_action_flow_result cloned =
            scenario_43.confirm_target({ 4, 16 });
    assert(cloned.success());
    assert(scenario_43.session().unit(1)->chakra == 2);
    assert(scenario_43.session().unit(5)->active);
    assert(scenario_43.session().unit(5)->summoner == 1);
    assert(scenario_43.session().unit(5)->position ==
           grid_point({ 4, 16 }));
    assert(scenario_43.select_facing(
                   battle_facing::up)
                   .success());
    assert(scenario_43.complete_without_defense().success());
    assert(scenario_43.session().current_side() ==
           battle_side::enemy);

    for(battle_unit_id enemy_id = 2;
            enemy_id <= 4; ++enemy_id)
    {
        assert(scenario_43.first_available_unit(
                       battle_side::enemy) ==
               enemy_id);
        const battle_ai_turn_flow_result turn =
                scenario_43.run_ai(
                        enemy_id,
                        {});
        assert(turn.success());
        if(enemy_id < 4)
        {
            assert(scenario_43.session().unit(enemy_id)->
                    ledger.completed);
        }
        else
        {
            assert(scenario_43.session().round_index() == 2);
            assert(! scenario_43.session().unit(enemy_id)->
                    ledger.completed);
        }
    }
    assert(scenario_43.session().current_side() ==
           battle_side::player);
    assert(scenario_43.session().round_index() == 2);
    assert(scenario_43.first_available_unit(
                   battle_side::player) == 1);
    assert(! scenario_43.session().unit(5)->
            ledger.completed);

    battle_encounter_runtime<11, 9, 22> too_small;
    const battle_encounter_load_result rejected =
            too_small.load(
                    battle_scenario_definitions[43],
                    battle_map_definitions[43],
                    battle_map_cells,
                    0,
                    fixed_pool,
                    battle_condition_variants[43][0],
                    0x43U);
    assert(rejected.error ==
           battle_encounter_load_error::
                   scenario_load_failed);
    assert(rejected.scenario_error ==
           battle_scenario_load_error::capacity_exceeded);
    assert(! too_small.loaded());
    assert(too_small.session().unit_count() == 0);
}
