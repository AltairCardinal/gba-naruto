#ifndef KONOHA_BATTLE_PLAYER_ACTION_FLOW_H
#define KONOHA_BATTLE_PLAYER_ACTION_FLOW_H

#include "konoha/battle_action_browser.h"
#include "konoha/battle_action_combinations.h"
#include "konoha/battle_action_execution.h"
#include "konoha/battle_capture_policy.h"
#include "konoha/battle_command_browser.h"
#include "konoha/battle_defense_browser.h"
#include "konoha/battle_direct_attack.h"
#include "konoha/battle_resource_commands.h"
#include "konoha/battle_terrain_traversal.h"
#include "konoha/battle_turn_flow.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_player_action_phase : std::uint8_t
{
    inactive,
    command_selection,
    move_selection,
    chakra_selection,
    rest_confirmation,
    action_selection,
    combination_decision,
    target_selection,
    facing_selection,
    defense_decision,
    defense_selection,
    completed,
    outcome,
};

enum class battle_player_action_flow_error : std::uint8_t
{
    none,
    invalid_phase,
    command_browser_failed,
    command_rejected,
    move_rejected,
    resource_rejected,
    action_browser_failed,
    action_rejected,
    defense_browser_failed,
    defense_rejected,
    turn_flow_failed,
};

struct battle_player_action_flow_result
{
    battle_player_action_flow_error error =
            battle_player_action_flow_error::none;
    action_error action_rejection = action_error::none;
    defense_preparation_error defense_error =
            defense_preparation_error::none;
    battle_turn_flow_error turn_flow_error =
            battle_turn_flow_error::none;
    battle_condition_outcome outcome =
            battle_condition_outcome::none;
    bool ends_battle = false;
    command_rejection command_error =
            command_rejection::none;
    battle_resource_command_error resource_error =
            battle_resource_command_error::none;
    std::array<battle_unit_id, 12> affected_unit_ids = {};
    int affected_unit_count = 0;
    bool affected_units_truncated = false;
    int impact_count = 0;
    int object_event_count = 0;
    battlefield_object_resolution_summary
            object_effects = {};
    int capture_count = 0;

    [[nodiscard]] constexpr bool success() const
    {
        return error == battle_player_action_flow_error::none;
    }
};

struct battle_action_access_policy
{
    bool restrict_active_actions = false;
    std::array<ability_id, 15> allowed_active_actions = {};
    std::size_t allowed_active_action_count = 0;
    bool allow_ninja_tools = true;
    bool allow_direct_attack = true;

    [[nodiscard]] constexpr bool allows(
            const battle_action_browser_entry& entry) const
    {
        if(entry.kind == battle_action_source_kind::ninja_tool)
        {
            return allow_ninja_tools;
        }
        if(entry.kind ==
                battle_action_source_kind::direct_attack)
        {
            return allow_direct_attack;
        }
        if(! restrict_active_actions)
        {
            return true;
        }
        for(std::size_t index = 0;
                index < allowed_active_action_count &&
                index < allowed_active_actions.size();
                ++index)
        {
            if(allowed_active_actions[index] == entry.action_id)
            {
                return true;
            }
        }
        return false;
    }
};

struct battle_action_menu_view
{
    std::uint8_t cost_scalar = 0;
    ability_id action_id = no_ability;
    std::uint8_t action_level = 0;
    std::uint8_t tool_slot = no_tool_slot;
    std::uint8_t effect_code = 0;
    action_error selection_error =
            action_error::invalid_definition;
    std::uint8_t requirement_reason_code = 0;
    std::uint8_t animation_family = 0;
    battle_action_source_kind kind : 2 =
            battle_action_source_kind::active_action;
    action_cost_kind cost_kind : 3 =
            action_cost_kind::none;
    target_policy_kind target_kind : 3 =
            target_policy_kind::
                    self_or_implicit_actor;

    [[nodiscard]] constexpr bool selectable() const
    {
        return selection_error == action_error::none;
    }
};

struct battle_command_menu_view
{
    command_rejection rejection =
            command_rejection::unit_inactive;
    battle_command_type type : 3 =
            battle_command_type::end_action;
    command_state state : 2 =
            command_state::hidden;

    [[nodiscard]] constexpr bool selectable() const
    {
        return state == command_state::available;
    }
};

struct battle_player_action_flow_snapshot
{
    battle_player_action_phase phase =
            battle_player_action_phase::inactive;
    std::uint8_t command_count = 0;
    std::uint8_t command_index = 0;
    std::array<battle_command_menu_view, 6>
            command_entries = {};
    battle_command_type selected_command =
            battle_command_type::end_action;
    command_rejection command_selection_error =
            command_rejection::unit_inactive;
    grid_point move_position = {};
    int move_cost = 0;
    bool movement_selection_confirmed = false;
    battle_resource_command_preview resource_preview = {};
    int action_count = 0;
    int action_index = 0;
    std::array<
            battle_action_menu_view,
            battle_action_catalog_capacity>
            action_entries = {};
    battle_action_source_kind selected_action_kind =
            battle_action_source_kind::active_action;
    ability_id selected_action_id = no_ability;
    std::uint8_t selected_action_tool_slot = no_tool_slot;
    action_error action_selection_error =
            action_error::invalid_definition;
    std::uint8_t combination_component_count = 0;
    battle_action_source_kind combination_first_kind =
            battle_action_source_kind::active_action;
    ability_id combination_first_action_id = no_ability;
    std::uint8_t combination_first_tool_slot = no_tool_slot;
    ability_id combination_result_action_id = no_ability;
    std::uint16_t combination_reserved_chakra = 0;
    bool combination_decision_selected = true;
    grid_point target_position = {};
    action_preview target_preview = {
        action_error::invalid_source,
    };
    int defense_action_count = 0;
    int defense_action_index = 0;
    defense_action_kind selected_defense_kind =
            defense_action_kind::none;
    ability_id selected_defense_action_id = no_ability;
    std::uint8_t selected_defense_tool_slot = no_tool_slot;
    defense_preparation_error defense_confirmation_error =
            defense_preparation_error::invalid_definition;
    battle_condition_outcome outcome =
            battle_condition_outcome::none;
    bool ends_battle = false;
};

