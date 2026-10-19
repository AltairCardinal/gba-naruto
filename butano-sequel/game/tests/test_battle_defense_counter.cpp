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
        int hp)
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
        5,
        5,
        3,
        true,
        {},
    };
    result.attack = 20;
    result.agility = 10;
    return result;
}

action_definition incoming_attack(int range)
{
    action_definition result;
    result.id = 5;
    result.effect = { 0x01, 0, 10, 1, 100, 0 };
    result.target = { target_policy_kind::opponent_unit, 0 };
    result.range = {
        static_cast<std::uint8_t>(range),
        1,
    };
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

void prepare_fire_bomb(
        battle_session<2>& session, int enemy_hp,
        grid_point enemy_position)
{
    battle_unit_instance defender = unit(
            1, battle_side::player, { 1, 1 }, 80);
    defender.equipped_tools[0] = 46;
    assert(session.add_unit(defender));
    assert(session.add_unit(unit(
            2, battle_side::enemy, enemy_position, enemy_hp)));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    open_defense(session);

    const action_definition fire_bomb =
            ninja_tool_action_for_slot(46, 0);
    const defense_preparation_preview preview =
            battle_defense_preparation::preview(
                    session, fire_bomb);
    assert(preview.legal());
    assert(preview.kind == defense_action_kind::ninja_tool);
    assert(preview.action_id == 46);
    assert(preview.tool_slot == 0);

    battle_condition_variant no_conditions;
    const battle_turn_flow_result completed =
            battle_turn_flow::complete_defense(
                    session, fire_bomb, no_conditions);
    assert(completed.error == battle_turn_flow_error::none);
    assert(completed.transition == battle_transition::side_changed);
    assert(session.unit(1)->equipped_tools[0] == no_ninja_tool);
    assert(session.unit(1)->ledger.defense_kind ==
           defense_action_kind::ninja_tool);
    assert(session.unit(1)->ledger.defense_ability == 46);
    assert(session.unit(1)->ledger.defense_tool_slot == 0);

    const std::uint8_t slot =
            session.unit(1)->statuses.find(0x19);
    assert(slot != no_status_slot);
    const status_record* prepared =
            session.unit(1)->statuses.active(slot);
    assert(prepared->raw_parameter_1 == (46 | 0x80));
    assert(prepared->value_u16 == 10);
}

void prepare_poison_smoke(
        battle_session<2>& session,
        grid_point enemy_position)
{
    battle_unit_instance defender = unit(
            1, battle_side::player, { 1, 1 }, 80);
    defender.equipped_tools[0] = 43;
    assert(session.add_unit(defender));
    battle_unit_instance attacker = unit(
            2, battle_side::enemy, enemy_position, 80);
    attacker.defense = 20;
    attacker.agility = 20;
    assert(session.add_unit(attacker));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    open_defense(session);

    const action_definition poison_smoke =
            ninja_tool_action_for_slot(43, 0);
    const defense_preparation_preview preview =
            battle_defense_preparation::preview(
                    session, poison_smoke);
    assert(preview.legal());
    assert(preview.kind == defense_action_kind::ninja_tool);
    assert(preview.action_id == 43);
    assert(preview.tool_slot == 0);

    battle_condition_variant no_conditions;
    const battle_turn_flow_result completed =
            battle_turn_flow::complete_defense(
                    session, poison_smoke, no_conditions);
    assert(completed.error == battle_turn_flow_error::none);
    assert(completed.transition == battle_transition::side_changed);
    assert(session.unit(1)->equipped_tools[0] == no_ninja_tool);
    const std::uint8_t slot =
            session.unit(1)->statuses.find(0x16);
    assert(slot != no_status_slot);
    const status_record* prepared =
            session.unit(1)->statuses.active(slot);
    assert((prepared->code_with_flags & 0x40) != 0);
    assert(prepared->raw_parameter_1 == (43 | 0x80));
    // complete_defense closes the player's side, so the stored
    // two-tick preparation has already consumed its first side-end tick.
    assert(prepared->duration_ticks == 1);
    assert(prepared->raw_parameter_3_low5 == 0);
    assert(prepared->raw_parameter_4 == 1);
    assert(prepared->value_u16 == 0);
}

}

