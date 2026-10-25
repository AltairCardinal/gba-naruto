// Stream U2 (wave 10) -- battle-14 balance probe + key script.
//
// Base: V4's ``tools/s49_victory_capture/v4_route_gen.cpp`` (wave 9).  The
// harness (the key recorder, the cursor/path helpers, the campaign setup) is
// unchanged; U2 adds
//
//   * ``--dump``  : print the *measured* battle-14 numbers (unit stats, the
//                   action catalogue of every participant and the damage the
//                   remake's own formula produces against a bee) so the
//                   remake's balance can be compared with the original's;
//   * a route that picks its attack by **effective damage** (template power
//                   x hit count, after the original's defence factor) instead
//                   of by raw template power.
//
// Why a host program at all
// -------------------------
// The remake's battle input dispatch is *uniform* (battle_runtime_scene.cpp:
// A -> controller.confirm(), B -> controller.cancel(), the four arrows ->
// controller.move_cursor(), L/R -> controller.cycle_unit()), so every key
// press maps to exactly one controller call.  That makes it possible to
// compute the winning key script **offline**, against the very same
// controller the ROM runs, and then replay the keys on the ROM.
//
// Nothing in the remake tree is modified.

#include "konoha/battle_action_catalog.h"
#include "konoha/battle_action_system.h"
#include "konoha/battle_campaign_route.h"
#include "konoha/battle_campaign_scene_progression.h"
#include "konoha/battle_campaign_sram.h"
#include "konoha/battle_mission_rules.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/battle_scene_controller.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <array>
#include <cstdio>
#include <cstring>
#include <algorithm>
#include <string>
#include <vector>

using namespace konoha;

namespace
{

using controller_type = battle_scene_controller<12, 15, 19>;
using snapshot_type = battle_scene_snapshot<12>;

// --- the recorder ---------------------------------------------------------

struct KeyStep
{
    std::string key;       // "A" / "B" / "Left" / ... / "" (a pure wait)
    int settle = 90;       // frames to run after the key
    int hold = 4;          // frames the key is held down
    std::string note;
    // The scene phase the key was issued in (battle_scene_phase ordinal).
    //
    // The offline controller runs the same state machine the ROM runs, so
    // the phase is the natural key for a **closed loop** driver: the driver
    // waits until the ROM is in this phase and only then presses the key.
    // An open loop replay (key after key, with fixed frame budgets) goes out
    // of step on the very first presentation and never recovers.
    int phase = -1;
};

// --- the waits ------------------------------------------------------------
// The ROM is slower than the offline controller: every presentation and
// every animation phase has to be waited out on the machine, so the waits
// are deliberately generous (a short wait makes the ROM run ahead of the
// script and the input is dropped).
static constexpr int settle_confirm = 240;
static constexpr int settle_cancel = 120;
static constexpr int settle_move = 60;
static constexpr int settle_tick_enemy = 45;
static constexpr int settle_tick_script = 12;
static constexpr int settle_presentation = 2500;

struct Recorder
{
    controller_type inner;
    std::vector<KeyStep> steps;
    std::vector<std::string> events;
    bool recording = true;

    void emit(const std::string& key, int settle, int hold,
              const std::string& note, int phase = -1)
    {
        if(! recording)
        {
            return;
        }
        KeyStep step;
        step.key = key;
        step.settle = settle;
        step.hold = hold;
        step.note = note;
        step.phase = phase;
        steps.push_back(step);
    }

    void note(const std::string& text)
    {
        if(recording)
        {
            events.push_back(text);
        }
    }

    void check(const battle_scene_control_result& result,
               const char* what)
    {
        if(! result.success())
        {
            std::fprintf(stderr,
                         "WARN %s failed: error=%d player=%d "
                         "action_rejection=%d phase=%d "
                         "ai_error=%d ai_turn=%d "
                         "ai_action=%d ai_kind=%d ai_action_id=%d\n",
                         what,
                         static_cast<int>(result.error),
                         static_cast<int>(result.player.error),
                         static_cast<int>(result.player.action_rejection),
                         static_cast<int>(inner.snapshot().phase),
                         static_cast<int>(result.ai.error),
                         static_cast<int>(result.ai.turn.error),
                         static_cast<int>(result.ai.plan.action),
                         static_cast<int>(result.ai.action_kind),
                         static_cast<int>(result.ai.action_id));
        }
    }

    // --- read-only facade ------------------------------------------------
    snapshot_type snapshot() const
    {
        return inner.snapshot();
    }

    const battle_result& result_snapshot() const
    {
        return inner.result_snapshot();
    }

    const std::array<character_progression_record, 3>&
    progression_roster() const
    {
        return inner.progression_roster();
    }

    bool presentation_pending() const
    {
        return inner.presentation_pending();
    }

    battle_scene_presentation_event take_presentation_event()
    {
        return inner.take_presentation_event();
    }

    // --- mutating facade (this is where the key is recorded) ------------
    battle_scene_control_result confirm()
    {
        const bool in_script =
            inner.snapshot().phase ==
            battle_scene_phase::script_blocked;
        const int phase_before =
                static_cast<int>(inner.snapshot().phase);
        const battle_scene_control_result result = inner.confirm();
        check(result, "confirm");
        
        // A script block waits for a *held* A: the typewriter has to finish
        // first, so the key is held long enough for that.
        emit("A", settle_confirm, in_script ? 120 : 4, "confirm",
             phase_before);
        return result;
    }

    battle_scene_control_result cancel()
    {
        const int phase_before =
                static_cast<int>(inner.snapshot().phase);
        const battle_scene_control_result result = inner.cancel();
        check(result, "cancel");
        
        emit("B", settle_cancel, 4, "cancel", phase_before);
        return result;
    }

    battle_scene_control_result move_cursor(int dx, int dy)
    {
        const int phase_before =
                static_cast<int>(inner.snapshot().phase);
        const battle_scene_control_result result =            inner.move_cursor(dx, dy);
        check(result, "move_cursor");
        
        std::string key;
        if(dx < 0)
        {
            key = "Left";
        }
        else if(dx > 0)
        {
            key = "Right";
        }
        else if(dy < 0)
        {
            key = "Up";
        }
        else
        {
            key = "Down";
        }
        emit(key, settle_move, 4, "move_cursor", phase_before);
        return result;
    }

    battle_scene_control_result cycle_unit(int delta)
    {
        const int phase_before =
                static_cast<int>(inner.snapshot().phase);
        const battle_scene_control_result result =            inner.cycle_unit(delta);
        check(result, "cycle_unit");
        
        emit(delta < 0 ? "L" : "R", settle_cancel, 4, "cycle_unit",
             phase_before);
        return result;
    }

