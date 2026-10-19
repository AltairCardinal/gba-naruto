#include "konoha/battle_content_catalog.h"
#include "konoha/battle_runtime_grid.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstdio>

using namespace konoha;

namespace
{

[[noreturn]] void fail(
        const char* stage,
        int battle_id,
        int variant,
        int error)
{
    std::fprintf(
            stderr,
            "%s failed for battle %d variant %d: %d\n",
            stage,
            battle_id,
            variant,
            error);
    std::abort();
}

void require_success(
        const battle_scene_control_result& result,
        const char* stage,
        int battle_id,
        int variant)
{
    if(! result.success())
    {
        std::fprintf(
                stderr,
                "nested errors: ai=%d browser=%d planning=%d action=%d player=%d "
                "plan_action=%d ability=%u kind=%d tool=%u destination=(%d,%d) "
                "target=(%d,%d) target_unit=%u summon=%u score=%d "
                "turn_error=%d object_events=%d\n",
                static_cast<int>(result.ai.error),
                static_cast<int>(result.ai.browser_error),
                static_cast<int>(result.ai.planning_error),
                static_cast<int>(result.ai.action_rejection),
                static_cast<int>(result.player.error),
                static_cast<int>(result.ai.plan.action),
                result.ai.plan.ability,
                static_cast<int>(result.ai.plan.action_kind),
                result.ai.plan.tool_slot,
                result.ai.plan.destination.x,
                result.ai.plan.destination.y,
                result.ai.plan.target_position.x,
                result.ai.plan.target_position.y,
                result.ai.plan.target_unit,
                result.ai.plan.summon_unit,
                result.ai.plan.score,
                static_cast<int>(result.ai.turn.error),
                result.ai.turn.object_event_count);
        fail(
                stage,
                battle_id,
                variant,
                static_cast<int>(result.error));
    }
}

void drain_presentations(
        battle_runtime_controller& controller)
{
    while(controller.take_presentation_event().valid)
    {
    }
}

void drive_through_hundred_rounds(
        battle_runtime_controller& controller,
        int battle_id,
        int variant)
{
    constexpr int target_round = 101;
    constexpr int maximum_steps = 262144;
    for(int step = 0; step < maximum_steps; ++step)
    {
        drain_presentations(controller);
        const battle_scene_snapshot<
                battle_runtime_max_units> state =
                        controller.snapshot();
        if(state.round >= target_round ||
                state.phase == battle_scene_phase::complete)
        {
            return;
        }

        switch(state.phase)
        {
        case battle_scene_phase::script_blocked:
            if(state.script.phase ==
                    battle_presentation_script_phase::
                            wait_frames)
            {
                require_success(
                        controller.tick(),
                        "script tick",
                        battle_id,
                        variant);
            }
            else
            {
                require_success(
                        controller.confirm(),
                        "script confirm",
                        battle_id,
                        variant);
            }
            break;
        case battle_scene_phase::unit_selection:
            require_success(
                    controller.confirm(),
                    "unit confirm",
                    battle_id,
                    variant);
            break;
        case battle_scene_phase::move_selection:
            require_success(
                    controller.confirm(),
                    "move confirm",
                    battle_id,
                    variant);
            break;
        case battle_scene_phase::command_selection:
        {
            int cycles = 0;
            while(controller.snapshot().
                          player.selected_command !=
                    battle_command_type::end_action &&
                    cycles < 8)
            {
                require_success(
                        controller.move_cursor(0, 1),
                        "command cycle",
                        battle_id,
                        variant);
                ++cycles;
            }
            if(controller.snapshot().
                       player.selected_command !=
                    battle_command_type::end_action)
            {
                fail(
                        "end command unavailable",
                        battle_id,
                        variant,
                        cycles);
            }
            require_success(
                    controller.confirm(),
                    "end command confirm",
                    battle_id,
                    variant);
            break;
        }
        case battle_scene_phase::facing_selection:
            require_success(
                    controller.confirm(),
                    "facing confirm",
                    battle_id,
                    variant);
            break;
        case battle_scene_phase::defense_decision:
            require_success(
                    controller.confirm(),
                    "defense confirm",
                    battle_id,
                    variant);
            break;
        case battle_scene_phase::enemy_turn:
        {
            const battle_scene_snapshot<
                    battle_runtime_max_units> before =
                            controller.snapshot();
            const battle_scene_control_result tick =
                    controller.tick();
            if(! tick.success())
            {
                const battle_scene_unit_view* selected = nullptr;
                for(const battle_scene_unit_view& unit :
                        before.units)
                {
                    if(unit.id == before.selected_unit)
                    {
                        selected = &unit;
                        break;
                    }
                }
                std::fprintf(
                        stderr,
                        "enemy pre-state: round=%d selected=%u "
                        "character=%u active=%d completed=%d "
                        "position=(%d,%d) hp=%d chakra=%d\n",
                        before.round,
                        before.selected_unit,
                        selected ? selected->character_id : 0,
                        selected ? selected->active : 0,
                        selected ? selected->completed : 0,
                        selected ? selected->position.x : -1,
                        selected ? selected->position.y : -1,
                        selected ? selected->hp : -1,
                        selected ? selected->chakra : -1);
                for(const battle_scene_unit_view& unit :
                        before.units)
                {
                    if(unit.active &&
                            unit.side == battle_side::enemy &&
                            ! unit.completed)
                    {
                        std::fprintf(
                                stderr,
                                "enemy candidate: id=%u character=%u "
                                "position=(%d,%d) hp=%d chakra=%d "
                                "statuses=%u\n",
                                unit.id,
                                unit.character_id,
                                unit.position.x,
                                unit.position.y,
                                unit.hp,
                                unit.chakra,
                                unit.status_count);
                    }
                }
            }
            require_success(
                    tick,
                    "enemy tick",
                    battle_id,
                    variant);
            break;
        }
        case battle_scene_phase::outcome:
            require_success(
                    controller.confirm(),
                    "outcome confirm",
                    battle_id,
                    variant);
            break;
        case battle_scene_phase::result:
            require_success(
                    controller.confirm(),
                    "result confirm",
                    battle_id,
                    variant);
            break;
        case battle_scene_phase::level_up:
            require_success(
                    controller.confirm(),
                    "level-up confirm",
                    battle_id,
                    variant);
            break;
        case battle_scene_phase::training:
            require_success(
                    controller.cancel(),
                    "training finish",
                    battle_id,
                    variant);
            break;
        default:
            fail(
                    "unexpected phase",
                    battle_id,
                    variant,
                    static_cast<int>(state.phase));
        }
    }
    fail(
            "first round timeout",
            battle_id,
            variant,
            maximum_steps);
}

}

