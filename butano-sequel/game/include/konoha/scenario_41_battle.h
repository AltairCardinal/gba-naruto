#ifndef KONOHA_SCENARIO_41_BATTLE_H
#define KONOHA_SCENARIO_41_BATTLE_H

#include "konoha/battle_effects.h"
#include "konoha/battle_ai.h"
#include "konoha/generated_battle_unit_content.h"
#include "konoha/grid_pathfinder.h"
#include "konoha/scenario_41_definition.h"

#include <array>

namespace konoha
{

enum class unit_id
{
    naruto,
    konoha_maru,
};

enum class team
{
    player,
    enemy,
};

struct battle_unit
{
    unit_id id;
    team side;
    grid_point position;
    int hp;
    int max_hp;
    int move_range;
    bool active;

    constexpr bool operator==(const battle_unit&) const = default;
};

enum class battle_phase
{
    prebattle_menu,
    prebattle_confirmation,
    intro,
    unit_select,
    move_select,
    action_menu,
    end_confirmation,
    facing_select,
    defense_confirmation,
    technique_menu,
    target_select,
    attack_confirmation,
    enemy_turn,
    tutorial_dialogue,
    combat_animation,
    combat_dialogue,
    combat_popup,
    victory,
    result,
    level_up,
    postbattle_dialogue,
    postbattle,
};

enum class command_kind
{
    move_cursor,
    confirm,
    cancel,
    wait,
    tick,
    cycle_previous_unit,
    cycle_next_unit,
};

struct battle_command
{
    command_kind kind;
    int dx = 0;
    int dy = 0;
};

enum class battle_event
{
    none,
    invalid,
    prebattle_confirmation_opened,
    prebattle_cancelled,
    intro_opened,
    intro_advanced,
    intro_dismissed,
    cursor_moved,
    unit_selected,
    move_previewed,
    technique_menu_opened,
    technique_selected,
    end_confirmation_opened,
    facing_opened,
    defense_opened,
    attack_confirmation_opened,
    combat_animation_started,
    combat_animation_advanced,
    combat_dialogue_opened,
    combat_popup_opened,
    waited,
    tutorial_opened,
    dialogue_advanced,
    player_turn_started,
    victory_shown,
    result_shown,
    level_up_shown,
    postbattle_dialogue_opened,
    postbattle_opened,
};

struct battle_snapshot
{
    battle_phase phase;
    int turn;
    grid_point cursor;
    grid_point committed_player_position;
    grid_point preview_player_position;
    battle_unit naruto;
    battle_unit konoha_maru;
    int menu_index;
    int confirmation_index;
    int facing_direction;
    int dialogue_page;
    int animation_frame;
    battle_event last_event;
    bool victory;
    int mission_exp;
    int battle_exp;
    int bonus_exp;
    int total_exp;
    int naruto_level;
    int hp_growth;
    presentation_cue presentation;
    presentation_mode presentation_mode_value;
    int presentation_remaining_frames;
    bool presentation_visible;
    battle_outcome pending_outcome;

    constexpr bool operator==(const battle_snapshot&) const = default;
};

struct reachable_grid_points
{
    std::array<grid_point, 24> points = {};
    std::size_t count = 0;
};

class scenario_41_battle
{
public:
    scenario_41_battle()
    {
        const battle_unit_instance player = instantiate_unit(unit_definitions[1],
            scenario_41_naruto_unit,
            battle_side::player,
            battle_control::player,
            { 4, 10 },
            battle_facing::up);
        const battle_unit_instance enemy = instantiate_unit(unit_definitions[30],
            scenario_41_konoha_maru_unit,
            battle_side::enemy,
            battle_control::ai,
            { 4, 4 },
            battle_facing::down);
        const bool added_player = _session.add_unit(player);
        const bool added_enemy = _session.add_unit(enemy);
        if(! added_player || ! added_enemy)
        {
            _state.last_event = battle_event::invalid;
        }
    }

    [[nodiscard]] constexpr battle_snapshot snapshot() const
    {
        return _state;
    }

