#ifndef KONOHA_BATTLE_SCENE_CONTROLLER_H
#define KONOHA_BATTLE_SCENE_CONTROLLER_H

#include "konoha/battle_encounter_runtime.h"
#include "konoha/battle_mission_rules.h"
#include "konoha/battle_presentation_script.h"
#include "konoha/battle_training_flow.h"
#include "konoha/battle_results.h"
#include "konoha/battle_scene_presentation.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

using battle_scene_party_equipment = std::array<
        std::array<
                ninja_tool_id,
                battle_ninja_tool_slot_capacity>,
        3>;

enum class battle_scene_phase : std::uint8_t
{
    preparation,
    unit_selection,
    move_selection,
    command_selection,
    chakra_selection,
    rest_confirmation,
    action_selection,
    combination_decision,
    target_selection,
    facing_selection,
    defense_decision,
    defense_selection,
    enemy_turn,
    outcome,
    result,
    level_up,
    complete,
    error,
    script_blocked,
    training,
    target_confirmation,
    end_confirmation,
    target_preview,
};

enum class battle_scene_control_error : std::uint8_t
{
    none,
    encounter_load_failed,
    invalid_phase,
    invalid_input,
    player_flow_failed,
    ai_flow_failed,
    presentation_failed,
    script_failed,
};

struct battle_scene_control_result
{
    battle_scene_control_error error =
            battle_scene_control_error::none;
    battle_encounter_load_result encounter = {};
    battle_player_action_flow_result player = {};
    battle_ai_turn_flow_result ai = {};

    [[nodiscard]] constexpr bool success() const
    {
        return error == battle_scene_control_error::none;
    }
};

struct battle_scene_unit_view
{
    battle_unit_id id = no_battle_unit;
    std::uint8_t character_id = 0;
    battle_side side = battle_side::player;
    battle_control control = battle_control::player;
    grid_point position = {};
    battle_facing facing = battle_facing::up;
    int level = 1;
    int attack = 0;
    int defense = 0;
    int agility = 0;
    int movement = 0;
    int hp = 0;
    int max_hp = 0;
    int chakra = 0;
    int max_chakra = 0;
    std::uint8_t status_count = 0;
    bool active = false;
    bool completed = false;
    battle_unit_id summoner = no_battle_unit;

    constexpr bool operator==(const battle_scene_unit_view&) const =
            default;
};

struct battle_scene_object_view
{
    std::uint8_t slot = no_battlefield_object;
    std::uint8_t type = 0;
    grid_point position = {};
    std::uint16_t payload_id = 0;
    std::uint16_t duration_ticks = 0;
    std::uint16_t source_unit_id = 0;

    constexpr bool operator==(
            const battle_scene_object_view&) const = default;
};

struct battle_scene_object_snapshot
{
    std::size_t count = 0;
    std::array<
            battle_scene_object_view,
            battlefield_object_table::usable_capacity>
            objects = {};
};

template<std::size_t MaxUnits>
struct battle_scene_snapshot
{
    static constexpr int maximum_overlay_rows = 32;

    battle_scene_phase phase = battle_scene_phase::preparation;
    int round = 0;
    battle_side current_side = battle_side::player;
    grid_point cursor = {};
    battle_unit_id selected_unit = no_battle_unit;
    battle_facing selected_facing = battle_facing::up;
    bool target_confirmation_yes = true;
    bool end_confirmation_yes = true;
    bool defense_confirmation_yes = true;
    std::size_t result_participant_index = 0;
    std::uint8_t level_up_detail_page = 0;
    bool training_summary_active = false;
    std::uint8_t training_detail_page = 0;
    int overlay_width = 0;
    int overlay_height = 0;
    std::array<std::uint32_t, maximum_overlay_rows>
            move_overlay_rows = {};
    std::array<std::uint32_t, maximum_overlay_rows>
            range_overlay_rows = {};
    std::array<std::uint32_t, maximum_overlay_rows>
            target_overlay_rows = {};
    std::array<std::uint32_t, maximum_overlay_rows>
            blocked_overlay_rows = {};
    std::size_t unit_count = 0;
    std::size_t active_unit_count = 0;
    std::array<battle_scene_unit_view, MaxUnits> units = {};
    battle_player_action_flow_snapshot player = {};
    battle_condition_outcome outcome =
            battle_condition_outcome::none;
    battle_presentation_script_snapshot script = {};
};

template<std::size_t MaxUnits, int Width, int Height>
class battle_scene_controller
{
public:
    template<std::size_t CellCount>
    [[nodiscard]] battle_scene_control_result load(
            const battle_scenario_definition& scenario,
            const battle_map_definition& map_definition,
            const std::array<battle_map_cell, CellCount>& map_cells,
            std::uint8_t variant,
            const battle_scenario_load_policy& load_policy,
            const battle_condition_variant& conditions,
            std::uint32_t rng_seed,
            std::array<
                    character_progression_record,
                    3> progression_roster = {},
            bool enable_presentation_scripts = false,
            battle_mission_rules mission_rules = {},
            battle_campaign_inventory inventory = {})
    {
        battle_scenario_load_policy effective_load_policy =
                load_policy;
        const std::size_t ai_unit_count =
                mission_rules.control.ai_unit_count <
                                mission_rules.control
                                        .ai_units
                                        .size() ?
                        mission_rules.control
                                .ai_unit_count :
                        mission_rules.control
                                .ai_units
                                .size();
        for(std::size_t index = 0;
                index < ai_unit_count;
                ++index)
        {
            const std::uint8_t character_id =
                    mission_rules.control
                            .ai_units[index]
                            .character_id;
            if(character_id <
                    effective_load_policy
                            .ai_characters.size())
            {
                effective_load_policy
                        .ai_characters[character_id] =
                        true;
            }
        }
        _progression_roster = progression_roster;
        _progression_unit_ids.fill(no_battle_unit);
        _progression_equipped_tools = {};
        for(std::size_t index = 0;
                index < _progression_roster.size();
                ++index)
        {
            const character_progression_record& progression =
                    _progression_roster[index];
            if(progression.active &&
                    progression.character_id <
                            load_policy
                                    .character_equipped_tools
                                    .size())
            {
                _progression_equipped_tools[index] =
                        load_policy.character_equipped_tools[
                                progression.character_id];
            }
        }
        _initialize_supplied_action_progression(
                scenario.battle_id,
                variant);
        const battle_encounter_load_result loaded =
                _runtime.load(
                        scenario,
                        map_definition,
                        map_cells,
                        variant,
                        effective_load_policy,
                        conditions,
                        rng_seed,
                        _progression_roster.data(),
                        _progression_roster.size(),
                        mission_rules, inventory);
        if(! loaded.success())
        {
            _phase = battle_scene_phase::error;
            return {
                battle_scene_control_error::
                        encounter_load_failed,
                loaded,
            };
        }
        _phase = battle_scene_phase::preparation;
        _cursor = {};
        _selected_unit = no_battle_unit;
        _selected_facing = battle_facing::up;
        _target_confirmation_yes = true;
        _end_confirmation_yes = true;
        _result_participant_index = 0;
        _level_up_detail_page = 0;
        _training_summary_active = false;
        _training_detail_page = 0;
        _defense_confirmation_yes = true;
        _outcome = battle_condition_outcome::none;
        _battle_id = scenario.battle_id;
        _variant = variant;
        _result = {};
        _training.clear();
        _initialize_progression_roster();
        _bind_progression_units();
        for(std::size_t index = 0;
                index < _progression_unit_ids.size();
                ++index)
        {
            const battle_unit_instance* unit =
                    _runtime.session().unit(
                            _progression_unit_ids[index]);
            if(unit)
            {
                _progression_equipped_tools[index] =
                        unit->equipped_tools;
            }
        }
        _presentation_queue.clear();
        _observed_side_start_sequence = 0;
        _presentation_scripts_enabled =
                enable_presentation_scripts;
        _mission_rules = mission_rules;
        _script = {};
        _script_selectors = {};
        _script_selector_index = 0;
        _script_flags = {};
        _script_resume_phase =
                battle_scene_phase::unit_selection;
        return {};
    }