    battle_scene_control_result tick()
    {
        const battle_scene_phase phase = inner.snapshot().phase;
        const battle_scene_control_result result = inner.tick();
        // The ROM ticks every 15 frames during the enemy turn, and once per
        // scene frame (2 GBA frames) inside a wait_frames script block.
        const int frames = phase == battle_scene_phase::enemy_turn ?
            settle_tick_enemy :
            settle_tick_script;
        emit("", frames, 0, "tick", static_cast<int>(phase));
        return result;
    }
};

// --- helpers (the tested route logic) -------------------------------------

const battle_scene_unit_view& unit(
        const snapshot_type& state,
        battle_unit_id id)
{
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(candidate.id == id)
        {
            return candidate;
        }
    }
    std::fprintf(stderr, "ERR unit %u not found\n",
                 static_cast<unsigned>(id));
    std::exit(3);
}

const battle_scene_unit_view* unit_at_cursor(
        const snapshot_type& state)
{
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(candidate.active &&
                candidate.position == state.cursor)
        {
            return &candidate;
        }
    }
    return nullptr;
}

const battle_scene_unit_view* active_unit(
        const snapshot_type& state,
        battle_unit_id id)
{
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(candidate.id == id && candidate.active)
        {
            return &candidate;
        }
    }
    return nullptr;
}

int distance(grid_point left, grid_point right)
{
    const int dx = left.x > right.x ?
            left.x - right.x :
            right.x - left.x;
    const int dy = left.y > right.y ?
            left.y - right.y :
            right.y - left.y;
    return dx + dy;
}

int active_enemy_count(const snapshot_type& state)
{
    int result = 0;
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(candidate.active &&
                candidate.side == battle_side::enemy)
        {
            ++result;
        }
    }
    return result;
}

const battle_scene_unit_view* weakest_enemy(
        const snapshot_type& state,
        const battle_scene_unit_view& actor,
        int action_range)
{
    const battle_scene_unit_view* result = nullptr;
    int best_hp = 0;
    int best_distance = 0;
    bool best_reachable = false;
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(! candidate.active ||
                candidate.side != battle_side::enemy)
        {
            continue;
        }
        const int candidate_distance =
            distance(actor.position, candidate.position);
        const bool candidate_reachable =
            candidate_distance <=
            actor.movement + action_range;
        if(result == nullptr ||
                (best_reachable && ! candidate_reachable) ||
                (best_reachable == candidate_reachable &&
                 (candidate.hp < best_hp ||
                  (candidate.hp == best_hp &&
                   candidate_distance < best_distance))))
        {
            result = &candidate;
            best_hp = candidate.hp;
            best_distance = candidate_distance;
            best_reachable = candidate_reachable;
        }
    }
    return result;
}

bool occupied(
        const snapshot_type& state,
        grid_point point,
        battle_unit_id actor)
{
    for(std::size_t index = 0;
            index < state.unit_count;
            ++index)
    {
        const battle_scene_unit_view& candidate =
                state.units[index];
        if(candidate.id != actor &&
                candidate.active &&
                candidate.position == point)
        {
            return true;
        }
    }
    return false;
}

bool player_can_enter(grid_point point)
{
    const battle_map_definition& map =
        battle_map_definitions[14];
    if(! map.contains(point.x, point.y))
    {
        return false;
    }
    return battle_map_cells[
                   map.cell_offset +
                   point.y * map.width +
                   point.x]
                   .terrain_class() == 0;
}

grid_point planned_move(
        const snapshot_type& state,
        const battle_scene_unit_view& actor,
        grid_point target,
        int target_distance)
{
    constexpr int width = 15;
    constexpr int height = 19;
    constexpr int cell_count = width * height;
    const auto point_index =
        [](grid_point point)
        {
            return point.y * width + point.x;
        };
    const auto index_point =
        [](int index)
        {
            return grid_point({
                index % width,
                index / width,
            });
        };

    std::array<int, cell_count> parents;
    std::array<int, cell_count> costs;
    std::array<int, cell_count> queue = {};
    parents.fill(-2);
    costs.fill(-1);
    const int start = point_index(actor.position);
    parents[static_cast<std::size_t>(start)] = -1;
    costs[static_cast<std::size_t>(start)] = 0;
    int queue_begin = 0;
    int queue_end = 0;
    queue[static_cast<std::size_t>(queue_end++)] = start;
    int found = -1;
    constexpr std::array<grid_point, 4> directions = {{
        { -1, 0 },
        { 0, -1 },
        { 1, 0 },
        { 0, 1 },
    }};

    while(queue_begin < queue_end)
    {
        const int current =
            queue[static_cast<std::size_t>(
                queue_begin++)];
        const grid_point point = index_point(current);
        if(distance(point, target) == target_distance)
        {
            found = current;
            break;
        }
        for(const grid_point direction : directions)
        {
            const grid_point next = {
                point.x + direction.x,
                point.y + direction.y,
            };
            if(! player_can_enter(next) ||
                    occupied(state, next, actor.id))
            {
                continue;
            }
            const int next_index = point_index(next);
            if(parents[static_cast<std::size_t>(
                       next_index)] != -2)
            {
                continue;
            }
            parents[static_cast<std::size_t>(next_index)] =
                current;
            costs[static_cast<std::size_t>(next_index)] =
                costs[static_cast<std::size_t>(current)] + 1;
            queue[static_cast<std::size_t>(queue_end++)] =
                next_index;
        }
    }

    if(found < 0)
    {
        return actor.position;
    }
    int selected = found;
    while(costs[static_cast<std::size_t>(selected)] >
            actor.movement)
    {
        selected =
            parents[static_cast<std::size_t>(selected)];
    }
    return index_point(selected);
}

