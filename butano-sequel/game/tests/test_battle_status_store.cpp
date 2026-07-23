#include "konoha/battle_status_store.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_status_store store;
    status_record first = { 0x90, 15, 2, 3, 4, 0, 7 };
    assert(store.upsert(first));
    assert(store.active_count() == 1);
    assert(store.find(0x10) == 0);
    assert(store.find(0x50) == 0);
    assert(store.active(0)->value_u16 == 7);

    status_record replacement = { 0x10, 21, 4, 0, 0, 0, 9 };
    assert(store.upsert(replacement));
    assert(store.active_count() == 1);
    assert(store.active(0)->raw_parameter_1 == 21);
    assert(store.active(0)->duration_ticks == 4);

    assert(store.remove(0x10, status_remove_mode::preserve_removed_event));
    assert(store.active_count() == 0);
    assert(store.removed_count() == 1);
    assert(store.removed(0)->value_u16 == 9);

    assert(store.upsert({ 1, 0, 2, 0, 0, 0, 0 }));
    assert(store.tick_side_end() == 0);
    assert(store.active(0)->duration_ticks == 1);
    assert(store.tick_side_end() == 1);
    assert(store.find(1) == no_status_slot);
    assert(store.removed_count() == 2);

    battle_status_store special;
    assert(special.upsert({ 0x3F, 0, 4, 0, 0, 0, 1 }));
    assert(special.upsert({ 0x3F, 0, 2, 0, 0, 0, 2 }));
    assert(special.active(0)->duration_ticks == 4);
    assert(special.active(0)->value_u16 == 1);
    assert(special.upsert({ 0x3F, 0, 6, 0, 0, 0, 3 }));
    assert(special.active(0)->duration_ticks == 6);
    assert(special.active(0)->value_u16 == 3);
    assert(special.upsert({ 0x3F, 0, 0, 0, 0, 0, 4 }));
    assert(special.active(0)->duration_ticks == 6);

    battle_status_store zero_duration;
    assert(zero_duration.upsert({ 2, 0, 0, 0, 0, 0, 0 }));
    assert(zero_duration.tick_side_end() == 0);
    assert(zero_duration.find(2) == 0);
}
