#include "konoha/battle_runtime_grid.h"
#include "konoha/battle_scene_controller.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    for(const bool scripts : { false, true })
    {
        battle_runtime_controller controller;
        assert(controller.load(battle_scenario_definitions[14],
                battle_map_definitions[14], battle_map_cells, 0, {},
                battle_condition_variants[14][0], 49U, {}, scripts,
                battle_mission_rules_for(14, 0)).success());
        const auto deployed = controller.snapshot();
        assert(deployed.units[3].character_id == 30);
        assert(deployed.units[3].position == grid_point({8, 7}));
        assert(controller.start().success());
        int script_steps = 0;
        while(controller.snapshot().phase == battle_scene_phase::script_blocked)
        {
            assert(++script_steps < 1000);
            if(controller.snapshot().script.phase ==
                    battle_presentation_script_phase::wait_frames)
            {
                assert(controller.tick().success());
            }
            else
            {
                assert(controller.confirm().success());
            }
        }
        // Original S49: the escort's first AI turn precedes player input.
        assert(controller.snapshot().phase == battle_scene_phase::enemy_turn);
        assert(! controller.confirm().success());
        while(controller.presentation_pending())
        {
            (void) controller.take_presentation_event();
        }
        const auto ai = controller.tick();
        assert(ai.success());
        const auto event = controller.take_presentation_event();
        assert(event.valid);
        assert(event.origin == grid_point({8, 7}));
        assert(event.destination == grid_point({10, 7}));
        const auto ready = controller.snapshot();
        assert(ready.phase == battle_scene_phase::unit_selection);
        assert(ready.round == 1 && ready.current_side == battle_side::player);
        assert(ready.units[3].position == grid_point({10, 7}));
        assert(ready.units[3].completed);
        for(std::size_t i = 0; i < ready.unit_count; ++i)
        {
            assert(ready.units[i].hp == deployed.units[i].hp);
            if(i != 3)
            {
                assert(ready.units[i].position == deployed.units[i].position);
                assert(! ready.units[i].completed);
            }
        }
        assert(! controller.tick().success()); // no duplicate opening move
        assert(controller.confirm().success());
        assert(controller.snapshot().phase == battle_scene_phase::command_selection);
    }
}
