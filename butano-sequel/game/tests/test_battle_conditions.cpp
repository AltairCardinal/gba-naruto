#include "konoha/battle_conditions.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        std::uint8_t character,
        int hp)
{
    battle_unit_instance result = {
        id,
        side,
        battle_control::player,
        { 0, 0 },
        battle_facing::down,
        hp,
        hp,
        0,
        0,
        3,
        hp > 0,
        {},
    };
    result.character_id = character;
    return result;
}

battle_condition_predicate condition(
        battle_condition_type type,
        std::uint8_t arg0 = 0,
        std::uint8_t arg1 = 0)
{
    return { type, arg0, arg1, 0 };
}

}

int main()
{
    battle_session<6> session;
    assert(session.add_unit(unit(11, battle_side::player, 4, 50)));
    assert(session.add_unit(unit(12, battle_side::enemy, 20, 35)));
    const std::uint8_t session_object = session.objects().allocate({
        2, 7, 8, 0, 0, { 9 }, 0, 0, 0,
    });
    assert(session_object == 1);
    battle_condition_context<6> session_context(session);
    assert(session_context.unit(11));
    assert(session_context.unit(12));
    assert(session_context.objects().record(session_object)->type == 2);
    assert(session.resolve_behavior_9(session_object, battle_side::player));
    battle_condition_context<6> resolved_context(session);
    assert(resolved_context.objects().record(session_object)->type == 0);
    assert(resolved_context.resolved_object_count(battle_side::player) == 1);

    battle_session<2> round_session;
    assert(round_session.add_unit(unit(
            21, battle_side::player, 4, 50)));
    assert(round_session.add_unit(unit(
            22, battle_side::enemy, 20, 35)));
    assert(round_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(round_session.select_unit(21) ==
           battle_transition::action_draft_opened);
    assert(round_session.commit_action(battle_facing::up, no_ability) ==
           battle_transition::side_changed);
    assert(! battle_condition_context<2>(round_session).full_round_boundary());
    assert(round_session.select_unit(22) ==
           battle_transition::action_draft_opened);
    assert(round_session.commit_action(battle_facing::down, no_ability) ==
           battle_transition::round_advanced);
    battle_condition_context<2> round_context(round_session);
    assert(round_context.full_round_boundary());
    assert(round_context.round_index() == 2);
    battle_condition_variant session_round_limit;
    session_round_limit.header[0] = 2;
    session_round_limit.win[0] = condition(
            battle_condition_type::round_limit_reached);
    assert(battle_condition_interpreter::evaluate(
                   round_context, session_round_limit).outcome ==
           battle_condition_outcome::win);

    battle_condition_context<6> context;
    assert(context.add_unit(unit(1, battle_side::player, 1, 40)));
    assert(context.add_unit(unit(2, battle_side::player, 2, 20)));
    assert(context.add_unit(unit(3, battle_side::enemy, 30, 10)));

    battle_condition_variant enemy_absent;
    enemy_absent.win[0] = condition(
            battle_condition_type::no_valid_unit_for_side, 1);
    battle_condition_result result =
            battle_condition_interpreter::evaluate(context, enemy_absent);
    assert(result.error == battle_condition_error::none);
    assert(result.outcome == battle_condition_outcome::none);

    context.mutable_unit(3)->active = false;
    result = battle_condition_interpreter::evaluate(context, enemy_absent);
    assert(result.outcome == battle_condition_outcome::win);
    assert(result.first_win_slot == 0);
    assert(result.presentation_id == 1);
    assert(result.ends_battle);

    battle_condition_variant lower_loss_slot;
    lower_loss_slot.win[0] = condition(
            battle_condition_type::no_valid_unit_for_side, 0);
    lower_loss_slot.win[1] = condition(
            battle_condition_type::no_valid_unit_for_side, 0);
    lower_loss_slot.win[2] = condition(
            battle_condition_type::no_valid_character_for_side, 1, 31);
    lower_loss_slot.lose[0] = condition(
            battle_condition_type::no_valid_character_for_side, 0, 99);
    result = battle_condition_interpreter::evaluate(context, lower_loss_slot);
    assert(result.outcome == battle_condition_outcome::loss);
    assert(result.first_win_slot == 2);
    assert(result.first_loss_slot == 0);
    assert(result.presentation_id == 2);

    battle_condition_variant same_slot;
    same_slot.win[0] = condition(
            battle_condition_type::no_valid_character_for_side, 1, 31);
    same_slot.lose[0] = condition(
            battle_condition_type::no_valid_character_for_side, 0, 99);
    result = battle_condition_interpreter::evaluate(context, same_slot);
    assert(result.outcome == battle_condition_outcome::equal_slot_result);
    assert(result.first_win_slot == 0);
    assert(result.first_loss_slot == 0);
    assert(result.presentation_id == 3);
    assert(result.ends_battle);

    context.set_round_limit(3);
    context.set_round_index(3);
    battle_condition_variant round_limit;
    round_limit.win[0] = condition(
            battle_condition_type::round_limit_reached);
    context.set_full_round_boundary(false);
    assert(battle_condition_interpreter::evaluate(context, round_limit).outcome ==
            battle_condition_outcome::none);
    context.set_full_round_boundary(true);
    assert(battle_condition_interpreter::evaluate(context, round_limit).outcome ==
            battle_condition_outcome::win);
    context.set_round_limit(0);
    assert(battle_condition_interpreter::evaluate(context, round_limit).outcome ==
            battle_condition_outcome::none);

    const std::uint8_t object_slot = context.objects().allocate({
        3, 4, 5, 0, 0, { 9 }, 0, 0, 0,
    });
    assert(object_slot == 1);
    battle_condition_variant object_inactive;
    object_inactive.win[0] = condition(
            battle_condition_type::object_slot_inactive, 0);
    assert(battle_condition_interpreter::evaluate(context, object_inactive).outcome ==
            battle_condition_outcome::none);
    assert(context.resolve_behavior_9(object_slot, battle_side::player));
    assert(context.objects().record(object_slot)->type == 0);
    assert(context.resolved_object_count(battle_side::player) == 1);
    assert(battle_condition_interpreter::evaluate(context, object_inactive).outcome ==
            battle_condition_outcome::win);

    context.set_round_limit(4);
    context.set_round_index(4);
    context.set_full_round_boundary(true);
    battle_condition_variant hp_sum;
    hp_sum.win[0] = condition(
            battle_condition_type::side_hp_sum_greater, 0);
    assert(battle_condition_interpreter::evaluate(context, hp_sum).outcome ==
            battle_condition_outcome::win);

    battle_condition_variant unit_count;
    unit_count.win[0] = condition(
            battle_condition_type::side_unit_count_greater, 0);
    assert(battle_condition_interpreter::evaluate(context, unit_count).outcome ==
            battle_condition_outcome::win);

    const std::uint8_t enemy_object = context.objects().allocate({
        4, 6, 7, 0, 0, { 9 }, 0, 0, 0,
    });
    assert(context.resolve_behavior_9(enemy_object, battle_side::enemy));
    assert(context.resolved_object_count(battle_side::enemy) == 1);
    const std::uint8_t player_object = context.objects().allocate({
        4, 6, 7, 0, 0, { 9 }, 0, 0, 0,
    });
    assert(context.resolve_behavior_9(player_object, battle_side::player));
    assert(context.resolved_object_count(battle_side::player) == 2);
    battle_condition_variant object_count;
    object_count.win[0] = condition(
            battle_condition_type::side_resolved_object_count_greater, 0);
    assert(battle_condition_interpreter::evaluate(context, object_count).outcome ==
            battle_condition_outcome::win);

    battle_condition_variant unsupported;
    unsupported.win[0] = condition(
            battle_condition_type::unused_4);
    result = battle_condition_interpreter::evaluate(context, unsupported);
    assert(result.error == battle_condition_error::unsupported_type);
    assert(result.outcome == battle_condition_outcome::none);
}
