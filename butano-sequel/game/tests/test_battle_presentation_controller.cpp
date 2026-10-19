#include "konoha/battle_scene_controller.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_scenario_load_policy policy;
    policy.preserve_empty_unit_slots = true;

    battle_scene_controller<12, 9, 22> controller;
    assert(controller.load(
                   battle_scenario_definitions[41],
                   battle_map_definitions[41],
                   battle_map_cells,
                   0,
                   policy,
                   battle_condition_variants[41][0],
                   0x41U,
                   {},
                   true)
                   .success());
    assert(controller.start().success());

    battle_scene_snapshot<12> state = controller.snapshot();
    assert(state.phase ==
            battle_scene_phase::script_blocked);
    assert(state.round == 1);
    assert(state.current_side == battle_side::player);
    assert(state.script.phase ==
            battle_presentation_script_phase::
                    wait_for_input);
    assert(state.script.selector == 1);
    assert(state.script.text_address == 0x0805B2C0U);

    const battle_scene_snapshot<12> before_input =
            state;
    assert(controller.move_cursor(1, 0).error ==
            battle_scene_control_error::invalid_phase);
    assert(controller.cycle_unit(1).error ==
            battle_scene_control_error::invalid_phase);
    assert(controller.cancel().error ==
            battle_scene_control_error::invalid_phase);
    assert(controller.tick().error ==
            battle_scene_control_error::invalid_phase);
    state = controller.snapshot();
    assert(state.round == before_input.round);
    assert(state.current_side ==
            before_input.current_side);
    assert(state.units == before_input.units);

    for(int page = 0; page < 4; ++page)
    {
        assert(controller.confirm().success());
        assert(controller.snapshot().phase ==
                battle_scene_phase::script_blocked);
    }
    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(state.phase ==
            battle_scene_phase::unit_selection);
    assert(state.round == 1);
    assert(state.current_side == battle_side::player);
    assert(state.units == before_input.units);

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
            battle_scene_phase::move_selection);

    battle_scene_controller<12, 15, 15>
            relationship_controller;
    assert(relationship_controller.load(
                   battle_scenario_definitions[1],
                   battle_map_definitions[1],
                   battle_map_cells,
                   0,
                   policy,
                   battle_condition_variants[1][0],
                   0x01U,
                   {},
                   true)
                   .success());
    assert(relationship_controller.start().success());
    assert(relationship_controller.snapshot().phase !=
            battle_scene_phase::error);

    battle_scenario_load_policy object_policy;
    object_policy.preserve_empty_unit_slots = true;
    object_policy.character_equipped_tools[1][0] = 67;
    battle_scene_controller<12, 9, 22> object_controller;
    assert(object_controller.load(
                   battle_scenario_definitions[41],
                   battle_map_definitions[41],
                   battle_map_cells,
                   0,
                   object_policy,
                   battle_condition_variants[41][0],
                   0x41U,
                   {},
                   true)
                   .success());
    assert(object_controller.start().success());
    for(int page = 0; page < 5; ++page)
    {
        assert(object_controller.confirm().success());
    }
    assert(object_controller.snapshot().phase ==
           battle_scene_phase::unit_selection);
    assert(object_controller.confirm().success());
    assert(object_controller.confirm().success());
    assert(object_controller.confirm().success());
    for(int index = 0;
            index < 19 &&
            (object_controller.snapshot().player
                             .selected_action_kind !=
                     battle_action_source_kind::ninja_tool ||
             object_controller.snapshot().player
                             .selected_action_id != 67);
            ++index)
    {
        assert(object_controller.move_cursor(0, 1).success());
    }
    assert(object_controller.confirm().success());
    assert(object_controller.move_cursor(0, -1).success());
    assert(object_controller.confirm().success());
    const battle_scene_presentation_event placement =
            object_controller.take_presentation_event();
    assert(placement.valid);
    assert(placement.action_id == 67);
    assert(object_controller.object_snapshot().count == 1);
    assert(object_controller.confirm().success());
    assert(object_controller.confirm().success());

    bool observed_object_result = false;
    bool observed_object_presentation = false;
    for(int step = 0; step < 256 &&
            ! observed_object_presentation; ++step)
    {
        while(true)
        {
            const battle_scene_presentation_event event =
                    object_controller.take_presentation_event();
            if(! event.valid)
            {
                break;
            }
            if(event.has_battlefield_object)
            {
                observed_object_presentation = true;
                assert(event.action_id == 67);
                assert(event.battlefield_object_damage > 0);
            }
        }
        const battle_scene_snapshot<12> object_state =
                object_controller.snapshot();
        battle_scene_control_result advanced;
        if(object_state.phase ==
                battle_scene_phase::enemy_turn)
        {
            advanced = object_controller.tick();
            if(advanced.ai.turn.object_event_count > 0)
            {
                observed_object_result = true;
                assert(advanced.ai.turn.object_effects
                               .battlefield_object_slot == 1);
                assert(advanced.ai.turn.object_effects
                               .total_damage > 0);
            }
        }
        else if(object_state.phase ==
                        battle_scene_phase::script_blocked &&
                object_state.script.phase ==
                        battle_presentation_script_phase::
                                wait_for_input)
        {
            advanced = object_controller.confirm();
        }
        else if(object_state.phase ==
                        battle_scene_phase::script_blocked &&
                object_state.script.phase ==
                        battle_presentation_script_phase::
                                wait_frames)
        {
            advanced = object_controller.tick();
        }
        else
        {
            break;
        }
        assert(advanced.success());
    }
    assert(observed_object_result);
    assert(observed_object_presentation);
    assert(object_controller.object_snapshot().count == 0);
    return 0;
}