    [[nodiscard]] bool reachable(grid_point destination) const
    {
        grid_map<9, 22> map = _movement_map();
        const auto path = find_path<9, 22, 64>(
                map, _state.committed_player_position, destination, _state.naruto.move_range);
        return path.found;
    }

    [[nodiscard]] reachable_grid_points reachable_points() const
    {
        reachable_grid_points result;
        for(int dy = -_state.naruto.move_range; dy <= _state.naruto.move_range; ++dy)
        {
            for(int dx = -_state.naruto.move_range; dx <= _state.naruto.move_range; ++dx)
            {
                const int absolute_dx = dx < 0 ? -dx : dx;
                const int absolute_dy = dy < 0 ? -dy : dy;
                if(absolute_dx + absolute_dy == 0 ||
                        absolute_dx + absolute_dy > _state.naruto.move_range)
                {
                    continue;
                }
                const grid_point point = {
                    _state.committed_player_position.x + dx,
                    _state.committed_player_position.y + dy,
                };
                if(point.x >= 0 && point.x < 9 && point.y >= 0 && point.y < 22 && reachable(point))
                {
                    result.points[result.count] = point;
                    ++result.count;
                }
            }
        }
        return result;
    }

    battle_event dispatch(battle_command command)
    {
        if(_state.phase == battle_phase::intro)
        {
            if(command.kind == command_kind::confirm)
            {
                return _advance_entrance_confirm();
            }
            if(command.kind == command_kind::tick)
            {
                return _advance_entrance_tick();
            }
            return battle_event::invalid;
        }

        if(command.kind == command_kind::move_cursor)
        {
            return _move_cursor(command);
        }

        if(command.kind == command_kind::cycle_previous_unit ||
                command.kind == command_kind::cycle_next_unit)
        {
            return _cycle_unit(command.kind == command_kind::cycle_next_unit ? 1 : -1);
        }

        if(command.kind == command_kind::confirm)
        {
            return _confirm();
        }

        if(command.kind == command_kind::cancel)
        {
            return _cancel();
        }

        if(command.kind == command_kind::tick)
        {
            if(_state.phase == battle_phase::enemy_turn)
            {
                return _run_enemy_turn();
            }
            if(_state.phase == battle_phase::combat_animation)
            {
                if(_state.animation_frame < 263)
                {
                    ++_state.animation_frame;
                    return _emit(battle_event::combat_animation_advanced);
                }
                _state.phase = battle_phase::combat_dialogue;
                return _emit(battle_event::combat_dialogue_opened);
            }
        }

        // The original controller does not expose START as a global quick-wait command.
        return battle_event::invalid;
    }

private:
    battle_event _cycle_unit(int direction)
    {
        if(_state.phase != battle_phase::unit_select)
        {
            return battle_event::invalid;
        }
        const battle_unit_instance* selected =
                _session.cycle_available_unit(scenario_41_naruto_unit, direction);
        if(! selected)
        {
            return battle_event::invalid;
        }
        _state.cursor = selected->position;
        return _emit(battle_event::cursor_moved);
    }

    battle_event _open_entrance()
    {
        _entrance = {};
        if(! load_scenario_41_entrance(_entrance))
        {
            return battle_event::invalid;
        }
        _state.phase = battle_phase::intro;
        _sync_presentation();
        return _emit(battle_event::intro_opened);
    }

    battle_event _advance_entrance_tick()
    {
        if(! _entrance.tick())
        {
            return battle_event::invalid;
        }
        return _finish_or_sync_entrance();
    }

    battle_event _advance_entrance_confirm()
    {
        if(! _entrance.confirm())
        {
            return battle_event::invalid;
        }
        return _finish_or_sync_entrance();
    }

    battle_event _finish_or_sync_entrance()
    {
        if(_entrance.empty())
        {
            _sync_presentation();
            if(_session.start_round() != battle_transition::unit_selection_opened)
            {
                return _emit(battle_event::invalid);
            }
            _state.phase = battle_phase::unit_select;
            _state.cursor = _state.naruto.position;
            return _emit(battle_event::intro_dismissed);
        }
        _sync_presentation();
        return _emit(battle_event::intro_advanced);
    }