    [[nodiscard]] battle_scene_control_result start()
    {
        if(_phase != battle_scene_phase::preparation ||
                _runtime.start() !=
                        battle_transition::
                                unit_selection_opened)
        {
            return _invalid_phase();
        }
        if(! _queue_new_side_start_presentations())
        {
            _phase = battle_scene_phase::error;
            return {
                battle_scene_control_error::
                        presentation_failed,
            };
        }
        if(! _select_first_player())
        {
            _phase = battle_scene_phase::error;
            return _invalid_phase();
        }
        if(! _start_boundary_scripts(
                    _has_opening_allied_ai() ?
                            battle_scene_phase::enemy_turn :
                            battle_scene_phase::unit_selection))
        {
            return {
                battle_scene_control_error::script_failed,
            };
        }
        return {};
    }

    [[nodiscard]] battle_scene_snapshot<MaxUnits> snapshot() const
    {
        battle_scene_snapshot<MaxUnits> result;
        result.phase = _phase;
        result.round = _runtime.session().round_index();
        result.current_side =
                _runtime.session().current_side();
        result.cursor = _cursor;
        result.selected_unit = _selected_unit;
        result.selected_facing = _selected_facing;
        result.target_confirmation_yes =
                _target_confirmation_yes;
        result.end_confirmation_yes =
                _end_confirmation_yes;
        result.defense_confirmation_yes =
                _defense_confirmation_yes;
        result.result_participant_index =
                _result_participant_index;
        result.level_up_detail_page =
                _level_up_detail_page;
        result.training_summary_active =
                _training_summary_active;
        result.training_detail_page =
                _training_detail_page;
        if(_phase == battle_scene_phase::move_selection ||
                _phase == battle_scene_phase::target_selection ||
                _phase == battle_scene_phase::target_preview ||
                _phase == battle_scene_phase::target_confirmation)
        {
            _refresh_overlay_cache();
            result.overlay_width = _overlay_width;
            result.overlay_height = _overlay_height;
            result.move_overlay_rows =
                    _move_overlay_rows;
            result.range_overlay_rows =
                    _range_overlay_rows;
            result.target_overlay_rows =
                    _target_overlay_rows;
            result.blocked_overlay_rows =
                    _blocked_overlay_rows;
        }
        else
        {
            _overlay_phase = battle_scene_phase::error;
        }
        result.unit_count = _runtime.session().unit_count();
        result.player = _runtime.player_snapshot();
        result.outcome = _outcome;
        result.script = _script.snapshot();
        for(std::size_t index = 0;
                index < result.unit_count &&
                index < result.units.size();
                ++index)
        {
            const battle_unit_instance* unit =
                    _runtime.session().unit_at(index);
            if(! unit)
            {
                continue;
            }
            result.units[index] = {
                unit->id,
                unit->character_id,
                unit->side,
                unit->control,
                unit->position,
                unit->facing,
                unit->level,
                unit->attack,
                unit->defense,
                unit->agility,
                unit->move_range,
                unit->hp,
                unit->max_hp,
                unit->chakra,
                unit->max_chakra,
                static_cast<std::uint8_t>(
                        unit->statuses.active_count()),
                unit->active,
                unit->ledger.completed,
                unit->summoner,
            };
            if(unit->active)
            {
                ++result.active_unit_count;
            }
        }
        return result;
    }

    [[nodiscard]] battle_scene_object_snapshot
    object_snapshot() const
    {
        battle_scene_object_snapshot result;
        for(std::uint8_t slot = 1;
                slot < battlefield_object_table::capacity;
                ++slot)
        {
            const battlefield_object_record* object =
                    _runtime.session().objects().record(slot);
            if(! object || object->type == 0)
            {
                continue;
            }
            result.objects[result.count] = {
                slot,
                object->type,
                { object->x, object->y },
                object->payload_id,
                object->duration_ticks,
                object->source_unit_id,
            };
            ++result.count;
        }
        return result;
    }

    [[nodiscard]] const battle_result& result_snapshot() const
    {
        return _result;
    }

    [[nodiscard]] battle_training_snapshot
    training_snapshot() const
    {
        return _training.snapshot(_progression_roster);
    }

    [[nodiscard]] const std::array<
            character_progression_record,
            3>& progression_roster() const
    {
        return _progression_roster;
    }

    [[nodiscard]] battle_scene_party_equipment
    equipped_tools_roster() const
    {
        battle_scene_party_equipment result =
                _progression_equipped_tools;
        for(std::size_t index = 0;
                index < _progression_roster.size();
                ++index)
        {
            if(! _progression_roster[index].active)
            {
                continue;
            }
            const battle_unit_instance* unit =
                    _runtime.session().unit(
                            _progression_unit_ids[index]);
            if(unit)
            {
                result[index] = unit->equipped_tools;
            }
        }
        return result;
    }

    [[nodiscard]] const battle_campaign_inventory& inventory() const { return _runtime.inventory(); }
    [[nodiscard]] battle_material_pickup last_pickup() const { return _runtime.last_pickup(); }

    [[nodiscard]] battle_scene_presentation_event
    take_presentation_event()
    {
        return _presentation_queue.pop();
    }

    [[nodiscard]] constexpr bool
    presentation_pending() const
    {
        return ! _presentation_queue.empty();
    }

    [[nodiscard]] battle_scene_control_result move_cursor(
            int dx, int dy)
    {
        if((dx == 0) == (dy == 0) ||
                dx < -1 || dx > 1 ||
                dy < -1 || dy > 1)
        {
            return _invalid_input();
        }
        battle_player_action_flow_result player;
        switch(_phase)
        {
        case battle_scene_phase::command_selection:
            if(dx != 0)
            {
                return _invalid_input();
            }
            player = _runtime.cycle_command(dy);
            return _player_result(player);
        case battle_scene_phase::chakra_selection:
            if(dx != 0)
            {
                return _invalid_input();
            }
            player = _runtime.cycle_chakra_amount(dy);
            return _player_result(player);
        case battle_scene_phase::action_selection:
            if(dx != 0)
            {
                return _invalid_input();
            }
            player = _runtime.cycle_action(dy);
            return _player_result(player);
        case battle_scene_phase::combination_decision:
            if(dx != 0)
            {
                return _invalid_input();
            }
            player =
                    _runtime.cycle_combination_decision(
                            dy);
            return _player_result(player);
        case battle_scene_phase::defense_selection:
            if(dx != 0)
            {
                return _invalid_input();
            }
            player = _runtime.cycle_defense_action(dy);
            return _player_result(player);
        case battle_scene_phase::training:
            if(dx != 0 ||
                    ! _training.cycle_action(
                            dy, _progression_roster))
            {
                return _invalid_input();
            }
            return {};
        case battle_scene_phase::facing_selection:
            if(dx > 0)
            {
                _selected_facing = battle_facing::right;
            }
            else if(dx < 0)
            {
                _selected_facing = battle_facing::left;
            }
            else if(dy > 0)
            {
                _selected_facing = battle_facing::down;
            }
            else
            {
                _selected_facing = battle_facing::up;
            }
            return {};
        case battle_scene_phase::move_selection:
        {
            const grid_point next = {
                _cursor.x + dx,
                _cursor.y + dy,
            };
            if(! _runtime.terrain().contains(next))
            {
                return _invalid_input();
            }
            player = _runtime.preview_move(next);
            if(! player.success())
            {
                return _player_result(player);
            }
            _selected_facing = dx < 0 ? battle_facing::left :
                    dx > 0 ? battle_facing::right :
                    dy < 0 ? battle_facing::up : battle_facing::down;
            _cursor = next;
            return {};
        }
        case battle_scene_phase::unit_selection:
            return cycle_unit(dx != 0 ? dx : dy);
        case battle_scene_phase::target_selection:
        {
            const grid_point next = {
                _cursor.x + dx,
                _cursor.y + dy,
            };
            if(! _runtime.terrain().contains(next))
            {
                return _invalid_input();
            }
            _cursor = next;
            return {};
        }
        case battle_scene_phase::target_confirmation:
            if(dx != 0)
            {
                return _invalid_input();
            }
            _target_confirmation_yes =
                    ! _target_confirmation_yes;
            return {};
        case battle_scene_phase::end_confirmation:
            if(dx != 0)
            {
                return _invalid_input();
            }
            _end_confirmation_yes =
                    ! _end_confirmation_yes;
            return {};
        case battle_scene_phase::defense_decision:
            if(dx != 0)
            {
                return _invalid_input();
            }
            _defense_confirmation_yes =
                    ! _defense_confirmation_yes;
            return {};
        default:
            return _invalid_phase();
        }
    }

