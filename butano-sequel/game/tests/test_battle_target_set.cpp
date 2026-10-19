#include "konoha/battle_target_set.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        grid_point position)
{
    return {
        id,
        side,
        battle_control::ai,
        position,
        battle_facing::down,
        100,
        100,
        0,
        0,
        3,
        true,
        {},
    };
}

}

int main()
{
    const battle_unit_instance source =
            unit(1, battle_side::player, { 0, 0 });
    const std::array<battle_unit_instance, 9> units = {
        source,
        unit(10, battle_side::enemy, { 3, 3 }),
        unit(11, battle_side::enemy, { 3, 2 }),
        unit(12, battle_side::enemy, { 4, 3 }),
        unit(13, battle_side::enemy, { 4, 4 }),
        unit(14, battle_side::player, { 2, 3 }),
        unit(15, battle_side::enemy, { 3, 1 }),
        unit(16, battle_side::enemy, { 5, 3 }),
        unit(17, battle_side::enemy, { 3, 0 }),
    };

    const battle_target_set<9> diamond =
            battle_action_targeting::collect(
                    source,
                    units,
                    target_policy{ target_policy_kind::opponent_unit, 0 },
                    range_shape{ 4, 2 },
                    { 3, 3 });
    assert(diamond.count == 3);
    assert(diamond.ids[0] == 10);
    assert(diamond.ids[1] == 11);
    assert(diamond.ids[2] == 12);
    assert(! diamond.contains(13));
    assert(! diamond.contains(14));
    assert(! diamond.contains(15));

    const battle_target_set<9> cross =
            battle_action_targeting::collect(
                    source,
                    units,
                    target_policy{ target_policy_kind::opponent_unit, 0 },
                    range_shape{ 4, 0x83 },
                    { 3, 3 });
    assert(cross.count == 5);
    assert(cross.contains(10));
    assert(cross.contains(11));
    assert(cross.contains(12));
    assert(cross.contains(15));
    assert(cross.contains(16));
    assert(! cross.contains(13));
    assert(! cross.contains(17));

    const battle_target_set<9> center_only =
            battle_action_targeting::collect(
                    source,
                    units,
                    target_policy{ target_policy_kind::opponent_unit, 0 },
                    range_shape{ 4, 1 },
                    { 3, 3 });
    assert(center_only.count == 1);
    assert(center_only.ids[0] == 10);

    const battle_target_set<9> friendly =
            battle_action_targeting::collect(
                    source,
                    units,
                    target_policy{ target_policy_kind::friendly_unit_policy_1, 0 },
                    range_shape{ 4, 2 },
                    { 3, 3 });
    assert(friendly.count == 1);
    assert(friendly.ids[0] == 14);
}