    void _sync_presentation()
    {
        if(const presentation_step* step = _entrance.current())
        {
            _state.presentation = step->cue;
            _state.presentation_mode_value = step->mode;
            _state.presentation_remaining_frames = step->remaining_frames;
            _state.presentation_visible = step->visible;
            return;
        }
        _state.presentation = presentation_cue::none;
        _state.presentation_mode_value = presentation_mode::automatic;
        _state.presentation_remaining_frames = 0;
        _state.presentation_visible = false;
    }

    battle_event _move_cursor(battle_command command)
    {
        if((command.dx == 0) == (command.dy == 0) ||
                command.dx < -1 || command.dx > 1 || command.dy < -1 || command.dy > 1)
        {
            return battle_event::invalid;
        }
        if(_state.phase == battle_phase::action_menu)
        {
            if(command.dx != 0)
            {
                return battle_event::invalid;
            }
            _state.menu_index = _state.menu_index == 0 ? 1 : 0;
            return _emit(battle_event::cursor_moved);
        }
        if(_state.phase == battle_phase::prebattle_menu)
        {
            if(command.dx != 0)
            {
                return battle_event::invalid;
            }
            _state.menu_index += command.dy;
            if(_state.menu_index < 0)
            {
                _state.menu_index = 3;
            }
            else if(_state.menu_index > 3)
            {
                _state.menu_index = 0;
            }
            return _emit(battle_event::cursor_moved);
        }
        if(_state.phase == battle_phase::prebattle_confirmation ||
                _state.phase == battle_phase::end_confirmation ||
                _state.phase == battle_phase::defense_confirmation)
        {
            if(command.dx != 0)
            {
                return battle_event::invalid;
            }
            _state.confirmation_index = _state.confirmation_index == 0 ? 1 : 0;
            return _emit(battle_event::cursor_moved);
        }
        if(_state.phase == battle_phase::facing_select)
        {
            if(command.dx == 1)
            {
                _state.facing_direction = 1;
            }
            else if(command.dy == 1)
            {
                _state.facing_direction = 2;
            }
            else if(command.dx == -1)
            {
                _state.facing_direction = 3;
            }
            else
            {
                _state.facing_direction = 0;
            }
            return _emit(battle_event::cursor_moved);
        }
        if(! _cursor_phase())
        {
            return battle_event::invalid;
        }
        const grid_point next = { _state.cursor.x + command.dx, _state.cursor.y + command.dy };
        if(next.x < 0 || next.x >= 9 || next.y < 0 || next.y >= 22)
        {
            return battle_event::invalid;
        }
        _state.cursor = next;
        return _emit(battle_event::cursor_moved);
    }