    [[nodiscard]] battle_scene_control_result cycle_unit(
            int direction)
    {
        if(_phase == battle_scene_phase::result)
        {
            if(direction == 0 ||
                    _result.participant_count == 0)
            {
                return _invalid_input();
            }
            if(direction > 0)
            {
                _result_participant_index =
                        (_result_participant_index + 1) %
                        _result.participant_count;
            }
            else
            {
                _result_participant_index =
                        (_result_participant_index +
                         _result.participant_count - 1) %
                        _result.participant_count;
            }
            return {};
        }
        if(_phase == battle_scene_phase::training)
        {
            return _training.cycle_character(
                           direction,
                           _progression_roster) ?
                    battle_scene_control_result{} :
                    _invalid_input();
        }
        if(_phase != battle_scene_phase::unit_selection ||
                direction == 0)
        {
            return _invalid_phase();
        }
        const battle_unit_instance* selected =
                _runtime.cycle_roster_unit(
                        _selected_unit, direction);
        if(! selected)
        {
            return _invalid_input();
        }
        _selected_unit = selected->id;
        _cursor = selected->position;
        return {};
    }

    [[nodiscard]] battle_scene_control_result confirm()
    {
        switch(_phase)
        {
        case battle_scene_phase::script_blocked:
            return _confirm_script();
        case battle_scene_phase::unit_selection:
            return _confirm_unit();
        case battle_scene_phase::move_selection:
            return _confirm_move();
        case battle_scene_phase::command_selection:
            return _confirm_command();
        case battle_scene_phase::chakra_selection:
        {
            const battle_player_action_flow_result player =
                    _runtime.confirm_chakra();
            if(! player.success())
            {
                return _player_result(player);
            }
            _phase = player.ends_battle ?
                    battle_scene_phase::outcome :
                    battle_scene_phase::facing_selection;
            return {};
        }
        case battle_scene_phase::rest_confirmation:
        {
            const battle_player_action_flow_result player =
                    _runtime.confirm_rest();
            if(! player.success())
            {
                return _player_result(player);
            }
            _phase = player.ends_battle ?
                    battle_scene_phase::outcome :
                    battle_scene_phase::facing_selection;
            return {};
        }
        case battle_scene_phase::action_selection:
        {
            const battle_player_action_flow_result player =
                    _runtime.confirm_action_selection();
            if(! player.success())
            {
                return _player_result(player);
            }
            _sync_action_scene_phase();
            return {};
        }
        case battle_scene_phase::combination_decision:
        {
            const battle_player_action_flow_result player =
                    _runtime.confirm_combination_decision();
            if(! player.success())
            {
                return _player_result(player);
            }
            _sync_action_scene_phase();
            return {};
        }
        case battle_scene_phase::target_selection:
            if(_mission_rules.confirm_targets)
            {
                const battle_player_action_flow_result preview =
                        _runtime.preview_target(_cursor);
                if(! preview.success())
                {
                    return _player_result(preview);
                }
                _target_confirmation_yes = true;
                _phase =
                        battle_scene_phase::
                                target_preview;
                return {};
            }
            return _confirm_target();
        case battle_scene_phase::target_preview:
            _target_confirmation_yes = true;
            _phase =
                    battle_scene_phase::
                            target_confirmation;
            return {};
        case battle_scene_phase::target_confirmation:
            if(! _target_confirmation_yes)
            {
                _phase =
                        battle_scene_phase::
                                target_preview;
                return {};
            }
            return _confirm_target();
        case battle_scene_phase::end_confirmation:
            if(! _end_confirmation_yes)
            {
                _phase =
                        battle_scene_phase::
                                command_selection;
                return {};
            }
        {
            const battle_player_action_flow_result player =
                    _runtime.end_without_action();
            if(! player.success())
            {
                return _player_result(player);
            }
            _phase = battle_scene_phase::facing_selection;
            return {};
        }
        case battle_scene_phase::facing_selection:
        {
            const battle_player_action_flow_result player =
                    _runtime.select_facing(
                            _selected_facing);
            if(! player.success())
            {
                return _player_result(player);
            }
            _defense_confirmation_yes = true;
            _phase = battle_scene_phase::defense_decision;
            return {};
        }
        case battle_scene_phase::defense_decision:
            if(_defense_confirmation_yes)
            {
                return open_defense_selection();
            }
            return _finish_player(
                    _runtime.complete_without_defense());
        case battle_scene_phase::defense_selection:
            return _finish_player(
                    _runtime.complete_selected_defense());
        case battle_scene_phase::outcome:
            return _open_result();
        case battle_scene_phase::result:
            return _settle_result();
        case battle_scene_phase::level_up:
            return _advance_level_up();
        case battle_scene_phase::training:
            if(_training_summary_active)
            {
                return _advance_training_summary();
            }
            (void) _training.confirm(
                    _progression_roster);
            return {};
        default:
            return _invalid_phase();
        }
    }

    [[nodiscard]] battle_scene_control_result
    open_defense_selection()
    {
        if(_phase != battle_scene_phase::defense_decision)
        {
            return _invalid_phase();
        }
        const battle_player_action_flow_result player =
                _runtime.open_defense_selection();
        if(! player.success())
        {
            return _player_result(player);
        }
        _phase = battle_scene_phase::defense_selection;
        return {};
    }

