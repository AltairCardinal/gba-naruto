#include "konoha/battle_map_scenery.h"

#include <cassert>

using namespace konoha;

int main()
{
    const battle_map_scenery_record* chest =
            battle_map_scenery_for(14);
    assert(chest);
    assert(chest->battle_id == 14);
    assert(chest->world_x == 176);
    assert(chest->world_y == -176);
    assert(chest->bg_priority == 2);
    assert(chest->z_order == -4);
    assert(! battle_map_scenery_for(13));
    assert(! battle_map_scenery_for(15));
}
