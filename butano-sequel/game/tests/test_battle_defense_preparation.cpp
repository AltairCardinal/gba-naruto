#include "konoha/battle_defense_preparation.h"
#include "konoha/battle_turn_flow.h"
#include "konoha/generated_battle_action_content.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        grid_point position,
        int hp,
        int chakra)
{
    battle_unit_instance result = {
        id,
        side,
        side == battle_side::player ?
                battle_control::player : battle_control::ai,
        position,
        battle_facing::down,
        hp,
        hp,
        chakra,
        chakra,
        3,
        true,
        {},
    };
    result.attack = 20;
    result.agility = 10;
    return result;
}

action_definition incoming_attack(
        int hit_count = 3, int success_rate = 100)
{
    action_definition result;
    result.id = 5;
    result.effect = {
        0x01,
        0,
        10,
        static_cast<std::uint8_t>(hit_count),
        static_cast<std::uint8_t>(success_rate),
        0,
    };
    result.target = { target_policy_kind::opponent_unit, 0 };
    result.range = { 1, 1 };
    return result;
}

void open_defense(battle_session<2>& session, battle_unit_id id)
{
    assert(session.select_unit(id) ==
           battle_transition::action_draft_opened);
    assert(session.open_facing_selection() ==
           battle_transition::facing_selection_opened);
    assert(session.select_facing(battle_facing::right) ==
           battle_transition::defense_selection_opened);
}

void finish_effects_without_defense(battle_session<2>& session)
{
    battle_condition_variant no_conditions;
    assert(battle_turn_flow::after_effects(
                   session, no_conditions).error ==
           battle_turn_flow_error::none);
    assert(session.select_facing(battle_facing::right) ==
           battle_transition::defense_selection_opened);
    assert(battle_turn_flow::complete_defense(
                   session, no_ability, no_conditions).error ==
           battle_turn_flow_error::none);
}

}