    [[nodiscard]] battle_scene_control_result cancel()
    {
        battle_player_action_flow_result player;
        switch(_phase)
        {
        case battle_scene_phase::move_selection:
            player = _mission_rules.open_command_before_move ?
                    _runtime.cancel_move_selection() :
                    _runtime.cancel_unit_action();
            if(player.success())
            {
                _phase = _mission_rules.open_command_before_move ?
                        battle_scene_phase::command_selection :
                        battle_scene_phase::unit_selection;
                _cursor = _selected_position();
                _selected_facing = _runtime.session().unit(_selected_unit)->facing;
            }
            return _player_result(player);
        case battle_scene_phase::unit_selection:
            return {};
        case battle_scene_phase::command_selection:
            if(_mission_rules.open_command_before_move &&
                    _runtime.player_snapshot().movement_selection_confirmed)
            {
                player = _runtime.cancel_move_selection();
                if(player.success())
                {
                    _cursor = _selected_position();
                    _selected_facing = _runtime.session().unit(_selected_unit)->facing;
                }
            }
            else if(_runtime.session().draft().move_previewed)
            {
                player = _runtime.reopen_move_selection();
                if(player.success())
                {
                    _phase = battle_scene_phase::move_selection;
                    _cursor = _runtime.session().draft().origin;
                }
            }
            else
            {
                player = _runtime.cancel_unit_action();
                if(player.success())
                {
                    _phase = battle_scene_phase::unit_selection;
                    _cursor = _selected_position();
                }
            }
            return _player_result(player);
        case battle_scene_phase::chakra_selection:
            player = _runtime.cancel_chakra_selection();
            if(player.success())
            {
                _phase = battle_scene_phase::command_selection;
            }
            return _player_result(player);
        case battle_scene_phase::rest_confirmation:
            player = _runtime.cancel_rest_confirmation();
            if(player.success())
            {
                _phase = battle_scene_phase::command_selection;
            }
            return _player_result(player);
        case battle_scene_phase::action_selection:
            player = _runtime.cancel_action_selection();
            if(player.success())
            {
                _phase = _runtime.player_snapshot().phase ==
                                battle_player_action_phase::
                                        action_selection ?
                        battle_scene_phase::action_selection :
                        battle_scene_phase::command_selection;
            }
            return _player_result(player);
        case battle_scene_phase::combination_decision:
            player =
                    _runtime.cancel_combination_decision();
            if(player.success())
            {
                _phase =
                        battle_scene_phase::
                                action_selection;
            }
            return _player_result(player);
        case battle_scene_phase::target_selection:
            player = _runtime.cancel_target_selection();
            if(player.success())
            {
                _phase = battle_scene_phase::action_selection;
            }
            return _player_result(player);
        case battle_scene_phase::target_preview:
            _phase = battle_scene_phase::target_selection;
            return {};
        case battle_scene_phase::target_confirmation:
            _phase = battle_scene_phase::target_preview;
            return {};
        case battle_scene_phase::end_confirmation:
            _phase = battle_scene_phase::command_selection;
            return {};
        case battle_scene_phase::defense_decision:
            player = _runtime.cancel_defense_decision();
            if(player.success())
            {
                _phase = battle_scene_phase::facing_selection;
            }
            return _player_result(player);
        case battle_scene_phase::defense_selection:
            player = _runtime.cancel_defense_selection();
            if(player.success())
            {
                _phase = battle_scene_phase::defense_decision;
            }
            return _player_result(player);
        case battle_scene_phase::training:
            _training.clear();
            _training_summary_active = false;
            _phase = battle_scene_phase::complete;
            return {};
        default:
            return _invalid_phase();
        }
    }

    [[nodiscard]] battle_scene_control_result tick()
    {
        if(_phase == battle_scene_phase::script_blocked)
        {
            if(_script.snapshot().phase !=
                    battle_presentation_script_phase::
                            wait_frames)
            {
                return _invalid_phase();
            }
            if(! _script.tick())
            {
                return {
                    battle_scene_control_error::
                            script_failed,
                };
            }
            if(_script.snapshot().phase ==
                    battle_presentation_script_phase::
                            complete &&
                    ! _continue_script_sequence())
            {
                return {
                    battle_scene_control_error::
                            script_failed,
                };
            }
            return {};
        }
        if(_phase != battle_scene_phase::enemy_turn)
        {
            return _invalid_phase();
        }
        const battle_side acting_side =
                _runtime.session().current_side();
        const bool opening_allied_ai = _has_opening_allied_ai();
        if(acting_side == battle_side::player &&
                ! opening_allied_ai &&
                _select_first_player())
        {
            if(! _start_boundary_scripts(
                        battle_scene_phase::
                                unit_selection))
            {
                return {
                    battle_scene_control_error::
                            script_failed,
                };
            }
            return {};
        }
        const battle_unit_id actor =
                _runtime.first_available_unit(
                        acting_side,
                        battle_control::ai);
        if(actor == no_battle_unit)
        {
            return _advance_empty_side();
        }
        const battle_unit_instance* acting_unit =
                _runtime.session().unit(actor);
        if(! acting_unit)
        {
            return {
                battle_scene_control_error::ai_flow_failed,
            };
        }
        const grid_point origin =
                acting_unit->position;
        std::array<battle_unit_id, MaxUnits>
                unit_ids_before = {};
        std::array<std::uint8_t, MaxUnits>
                character_ids_before = {};
        std::array<int, MaxUnits> hp_before = {};
        std::array<int, MaxUnits> max_hp_before = {};
        const std::size_t unit_count_before =
                _runtime.session().unit_count();
        for(std::size_t index = 0;
                index < unit_count_before;
                ++index)
        {
            const battle_unit_instance* unit =
                    _runtime.session().unit_at(index);
            if(unit)
            {
                unit_ids_before[index] = unit->id;
                character_ids_before[index] =
                        unit->character_id;
                hp_before[index] = unit->hp;
                max_hp_before[index] = unit->max_hp;
            }
        }
        ai_objective objective;
        const battle_mission_ai_unit_policy*
                mission_ai_unit =
                        _mission_rules.control.ai_unit(
                                acting_unit->character_id);
        if(mission_ai_unit &&
                mission_ai_unit->has_focus_position)
        {
            objective.has_focus_position = true;
            objective.focus_position =
                    mission_ai_unit->focus_position;
            objective.focus_position_weight =
                    mission_ai_unit->
                            focus_position_weight;
        }
        const battle_ai_turn_flow_result ai =
                _runtime.run_ai(actor, objective);
        if(! ai.success())
        {
            battle_scene_control_result result;
            result.error =
                    battle_scene_control_error::
                            ai_flow_failed;
            result.ai = ai;
            return result;
        }
        if(ai.turn.ends_battle)
        {
            _outcome = ai.turn.outcome;
            _phase = battle_scene_phase::outcome;
        }
        else if(_runtime.session().current_side() ==
                battle_side::player)
        {
            if(! _select_first_player())
            {
                if(! _start_boundary_scripts(
                            battle_scene_phase::
                                    enemy_turn))
                {
                    return {
                        battle_scene_control_error::
                                script_failed,
                    };
                }
            }
            else if(opening_allied_ai)
            {
                // The opening side's dialogue already ran before this AI turn.
                _phase = battle_scene_phase::unit_selection;
            }
            else if(! _start_boundary_scripts(
                            battle_scene_phase::
                                    unit_selection))
            {
                return {
                    battle_scene_control_error::
                            script_failed,
                };
            }
        }
        battle_scene_control_result result;
        result.ai = ai;
        battle_scene_presentation_event presentation = {
            true,
            ai.action_resolved,
            actor,
            ai.action_id,
            origin,
            ai.plan.destination,
            ai.plan.target_position,
            ai.action_kind ==
                    battle_action_source_kind::ninja_tool,
            ai.animation_family,
            ai.targets_opponent,
            ai.target_id,
            ai.action_resolved &&
                    battle_combat_actor_lunges(
                            ai.action_id,
                            ai.action_kind ==
                                    battle_action_source_kind::
                                            ninja_tool),
        };
        presentation.affected_unit_ids =
                ai.affected_unit_ids;
        presentation.affected_unit_count =
                ai.affected_unit_count;
        for(int affected_index = 0;
                affected_index <
                        presentation.affected_unit_count;
                ++affected_index)
        {
            const battle_unit_id affected_id =
                    presentation.affected_unit_ids[
                            static_cast<std::size_t>(
                                    affected_index)];
            for(std::size_t unit_index = 0;
                    unit_index < unit_count_before;
                    ++unit_index)
            {
                if(unit_ids_before[unit_index] ==
                        affected_id)
                {
                    presentation.affected_character_ids[
                            static_cast<std::size_t>(
                                    affected_index)] =
                            character_ids_before[
                                    unit_index];
                    break;
                }
            }
        }
        presentation.affected_units_truncated =
                ai.affected_units_truncated;
        presentation.impact_count = ai.impact_count;
        const battle_unit_instance* actor_after =
                _runtime.session().unit(actor);
        const battle_unit_instance* target_after =
                _runtime.session().unit(ai.target_id);
        for(std::size_t index = 0;
                index < unit_count_before;
                ++index)
        {
            if(unit_ids_before[index] == ai.target_id &&
                    actor_after &&
                    target_after)
            {
                presentation.has_combatant_vitals = true;
                presentation.actor_hp = actor_after->hp;
                presentation.actor_max_hp =
                        actor_after->max_hp;
                presentation.target_hp_before =
                        hp_before[index];
                presentation.target_hp_after =
                        target_after->hp;
                presentation.target_max_hp =
                        max_hp_before[index];
                break;
            }
        }
        presentation.has_resource =
                ai.resource_resolved;
        presentation.resource_type =
                ai.resource_type;
        presentation.resource_amount =
                ai.resource_amount;
        presentation.resource_hp_delta =
                ai.resource_hp_delta;
        presentation.resource_chakra_delta =
                ai.resource_chakra_delta;
        if(! _presentation_queue.push(presentation) ||
                ! _queue_battlefield_object_presentations(
                        ai.turn.object_event_count) ||
                ! _queue_new_side_start_presentations())
        {
            result.error =
                    battle_scene_control_error::
                            presentation_failed;
        }
        return result;
    }

private:
    [[nodiscard]] battle_scene_control_result
    _advance_empty_side()
    {
        const battle_turn_flow_result turn =
                _runtime.advance_empty_side();
        if(turn.error != battle_turn_flow_error::none)
        {
            return {
                battle_scene_control_error::
                        ai_flow_failed,
            };
        }
        if(! _queue_battlefield_object_presentations(
                   turn.object_event_count) ||
                ! _queue_new_side_start_presentations())
        {
            return {
                battle_scene_control_error::
                        presentation_failed,
            };
        }
        if(turn.ends_battle)
        {
            _outcome = turn.outcome;
            _phase = battle_scene_phase::outcome;
        }
        else if(_runtime.session().current_side() ==
                battle_side::player)
        {
            if(_select_first_player())
            {
                if(! _start_boundary_scripts(
                            battle_scene_phase::
                                    unit_selection))
                {
                    return {
                        battle_scene_control_error::
                                script_failed,
                    };
                }
            }
            else
            {
                if(! _start_boundary_scripts(
                            battle_scene_phase::
                                    enemy_turn))
                {
                    return {
                        battle_scene_control_error::
                                script_failed,
                    };
                }
            }
        }
        else
        {
            if(! _start_boundary_scripts(
                        battle_scene_phase::enemy_turn))
            {
                return {
                    battle_scene_control_error::
                            script_failed,
                };
            }
        }
        return {};
    }

