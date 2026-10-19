#ifndef KONOHA_BATTLE_TURN_FLOW_H
#define KONOHA_BATTLE_TURN_FLOW_H

#include "konoha/battle_conditions.h"
#include "konoha/battle_defense_preparation.h"
#include "konoha/battle_mission_objective.h"
#include "konoha/generated_battle_action_content.h"

namespace konoha
{

enum class battle_turn_flow_error : std::uint8_t
{
    none,
    invalid_phase,
    condition_error,
    defense_preparation_error,
    battlefield_object_resolution_error,
    mission_objective_error,
};

struct battlefield_object_resolution_summary
{
    int total_damage = 0;
    int target_count = 0;
    int impact_count = 0;
    std::uint8_t battlefield_object_slot =
            no_battlefield_object;
};

struct battle_turn_flow_result
{
    battle_turn_flow_error error = battle_turn_flow_error::none;
    battle_transition transition = battle_transition::none;
    battle_condition_outcome outcome = battle_condition_outcome::none;
    std::uint8_t presentation_id = 0;
    bool ends_battle = false;
    int object_event_count = 0;
    battlefield_object_resolution_summary
            object_effects = {};
};

class battle_turn_flow
{
public:
    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_turn_flow_result
    advance_empty_side(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions,
            deterministic_rng& rng)
    {
        battle_session<MaxUnits> next = session;
        deterministic_rng next_rng = rng;
        const battle_transition transition =
                next.advance_empty_side_before_boundary();
        if(transition == battle_transition::invalid)
        {
            return {
                battle_turn_flow_error::invalid_phase,
            };
        }

        battle_turn_flow_result result;
        result.transition = transition;
        if(! _resolve_battlefield_objects(
                   next, transition, next_rng, result))
        {
            return {
                battle_turn_flow_error::
                        battlefield_object_resolution_error,
            };
        }
        next._finalize_action_boundary(transition);
        const battle_condition_result condition =
                battle_condition_interpreter::evaluate_session(
                        next, conditions);
        if(condition.error != battle_condition_error::none)
        {
            return {
                battle_turn_flow_error::condition_error,
            };
        }

        session = next;
        rng = next_rng;
        _set_condition_result(condition, result);
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_turn_flow_result
    complete_non_target_action(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions)
    {
        deterministic_rng rng(1);
        return complete_non_target_action(
                session, conditions, rng);
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_turn_flow_result
    complete_non_target_action(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions,
            deterministic_rng& rng,
            const battle_mission_objective& objective = {})
    {
        battle_session<MaxUnits> next = session;
        deterministic_rng next_rng = rng;
        const battle_turn_flow_result result =
                complete_non_target_action_in_place(
                        next, conditions, next_rng, objective);
        if(result.error == battle_turn_flow_error::none)
        {
            session = next;
            rng = next_rng;
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_turn_flow_result
    complete_non_target_action_in_place(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions,
            deterministic_rng& rng,
            const battle_mission_objective& objective = {})
    {
        if(session.lifecycle() !=
                battle_lifecycle::action_drafting)
        {
            return { battle_turn_flow_error::invalid_phase };
        }
        const battle_unit_id actor_id =
                session.draft().unit_id;

        const battle_transition transition =
                session.complete_non_target_action();
        if(transition == battle_transition::invalid)
        {
            return { battle_turn_flow_error::invalid_phase };
        }
        deterministic_rng next_rng = rng;
        battle_turn_flow_result result;
        result.transition = transition;
        if(! _resolve_battlefield_objects(
                   session, transition, next_rng, result))
        {
            return {
                battle_turn_flow_error::
                        battlefield_object_resolution_error,
            };
        }
        if(! _resolve_mission_objective(
                   session, objective, actor_id))
        {
            return {
                battle_turn_flow_error::
                        mission_objective_error,
            };
        }
        session._finalize_action_boundary(transition);
        const battle_condition_result condition =
                battle_condition_interpreter::evaluate_session(
                        session, conditions);
        if(condition.error != battle_condition_error::none)
        {
            return { battle_turn_flow_error::condition_error };
        }
        rng = next_rng;
        _set_condition_result(condition, result);
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_turn_flow_result after_effects(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions)
    {
        battle_session<MaxUnits> next = session;
        const battle_turn_flow_result result =
                after_effects_in_place(next, conditions);
        if(result.error == battle_turn_flow_error::none)
        {
            session = next;
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_turn_flow_result
    after_effects_in_place(
            battle_session<MaxUnits>& session,
            const battle_condition_variant& conditions)
    {
        if(session.lifecycle() != battle_lifecycle::effects_resolved)
        {
            return { battle_turn_flow_error::invalid_phase };
        }

        const battle_condition_result condition =
                battle_condition_interpreter::evaluate_session(
                        session, conditions);
        if(condition.error != battle_condition_error::none)
        {
            return { battle_turn_flow_error::condition_error };
        }
        if(condition.ends_battle)
        {
            return _result(battle_transition::none, condition);
        }

        const battle_transition transition =
                session.open_facing_selection();
        if(transition != battle_transition::facing_selection_opened)
        {
            return { battle_turn_flow_error::invalid_phase };
        }
        return _result(transition, condition);
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_turn_flow_result complete_defense(
            battle_session<MaxUnits>& session,
            ability_id defense_ability,
            const battle_condition_variant& conditions)
    {
        deterministic_rng rng(1);
        return complete_defense(
                session, defense_ability, conditions, rng);
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_turn_flow_result complete_defense(
            battle_session<MaxUnits>& session,
            ability_id defense_ability,
            const battle_condition_variant& conditions,
            deterministic_rng& rng,
            const battle_mission_objective& objective = {})
    {
        battle_session<MaxUnits> next = session;
        deterministic_rng next_rng = rng;
        const battle_turn_flow_result result =
                complete_defense_in_place(
                        next,
                        defense_ability,
                        conditions,
                        next_rng,
                        objective);
        if(result.error == battle_turn_flow_error::none)
        {
            session = next;
            rng = next_rng;
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_turn_flow_result
    complete_defense_in_place(
            battle_session<MaxUnits>& session,
            ability_id defense_ability,
            const battle_condition_variant& conditions,
            deterministic_rng& rng,
            const battle_mission_objective& objective = {})
    {
        if(session.lifecycle() != battle_lifecycle::defense_select)
        {
            return { battle_turn_flow_error::invalid_phase };
        }
        const battle_unit_id actor_id =
                session.draft().unit_id;

        const battle_transition transition =
                session.complete_action_before_boundary(
                        defense_ability);
        if(transition == battle_transition::invalid)
        {
            return { battle_turn_flow_error::invalid_phase };
        }

        deterministic_rng next_rng = rng;
        battle_turn_flow_result result;
        result.transition = transition;
        if(! _resolve_battlefield_objects(
                   session, transition, next_rng, result))
        {
            return {
                battle_turn_flow_error::
                        battlefield_object_resolution_error,
            };
        }
        if(! _resolve_mission_objective(
                   session, objective, actor_id))
        {
            return {
                battle_turn_flow_error::
                        mission_objective_error,
            };
        }
        session._finalize_action_boundary(transition);
        const battle_condition_result condition =
                battle_condition_interpreter::evaluate_session(
                        session, conditions);
        if(condition.error != battle_condition_error::none)
        {
            return { battle_turn_flow_error::condition_error };
        }

        rng = next_rng;
        _set_condition_result(condition, result);
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_turn_flow_result complete_defense(
            battle_session<MaxUnits>& session,
            const action_definition& defense_action,
            const battle_condition_variant& conditions)
    {
        deterministic_rng rng(1);
        return complete_defense(
                session, defense_action, conditions, rng);
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_turn_flow_result complete_defense(
            battle_session<MaxUnits>& session,
            const action_definition& defense_action,
            const battle_condition_variant& conditions,
            deterministic_rng& rng,
            const battle_mission_objective& objective = {})
    {
        battle_session<MaxUnits> next = session;
        deterministic_rng next_rng = rng;
        const battle_turn_flow_result result =
                complete_defense_in_place(
                        next,
                        defense_action,
                        conditions,
                        next_rng,
                        objective);
        if(result.error == battle_turn_flow_error::none)
        {
            session = next;
            rng = next_rng;
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_turn_flow_result
    complete_defense_in_place(
            battle_session<MaxUnits>& session,
            const action_definition& defense_action,
            const battle_condition_variant& conditions,
            deterministic_rng& rng,
            const battle_mission_objective& objective = {})
    {
        if(session.lifecycle() != battle_lifecycle::defense_select)
        {
            return { battle_turn_flow_error::invalid_phase };
        }
        const battle_unit_id actor_id =
                session.draft().unit_id;

        const defense_preparation_preview prepared =
                battle_defense_preparation::commit_in_place(
                        session, defense_action);
        if(! prepared.legal())
        {
            return {
                battle_turn_flow_error::
                        defense_preparation_error,
            };
        }
        const battle_transition transition =
                session.complete_action_before_boundary(
                        prepared.preparation());
        if(transition == battle_transition::invalid)
        {
            return { battle_turn_flow_error::invalid_phase };
        }

        deterministic_rng next_rng = rng;
        battle_turn_flow_result result;
        result.transition = transition;
        if(! _resolve_battlefield_objects(
                   session, transition, next_rng, result))
        {
            return {
                battle_turn_flow_error::
                        battlefield_object_resolution_error,
            };
        }
        if(! _resolve_mission_objective(
                   session, objective, actor_id))
        {
            return {
                battle_turn_flow_error::
                        mission_objective_error,
            };
        }
        session._finalize_action_boundary(transition);
        const battle_condition_result condition =
                battle_condition_interpreter::evaluate_session(
                        session, conditions);
        if(condition.error != battle_condition_error::none)
        {
            return { battle_turn_flow_error::condition_error };
        }

        rng = next_rng;
        _set_condition_result(condition, result);
        return result;
    }

private:
    template<std::size_t MaxUnits>
    [[nodiscard]] static bool _resolve_mission_objective(
            battle_session<MaxUnits>& session,
            const battle_mission_objective& objective,
            battle_unit_id actor_id)
    {
        return battle_mission_objective_system::
                       resolve_player_action_boundary(
                               session,
                               objective,
                               actor_id) !=
                battle_mission_objective_resolution::
                        invalid_state;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static bool _resolve_battlefield_objects(
            battle_session<MaxUnits>& session,
            battle_transition transition,
            deterministic_rng& rng,
            battle_turn_flow_result& result)
    {
        if(transition != battle_transition::side_changed &&
                transition != battle_transition::round_advanced)
        {
            return true;
        }

        result.object_event_count =
                session.object_tick_event_count();
        for(int index = 0;
                index < result.object_event_count; ++index)
        {
            const battlefield_object_tick_event* event =
                    session.object_tick_event_at(index);
            if(! event || ! event->valid())
            {
                return false;
            }
            if(event->kind ==
                    battlefield_object_tick_kind::type_2_expired)
            {
                continue;
            }
            if(event->kind !=
                    battlefield_object_tick_kind::type_1_due ||
                    event->object.payload_id >=
                            ninja_tool_action_definitions.size())
            {
                return false;
            }
            const action_definition& payload =
                    ninja_tool_action_definitions[
                            event->object.payload_id];
            if(payload.id != event->object.payload_id)
            {
                return false;
            }
            const action_result item =
                    battle_action_resolver::
                            resolve_battlefield_object_event(
                                    session,
                                    *event,
                                    payload,
                                    rng);
            if(! item.success())
            {
                return false;
            }
            if(! session.record_object_tick_resolution(
                       static_cast<std::size_t>(index),
                       item.affected_unit_ids,
                       item.affected_unit_count,
                       item.affected_units_truncated,
                       item.generated_hits,
                       item.total_damage))
            {
                return false;
            }
            battlefield_object_resolution_summary&
                    summary = result.object_effects;
            summary.total_damage += item.total_damage;
            summary.target_count += item.target_count;
            summary.impact_count += item.generated_hits;
            if(summary.battlefield_object_slot ==
                    no_battlefield_object)
            {
                summary.battlefield_object_slot =
                        item.battlefield_object_slot;
            }
        }
        return true;
    }

    static void _set_condition_result(
            const battle_condition_result& condition,
            battle_turn_flow_result& result)
    {
        result.error = battle_turn_flow_error::none;
        result.outcome = condition.outcome;
        result.presentation_id = condition.presentation_id;
        result.ends_battle = condition.ends_battle;
    }

    [[nodiscard]] static battle_turn_flow_result _result(
            battle_transition transition,
            const battle_condition_result& condition)
    {
        return {
            battle_turn_flow_error::none,
            transition,
            condition.outcome,
            condition.presentation_id,
            condition.ends_battle,
        };
    }
};

}

#endif
