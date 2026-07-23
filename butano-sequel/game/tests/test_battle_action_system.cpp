#include "konoha/battle_action_system.h"
#include "konoha/generated_battle_action_content.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id, battle_side side, grid_point position, int hp, int chakra)
{
    battle_unit_instance result = {
        id,
        side,
        side == battle_side::player ? battle_control::player : battle_control::ai,
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
    result.defense = 0;
    result.agility = 10;
    return result;
}

action_definition damage_action()
{
    action_definition result;
    result.id = 19;
    result.cost = { action_cost_kind::current_hp, 5, no_tool_slot };
    result.presentation = { 1 };
    result.effect = { 1, 0, 10, 3, 100, 0 };
    result.target = { target_policy_kind::opponent_unit, 0 };
    result.range = { 1, 0 };
    return result;
}

}

int main()
{
    const action_definition rom_lion_barrage = active_action_definitions[19];
    assert(rom_lion_barrage.cost.kind == action_cost_kind::current_hp);
    assert(rom_lion_barrage.cost.scalar == 80);
    assert(rom_lion_barrage.effect.code == 1);
    assert(rom_lion_barrage.effect.base_hit_count == 3);
    const action_definition rom_cross_shuriken = ninja_tool_action_for_slot(1, 2);
    assert(rom_cross_shuriken.cost.kind == action_cost_kind::battle_local_ninja_tool_slot);
    assert(rom_cross_shuriken.cost.tool_slot == 2);
    assert(rom_cross_shuriken.effect.code == 1);

    action_definition action = damage_action();
    assert(static_cast<int>(action.cost.kind) == 2);
    assert(action.presentation.animation_family == 1);
    assert(action.effect.code == 1);
    assert(action.target.kind == target_policy_kind::opponent_unit);
    assert(effect_resolver_registry::handler_for(1) == effect_handler_kind::damage);
    assert(effect_resolver_registry::handler_for(6) == effect_handler_kind::heal);
    assert(effect_resolver_registry::rom_handler_address(1) == 0x08077040U);
    assert(effect_resolver_registry::rom_handler_address(0x3F) == 0x0807755CU);

    battle_session<4> session;
    assert(session.add_unit(unit(1, battle_side::player, { 2, 2 }, 80, 10)));
    assert(session.add_unit(unit(2, battle_side::enemy, { 3, 2 }, 100, 0)));
    assert(session.start_round() == battle_transition::unit_selection_opened);
    assert(session.select_unit(1) == battle_transition::action_draft_opened);

    const action_preview preview = battle_action_resolver::preview(
            session, 2, no_battle_unit, action, { 3, 2 });
    assert(preview.legal());
    assert(preview.cost_kind == action_cost_kind::current_hp);
    assert(preview.scalar_cost == 5);
    assert(preview.hit_count == 3);
    assert(preview.damage_per_hit == 20);
    assert(preview.total_damage == 60);
    assert(session.unit(1)->hp == 80);
    assert(session.unit(2)->hp == 100);

    deterministic_rng rng(7);
    const action_result resolved = battle_action_resolver::resolve_draft(
            session, 2, no_battle_unit, action, { 3, 2 }, rng);
    assert(resolved.success());
    assert(resolved.generated_hits == 3);
    assert(resolved.effective_hits == 3);
    assert(resolved.total_damage == 60);
    assert(session.unit(1)->hp == 75);
    assert(session.unit(2)->hp == 40);
    assert(session.unit(1)->ledger.acted);
    assert(session.unit(1)->ledger.completed);
    assert(session.current_side() == battle_side::enemy);

    battle_session<2> rejected_session;
    assert(rejected_session.add_unit(unit(3, battle_side::player, { 1, 1 }, 4, 10)));
    assert(rejected_session.add_unit(unit(4, battle_side::enemy, { 2, 1 }, 30, 0)));
    assert(rejected_session.start_round() == battle_transition::unit_selection_opened);
    assert(rejected_session.select_unit(3) == battle_transition::action_draft_opened);
    const battle_session<2> before_rejection = rejected_session;
    deterministic_rng rejected_rng(7);
    const action_result rejected = battle_action_resolver::resolve_draft(
            rejected_session, 4, no_battle_unit, action, { 2, 1 }, rejected_rng);
    assert(rejected.error == action_error::insufficient_hp);
    assert(rejected_session == before_rejection);

    battle_unit_instance tool_user = unit(5, battle_side::player, { 1, 1 }, 30, 0);
    tool_user.equipped_tools[0] = 73;
    battle_session<2> tool_session;
    assert(tool_session.add_unit(tool_user));
    assert(tool_session.add_unit(unit(6, battle_side::enemy, { 3, 1 }, 30, 0)));
    assert(tool_session.start_round() == battle_transition::unit_selection_opened);
    assert(tool_session.select_unit(5) == battle_transition::action_draft_opened);

    action_definition tool_action;
    tool_action.id = 73;
    tool_action.cost = { action_cost_kind::battle_local_ninja_tool_slot, 0, 0 };
    tool_action.presentation = { 5 };
    tool_action.effect = { 6, 0, 10, 1, 100, 0 };
    tool_action.target = { target_policy_kind::self_or_implicit_actor, 0 };
    tool_action.range = { 0, 0 };
    deterministic_rng tool_rng(3);
    const action_result tool_result = battle_action_resolver::resolve_draft(
            tool_session, 5, no_battle_unit, tool_action, { 1, 1 }, tool_rng);
    assert(tool_result.success());
    assert(tool_session.unit(5)->equipped_tools[0] == no_ninja_tool);

    battle_session<2> target_session;
    assert(target_session.add_unit(unit(7, battle_side::player, { 1, 1 }, 30, 10)));
    assert(target_session.add_unit(unit(8, battle_side::enemy, { 2, 1 }, 30, 0)));
    assert(target_session.start_round() == battle_transition::unit_selection_opened);
    assert(target_session.select_unit(7) == battle_transition::action_draft_opened);
    action.cost = { action_cost_kind::current_chakra, 11, no_tool_slot };
    assert(battle_action_resolver::preview(
                   target_session, 8, no_battle_unit, action, { 2, 1 }).error ==
           action_error::insufficient_chakra);
    action.cost = { action_cost_kind::current_chakra, 1, no_tool_slot };
    action.target = { target_policy_kind::friendly_unit_policy_1, 0 };
    assert(battle_action_resolver::preview(
                   target_session, 8, no_battle_unit, action, { 2, 1 }).error ==
           action_error::invalid_target);
    action.target = { target_policy_kind::empty_tile, 0 };
    action.effect = { 2, 0, 0, 1, 100, 0 };
    action.range = { 2, 0 };
    assert(battle_action_resolver::preview(
                   target_session, no_battle_unit, no_battle_unit, action, { 2, 1 }).error ==
           action_error::occupied_target_tile);

    battle_unit_instance sharingan_target = unit(
            10, battle_side::enemy, { 2, 1 }, 30, 0);
    assert(sharingan_target.statuses.upsert({ 0x10, 15, 0, 0, 0, 0, 0 }));
    battle_session<2> reaction_session;
    assert(reaction_session.add_unit(unit(9, battle_side::player, { 1, 1 }, 30, 10)));
    assert(reaction_session.add_unit(sharingan_target));
    assert(reaction_session.start_round() == battle_transition::unit_selection_opened);
    assert(reaction_session.select_unit(9) == battle_transition::action_draft_opened);
    action_definition incoming = damage_action();
    incoming.cost = { action_cost_kind::current_chakra, 1, no_tool_slot };
    deterministic_rng reaction_rng(7);
    const action_result reacted = battle_action_resolver::resolve_draft(
            reaction_session, 10, no_battle_unit, incoming, { 2, 1 }, reaction_rng);
    assert(reacted.success());
    assert(reacted.generated_hits == 3);
    assert(reacted.effective_hits == 1);
    assert(reacted.total_damage == 0);
    assert(reacted.reaction_code == 0x10);
    assert(reacted.reaction_action_id == 15);
    assert(reacted.reaction_hit_index == 0);
    assert(reaction_session.unit(10)->hp == 30);
    assert(reaction_session.unit(10)->statuses.find(0x10) == no_status_slot);

    battle_session<2> facing_session;
    assert(facing_session.add_unit(unit(11, battle_side::player, { 1, 1 }, 30, 10)));
    assert(facing_session.add_unit(unit(12, battle_side::enemy, { 2, 1 }, 30, 0)));
    assert(facing_session.start_round() == battle_transition::unit_selection_opened);
    assert(facing_session.select_unit(11) == battle_transition::action_draft_opened);
    deterministic_rng facing_rng(7);
    const action_result faced = battle_action_resolver::resolve_draft(
            facing_session,
            12,
            no_battle_unit,
            incoming,
            { 2, 1 },
            battle_facing::right,
            facing_rng);
    assert(faced.success());
    assert(facing_session.unit(11)->facing == battle_facing::right);

    battle_unit_instance buff_target = unit(
            13, battle_side::player, { 1, 1 }, 100, 10);
    buff_target.attack = 20;
    buff_target.defense = 20;
    buff_target.agility = 20;
    battle_session<1> status_session;
    assert(status_session.add_unit(buff_target));
    assert(status_session.start_round() == battle_transition::unit_selection_opened);
    assert(status_session.select_unit(13) == battle_transition::action_draft_opened);
    action_definition compound;
    compound.id = 93;
    compound.cost = { action_cost_kind::none, 0, no_tool_slot };
    compound.presentation = { 1 };
    compound.effect = { 0x26, 0, 25, 1, 100, 2 };
    compound.target = { target_policy_kind::friendly_unit_policy_1, 0 };
    compound.range = { 0, 0 };
    deterministic_rng status_rng(9);
    const action_result compounded = battle_action_resolver::resolve_draft(
            status_session,
            13,
            no_battle_unit,
            compound,
            { 1, 1 },
            status_rng);
    assert(compounded.success());
    assert(compounded.applied_status_count == 4);
    assert(status_session.unit(13)->statuses.find(0x1E) != no_status_slot);
    assert(status_session.unit(13)->statuses.find(0x20) != no_status_slot);
    assert(status_session.unit(13)->statuses.find(0x22) != no_status_slot);
    assert(status_session.unit(13)->statuses.find(0x1B) != no_status_slot);
    assert(status_session.unit(13)->attack == 25);
    assert(status_session.unit(13)->defense == 25);
    assert(status_session.unit(13)->agility == 25);
    assert(status_session.unit(13)->max_hp == 125);
    assert(status_session.unit(13)->hp == 125);

    battle_unit_instance crowded = unit(
            14, battle_side::player, { 1, 1 }, 100, 10);
    for(std::uint8_t code = 1; code <= 14; ++code)
    {
        assert(crowded.statuses.upsert({ code, 0, 0, 0, 0, 0, 1 }));
    }
    battle_session<1> crowded_session;
    assert(crowded_session.add_unit(crowded));
    assert(crowded_session.start_round() == battle_transition::unit_selection_opened);
    assert(crowded_session.select_unit(14) == battle_transition::action_draft_opened);
    const battle_session<1> before_crowded = crowded_session;
    deterministic_rng crowded_rng(9);
    const action_result crowded_result = battle_action_resolver::resolve_draft(
            crowded_session,
            14,
            no_battle_unit,
            compound,
            { 1, 1 },
            crowded_rng);
    assert(crowded_result.error == action_error::status_capacity_exhausted);
    assert(crowded_session == before_crowded);
}
