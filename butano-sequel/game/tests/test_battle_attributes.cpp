#include "konoha/battle_attributes.h"
#include "konoha/battle_session.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit()
{
    battle_unit_instance result = {
        1,
        battle_side::player,
        battle_control::player,
        { 1, 1 },
        battle_facing::down,
        100,
        100,
        5,
        5,
        3,
        true,
        {},
    };
    result.attack = 10;
    result.defense = 20;
    result.agility = 30;
    return result;
}

}

int main()
{
    battle_unit_instance modified = unit();
    battle_attribute_system::initialize_base(modified);
    assert(modified.base_attack == 10);
    assert(modified.base_defense == 20);
    assert(modified.base_agility == 30);
    assert(modified.base_move_range == 3);
    assert(modified.base_max_hp == 100);

    assert(modified.statuses.upsert({ 0x1E, 0, 0, 0, 0, 0, 50 }));
    assert(modified.statuses.upsert({ 0x1F, 0, 0, 0, 0, 0, 50 }));
    assert(modified.statuses.upsert({ 0x20, 0, 0, 0, 0, 0, 50 }));
    assert(modified.statuses.upsert({ 0x21, 0, 0, 0, 0, 0, 50 }));
    assert(modified.statuses.upsert({ 0x22, 0, 0, 0, 0, 0, 20 }));
    assert(modified.statuses.upsert({ 0x23, 0, 0, 0, 0, 0, 50 }));
    assert(modified.statuses.upsert({ 0x24, 0, 0, 0, 0, 0, 8 }));
    assert(modified.statuses.upsert({ 0x25, 0, 0, 0, 0, 0, 2 }));
    assert(modified.statuses.upsert({ 0x1B, 0, 0, 0, 0, 0, 50 }));
    modified.hp = 999;
    battle_attribute_system::recompute(modified);
    assert(modified.attack == 8);
    assert(modified.defense == 15);
    assert(modified.agility == 18);
    assert(modified.move_range == 7);
    assert(modified.max_hp == 150);
    assert(modified.hp == 150);

    battle_unit_instance ordered = unit();
    battle_attribute_system::initialize_base(ordered);
    assert(ordered.statuses.upsert({ 0x1F, 0, 0, 0, 0, 0, 50 }));
    assert(ordered.statuses.upsert({ 0x1E, 0, 0, 0, 0, 0, 50 }));
    battle_attribute_system::recompute(ordered);
    assert(ordered.attack == 7);

    battle_unit_instance expiring = unit();
    assert(expiring.statuses.upsert({ 0x1E, 0, 1, 0, 0, 0, 50 }));
    battle_session<1> session;
    assert(session.add_unit(expiring));
    assert(session.start_round() == battle_transition::unit_selection_opened);
    assert(session.select_unit(1) == battle_transition::action_draft_opened);
    assert(session.commit_action(battle_facing::up, no_ability) ==
           battle_transition::round_advanced);
    assert(session.unit(1)->statuses.find(0x1E) == no_status_slot);
    assert(session.unit(1)->attack == 10);
}
