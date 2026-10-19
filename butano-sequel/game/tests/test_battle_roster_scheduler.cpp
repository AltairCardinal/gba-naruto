#include "konoha/battle_session.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        battle_control control)
{
    return {
        id,
        side,
        control,
        { id, 1 },
        battle_facing::down,
        50,
        50,
        5,
        5,
        2,
        true,
        {},
    };
}

}

int main()
{
    battle_session<5> session;
    assert(session.add_unit(unit(
            1, battle_side::player, battle_control::player)));
    assert(session.add_unit(unit(
            2, battle_side::player, battle_control::player)));
    assert(session.add_unit(unit(
            3, battle_side::player, battle_control::scripted)));
    assert(session.add_unit(unit(
            4, battle_side::enemy, battle_control::ai)));
    assert(session.add_unit(unit(
            5, battle_side::enemy, battle_control::ai)));
    assert(session.start_round() == battle_transition::unit_selection_opened);

    assert(session.cycle_roster_unit(1, 1)->id == 2);
    assert(session.cycle_roster_unit(2, 1)->id == 3);
    assert(session.cycle_roster_unit(3, 1)->id == 1);
    assert(session.can_issue_commands(1));
    assert(! session.can_issue_commands(3));
    assert(session.select_unit(3) == battle_transition::invalid);

    assert(session.select_unit(1) == battle_transition::action_draft_opened);
    assert(session.commit_action(battle_facing::right, no_ability) ==
           battle_transition::unit_completed);
    assert(session.cycle_roster_unit(2, -1)->id == 1);
    assert(! session.can_issue_commands(1));
    assert(session.cycle_available_unit(2, -1)->id == 2);

    assert(session.select_unit(2) == battle_transition::action_draft_opened);
    assert(session.commit_action(battle_facing::up, no_ability) ==
           battle_transition::side_changed);
    assert(session.current_side() == battle_side::enemy);

    assert(session.select_unit(4) == battle_transition::action_draft_opened);
    assert(session.commit_action(battle_facing::left, no_ability) ==
           battle_transition::unit_completed);
    assert(session.current_side() == battle_side::enemy);
    assert(session.select_unit(5) == battle_transition::action_draft_opened);
    assert(session.commit_action(battle_facing::left, no_ability) ==
           battle_transition::round_advanced);
    assert(session.round_index() == 2);
}