grid_point find_attack_cell(
        const snapshot_type& state,
        const battle_scene_unit_view& actor,
        const grid_point enemy,
        int max_distance,
        int* out_distance,
        bool require_alignment = true)
{
    constexpr int width = 15;
    constexpr int height = 19;
    constexpr int cell_count = width * height;
    const auto point_index =
        [](grid_point point)
        {
            return point.y * width + point.x;
        };
    const auto index_point =
        [](int index)
        {
            return grid_point({
                index % width,
                index / width,
            });
        };
    std::array<int, cell_count> costs;
    std::array<int, cell_count> queue = {};
    costs.fill(-1);
    const int start = point_index(actor.position);
    costs[static_cast<std::size_t>(start)] = 0;
    int queue_begin = 0;
    int queue_end = 0;
    queue[static_cast<std::size_t>(queue_end++)] = start;
    constexpr std::array<grid_point, 4> directions = {{
        { -1, 0 },
        { 0, -1 },
        { 1, 0 },
        { 0, 1 },
    }};
    grid_point best = actor.position;
    int best_distance = 1 << 20;
    int best_cost = 1 << 20;
    bool found = false;
    while(queue_begin < queue_end)
    {
        const int current =
            queue[static_cast<std::size_t>(
                queue_begin++)];
        const grid_point point = index_point(current);
        const int cost = costs[static_cast<std::size_t>(current)];
        const int candidate_distance = distance(point, enemy);
        // The original's attack range is a straight line (the same row or
        // the same column), so only aligned cells can ever be a target.
        const bool aligned =
            ! require_alignment ||
            point.x == enemy.x || point.y == enemy.y;
        if(aligned && candidate_distance >= 1 &&
                candidate_distance <= max_distance &&
                (candidate_distance < best_distance ||
                 (candidate_distance == best_distance &&
                  cost < best_cost)))
        {
            found = true;
            best = point;
            best_distance = candidate_distance;
            best_cost = cost;
        }
        if(cost >= actor.movement)
        {
            continue;
        }
        for(const grid_point direction : directions)
        {
            const grid_point next = {
                point.x + direction.x,
                point.y + direction.y,
            };
            if(! player_can_enter(next) ||
                    occupied(state, next, actor.id))
            {
                continue;
            }
            const int next_index = point_index(next);
            if(costs[static_cast<std::size_t>(next_index)] != -1)
            {
                continue;
            }
            costs[static_cast<std::size_t>(next_index)] = cost + 1;
            queue[static_cast<std::size_t>(queue_end++)] = next_index;
        }
    }
    if(out_distance)
    {
        *out_distance = found ? best_distance : -1;
    }
    return best;
}

// The reachable cell that gets the actor closest to the enemy (used when
// no attack is possible this turn).
grid_point find_step_toward(
        const snapshot_type& state,
        const battle_scene_unit_view& actor,
        const grid_point enemy)
{
    constexpr int width = 15;
    constexpr int height = 19;
    constexpr int cell_count = width * height;
    const auto point_index =
        [](grid_point point)
        {
            return point.y * width + point.x;
        };
    const auto index_point =
        [](int index)
        {
            return grid_point({
                index % width,
                index / width,
            });
        };
    std::array<int, cell_count> costs;
    std::array<int, cell_count> queue = {};
    costs.fill(-1);
    const int start = point_index(actor.position);
    costs[static_cast<std::size_t>(start)] = 0;
    int queue_begin = 0;
    int queue_end = 0;
    queue[static_cast<std::size_t>(queue_end++)] = start;
    constexpr std::array<grid_point, 4> directions = {{
        { -1, 0 },
        { 0, -1 },
        { 1, 0 },
        { 0, 1 },
    }};
    grid_point best = actor.position;
    int best_distance = distance(actor.position, enemy);
    while(queue_begin < queue_end)
    {
        const int current =
            queue[static_cast<std::size_t>(
                queue_begin++)];
        const grid_point point = index_point(current);
        const int cost = costs[static_cast<std::size_t>(current)];
        const int candidate_distance = distance(point, enemy);
        if(candidate_distance < best_distance)
        {
            best_distance = candidate_distance;
            best = point;
        }
        if(cost >= actor.movement)
        {
            continue;
        }
        for(const grid_point direction : directions)
        {
            const grid_point next = {
                point.x + direction.x,
                point.y + direction.y,
            };
            if(! player_can_enter(next) ||
                    occupied(state, next, actor.id))
            {
                continue;
            }
            const int next_index = point_index(next);
            if(costs[static_cast<std::size_t>(next_index)] != -1)
            {
                continue;
            }
            costs[static_cast<std::size_t>(next_index)] = cost + 1;
            queue[static_cast<std::size_t>(queue_end++)] = next_index;
        }
    }
    return best;
}

void set_cursor(Recorder& controller, grid_point target)
{
    if(controller.snapshot().phase ==
            battle_scene_phase::move_selection)
    {
        constexpr int width = 15;
        constexpr int height = 19;
        constexpr int cell_count = width * height;
        const snapshot_type state = controller.snapshot();
        const auto point_index =
            [](grid_point point)
            {
                return point.y * width + point.x;
            };
        const auto index_point =
            [](int index)
            {
                return grid_point({
                    index % width,
                    index / width,
                });
            };
        std::array<int, cell_count> parents;
        std::array<int, cell_count> queue = {};
        parents.fill(-2);
        const int start = point_index(state.cursor);
        const int finish = point_index(target);
        parents[static_cast<std::size_t>(start)] = -1;
        int queue_begin = 0;
        int queue_end = 0;
        queue[static_cast<std::size_t>(queue_end++)] = start;
        constexpr std::array<grid_point, 4> directions = {{
            { -1, 0 },
            { 0, -1 },
            { 1, 0 },
            { 0, 1 },
        }};
        while(queue_begin < queue_end &&
                parents[static_cast<std::size_t>(
                            finish)] == -2)
        {
            const int current =
                queue[static_cast<std::size_t>(
                    queue_begin++)];
            const grid_point point = index_point(current);
            for(const grid_point direction : directions)
            {
                const grid_point next = {
                    point.x + direction.x,
                    point.y + direction.y,
                };
                if(! player_can_enter(next) ||
                        occupied(
                            state,
                            next,
                            state.selected_unit))
                {
                    continue;
                }
                const int next_index = point_index(next);
                if(parents[static_cast<std::size_t>(
                           next_index)] != -2)
                {
                    continue;
                }
                parents[static_cast<std::size_t>(
                    next_index)] = current;
                queue[static_cast<std::size_t>(
                    queue_end++)] = next_index;
            }
        }
        std::array<grid_point, cell_count> reverse_path;
        int path_size = 0;
        for(int current = finish;
                current != start;
                current = parents[static_cast<std::size_t>(
                    current)])
        {
            reverse_path[static_cast<std::size_t>(
                path_size++)] = index_point(current);
        }
        for(int index = path_size - 1; index >= 0; --index)
        {
            const grid_point current =
                controller.snapshot().cursor;
            const grid_point next =
                reverse_path[static_cast<std::size_t>(
                    index)];
            controller.move_cursor(
                next.x - current.x,
                next.y - current.y);
        }
        return;
    }

    while(controller.snapshot().cursor.x != target.x)
    {
        controller.move_cursor(
            controller.snapshot().cursor.x <
                            target.x ?
                1 :
                -1,
            0);
    }
    while(controller.snapshot().cursor.y != target.y)
    {
        controller.move_cursor(
            0,
            controller.snapshot().cursor.y <
                            target.y ?
                1 :
                -1);
    }
}

