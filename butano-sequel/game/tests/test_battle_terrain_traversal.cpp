#include "konoha/battle_ai.h"
#include "konoha/battle_player_action_flow.h"
#include "konoha/battle_terrain_traversal.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        battle_control control,
        grid_point position,
        int move_range)
{
    battle_unit_instance result = {
        id,
        side,
        control,
        position,
        battle_facing::right,
        30,
        30,
        10,
        10,
        move_range,
        true,
        {},
    };
    result.attack = 20;
    result.primary_action_ids[0] = 5;
    result.primary_action_levels[0] = 1;
    return result;
}

action_definition strike()
{
    action_definition result;
    result.id = 5;
    result.effect = { 0x01, 0, 10, 1, 100, 0 };
    result.target = {
        target_policy_kind::opponent_unit,
        0,
    };
    result.range = { 1, 1 };
    return result;
}

}

int main()
{
    grid_map<5, 1> class_one_map;
    assert(class_one_map.set_terrain_class(
            { 1, 0 }, grid_terrain_class_one));
    assert(class_one_map.set_terrain_class(
            { 2, 0 }, grid_terrain_class_one));
    assert(class_one_map.set_terrain_class(
            { 3, 0 }, grid_terrain_class_one));

    const reachable_cost_result<5, 1> without_training =
            compute_reachable_costs(
                    class_one_map,
                    { 0, 0 },
                    4,
                    {});
    assert(without_training.valid);
    assert(without_training.cost({ 0, 0 }) == 0);
    assert(without_training.cost({ 1, 0 }) == -1);

    grid_terrain_traversal_limits two_class_one;
    two_class_one.class_one = 2;
    const reachable_cost_result<5, 1> class_one_reachable =
            compute_reachable_costs(
                    class_one_map,
                    { 0, 0 },
                    4,
                    two_class_one);
    assert(class_one_reachable.cost({ 1, 0 }) == 1);
    assert(class_one_reachable.cost({ 2, 0 }) == 2);
    assert(class_one_reachable.cost({ 3, 0 }) == -1);
    assert((find_path<5, 1, 5>(
                   class_one_map,
                   { 0, 0 },
                   { 2, 0 },
                   4,
                   two_class_one)
                   .found));
    assert((! find_path<5, 1, 5>(
                    class_one_map,
                    { 0, 0 },
                    { 3, 0 },
                    4,
                    two_class_one)
                    .found));

    grid_map<3, 1> class_three_map;
    assert(class_three_map.set_terrain_class(
            { 0, 0 }, grid_terrain_class_three));
    assert(class_three_map.set_terrain_class(
            { 1, 0 }, grid_terrain_class_three));
    assert(class_three_map.set_terrain_class(
            { 2, 0 }, grid_terrain_class_three));
    grid_terrain_traversal_limits two_class_three;
    two_class_three.class_three = 2;
    assert(compute_reachable_costs(
                   class_three_map,
                   { 0, 0 },
                   2,
                   two_class_three)
                   .cost({ 1, 0 }) == 1);
    assert(compute_reachable_costs(
                   class_three_map,
                   { 0, 0 },
                   2,
                   two_class_three)
                   .cost({ 2, 0 }) == -1);

    grid_map<3, 1> class_seven_map;
    assert(class_seven_map.set_terrain_class(
            { 1, 0 }, grid_terrain_class_seven));
    assert(class_seven_map.set_terrain_class(
            { 2, 0 }, grid_terrain_class_seven));
    grid_terrain_traversal_limits one_class_seven;
    one_class_seven.class_seven = 1;
    assert(compute_reachable_costs(
                   class_seven_map,
                   { 0, 0 },
                   2,
                   one_class_seven)
                   .cost({ 1, 0 }) == 1);
    assert(compute_reachable_costs(
                   class_seven_map,
                   { 0, 0 },
                   2,
                   one_class_seven)
                   .cost({ 2, 0 }) == -1);

    battle_passive_state passives;
    assert(passives.set_slot(0, 21, 1));
    assert(passives.set_slot(1, 22, 2));
    assert(passives.set_slot(2, 23, 3));
    const grid_terrain_traversal_limits passive_limits =
            battle_terrain_traversal_limits(passives);
    assert(passive_limits.class_one == 2);
    assert(passive_limits.class_seven == 3);
    assert(passive_limits.class_three == 4);

    battle_unit_instance player = unit(
            1,
            battle_side::player,
            battle_control::player,
            { 0, 0 },
            4);
    player.passives = {};
    assert(player.passives.set_slot(0, 21, 1));
    const battle_unit_instance enemy = unit(
            2,
            battle_side::enemy,
            battle_control::ai,
            { 4, 0 },
            0);
    battle_session<2> player_session;
    assert(player_session.add_unit(player));
    assert(player_session.add_unit(enemy));
    assert(player_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(player_session.select_unit(1) ==
           battle_transition::action_draft_opened);
    battle_player_action_flow<2> player_flow;
    assert(player_flow.begin(player_session).success());
    assert(player_flow.open_move_selection(
                   player_session)
                   .success());
    grid_map<5, 1> player_map = class_one_map;
    assert(player_map.set_occupied({ 0, 0 }, true));
    assert(player_map.set_occupied({ 4, 0 }, true));
    assert(player_flow.preview_move(
                   player_session,
                   player_map,
                   { 2, 0 })
                   .success());
    assert(player_flow.preview_move(
                   player_session,
                   player_map,
                   { 3, 0 })
                   .error ==
           battle_player_action_flow_error::move_rejected);

    battle_unit_instance stationary_player = unit(
            5,
            battle_side::player,
            battle_control::player,
            { 1, 0 },
            4);
    stationary_player.passives = {};
    battle_unit_instance stationary_enemy = enemy;
    stationary_enemy.id = 6;
    battle_session<2> stationary_session;
    assert(stationary_session.add_unit(stationary_player));
    assert(stationary_session.add_unit(stationary_enemy));
    assert(stationary_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(stationary_session.select_unit(5) ==
           battle_transition::action_draft_opened);
    battle_player_action_flow<2> stationary_flow;
    assert(stationary_flow.begin(stationary_session).success());
    assert(stationary_flow.open_move_selection(
                   stationary_session)
                   .success());
    grid_map<5, 1> stationary_map = class_one_map;
    assert(stationary_map.set_occupied({ 1, 0 }, true));
    assert(stationary_map.set_occupied({ 4, 0 }, true));
    assert(stationary_flow.preview_move(
                   stationary_session,
                   stationary_map,
                   { 1, 0 })
                   .success());
    assert(stationary_flow.preview_move(
                   stationary_session,
                   stationary_map,
                   { 0, 0 })
                   .error ==
           battle_player_action_flow_error::move_rejected);

    battle_unit_instance ai_actor = unit(
            3,
            battle_side::enemy,
            battle_control::ai,
            { 0, 0 },
            3);
    ai_actor.passives = {};
    assert(ai_actor.passives.set_slot(0, 21, 1));
    const battle_unit_instance ai_target = unit(
            4,
            battle_side::player,
            battle_control::player,
            { 4, 0 },
            0);
    std::array ai_units = { ai_actor, ai_target };
    grid_map<5, 1> ai_map = class_one_map;
    assert(ai_map.set_terrain_class({ 3, 0 }, 0));
    assert(ai_map.set_occupied({ 0, 0 }, true));
    assert(ai_map.set_occupied({ 4, 0 }, true));
    deterministic_rng rng(17);
    const action_definition ai_strike = strike();
    const ai_plan trained_plan = battle_ai::plan(
            ai_map,
            ai_units[0],
            ai_units,
            &ai_strike,
            ai_objective{ false, {}, 4, no_battle_unit },
            rng);
    assert(trained_plan.error == ai_error::none);
    assert(trained_plan.action == ai_action::move);
    assert(trained_plan.destination == grid_point({ 2, 0 }));

    ai_units[0].passives = {};
    deterministic_rng untrained_rng(17);
    const ai_plan untrained_plan = battle_ai::plan(
            ai_map,
            ai_units[0],
            ai_units,
            &ai_strike,
            ai_objective{ false, {}, 4, no_battle_unit },
            untrained_rng);
    assert(untrained_plan.error == ai_error::none);
    assert(untrained_plan.action != ai_action::ability);
}
