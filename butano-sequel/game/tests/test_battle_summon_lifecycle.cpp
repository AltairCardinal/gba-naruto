#include "konoha/battle_action_system.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        battle_control control,
        grid_point position,
        bool active = true)
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
        active,
        {},
    };
    result.attack = 17;
    result.defense = 9;
    result.agility = 11;
    result.character_id = 1;
    result.original_character_id = 1;
    return result;
}

}

int main()
{
    battle_session<3> session;
    assert(session.add_unit(unit(
            1,
            battle_side::player,
            battle_control::player,
            { 1, 1 })));
    battle_unit_instance free_slot = unit(
            7,
            battle_side::player,
            battle_control::player,
            { 0, 0 },
            false);
    free_slot.character_id = 30;
    free_slot.original_character_id = 30;
    free_slot.hp = 1;
    free_slot.max_hp = 1;
    assert(session.add_unit(free_slot));
    assert(session.add_unit(unit(
            9,
            battle_side::enemy,
            battle_control::ai,
            { 5, 5 })));
    assert(session.start_round() == battle_transition::unit_selection_opened);
    assert(session.select_unit(1) == battle_transition::action_draft_opened);

    const action_definition summon_action = {
        1,
        { action_cost_kind::current_chakra, 2, no_tool_slot },
        {},
        { 0x02, 0, 0, 1, 100, 0 },
        { target_policy_kind::empty_tile, 0 },
        { 3, 1 },
        {},
    };
    deterministic_rng summon_rng(5);
    const action_result summoned = battle_action_resolver::resolve_draft(
            session,
            no_battle_unit,
            7,
            summon_action,
            { 2, 1 },
            summon_rng);
    assert(summoned.success());
    assert(summoned.summoned);
    const battle_unit_instance* source = session.unit(1);
    const battle_unit_instance* clone = session.unit(7);
    assert(source->chakra == 3);
    assert(source->ai_linked_unit == 7);
    assert(clone->active);
    assert(clone->id == 7);
    assert(clone->summoner == 1);
    assert(clone->ai_linked_unit == 1);
    assert(clone->side == source->side);
    assert(clone->control == source->control);
    assert((clone->position == grid_point{ 2, 1 }));
    assert(clone->character_id == source->character_id);
    assert(clone->max_hp == source->max_hp);
    assert(clone->attack == source->attack);
    assert(clone->ledger.acted);
    assert(clone->ledger.completed);
    assert(! source->ledger.completed);
    assert(session.open_facing_selection() ==
           battle_transition::facing_selection_opened);
    assert(session.select_facing(battle_facing::right) ==
           battle_transition::defense_selection_opened);
    assert(session.complete_action(no_ability) ==
           battle_transition::side_changed);
    assert(session.current_side() == battle_side::enemy);

    assert(session.select_unit(9) == battle_transition::action_draft_opened);
    assert(session.commit_action(battle_facing::left, no_ability) ==
           battle_transition::round_advanced);
    assert(session.round_index() == 2);
    assert(! session.unit(7)->ledger.completed);
    assert(session.select_unit(7) == battle_transition::action_draft_opened);
}
