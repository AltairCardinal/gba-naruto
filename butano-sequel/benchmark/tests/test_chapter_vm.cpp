#include "konoha_bench/chapter_vm.h"

#include <array>
#include <cassert>

using namespace konoha_bench;

int main()
{
    const std::array<std::uint8_t, 13> program = {
        1, 7,       // emit text 7
        2, 2,       // set flag 2
        3, 2, 9,    // if flag 2, jump to start battle
        1, 99,      // skipped text
        5, 3,       // start battle 3
        4,          // wait
        255,        // end
    };
    chapter_vm<13, 4> vm(program, program.size());
    assert(vm.run(10) == vm_status::emitted);
    assert(vm.event_count() == 1);
    assert((vm.event(0) == chapter_event{ event_kind::text, 7 }));

    assert(vm.run(10) == vm_status::battle);
    assert(vm.flag(2));
    assert(vm.event_count() == 2);
    assert((vm.event(1) == chapter_event{ event_kind::battle, 3 }));

    assert(vm.run(10) == vm_status::waiting);
    const std::size_t wait_pc = vm.pc();
    assert(vm.run(10) == vm_status::waiting);
    assert(vm.pc() == wait_pc);
    assert(vm.resume());
    assert(! vm.resume());
    assert(vm.run(10) == vm_status::ended);

    const std::array<std::uint8_t, 1> invalid_opcode = { 77 };
    chapter_vm<1, 1> invalid_vm(invalid_opcode, 1);
    assert(invalid_vm.run(1) == vm_status::error);
    assert(invalid_vm.error() == vm_error::invalid_opcode);

    const std::array<std::uint8_t, 1> truncated = { 1 };
    chapter_vm<1, 1> truncated_vm(truncated, 1);
    assert(truncated_vm.run(1) == vm_status::error);
    assert(truncated_vm.error() == vm_error::truncated_operand);

    const std::array<std::uint8_t, 7> bad_jump = { 2, 1, 3, 1, 9, 255, 255 };
    chapter_vm<7, 1> bad_jump_vm(bad_jump, 6);
    assert(bad_jump_vm.run(3) == vm_status::error);
    assert(bad_jump_vm.error() == vm_error::jump_out_of_range);

    const std::array<std::uint8_t, 2> missing_end = { 2, 1 };
    chapter_vm<2, 1> missing_end_vm(missing_end, 2);
    assert(missing_end_vm.run(3) == vm_status::error);
    assert(missing_end_vm.error() == vm_error::missing_end);

    const std::array<std::uint8_t, 5> loop = { 2, 1, 3, 1, 0 };
    chapter_vm<5, 1> loop_vm(loop, 5);
    assert(loop_vm.run(4) == vm_status::error);
    assert(loop_vm.error() == vm_error::step_budget_exhausted);

    const std::array<std::uint8_t, 5> too_many_events = { 1, 1, 1, 2, 255 };
    chapter_vm<5, 1> overflow_vm(too_many_events, 5);
    assert(overflow_vm.run(2) == vm_status::emitted);
    assert(overflow_vm.run(2) == vm_status::error);
    assert(overflow_vm.error() == vm_error::event_overflow);
}
