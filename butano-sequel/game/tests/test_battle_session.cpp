#include "konoha/battle_session.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id, battle_side side, battle_control control, grid_point position)
{
    return {
        id,
        side,
        control,
        position,
        battle_facing::down,
        80,
        80,
        40,
        40,
        3,
        true,
        {},
    };
}

}

int main()
{
    battle_session<3> session;
    assert(session.add_unit(unit(1, battle_side::player, battle_control::player, { 2, 4 })));
    assert(session.add_unit(unit(2, battle_side::player, battle_control::player, { 3, 4 })));
    assert(session.add_unit(unit(3, battle_side::enemy, battle_control::ai, { 6, 4 })));
    assert(! session.add_unit(unit(3, battle_side::enemy, battle_control::ai, { 7, 4 })));
    assert(session.unit_count() == 3);

    assert(session.start_round() == battle_transition::unit_selection_opened);
    assert(session.round_index() == 1);
    assert(session.current_side() == battle_side::player);
    assert(session.lifecycle() == battle_lifecycle::unit_select);
    assert(session.cycle_available_unit(1, 1)->id == 2);
    assert(session.cycle_available_unit(2, 1)->id == 1);
    assert(session.cycle_available_unit(1, -1)->id == 2);
    assert(session.cycle_available_unit(1, 0) == nullptr);
    assert(session.select_unit(3) == battle_transition::invalid);

    assert(session.select_unit(1) == battle_transition::action_draft_opened);
    assert(session.lifecycle() == battle_lifecycle::action_drafting);
    assert(session.preview_move({ 2, 2 }) == battle_transition::move_previewed);
    assert((session.unit(1)->position == grid_point{ 2, 4 }));
    assert(session.draft().active);
    assert((session.draft().origin == grid_point{ 2, 4 }));
    assert((session.draft().preview_position == grid_point{ 2, 2 }));

    assert(session.cancel_action() == battle_transition::unit_selection_opened);
    assert(session.lifecycle() == battle_lifecycle::unit_select);
    assert((session.unit(1)->position == grid_point{ 2, 4 }));
    assert(! session.draft().active);

    assert(session.select_unit(1) == battle_transition::action_draft_opened);
    assert(session.preview_move({ 2, 2 }) == battle_transition::move_previewed);
    assert(session.commit_action(battle_facing::left, 7) == battle_transition::unit_completed);
    assert((session.unit(1)->position == grid_point{ 2, 2 }));
    assert(session.unit(1)->facing == battle_facing::left);
    assert(session.unit(1)->ledger.moved);
    assert(session.unit(1)->ledger.completed);
    assert(session.unit(1)->ledger.defense_ability == 7);
    assert(session.lifecycle() == battle_lifecycle::unit_select);
    assert(session.select_unit(1) == battle_transition::invalid);

    assert(session.select_unit(2) == battle_transition::action_draft_opened);
    assert(session.commit_action(battle_facing::up, no_ability) ==
           battle_transition::side_changed);
    assert(session.current_side() == battle_side::enemy);
    assert(session.lifecycle() == battle_lifecycle::unit_select);

    assert(session.select_unit(3) == battle_transition::action_draft_opened);
    assert(session.commit_action(battle_facing::right, no_ability) ==
           battle_transition::round_advanced);
    assert(session.round_index() == 2);
    assert(session.current_side() == battle_side::player);
    assert(! session.unit(1)->ledger.completed);
    assert(! session.unit(2)->ledger.completed);
    assert(! session.unit(3)->ledger.completed);
}