template<std::size_t MaxUnits>
class battle_player_action_flow
{
public:
    [[nodiscard]] const battle_player_action_flow_snapshot&
    snapshot() const
    {
        return _state;
    }

    [[nodiscard]] battle_player_action_flow_result begin(
            const battle_session<MaxUnits>& session,
            const battle_command_access_policy&
                    command_access = {})
    {
        if(session.lifecycle() !=
                        battle_lifecycle::action_drafting ||
                ! session.draft().active)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _actions = {};
        _defense_actions = {};
        _commands = {};
        _command_access = command_access;
        _command_index = 0;
        _action_index = 0;
        _defense_index = 0;
        _clear_combination();
        _state = {};
        _state.move_position = session.draft().preview_position;
        _state.phase =
                battle_player_action_phase::command_selection;
        if(! _refresh_commands(session))
        {
            _state.phase =
                    battle_player_action_phase::inactive;
            return {
                battle_player_action_flow_error::
                        command_browser_failed,
            };
        }
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    cycle_command(int direction)
    {
        if(_state.phase !=
                        battle_player_action_phase::
                                command_selection ||
                direction == 0 || _commands.count == 0)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _command_index = _wrapped_index(
                _command_index,
                direction,
                static_cast<int>(_commands.count));
        _sync_command_selection();
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    select_command(battle_command_type type)
    {
        if(_state.phase !=
                battle_player_action_phase::command_selection)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        for(std::size_t index = 0;
                index < _commands.count; ++index)
        {
            if(_commands.entries[index].type == type)
            {
                _command_index =
                        static_cast<int>(index);
                _sync_command_selection();
                return {};
            }
        }
        return {
            battle_player_action_flow_error::
                    command_rejected,
        };
    }

    [[nodiscard]] battle_player_action_flow_result
    open_move_selection(
            const battle_session<MaxUnits>& session)
    {
        const battle_command_browser_entry* selected =
                _selected_command();
        if(_state.phase !=
                        battle_player_action_phase::
                                command_selection ||
                ! selected ||
                selected->type != battle_command_type::move)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        if(! selected->selectable())
        {
            return _command_rejected(
                    selected->availability.reason);
        }
        _state.phase =
                battle_player_action_phase::move_selection;
        _state.move_position = session.draft().origin;
        _state.move_cost = 0;
        return {};
    }

    template<int Width, int Height>
    [[nodiscard]] battle_player_action_flow_result
    preview_move(
            battle_session<MaxUnits>& session,
            const grid_map<Width, Height>& map,
            grid_point destination,
            pathfinder_workspace<Width, Height>& workspace)
    {
        if(_state.phase !=
                battle_player_action_phase::move_selection)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        const battle_unit_instance* unit =
                session.unit(session.draft().unit_id);
        if(! unit)
        {
            return {
                battle_player_action_flow_error::
                        move_rejected,
            };
        }
        if(destination == session.draft().origin)
        {
            if(session.preview_move(destination) !=
                    battle_transition::move_previewed)
            {
                return {
                    battle_player_action_flow_error::
                            move_rejected,
                };
            }
            _state.move_position = destination;
            _state.move_cost = 0;
            return {};
        }
        const path_result<
                static_cast<std::size_t>(Width * Height)> path =
                find_path<
                        Width,
                        Height,
                        static_cast<std::size_t>(
                                Width * Height)>(
                        map,
                        session.draft().origin,
                        destination,
                        unit->move_range,
                        battle_terrain_traversal_limits(
                                unit->passives),
                        workspace);
        if(! path.found ||
                session.preview_move(destination) !=
                        battle_transition::move_previewed)
        {
            return {
                battle_player_action_flow_error::
                        move_rejected,
            };
        }
        _state.move_position = destination;
        _state.move_cost = path.total_cost;
        return {};
    }

    template<int Width, int Height>
    [[nodiscard]] battle_player_action_flow_result
    preview_move(
            battle_session<MaxUnits>& session,
            const grid_map<Width, Height>& map,
            grid_point destination)
    {
        pathfinder_workspace<Width, Height> workspace;
        return preview_move(
                session, map, destination, workspace);
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_move_selection(
            battle_session<MaxUnits>& session)
    {
        if((_state.phase !=
                        battle_player_action_phase::move_selection &&
                ! (_state.phase == battle_player_action_phase::command_selection &&
                   _state.movement_selection_confirmed)) ||
                session.preview_move(session.draft().origin) !=
                        battle_transition::move_previewed)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _state.phase =
                battle_player_action_phase::command_selection;
        _state.move_position = session.draft().origin;
        _state.move_cost = 0;
        _state.movement_selection_confirmed = false;
        if(! _refresh_commands(
                   session, battle_command_type::move))
        {
            return {
                battle_player_action_flow_error::
                        command_browser_failed,
            };
        }
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_move_selection(
            const battle_session<MaxUnits>& session)
    {
        if(_state.phase !=
                battle_player_action_phase::move_selection)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        const battle_command_browser_result previous_commands =
                _commands;
        const int previous_command_index = _command_index;
        const battle_player_action_flow_snapshot previous_state =
                _state;
        if(_command_access.confirm_move_consumes_movement)
        {
            _state.movement_selection_confirmed = true;
        }
        if(! _refresh_commands(
                   session, battle_command_type::ability))
        {
            _commands = previous_commands;
            _command_index = previous_command_index;
            _state = previous_state;
            return {
                battle_player_action_flow_error::
                        command_browser_failed,
            };
        }
        _state.phase =
                battle_player_action_phase::command_selection;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    reopen_move_selection(
            battle_session<MaxUnits>& session)
    {
        if(_state.phase !=
                        battle_player_action_phase::
                                command_selection ||
                session.preview_move(session.draft().origin) !=
                        battle_transition::move_previewed)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _state.phase =
                battle_player_action_phase::move_selection;
        _state.move_position = session.draft().origin;
        _state.move_cost = 0;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_unit_action(
            battle_session<MaxUnits>& session)
    {
        if((_state.phase !=
                            battle_player_action_phase::
                                    move_selection &&
                   _state.phase !=
                            battle_player_action_phase::
                                    command_selection) ||
                session.cancel_action() !=
                        battle_transition::unit_selection_opened)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _commands = {};
        _state = {};
        _state.phase =
                battle_player_action_phase::inactive;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    open_chakra_selection(
            const battle_session<MaxUnits>& session)
    {
        const battle_command_browser_entry* selected =
                _selected_command();
        if(_state.phase !=
                        battle_player_action_phase::
                                command_selection ||
                ! selected ||
                selected->type !=
                        battle_command_type::
                                replenish_chakra)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        if(! selected->selectable())
        {
            return _command_rejected(
                    selected->availability.reason);
        }
        _state.resource_preview =
                battle_resource_commands::preview(
                        session,
                        battle_resource_command_type::
                                replenish_chakra,
                        1);
        if(! _state.resource_preview.legal())
        {
            return _resource_rejected(
                    _state.resource_preview.error);
        }
        _state.phase =
                battle_player_action_phase::chakra_selection;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    cycle_chakra_amount(
            const battle_session<MaxUnits>& session,
            int direction)
    {
        if(_state.phase !=
                        battle_player_action_phase::
                                chakra_selection ||
                direction == 0)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        const int next = _state.resource_preview.amount +
                (direction > 0 ? 1 : -1);
        const battle_resource_command_preview preview =
                battle_resource_commands::preview(
                        session,
                        battle_resource_command_type::
                                replenish_chakra,
                        next);
        if(! preview.legal())
        {
            return _resource_rejected(preview.error);
        }
        _state.resource_preview = preview;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_chakra_selection()
    {
        if(_state.phase !=
                battle_player_action_phase::chakra_selection)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _state.phase =
                battle_player_action_phase::command_selection;
        _state.resource_preview = {};
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_chakra(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions)
    {
        deterministic_rng rng(1);
        return confirm_chakra(session, conditions, rng);
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_chakra(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions,
            deterministic_rng& rng)
    {
        if(_state.phase !=
                battle_player_action_phase::chakra_selection)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        return _commit_resource(
                session,
                battle_resource_command_type::
                        replenish_chakra,
                _state.resource_preview.amount,
                conditions,
                rng);
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_chakra_in_place(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions)
    {
        deterministic_rng rng(1);
        return confirm_chakra_in_place(
                session, conditions, rng);
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_chakra_in_place(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions,
            deterministic_rng& rng,
            const battle_mission_objective& objective = {})
    {
        if(_state.phase !=
                battle_player_action_phase::chakra_selection)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        return _commit_resource_in_place(
                session,
                battle_resource_command_type::
                        replenish_chakra,
                _state.resource_preview.amount,
                conditions,
                rng,
                objective);
    }

    [[nodiscard]] battle_player_action_flow_result
    open_rest_confirmation(
            const battle_session<MaxUnits>& session)
    {
        const battle_command_browser_entry* selected =
                _selected_command();
        if(_state.phase !=
                        battle_player_action_phase::
                                command_selection ||
                ! selected ||
                selected->type != battle_command_type::rest)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        if(! selected->selectable())
        {
            return _command_rejected(
                    selected->availability.reason);
        }
        _state.resource_preview =
                battle_resource_commands::preview(
                        session,
                        battle_resource_command_type::rest);
        if(! _state.resource_preview.legal())
        {
            return _resource_rejected(
                    _state.resource_preview.error);
        }
        _state.phase =
                battle_player_action_phase::rest_confirmation;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_rest_confirmation()
    {
        if(_state.phase !=
                battle_player_action_phase::rest_confirmation)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _state.phase =
                battle_player_action_phase::command_selection;
        _state.resource_preview = {};
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_rest(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions)
    {
        deterministic_rng rng(1);
        return confirm_rest(session, conditions, rng);
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_rest(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions,
            deterministic_rng& rng)
    {
        if(_state.phase !=
                battle_player_action_phase::rest_confirmation)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        return _commit_resource(
                session,
                battle_resource_command_type::rest,
                1,
                conditions,
                rng);
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_rest_in_place(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions)
    {
        deterministic_rng rng(1);
        return confirm_rest_in_place(
                session, conditions, rng);
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_rest_in_place(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions,
            deterministic_rng& rng,
            const battle_mission_objective& objective = {})
    {
        if(_state.phase !=
                battle_player_action_phase::rest_confirmation)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        return _commit_resource_in_place(
                session,
                battle_resource_command_type::rest,
                1,
                conditions,
                rng,
                objective);
    }

    [[nodiscard]] battle_player_action_flow_result
    open_action_selection(
            const battle_session<MaxUnits>& session,
            const battle_action_access_policy& access = {},
            ability_id preferred_action = no_ability,
            const battle_capture_policy& capture_policy = {})
    {
        const battle_command_browser_entry* command =
                _selected_command();
        if(_state.phase !=
                        battle_player_action_phase::
                                command_selection ||
                ! command ||
                command->type != battle_command_type::ability)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        if(! command->selectable())
        {
            return _command_rejected(
                    command->availability.reason);
        }
        const battle_action_browser_result available =
                battle_action_browser::build(session);
        if(available.error != battle_action_browser_error::none)
        {
            return {
                battle_player_action_flow_error::
                        action_browser_failed,
            };
        }

        _actions = {};
        _clear_combination();
        for(std::size_t index = 0;
                index < available.count;
                ++index)
        {
            battle_action_browser_entry entry =
                    available.entries[index];
            if(access.allows(entry))
            {
                entry.action =
                        capture_policy.transform(
                                entry.action);
                _actions.entries[_actions.count] = entry;
                ++_actions.count;
            }
        }
        if(_actions.count == 0)
        {
            return {
                battle_player_action_flow_error::
                        action_browser_failed,
            };
        }

        _action_index = 0;
        if(preferred_action != no_ability)
        {
            for(std::size_t index = 0;
                    index < _actions.count;
                    ++index)
            {
                if(_actions.entries[index].action_id ==
                        preferred_action)
                {
                    _action_index = static_cast<int>(index);
                    break;
                }
            }
        }
        _state.phase =
                battle_player_action_phase::action_selection;
        _sync_action_selection();
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    open_direct_attack_targeting(
            const battle_session<MaxUnits>& session,
            const battle_action_access_policy& access = {})
    {
        const battle_command_browser_entry* command =
                _selected_command();
        if(_state.phase !=
                        battle_player_action_phase::
                                command_selection ||
                ! command ||
                command->type !=
                        battle_command_type::direct_attack)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        if(! command->selectable())
        {
            return _command_rejected(
                    command->availability.reason);
        }
        if(! access.allow_direct_attack)
        {
            return {
                battle_player_action_flow_error::
                        action_rejected,
                action_error::mission_restricted,
            };
        }
        if(session.lifecycle() !=
                        battle_lifecycle::action_drafting ||
                ! session.draft().active)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }

        _actions = {};
        _clear_combination();
        _actions.entries[0] = {
            battle_action_source_kind::direct_attack,
            direct_attack_ability_id,
            0,
            no_tool_slot,
            direct_attack_definition,
            action_error::none,
            0,
        };
        _actions.count = 1;
        _action_index = 0;
        _state.phase =
                battle_player_action_phase::target_selection;
        _state.target_position =
                session.draft().preview_position;
        _state.target_preview = {
            action_error::invalid_target,
        };
        _sync_action_selection();
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    cycle_action(int direction)
    {
        if(_state.phase !=
                        battle_player_action_phase::action_selection ||
                direction == 0 || _actions.count == 0)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _action_index = _wrapped_index(
                _action_index,
                direction,
                static_cast<int>(_actions.count));
        _sync_action_selection();
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_action_selection()
    {
        if(_state.phase !=
                battle_player_action_phase::action_selection)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        if(_state.combination_component_count == 1)
        {
            _clear_combination();
            _sync_action_selection();
            return {};
        }
        _state.phase =
                battle_player_action_phase::command_selection;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_action_selection(
            const battle_session<MaxUnits>& session)
    {
        const battle_action_browser_entry* selected =
                _selected_action();
        if(_state.phase !=
                        battle_player_action_phase::action_selection ||
                ! selected)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        if(! selected->selectable())
        {
            return {
                battle_player_action_flow_error::action_rejected,
                selected->selection_error,
            };
        }
        if(_state.combination_component_count == 0 &&
                battle_action_combinations::can_start(
                        _component(*selected),
                        selected->action))
        {
            _combination_first = *selected;
            if(! battle_action_combinations::requires_follow(
                       _component(*selected),
                       selected->action))
            {
                _state.combination_decision_selected =
                        true;
                _state.phase =
                        battle_player_action_phase::
                                combination_decision;
                return {};
            }
            _stage_combination_first();
            return {};
        }
        if(_state.combination_component_count == 1)
        {
            _combination = battle_action_combinations::compose(
                    _component(_combination_first),
                    _combination_first.action,
                    _component(*selected),
                    selected->action);
            if(! _combination.valid())
            {
                return {
                    battle_player_action_flow_error::
                            action_rejected,
                    action_error::invalid_definition,
                };
            }
            const action_preview checked =
                    battle_action_combinations::preview(
                            session,
                            _combination,
                            session.draft().preview_position);
            if(checked.error ==
                            action_error::insufficient_chakra ||
                    checked.error ==
                            action_error::insufficient_hp ||
                    checked.error ==
                            action_error::
                                    missing_ninja_tool)
            {
                return {
                    battle_player_action_flow_error::
                            action_rejected,
                    checked.error,
                };
            }
            _state.combination_component_count = 2;
            _state.combination_result_action_id =
                    _combination.result.id;
        }
        _state.phase =
                battle_player_action_phase::target_selection;
        _state.target_preview = {
            action_error::invalid_target,
        };
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    cycle_combination_decision(int direction)
    {
        if(_state.phase !=
                        battle_player_action_phase::
                                combination_decision ||
                direction == 0)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _state.combination_decision_selected =
                ! _state.combination_decision_selected;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_combination_decision()
    {
        if(_state.phase !=
                battle_player_action_phase::
                        combination_decision)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        if(_state.combination_decision_selected)
        {
            _stage_combination_first();
            _state.phase =
                    battle_player_action_phase::
                            action_selection;
        }
        else
        {
            _combination_first = {};
            _state.phase =
                    battle_player_action_phase::
                            target_selection;
            _state.target_preview = {
                action_error::invalid_target,
            };
        }
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_combination_decision()
    {
        if(_state.phase !=
                battle_player_action_phase::
                        combination_decision)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _combination_first = {};
        _state.combination_decision_selected = true;
        _state.phase =
                battle_player_action_phase::
                        action_selection;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result preview_target(
            const battle_session<MaxUnits>& session,
            grid_point target_position)
    {
        const battle_action_browser_entry* selected =
                _selected_action();
        if(_state.phase !=
                        battle_player_action_phase::target_selection ||
                ! selected)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _state.target_position = target_position;
        _state.target_preview =
                _state.combination_component_count == 2 ?
                battle_action_combinations::preview(
                        session,
                        _combination,
                        target_position) :
                battle_action_execution::preview(
                        session,
                        selected->action,
                        target_position);
        if(! _state.target_preview.legal())
        {
            return {
                battle_player_action_flow_error::action_rejected,
                _state.target_preview.error,
            };
        }
        return {};
    }

    [[nodiscard]] int target_maximum_distance() const
    {
        if(_state.phase !=
                battle_player_action_phase::target_selection)
        {
            return -1;
        }
        if(_state.combination_component_count == 2 &&
                _combination.valid())
        {
            return _combination.result.range.maximum_distance();
        }
        const battle_action_browser_entry* selected =
                _selected_action();
        return selected ?
                selected->action.range.maximum_distance() :
                -1;
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_target_selection()
    {
        if(_state.phase !=
                battle_player_action_phase::target_selection)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _state.phase =
                battle_player_action_phase::action_selection;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result confirm_target(
            battle_session<MaxUnits>& session,
            grid_point target_position,
            deterministic_rng& rng,
            const battle_condition_variant& conditions,
            const battle_capture_policy& capture_policy = {})
    {
        battle_session<MaxUnits> next = session;
        const battle_player_action_flow_result result =
                confirm_target_in_place(
                        next,
                        target_position,
                        rng,
                        conditions,
                        capture_policy);
        if(result.success())
        {
            session = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_target_in_place(
            battle_session<MaxUnits>& session,
            grid_point target_position,
            deterministic_rng& rng,
            const battle_condition_variant& conditions,
            const battle_capture_policy& capture_policy = {})
    {
        const battle_action_browser_entry* selected =
                _selected_action();
        if(_state.phase !=
                        battle_player_action_phase::target_selection ||
                ! selected)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }

        const action_result resolved =
                _state.combination_component_count == 2 ?
                battle_action_combinations::resolve(
                        session,
                        _combination,
                        target_position,
                        rng) :
                battle_action_execution::resolve_in_place(
                        session,
                        selected->action,
                        target_position,
                        rng);
        if(! resolved.success())
        {
            _state.target_position = target_position;
            _state.target_preview = {
                resolved.error,
            };
            return {
                battle_player_action_flow_error::action_rejected,
                resolved.error,
            };
        }
        const battle_capture_summary captured =
                battle_capture_system::apply(
                        session,
                        capture_policy,
                        _capture_source(*selected),
                        resolved);
        const battle_turn_flow_result tail =
                battle_turn_flow::after_effects_in_place(
                        session, conditions);
        if(tail.error != battle_turn_flow_error::none)
        {
            return {
                battle_player_action_flow_error::
                        turn_flow_failed,
                action_error::none,
                defense_preparation_error::none,
                tail.error,
                tail.outcome,
                tail.ends_battle,
            };
        }
        _state.target_position = target_position;
        _state.outcome = tail.outcome;
        _state.ends_battle = tail.ends_battle;
        _state.phase = tail.ends_battle ?
                battle_player_action_phase::outcome :
                battle_player_action_phase::facing_selection;
        battle_player_action_flow_result result = {
            battle_player_action_flow_error::none,
            action_error::none,
            defense_preparation_error::none,
            battle_turn_flow_error::none,
            tail.outcome,
            tail.ends_battle,
        };
        result.affected_unit_ids =
                resolved.affected_unit_ids;
        result.affected_unit_count =
                resolved.affected_unit_count;
        result.affected_units_truncated =
                resolved.affected_units_truncated;
        result.impact_count = resolved.generated_hits;
        result.capture_count = captured.count;
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result end_without_action(
            battle_session<MaxUnits>& session)
    {
        const battle_command_browser_entry* command =
                _selected_command();
        if(_state.phase !=
                        battle_player_action_phase::
                                command_selection ||
                ! command ||
                command->type !=
                        battle_command_type::end_action)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        if(! command->selectable())
        {
            return _command_rejected(
                    command->availability.reason);
        }
        if(
                session.open_facing_selection() !=
                        battle_transition::facing_selection_opened)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _state.phase =
                battle_player_action_phase::facing_selection;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result select_facing(
            battle_session<MaxUnits>& session,
            battle_facing facing)
    {
        if(_state.phase !=
                        battle_player_action_phase::facing_selection ||
                session.select_facing(facing) !=
                        battle_transition::defense_selection_opened)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _state.phase =
                battle_player_action_phase::defense_decision;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    open_defense_selection(
            const battle_session<MaxUnits>& session)
    {
        if(_state.phase !=
                battle_player_action_phase::defense_decision)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _defense_actions =
                battle_defense_browser::build(session);
        if(_defense_actions.error !=
                            battle_defense_browser_error::none ||
                _defense_actions.count == 0)
        {
            return {
                battle_player_action_flow_error::
                        defense_browser_failed,
            };
        }
        _defense_index = 0;
        _state.phase =
                battle_player_action_phase::defense_selection;
        _sync_defense_selection();
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_defense_decision(
            battle_session<MaxUnits>& session)
    {
        if(_state.phase !=
                        battle_player_action_phase::
                                defense_decision ||
                session.reopen_facing_selection() !=
                        battle_transition::
                                facing_selection_opened)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _state.phase =
                battle_player_action_phase::facing_selection;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    cycle_defense_action(int direction)
    {
        if(_state.phase !=
                        battle_player_action_phase::defense_selection ||
                direction == 0 || _defense_actions.count == 0)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _defense_index = _wrapped_index(
                _defense_index,
                direction,
                static_cast<int>(_defense_actions.count));
        _sync_defense_selection();
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_defense_selection()
    {
        if(_state.phase !=
                battle_player_action_phase::defense_selection)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        _state.phase =
                battle_player_action_phase::defense_decision;
        return {};
    }

    [[nodiscard]] battle_player_action_flow_result
    complete_without_defense(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions)
    {
        deterministic_rng rng(1);
        return complete_without_defense(
                session, conditions, rng);
    }

    [[nodiscard]] battle_player_action_flow_result
    complete_without_defense(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions,
            deterministic_rng& rng)
    {
        if(_state.phase !=
                battle_player_action_phase::defense_decision)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        return _finish(
                session,
                battle_turn_flow::complete_defense(
                        session,
                        no_ability,
                        conditions,
                        rng));
    }

    [[nodiscard]] battle_player_action_flow_result
    complete_without_defense_in_place(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions)
    {
        deterministic_rng rng(1);
        return complete_without_defense_in_place(
                session, conditions, rng);
    }

    [[nodiscard]] battle_player_action_flow_result
    complete_without_defense_in_place(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions,
            deterministic_rng& rng,
            const battle_mission_objective& objective = {})
    {
        if(_state.phase !=
                battle_player_action_phase::defense_decision)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        return _finish(
                session,
                battle_turn_flow::complete_defense_in_place(
                        session,
                        no_ability,
                        conditions,
                        rng,
                        objective));
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_defense_action(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions)
    {
        deterministic_rng rng(1);
        return confirm_defense_action(
                session, conditions, rng);
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_defense_action(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions,
            deterministic_rng& rng)
    {
        const battle_defense_browser_entry* selected =
                _selected_defense();
        if(_state.phase !=
                        battle_player_action_phase::defense_selection ||
                ! selected)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        if(! selected->confirmable())
        {
            return {
                battle_player_action_flow_error::defense_rejected,
                action_error::none,
                selected->confirmation_error,
            };
        }
        return _finish(
                session,
                battle_turn_flow::complete_defense(
                        session,
                        selected->action,
                        conditions,
                        rng));
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_defense_action_in_place(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions)
    {
        deterministic_rng rng(1);
        return confirm_defense_action_in_place(
                session, conditions, rng);
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_defense_action_in_place(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions,
            deterministic_rng& rng,
            const battle_mission_objective& objective = {})
    {
        const battle_defense_browser_entry* selected =
                _selected_defense();
        if(_state.phase !=
                        battle_player_action_phase::defense_selection ||
                ! selected)
        {
            return {
                battle_player_action_flow_error::invalid_phase,
            };
        }
        if(! selected->confirmable())
        {
            return {
                battle_player_action_flow_error::defense_rejected,
                action_error::none,
                selected->confirmation_error,
            };
        }
        return _finish(
                session,
                battle_turn_flow::complete_defense_in_place(
                        session,
                        selected->action,
                        conditions,
                        rng,
                        objective));
    }

private:
    [[nodiscard]] static int _wrapped_index(
            int current, int direction, int count)
    {
        int next = current + (direction > 0 ? 1 : -1);
        if(next < 0)
        {
            next = count - 1;
        }
        else if(next >= count)
        {
            next = 0;
        }
        return next;
    }

    [[nodiscard]] const battle_command_browser_entry*
    _selected_command() const
    {
        return _command_index >= 0 &&
                       _command_index <
                               static_cast<int>(_commands.count) ?
                &_commands.entries[
                        static_cast<std::size_t>(
                                _command_index)] :
                nullptr;
    }

    [[nodiscard]] bool _refresh_commands(
            const battle_session<MaxUnits>& session,
            battle_command_type preferred =
                    battle_command_type::move)
    {
        _commands = battle_command_browser::build(
                session,
                _command_access,
                _state.movement_selection_confirmed);
        if(_commands.error !=
                            battle_command_browser_error::none ||
                _commands.count == 0)
        {
            return false;
        }
        _command_index = 0;
        for(std::size_t index = 0;
                index < _commands.count; ++index)
        {
            if(_commands.entries[index].type == preferred)
            {
                _command_index =
                        static_cast<int>(index);
                break;
            }
        }
        _sync_command_selection();
        return true;
    }

    void _sync_command_selection()
    {
        _state.command_count =
                static_cast<int>(_commands.count);
        _state.command_index = _command_index;
        _state.command_entries = {};
        for(std::size_t index = 0;
                index < _commands.count &&
                index < _state.command_entries.size();
                ++index)
        {
            const battle_command_browser_entry& source =
                    _commands.entries[index];
            _state.command_entries[index] =
                    battle_command_menu_view{
                source.availability.reason,
                source.type,
                source.availability.state,
            };
        }
        const battle_command_browser_entry* selected =
                _selected_command();
        if(! selected)
        {
            _state.selected_command =
                    battle_command_type::end_action;
            _state.command_selection_error =
                    command_rejection::unit_inactive;
            return;
        }
        _state.selected_command = selected->type;
        _state.command_selection_error =
                selected->availability.reason;
    }

    [[nodiscard]] static battle_player_action_flow_result
    _command_rejected(command_rejection rejection)
    {
        battle_player_action_flow_result result;
        result.error =
                battle_player_action_flow_error::
                        command_rejected;
        result.command_error = rejection;
        return result;
    }

    [[nodiscard]] static battle_player_action_flow_result
    _resource_rejected(
            battle_resource_command_error rejection)
    {
        battle_player_action_flow_result result;
        result.error =
                battle_player_action_flow_error::
                        resource_rejected;
        result.resource_error = rejection;
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    _commit_resource(
            battle_session<MaxUnits>& session,
            battle_resource_command_type type,
            int amount,
            const battle_condition_variant& conditions,
            deterministic_rng& rng)
    {
        battle_session<MaxUnits> next = session;
        const battle_player_action_flow_result result =
                _commit_resource_in_place(
                        next,
                        type,
                        amount,
                        conditions,
                        rng);
        if(result.success())
        {
            session = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    _commit_resource_in_place(
            battle_session<MaxUnits>& session,
            battle_resource_command_type type,
            int amount,
            const battle_condition_variant& conditions,
            deterministic_rng& rng,
            const battle_mission_objective& objective = {})
    {
        static_cast<void>(rng);
        static_cast<void>(objective);
        const battle_resource_command_preview committed =
                battle_resource_commands::commit_in_place(
                        session, type, amount);
        if(! committed.legal())
        {
            return _resource_rejected(committed.error);
        }
        const battle_condition_result condition =
                battle_condition_interpreter::evaluate_session(
                        session, conditions);
        if(condition.error != battle_condition_error::none)
        {
            return {
                battle_player_action_flow_error::
                        turn_flow_failed,
                action_error::none,
                defense_preparation_error::none,
                battle_turn_flow_error::condition_error,
            };
        }
        const bool ends_battle = condition.ends_battle;
        if(! ends_battle &&
                session.open_facing_selection() !=
                        battle_transition::
                                facing_selection_opened)
        {
            return {
                battle_player_action_flow_error::
                        turn_flow_failed,
                action_error::none,
                defense_preparation_error::none,
                battle_turn_flow_error::invalid_phase,
            };
        }
        _state.resource_preview = committed;
        _state.outcome = condition.outcome;
        _state.ends_battle = ends_battle;
        _state.phase = ends_battle ?
                battle_player_action_phase::outcome :
                battle_player_action_phase::facing_selection;
        battle_player_action_flow_result result = {
            battle_player_action_flow_error::none,
            action_error::none,
            defense_preparation_error::none,
            battle_turn_flow_error::none,
            condition.outcome,
            ends_battle,
        };
        return result;
    }

    [[nodiscard]] const battle_action_browser_entry*
    _selected_action() const
    {
        return _action_index >= 0 &&
                       _action_index <
                               static_cast<int>(_actions.count) ?
                &_actions.entries[
                        static_cast<std::size_t>(_action_index)] :
                nullptr;
    }

    [[nodiscard]] static battle_action_component _component(
            const battle_action_browser_entry& entry)
    {
        return {
            entry.kind ==
                            battle_action_source_kind::
                                    ninja_tool ?
                    battle_action_component_kind::ninja_tool :
                    battle_action_component_kind::
                            active_action,
            entry.action_id,
            entry.tool_slot,
        };
    }

    [[nodiscard]] static constexpr battle_action_source_kind
    _source_kind(battle_action_component_kind kind)
    {
        return kind ==
                               battle_action_component_kind::
                                       ninja_tool ?
                battle_action_source_kind::ninja_tool :
                battle_action_source_kind::active_action;
    }

    [[nodiscard]] battle_capture_source _capture_source(
            const battle_action_browser_entry& selected) const
    {
        if(_state.combination_component_count != 2)
        {
            return battle_capture_source::single(
                    selected.kind);
        }
        return {
            {
                _source_kind(_combination.components[0].kind),
                _source_kind(_combination.components[1].kind),
            },
            2,
        };
    }

    void _clear_combination()
    {
        _combination = {};
        _combination_first = {};
        _state.combination_component_count = 0;
        _state.combination_first_kind =
                battle_action_source_kind::active_action;
        _state.combination_first_action_id = no_ability;
        _state.combination_first_tool_slot = no_tool_slot;
        _state.combination_result_action_id = no_ability;
        _state.combination_reserved_chakra = 0;
        _state.combination_decision_selected = true;
    }

    void _stage_combination_first()
    {
        _state.combination_component_count = 1;
        _state.combination_first_kind =
                _combination_first.kind;
        _state.combination_first_action_id =
                _combination_first.action_id;
        _state.combination_first_tool_slot =
                _combination_first.tool_slot;
        _state.combination_reserved_chakra =
                _combination_first.action.cost.kind ==
                                action_cost_kind::
                                        current_chakra ?
                        _combination_first.action.cost.scalar :
                        0;
        _sync_action_selection();
    }

    [[nodiscard]] const battle_defense_browser_entry*
    _selected_defense() const
    {
        return _defense_index >= 0 &&
                       _defense_index <
                               static_cast<int>(
                                       _defense_actions.count) ?
                &_defense_actions.entries[
                        static_cast<std::size_t>(
                                _defense_index)] :
                nullptr;
    }

    void _sync_action_selection()
    {
        _state.action_count = static_cast<int>(_actions.count);
        _state.action_index = _action_index;
        _state.action_entries = {};
        for(std::size_t index = 0;
                index < _actions.count; ++index)
        {
            const battle_action_browser_entry& source =
                    _actions.entries[index];
            action_error selection_error =
                    source.selection_error;
            if(selection_error == action_error::none &&
                    _state.combination_component_count == 1 &&
                    ! battle_action_combinations::can_follow(
                            _component(source),
                            source.action))
            {
                selection_error =
                        action_error::invalid_definition;
            }
            _state.action_entries[index] =
                    battle_action_menu_view{
                static_cast<std::uint8_t>(
                        source.action.cost.scalar),
                source.action_id,
                source.action_level,
                source.tool_slot,
                source.action.effect.code,
                selection_error,
                source.requirement_reason_code,
                source.action.presentation.animation_family,
                source.kind,
                source.action.cost.kind,
                source.action.target.kind,
            };
        }
        const battle_action_browser_entry* selected =
                _selected_action();
        if(! selected)
        {
            _state.selected_action_id = no_ability;
            _state.action_selection_error =
                    action_error::invalid_definition;
            return;
        }
        _state.selected_action_kind = selected->kind;
        _state.selected_action_id = selected->action_id;
        _state.selected_action_tool_slot = selected->tool_slot;
        _state.action_selection_error =
                _state.action_entries[
                        static_cast<std::size_t>(
                                _action_index)]
                        .selection_error;
    }

    void _sync_defense_selection()
    {
        _state.defense_action_count =
                static_cast<int>(_defense_actions.count);
        _state.defense_action_index = _defense_index;
        const battle_defense_browser_entry* selected =
                _selected_defense();
        if(! selected)
        {
            _state.selected_defense_kind =
                    defense_action_kind::none;
            _state.selected_defense_action_id = no_ability;
            _state.selected_defense_tool_slot = no_tool_slot;
            _state.defense_confirmation_error =
                    defense_preparation_error::
                            invalid_definition;
            return;
        }
        _state.selected_defense_kind = selected->kind;
        _state.selected_defense_action_id =
                selected->action_id;
        _state.selected_defense_tool_slot =
                selected->tool_slot;
        _state.defense_confirmation_error =
                selected->confirmation_error;
    }

    [[nodiscard]] battle_player_action_flow_result _finish(
            battle_session<MaxUnits>&,
            const battle_turn_flow_result& result)
    {
        if(result.error != battle_turn_flow_error::none)
        {
            return {
                battle_player_action_flow_error::
                        turn_flow_failed,
                action_error::none,
                defense_preparation_error::none,
                result.error,
                result.outcome,
                result.ends_battle,
            };
        }
        _state.outcome = result.outcome;
        _state.ends_battle = result.ends_battle;
        _state.phase = result.ends_battle ?
                battle_player_action_phase::outcome :
                battle_player_action_phase::completed;
        battle_player_action_flow_result completed = {
            battle_player_action_flow_error::none,
            action_error::none,
            defense_preparation_error::none,
            battle_turn_flow_error::none,
            result.outcome,
            result.ends_battle,
        };
        completed.object_event_count =
                result.object_event_count;
        completed.object_effects =
                result.object_effects;
        return completed;
    }

    battle_player_action_flow_snapshot _state;
    battle_action_browser_entry _combination_first = {};
    battle_combination_action _combination = {};
    battle_command_browser_result _commands;
    battle_command_access_policy _command_access;
    int _command_index = 0;
    battle_action_browser_result _actions;
    battle_defense_browser_result _defense_actions;
    int _action_index = 0;
    int _defense_index = 0;
};

}

#endif
