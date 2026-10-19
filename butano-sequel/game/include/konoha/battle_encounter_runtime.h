#ifndef KONOHA_BATTLE_ENCOUNTER_RUNTIME_H
#define KONOHA_BATTLE_ENCOUNTER_RUNTIME_H

#include "konoha/battle_ai_turn_flow.h"
#include "konoha/battle_map_loader.h"
#include "konoha/battle_mission_rules.h"
#include "konoha/battle_material_pickups.h"
#include "konoha/battle_player_action_flow.h"
#include "konoha/battle_scenario_loader.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_encounter_load_error : std::uint8_t
{
    none,
    scenario_load_failed,
    map_load_failed,
    formation_invalid,
    mission_objective_invalid,
};

struct battle_encounter_load_result
{
    battle_encounter_load_error error =
            battle_encounter_load_error::none;
    battle_scenario_load_error scenario_error =
            battle_scenario_load_error::none;
    battle_map_load_error map_error =
            battle_map_load_error::none;
    battle_mission_objective_error objective_error =
            battle_mission_objective_error::none;

    [[nodiscard]] constexpr bool success() const
    {
        return error == battle_encounter_load_error::none;
    }
};

template<std::size_t MaxUnits, int Width, int Height>
struct battle_encounter_load_workspace
{
    battle_session<MaxUnits> session;
    grid_map<Width, Height> terrain;
    grid_map<Width, Height> movement;
};

template<std::size_t MaxUnits>
struct battle_encounter_transaction_workspace
{
    battle_session<MaxUnits> session;
    battle_player_action_flow<MaxUnits> player_flow;
};

template<std::size_t MaxUnits, int Width, int Height>
class battle_encounter_runtime
{
public:
    template<std::size_t CellCount>
    [[nodiscard]] battle_encounter_load_result load(
            const battle_scenario_definition& scenario,
            const battle_map_definition& map_definition,
            const std::array<battle_map_cell, CellCount>& map_cells,
            std::uint8_t variant,
            const battle_scenario_load_policy& load_policy,
            const battle_condition_variant& conditions,
            std::uint32_t rng_seed,
            const character_progression_record*
                    progression_records = nullptr,
            std::size_t progression_record_count = 0,
            battle_mission_rules mission_rules = {},
            battle_campaign_inventory inventory = {})
    {
        battle_encounter_load_workspace<
                MaxUnits, Width, Height>& workspace =
                _load_workspace;
        const battle_scenario_load_result scenario_result =
                load_battle_scenario_into_empty(
                        scenario,
                        variant,
                        load_policy,
                        workspace.session,
                        progression_records,
                        progression_record_count);
        if(scenario_result.error !=
                battle_scenario_load_error::none)
        {
            return {
                battle_encounter_load_error::
                        scenario_load_failed,
                scenario_result.error,
            };
        }

        const battle_map_load_error map_result =
                materialize_battle_map(
                        map_definition,
                        map_cells,
                        workspace.terrain);
        if(map_result != battle_map_load_error::none)
        {
            return {
                battle_encounter_load_error::
                        map_load_failed,
                battle_scenario_load_error::none,
                map_result,
            };
        }

        workspace.movement = workspace.terrain;
        const battle_map_load_error formation_result =
                apply_battle_occupancy(
                        workspace.session,
                        workspace.movement);
        if(formation_result != battle_map_load_error::none)
        {
            return {
                battle_encounter_load_error::
                        formation_invalid,
                battle_scenario_load_error::none,
                formation_result,
            };
        }
        if(! workspace.session.configure_battlefield(
                   workspace.terrain))
        {
            return {
                battle_encounter_load_error::
                        map_load_failed,
                battle_scenario_load_error::none,
                battle_map_load_error::
                        content_out_of_bounds,
            };
        }
        const battle_mission_objective_error
                objective_error =
                        battle_mission_objective_system::
                                initialize(
                                        workspace.session,
                                        mission_rules
                                                .objective);
        if(objective_error !=
                battle_mission_objective_error::none)
        {
            return {
                battle_encounter_load_error::
                        mission_objective_invalid,
                battle_scenario_load_error::none,
                battle_map_load_error::none,
                objective_error,
            };
        }

        if(! battle_material_pickups::initialize(workspace.session,
                    scenario.battle_id, variant))
        {
            return {battle_encounter_load_error::mission_objective_invalid};
        }
        _inventory = inventory;
        _pickup = {};
        _session = workspace.session;
        _terrain = workspace.terrain;
        _player_flow = {};
        _conditions = conditions;
        _mission_rules = mission_rules;
        _rng = deterministic_rng(rng_seed);
        _loaded = true;
        return {};
    }