    battle_event _confirm()
    {
        switch(_state.phase)
        {
        case battle_phase::prebattle_menu:
            if(_state.menu_index == 2)
            {
                _state.phase = battle_phase::prebattle_confirmation;
                _state.confirmation_index = 0;
                return _emit(battle_event::prebattle_confirmation_opened);
            }
            break;
        case battle_phase::prebattle_confirmation:
            if(_state.confirmation_index == 0)
            {
                return _open_entrance();
            }
            _state.phase = battle_phase::prebattle_menu;
            return _emit(battle_event::prebattle_cancelled);
        case battle_phase::unit_select:
            if(_state.cursor == _state.naruto.position && _state.naruto.active)
            {
                if(_session.select_unit(scenario_41_naruto_unit) !=
                        battle_transition::action_draft_opened)
                {
                    return battle_event::invalid;
                }
                _state.phase = battle_phase::move_select;
                return _emit(battle_event::unit_selected);
            }
            break;
        case battle_phase::move_select:
            if(reachable(_state.cursor))
            {
                if(_session.preview_move(_state.cursor) != battle_transition::move_previewed)
                {
                    return battle_event::invalid;
                }
                _state.preview_player_position = _state.cursor;
                _state.phase = battle_phase::action_menu;
                _state.menu_index = 0;
                return _emit(battle_event::move_previewed);
            }
            break;
        case battle_phase::action_menu:
            if(_state.menu_index == 0)
            {
                _state.phase = battle_phase::technique_menu;
                return _emit(battle_event::technique_menu_opened);
            }
            _state.phase = battle_phase::end_confirmation;
            _state.confirmation_index = 0;
            return _emit(battle_event::end_confirmation_opened);
        case battle_phase::end_confirmation:
            if(_state.confirmation_index == 1)
            {
                _state.phase = battle_phase::facing_select;
                return _emit(battle_event::facing_opened);
            }
            _state.phase = battle_phase::action_menu;
            return _emit(battle_event::none);
        case battle_phase::facing_select:
            _state.phase = battle_phase::defense_confirmation;
            _state.confirmation_index = 0;
            return _emit(battle_event::defense_opened);
        case battle_phase::defense_confirmation:
            if(_session.commit_action(_selected_facing(), no_ability) ==
                    battle_transition::invalid)
            {
                return battle_event::invalid;
            }
            _sync_units_from_domain();
            _state.phase = battle_phase::enemy_turn;
            return _emit(battle_event::waited);
        case battle_phase::technique_menu:
            _state.phase = battle_phase::target_select;
            _state.cursor = _state.preview_player_position;
            return _emit(battle_event::technique_selected);
        case battle_phase::target_select:
            if(_state.konoha_maru.active &&
                    _state.cursor == _state.konoha_maru.position &&
                    _distance(_state.preview_player_position, _state.konoha_maru.position) == 1)
            {
                _state.phase = battle_phase::attack_confirmation;
                return _emit(battle_event::attack_confirmation_opened);
            }
            break;
        case battle_phase::attack_confirmation:
            return _combo();
        case battle_phase::combat_dialogue:
            _state.phase = battle_phase::combat_popup;
            return _emit(battle_event::combat_popup_opened);
        case battle_phase::combat_popup:
            if(_state.pending_outcome != battle_outcome::victory)
            {
                return battle_event::invalid;
            }
            _state.phase = battle_phase::victory;
            _state.victory = true;
            return _emit(battle_event::victory_shown);
        case battle_phase::tutorial_dialogue:
            if(_state.dialogue_page < 3)
            {
                ++_state.dialogue_page;
                return _emit(battle_event::dialogue_advanced);
            }
            _state.dialogue_page = 0;
            _state.phase = battle_phase::unit_select;
            _state.cursor = _state.naruto.position;
            return _emit(battle_event::player_turn_started);
        case battle_phase::victory:
            _state.phase = battle_phase::result;
            return _emit(battle_event::result_shown);
        case battle_phase::result:
            _state.phase = battle_phase::level_up;
            _state.naruto_level = 2;
            _state.dialogue_page = 0;
            return _emit(battle_event::level_up_shown);
        case battle_phase::level_up:
            if(_state.dialogue_page == 0)
            {
                _state.dialogue_page = 1;
                return _emit(battle_event::dialogue_advanced);
            }
            _state.phase = battle_phase::postbattle_dialogue;
            _state.dialogue_page = 0;
            return _emit(battle_event::postbattle_dialogue_opened);
        case battle_phase::postbattle_dialogue:
            if(_state.dialogue_page < 10)
            {
                ++_state.dialogue_page;
                return _emit(battle_event::dialogue_advanced);
            }
            _state.phase = battle_phase::postbattle;
            return _emit(battle_event::postbattle_opened);
        default:
            break;
        }
        return battle_event::invalid;
    }

