#include "konoha/battle_session.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(battle_unit_id id, battle_side side)
{
    return {
        id,
        side,
        side == battle_side::player ? battle_control::player : battle_control::ai,
        { static_cast<int>(id), 1 },
        battle_facing::down,
        30,
        30,
        5,
        5,
        3,
        true,
        {},
    };
}

}

int main()
{
    battle_unit_instance player = unit(1, battle_side::player);
    assert(player.statuses.upsert({ 1, 0, 2, 0, 0, 0, 0 }));
    battle_unit_instance enemy = unit(2, battle_side::enemy);
    assert(enemy.statuses.upsert({ 2, 0, 0, 0, 0, 0, 0 }));

    battle_session<2> session;
    assert(session.add_unit(player));
    assert(session.add_unit(enemy));
    assert(session.start_round() == battle_transition::unit_selection_opened);
    assert(session.select_unit(1) == battle_transition::action_draft_opened);
    assert(session.commit_action(battle_facing::down, no_ability) ==
           battle_transition::side_changed);
    assert(session.unit(1)->statuses.active(0)->duration_ticks == 1);
    assert(session.unit(2)->statuses.find(2) == 0);

    assert(session.select_unit(2) == battle_transition::action_draft_opened);
    assert(session.commit_action(battle_facing::up, no_ability) ==
           battle_transition::round_advanced);
    assert(session.unit(1)->statuses.find(1) == no_status_slot);
    assert(session.unit(1)->statuses.removed_count() == 1);
    assert(session.unit(2)->statuses.find(2) == 0);
}
