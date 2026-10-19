#include "konoha/battle_action_system.h"
#include "konoha/battle_conditions.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        battle_control control,
        grid_point position,
        int hp,
        std::uint8_t character,
        bool active = true)
{
    battle_unit_instance result = {
        id,
        side,
        control,
        position,
        battle_facing::down,
        hp,
        hp,
        10,
        10,
        3,
        active,
        {},
    };
    result.attack = 20;
    result.agility = 10;
    result.character_id = character;
    result.original_character_id = character;
    return result;
}

action_definition action(
        ability_id id,
        std::uint8_t effect_code,
        std::uint8_t potency,
        target_policy_kind target,
        range_shape range)
{
    action_definition result;
    result.id = id;
    result.effect = { effect_code, 0, potency, 1, 100, 0 };
    result.target = { target, 0 };
    result.range = range;
    return result;
}

battle_condition_variant encounter_conditions()
{
    battle_condition_variant result;
    result.win[0] = {
        battle_condition_type::no_valid_unit_for_side, 1, 0, 0,
    };
    result.lose[0] = {
        battle_condition_type::no_valid_character_for_side, 0, 42, 0,
    };
    return result;
}

}

int main()
{
    battle_session<7> victory_session;
    assert(victory_session.add_unit(unit(
            1, battle_side::player, battle_control::player, { 1, 2 }, 80, 1)));
    assert(victory_session.add_unit(unit(
            2, battle_side::player, battle_control::player, { 2, 2 }, 80, 2)));
    assert(victory_session.add_unit(unit(
            3, battle_side::player, battle_control::scripted, { 1, 3 }, 50, 42)));
    assert(victory_session.add_unit(unit(
            4, battle_side::player, battle_control::player, { 0, 0 }, 1, 0, false)));
    assert(victory_session.add_unit(unit(
            5, battle_side::player, battle_control::player, { 0, 0 }, 1, 0, false)));
    assert(victory_session.add_unit(unit(
            6, battle_side::enemy, battle_control::ai, { 3, 2 }, 30, 20)));
    assert(victory_session.add_unit(unit(
            7, battle_side::enemy, battle_control::ai, { 4, 2 }, 30, 21)));
    assert(victory_session.start_round() ==
           battle_transition::unit_selection_opened);

    assert(victory_session.select_unit(1) ==
           battle_transition::action_draft_opened);
    deterministic_rng summon_rng(1);
    const action_result summoned = battle_action_resolver::resolve_draft(
            victory_session,
            no_battle_unit,
            4,
            action(
                    69,
                    0x17,
                    0,
                    target_policy_kind::empty_tile,
                    { 2, 1 }),
            { 1, 1 },
            summon_rng);
    assert(summoned.success());
    assert(summoned.summon_count == 2);
    assert(victory_session.current_side() == battle_side::player);
    assert(victory_session.open_facing_selection() ==
           battle_transition::facing_selection_opened);
    assert(victory_session.select_facing(battle_facing::right) ==
           battle_transition::defense_selection_opened);
    assert(victory_session.complete_action(no_ability) ==
           battle_transition::unit_completed);

    assert(victory_session.select_unit(2) ==
           battle_transition::action_draft_opened);
    deterministic_rng area_rng(1);
    const action_result area = battle_action_resolver::resolve_area_draft(
            victory_session,
            action(
                    5,
                    0x01,
                    20,
                    target_policy_kind::opponent_unit,
                    { 2, 2 }),
            { 3, 2 },
            area_rng);
    assert(area.success());
    assert(area.target_count == 2);
    assert(! victory_session.unit(6)->active);
    assert(! victory_session.unit(7)->active);
    const battle_condition_result victory =
            battle_condition_interpreter::evaluate_session(
                    victory_session, encounter_conditions());
    assert(victory.outcome == battle_condition_outcome::win);

    battle_session<3> escort_session;
    assert(escort_session.add_unit(unit(
            10, battle_side::player, battle_control::player, { 1, 1 }, 80, 1)));
    assert(escort_session.add_unit(unit(
            11, battle_side::player, battle_control::scripted, { 2, 1 }, 15, 42)));
    assert(escort_session.add_unit(unit(
            12, battle_side::enemy, battle_control::ai, { 3, 1 }, 50, 20)));
    assert(escort_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(escort_session.select_unit(10) ==
           battle_transition::action_draft_opened);
    assert(escort_session.commit_action(battle_facing::right, no_ability) ==
           battle_transition::side_changed);
    assert(escort_session.select_unit(12) ==
           battle_transition::action_draft_opened);
    deterministic_rng escort_rng(1);
    const action_result escort_hit = battle_action_resolver::resolve_draft(
            escort_session,
            11,
            no_battle_unit,
            action(
                    5,
                    0x01,
                    10,
                    target_policy_kind::opponent_unit,
                    { 2, 1 }),
            { 2, 1 },
            escort_rng);
    assert(escort_hit.success());
    assert(! escort_session.unit(11)->active);
    const battle_condition_result loss =
            battle_condition_interpreter::evaluate_session(
                    escort_session, encounter_conditions());
    assert(loss.outcome == battle_condition_outcome::loss);
}