void drain_presentations(Recorder& controller)
{
    int drained = 0;
    while(controller.take_presentation_event().valid)
    {
        ++drained;
    }
    if(drained > 0)
    {
        // The ROM plays each drained presentation out before it accepts
        // input again; the controller's own duration is not exposed here, so
        // a generous wait is used.
        controller.emit("", settle_presentation * drained, 0, "presentation");
    }
}

void finish_scripts(Recorder& controller)
{
    for(int step = 0;
            step < 4096 &&
            controller.snapshot().phase ==
                    battle_scene_phase::script_blocked;
            ++step)
    {
        drain_presentations(controller);
        if(controller.snapshot().script.phase ==
                battle_presentation_script_phase::
                        wait_frames)
        {
            controller.tick();
        }
        else
        {
            controller.confirm();
        }
    }
}

void select_command(Recorder& controller, battle_command_type command)
{
    for(int step = 0;
            step < 10 &&
            controller.snapshot().player.selected_command !=
                    command;
            ++step)
    {
        controller.move_cursor(0, 1);
    }
    controller.confirm();
}

void finish_turn(Recorder& controller)
{
    drain_presentations(controller);
    finish_scripts(controller);
    if(controller.snapshot().phase ==
            battle_scene_phase::outcome)
    {
        return;
    }
    if(controller.snapshot().phase ==
            battle_scene_phase::end_confirmation)
    {
        controller.confirm();
    }
    if(controller.snapshot().phase ==
            battle_scene_phase::facing_selection)
    {
        controller.confirm();
    }
    if(controller.snapshot().phase ==
            battle_scene_phase::defense_decision)
    {
        controller.move_cursor(0, 1);
        controller.confirm();
    }
    finish_scripts(controller);
    for(int step = 0;
            step < 128 &&
            controller.snapshot().phase ==
                    battle_scene_phase::enemy_turn;
            ++step)
    {
        drain_presentations(controller);
        controller.tick();
        finish_scripts(controller);
    }
    drain_presentations(controller);
    finish_scripts(controller);
}

void move_actor(
        Recorder& controller,
        grid_point destination,
        int target_distance)
{
    const snapshot_type before = controller.snapshot();
    const battle_scene_unit_view* actor =
        unit_at_cursor(before);
    const grid_point selected = planned_move(
        before,
        *actor,
        destination,
        target_distance);
    controller.confirm();
    controller.confirm();
    set_cursor(controller, selected);
    controller.confirm();
}

// Walk the actor to an **already chosen** cell (the route computes the
// attack cell itself).
void move_to_cell(Recorder& controller, grid_point cell)
{
    std::fprintf(stderr,
                 "  move_to_cell: phase %d -> ",
                 static_cast<int>(controller.snapshot().phase));
    controller.confirm();
    std::fprintf(stderr,
                 "%d -> ",
                 static_cast<int>(controller.snapshot().phase));
    controller.confirm();
    std::fprintf(stderr,
                 "%d -> ",
                 static_cast<int>(controller.snapshot().phase));
    set_cursor(controller, cell);
    std::fprintf(stderr,
                 "%d -> ",
                 static_cast<int>(controller.snapshot().phase));
    controller.confirm();
    std::fprintf(stderr,
                 "%d\n",
                 static_cast<int>(controller.snapshot().phase));
}

bool select_active_action(
        Recorder& controller,
        ability_id action)
{
    select_command(controller, battle_command_type::ability);
    for(int step = 0; step < 24; ++step)
    {
        const snapshot_type snapshot = controller.snapshot();
        const battle_player_action_flow_snapshot& state =
            snapshot.player;
        const battle_action_menu_view& selected =
            state.action_entries[
                static_cast<std::size_t>(
                    state.action_index)];
        std::fprintf(stderr,
                     "  action menu[%d]: kind=%d id=%u selectable=%d "
                     "(target id=%u)\n",
                     static_cast<int>(state.action_index),
                     static_cast<int>(selected.kind),
                     static_cast<unsigned>(selected.action_id),
                     selected.selectable() ? 1 : 0,
                     static_cast<unsigned>(action));
        if(selected.kind ==
                    battle_action_source_kind::
                            active_action &&
                selected.action_id == action)
        {
            if(! selected.selectable())
            {
                controller.cancel();
                return false;
            }
            controller.confirm();
            if(controller.snapshot().phase ==
                    battle_scene_phase::
                            combination_decision)
            {
                controller.move_cursor(0, 1);
                controller.confirm();
            }
            return true;
        }
        controller.move_cursor(0, 1);
    }
    return false;
}

// Pick a **ninja tool** entry (the remake lists the tools with their own
// ids, not with the active action ids).
bool select_tool_action(
        Recorder& controller,
        ability_id tool)
{
    select_command(controller, battle_command_type::ability);
    for(int step = 0; step < 24; ++step)
    {
        const snapshot_type snapshot = controller.snapshot();
        const battle_player_action_flow_snapshot& state =
            snapshot.player;
        const battle_action_menu_view& selected =
            state.action_entries[
                static_cast<std::size_t>(
                    state.action_index)];
        std::fprintf(stderr,
                     "  tool menu[%d]: kind=%d id=%u selectable=%d "
                     "(target id=%u)\n",
                     static_cast<int>(state.action_index),
                     static_cast<int>(selected.kind),
                     static_cast<unsigned>(selected.action_id),
                     selected.selectable() ? 1 : 0,
                     static_cast<unsigned>(tool));
        if(selected.kind ==
                    battle_action_source_kind::
                            ninja_tool &&
                selected.action_id == tool)
        {
            if(! selected.selectable())
            {
                controller.cancel();
                return false;
            }
            controller.confirm();
            if(controller.snapshot().phase ==
                    battle_scene_phase::
                            combination_decision)
            {
                controller.move_cursor(0, 1);
                controller.confirm();
            }
            return true;
        }
        controller.move_cursor(0, 1);
    }
    return false;
}

// ---------------------------------------------------------------------------
// U2: the original ROM's damage / hit-rate formulas.
// ---------------------------------------------------------------------------

int integer_sqrt(int value)
{
    int root = 0;
    while((root + 1) * (root + 1) <= value)
    {
        ++root;
    }
    return root;
}