    [[nodiscard]] const battle_campaign_inventory& inventory() const { return _inventory; }
    [[nodiscard]] battle_material_pickup last_pickup() const { return _pickup; }

    [[nodiscard]] bool loaded() const
    {
        return _loaded;
    }

    [[nodiscard]] const battle_session<MaxUnits>& session() const
    {
        return _session;
    }

    [[nodiscard]] const grid_map<Width, Height>& terrain() const
    {
        return _terrain;
    }

    [[nodiscard]] const battle_condition_variant& conditions() const
    {
        return _conditions;
    }

    [[nodiscard]] const battle_player_action_flow_snapshot&
    player_snapshot() const
    {
        return _player_flow.snapshot();
    }

    [[nodiscard]] battle_transition start()
    {
        if(! _loaded)
        {
            return battle_transition::invalid;
        }
        battle_session<MaxUnits>& next =
                _transaction_session();
        const battle_transition result = next.start_round();
        if(result == battle_transition::unit_selection_opened)
        {
            _session = next;
        }
        return result;
    }

    [[nodiscard]] battle_map_load_error movement_map(
            grid_map<Width, Height>& destination) const
    {
        if(! _loaded)
        {
            return battle_map_load_error::content_out_of_bounds;
        }
        grid_map<Width, Height> candidate = _terrain;
        const battle_map_load_error result =
                apply_battle_occupancy(_session, candidate);
        if(result == battle_map_load_error::none)
        {
            destination = candidate;
        }
        return result;
    }

    [[nodiscard]] const battle_unit_instance* cycle_roster_unit(
            battle_unit_id current,
            int direction) const
    {
        return _session.cycle_roster_unit(current, direction);
    }

    [[nodiscard]] battle_unit_id first_available_unit(
            battle_side side) const
    {
        if(_session.current_side() != side)
        {
            return no_battle_unit;
        }
        for(std::size_t index = 0;
                index < _session.unit_count(); ++index)
        {
            const battle_unit_instance* unit =
                    _session.unit_at(index);
            if(unit && unit->side == side &&
                    _session.can_issue_commands(unit->id))
            {
                return unit->id;
            }
        }
        return no_battle_unit;
    }

    [[nodiscard]] battle_unit_id first_available_unit(
            battle_side side,
            battle_control control) const
    {
        if(_session.current_side() != side)
        {
            return no_battle_unit;
        }
        for(std::size_t index = 0;
                index < _session.unit_count();
                ++index)
        {
            const battle_unit_instance* unit =
                    _session.unit_at(index);
            if(unit && unit->side == side &&
                    unit->control == control &&
                    _session.can_issue_commands(unit->id))
            {
                return unit->id;
            }
        }
        return no_battle_unit;
    }