int main()
{
    battle_session<2> session;
    assert(session.add_unit(unit(
            1, battle_side::player, { 1, 1 }, 80, 5)));
    assert(session.add_unit(unit(
            2, battle_side::enemy, { 2, 1 }, 80, 5)));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    open_defense(session, 1);

    const action_definition sharingan = active_action_definitions[15];
    const battle_session<2> before_preview = session;
    const defense_preparation_preview preview =
            battle_defense_preparation::preview(session, sharingan);
    assert(preview.error == defense_preparation_error::none);
    assert(preview.kind == defense_action_kind::active_action);
    assert(preview.action_id == 15);
    assert(preview.chakra_cost == 2);
    assert(session == before_preview);

    action_definition forged_tool_sharingan = sharingan;
    forged_tool_sharingan.cost = {
        action_cost_kind::battle_local_ninja_tool_slot,
        0,
        0,
    };
    const defense_preparation_preview wrong_source_kind =
            battle_defense_preparation::preview(
                    session, forged_tool_sharingan);
    assert(wrong_source_kind.error ==
           defense_preparation_error::unsupported_category);
    assert(session == before_preview);

    const defense_preparation_preview offensive =
            battle_defense_preparation::preview(
                    session, active_action_definitions[12]);
    assert(offensive.error ==
           defense_preparation_error::unsupported_category);
    assert(session == before_preview);
    const defense_preparation_preview clone =
            battle_defense_preparation::preview(
                    session, active_action_definitions[1]);
    assert(clone.error ==
           defense_preparation_error::unsupported_category);
    assert(session == before_preview);

    battle_condition_variant no_conditions;
    const battle_turn_flow_result completed =
            battle_turn_flow::complete_defense(
                    session, sharingan, no_conditions);
    assert(completed.error == battle_turn_flow_error::none);
    assert(completed.transition == battle_transition::side_changed);
    assert(session.unit(1)->chakra == 3);
    assert(session.unit(1)->ledger.defense_kind ==
           defense_action_kind::active_action);
    assert(session.unit(1)->ledger.defense_ability == 15);
    assert(session.unit(1)->ledger.defense_tool_slot == no_tool_slot);
    const std::uint8_t sharingan_slot =
            session.unit(1)->statuses.find(0x10);
    assert(sharingan_slot != no_status_slot);
    const status_record* prepared =
            session.unit(1)->statuses.active(sharingan_slot);
    assert(prepared->raw_parameter_1 == 15);
    assert(prepared->duration_ticks == 1);

    battle_session<2> in_place;
    assert(in_place.add_unit(unit(
            9, battle_side::player, { 1, 1 }, 80, 5)));
    assert(in_place.add_unit(unit(
            10, battle_side::enemy, { 2, 1 }, 80, 5)));
    assert(in_place.start_round() ==
           battle_transition::unit_selection_opened);
    open_defense(in_place, 9);
    const defense_preparation_preview in_place_prepared =
            battle_defense_preparation::commit_in_place(
                    in_place, sharingan);
    assert(in_place_prepared.legal());
    assert(in_place.unit(9)->chakra == 3);
    assert(in_place.unit(9)->statuses.find(0x10) !=
           no_status_slot);

    assert(session.select_unit(2) ==
           battle_transition::action_draft_opened);
    deterministic_rng incoming_rng(1);
    const action_result reacted = battle_action_resolver::resolve_draft(
            session,
            1,
            no_battle_unit,
            incoming_attack(),
            { 1, 1 },
            incoming_rng);
    assert(reacted.success());
    assert(reacted.generated_hits == 3);
    assert(reacted.effective_hits == 1);
    assert(reacted.reaction_code == 0x10);
    assert(reacted.reaction_action_id == 15);
    assert(reacted.reaction_hit_index == 0);
    assert(reacted.reaction_event.triggered);
    assert(reacted.reaction_event.action_kind ==
           defense_action_kind::active_action);
    assert(reacted.reaction_event.action_id == 15);
    assert(reacted.reaction_event.tool_slot == no_tool_slot);
    assert(reacted.reaction_event.source_id == 1);
    assert(reacted.reaction_event.target_id == 2);
    assert(reacted.damage_step_count == 0);
    assert(session.unit(1)->hp == 80);
    assert(session.unit(1)->statuses.find(0x10) == no_status_slot);

    finish_effects_without_defense(session);
    open_defense(session, 1);
    assert(battle_turn_flow::complete_defense(
                   session, no_ability, no_conditions).error ==
           battle_turn_flow_error::none);
    assert(session.select_unit(2) ==
           battle_transition::action_draft_opened);
    deterministic_rng second_rng(1);
    const action_result second = battle_action_resolver::resolve_draft(
            session,
            1,
            no_battle_unit,
            incoming_attack(1),
            { 1, 1 },
            second_rng);
    assert(second.success());
    assert(second.reaction_code == 0);
    assert(second.damage_step_count == 1);
    assert(session.unit(1)->hp < 80);

    battle_session<2> missed;
    assert(missed.add_unit(unit(
            5, battle_side::player, { 1, 1 }, 80, 5)));
    assert(missed.add_unit(unit(
            6, battle_side::enemy, { 2, 1 }, 80, 5)));
    assert(missed.start_round() ==
           battle_transition::unit_selection_opened);
    open_defense(missed, 5);
    assert(battle_turn_flow::complete_defense(
                   missed, sharingan, no_conditions).error ==
           battle_turn_flow_error::none);
    assert(missed.select_unit(6) ==
           battle_transition::action_draft_opened);
    deterministic_rng missed_rng(1);
    const action_result missed_attack =
            battle_action_resolver::resolve_draft(
                    missed,
                    5,
                    no_battle_unit,
                    incoming_attack(1, 0),
                    { 1, 1 },
                    missed_rng);
    assert(missed_attack.success());
    assert(missed_attack.effective_hits == 0);
    assert(missed_attack.reaction_code == 0);
    assert(missed.unit(5)->statuses.find(0x10) !=
           no_status_slot);
    assert(missed.unit(5)->hp == 80);

    battle_session<2> insufficient;
    assert(insufficient.add_unit(unit(
            3, battle_side::player, { 1, 1 }, 80, 1)));
    assert(insufficient.add_unit(unit(
            4, battle_side::enemy, { 2, 1 }, 80, 5)));
    assert(insufficient.start_round() ==
           battle_transition::unit_selection_opened);
    open_defense(insufficient, 3);
    const battle_session<2> before_insufficient = insufficient;
    const battle_turn_flow_result rejected =
            battle_turn_flow::complete_defense(
                    insufficient, sharingan, no_conditions);
    assert(rejected.error ==
           battle_turn_flow_error::defense_preparation_error);
    assert(insufficient == before_insufficient);

    battle_session<2> full_statuses;
    battle_unit_instance saturated = unit(
            7, battle_side::player, { 1, 1 }, 80, 5);
    for(std::uint8_t code = 1; code <= 14; ++code)
    {
        assert(saturated.statuses.upsert({
            code, 0, 4, 0, 7, 0, 0,
        }));
    }
    assert(saturated.statuses.upsert({
        0x12, 0, 4, 0, 7, 0, 0,
    }));
    assert(saturated.statuses.upsert({
        0x13, 0, 4, 0, 7, 0, 0,
    }));
    assert(full_statuses.add_unit(saturated));
    assert(full_statuses.add_unit(unit(
            8, battle_side::enemy, { 2, 1 }, 80, 5)));
    assert(full_statuses.start_round() ==
           battle_transition::unit_selection_opened);
    open_defense(full_statuses, 7);
    const battle_session<2> before_saturated = full_statuses;
    const defense_preparation_preview no_capacity =
            battle_defense_preparation::preview(
                    full_statuses, sharingan);
    assert(no_capacity.error ==
           defense_preparation_error::status_capacity_exhausted);
    assert(full_statuses == before_saturated);
}