    battle_event _cancel()
    {
        switch(_state.phase)
        {
        case battle_phase::prebattle_confirmation:
            _state.phase = battle_phase::prebattle_menu;
            return _emit(battle_event::prebattle_cancelled);
        case battle_phase::target_select:
            _state.phase = battle_phase::technique_menu;
            return _emit(battle_event::none);
        case battle_phase::technique_menu:
        case battle_phase::end_confirmation:
            _state.phase = battle_phase::action_menu;
            return _emit(battle_event::none);
        case battle_phase::action_menu:
            if(_session.preview_move(_state.committed_player_position) !=
                    battle_transition::move_previewed)
            {
                return battle_event::invalid;
            }
            _state.phase = battle_phase::move_select;
            _state.preview_player_position = _state.committed_player_position;
            return _emit(battle_event::none);
        case battle_phase::move_select:
            if(_session.cancel_action() != battle_transition::unit_selection_opened)
            {
                return battle_event::invalid;
            }
            _state.phase = battle_phase::unit_select;
            _state.cursor = _state.committed_player_position;
            return _emit(battle_event::none);
        default:
            return battle_event::invalid;
        }
    }

    [[nodiscard]] bool _cursor_phase() const
    {
        return _state.phase == battle_phase::unit_select ||
               _state.phase == battle_phase::move_select ||
               _state.phase == battle_phase::target_select;
    }

    [[nodiscard]] grid_map<9, 22> _movement_map() const
    {
        grid_map<9, 22> map;
        constexpr std::array obstacles = {
            grid_point{ 3, 9 }, grid_point{ 5, 9 }, grid_point{ 2, 7 },
            grid_point{ 6, 7 }, grid_point{ 1, 4 }, grid_point{ 7, 4 },
        };
        for(grid_point obstacle : obstacles)
        {
            map.set_cost(obstacle, 0);
        }
        map.set_occupied(_state.naruto.position, _state.naruto.active);
        map.set_occupied(_state.konoha_maru.position, _state.konoha_maru.active);
        return map;
    }

    [[nodiscard]] battle_facing _selected_facing() const
    {
        switch(_state.facing_direction)
        {
        case 1:
            return battle_facing::right;
        case 2:
            return battle_facing::down;
        case 3:
            return battle_facing::left;
        default:
            return battle_facing::up;
        }
    }

    void _sync_units_from_domain()
    {
        const battle_unit_instance* player = _session.unit(scenario_41_naruto_unit);
        const battle_unit_instance* enemy = _session.unit(scenario_41_konoha_maru_unit);
        if(player)
        {
            _state.naruto.position = player->position;
            _state.naruto.hp = player->hp;
            _state.naruto.active = player->active;
            _state.committed_player_position = player->position;
            _state.preview_player_position = player->position;
            _state.cursor = player->position;
        }
        if(enemy)
        {
            _state.konoha_maru.position = enemy->position;
            _state.konoha_maru.hp = enemy->hp;
            _state.konoha_maru.active = enemy->active;
        }
    }

    battle_event _combo()
    {
        const action_result result = battle_action_resolver::resolve_draft(
                _session,
                scenario_41_konoha_maru_unit,
                no_battle_unit,
                scenario_41_combo_action(),
                _state.konoha_maru.position,
                _facing_toward(
                        _state.preview_player_position, _state.konoha_maru.position),
                _rng);
        if(! result.success())
        {
            return battle_event::invalid;
        }
        _sync_units_from_domain();
        objective_context<2, 1> context;
        const battle_unit_instance* player = _session.unit(scenario_41_naruto_unit);
        const battle_unit_instance* enemy = _session.unit(scenario_41_konoha_maru_unit);
        if(! player || ! enemy || ! context.add_unit(*player) || ! context.add_unit(*enemy))
        {
            return battle_event::invalid;
        }
        const std::array objectives = { scenario_41_victory_objective() };
        const objective_result outcome = objective_engine::evaluate(
                context, battle_domain_event::effects_resolved, objectives);
        if(! outcome.success())
        {
            return battle_event::invalid;
        }
        _state.pending_outcome = outcome.outcome;
        _state.animation_frame = 0;
        _state.phase = battle_phase::combat_animation;
        return _emit(battle_event::combat_animation_started);
    }