int main()
{
    battle_scenario_load_policy load_policy;
    load_policy.placeholder_characters = {
        1, 2, 3, 4, 5, 6,
    };
    load_policy.preserve_empty_unit_slots = true;

    int playable_variants = 0;
    int started_variants = 0;
    for(int battle_id = 0;
            battle_id <
                    static_cast<int>(
                            battle_scenario_definitions.size());
            ++battle_id)
    {
        for(int variant = 0; variant < 3; ++variant)
        {
            const battle_content_entry content =
                    generated_battle_content_entry(
                            battle_id, variant);
            assert(content.valid());
            if(content.kind ==
                    battle_content_entry_kind::empty)
            {
                continue;
            }
            ++playable_variants;

            battle_runtime_controller controller;
            const battle_scene_control_result loaded =
                    controller.load(
                            *content.scenario,
                            *content.map,
                            battle_map_cells,
                            static_cast<std::uint8_t>(
                                    variant),
                            load_policy,
                            *content.conditions,
                            static_cast<std::uint32_t>(
                                    0xB000U +
                                    battle_id * 3 +
                                    variant),
                            {},
                            true);
            if(! loaded.success())
            {
                fail(
                        "load",
                        battle_id,
                        variant,
                        static_cast<int>(loaded.error));
            }
            const battle_scene_control_result started =
                    controller.start();
            if(! started.success())
            {
                fail(
                        "start",
                        battle_id,
                        variant,
                        static_cast<int>(started.error));
            }

            const battle_scene_snapshot<
                    battle_runtime_max_units> state =
                            controller.snapshot();
            if(state.phase ==
                    battle_scene_phase::error)
            {
                fail(
                        "snapshot",
                        battle_id,
                        variant,
                        static_cast<int>(state.phase));
            }
            assert(state.round == 1);
            assert(state.current_side ==
                   battle_side::player);
            assert(state.unit_count ==
                   battle_runtime_max_units);
            assert(state.active_unit_count > 0);
            assert(state.selected_unit != no_battle_unit);
            drive_through_hundred_rounds(
                    controller,
                    battle_id,
                    variant);
            ++started_variants;
        }
    }

    assert(playable_variants == 85);
    assert(started_variants == playable_variants);
}