    [[nodiscard]] battle_player_action_flow_result
    begin_player_unit(
            battle_unit_id unit_id,
            const battle_command_access_policy&
                    command_access = {})
    {
        battle_session<MaxUnits>& next_session =
                _transaction_session();
        battle_player_action_flow<MaxUnits>& next_flow =
                _transaction_player_flow();
        if(next_session.select_unit(unit_id) !=
                battle_transition::action_draft_opened)
        {
            return {
                battle_player_action_flow_error::
                        invalid_phase,
            };
        }
        const battle_player_action_flow_result result =
                next_flow.begin(next_session, command_access);
        if(result.success())
        {
            _session = next_session;
            _player_flow = next_flow;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    cycle_command(int direction)
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.cycle_command(direction);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    select_command(battle_command_type type)
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.select_command(type);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    open_move_selection()
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.open_move_selection(_session);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    preview_move(grid_point destination)
    {
        _movement_map_workspace = _terrain;
        if(apply_battle_occupancy(
                   _session,
                   _movement_map_workspace) !=
                battle_map_load_error::none)
        {
            return {
                battle_player_action_flow_error::
                        move_rejected,
            };
        }
        battle_session<MaxUnits>& next_session =
                _transaction_session();
        battle_player_action_flow<MaxUnits>& next_flow =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next_flow.preview_move(
                        next_session,
                        _movement_map_workspace,
                        destination,
                        _path_workspace);
        if(result.success())
        {
            _session = next_session;
            _player_flow = next_flow;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_move_selection()
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.confirm_move_selection(_session);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    reopen_move_selection()
    {
        battle_session<MaxUnits>& next_session =
                _transaction_session();
        battle_player_action_flow<MaxUnits>& next_flow =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next_flow.reopen_move_selection(
                        next_session);
        if(result.success())
        {
            _session = next_session;
            _player_flow = next_flow;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_move_selection()
    {
        battle_session<MaxUnits>& next_session =
                _transaction_session();
        battle_player_action_flow<MaxUnits>& next_flow =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next_flow.cancel_move_selection(next_session);
        if(result.success())
        {
            _session = next_session;
            _player_flow = next_flow;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_unit_action()
    {
        battle_session<MaxUnits>& next_session =
                _transaction_session();
        battle_player_action_flow<MaxUnits>& next_flow =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next_flow.cancel_unit_action(
                        next_session);
        if(result.success())
        {
            _session = next_session;
            _player_flow = next_flow;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    open_action_selection(
            const battle_action_access_policy& access = {},
            ability_id preferred_action = no_ability)
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.open_action_selection(
                        _session,
                        access,
                        preferred_action,
                        _mission_rules.capture);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    open_direct_attack_targeting(
            const battle_action_access_policy& access = {})
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.open_direct_attack_targeting(
                        _session, access);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    open_chakra_selection()
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.open_chakra_selection(_session);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    cycle_chakra_amount(int direction)
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.cycle_chakra_amount(
                        _session, direction);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_chakra_selection()
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.cancel_chakra_selection();
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_chakra()
    {
        battle_session<MaxUnits>& next_session =
                _transaction_session();
        battle_player_action_flow<MaxUnits>& next_flow =
                _transaction_player_flow();
        deterministic_rng next_rng = _rng;
        const battle_player_action_flow_result result =
                next_flow.confirm_chakra_in_place(
                        next_session,
                        _conditions,
                        next_rng,
                        _mission_rules.objective);
        if(result.success())
        {
            _session = next_session;
            _player_flow = next_flow;
            _rng = next_rng;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    open_rest_confirmation()
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.open_rest_confirmation(_session);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_rest_confirmation()
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.cancel_rest_confirmation();
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_rest()
    {
        battle_session<MaxUnits>& next_session =
                _transaction_session();
        battle_player_action_flow<MaxUnits>& next_flow =
                _transaction_player_flow();
        deterministic_rng next_rng = _rng;
        const battle_player_action_flow_result result =
                next_flow.confirm_rest_in_place(
                        next_session,
                        _conditions,
                        next_rng,
                        _mission_rules.objective);
        if(result.success())
        {
            _session = next_session;
            _player_flow = next_flow;
            _rng = next_rng;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    cycle_action(int direction)
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.cycle_action(direction);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_action_selection()
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.confirm_action_selection(_session);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    cycle_combination_decision(int direction)
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.cycle_combination_decision(direction);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_combination_decision()
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.confirm_combination_decision();
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_combination_decision()
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.cancel_combination_decision();
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_action_selection()
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.cancel_action_selection();
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    preview_target(grid_point target)
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.preview_target(_session, target);
        _player_flow = next;
        return result;
    }

    [[nodiscard]] bool target_legal(
            grid_point target) const
    {
        battle_player_action_flow<MaxUnits> next =
                _player_flow;
        return next.preview_target(
                           _session, target)
                .success();
    }

    [[nodiscard]] int target_maximum_distance() const
    {
        return _player_flow.target_maximum_distance();
    }

    [[nodiscard]] const reachable_cost_result<Width, Height>&
    reachable_costs() const
    {
        _movement_map_workspace = _terrain;
        if(apply_battle_occupancy(
                   _session, _movement_map_workspace) !=
                battle_map_load_error::none)
        {
            _reachable_cost_workspace = {};
            return _reachable_cost_workspace;
        }
        const battle_unit_instance* unit =
                _session.unit(_session.draft().unit_id);
        if(! unit)
        {
            _reachable_cost_workspace = {};
            return _reachable_cost_workspace;
        }
        compute_reachable_costs(
                _movement_map_workspace,
                _session.draft().origin,
                unit->move_range,
                battle_terrain_traversal_limits(
                        unit->passives),
                _reachable_cost_workspace,
                _path_workspace);
        return _reachable_cost_workspace;
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_target_selection()
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.cancel_target_selection();
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    confirm_target(grid_point target)
    {
        battle_session<MaxUnits>& next_session =
                _transaction_session();
        battle_player_action_flow<MaxUnits>& next_flow =
                _transaction_player_flow();
        deterministic_rng next_rng = _rng;
        const battle_player_action_flow_result result =
                next_flow.confirm_target_in_place(
                        next_session,
                        target,
                        next_rng,
                        _conditions,
                        _mission_rules.capture);
        _player_flow = next_flow;
        if(result.success())
        {
            _session = next_session;
            _rng = next_rng;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    end_without_action()
    {
        battle_session<MaxUnits>& next_session =
                _transaction_session();
        battle_player_action_flow<MaxUnits>& next_flow =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next_flow.end_without_action(next_session);
        if(result.success())
        {
            _session = next_session;
            _player_flow = next_flow;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    select_facing(battle_facing facing)
    {
        battle_session<MaxUnits>& next_session =
                _transaction_session();
        battle_player_action_flow<MaxUnits>& next_flow =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next_flow.select_facing(
                        next_session, facing);
        if(result.success())
        {
            _session = next_session;
            _player_flow = next_flow;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    open_defense_selection()
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.open_defense_selection(_session);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_defense_decision()
    {
        battle_session<MaxUnits>& next_session =
                _transaction_session();
        battle_player_action_flow<MaxUnits>& next_flow =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next_flow.cancel_defense_decision(
                        next_session);
        if(result.success())
        {
            _session = next_session;
            _player_flow = next_flow;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    cycle_defense_action(int direction)
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.cycle_defense_action(direction);
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    cancel_defense_selection()
    {
        battle_player_action_flow<MaxUnits>& next =
                _transaction_player_flow();
        const battle_player_action_flow_result result =
                next.cancel_defense_selection();
        if(result.success())
        {
            _player_flow = next;
        }
        return result;
    }

    [[nodiscard]] battle_player_action_flow_result
    complete_without_defense()
    {
        return _finish_player(
                false);
    }

    [[nodiscard]] battle_player_action_flow_result
    complete_selected_defense()
    {
        return _finish_player(
                true);
    }

    [[nodiscard]] battle_ai_turn_flow_result run_ai(
            battle_unit_id actor_id,
            ai_objective objective)
    {
        _movement_map_workspace = _terrain;
        if(apply_battle_occupancy(
                   _session,
                   _movement_map_workspace) !=
                battle_map_load_error::none)
        {
            return {
                battle_ai_turn_flow_error::
                        execution_failed,
            };
        }
        deterministic_rng next_rng = _rng;
        const battle_ai_turn_flow_result result =
                battle_ai_turn_flow::execute(
                        _session,
                        _movement_map_workspace,
                        actor_id,
                        objective,
                        _conditions,
                        next_rng,
                        _ai_workspace);
        if(result.success())
        {
            _rng = next_rng;
        }
        return result;
    }

    [[nodiscard]] battle_turn_flow_result
    advance_empty_side()
    {
        return battle_turn_flow::advance_empty_side(
                _session,
                _conditions,
                _rng);
    }

private:
    [[nodiscard]] battle_session<MaxUnits>&
    _transaction_session()
    {
        _transaction_workspace.session = _session;
        return _transaction_workspace.session;
    }

    [[nodiscard]] battle_player_action_flow<MaxUnits>&
    _transaction_player_flow()
    {
        _transaction_workspace.player_flow = _player_flow;
        return _transaction_workspace.player_flow;
    }

    [[nodiscard]] battle_player_action_flow_result
    _finish_player(bool selected_defense)
    {
        const battle_unit_id actor_id = _session.draft().unit_id;
        battle_session<MaxUnits>& next_session =
                _transaction_session();
        battle_player_action_flow<MaxUnits>& next_flow =
                _transaction_player_flow();
        deterministic_rng next_rng = _rng;
        const battle_player_action_flow_result result =
                selected_defense ?
                next_flow.confirm_defense_action_in_place(
                        next_session,
                        _conditions,
                        next_rng,
                        _mission_rules.objective) :
                next_flow.complete_without_defense_in_place(
                        next_session,
                        _conditions,
                        next_rng,
                        _mission_rules.objective);
        if(result.success())
        {
            battle_material_pickups::complete_action(
                    next_session, actor_id, _inventory, _pickup);
            _session = next_session;
            _player_flow = next_flow;
            _rng = next_rng;
        }
        return result;
    }

    battle_campaign_inventory _inventory;
    battle_material_pickup _pickup;
    battle_session<MaxUnits> _session;
    grid_map<Width, Height> _terrain;
    mutable grid_map<Width, Height>
            _movement_map_workspace;
    mutable reachable_cost_result<Width, Height>
            _reachable_cost_workspace;
    mutable pathfinder_workspace<Width, Height>
            _path_workspace;
    battle_player_action_flow<MaxUnits> _player_flow;
    battle_condition_variant _conditions;
    battle_mission_rules _mission_rules;
    deterministic_rng _rng{ 1U };
    battle_ai_turn_workspace<MaxUnits, Width, Height>
            _ai_workspace;
    battle_encounter_load_workspace<MaxUnits, Width, Height>
            _load_workspace;
    battle_encounter_transaction_workspace<MaxUnits>
            _transaction_workspace;
    bool _loaded = false;
};

}

#endif
