#include "konoha/battle_action_system.h"
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
        int max_hp,
        int chakra,
        int max_chakra)
{
    battle_unit_instance result = {
        id,
        side,
        side == battle_side::player ? battle_control::player : battle_control::ai,
        position,
        battle_facing::down,
        hp,
        max_hp,
        chakra,
        max_chakra,
        3,
        true,
        {},
    };
    result.attack = 20;
    result.agility = 10;
    return result;
}

action_definition action(
        ability_id id,
        std::uint8_t effect_code,
        std::uint8_t potency,
        target_policy_kind target,
        std::uint8_t duration = 0)
{
    action_definition result;
    result.id = id;
    result.effect = { effect_code, 0, potency, 1, 100, duration };
    result.target = { target, 0 };
    result.range = { 4, 1 };
    return result;
}

}

int main()
{
    for(const action_definition& definition : active_action_definitions)
    {
        if(definition.effect.code != 0)
        {
            assert(effect_resolver_registry::handler_for(
                           definition.effect.code) !=
                   effect_handler_kind::unimplemented);
        }
    }
    for(const action_definition& definition : ninja_tool_action_definitions)
    {
        if(definition.effect.code != 0)
        {
            assert(effect_resolver_registry::handler_for(
                           definition.effect.code) !=
                   effect_handler_kind::unimplemented);
        }
    }

    battle_session<2> heal_session;
    assert(heal_session.add_unit(unit(
            1, battle_side::player, { 1, 1 }, 120, 150, 10, 10)));
    assert(heal_session.add_unit(unit(
            2, battle_side::enemy, { 5, 5 }, 100, 100, 0, 0)));
    assert(heal_session.start_round() == battle_transition::unit_selection_opened);
    assert(heal_session.select_unit(1) == battle_transition::action_draft_opened);
    deterministic_rng heal_rng(3);
    const action_result healed = battle_action_resolver::resolve_draft(
            heal_session,
            1,
            no_battle_unit,
            action(6, 0x06, 20, target_policy_kind::friendly_unit_policy_1),
            { 1, 1 },
            heal_rng);
    assert(healed.success());
    assert(healed.total_healing == 30);
    assert(heal_session.unit(1)->hp == 150);

    battle_session<2> chakra_session;
    assert(chakra_session.add_unit(unit(
            3, battle_side::player, { 1, 1 }, 80, 80, 2, 8)));
    assert(chakra_session.add_unit(unit(
            4, battle_side::enemy, { 2, 1 }, 80, 80, 6, 6)));
    assert(chakra_session.start_round() == battle_transition::unit_selection_opened);
    assert(chakra_session.select_unit(3) == battle_transition::action_draft_opened);
    deterministic_rng chakra_rng(5);
    const action_result restored = battle_action_resolver::resolve_draft(
            chakra_session,
            3,
            no_battle_unit,
            action(76, 0x1C, 5, target_policy_kind::friendly_unit_policy_1),
            { 1, 1 },
            chakra_rng);
    assert(restored.success());
    assert(restored.chakra_delta == 5);
    assert(chakra_session.unit(3)->chakra == 7);
    assert(chakra_session.open_facing_selection() ==
           battle_transition::facing_selection_opened);
    assert(chakra_session.select_facing(battle_facing::right) ==
           battle_transition::defense_selection_opened);
    assert(chakra_session.complete_action(no_ability) ==
           battle_transition::side_changed);

    assert(chakra_session.select_unit(4) == battle_transition::action_draft_opened);
    deterministic_rng drain_rng(7);
    const action_result drained = battle_action_resolver::resolve_draft(
            chakra_session,
            3,
            no_battle_unit,
            action(52, 0x1D, 9, target_policy_kind::opponent_unit),
            { 1, 1 },
            drain_rng);
    assert(drained.success());
    assert(drained.chakra_delta == -7);
    assert(chakra_session.unit(3)->chakra == 0);

    battle_session<2> object_session;
    assert(object_session.add_unit(unit(
            5, battle_side::player, { 1, 1 }, 80, 80, 0, 0)));
    assert(object_session.add_unit(unit(
            6, battle_side::enemy, { 5, 5 }, 80, 80, 0, 0)));
    assert(object_session.start_round() == battle_transition::unit_selection_opened);
    assert(object_session.select_unit(5) == battle_transition::action_draft_opened);
    deterministic_rng object_rng(9);
    const action_result created = battle_action_resolver::resolve_draft(
            object_session,
            no_battle_unit,
            no_battle_unit,
            action(37, 0x0C, 20, target_policy_kind::empty_tile, 4),
            { 3, 2 },
            object_rng);
    assert(created.success());
    assert(created.battlefield_object_slot == 1);
    const battlefield_object_record* object =
            object_session.objects().record(created.battlefield_object_slot);
    assert(object && object->type == 2);
    assert(object->x == 3 && object->y == 2);
    assert(object->payload_id == 37);
    assert(object->duration_ticks == 8);
    assert(object->source_unit_id == 0);
    assert(object->auxiliary == 0);

    battle_session<2> explosive_session;
    assert(explosive_session.add_unit(unit(
            15, battle_side::player, { 1, 1 }, 80, 80, 0, 0)));
    assert(explosive_session.add_unit(unit(
            16, battle_side::enemy, { 5, 5 }, 80, 80, 0, 0)));
    assert(explosive_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(explosive_session.select_unit(15) ==
           battle_transition::action_draft_opened);
    deterministic_rng explosive_rng(10);
    const action_result explosive_created =
            battle_action_resolver::resolve_draft(
                    explosive_session,
                    no_battle_unit,
                    no_battle_unit,
                    action(
                            67,
                            0x18,
                            20,
                            target_policy_kind::empty_tile,
                            1),
                    { 3, 2 },
                    explosive_rng);
    assert(explosive_created.success());
    const battlefield_object_record* explosive =
            explosive_session.objects().record(
                    explosive_created.battlefield_object_slot);
    assert(explosive && explosive->type == 1);
    assert(explosive->payload_id == 67);
    assert(explosive->duration_ticks == 2);
    assert(explosive->source_unit_id == 15);
    assert(explosive->auxiliary == 0);

    battle_session<4> explosion_session;
    assert(explosion_session.add_unit(unit(
            20, battle_side::player, { 1, 1 }, 80, 80, 0, 0)));
    assert(explosion_session.add_unit(unit(
            21, battle_side::enemy, { 3, 2 }, 100, 100, 0, 0)));
    assert(explosion_session.add_unit(unit(
            22, battle_side::player, { 3, 3 }, 100, 100, 0, 0)));
    assert(explosion_session.add_unit(unit(
            23, battle_side::enemy, { 5, 5 }, 100, 100, 0, 0)));
    battlefield_object_tick_event explosion_event;
    explosion_event.kind = battlefield_object_tick_kind::type_1_due;
    explosion_event.slot = 1;
    explosion_event.object.type = 1;
    explosion_event.object.x = 3;
    explosion_event.object.y = 2;
    explosion_event.object.payload_id = 67;
    explosion_event.object.source_unit_id = 20;
    deterministic_rng explosion_rng(12);
    const action_result exploded =
            battle_action_resolver::
                    resolve_battlefield_object_event(
                            explosion_session,
                            explosion_event,
                            ninja_tool_action_definitions[67],
                            explosion_rng);
    assert(exploded.success());
    assert(exploded.target_count == 2);
    assert(exploded.affected_unit_count == 2);
    assert(exploded.total_damage == 80);
    assert(explosion_session.unit(21)->hp == 60);
    assert(explosion_session.unit(22)->hp == 60);
    assert(explosion_session.unit(23)->hp == 100);

    battle_unit_instance paralysis_target = unit(
            25, battle_side::enemy, { 2, 1 }, 100, 100, 0, 0);
    paralysis_target.defense = 20;
    battle_session<2> paralysis_session;
    assert(paralysis_session.add_unit(unit(
            24, battle_side::player, { 1, 1 }, 80, 80, 5, 5)));
    assert(paralysis_session.add_unit(paralysis_target));
    assert(paralysis_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(paralysis_session.select_unit(24) ==
           battle_transition::action_draft_opened);
    action_definition paralysis =
            action(8, 0x01, 5, target_policy_kind::opponent_unit);
    paralysis.effect.flags = 0x80;
    deterministic_rng paralysis_rng(13);
    const action_result paralyzed =
            battle_action_resolver::resolve_draft(
                    paralysis_session,
                    25,
                    no_battle_unit,
                    paralysis,
                    { 2, 1 },
                    paralysis_rng);
    assert(paralyzed.success());
    assert(paralyzed.applied_status_count == 1);
    const battle_unit_instance* paralyzed_target =
            paralysis_session.unit(25);
    const std::uint8_t paralysis_slot =
            paralyzed_target->statuses.find(0x3F);
    assert(paralysis_slot != no_status_slot);
    const status_record* paralysis_status =
            paralyzed_target->statuses.active(paralysis_slot);
    assert(paralysis_status->raw_parameter_1 == 5);
    assert(paralysis_status->duration_ticks == 2);
    assert(paralysis_status->raw_parameter_3_low5 == 0);
    assert(paralysis_status->raw_parameter_4 == 24);
    assert(paralysis_status->value_u16 == 0);
    assert(paralyzed_target->reaction_state == 0x30);

    battle_unit_instance poison_target = unit(
            27, battle_side::enemy, { 2, 1 }, 100, 100, 0, 0);
    poison_target.attack = 20;
    poison_target.defense = 20;
    poison_target.agility = 20;
    battle_unit_instance poison_source = unit(
            26, battle_side::player, { 1, 1 }, 80, 80, 0, 0);
    poison_source.equipped_tools[0] = 11;
    battle_session<2> poison_session;
    assert(poison_session.add_unit(poison_source));
    assert(poison_session.add_unit(poison_target));
    assert(poison_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(poison_session.select_unit(26) ==
           battle_transition::action_draft_opened);
    deterministic_rng poison_rng(17);
    const action_result poisoned =
            battle_action_resolver::resolve_draft(
                    poison_session,
                    27,
                    no_battle_unit,
                    ninja_tool_action_for_slot(11, 0),
                    { 2, 1 },
                    poison_rng);
    assert(poisoned.success());
    assert(poisoned.applied_status_count == 3);
    const battle_unit_instance* poisoned_target =
            poison_session.unit(27);
    for(const std::uint8_t code : { 0x1F, 0x21, 0x23 })
    {
        const std::uint8_t slot =
                poisoned_target->statuses.find(code);
        assert(slot != no_status_slot);
        const status_record* status =
                poisoned_target->statuses.active(slot);
        assert(status->raw_parameter_1 == 6);
        assert(status->duration_ticks == 6);
        assert(status->raw_parameter_3_low5 == 0);
        assert(status->raw_parameter_4 == 26);
        assert(status->value_u16 == 10);
    }
    assert(poisoned_target->attack == 18);
    assert(poisoned_target->defense == 18);
    assert(poisoned_target->agility == 18);

    battle_unit_instance lethal_poison_target = unit(
            34, battle_side::enemy, { 2, 1 }, 1, 100, 0, 0);
    lethal_poison_target.attack = 20;
    lethal_poison_target.defense = 20;
    lethal_poison_target.agility = 20;
    battle_unit_instance lethal_poison_source = unit(
            33, battle_side::player, { 1, 1 }, 80, 80, 0, 0);
    lethal_poison_source.equipped_tools[0] = 11;
    battle_session<2> lethal_poison_session;
    assert(lethal_poison_session.add_unit(
            lethal_poison_source));
    assert(lethal_poison_session.add_unit(
            lethal_poison_target));
    assert(lethal_poison_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(lethal_poison_session.select_unit(33) ==
           battle_transition::action_draft_opened);
    deterministic_rng lethal_poison_rng(17);
    const action_result lethal_poison =
            battle_action_resolver::resolve_draft(
                    lethal_poison_session,
                    34,
                    no_battle_unit,
                    ninja_tool_action_for_slot(11, 0),
                    { 2, 1 },
                    lethal_poison_rng);
    assert(lethal_poison.success());
    assert(lethal_poison.defeated);
    assert(lethal_poison.applied_status_count == 3);
    const battle_unit_instance* lethal_poisoned_target =
            lethal_poison_session.unit(34);
    assert(! lethal_poisoned_target->active);
    assert(lethal_poisoned_target->hp == 0);
    for(const std::uint8_t code : { 0x1F, 0x21, 0x23 })
    {
        assert(lethal_poisoned_target->statuses.find(code) !=
               no_status_slot);
    }

    battle_unit_instance saturated_poison_target = unit(
            29, battle_side::enemy, { 2, 1 }, 100, 100, 0, 0);
    constexpr std::array<std::uint8_t, 14>
            non_reaction_status_codes = {{
                0x01, 0x02, 0x03, 0x05, 0x06, 0x07, 0x08,
                0x0B, 0x0C, 0x0E, 0x0F, 0x11, 0x12, 0x13,
            }};
    for(const std::uint8_t code : non_reaction_status_codes)
    {
        assert(saturated_poison_target.statuses.upsert({
            code, 0, 0, 0, 0, 0, 1,
        }));
    }
    battle_unit_instance saturated_poison_source = unit(
            28, battle_side::player, { 1, 1 }, 80, 80, 0, 0);
    saturated_poison_source.equipped_tools[0] = 11;
    battle_session<2> saturated_poison_session;
    assert(saturated_poison_session.add_unit(
            saturated_poison_source));
    assert(saturated_poison_session.add_unit(
            saturated_poison_target));
    assert(saturated_poison_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(saturated_poison_session.select_unit(28) ==
           battle_transition::action_draft_opened);
    const battle_session<2> before_saturated_poison =
            saturated_poison_session;
    deterministic_rng saturated_poison_rng(19);
    deterministic_rng expected_saturated_poison_rng(19);
    const action_result saturated_poison =
            battle_action_resolver::resolve_draft(
                    saturated_poison_session,
                    29,
                    no_battle_unit,
                    ninja_tool_action_for_slot(11, 0),
                    { 2, 1 },
                    saturated_poison_rng);
    assert(saturated_poison.error ==
           action_error::status_capacity_exhausted);
    assert(saturated_poison_session == before_saturated_poison);
    assert(saturated_poison_rng.next_u15() ==
           expected_saturated_poison_rng.next_u15());

    battle_unit_instance poison_explosion_target = unit(
            31, battle_side::enemy, { 3, 2 }, 100, 100, 0, 0);
    poison_explosion_target.attack = 20;
    poison_explosion_target.defense = 20;
    poison_explosion_target.agility = 20;
    battle_session<2> poison_explosion_session;
    assert(poison_explosion_session.add_unit(unit(
            30, battle_side::player, { 1, 1 }, 80, 80, 0, 0)));
    assert(poison_explosion_session.add_unit(
            poison_explosion_target));
    battlefield_object_tick_event poison_explosion_event;
    poison_explosion_event.kind =
            battlefield_object_tick_kind::type_1_due;
    poison_explosion_event.slot = 1;
    poison_explosion_event.object.type = 1;
    poison_explosion_event.object.x = 3;
    poison_explosion_event.object.y = 2;
    poison_explosion_event.object.payload_id = 70;
    poison_explosion_event.object.source_unit_id = 30;
    deterministic_rng poison_explosion_rng(23);
    const action_result poison_explosion =
            battle_action_resolver::resolve_battlefield_object_event(
                    poison_explosion_session,
                    poison_explosion_event,
                    ninja_tool_action_definitions[70],
                    poison_explosion_rng);
    assert(poison_explosion.success());
    assert(poison_explosion.applied_status_count == 3);
    const battle_unit_instance* poison_exploded =
            poison_explosion_session.unit(31);
    assert(poison_exploded->statuses.find(0x1F) != no_status_slot);
    assert(poison_exploded->statuses.find(0x21) != no_status_slot);
    assert(poison_exploded->statuses.find(0x23) != no_status_slot);
    assert(poison_exploded->attack == 18);
    assert(poison_exploded->defense == 18);
    assert(poison_exploded->agility == 18);

    battle_unit_instance saturated_object_target = unit(
            33, battle_side::enemy, { 3, 2 }, 100, 100, 0, 0);
    saturated_object_target.attack = 20;
    saturated_object_target.defense = 20;
    saturated_object_target.agility = 20;
    for(const std::uint8_t code : non_reaction_status_codes)
    {
        assert(saturated_object_target.statuses.upsert({
            code, 0, 0, 0, 0, 0, 1,
        }));
    }
    battle_session<2> saturated_object_session;
    assert(saturated_object_session.add_unit(unit(
            32, battle_side::player, { 0, 0 }, 80, 80, 0, 0)));
    assert(saturated_object_session.add_unit(
            saturated_object_target));
    battlefield_object_tick_event saturated_object_event =
            poison_explosion_event;
    saturated_object_event.object.source_unit_id = 32;
    const battle_session<2> before_saturated_object =
            saturated_object_session;
    deterministic_rng saturated_object_rng(29);
    deterministic_rng expected_saturated_object_rng(29);
    const action_result saturated_object =
            battle_action_resolver::resolve_battlefield_object_event(
                    saturated_object_session,
                    saturated_object_event,
                    ninja_tool_action_definitions[70],
                    saturated_object_rng);
    assert(saturated_object.error ==
           action_error::status_capacity_exhausted);
    assert(saturated_object_session == before_saturated_object);
    assert(saturated_object_rng.next_u15() ==
           expected_saturated_object_rng.next_u15());

    battle_unit_instance later_saturated_target = unit(
            42, battle_side::enemy, { 4, 2 }, 100, 100, 0, 0);
    later_saturated_target.attack = 20;
    later_saturated_target.defense = 20;
    later_saturated_target.agility = 20;
    for(const std::uint8_t code : non_reaction_status_codes)
    {
        assert(later_saturated_target.statuses.upsert({
            code, 0, 0, 0, 0, 0, 1,
        }));
    }
    battle_session<3> multi_object_session;
    assert(multi_object_session.add_unit(unit(
            40, battle_side::player, { 0, 0 }, 80, 80, 0, 0)));
    battle_unit_instance first_object_target = unit(
            41, battle_side::enemy, { 3, 2 }, 100, 100, 0, 0);
    first_object_target.attack = 20;
    first_object_target.defense = 20;
    first_object_target.agility = 20;
    assert(multi_object_session.add_unit(first_object_target));
    assert(multi_object_session.add_unit(later_saturated_target));
    battlefield_object_tick_event multi_object_event =
            poison_explosion_event;
    multi_object_event.object.source_unit_id = 40;
    const battle_session<3> before_multi_object =
            multi_object_session;
    deterministic_rng multi_object_rng(31);
    deterministic_rng expected_multi_object_rng(31);
    const action_result multi_object =
            battle_action_resolver::resolve_battlefield_object_event(
                    multi_object_session,
                    multi_object_event,
                    ninja_tool_action_definitions[70],
                    multi_object_rng);
    assert(multi_object.error ==
           action_error::status_capacity_exhausted);
    assert(multi_object_session == before_multi_object);
    assert(multi_object_rng.next_u15() ==
           expected_multi_object_rng.next_u15());

    battle_session<2> state_session;
    assert(state_session.add_unit(unit(
            7, battle_side::player, { 1, 1 }, 80, 80, 0, 0)));
    assert(state_session.add_unit(unit(
            8, battle_side::enemy, { 2, 1 }, 80, 80, 0, 0)));
    assert(state_session.start_round() == battle_transition::unit_selection_opened);
    assert(state_session.select_unit(7) == battle_transition::action_draft_opened);
    deterministic_rng state_rng(11);
    const action_result state_changed = battle_action_resolver::resolve_draft(
            state_session,
            8,
            no_battle_unit,
            action(80, 0x3F, 0, target_policy_kind::opponent_unit, 2),
            { 2, 1 },
            state_rng);
    assert(state_changed.success());
    assert(state_changed.applied_status_count == 1);
    assert(state_changed.reaction_state_changed);
    const battle_unit_instance* restrained_target =
            state_session.unit(8);
    assert(restrained_target);
    assert(restrained_target->reaction_state == 0x30);
    const std::uint8_t restraint_slot =
            restrained_target->statuses.find(0x3F);
    assert(restraint_slot != no_status_slot);
    const status_record* restraint =
            restrained_target->statuses.active(restraint_slot);
    assert(restraint);
    assert(restraint->code_with_flags == 0x3F);
    assert(restraint->duration_ticks ==
           encode_status_duration_ticks(2));
    assert(restraint->value_u16 == 0);

    battle_session<2> missed_state_session;
    assert(missed_state_session.add_unit(unit(
            26, battle_side::player, { 1, 1 }, 80, 80, 0, 0)));
    assert(missed_state_session.add_unit(unit(
            27, battle_side::enemy, { 2, 1 }, 80, 80, 0, 0)));
    assert(missed_state_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(missed_state_session.select_unit(26) ==
           battle_transition::action_draft_opened);
    action_definition fallible_state =
            action(80, 0x3F, 0, target_policy_kind::opponent_unit, 2);
    fallible_state.effect.success_rate_percent =
            active_action_definitions[80]
                    .effect.success_rate_percent;
    const action_preview fallible_state_preview =
            battle_action_resolver::preview(
                    missed_state_session,
                    27,
                    no_battle_unit,
                    fallible_state,
                    { 2, 1 });
    assert(fallible_state_preview.legal());
    assert(fallible_state_preview.success_rate_percent == 85);
    deterministic_rng missed_state_rng(1585);
    const action_result missed_state =
            battle_action_resolver::resolve_draft(
                    missed_state_session,
                    27,
                    no_battle_unit,
                    fallible_state,
                    { 2, 1 },
                    missed_state_rng);
    assert(missed_state.success());
    assert(missed_state.generated_hits == 1);
    assert(missed_state.effective_hits == 0);
    assert(missed_state.applied_status_count == 0);
    assert(! missed_state.reaction_state_changed);
    assert(missed_state_session.unit(27)->reaction_state == 0);
    assert(missed_state_session.unit(27)->statuses.find(0x3F) ==
           no_status_slot);

    battle_session<2> missed_status_session;
    assert(missed_status_session.add_unit(unit(
            28, battle_side::player, { 1, 1 }, 80, 80, 0, 0)));
    assert(missed_status_session.add_unit(unit(
            29, battle_side::enemy, { 2, 1 }, 80, 80, 0, 0)));
    assert(missed_status_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(missed_status_session.select_unit(28) ==
           battle_transition::action_draft_opened);
    action_definition fallible_status =
            action(23, 0x0E, 0, target_policy_kind::opponent_unit, 2);
    fallible_status.effect.success_rate_percent =
            active_action_definitions[23]
                    .effect.success_rate_percent;
    const action_preview fallible_status_preview =
            battle_action_resolver::preview(
                    missed_status_session,
                    29,
                    no_battle_unit,
                    fallible_status,
                    { 2, 1 });
    assert(fallible_status_preview.legal());
    assert(fallible_status_preview.success_rate_percent == 70);
    deterministic_rng missed_status_rng(1585);
    const action_result missed_status =
            battle_action_resolver::resolve_draft(
                    missed_status_session,
                    29,
                    no_battle_unit,
                    fallible_status,
                    { 2, 1 },
                    missed_status_rng);
    assert(missed_status.success());
    assert(missed_status.generated_hits == 1);
    assert(missed_status.effective_hits == 0);
    assert(missed_status.applied_status_count == 0);
    assert(missed_status_session.unit(29)->statuses.find(0x0E) ==
           no_status_slot);
    assert(missed_status_session.unit(29)->statuses.find(0x3E) ==
           no_status_slot);

    battle_unit_instance variant_source = unit(
            9, battle_side::player, { 1, 1 }, 80, 80, 5, 5);
    variant_source.character_id = 8;
    variant_source.original_character_id = 8;
    battle_unit_instance variant_slot = unit(
            10, battle_side::player, { 0, 0 }, 1, 1, 0, 0);
    variant_slot.active = false;
    battle_session<3> variant_session;
    assert(variant_session.add_unit(variant_source));
    assert(variant_session.add_unit(variant_slot));
    assert(variant_session.add_unit(unit(
            11, battle_side::enemy, { 5, 5 }, 80, 80, 0, 0)));
    assert(variant_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(variant_session.select_unit(9) ==
           battle_transition::action_draft_opened);
    deterministic_rng variant_rng(13);
    const action_result variant = battle_action_resolver::resolve_draft(
            variant_session,
            no_battle_unit,
            10,
            action(7, 0x07, 0, target_policy_kind::empty_tile),
            { 2, 1 },
            variant_rng);
    assert(variant.success());
    assert(variant.summon_count == 1);
    assert(variant_session.unit(9)->character_id == 0x39);
    assert(variant_session.unit(10)->character_id == 0x39);
    assert(variant_session.unit(10)->unit_state_code == 0x04);

    battle_unit_instance pair_primary_slot = unit(
            13, battle_side::player, { 0, 0 }, 1, 1, 0, 0);
    pair_primary_slot.active = false;
    battle_unit_instance pair_auxiliary_slot = unit(
            14, battle_side::player, { 0, 0 }, 1, 1, 0, 0);
    pair_auxiliary_slot.active = false;
    battle_session<4> pair_session;
    assert(pair_session.add_unit(unit(
            12, battle_side::player, { 1, 1 }, 90, 90, 4, 4)));
    assert(pair_session.add_unit(pair_primary_slot));
    assert(pair_session.add_unit(pair_auxiliary_slot));
    assert(pair_session.add_unit(unit(
            15, battle_side::enemy, { 5, 5 }, 80, 80, 0, 0)));
    assert(pair_session.start_round() == battle_transition::unit_selection_opened);
    assert(pair_session.select_unit(12) == battle_transition::action_draft_opened);
    deterministic_rng pair_rng(15);
    const action_result pair = battle_action_resolver::resolve_draft(
            pair_session,
            no_battle_unit,
            13,
            action(69, 0x17, 0, target_policy_kind::empty_tile),
            { 2, 1 },
            pair_rng);
    assert(pair.success());
    assert(pair.summon_count == 2);
    assert(pair_session.unit(12)->unit_state_code == 0x06);
    assert(pair_session.unit(12)->ai_linked_unit == 13);
    assert(pair_session.unit(13)->unit_state_code == 0x06);
    assert(pair_session.unit(13)->ai_linked_unit == 14);
    assert(pair_session.unit(14)->unit_state_code == 0x06);
    assert(pair_session.unit(14)->ai_linked_unit == 12);
    assert(pair_session.unit(14)->ai_secondary_linked_unit == 13);
    assert(pair_session.unit(13)->ledger.completed);
    assert(pair_session.unit(14)->ledger.completed);

    battle_unit_instance only_pair_slot = unit(
            21, battle_side::player, { 0, 0 }, 1, 1, 0, 0);
    only_pair_slot.active = false;
    battle_session<3> rejected_pair_session;
    assert(rejected_pair_session.add_unit(unit(
            20, battle_side::player, { 1, 1 }, 90, 90, 4, 4)));
    assert(rejected_pair_session.add_unit(only_pair_slot));
    assert(rejected_pair_session.add_unit(unit(
            22, battle_side::enemy, { 5, 5 }, 80, 80, 0, 0)));
    assert(rejected_pair_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(rejected_pair_session.select_unit(20) ==
           battle_transition::action_draft_opened);
    assert(battle_action_resolver::preview(
                   rejected_pair_session,
                   no_battle_unit,
                   21,
                   action(69, 0x17, 0, target_policy_kind::empty_tile),
                   { 2, 1 }).error ==
           action_error::summon_slot_unavailable);

    battle_session<2> rest_session;
    assert(rest_session.add_unit(unit(
            16, battle_side::player, { 1, 1 }, 50, 100, 1, 8)));
    assert(rest_session.add_unit(unit(
            17, battle_side::enemy, { 5, 5 }, 80, 80, 0, 0)));
    assert(rest_session.start_round() == battle_transition::unit_selection_opened);
    assert(rest_session.select_unit(16) == battle_transition::action_draft_opened);
    deterministic_rng rest_rng(17);
    const action_result rested = battle_action_resolver::resolve_draft(
            rest_session,
            16,
            no_battle_unit,
            action(28, 0x11, 4, target_policy_kind::self_or_implicit_actor),
            { 1, 1 },
            rest_rng);
    assert(rested.success());
    assert(rested.total_healing == 20);
    assert(rested.chakra_delta == 4);
    assert(rest_session.unit(16)->hp == 70);
    assert(rest_session.unit(16)->chakra == 5);
    assert(rest_session.unit(16)->statuses.find(0x02) != no_status_slot);

    battle_unit_instance passive_rest_unit =
            unit(23, battle_side::player, { 1, 1 }, 50, 100, 1, 8);
    assert(passive_rest_unit.passives.set_slot(0, 15, 1));
    battle_session<2> passive_rest_session;
    assert(passive_rest_session.add_unit(passive_rest_unit));
    assert(passive_rest_session.add_unit(unit(
            24, battle_side::enemy, { 5, 5 }, 80, 80, 0, 0)));
    assert(passive_rest_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(passive_rest_session.select_unit(23) ==
           battle_transition::action_draft_opened);
    deterministic_rng passive_rest_rng(23);
    const action_result passive_rested =
            battle_action_resolver::resolve_draft(
                    passive_rest_session,
                    23,
                    no_battle_unit,
                    action(
                            28,
                            0x11,
                            4,
                            target_policy_kind::self_or_implicit_actor),
                    { 1, 1 },
                    passive_rest_rng);
    assert(passive_rested.success());
    assert(passive_rested.total_healing == 50);
    assert(passive_rest_session.unit(23)->hp == 100);

    battle_session<2> compound_state_session;
    assert(compound_state_session.add_unit(unit(
            18, battle_side::player, { 1, 1 }, 80, 80, 0, 0)));
    assert(compound_state_session.add_unit(unit(
            19, battle_side::enemy, { 2, 1 }, 100, 100, 0, 0)));
    assert(compound_state_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(compound_state_session.select_unit(18) ==
           battle_transition::action_draft_opened);
    deterministic_rng compound_state_rng(19);
    action_definition damage_and_state =
            action(53, 0x15, 5, target_policy_kind::opponent_unit, 1);
    const action_result state_damage = battle_action_resolver::resolve_draft(
            compound_state_session,
            19,
            no_battle_unit,
            damage_and_state,
            { 2, 1 },
            compound_state_rng);
    assert(state_damage.success());
    assert(state_damage.total_damage == 10);
    assert(state_damage.applied_status_count == 1);
    assert(compound_state_session.unit(19)->statuses.find(0x15) !=
           no_status_slot);
    assert(compound_state_session.unit(19)->reaction_state == 0x40);
}