// The original ROM's damage formula (reverse line:
// notes/battle-damage-hit-bindings-20260723.json):
//   raw      = floor(power * attack / 10)
//   factor   = 100 - 5 * isqrt(defense)
//   per hit  = floor(raw * factor / 100)
//   preview  = per hit * hit count
int original_preview_damage(
        int power,
        int hit_count,
        int attack,
        int defense)
{
    const int raw = power * attack / 10;
    int factor = 100 - 5 * integer_sqrt(defense);
    if(factor < 0)
    {
        factor = 0;
    }
    const int per_hit = raw * factor / 100;
    return per_hit * hit_count;
}

// The original's per-hit success rate:
//   min(99, template + trunc((attacker agility - target agility) / 2))
int original_success_rate(
        int template_rate,
        int attacker_agility,
        int target_agility)
{
    int delta = attacker_agility - target_agility;
    const int half = delta < 0 ? -((-delta) / 2) : delta / 2;
    int rate = template_rate + half;
    if(rate > 99)
    {
        rate = 99;
    }
    if(rate < 0)
    {
        rate = 0;
    }
    return rate;
}

// Open the ability menu once and pick the **best selectable entry**: the one
// with the highest effective damage (template power x hit count, after the
// original's defence factor) that still reaches the target.
//
// V4 picked the action by a hardcoded list and a hardcoded order, so a
// consumed ninja tool (a tool is removed from its slot by its use) made the
// whole turn fail.  Here the menu itself is the source of truth.
bool select_best_action(
        Recorder& controller,
        int attacker_attack,
        int target_defense,
        int attack_distance)
{
    select_command(controller, battle_command_type::ability);
    if(controller.snapshot().phase != battle_scene_phase::action_selection)
    {
        return false;
    }
    const snapshot_type snapshot = controller.snapshot();
    const battle_player_action_flow_snapshot& state = snapshot.player;
    int best_index = -1;
    int best_damage = 0;
    for(int index = 0; index < state.action_count; ++index)
    {
        const battle_action_menu_view& entry =
                state.action_entries[static_cast<std::size_t>(index)];
        if(! entry.selectable())
        {
            continue;
        }
        if(entry.target_kind != target_policy_kind::opponent_unit)
        {
            continue;
        }
        const action_definition* definition = nullptr;
        if(entry.kind == battle_action_source_kind::active_action)
        {
            if(entry.action_id >= active_action_definitions.size())
            {
                continue;
            }
            definition = &active_action_definitions[entry.action_id];
        }
        else if(entry.kind == battle_action_source_kind::ninja_tool)
        {
            if(entry.action_id >= ninja_tool_action_definitions.size())
            {
                continue;
            }
            definition = &ninja_tool_action_definitions[entry.action_id];
        }
        if(definition == nullptr)
        {
            continue;
        }
        if(definition->range.maximum_distance() < attack_distance)
        {
            continue;
        }
        const int damage = original_preview_damage(
                definition->effect.potency,
                definition->effect.base_hit_count,
                attacker_attack,
                target_defense);
        if(damage > best_damage)
        {
            best_damage = damage;
            best_index = index;
        }
    }
    if(best_index < 0)
    {
        return false;
    }
    const int count = state.action_count;
    const int current = state.action_index;
    for(int index = 0; index < count; ++index)
    {
        const battle_action_menu_view& entry =
                state.action_entries[static_cast<std::size_t>(index)];
        std::fprintf(stderr,
                     "  best-menu[%d]: kind=%d id=%u selectable=%d "
                     "target_kind=%d\n",
                     index,
                     static_cast<int>(entry.kind),
                     static_cast<unsigned>(entry.action_id),
                     entry.selectable() ? 1 : 0,
                     static_cast<int>(entry.target_kind));
    }
    const int steps = (best_index - current + count) % count;
    for(int step = 0; step < steps; ++step)
    {
        controller.move_cursor(0, 1);
    }
    controller.confirm();
    if(controller.snapshot().phase ==
            battle_scene_phase::combination_decision)
    {
        controller.move_cursor(0, 1);
        controller.confirm();
    }
    return true;
}

void confirm_target(Recorder& controller, grid_point target)
{
    set_cursor(controller, target);
    const snapshot_type before = controller.snapshot();
    std::fprintf(stderr,
                 "  target selection: cursor (%d,%d) target (%d,%d) "
                 "actor (%d,%d) move_position (%d,%d)\n",
                 before.cursor.x,
                 before.cursor.y,
                 target.x,
                 target.y,
                 before.units[0].position.x,
                 before.units[0].position.y,
                 before.player.move_position.x,
                 before.player.move_position.y);
    controller.confirm();
    controller.confirm();
    controller.confirm();
}

void end_actor(Recorder& controller, grid_point destination)
{
    move_actor(controller, destination, 0);
    select_command(controller, battle_command_type::end_action);
    finish_turn(controller);
}

void replenish_actor(Recorder& controller, grid_point position)
{
    controller.confirm();
    select_command(controller, battle_command_type::replenish_chakra);
    controller.confirm();
    controller.confirm();
}

character_progression_record progression(
        std::uint8_t character_id,
        int level,
        int experience,
        int training_points)
{
    character_progression_record result = {
        character_id,
        level,
        experience,
        training_points,
        true,
    };
    initialize_character_action_progression(
        result,
        unit_definitions[character_id]);
    return result;
}

void load_controller(Recorder& recorder, bool record)
{
    battle_scenario_load_policy policy;
    policy.preserve_empty_unit_slots = true;
    battle_campaign_state campaign = empty_battle_campaign();
    // The same call main.cpp makes: chapter 49, the party policy of the
    // route, and the default progression (levels 5 / 4 / 5).
    if(! prepare_battle_campaign_stage(campaign).success())
    {
        std::fprintf(stderr, "ERR cannot prepare the campaign stage\n");
        std::exit(3);
    }
    battle_campaign_scene_progression progression_state;
    progression_state.begin(campaign);
    // The ROM hands the controller the campaign's inventory and the
    // campaign's equipment policy; without them the ninja tools (the
    // original's 鍗佸瓧鎵嬮噷鍓? are missing from the ability list.
    if(apply_battle_campaign_scene_policy(campaign, policy) !=
            battle_campaign_error::none)
    {
        std::fprintf(stderr, "ERR cannot apply the campaign policy\n");
        std::exit(3);
    }
    recorder.recording = record;
    recorder.inner.load(
        battle_scenario_definitions[14],
        battle_map_definitions[14],
        battle_map_cells,
        0,
        policy,
        battle_condition_variants[14][0],
        49U,
        progression_state.records(),
        true,
        battle_mission_rules_for(14, 0),
        campaign.inventory);
    recorder.inner.start();
    finish_scripts(recorder);
    recorder.inner.tick();
    drain_presentations(recorder);
    // The round banner waits for exactly one button press (the original
    // shows it between the opening dialogue and the first move).
    for(int step = 0;
            step < 8 &&
            recorder.snapshot().phase ==
                    battle_scene_phase::turn_banner;
            ++step)
    {
        recorder.confirm();
        finish_scripts(recorder);
    }
}

