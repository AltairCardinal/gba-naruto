#include "konoha_bench/action_state_machine.h"

#include <cassert>

using namespace konoha_bench;

int main()
{
    action_state_machine machine;
    assert(machine.phase() == action_phase::unit_select);
    assert(! machine.committed());

    const action_result invalid = machine.step(action_input::confirm_move);
    assert(! invalid.accepted);
    assert(invalid.from == action_phase::unit_select);
    assert(invalid.to == action_phase::unit_select);

    assert(machine.step(action_input::select_unit).accepted);
    assert(machine.phase() == action_phase::move_preview);
    assert(machine.step(action_input::cancel).accepted);
    assert(machine.phase() == action_phase::unit_select);

    assert(machine.step(action_input::select_unit).accepted);
    assert(machine.step(action_input::confirm_move).accepted);
    assert(machine.phase() == action_phase::action_menu);
    assert(machine.step(action_input::cancel).accepted);
    assert(machine.phase() == action_phase::move_preview);

    assert(machine.step(action_input::confirm_move).accepted);
    assert(machine.step(action_input::choose_action).accepted);
    assert(machine.phase() == action_phase::target_select);
    assert(machine.step(action_input::cancel).accepted);
    assert(machine.phase() == action_phase::action_menu);

    assert(machine.step(action_input::choose_action).accepted);
    assert(machine.step(action_input::confirm_target).accepted);
    assert(machine.phase() == action_phase::committed);
    assert(machine.committed());
    assert(! machine.step(action_input::cancel).accepted);
    assert(machine.phase() == action_phase::committed);

    action_state_machine end_turn_machine;
    assert(end_turn_machine.step(action_input::end_turn).accepted);
    assert(end_turn_machine.phase() == action_phase::turn_end);
    assert(! end_turn_machine.step(action_input::select_unit).accepted);
}
