#include "konoha/battle_presentation_script.h"
#include "konoha/generated_battle_presentation_content.h"

#include <cassert>

using namespace konoha;

namespace
{

void confirm_all_pages(
        battle_presentation_script& script,
        int expected_pages)
{
    int pages = 0;
    while(script.snapshot().phase ==
            battle_presentation_script_phase::
                    wait_for_input)
    {
        ++pages;
        assert(script.confirm());
    }
    assert(pages == expected_pages);
    assert(script.snapshot().phase ==
            battle_presentation_script_phase::complete);
}

}

int main()
{
    const battle_presentation_definition* battle_41 =
            battle_presentation_definition_for(41);
    assert(battle_41);
    assert(battle_41->case_count == 2);

    battle_presentation_selector selector;
    battle_presentation_selector_context context;
    context.round_index = 1;
    context.side = 0;
    battle_presentation_selector_result selected =
            selector.evaluate(*battle_41, context);
    assert(selected.success());
    assert(selected.count == 1);
    assert(selected.selectors[0] == 1);

    battle_presentation_script script;
    assert(script.begin(*battle_41, selected.selectors[0]));
    battle_presentation_script_snapshot state = script.snapshot();
    assert(state.phase ==
            battle_presentation_script_phase::wait_for_input);
    assert(state.selector == 1);
    assert(state.speaker == 30);
    assert(state.text_length == 36);
    assert(state.text_address == 0x0805B2C0U);
    assert(state.message_window_visible);
    assert(state.portraits[0].visible);
    assert(state.portraits[0].portrait_id == 1);
    assert(state.portraits[0].expression_id == 0);
    assert(! state.portraits[0].focused);
    assert(state.portraits[1].visible);
    assert(state.portraits[1].portrait_id == 30);
    assert(state.portraits[1].expression_id == 0);
    assert(state.portraits[1].focused);

    assert(script.confirm());
    state = script.snapshot();
    assert(state.phase ==
            battle_presentation_script_phase::wait_for_input);
    assert(state.speaker == 1);
    assert(state.text_address == 0x0805B2ECU);
    assert(state.portraits[0].visible);
    assert(state.portraits[0].portrait_id == 1);
    assert(state.portraits[0].expression_id == 2);
    assert(state.portraits[0].focused);
    assert(! state.portraits[1].focused);
    confirm_all_pages(script, 4);
    const battle_presentation_script_snapshot completed =
            script.snapshot();
    assert(! script.confirm());
    assert(script.snapshot() == completed);

    context.round_index = 2;
    selected = selector.evaluate(*battle_41, context);
    assert(selected.success());
    assert(selected.count == 1);
    assert(selected.selectors[0] == 2);
    assert(script.begin(*battle_41, selected.selectors[0]));
    confirm_all_pages(script, 2);

    context.round_index = 3;
    selected = selector.evaluate(*battle_41, context);
    assert(selected.success());
    assert(selected.count == 0);

    context.round_index = 1;
    context.side = 1;
    selected = selector.evaluate(*battle_41, context);
    assert(selected.success());
    assert(selected.count == 0);

    const battle_presentation_definition* battle_44 =
            battle_presentation_definition_for(44);
    assert(battle_44);
    context.side = 0;
    context.round_index = 4;
    selected = selector.evaluate(*battle_44, context);
    assert(selected.success());
    assert(selected.count == 1);
    assert(selected.selectors[0] == 4);
    assert(script.begin(*battle_44, selected.selectors[0]));
    assert(script.snapshot().phase ==
            battle_presentation_script_phase::wait_for_input);

    const battle_presentation_definition* battle_45 =
            battle_presentation_definition_for(45);
    assert(battle_45);
    for(int round = 1; round <= 3; ++round)
    {
        context.round_index = round;
        context.side = 0;
        selected = selector.evaluate(*battle_45, context);
        assert(selected.success());
        assert(selected.count == 1);
        assert(selected.selectors[0] == round);
        assert(script.begin(
                *battle_45,
                selected.selectors[0]));
        assert(script.snapshot().phase ==
               battle_presentation_script_phase::
                       wait_for_input);
    }
    context.round_index = 4;
    selected = selector.evaluate(*battle_45, context);
    assert(selected.success());
    assert(selected.count == 0);
    context.round_index = 2;
    context.side = 1;
    selected = selector.evaluate(*battle_45, context);
    assert(selected.success());
    assert(selected.count == 0);

    const battle_presentation_definition* battle_1 =
            battle_presentation_definition_for(1);
    assert(battle_1);
    assert(script.begin(*battle_1, 2));
    assert(script.snapshot().portraits[0].portrait_id == 25);
    assert(script.snapshot().portraits[1].portrait_id == 26);
    assert(script.confirm());
    assert(script.confirm());
    state = script.snapshot();
    assert(state.portraits[0].visible);
    assert(state.portraits[0].portrait_id == 1);
    assert(state.portraits[0].expression_id == 2);
    assert(state.portraits[0].focused);
    assert(! state.portraits[1].visible);

    const battle_presentation_definition* battle_2 =
            battle_presentation_definition_for(2);
    assert(battle_2);
    assert(script.begin(*battle_2, 1));
    assert(script.snapshot().portraits[0].focused);
    assert(script.confirm());
    assert(script.snapshot().portraits[1].focused);
    assert(! script.snapshot().portraits[0].focused);

    const battle_presentation_definition* battle_9 =
            battle_presentation_definition_for(9);
    assert(battle_9);
    assert(script.begin(*battle_9, 4));
    assert(script.confirm());
    assert(script.snapshot().phase ==
            battle_presentation_script_phase::wait_frames);
    assert(script.snapshot().remaining_frames == 30);
    assert(script.snapshot().portraits[0].motion_mode == 2);
    assert(script.snapshot().portraits[0].motion_parameter == 1);
    for(int frame = 0; frame < 30; ++frame)
    {
        assert(script.tick());
    }
    assert(script.snapshot().phase ==
            battle_presentation_script_phase::wait_for_input);
    assert(script.snapshot().portraits[0].motion_mode == 2);
    assert(script.confirm());
    assert(script.snapshot().portraits[0].portrait_id == 1);
    assert(script.snapshot().portraits[0].expression_id == 0);
    assert(script.snapshot().portraits[0].motion_mode == 3);
    assert(script.snapshot().portraits[0].motion_parameter == 1);

    context.round_index = 1;
    context.side = 0;
    battle_presentation_script_flags flags;
    context.flags = &flags;
    context.unit_count = 3;
    context.units[0] = {
        1, 0, 0, 0, true,
    };
    context.units[1] = {
        2, 0, 1, 0, true,
    };
    context.units[2] = {
        3, 0, 5, 5, true,
    };
    selected = selector.evaluate(*battle_1, context);
    assert(selected.success());
    assert(selected.count == 1);
    assert(selected.selectors[0] == 5);
    assert(flags.test(0));
    selected = selector.evaluate(*battle_1, context);
    assert(selected.success());
    assert(selected.count == 0);

    const battle_presentation_definition* battle_32 =
            battle_presentation_definition_for(32);
    assert(battle_32);
    context = {};
    selected = selector.evaluate(*battle_32, context);
    assert(selected.success());
    assert(selected.count == 4);
    assert(selected.selectors[0] == 0);
    assert(selected.selectors[1] == 1);
    assert(selected.selectors[2] == 2);
    assert(selected.selectors[3] == 3);
    assert(script.begin(*battle_32, 0));
    assert(script.snapshot().text_address ==
            0x0805A929U);

    for(int battle_id = 1; battle_id < 47; ++battle_id)
    {
        const battle_presentation_definition* definition =
                battle_presentation_definition_for(
                        battle_id);
        assert(definition);
        battle_presentation_script_flags
                complete_flags;
        battle_presentation_selector_context
                complete_context;
        complete_context.flags = &complete_flags;
        assert(selector.evaluate(
                           *definition,
                           complete_context)
                       .success());
    }

    return 0;
}
