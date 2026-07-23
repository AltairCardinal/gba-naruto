#include "konoha_bench/self_test.h"

#include "konoha_bench/action_state_machine.h"
#include "konoha_bench/battle_effects.h"
#include "konoha_bench/chapter_vm.h"
#include "konoha_bench/grid_pathfinder.h"
#include "konoha_bench/save_codec.h"

#include <array>

namespace konoha_bench
{

namespace
{
    bool state_machine_passes()
    {
        action_state_machine machine;
        return machine.step(action_input::select_unit).accepted &&
               machine.step(action_input::confirm_move).accepted &&
               machine.step(action_input::choose_action).accepted &&
               machine.step(action_input::confirm_target).accepted && machine.committed();
    }

    bool pathfinder_passes()
    {
        grid_map<3, 2> map;
        map.set_cost({ 1, 0 }, 0);
        const auto path = find_path<3, 2, 8>(map, { 0, 0 }, { 2, 0 }, 4);
        return path.found && path.total_cost == 4 && path.length == 5;
    }

    bool effects_pass()
    {
        unit_state source{ 10, 10, 4, 0, 0, 0, true };
        unit_state target{ 10, 10, 0, 1, 0, 0, true };
        const std::array effects = {
            effect{ effect_kind::spend_chakra, 2, 0 },
            effect{ effect_kind::damage, 3, 0 },
        };
        const auto result = apply_effect_chain(source, target, effects);
        return result.success() && source.chakra == 2 && target.hp == 7;
    }

    bool chapter_vm_passes()
    {
        const std::array<std::uint8_t, 3> program = { 1, 9, 255 };
        chapter_vm<3, 1> vm(program, program.size());
        return vm.run(2) == vm_status::emitted && vm.run(1) == vm_status::ended &&
               vm.event_count() == 1;
    }

    bool save_codec_passes()
    {
        const save_payload payload{ 2, 50, 3, 4 };
        const decode_result decoded = decode_slot(encode_slot(payload, 6));
        return decoded.valid() && decoded.payload == payload && decoded.generation == 6;
    }
}
self_test_result run_self_tests()
{
    std::uint8_t mask = 0;
    mask |= state_machine_passes() ? 1U << 0 : 0;
    mask |= pathfinder_passes() ? 1U << 1 : 0;
    mask |= effects_pass() ? 1U << 2 : 0;
    mask |= chapter_vm_passes() ? 1U << 3 : 0;
    mask |= save_codec_passes() ? 1U << 4 : 0;
    return { mask };
}

}
