#ifndef KONOHA_BATTLE_DEFENSE_PREPARATION_H
#define KONOHA_BATTLE_DEFENSE_PREPARATION_H

#include "konoha/battle_action_system.h"

namespace konoha
{

enum class defense_preparation_error : std::uint8_t
{
    none,
    invalid_phase,
    invalid_definition,
    unsupported_category,
    action_requirement_not_met,
    insufficient_chakra,
    insufficient_hp,
    missing_ninja_tool,
    status_capacity_exhausted,
};

struct defense_preparation_preview
{
    defense_preparation_error error =
            defense_preparation_error::none;
    defense_action_kind kind = defense_action_kind::none;
    ability_id action_id = no_ability;
    std::uint8_t tool_slot = no_tool_slot;
    int chakra_cost = 0;
    int hp_cost = 0;

    [[nodiscard]] constexpr bool legal() const
    {
        return error == defense_preparation_error::none;
    }

    [[nodiscard]] constexpr prepared_defense_action preparation() const
    {
        return { kind, action_id, tool_slot };
    }
};

class battle_defense_preparation
{
public:
    template<std::size_t MaxUnits>
    [[nodiscard]] static defense_preparation_preview preview(
            const battle_session<MaxUnits>& session,
            const action_definition& action)
    {
        if(session._lifecycle != battle_lifecycle::defense_select ||
                ! session._draft.active)
        {
            return { defense_preparation_error::invalid_phase };
        }
        const battle_unit_instance* actor =
                session._find_unit(session._draft.unit_id);
        if(! actor)
        {
            return { defense_preparation_error::invalid_phase };
        }
        if(action.id == no_ability)
        {
            return { defense_preparation_error::invalid_definition };
        }
        const defense_action_kind kind =
                action.cost.kind ==
                        action_cost_kind::battle_local_ninja_tool_slot ?
                defense_action_kind::ninja_tool :
                defense_action_kind::active_action;
        if(! _implemented_binding(action.effect.code, kind))
        {
            return {
                defense_preparation_error::unsupported_category,
            };
        }
        if(action.target.kind !=
                        target_policy_kind::self_or_implicit_actor ||
                effect_resolver_registry::handler_for(
                        action.effect.code) !=
                        effect_handler_kind::status)
        {
            return { defense_preparation_error::invalid_definition };
        }

        if(kind == defense_action_kind::active_action)
        {
            const action_requirement requirement =
                    battle_action_eligibility::query(
                            *actor, action.id);
            if(! requirement.available())
            {
                return {
                    defense_preparation_error::
                            action_requirement_not_met,
                };
            }
        }

        const action_error cost_error =
                battle_action_cost_policy::validate(
                        *actor, action.cost, action.id);
        if(cost_error != action_error::none)
        {
            return {
                _cost_error(cost_error),
                kind,
                action.id,
                action.cost.tool_slot,
            };
        }

        battle_unit_instance changed = *actor;
        if(! changed.statuses.upsert(
                   _status(action, kind, actor->id)))
        {
            return {
                defense_preparation_error::
                        status_capacity_exhausted,
                kind,
                action.id,
                action.cost.tool_slot,
            };
        }

        defense_preparation_preview result;
        result.kind = kind;
        result.action_id = action.id;
        result.tool_slot = action.cost.tool_slot;
        if(action.cost.kind == action_cost_kind::current_chakra)
        {
            result.chakra_cost = action.cost.scalar;
        }
        else if(action.cost.kind == action_cost_kind::current_hp)
        {
            result.hp_cost = action.cost.scalar;
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static defense_preparation_preview commit(
            battle_session<MaxUnits>& session,
            const action_definition& action)
    {
        battle_session<MaxUnits> next = session;
        const defense_preparation_preview checked =
                commit_in_place(next, action);
        if(checked.legal())
        {
            session = next;
        }
        return checked;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static defense_preparation_preview
    commit_in_place(
            battle_session<MaxUnits>& session,
            const action_definition& action)
    {
        const defense_preparation_preview checked =
                preview(session, action);
        if(! checked.legal())
        {
            return checked;
        }

        battle_unit_instance* actor =
                session._find_unit(session._draft.unit_id);
        battle_action_cost_policy::commit(*actor, action.cost);
        if(! actor->statuses.upsert(
                   _status(action, checked.kind, actor->id)))
        {
            return {
                defense_preparation_error::
                        status_capacity_exhausted,
                checked.kind,
                checked.action_id,
                checked.tool_slot,
            };
        }
        return checked;
    }

private:
    [[nodiscard]] static constexpr bool _implemented_binding(
            std::uint8_t effect_code,
            defense_action_kind kind)
    {
        return (effect_code == 0x10 &&
                       kind == defense_action_kind::active_action) ||
                (effect_code == 0x04 &&
                        kind == defense_action_kind::active_action) ||
                (effect_code == 0x16 &&
                        kind == defense_action_kind::ninja_tool) ||
                (effect_code == 0x19 &&
                        kind == defense_action_kind::ninja_tool);
    }

    [[nodiscard]] static constexpr std::uint8_t _reaction_code(
            const action_definition& action)
    {
        // The action table identifies Kawarimi with effect 0x04, while
        // the battle reaction state observed in the original ROM is 0x16.
        return action.effect.code == 0x04 ?
                0x16 : action.effect.code;
    }

    [[nodiscard]] static status_record _status(
            const action_definition& action,
            defense_action_kind kind,
            battle_unit_id actor_id)
    {
        return {
            static_cast<std::uint8_t>(
                    (_reaction_code(action) & 0x3F) |
                    action.effect.flags),
            static_cast<std::uint8_t>(
                    kind == defense_action_kind::ninja_tool ?
                    action.id | 0x80 :
                    action.id),
            encode_status_duration_ticks(
                    action.effect.duration_turns),
            action.cost.tool_slot,
            actor_id,
            0,
            action.effect.potency,
        };
    }

    [[nodiscard]] static constexpr defense_preparation_error
    _cost_error(action_error error)
    {
        switch(error)
        {
        case action_error::insufficient_chakra:
            return defense_preparation_error::insufficient_chakra;
        case action_error::insufficient_hp:
            return defense_preparation_error::insufficient_hp;
        case action_error::missing_ninja_tool:
            return defense_preparation_error::missing_ninja_tool;
        default:
            return defense_preparation_error::invalid_definition;
        }
    }
};

}

#endif
