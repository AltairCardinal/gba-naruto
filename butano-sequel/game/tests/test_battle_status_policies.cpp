#include "konoha/battle_status_policies.h"
#include "konoha/battle_session.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(battle_unit_id id)
{
    return {
        id,
        battle_side::player,
        battle_control::player,
        { 1, 1 },
        battle_facing::down,
        30,
        30,
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
    battle_unit_instance source = unit(1);
    battle_unit_instance target = unit(2);
    assert(source.statuses.upsert({ 0x0D, 0, 0, 0, 0, 0, 0 }));
    assert(target.statuses.upsert({ 0x0D, 0, 0, 0, 0, 0, 0 }));
    target.status_mask = 0x00000100U;
    const status_consumption_result consumed =
            status_consumption_policy::apply(source, &target, 0x01);
    assert(consumed.source_consumed);
    assert(consumed.target_consumed);
    assert(consumed.count() == 2);
    assert(source.statuses.find(0x0D) == no_status_slot);
    assert(target.statuses.find(0x0D) == no_status_slot);
    assert(source.statuses.removed_count() == 0);
    assert(target.statuses.removed_count() == 0);
    assert((target.status_mask & 0x00000100U) == 0);

    for(std::uint8_t excluded : { 0x04, 0x09, 0x0A, 0x10, 0x16, 0x19 })
    {
        source = unit(1);
        target = unit(2);
        assert(source.statuses.upsert({ 0x0D, 0, 0, 0, 0, 0, 0 }));
        assert(target.statuses.upsert({ 0x0D, 0, 0, 0, 0, 0, 0 }));
        target.status_mask = 0x00000100U;
        const status_consumption_result preserved =
                status_consumption_policy::apply(source, &target, excluded);
        assert(preserved.count() == 0);
        assert(source.statuses.find(0x0D) != no_status_slot);
        assert(target.statuses.find(0x0D) != no_status_slot);
        assert((target.status_mask & 0x00000100U) != 0);
    }
}
