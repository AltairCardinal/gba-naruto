#ifndef KONOHA_BATTLE_MISSION_OBJECTIVE_H
#define KONOHA_BATTLE_MISSION_OBJECTIVE_H

#include "konoha/battle_session.h"

#include <cstddef>
#include <cstdint>

namespace konoha
{

struct battle_mission_objective
{
    bool enabled = false;
    std::uint8_t object_slot = no_battlefield_object;
    battlefield_object_record object = {};
    battle_side actor_side = battle_side::player;
    grid_point interaction_position = {};
    battle_facing interaction_facing = battle_facing::up;
    bool require_side_inactive = false;
    battle_side required_inactive_side = battle_side::enemy;

    constexpr bool operator==(
            const battle_mission_objective&) const = default;
};

enum class battle_mission_objective_error : std::uint8_t
{
    none,
    invalid_definition,
    object_slot_unavailable,
};

enum class battle_mission_objective_resolution : std::uint8_t
{
    not_applicable,
    requirements_not_met,
    resolved,
    invalid_state,
};

class battle_mission_objective_system
{
public:
    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_mission_objective_error initialize(
            battle_session<MaxUnits>& session,
            const battle_mission_objective& objective)
    {
        if(! objective.enabled)
        {
            return battle_mission_objective_error::none;
        }
        if(objective.object_slot == 0 ||
                objective.object_slot >=
                        battlefield_object_table::capacity ||
                objective.object.type == 0)
        {
            return battle_mission_objective_error::
                    invalid_definition;
        }
        if(! session.objects().place(
                   objective.object_slot,
                   objective.object))
        {
            return battle_mission_objective_error::
                    object_slot_unavailable;
        }
        return battle_mission_objective_error::none;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_mission_objective_resolution
    resolve_player_action_boundary(
            battle_session<MaxUnits>& session,
            const battle_mission_objective& objective)
    {
        const action_draft& draft = session.draft();
        return draft.active ?
                resolve_player_action_boundary(
                        session,
                        objective,
                        draft.unit_id) :
                battle_mission_objective_resolution::
                        requirements_not_met;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_mission_objective_resolution
    resolve_player_action_boundary(
            battle_session<MaxUnits>& session,
            const battle_mission_objective& objective,
            battle_unit_id actor_id)
    {
        if(! objective.enabled)
        {
            return battle_mission_objective_resolution::
                    not_applicable;
        }
        const battlefield_object_record* object =
                session.objects().record(
                        objective.object_slot);
        if(! object || object->type == 0)
        {
            return battle_mission_objective_resolution::
                    not_applicable;
        }
        if(*object != objective.object)
        {
            return battle_mission_objective_resolution::
                    invalid_state;
        }

        const battle_unit_instance* actor =
                session.unit(actor_id);
        if(! actor || ! actor->active ||
                actor->side != objective.actor_side ||
                actor->position !=
                        objective.interaction_position ||
                actor->facing !=
                        objective.interaction_facing)
        {
            return battle_mission_objective_resolution::
                    requirements_not_met;
        }
        if(objective.require_side_inactive)
        {
            for(std::size_t index = 0;
                    index < session.unit_count();
                    ++index)
            {
                const battle_unit_instance* unit =
                        session.unit_at(index);
                if(unit && unit->active &&
                        unit->side ==
                                objective
                                        .required_inactive_side)
                {
                    return battle_mission_objective_resolution::
                            requirements_not_met;
                }
            }
        }
        return session.objects().free(
                       objective.object_slot) ?
                battle_mission_objective_resolution::resolved :
                battle_mission_objective_resolution::invalid_state;
    }
};

}

#endif
