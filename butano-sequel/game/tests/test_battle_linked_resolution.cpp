#include "konoha/battle_action_system.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id, battle_side side, grid_point position, int hp)
{
    battle_unit_instance result = {
        id,
        side,
        side == battle_side::player ? battle_control::player : battle_control::ai,
        position,
        battle_facing::down,
        hp,
        hp,
        10,
        10,
        3,
        true,
        {},
    };
    result.attack = 20;
    result.defense = 0;
    result.agility = 10;
    result.character_id = id;
    result.original_character_id = id;
    return result;
}

action_definition damage_action()
{
    action_definition result;
    result.id = 19;
    result.effect = { 1, 0, 10, 1, 100, 0 };
    result.target = { target_policy_kind::opponent_unit, 0 };
    result.range = { 1, 0 };
    return result;
}

}

int main()
{
    battle_unit_instance primary = unit(
            2, battle_side::enemy, { 2, 1 }, 50);
    assert(primary.statuses.upsert({ 0x0E, 0, 0, 0, 3, 0, 0 }));
    battle_unit_instance linked = unit(
            3, battle_side::enemy, { 5, 5 }, 15);
    assert(linked.statuses.upsert({ 0x0E, 0, 0, 0, 2, 0, 0 }));

    battle_session<3> session;
    assert(session.add_unit(unit(1, battle_side::player, { 1, 1 }, 40)));
    assert(session.add_unit(primary));
    assert(session.add_unit(linked));
    assert(session.start_round() == battle_transition::unit_selection_opened);
    assert(session.select_unit(1) == battle_transition::action_draft_opened);
    deterministic_rng rng(7);
    const action_result result = battle_action_resolver::resolve_draft(
            session,
            2,
            no_battle_unit,
            damage_action(),
            { 2, 1 },
            rng);
    assert(result.success());
    assert(result.generated_hits == 1);
    assert(result.effective_hits == 1);
    assert(result.total_damage == 35);
    assert(result.linked_resolution_count == 1);
    assert(result.damage_step_count == 2);
    assert(result.damage_steps[0].linked);
    assert(result.damage_steps[0].target_id == 3);
    assert(result.damage_steps[0].damage == 15);
    assert(result.damage_steps[0].defeated);
    assert(! result.damage_steps[1].linked);
    assert(result.damage_steps[1].target_id == 2);
    assert(result.damage_steps[1].damage == 20);
    assert(! result.damage_steps[1].defeated);
    assert(! session.unit(3)->active);
    assert(session.unit(3)->hp == 0);
    assert(session.unit(2)->hp == 30);

    battle_unit_instance reacting_primary = unit(
            5, battle_side::enemy, { 2, 1 }, 50);
    assert(reacting_primary.statuses.upsert({ 0x0E, 0, 0, 0, 6, 0, 0 }));
    assert(reacting_primary.statuses.upsert({ 0x10, 44, 0, 0, 0, 0, 0 }));
    battle_session<3> reaction_session;
    assert(reaction_session.add_unit(unit(
            4, battle_side::player, { 1, 1 }, 40)));
    assert(reaction_session.add_unit(reacting_primary));
    assert(reaction_session.add_unit(unit(
            6, battle_side::enemy, { 5, 5 }, 30)));
    assert(reaction_session.start_round() == battle_transition::unit_selection_opened);
    assert(reaction_session.select_unit(4) == battle_transition::action_draft_opened);
    deterministic_rng reaction_rng(7);
    const action_result reaction = battle_action_resolver::resolve_draft(
            reaction_session,
            5,
            no_battle_unit,
            damage_action(),
            { 2, 1 },
            reaction_rng);
    assert(reaction.success());
    assert(reaction.reaction_code == 0x10);
    assert(reaction.damage_step_count == 0);
    assert(reaction.linked_resolution_count == 0);
    assert(reaction_session.unit(5)->hp == 50);
    assert(reaction_session.unit(6)->hp == 30);
}