    [[nodiscard]] battle_scene_control_result _confirm_script()
    {
        if(_script.snapshot().phase !=
                battle_presentation_script_phase::
                        wait_for_input ||
                ! _script.confirm())
        {
            return _invalid_input();
        }
        if(_script.snapshot().phase ==
                battle_presentation_script_phase::
                        complete &&
                ! _continue_script_sequence())
        {
            return {
                battle_scene_control_error::script_failed,
            };
        }
        return {};
    }

    [[nodiscard]] bool _start_boundary_scripts(
            battle_scene_phase resume_phase)
    {
        _script_resume_phase = resume_phase;
        if(! _presentation_scripts_enabled)
        {
            _phase = resume_phase;
            return true;
        }
        const battle_presentation_definition* definition =
                battle_presentation_definition_for(
                        _battle_id);
        if(! definition)
        {
            _phase = battle_scene_phase::error;
            return false;
        }
        battle_presentation_selector_context context;
        context.round_index =
                _runtime.session().round_index();
        context.side = static_cast<std::uint8_t>(
                _runtime.session().current_side());
        context.battle_state =
                static_cast<std::uint8_t>(_variant);
        context.flags = &_script_flags;
        const std::size_t unit_count =
                _runtime.session().unit_count();
        context.unit_count =
                static_cast<std::uint8_t>(
                        unit_count < context.units.size() ?
                                unit_count :
                                context.units.size());
        for(std::size_t index = 0;
                index < context.unit_count; ++index)
        {
            const battle_unit_instance* unit =
                    _runtime.session().unit_at(index);
            if(unit)
            {
                context.units[index] = {
                    unit->character_id,
                    static_cast<std::uint8_t>(
                            unit->side),
                    static_cast<std::int8_t>(
                            unit->position.x),
                    static_cast<std::int8_t>(
                            unit->position.y),
                    unit->active && unit->hp > 0,
                };
            }
        }
        _script_selectors =
                _script_selector.evaluate(
                        *definition, context);
        _script_selector_index = 0;
        if(! _script_selectors.success())
        {
            _phase = battle_scene_phase::error;
            return false;
        }
        return _continue_script_sequence();
    }

    [[nodiscard]] bool _continue_script_sequence()
    {
        if(_script_selector_index >=
                _script_selectors.count)
        {
            _phase = _script_resume_phase;
            return true;
        }
        const battle_presentation_definition* definition =
                battle_presentation_definition_for(
                        _battle_id);
        if(! definition ||
                ! _script.begin(
                        *definition,
                        _script_selectors.selectors[
                                _script_selector_index]))
        {
            _phase = battle_scene_phase::error;
            return false;
        }
        ++_script_selector_index;
        _phase = battle_scene_phase::script_blocked;
        return true;
    }

    [[nodiscard]] battle_scene_control_result _open_result()
    {
        if(_outcome != battle_condition_outcome::win)
        {
            _phase = battle_scene_phase::complete;
            return {};
        }
        const std::uint8_t record =
                battle_reward_record_for_scenario(
                        _battle_id, _variant);
        if(record == no_battle_reward_record)
        {
            _phase = battle_scene_phase::error;
            return {
                battle_scene_control_error::
                        invalid_input,
            };
        }
        _result = battle_result_system::preview(
                _runtime.session(),
                battle_reward_definitions[record],
                _runtime.session().round_index(),
                _progression_roster,
                _mission_rules.result);
        if(_result.participant_count == 0)
        {
            _phase = battle_scene_phase::error;
            return {
                battle_scene_control_error::
                        invalid_input,
            };
        }
        _result_participant_index = 0;
        _phase = battle_scene_phase::result;
        return {};
    }

    [[nodiscard]] battle_scene_control_result _settle_result()
    {
        if(! battle_result_system::apply_experience(
                   _result, _progression_roster) ||
                ! battle_result_system::settle_levels(
                        _result, _progression_roster))
        {
            _phase = battle_scene_phase::error;
            return {
                battle_scene_control_error::
                        invalid_input,
            };
        }
        std::size_t first_level_up =
                _result.participant_count;
        for(std::size_t index = 0;
                index < _result.participant_count;
                ++index)
        {
            const battle_result_participant& participant =
                    _result.participants[index];
            if(participant.after.level >
                    participant.before.level)
            {
                first_level_up = index;
                break;
            }
        }
        if(first_level_up < _result.participant_count)
        {
            _result_participant_index = first_level_up;
            _level_up_detail_page = 0;
            _phase = battle_scene_phase::level_up;
        }
        else
        {
            _phase = _begin_training() ?
                    battle_scene_phase::training :
                    battle_scene_phase::complete;
        }
        return {};
    }

    [[nodiscard]] battle_scene_control_result
    _advance_level_up()
    {
        if(_result_participant_index >=
                _result.participant_count)
        {
            return _invalid_input();
        }
        if(_level_up_detail_page == 0)
        {
            _level_up_detail_page = 1;
            return {};
        }
        for(std::size_t index =
                        _result_participant_index + 1;
                index < _result.participant_count;
                ++index)
        {
            const battle_result_participant& participant =
                    _result.participants[index];
            if(participant.after.level >
                    participant.before.level)
            {
                _result_participant_index = index;
                _level_up_detail_page = 0;
                return {};
            }
        }
        _level_up_detail_page = 0;
        _phase = _begin_training() ?
                battle_scene_phase::training :
                battle_scene_phase::complete;
        return {};
    }

    [[nodiscard]] bool _begin_training()
    {
        const bool active = _training.begin(
                _progression_roster);
        _training_summary_active =
                active && _battle_id == 14 &&
                _variant == 0;
        _training_detail_page = 0;
        return active;
    }

