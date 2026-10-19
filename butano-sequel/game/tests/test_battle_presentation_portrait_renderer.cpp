#include "konoha/battle_presentation_portrait_renderer.h"

#include <cassert>
#include <cstddef>

using namespace konoha;

int main()
{
    assert(battle_presentation_portrait_components.size() == 6);
    std::size_t bytes = 0;
    for(const battle_presentation_portrait_component& component :
            battle_presentation_portrait_components)
    {
        assert(component.source_offset == bytes);
        assert(component.source_bytes ==
                static_cast<std::size_t>(
                        component.width *
                        component.height));
        bytes += component.source_bytes;
    }
    assert(bytes == 6400);

    assert(battle_presentation_portrait_origin_x(
                   0,
                   no_battle_presentation_portrait_motion) == 16);
    assert(battle_presentation_portrait_origin_x(
                   1,
                   no_battle_presentation_portrait_motion) == 144);
    assert(battle_presentation_portrait_origin_x(0, 2) == 80);
    assert(battle_presentation_portrait_origin_x(1, 2) == 80);
    assert(battle_presentation_portrait_origin_x(0, 3) == 64);
    assert(battle_presentation_portrait_origin_x(1, 3) == 96);
    assert(battle_presentation_portrait_origin_x(0, 4) == 16);
    assert(battle_presentation_portrait_origin_x(1, 4) == 144);

    assert(battle_presentation_portrait_palette_index(0, 0) == 0);
    assert(battle_presentation_portrait_palette_index(63, 0) == 63);
    assert(battle_presentation_portrait_palette_index(0, 1) == 0);
    assert(battle_presentation_portrait_palette_index(1, 1) == 65);
    assert(battle_presentation_portrait_palette_index(63, 1) == 127);

    assert(dim_battle_presentation_portrait_color(0x7FFF) == 0x5AD6);
    assert(dim_battle_presentation_portrait_color(0x001F) == 0x0016);
    assert(dim_battle_presentation_portrait_color(0x03E0) == 0x02C0);
    assert(dim_battle_presentation_portrait_color(0x7C00) == 0x5800);
}