// ---------------------------------------------------------------------------
// U2: the measured battle-14 truth of the remake.
// ---------------------------------------------------------------------------


void dump_battle_14()
{
    battle_scenario_load_policy policy;
    policy.preserve_empty_unit_slots = true;
    battle_campaign_state campaign = empty_battle_campaign();
    if(! prepare_battle_campaign_stage(campaign).success())
    {
        std::fprintf(stderr, "ERR cannot prepare the campaign stage\n");
        std::exit(3);
    }
    battle_campaign_scene_progression progression_state;
    progression_state.begin(campaign);
    if(apply_battle_campaign_scene_policy(campaign, policy) !=
            battle_campaign_error::none)
    {
        std::fprintf(stderr, "ERR cannot apply the campaign policy\n");
        std::exit(3);
    }
    // The controller marks the mission rules' AI characters before the load
    // (battle_scene_controller.h:229-245); the escort (character 30) is an
    // *allied* AI unit in battle 14, and that flag is what makes the loader
    // honour the scenario's embedded level / ai config for it.
    const battle_mission_rules mission_rules = battle_mission_rules_for(14, 0);
    for(std::size_t index = 0;
            index < mission_rules.control.ai_unit_count &&
            index < mission_rules.control.ai_units.size();
            ++index)
    {
        policy.ai_characters[
                mission_rules.control.ai_units[index].character_id] = true;
    }
    battle_session<12> session;
    const battle_scenario_load_result loaded = load_battle_scenario(
        battle_scenario_definitions[14],
        0,
        policy,
        session,
        progression_state.records().data(),
        progression_state.records().size());
    if(loaded.error != battle_scenario_load_error::none)
    {
        std::fprintf(stderr,
                     "ERR cannot load the scenario (error=%d)\n",
                     static_cast<int>(loaded.error));
        std::exit(3);
    }

    std::printf("=== U2 dump: remake S49 battle-14 ===\n");
    std::printf(
        "id  char side lvl   hp/max  atk def agi mv  chakra ai  pos\n");
    const battle_unit_instance* bee = nullptr;
    for(std::size_t index = 0; index < session.unit_count(); ++index)
    {
        const battle_unit_instance* u = session.unit_at(index);
        if(! u)
        {
            continue;
        }
        std::printf(
            "%-3u %-4u %-4s %-3d  %3d/%-3d %3d %3d %3d %2d  %d/%-3d %-3u (%d,%d)\n",
            static_cast<unsigned>(u->id),
            static_cast<unsigned>(u->character_id),
            u->side == battle_side::player ? "ply" : "foe",
            u->level,
            u->hp,
            u->max_hp,
            u->attack,
            u->defense,
            u->agility,
            u->move_range,
            u->chakra,
            u->max_chakra,
            static_cast<unsigned>(u->ai_config_id),
            u->position.x,
            u->position.y);
        if(u->side == battle_side::enemy && ! bee)
        {
            bee = u;
        }
    }

    std::printf("\n=== U2 dump: action catalogue + measured damage ===\n");
    for(std::size_t index = 0; index < session.unit_count(); ++index)
    {
        const battle_unit_instance* u = session.unit_at(index);
        if(! u || u->side != battle_side::player)
        {
            continue;
        }
        std::printf(
            "\nunit %u (char %u, atk %d agi %d) tools:",
            static_cast<unsigned>(u->id),
            static_cast<unsigned>(u->character_id),
            u->attack,
            u->agility);
        for(const ninja_tool_id tool : u->equipped_tools)
        {
            if(tool != no_ninja_tool)
            {
                std::printf(" %u", static_cast<unsigned>(tool));
            }
        }
        std::printf("\n");
        const battle_action_catalog_result catalogue =
                battle_action_catalog::build(*u);
        for(std::size_t entry = 0; entry < catalogue.count; ++entry)
        {
            const battle_action_catalog_entry& item =
                    catalogue.entries[entry];
            const action_definition& action = item.action;
            const int power = action.effect.potency;
            const int hits = action.effect.base_hit_count;
            const int preview = bee ?
                    original_preview_damage(
                            power,
                            hits,
                            u->attack,
                            bee->defense) :
                    0;
            const int rate = bee ?
                    original_success_rate(
                            action.effect.success_rate_percent,
                            u->agility,
                            bee->agility) :
                    0;
            std::printf(
                "  [%2u] %-8s id=%-3u lvl=%u tool=%-3u code=%-3u "
                "power=%-3d hits=%-2d rate=%-3u range=%d "
                "preview=%-3d success=%d%% target=%d\n",
                static_cast<unsigned>(entry),
                item.kind ==
                        battle_action_source_kind::ninja_tool ?
                    "tool" :
                    "active",
                static_cast<unsigned>(item.action_id),
                static_cast<unsigned>(item.action_level),
                static_cast<unsigned>(item.tool_slot),
                static_cast<unsigned>(action.effect.code),
                power,
                hits,
                static_cast<unsigned>(action.effect.success_rate_percent),
                action.range.maximum_distance(),
                preview,
                rate,
                static_cast<int>(action.target.kind));
        }
    }
    std::printf("\n");
}

void print_json(const Recorder& recorder,
                const std::string& final_phase,
                int round,
                int enemies_left)
{
    std::printf("{\n");
    std::printf(" \"schema\":\"konoha.s49-remake-key-script.v1\",\n");
    std::printf(" \"final_phase\":\"%s\",\n", final_phase.c_str());
    std::printf(" \"round\":%d,\n", round);
    std::printf(" \"enemies_left\":%d,\n", enemies_left);
    std::printf(" \"steps\":[\n");
    for(std::size_t index = 0;
            index < recorder.steps.size();
            ++index)
    {
        const KeyStep& step = recorder.steps[index];
        std::printf(
            "  {\"key\":\"%s\",\"settle\":%d,\"hold\":%d,\"note\":\"%s\","
            "\"phase\":%d}%s\n",
            step.key.c_str(),
            step.settle,
            step.hold,
            step.note.c_str(),
            step.phase,
            index + 1 < recorder.steps.size() ? "," : "");
    }
    std::printf(" ],\n");
    std::printf(" \"events\":[\n");
    for(std::size_t index = 0;
            index < recorder.events.size();
            ++index)
    {
        std::printf(
            "  \"%s\"%s\n",
            recorder.events[index].c_str(),
            index + 1 < recorder.events.size() ? "," : "");
    }
    std::printf(" ]\n}\n");
}

}