    [[nodiscard]] battle_scene_control_result
    _advance_training_summary()
    {
        constexpr std::uint8_t page_count = 6;
        if(_phase != battle_scene_phase::training ||
                ! _training_summary_active)
        {
            return _invalid_phase();
        }
        if(_training_detail_page + 1 < page_count)
        {
            ++_training_detail_page;
            return {};
        }
        _training.clear();
        _training_summary_active = false;
        _phase = battle_scene_phase::complete;
        return {};
    }

    void _initialize_progression_roster()
    {
        for(const character_progression_record& progression :
                _progression_roster)
        {
            if(progression.active)
            {
                return;
            }
        }
        std::size_t output_index = 0;
        for(std::size_t index = 0;
                index < _runtime.session().unit_count() &&
                output_index < _progression_roster.size();
                ++index)
        {
            const battle_unit_instance* unit =
                    _runtime.session().unit_at(index);
            if(! unit || unit->side != battle_side::player ||
                    ! unit->active)
            {
                continue;
            }
            character_progression_record& progression =
                    _progression_roster[output_index++];
            progression = {
                unit->character_id,
                unit->level,
                0,
                0,
                true,
            };
            if(unit->character_id <
                    unit_definitions.size())
            {
                (void)
                        initialize_character_action_progression(
                                progression,
                                unit_definitions[
                                        unit->character_id]);
            }
        }
    }

    void _bind_progression_units()
    {
        _progression_unit_ids.fill(no_battle_unit);
        for(std::size_t progression_index = 0;
                progression_index <
                        _progression_roster.size();
                ++progression_index)
        {
            const character_progression_record& progression =
                    _progression_roster[progression_index];
            if(! progression.active)
            {
                continue;
            }
            for(std::size_t unit_index = 0;
                    unit_index <
                            _runtime.session().unit_count();
                    ++unit_index)
            {
                const battle_unit_instance* unit =
                        _runtime.session().unit_at(
                                unit_index);
                if(unit &&
                        unit->side == battle_side::player &&
                        unit->summoner == no_battle_unit &&
                        unit->original_character_id ==
                                progression.character_id)
                {
                    _progression_unit_ids[
                            progression_index] =
                                    unit->id;
                    break;
                }
            }
        }
    }

    void _initialize_supplied_action_progression(
            int battle_id,
            int variant)
    {
        for(character_progression_record& progression :
                _progression_roster)
        {
            if(! progression.active ||
                    progression.character_id >=
                            unit_definitions.size())
            {
                continue;
            }
            (void) synchronize_character_action_unlocks(
                    progression,
                    unit_definitions[
                            progression.character_id]);
            (void) synchronize_scenario_action_unlocks(
                    progression,
                    unit_definitions[
                            progression.character_id],
                    battle_id,
                    variant);
        }
    }

    void _sync_action_scene_phase()
    {
        switch(_runtime.player_snapshot().phase)
        {
        case battle_player_action_phase::action_selection:
            _phase = battle_scene_phase::action_selection;
            break;
        case battle_player_action_phase::
                combination_decision:
            _phase =
                    battle_scene_phase::
                            combination_decision;
            break;
        case battle_player_action_phase::target_selection:
            _phase = battle_scene_phase::target_selection;
            break;
        default:
            _phase = battle_scene_phase::error;
            break;
        }
    }

    [[nodiscard]] battle_scene_control_result _confirm_unit()
    {
        const battle_unit_instance* selected =
                _runtime.session().active_unit_at(_cursor);
        if(! selected ||
                selected->control != battle_control::player ||
                ! _runtime.session().can_issue_commands(
                        selected->id))
        {
            return _invalid_input();
        }
        const battle_player_action_flow_result begun =
                _runtime.begin_player_unit(
                        selected->id,
                        _mission_rules.command_access);
        if(! begun.success())
        {
            return _player_result(begun);
        }
        _selected_unit = selected->id;
        _selected_facing = selected->facing;
        if(_mission_rules.open_command_before_move)
        {
            _phase = battle_scene_phase::command_selection;
            return {};
        }
        const battle_player_action_flow_result move =
                _runtime.open_move_selection();
        if(! move.success())
        {
            return _player_result(move);
        }
        _phase = battle_scene_phase::move_selection;
        return {};
    }

    [[nodiscard]] battle_scene_control_result _confirm_move()
    {
        const battle_player_action_flow_result preview =
                _runtime.preview_move(_cursor);
        if(! preview.success())
        {
            return _player_result(preview);
        }
        const battle_player_action_flow_result confirmed =
                _runtime.confirm_move_selection();
        if(! confirmed.success())
        {
            return _player_result(confirmed);
        }
        _phase = battle_scene_phase::command_selection;
        return {};
    }

    [[nodiscard]] battle_scene_control_result _confirm_command()
    {
        const battle_command_type command =
                _runtime.player_snapshot().selected_command;
        battle_player_action_flow_result player;
        switch(command)
        {
        case battle_command_type::move:
            player = _runtime.reopen_move_selection();
            if(player.success())
            {
                _phase = battle_scene_phase::move_selection;
                _cursor = _runtime.session().draft().origin;
            }
            break;
        case battle_command_type::ability:
            player = _runtime.open_action_selection(
                    _mission_rules.action_access);
            if(player.success())
            {
                _phase = battle_scene_phase::action_selection;
            }
            break;
        case battle_command_type::direct_attack:
            player = _runtime.open_direct_attack_targeting(
                    _mission_rules.action_access);
            if(player.success())
            {
                _phase =
                        battle_scene_phase::target_selection;
                _cursor = _runtime.session()
                                  .draft()
                                  .preview_position;
            }
            break;
        case battle_command_type::replenish_chakra:
            player = _runtime.open_chakra_selection();
            if(player.success())
            {
                _phase = battle_scene_phase::chakra_selection;
            }
            break;
        case battle_command_type::rest:
            player = _runtime.open_rest_confirmation();
            if(player.success())
            {
                _phase = battle_scene_phase::rest_confirmation;
            }
            break;
        case battle_command_type::end_action:
            _end_confirmation_yes = true;
            _phase = battle_scene_phase::end_confirmation;
            return {};
        default:
            return _invalid_input();
        }
        return _player_result(player);
    }

