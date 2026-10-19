#include "konoha/battle_conditions.h"
#include "konoha/battle_mission_rules.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_session<2> prepared_session(
        grid_point player_position,
        battle_facing facing,
        bool enemy_active)
{
    battle_session<2> session;
    battle_unit_instance player;
    player.id = 1;
    player.side = battle_side::player;
    player.control = battle_control::player;
    player.position = player_position;
    player.facing = battle_facing::up;
    player.hp = 100;
    player.max_hp = 100;
    player.chakra = 5;
    player.max_chakra = 5;
    player.move_range = 6;
    player.active = true;
    battle_unit_instance enemy;
    enemy.id = 2;
    enemy.side = battle_side::enemy;
    enemy.control = battle_control::ai;
    enemy.position = { 4, 6 };
    enemy.facing = battle_facing::down;
    enemy.hp = 100;
    enemy.max_hp = 100;
    enemy.chakra = 5;
    enemy.max_chakra = 5;
    enemy.move_range = 6;
    enemy.active = enemy_active;
    assert(session.add_unit(player));
    assert(session.add_unit(enemy));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);
    assert(session.open_facing_selection() ==
           battle_transition::facing_selection_opened);
    assert(session.select_facing(facing) ==
           battle_transition::defense_selection_opened);
    return session;
}

battle_condition_variant object_condition()
{
    battle_condition_variant result;
    result.win[0] = {
        battle_condition_type::object_slot_inactive,
        0,
    };
    return result;
}

}

int main()
{
    const battle_mission_objective objective =
            battle_mission_rules_for(44, 0).objective;

    battle_session<2> blocked =
            prepared_session(
                    { 4, 3 },
                    battle_facing::down,
                    true);
    assert(battle_mission_objective_system::initialize(
                   blocked, objective) ==
           battle_mission_objective_error::none);
    assert(battle_condition_interpreter::evaluate_session(
                   blocked, object_condition())
                   .outcome ==
           battle_condition_outcome::none);
    assert(battle_mission_objective_system::
                   resolve_player_action_boundary(
                           blocked, objective) ==
           battle_mission_objective_resolution::
                   requirements_not_met);
    assert(blocked.objects().record(1)->type == 3);

    battle_session<2> wrong_position =
            prepared_session(
                    { 3, 4 },
                    battle_facing::down,
                    false);
    assert(battle_mission_objective_system::initialize(
                   wrong_position, objective) ==
           battle_mission_objective_error::none);
    assert(battle_mission_objective_system::
                   resolve_player_action_boundary(
                           wrong_position, objective) ==
           battle_mission_objective_resolution::
                   requirements_not_met);
    assert(wrong_position.objects().record(1)->type == 3);

    battle_session<2> object_tile =
            prepared_session(
                    { 4, 4 },
                    battle_facing::down,
                    false);
    assert(battle_mission_objective_system::initialize(
                   object_tile, objective) ==
           battle_mission_objective_error::none);
    assert(battle_mission_objective_system::
                   resolve_player_action_boundary(
                           object_tile, objective) ==
           battle_mission_objective_resolution::
                   requirements_not_met);
    assert(object_tile.objects().record(1)->type == 3);

    battle_session<2> wrong_facing =
            prepared_session(
                    { 4, 3 },
                    battle_facing::left,
                    false);
    assert(battle_mission_objective_system::initialize(
                   wrong_facing, objective) ==
           battle_mission_objective_error::none);
    assert(battle_mission_objective_system::
                   resolve_player_action_boundary(
                           wrong_facing, objective) ==
           battle_mission_objective_resolution::
                   requirements_not_met);
    assert(wrong_facing.objects().record(1)->type == 3);

    battle_session<2> resolved =
            prepared_session(
                    { 4, 3 },
                    battle_facing::down,
                    false);
    assert(battle_mission_objective_system::initialize(
                   resolved, objective) ==
           battle_mission_objective_error::none);
    assert(battle_mission_objective_system::
                   resolve_player_action_boundary(
                           resolved, objective) ==
           battle_mission_objective_resolution::resolved);
    assert(resolved.objects().record(1)->type == 0);
    assert(battle_condition_interpreter::evaluate_session(
                   resolved, object_condition())
                   .outcome ==
           battle_condition_outcome::win);

    assert(! resolved.objects().place(0, objective.object));
    assert(! resolved.objects().place(1, {}));
}