int main(int argc, char** argv)
{
    for(int index = 1; index < argc; ++index)
    {
        if(std::strcmp(argv[index], "--dump") == 0)
        {
            dump_battle_14();
            return 0;
        }
    }
    Recorder recorder;
    load_controller(recorder, true);

    const snapshot_type initial = recorder.snapshot();
    std::fprintf(stderr,
                 "initial phase=%d round=%d units=%d\n",
                 static_cast<int>(initial.phase),
                 initial.round,
                 static_cast<int>(initial.unit_count));

    bool replenished_sasuke = false;
    bool used_fireball = false;
    int previous_enemy_count = 5;
    for(int turn = 0;
            turn < 120 &&
            recorder.snapshot().phase !=
                    battle_scene_phase::outcome;
            ++turn)
    {
        finish_scripts(recorder);
        const snapshot_type before = recorder.snapshot();
        if(before.phase == battle_scene_phase::turn_banner)
        {
            recorder.confirm();
            finish_scripts(recorder);
            continue;
        }
        if(before.phase == battle_scene_phase::enemy_turn)
        {
            recorder.tick();
            drain_presentations(recorder);
            continue;
        }
        if(before.phase == battle_scene_phase::defense_decision)
        {
            std::fprintf(stderr,
                         "  defense_decision turn %d: count %d index %d "
                         "kind %d err %d\n",
                         turn,
                         before.player.defense_action_count,
                         before.player.defense_action_index,
                         static_cast<int>(
                             before.player.selected_defense_kind),
                         static_cast<int>(
                             before.player.defense_confirmation_error));
            // The defense menu is a yes/no: the up/down keys toggle it.
            // Toggling it to "no" takes the hit without a defense action,
            // which is the only legal answer when the unit has no status
            // effect to prepare (every entry reports
            // defense_preparation_error::unsupported_category).
            recorder.move_cursor(0, 1);
            recorder.confirm();
            continue;
        }
        if(before.phase == battle_scene_phase::defense_selection)
        {
            std::fprintf(stderr,
                         "  defense_selection turn %d: count %d index %d "
                         "kind %d err %d\n",
                         turn,
                         before.player.defense_action_count,
                         before.player.defense_action_index,
                         static_cast<int>(
                             before.player.selected_defense_kind),
                         static_cast<int>(
                             before.player.defense_confirmation_error));
            // The default defense entry is not always confirmable, so the
            // menu is cycled until a confirmable defense action is selected.
            bool confirmable = false;
            for(int step = 0; step < 8; ++step)
            {
                if(recorder.snapshot().player.defense_confirmation_error ==
                        defense_preparation_error::none)
                {
                    confirmable = true;
                    break;
                }
                recorder.move_cursor(0, 1);
            }
            if(confirmable)
            {
                recorder.confirm();
            }
            else
            {
                // No defense action is available: back out and take the hit.
                recorder.cancel();
                recorder.move_cursor(0, 1);
                recorder.confirm();
            }
            continue;
        }
        if(before.phase != battle_scene_phase::unit_selection)
        {
            std::fprintf(stderr,
                         "ERR turn %d: phase %d is not unit_selection\n",
                         turn,
                         static_cast<int>(before.phase));
            break;
        }
        const battle_scene_unit_view* actor = unit_at_cursor(before);
        if(! actor)
        {
            std::fprintf(stderr,
                         "ERR turn %d: no unit at the cursor\n",
                         turn);
            break;
        }
        {
            const battle_scene_unit_view* trace_escort =
                active_unit(before, 4);
            std::fprintf(stderr,
                         "state turn %d round %d actor %u char %u at (%d,%d) "
                         "hp %d escort (%d,%d) hp %d\n",
                         turn,
                         before.round,
                         static_cast<unsigned>(actor->id),
                         static_cast<unsigned>(actor->character_id),
                         actor->position.x,
                         actor->position.y,
                         actor->hp,
                         trace_escort ? trace_escort->position.x : -1,
                         trace_escort ? trace_escort->position.y : -1,
                         trace_escort ? trace_escort->hp : -1);
        }
        if(actor->character_id == 2 &&
                actor->chakra < 2 &&
                ! replenished_sasuke)
        {
            replenish_actor(recorder, actor->position);
            replenished_sasuke = true;
            recorder.note("replenish-sasuke");
            continue;
        }
        // --- the route ----------------------------------------------------
        // U2: the attack is chosen by **effective damage**, not by the raw
        // template power.  V4 compared the template power (10 / 15 / 6) with
        // the original's *preview total* (27) -- two different units.  The
        // original's preview total is the per-hit defended damage times the
        // hit count, so the 十字手里剑 (power 6, **3 hits**, range 3) is the
        // strongest option at 27, not the 忍者组合拳 at 16.
        struct attack_option
        {
            battle_action_source_kind kind;
            ability_id id;
            int range;
            int power;
            int hits;
        };
        std::vector<attack_option> options;
        if(actor->character_id == 1)
        {
            options.push_back({battle_action_source_kind::active_action,
                               5, 1, 10, 1});
            options.push_back({battle_action_source_kind::ninja_tool,
                               1, 3, 6, 3});
            options.push_back({battle_action_source_kind::ninja_tool,
                               11, 3, 6, 3});
        }
        else if(actor->character_id == 2)
        {
            options.push_back({battle_action_source_kind::active_action,
                               5, 1, 10, 1});
            options.push_back({battle_action_source_kind::active_action,
                               16, 2, 15, 1});
        }
        else
        {
            options.push_back({battle_action_source_kind::active_action,
                               5, 1, 10, 1});
        }
        int reach = 0;
        for(const attack_option& option : options)
        {
            reach = option.range > reach ? option.range : reach;
        }
        const battle_scene_unit_view* escort = active_unit(before, 4);
        const battle_scene_unit_view* enemy = nullptr;
        grid_point attack_cell = actor->position;
        int attack_distance = -1;
        int best_escort_distance = 1 << 20;
        for(std::size_t index = 0;
                index < before.unit_count;
                ++index)
        {
            const battle_scene_unit_view& candidate =
                before.units[index];
            if(! candidate.active ||
                    candidate.side != battle_side::enemy)
            {
                continue;
            }
            int candidate_distance = -1;
            const grid_point cell = find_attack_cell(
                before,
                *actor,
                candidate.position,
                reach,
                &candidate_distance);
            if(candidate_distance < 0)
            {
                continue;
            }
            const int escort_distance = escort ?
                    distance(escort->position, candidate.position) :
                    0;
            if(escort_distance < best_escort_distance ||
                    (escort_distance == best_escort_distance &&
                     enemy != nullptr &&
                     candidate.hp < enemy->hp))
            {
                best_escort_distance = escort_distance;
                enemy = &candidate;
                attack_cell = cell;
                attack_distance = candidate_distance;
            }
        }
        if(! enemy)
        {
            // No bee in reach: hold the ground next to the escort.
            std::fprintf(stderr,
                         "  diag turn %d actor %u at (%d,%d) mv %d : "
                         "bees",
                         turn,
                         static_cast<unsigned>(actor->id),
                         actor->position.x,
                         actor->position.y,
                         actor->movement);
            for(std::size_t index = 0;
                    index < before.unit_count;
                    ++index)
            {
                const battle_scene_unit_view& candidate =
                        before.units[index];
                if(! candidate.active ||
                        candidate.side != battle_side::enemy)
                {
                    continue;
                }
                int candidate_distance = -1;
                (void) find_attack_cell(
                    before,
                    *actor,
                    candidate.position,
                    reach,
                    &candidate_distance);
                std::fprintf(stderr,
                             "  (%d,%d) hp %d d=%d",
                             candidate.position.x,
                             candidate.position.y,
                             candidate.hp,
                             candidate_distance);
            }
            std::fprintf(stderr, "\n");
            // U2: no bee is in reach, so *close the distance* to the nearest
            // bee instead of guarding the escort.  The bees' own AI runs at
            // the escort, so they come to the party anyway; a guard that
            // never attacks leaves the last bee alive forever (V4's route
            // lost exactly like that in round 5).
            const battle_scene_unit_view* nearest = nullptr;
            int nearest_distance = 1 << 20;
            for(std::size_t index = 0;
                    index < before.unit_count;
                    ++index)
            {
                const battle_scene_unit_view& candidate =
                        before.units[index];
                if(! candidate.active ||
                        candidate.side != battle_side::enemy)
                {
                    continue;
                }
                const int candidate_distance =
                        distance(actor->position, candidate.position);
                if(candidate_distance < nearest_distance)
                {
                    nearest_distance = candidate_distance;
                    nearest = &candidate;
                }
            }
            grid_point guard = actor->position;
            if(nearest)
            {
                guard = find_step_toward(
                    before,
                    *actor,
                    nearest->position);
            }
            end_actor(recorder, guard);
            continue;
        }
        const grid_point enemy_position = enemy->position;
        // U2: move to the cell ``find_attack_cell`` has already validated
        // (aligned with the target, at the right distance and inside the
        // movement range).  V4 routed through ``planned_move`` instead, which
        // searches for *any* cell at that Manhattan distance -- an
        // unaligned one -- and then walks back along the path until the
        // movement budget is spent, so the actor never ended up on the
        // attack line and every turn was given up.
        move_to_cell(recorder, attack_cell);
        const snapshot_type moved = recorder.snapshot();
        if(distance(moved.player.move_position, enemy_position) >
                attack_distance)
        {
            select_command(recorder, battle_command_type::end_action);
            finish_turn(recorder);
            continue;
        }
        // The options with the highest *effective* damage that still reach,
        // tried from the best one down: a ninja tool is consumed by its use,
        // so the next best option has to be tried when the tool is gone.
        const bool picked = select_best_action(
            recorder,
            actor->attack,
            enemy->defense,
            attack_distance);
        if(! picked)
        {
            std::fprintf(stderr,
                         "ERR turn %d: no option is selectable\n",
                         turn);
            break;
        }
        confirm_target(recorder, enemy_position);
        finish_turn(recorder);
        const int current_enemy_count =
            active_enemy_count(recorder.snapshot());
        const battle_scene_unit_view* escort_now =
            active_unit(recorder.snapshot(), 4);
        std::fprintf(stderr,
                     "turn %d actor %u char %u at (%d,%d) hp %d "
                     "enemy (%d,%d) hp %d escort hp %d enemies %d round %d\n",
                     turn,
                     static_cast<unsigned>(actor->id),
                     static_cast<unsigned>(actor->character_id),
                     actor->position.x,
                     actor->position.y,
                     actor->hp,
                     enemy_position.x,
                     enemy_position.y,
                     enemy->hp,
                     escort_now ? escort_now->hp : -1,
                     current_enemy_count,
                     recorder.snapshot().round);
        if(current_enemy_count > previous_enemy_count)
        {
            std::fprintf(stderr,
                         "ERR turn %d: enemies grew %d -> %d\n",
                         turn,
                         previous_enemy_count,
                         current_enemy_count);
        }
        previous_enemy_count = current_enemy_count;
    }

    const snapshot_type outcome = recorder.snapshot();
    std::fprintf(stderr,
                 "after the battle: phase=%d round=%d outcome=%d enemies=%d\n",
                 static_cast<int>(outcome.phase),
                 outcome.round,
                 static_cast<int>(outcome.outcome),
                 active_enemy_count(outcome));
    if(outcome.phase != battle_scene_phase::outcome)
    {
        std::fprintf(stderr, "ERR the battle was not won\n");
        print_json(recorder,
                   "not_outcome",
                   outcome.round,
                   active_enemy_count(outcome));
        return 1;
    }

    // --- the settlement chain ------------------------------------------
    // outcome -> result -> level_up (two pages per participant) ->
    // training (six pages) -> complete.
    recorder.note("settlement-start");
    recorder.confirm();
    recorder.note("result");
    recorder.confirm();
    recorder.note("level-up");
    for(int participant = 0; participant < 3; ++participant)
    {
        recorder.confirm();
        recorder.note("level-up-detail");
        recorder.confirm();
    }
    for(int page = 0; page < 6; ++page)
    {
        recorder.confirm();
        recorder.note("training-page");
    }
    const snapshot_type final_state = recorder.snapshot();
    std::fprintf(stderr,
                 "after the settlement: phase=%d\n",
                 static_cast<int>(final_state.phase));
    print_json(recorder,
               final_state.phase == battle_scene_phase::complete ?
                    "complete" :
                    "not_complete",
               final_state.round,
               active_enemy_count(final_state));
    return final_state.phase == battle_scene_phase::complete ? 0 : 1;
}