    [[nodiscard]] battle_scene_control_result _confirm_target()
    {
        const action_draft draft =
                _runtime.session().draft();
        const battle_player_action_flow_snapshot&
                player_snapshot =
                        _runtime.player_snapshot();
        const bool presents_special_combination =
                player_snapshot.combination_component_count == 2 &&
                player_snapshot.combination_result_action_id !=
                        no_ability;
        const ability_id selected_action_id =
                presents_special_combination ?
                player_snapshot.combination_result_action_id :
                player_snapshot.selected_action_id;
        const battle_unit_instance* actor =
                _runtime.session().unit(draft.unit_id);
        if(! actor)
        {
            return _invalid_input();
        }
        if(player_snapshot.action_index < 0 ||
                player_snapshot.action_index >=
                        player_snapshot.action_count)
        {
            return _invalid_input();
        }
        const battle_action_menu_view& selected_action =
                player_snapshot.action_entries[
                        static_cast<std::size_t>(
                                player_snapshot.action_index)];
        const action_definition* presented_definition =
                presents_special_combination &&
                        selected_action_id <
                                active_action_definitions.size() ?
                &active_action_definitions[
                        selected_action_id] :
                nullptr;
        if(selected_action.target_kind ==
                        target_policy_kind::empty_tile &&
                (_runtime.terrain().cost(_cursor) == 0 ||
                 _runtime.terrain().terrain_class(
                         _cursor) ==
                         grid_fully_closed ||
                 _runtime.session().active_unit_at(_cursor)))
        {
            return _invalid_input();
        }
        const grid_point action_position =
                draft.preview_position;
        const grid_point target_position = _cursor;
        std::array<battle_unit_id, MaxUnits>
                unit_ids_before = {};
        std::array<std::uint8_t, MaxUnits>
                character_ids_before = {};
        const std::size_t unit_count_before =
                _runtime.session().unit_count();
        for(std::size_t index = 0;
                index < unit_count_before;
                ++index)
        {
            const battle_unit_instance* unit =
                    _runtime.session().unit_at(index);
            if(unit)
            {
                unit_ids_before[index] = unit->id;
                character_ids_before[index] =
                        unit->character_id;
            }
        }
        const battle_unit_instance* presentation_target =
                _runtime.session().active_unit_at(_cursor);
        const battle_unit_id presentation_target_id =
                presentation_target ?
                        presentation_target->id :
                        no_battle_unit;
        const int actor_hp_before = actor->hp;
        const int actor_max_hp_before = actor->max_hp;
        const int target_hp_before =
                presentation_target ?
                        presentation_target->hp :
                        0;
        const int target_max_hp_before =
                presentation_target ?
                        presentation_target->max_hp :
                        0;
        const battle_player_action_flow_result preview =
                _runtime.preview_target(target_position);
        if(! preview.success())
        {
            return _player_result(preview);
        }
        const battle_player_action_flow_result confirmed =
                _runtime.confirm_target(target_position);
        if(! confirmed.success())
        {
            return _player_result(confirmed);
        }
        if(confirmed.ends_battle)
        {
            _outcome = confirmed.outcome;
            _phase = battle_scene_phase::outcome;
        }
        else
        {
            _cursor = action_position;
            _phase = battle_scene_phase::facing_selection;
        }
        battle_scene_control_result result;
        result.player = confirmed;
        battle_scene_presentation_event presentation = {
            true,
            true,
            draft.unit_id,
            selected_action_id,
            draft.origin,
            action_position,
            target_position,
            ! presented_definition &&
                    selected_action.kind ==
                    battle_action_source_kind::ninja_tool,
            presented_definition ?
                    presented_definition->presentation
                            .animation_family :
                    selected_action.animation_family,
            (presented_definition ?
                     presented_definition->target.kind :
                     selected_action.target_kind) ==
                    target_policy_kind::opponent_unit,
            presentation_target_id,
            battle_combat_actor_lunges(
                    selected_action_id,
                    ! presented_definition &&
                            selected_action.kind ==
                                    battle_action_source_kind::
                                            ninja_tool) ||
                    selected_action.kind ==
                            battle_action_source_kind::
                                    direct_attack,
        };
        presentation.affected_unit_ids =
                confirmed.affected_unit_ids;
        presentation.affected_unit_count =
                confirmed.affected_unit_count;
        for(int affected_index = 0;
                affected_index <
                        presentation.affected_unit_count;
                ++affected_index)
        {
            const battle_unit_id affected_id =
                    presentation.affected_unit_ids[
                            static_cast<std::size_t>(
                                    affected_index)];
            for(std::size_t unit_index = 0;
                    unit_index < unit_count_before;
                    ++unit_index)
            {
                if(unit_ids_before[unit_index] ==
                        affected_id)
                {
                    presentation.affected_character_ids[
                            static_cast<std::size_t>(
                                    affected_index)] =
                            character_ids_before[
                                    unit_index];
                    break;
                }
            }
        }
        presentation.special_combination =
                presents_special_combination;
        presentation.direct_attack =
                selected_action.kind ==
                battle_action_source_kind::direct_attack;
        presentation.capture_count =
                confirmed.capture_count;
        presentation.affected_units_truncated =
                confirmed.affected_units_truncated;
        presentation.impact_count = confirmed.impact_count;
        const battle_unit_instance* actor_after =
                _runtime.session().unit(draft.unit_id);
        const battle_unit_instance* target_after =
                _runtime.session().unit(
                        presentation_target_id);
        if(presentation_target && target_after)
        {
            presentation.has_combatant_vitals = true;
            presentation.actor_hp =
                    actor_after ?
                            actor_after->hp :
                            actor_hp_before;
            presentation.actor_max_hp =
                    actor_after ?
                            actor_after->max_hp :
                            actor_max_hp_before;
            presentation.target_hp_before =
                    target_hp_before;
            presentation.target_hp_after =
                    target_after->hp;
            presentation.target_max_hp =
                    target_max_hp_before;
        }
        if(! _presentation_queue.push(presentation))
        {
            result.error =
                    battle_scene_control_error::
                            presentation_failed;
        }
        return result;
    }

    [[nodiscard]] battle_scene_control_result _finish_player(
            const battle_player_action_flow_result& player)
    {
        if(! player.success())
        {
            return _player_result(player);
        }
        if(! _queue_battlefield_object_presentations(
                   player.object_event_count) ||
                ! _queue_new_side_start_presentations())
        {
            return {
                battle_scene_control_error::
                        presentation_failed,
            };
        }
        if(player.ends_battle)
        {
            _outcome = player.outcome;
            _phase = battle_scene_phase::outcome;
        }
        else if(_runtime.session().current_side() ==
                battle_side::enemy)
        {
            if(! _start_boundary_scripts(
                        battle_scene_phase::enemy_turn))
            {
                return {
                    battle_scene_control_error::
                            script_failed,
                };
            }
        }
        else
        {
            if(_select_first_player())
            {
                _phase = battle_scene_phase::unit_selection;
            }
            else if(_runtime.first_available_unit(
                            battle_side::player,
                            battle_control::ai) !=
                    no_battle_unit)
            {
                _phase = battle_scene_phase::enemy_turn;
            }
            else
            {
                _phase = battle_scene_phase::error;
                return {
                    battle_scene_control_error::
                            player_flow_failed,
                };
            }
        }
        return {};
    }

    [[nodiscard]] bool _has_opening_allied_ai() const
    {
        return _mission_rules.control.allied_ai_before_first_player_turn &&
                _runtime.session().round_index() == 1 &&
                _runtime.session().current_side() == battle_side::player &&
                _runtime.first_available_unit(
                        battle_side::player, battle_control::ai) != no_battle_unit;
    }

    [[nodiscard]] bool _select_first_player()
    {
        const battle_unit_id first =
                _runtime.first_available_unit(
                        battle_side::player,
                        battle_control::player);
        const battle_unit_instance* unit =
                _runtime.session().unit(first);
        if(first == no_battle_unit || ! unit)
        {
            return false;
        }
        _selected_unit = first;
        _cursor = unit->position;
        _selected_facing = unit->facing;
        return true;
    }

    [[nodiscard]] bool
    _queue_battlefield_object_presentations(
            int event_count)
    {
        if(event_count < 0)
        {
            return false;
        }
        if(event_count == 0)
        {
            return true;
        }
        if(
                static_cast<std::size_t>(event_count) !=
                        _runtime.session()
                                .object_tick_event_count())
        {
            return false;
        }
        for(int index = 0; index < event_count; ++index)
        {
            const battlefield_object_tick_event* event =
                    _runtime.session()
                            .object_tick_event_at(
                                    static_cast<std::size_t>(
                                            index));
            if(! event || ! event->valid())
            {
                return false;
            }
            if(event->kind ==
                    battlefield_object_tick_kind::
                            type_2_expired)
            {
                if(! _presentation_queue.push(
                           make_battlefield_object_presentation_event(
                                   *event, {}, 0)))
                {
                    return false;
                }
                continue;
            }
            if(event->object.payload_id >=
                        ninja_tool_action_definitions.size() ||
                    event->object.source_unit_id > 0xFF)
            {
                return false;
            }
            const action_definition& payload =
                    ninja_tool_action_definitions[
                            event->object.payload_id];
            const battle_unit_instance* actor =
                    _runtime.session().unit(
                            static_cast<battle_unit_id>(
                                    event->object
                                            .source_unit_id));
            if(payload.id != event->object.payload_id ||
                    ! actor ||
                    ! _presentation_queue.push(
                            make_battlefield_object_presentation_event(
                                    *event,
                                    actor->position,
                                    payload.presentation
                                            .animation_family)))
            {
                return false;
            }
        }
        return true;
    }

