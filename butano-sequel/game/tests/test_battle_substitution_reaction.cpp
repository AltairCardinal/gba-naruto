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
        battle_control control,
        grid_point position)
{
    battle_unit_instance result = {
        id,
        side,
        control,
        position,
        battle_facing::down,
        80,
        80,
        5,
        5,
        3,
        true,
        {},
    };
    result.character_id = 35;
    result.original_character_id = 35;
    result.level = 1;
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
    result.target = {
        target_policy_kind::opponent_unit,
        0,
    };
    result.range = { 1, 1 };
    return result;
}

void open_defense(battle_session<2>& session)
{
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);
    assert(session.open_facing_selection() ==
           battle_transition::facing_selection_opened);
    assert(session.select_facing(battle_facing::right) ==
           battle_transition::defense_selection_opened);
}

}

int main()
{
    const action_definition substitution =
            active_action_definitions[3];
    assert(substitution.effect.code == 0x04);
    assert(substitution.cost.kind ==
           action_cost_kind::current_chakra);
    assert(substitution.cost.scalar == 3);

    battle_session<2> session;
    grid_map<5, 5> reaction_map;
    for(int y = 0; y < 5; ++y)
    {
        for(int x = 0; x < 5; ++x)
        {
            assert(reaction_map.set_cost(
                    { x, y }, 0));
        }
    }
    assert(reaction_map.set_cost({ 2, 2 }, 1));
    assert(reaction_map.set_cost({ 3, 2 }, 1));
    assert(reaction_map.set_cost({ 1, 2 }, 1));
    assert(session.configure_battlefield(
            reaction_map));
    assert(session.add_unit(unit(
            1,
            battle_side::player,
            battle_control::player,
            { 2, 2 })));
    assert(session.add_unit(unit(
            2,
            battle_side::enemy,
            battle_control::ai,
            { 3, 2 })));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    open_defense(session);

    const battle_session<2> before_preview = session;
    const defense_preparation_preview preview =
            battle_defense_preparation::preview(
                    session, substitution);
    assert(preview.legal());
    assert(preview.kind ==
           defense_action_kind::active_action);
    assert(preview.action_id == 3);
    assert(preview.chakra_cost == 3);
    assert(session == before_preview);

    battle_condition_variant no_conditions;
    const battle_turn_flow_result prepared =
            battle_turn_flow::complete_defense(
                    session,
                    substitution,
                    no_conditions);
    assert(prepared.error ==
           battle_turn_flow_error::none);
    assert(session.unit(1)->chakra == 2);
    assert(session.unit(1)->ledger.defense_kind ==
           defense_action_kind::active_action);
    assert(session.unit(1)->ledger.defense_ability == 3);
    const std::uint8_t substitution_slot =
            session.unit(1)->statuses.find(0x16);
    assert(substitution_slot != no_status_slot);
    const status_record* stored =
            session.unit(1)->statuses.active(
                    substitution_slot);
    assert(stored);
    assert(stored->raw_parameter_1 == 3);

    assert(session.select_unit(2) ==
           battle_transition::action_draft_opened);
    const grid_point origin =
            session.unit(1)->position;
    deterministic_rng incoming_rng(1);
    const action_result reacted =
            battle_action_resolver::resolve_draft(
                    session,
                    1,
                    no_battle_unit,
                    incoming_attack(),
                    origin,
                    incoming_rng);
    assert(reacted.success());
    assert(reacted.generated_hits == 3);
    assert(reacted.effective_hits == 1);
    assert(reacted.total_damage == 0);
    assert(reacted.damage_step_count == 0);
    assert(reacted.reaction_code == 0x16);
    assert(reacted.reaction_action_id == 3);
    assert(reacted.reaction_hit_index == 0);
    assert(reacted.reaction_event.triggered);
    assert(reacted.reaction_event.code == 0x16);
    assert(reacted.reaction_event.action_kind ==
           defense_action_kind::active_action);
    assert(reacted.reaction_event.action_id == 3);
    assert(reacted.reaction_event.source_id == 1);
    assert(reacted.reaction_event.target_id == 2);
    assert(reacted.reaction_event.moved);
    assert(reacted.reaction_event.movement_origin ==
           origin);
    assert(reacted.reaction_event.movement_destination ==
           session.unit(1)->position);
    assert(reacted.moved);
    assert(reacted.movement_origin == origin);
    assert(reacted.movement_destination ==
           session.unit(1)->position);
    assert(reacted.movement_destination != origin);
    assert(reacted.movement_destination !=
           session.unit(2)->position);
    assert(reacted.movement_destination ==
           grid_point(1, 2));
    const int dx = reacted.movement_destination.x >
                           origin.x ?
            reacted.movement_destination.x - origin.x :
            origin.x - reacted.movement_destination.x;
    const int dy = reacted.movement_destination.y >
                           origin.y ?
            reacted.movement_destination.y - origin.y :
            origin.y - reacted.movement_destination.y;
    assert(dx + dy >= 1);
    assert(dx + dy <= 2);
    assert(session.unit(1)->hp == 80);
    assert(session.unit(1)->statuses.find(0x16) ==
           no_status_slot);

    battle_session<2> missed;
    assert(missed.add_unit(unit(
            1,
            battle_side::player,
            battle_control::player,
            { 2, 2 })));
    assert(missed.add_unit(unit(
            2,
            battle_side::enemy,
            battle_control::ai,
            { 3, 2 })));
    assert(missed.start_round() ==
           battle_transition::unit_selection_opened);
    open_defense(missed);
    assert(battle_turn_flow::complete_defense(
                   missed,
                   substitution,
                   no_conditions)
                   .error ==
           battle_turn_flow_error::none);
    assert(missed.select_unit(2) ==
           battle_transition::action_draft_opened);
    deterministic_rng missed_rng(1);
    const action_result missed_attack =
            battle_action_resolver::resolve_draft(
                    missed,
                    1,
                    no_battle_unit,
                    incoming_attack(1, 0),
                    { 2, 2 },
                    missed_rng);
    assert(missed_attack.success());
    assert(missed_attack.effective_hits == 0);
    assert(missed_attack.reaction_code == 0);
    assert(! missed_attack.moved);
    assert(missed.unit(1)->position ==
           grid_point(2, 2));
    assert(missed.unit(1)->statuses.find(0x16) !=
           no_status_slot);

    battle_unit_instance distant_substitution_defender =
            unit(
                    16,
                    battle_side::enemy,
                    battle_control::ai,
                    { 3, 1 });
    assert(distant_substitution_defender.statuses.upsert(
            { 0x16, 3, 0, 0, 0, 0, 0 }));
    battle_session<2> distant_substitution;
    assert(distant_substitution.add_unit(unit(
            15,
            battle_side::player,
            battle_control::player,
            { 1, 1 })));
    assert(distant_substitution.add_unit(
            distant_substitution_defender));
    assert(distant_substitution.start_round() ==
           battle_transition::unit_selection_opened);
    assert(distant_substitution.select_unit(15) ==
           battle_transition::action_draft_opened);
    deterministic_rng distant_substitution_rng(17);
    action_definition distant_attack = incoming_attack(1);
    distant_attack.range = { 3, 1 };
    const action_result distant_substitution_result =
            battle_action_resolver::resolve_draft(
                    distant_substitution,
                    16,
                    no_battle_unit,
                    distant_attack,
                    { 3, 1 },
                    distant_substitution_rng);
    assert(distant_substitution_result.success());
    assert(distant_substitution_result.reaction_code == 0);
    assert(distant_substitution_result.total_damage > 0);
    assert(distant_substitution.unit(16)->hp < 80);
    assert(distant_substitution.unit(16)->position ==
           grid_point(3, 1));
    assert(distant_substitution.unit(16)->statuses.find(0x16) !=
           no_status_slot);

    battle_unit_instance prioritized_defender = unit(
            4,
            battle_side::enemy,
            battle_control::ai,
            { 2, 1 });
    assert(prioritized_defender.statuses.upsert(
            { 0x10, 15, 0, 0, 0, 0, 0 }));
    assert(prioritized_defender.statuses.upsert(
            { 0x16, 3, 0, 0, 0, 0, 0 }));
    assert(prioritized_defender.statuses.upsert(
            { 0x19, static_cast<std::uint8_t>(46 | 0x80),
              0, 0, 0, 0, 10 }));
    battle_session<2> prioritized;
    assert(prioritized.add_unit(unit(
            3,
            battle_side::player,
            battle_control::player,
            { 1, 1 })));
    assert(prioritized.add_unit(prioritized_defender));
    assert(prioritized.start_round() ==
           battle_transition::unit_selection_opened);
    assert(prioritized.select_unit(3) ==
           battle_transition::action_draft_opened);
    deterministic_rng prioritized_rng(17);
    const action_result prioritized_result =
            battle_action_resolver::resolve_draft(
                    prioritized,
                    4,
                    no_battle_unit,
                    incoming_attack(),
                    { 2, 1 },
                    prioritized_rng);
    assert(prioritized_result.success());
    assert(prioritized_result.reaction_code == 0x10);
    assert(prioritized.unit(4)->statuses.find(0x10) ==
           no_status_slot);
    assert(prioritized.unit(4)->statuses.find(0x16) !=
           no_status_slot);
    assert(prioritized.unit(4)->statuses.find(0x19) !=
           no_status_slot);
    assert(prioritized.unit(4)->position ==
           grid_point(2, 1));
    assert(prioritized.unit(3)->hp == 80);

    battle_unit_instance evasion_defender = unit(
            6,
            battle_side::enemy,
            battle_control::ai,
            { 2, 1 });
    assert(evasion_defender.statuses.upsert(
            { 0x04, 41, 0, 0, 0, 0, 0 }));
    assert(evasion_defender.statuses.upsert(
            { 0x10, 15, 0, 0, 0, 0, 0 }));
    battle_session<2> evasion;
    assert(evasion.add_unit(unit(
            5,
            battle_side::player,
            battle_control::player,
            { 1, 1 })));
    assert(evasion.add_unit(evasion_defender));
    assert(evasion.start_round() ==
           battle_transition::unit_selection_opened);
    assert(evasion.select_unit(5) ==
           battle_transition::action_draft_opened);
    deterministic_rng evasion_rng(17);
    const action_result evasion_result =
            battle_action_resolver::resolve_draft(
                    evasion,
                    6,
                    no_battle_unit,
                    incoming_attack(),
                    { 2, 1 },
                    evasion_rng);
    assert(evasion_result.success());
    assert(evasion_result.effective_hits == 1);
    assert(evasion_result.total_damage == 0);
    assert(evasion_result.damage_step_count == 0);
    assert(evasion_result.reaction_code == 0x04);
    assert(evasion_result.reaction_action_id == 41);
    assert(evasion_result.reaction_hit_index == 0);
    assert(evasion_result.reaction_event.triggered);
    assert(evasion_result.reaction_event.code == 0x04);
    assert(evasion_result.reaction_event.source_id == 6);
    assert(evasion_result.reaction_event.target_id == 5);
    assert(! evasion_result.reaction_event.moved);
    assert(evasion.unit(6)->hp == 80);
    assert(evasion.unit(6)->position == grid_point(2, 1));
    assert(evasion.unit(6)->statuses.find(0x04) ==
           no_status_slot);
    assert(evasion.unit(6)->statuses.find(0x10) !=
           no_status_slot);

    battle_unit_instance area_evasion_defender =
            unit(
                    10,
                    battle_side::enemy,
                    battle_control::ai,
                    { 2, 1 });
    assert(area_evasion_defender.statuses.upsert(
            { 0x04, 41, 0, 0, 0, 0, 0 }));
    battle_session<2> area_evasion;
    assert(area_evasion.add_unit(unit(
            9,
            battle_side::player,
            battle_control::player,
            { 1, 1 })));
    assert(area_evasion.add_unit(
            area_evasion_defender));
    assert(area_evasion.start_round() ==
           battle_transition::unit_selection_opened);
    assert(area_evasion.select_unit(9) ==
           battle_transition::action_draft_opened);
    deterministic_rng area_evasion_rng(17);
    const action_result area_evasion_result =
            battle_action_resolver::resolve_area_draft(
                    area_evasion,
                    incoming_attack(1),
                    { 2, 1 },
                    area_evasion_rng);
    assert(area_evasion_result.success());
    assert(area_evasion_result.reaction_code == 0x04);
    assert(area_evasion_result.total_damage == 0);
    assert(area_evasion.unit(10)->hp == 80);
    assert(area_evasion.unit(10)->statuses.find(0x04) ==
           no_status_slot);

    battle_unit_instance counter_only_defender =
            unit(
                    12,
                    battle_side::enemy,
                    battle_control::ai,
                    { 2, 1 });
    assert(counter_only_defender.statuses.upsert(
            { 0x09, 33, 0, 1, 0, 0, 10 }));
    battle_session<2> counter_only;
    assert(counter_only.add_unit(unit(
            11,
            battle_side::player,
            battle_control::player,
            { 1, 1 })));
    assert(counter_only.add_unit(counter_only_defender));
    assert(counter_only.start_round() ==
           battle_transition::unit_selection_opened);
    assert(counter_only.select_unit(11) ==
           battle_transition::action_draft_opened);
    deterministic_rng counter_only_rng(17);
    const action_result counter_only_result =
            battle_action_resolver::resolve_draft(
                    counter_only,
                    12,
                    no_battle_unit,
                    incoming_attack(1),
                    { 2, 1 },
                    counter_only_rng);
    assert(counter_only_result.success());
    assert(counter_only_result.reaction_code == 0x09);
    assert(counter_only_result.reaction_event.triggered);
    assert(counter_only_result.reaction_event.damage > 0);
    assert(counter_only_result.reaction_event.source_id == 12);
    assert(counter_only_result.reaction_event.target_id == 11);
    assert(counter_only_result.damage_step_count == 1);
    assert(counter_only_result.damage_steps[0].target_id == 11);
    assert(counter_only.unit(11)->hp < 80);
    assert(counter_only.unit(12)->hp == 80);
    assert(counter_only.unit(12)->statuses.find(0x09) ==
           no_status_slot);

    battle_unit_instance exchange_defender =
            unit(
                    14,
                    battle_side::enemy,
                    battle_control::ai,
                    { 2, 1 });
    assert(exchange_defender.statuses.upsert(
            { 0x0A, 21, 0, 1, 0, 0, 10 }));
    battle_session<2> exchange;
    assert(exchange.add_unit(unit(
            13,
            battle_side::player,
            battle_control::player,
            { 1, 1 })));
    assert(exchange.add_unit(exchange_defender));
    assert(exchange.start_round() ==
           battle_transition::unit_selection_opened);
    assert(exchange.select_unit(13) ==
           battle_transition::action_draft_opened);
    deterministic_rng exchange_rng(17);
    const action_result exchange_result =
            battle_action_resolver::resolve_draft(
                    exchange,
                    14,
                    no_battle_unit,
                    incoming_attack(1),
                    { 2, 1 },
                    exchange_rng);
    assert(exchange_result.success());
    assert(exchange_result.reaction_code == 0x0A);
    assert(exchange_result.reaction_event.triggered);
    assert(exchange_result.reaction_event.damage > 0);
    assert(exchange_result.damage_step_count == 2);
    assert(exchange_result.damage_steps[0].target_id == 13);
    assert(exchange_result.damage_steps[1].target_id == 14);
    assert(exchange.unit(13)->hp < 80);
    assert(exchange.unit(14)->hp < 80);
    assert(exchange.unit(14)->statuses.find(0x0A) ==
           no_status_slot);

    battle_unit_instance enclosed_defender = unit(
            8,
            battle_side::enemy,
            battle_control::ai,
            { 1, 0 });
    assert(enclosed_defender.statuses.upsert(
            { 0x16, 3, 0, 0, 0, 0, 0 }));
    assert(enclosed_defender.statuses.upsert(
            { 0x19, static_cast<std::uint8_t>(46 | 0x80),
              0, 0, 0, 0, 10 }));
    battle_session<2> enclosed;
    grid_map<2, 1> enclosed_map;
    assert(enclosed_map.set_cost({ 0, 0 }, 1));
    assert(enclosed_map.set_cost({ 1, 0 }, 1));
    assert(enclosed.configure_battlefield(enclosed_map));
    assert(enclosed.add_unit(unit(
            7,
            battle_side::player,
            battle_control::player,
            { 0, 0 })));
    assert(enclosed.add_unit(enclosed_defender));
    assert(enclosed.start_round() ==
           battle_transition::unit_selection_opened);
    assert(enclosed.select_unit(7) ==
           battle_transition::action_draft_opened);
    deterministic_rng enclosed_rng(17);
    const action_result enclosed_result =
            battle_action_resolver::resolve_draft(
                    enclosed,
                    8,
                    no_battle_unit,
                    incoming_attack(1),
                    { 1, 0 },
                    enclosed_rng);
    assert(enclosed_result.success());
    assert(enclosed_result.reaction_code == 0);
    assert(enclosed_result.total_damage > 0);
    assert(enclosed.unit(8)->hp < 80);
    assert(enclosed.unit(7)->hp == 80);
    assert(enclosed.unit(8)->statuses.find(0x16) !=
           no_status_slot);
    assert(enclosed.unit(8)->statuses.find(0x19) !=
           no_status_slot);
}