int main()
{
    battle_session<2> wrong_tool;
    battle_unit_instance mismatched = unit(
            1, battle_side::player, { 1, 1 }, 80);
    mismatched.equipped_tools[0] = 47;
    assert(wrong_tool.add_unit(mismatched));
    assert(wrong_tool.add_unit(unit(
            2, battle_side::enemy, { 2, 1 }, 80)));
    assert(wrong_tool.start_round() ==
           battle_transition::unit_selection_opened);
    open_defense(wrong_tool);
    const battle_session<2> before_wrong_tool = wrong_tool;
    const defense_preparation_preview rejected_tool =
            battle_defense_preparation::preview(
                    wrong_tool,
                    ninja_tool_action_for_slot(46, 0));
    assert(rejected_tool.error ==
           defense_preparation_error::missing_ninja_tool);
    assert(wrong_tool == before_wrong_tool);

    battle_session<2> adjacent;
    prepare_fire_bomb(adjacent, 15, { 2, 1 });
    assert(adjacent.select_unit(2) ==
           battle_transition::action_draft_opened);
    deterministic_rng adjacent_rng(1);
    const action_result countered =
            battle_action_resolver::resolve_draft(
                    adjacent,
                    1,
                    no_battle_unit,
                    incoming_attack(1),
                    { 1, 1 },
                    adjacent_rng);
    assert(countered.success());
    assert(countered.generated_hits == 1);
    assert(countered.effective_hits == 1);
    assert(countered.reaction_code == 0x19);
    assert(countered.reaction_action_id == (46 | 0x80));
    assert(countered.reaction_hit_index == 0);
    assert(countered.reaction_event.triggered);
    assert(countered.reaction_event.action_kind ==
           defense_action_kind::ninja_tool);
    assert(countered.reaction_event.action_id == 46);
    assert(countered.reaction_event.tool_slot == 0);
    assert(countered.reaction_event.source_id == 1);
    assert(countered.reaction_event.target_id == 2);
    assert(countered.reaction_event.damage == 15);
    assert(countered.reaction_event.defeated);
    assert(countered.damage_step_count == 1);
    assert(countered.damage_steps[0].target_id == 2);
    assert(adjacent.unit(1)->hp == 80);
    assert(! adjacent.unit(2)->active);
    assert(adjacent.unit(1)->statuses.find(0x19) ==
           no_status_slot);

    battle_session<2> distant;
    prepare_fire_bomb(distant, 80, { 3, 1 });
    assert(distant.select_unit(2) ==
           battle_transition::action_draft_opened);
    deterministic_rng distant_rng(1);
    const action_result not_countered =
            battle_action_resolver::resolve_draft(
                    distant,
                    1,
                    no_battle_unit,
                    incoming_attack(3),
                    { 1, 1 },
                    distant_rng);
    assert(not_countered.success());
    assert(not_countered.reaction_code == 0);
    assert(! not_countered.reaction_event.triggered);
    assert(not_countered.damage_step_count == 1);
    assert(not_countered.damage_steps[0].target_id == 1);
    assert(distant.unit(1)->hp == 60);
    assert(distant.unit(1)->statuses.find(0x19) !=
           no_status_slot);

    battle_session<2> poison_smoke;
    prepare_poison_smoke(poison_smoke, { 2, 1 });
    assert(poison_smoke.select_unit(2) ==
           battle_transition::action_draft_opened);
    deterministic_rng poison_smoke_rng(5);
    const action_result smoke_countered =
            battle_action_resolver::resolve_draft(
                    poison_smoke,
                    1,
                    no_battle_unit,
                    incoming_attack(1),
                    { 1, 1 },
                    poison_smoke_rng);
    assert(smoke_countered.success());
    assert(smoke_countered.reaction_code == 0x16);
    assert(smoke_countered.reaction_action_id ==
           (43 | 0x80));
    assert(smoke_countered.reaction_event.triggered);
    assert(smoke_countered.reaction_event.action_kind ==
           defense_action_kind::ninja_tool);
    assert(smoke_countered.reaction_event.action_id == 43);
    assert(smoke_countered.reaction_event.tool_slot == 0);
    assert(smoke_countered.applied_status_count == 3);
    assert(poison_smoke.unit(1)->hp == 80);
    assert(poison_smoke.unit(1)->position !=
           grid_point({ 1, 1 }));
    const battle_unit_instance* poisoned_attacker =
            poison_smoke.unit(2);
    for(const std::uint8_t code : { 0x1F, 0x21, 0x23 })
    {
        const std::uint8_t slot =
                poisoned_attacker->statuses.find(code);
        assert(slot != no_status_slot);
        const status_record* status =
                poisoned_attacker->statuses.active(slot);
        assert(status->raw_parameter_1 == 0);
        assert(status->duration_ticks == 6);
        assert(status->raw_parameter_3_low5 == 0);
        assert(status->raw_parameter_4 == 1);
        assert(status->value_u16 == 10);
    }
    assert(poisoned_attacker->attack == 18);
    assert(poisoned_attacker->defense == 18);
    assert(poisoned_attacker->agility == 18);
}