    [[nodiscard]] bool
    _queue_new_side_start_presentations()
    {
        return queue_new_side_start_presentations(
                _runtime.session(),
                _observed_side_start_sequence,
                _presentation_queue);
    }

    [[nodiscard]] grid_point _selected_position() const
    {
        const battle_unit_instance* unit =
                _runtime.session().unit(_selected_unit);
        return unit ? unit->position : grid_point{};
    }

    void _refresh_overlay_cache() const
    {
        const battle_player_action_flow_snapshot& player =
                _runtime.player_snapshot();
        const grid_point origin =
                _phase == battle_scene_phase::move_selection ?
                _runtime.session().draft().origin :
                _runtime.session().draft().preview_position;
        if(_overlay_phase == _phase &&
                _overlay_unit == _selected_unit &&
                _overlay_origin == origin &&
                _overlay_action_kind ==
                        player.selected_action_kind &&
                _overlay_action_id ==
                        player.selected_action_id &&
                _overlay_combination_count ==
                        player.combination_component_count &&
                _overlay_combination_result ==
                        player.combination_result_action_id)
        {
            return;
        }

        _overlay_phase = _phase;
        _overlay_unit = _selected_unit;
        _overlay_origin = origin;
        _overlay_action_kind =
                player.selected_action_kind;
        _overlay_action_id =
                player.selected_action_id;
        _overlay_combination_count =
                player.combination_component_count;
        _overlay_combination_result =
                player.combination_result_action_id;
        _overlay_width = 0;
        _overlay_height = 0;
        _move_overlay_rows.fill(0);
        _range_overlay_rows.fill(0);
        _target_overlay_rows.fill(0);
        _blocked_overlay_rows.fill(0);

        const reachable_cost_result<Width, Height>& reachable =
                _runtime.reachable_costs();
        const grid_map<Width, Height>& terrain =
                _runtime.terrain();
        _overlay_width = terrain.active_width();
        _overlay_height = terrain.active_height();
        for(int y = 0; y < _overlay_height; ++y)
        {
            for(int x = 0; x < _overlay_width; ++x)
            {
                if(terrain.cost({ x, y }) == 0)
                {
                    _blocked_overlay_rows[
                            static_cast<std::size_t>(y)] |=
                            std::uint32_t(1) << x;
                }
            }
        }
        const battle_session<MaxUnits>& session =
                _runtime.session();
        for(std::size_t index = 0;
                index < session.unit_count();
                ++index)
        {
            const battle_unit_instance* unit =
                    session.unit_at(index);
            if(unit && unit->active &&
                    terrain.contains(unit->position))
            {
                _blocked_overlay_rows[
                        static_cast<std::size_t>(
                                unit->position.y)] |=
                        std::uint32_t(1) <<
                                unit->position.x;
            }
        }
        if(reachable.valid)
        {
            for(int y = 0; y < _overlay_height; ++y)
            {
                for(int x = 0; x < _overlay_width; ++x)
                {
                    if(reachable.cost({ x, y }) >= 0)
                    {
                        _move_overlay_rows[
                                static_cast<std::size_t>(y)] |=
                                std::uint32_t(1) << x;
                    }
                }
            }
        }

        if(_phase == battle_scene_phase::move_selection)
        {
            _range_overlay_rows = _move_overlay_rows;
            return;
        }

        const int maximum_distance =
                _runtime.target_maximum_distance();
        if(maximum_distance < 0)
        {
            return;
        }
        for(int y = 0; y < _overlay_height; ++y)
        {
            for(int x = 0; x < _overlay_width; ++x)
            {
                const int dx = x - origin.x;
                const int dy = y - origin.y;
                const int distance =
                        (dx < 0 ? -dx : dx) +
                        (dy < 0 ? -dy : dy);
                const std::uint32_t bit =
                        std::uint32_t(1) << x;
                if(distance <= maximum_distance)
                {
                    _range_overlay_rows[
                            static_cast<std::size_t>(y)] |= bit;
                }
                if(_runtime.target_legal({ x, y }))
                {
                    _target_overlay_rows[
                            static_cast<std::size_t>(y)] |= bit;
                }
            }
        }
    }

    [[nodiscard]] static battle_scene_control_result
    _player_result(
            const battle_player_action_flow_result& player)
    {
        battle_scene_control_result result;
        result.player = player;
        if(! player.success())
        {
            result.error =
                    battle_scene_control_error::
                            player_flow_failed;
        }
        return result;
    }

    [[nodiscard]] static battle_scene_control_result
    _invalid_phase()
    {
        return {
            battle_scene_control_error::invalid_phase,
        };
    }

    [[nodiscard]] static battle_scene_control_result
    _invalid_input()
    {
        return {
            battle_scene_control_error::invalid_input,
        };
    }

    battle_encounter_runtime<MaxUnits, Width, Height> _runtime;
    battle_scene_phase _phase = battle_scene_phase::preparation;
    grid_point _cursor = {};
    battle_unit_id _selected_unit = no_battle_unit;
    battle_facing _selected_facing = battle_facing::up;
    bool _target_confirmation_yes = true;
    bool _end_confirmation_yes = true;
    bool _defense_confirmation_yes = true;
    mutable battle_scene_phase _overlay_phase =
            battle_scene_phase::error;
    mutable battle_unit_id _overlay_unit =
            no_battle_unit;
    mutable grid_point _overlay_origin = {};
    mutable battle_action_source_kind
            _overlay_action_kind =
                    battle_action_source_kind::active_action;
    mutable ability_id _overlay_action_id = no_ability;
    mutable std::uint8_t _overlay_combination_count = 0;
    mutable ability_id _overlay_combination_result =
            no_ability;
    mutable int _overlay_width = 0;
    mutable int _overlay_height = 0;
    mutable std::array<
            std::uint32_t,
            battle_scene_snapshot<
                    MaxUnits>::maximum_overlay_rows>
            _move_overlay_rows = {};
    mutable std::array<
            std::uint32_t,
            battle_scene_snapshot<
                    MaxUnits>::maximum_overlay_rows>
            _range_overlay_rows = {};
    mutable std::array<
            std::uint32_t,
            battle_scene_snapshot<
                    MaxUnits>::maximum_overlay_rows>
            _target_overlay_rows = {};
    mutable std::array<
            std::uint32_t,
            battle_scene_snapshot<
                    MaxUnits>::maximum_overlay_rows>
            _blocked_overlay_rows = {};
    battle_condition_outcome _outcome =
            battle_condition_outcome::none;
    int _battle_id = 0;
    int _variant = 0;
    battle_result _result = {};
    std::size_t _result_participant_index = 0;
    std::uint8_t _level_up_detail_page = 0;
    bool _training_summary_active = false;
    std::uint8_t _training_detail_page = 0;
    std::array<character_progression_record, 3>
            _progression_roster = {};
    std::array<battle_unit_id, 3>
            _progression_unit_ids = {
                no_battle_unit,
                no_battle_unit,
                no_battle_unit,
            };
    battle_scene_party_equipment
            _progression_equipped_tools = {};
    battle_training_flow _training;
    battle_scene_presentation_queue<
            MaxUnits +
                    battlefield_object_table::usable_capacity +
                    2> _presentation_queue;
    std::uint32_t _observed_side_start_sequence = 0;
    bool _presentation_scripts_enabled = false;
    battle_mission_rules _mission_rules = {};
    battle_presentation_selector _script_selector;
    battle_presentation_selector_result _script_selectors;
    std::uint8_t _script_selector_index = 0;
    battle_presentation_script_flags _script_flags;
    battle_scene_phase _script_resume_phase =
            battle_scene_phase::unit_selection;
    battle_presentation_script _script;
};

}

#endif
