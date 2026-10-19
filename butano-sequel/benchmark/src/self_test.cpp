#include "konoha_bench/self_test.h"

#include "konoha_bench/action_state_machine.h"
#include "konoha_bench/battle_domain.h"
#include "konoha_bench/chapter_vm.h"
#include "konoha_bench/grid_pathfinder.h"
#include "konoha_bench/save_codec.h"
#include "konoha/battle_content_catalog.h"

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

    bool battle_domain_passes()
    {
        battle_unit_instance source = {
            1,
            battle_side::player,
            battle_control::player,
            { 0, 0 },
            battle_facing::right,
            10,
            10,
            4,
            4,
            2,
            true,
            {},
        };
        source.attack = 20;
        const battle_unit_instance target = {
            2,
            battle_side::enemy,
            battle_control::ai,
            { 1, 0 },
            battle_facing::left,
            10,
            10,
            0,
            0,
            2,
            true,
            {},
        };
        action_definition action;
        action.id = 5;
        action.cost = {
            action_cost_kind::current_chakra,
            2,
            no_tool_slot,
        };
        action.effect = {
            0x01,
            0,
            3,
            1,
            100,
            0,
        };
        action.target = {
            target_policy_kind::opponent_unit,
            0,
        };
        action.range = { 1, 1 };
        const konoha::action_preview preview =
                battle_action_resolver::preview_units(
                        source,
                        &target,
                        nullptr,
                        true,
                        action,
                        target.position);
        return preview.legal() &&
                preview.scalar_cost == 2 &&
                preview.hit_count == 1 &&
                preview.total_damage > 0;
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

    bool battle_content_catalog_passes()
    {
        const konoha::battle_content_catalog_result result =
                konoha::validate_generated_battle_content_catalog();
        return result.success() &&
                result.scenario_count == 47 &&
                result.variant_count == 141 &&
                result.playable_variant_count == 85;
    }
}
self_test_result run_self_tests()
{
    std::uint8_t mask = 0;
    mask |= state_machine_passes() ? 1U << 0 : 0;
    mask |= pathfinder_passes() ? 1U << 1 : 0;
    mask |= battle_domain_passes() ? 1U << 2 : 0;
    mask |= chapter_vm_passes() ? 1U << 3 : 0;
    mask |= save_codec_passes() ? 1U << 4 : 0;
    mask |= battle_content_catalog_passes() ? 1U << 5 : 0;
    return { mask };
}

}