    [[nodiscard]] static int _distance(grid_point first, grid_point second)
    {
        const int dx = first.x > second.x ? first.x - second.x : second.x - first.x;
        const int dy = first.y > second.y ? first.y - second.y : second.y - first.y;
        return dx + dy;
    }

    battle_event _run_enemy_turn()
    {
        if(_session.select_unit(scenario_41_konoha_maru_unit) !=
                battle_transition::action_draft_opened)
        {
            return battle_event::invalid;
        }
        const battle_unit_instance* enemy = _session.unit(scenario_41_konoha_maru_unit);
        const battle_unit_instance* player = _session.unit(scenario_41_naruto_unit);
        if(! enemy || ! player)
        {
            return battle_event::invalid;
        }
        const std::array roster = { *player, *enemy };
        const ai_objective objective = {
            true,
            player->position,
            scenario_41_naruto_unit,
            no_battle_unit,
        };
        const action_definition_set<15> enemy_actions = scenario_41_enemy_actions();
        if(! enemy_actions.valid || enemy_actions.count == 0)
        {
            return battle_event::invalid;
        }
        const ai_plan plan = battle_ai::plan(
                _movement_map(),
                *enemy,
                roster,
                enemy_actions.values,
                enemy_actions.count,
                objective,
                _rng);
        if(plan.error != ai_error::none)
        {
            return battle_event::invalid;
        }
        if(plan.destination != enemy->position &&
                _session.preview_move(plan.destination) != battle_transition::move_previewed)
        {
            return battle_event::invalid;
        }
        const battle_facing facing = _facing_toward(plan.destination, player->position);
        if(plan.action == ai_action::ability)
        {
            const action_definition* selected_action = nullptr;
            for(std::size_t index = 0; index < enemy_actions.count; ++index)
            {
                if(enemy_actions.values[index].id == plan.ability)
                {
                    selected_action = &enemy_actions.values[index];
                    break;
                }
            }
            if(! selected_action)
            {
                return battle_event::invalid;
            }
            const action_result result = battle_action_resolver::resolve_draft(
                    _session,
                    scenario_41_naruto_unit,
                    no_battle_unit,
                    *selected_action,
                    player->position,
                    facing,
                    _rng);
            if(! result.success())
            {
                return battle_event::invalid;
            }
        }
        else if(_session.commit_action(facing, no_ability) == battle_transition::invalid)
        {
            return battle_event::invalid;
        }
        _sync_units_from_domain();
        _state.turn = _session.round_index();
        if(_state.turn == 2)
        {
            _state.phase = battle_phase::tutorial_dialogue;
            _state.dialogue_page = 0;
            return _emit(battle_event::tutorial_opened);
        }
        _state.phase = battle_phase::unit_select;
        return _emit(battle_event::player_turn_started);
    }

    [[nodiscard]] static battle_facing _facing_toward(grid_point from, grid_point to)
    {
        const int dx = to.x - from.x;
        const int dy = to.y - from.y;
        const int absolute_dx = dx < 0 ? -dx : dx;
        const int absolute_dy = dy < 0 ? -dy : dy;
        if(absolute_dx > absolute_dy)
        {
            return dx > 0 ? battle_facing::right : battle_facing::left;
        }
        return dy > 0 ? battle_facing::down : battle_facing::up;
    }

    battle_event _emit(battle_event event)
    {
        _state.last_event = event;
        return event;
    }

    presentation_queue<6> _entrance;
    battle_session<2> _session;
    deterministic_rng _rng{ 0x41U };
    battle_snapshot _state = {
        battle_phase::prebattle_menu,
        1,
        { 4, 10 },
        { 4, 10 },
        { 4, 10 },
        { unit_id::naruto, team::player, { 4, 10 }, 80, 80, 3, true },
        { unit_id::konoha_maru, team::enemy, { 4, 4 }, 10, 10, 2, true },
        0,
        0,
        0,
        0,
        0,
        battle_event::none,
        false,
        100,
        50,
        0,
        150,
        1,
        14,
        presentation_cue::none,
        presentation_mode::automatic,
        0,
        false,
        battle_outcome::none,
    };
};

}

#endif
