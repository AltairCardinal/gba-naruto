#include "konoha/battle_range_ui_style.h"

#include <array>
#include <cassert>

using namespace konoha;

int main()
{
    // _prepare_tiles stores the original menu tiles 25..52 in the same BG
    // allocation as the grid. No range cell may be overwritten by that upload.
    std::array<bool, 128> used = {};
    for(int tile = 25; tile < 53; ++tile)
    {
        used[tile] = true;
    }
    for(int kind = 0; kind < battle_range_ui_range_kind_count; ++kind)
    {
        for(int y = 0; y < 2; ++y)
        {
            for(int x = 0; x < 4; ++x)
            {
                const int tile = battle_range_ui_tile_index(
                        static_cast<battle_range_ui_tile_kind>(kind), x, y);
                assert(tile > 0 && tile < battle_range_ui_logical_tile_count);
                assert(! used[tile]);
                used[tile] = true;
            }
        }
    }
}
