#include "konoha/battle_ui_model.h"
#include <array>
#include <cassert>

using namespace konoha;

int main()
{
    // Original zero-input recording: six exact repetitions of this cycle.
    constexpr std::array<int, 44> expected = {
        3,3,3,3, 2,2,2,2,2, 1,1,1,1,1,1,1,
        0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
        1,1,1,1,1,1,1,1, 2,2,2,2,2
    };
    for(int phase = 0; phase < 132; ++phase)
    {
        assert(battle_ui_destination_cursor_frame(phase) ==
                expected[static_cast<std::size_t>(phase % 44)]);
    }
    battle_scene_snapshot<12> state;
    state.phase = battle_scene_phase::move_selection;
    assert(! battle_ui_map_cursor_visible(state)); // no actor at the cursor
    assert(battle_ui_ground_cursor_visible(state, false, false));
    state.phase = battle_scene_phase::command_selection;
    assert(battle_ui_ground_cursor_visible(state, false, true)); // confirmed walk
    assert(! battle_ui_ground_cursor_visible(state, true, true));
    state.phase = battle_scene_phase::result;
    assert(! battle_ui_ground_cursor_visible(state, false, false));
}
