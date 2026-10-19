#ifndef KONOHA_BATTLE_ACTION_EXECUTION_H
#define KONOHA_BATTLE_ACTION_EXECUTION_H

#include "konoha/battle_action_system.h"

namespace konoha
{

class battle_action_execution
{
public:
    template<std::size_t MaxUnits>
    [[nodiscard]] static action_preview preview(
            const battle_session<MaxUnits>& session,
            const action_definition& action,
            grid_point target_position)
    {
        const effect_handler_kind handler =
                effect_resolver_registry::handler_for(
                        action.effect.code);
        if(_uses_area_resolution(handler))
        {
            return battle_action_resolver::preview_area(
                    session, action, _normalized_target_position(
                                             session,
                                             action,
                                             target_position));
        }
        return battle_action_resolver::preview(
                session,
                _target_id(session, action, target_position),
                _summon_id(session, handler),
                action,
                _normalized_target_position(
                        session, action, target_position));
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_result resolve(
            battle_session<MaxUnits>& session,
            const action_definition& action,
            grid_point target_position,
            deterministic_rng& rng)
    {
        const effect_handler_kind handler =
                effect_resolver_registry::handler_for(
                        action.effect.code);
        if(_uses_area_resolution(handler))
        {
            return battle_action_resolver::resolve_area_draft(
                    session,
                    action,
                    _normalized_target_position(
                            session, action, target_position),
                    rng);
        }
        return battle_action_resolver::resolve_draft(
                session,
                _target_id(session, action, target_position),
                _summon_id(session, handler),
                action,
                _normalized_target_position(
                        session, action, target_position),
                rng);
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_result resolve_in_place(
            battle_session<MaxUnits>& session,
            const action_definition& action,
            grid_point target_position,
            deterministic_rng& rng)
    {
        const effect_handler_kind handler =
                effect_resolver_registry::handler_for(
                        action.effect.code);
        if(_uses_area_resolution(handler))
        {
            return battle_action_resolver::
                    resolve_area_draft_in_place(
                            session,
                            action,
                            _normalized_target_position(
                                    session,
                                    action,
                                    target_position),
                            rng);
        }
        return battle_action_resolver::resolve_draft_in_place(
                session,
                _target_id(session, action, target_position),
                _summon_id(session, handler),
                action,
                _normalized_target_position(
                        session, action, target_position),
                rng);
    }

private:
    [[nodiscard]] static constexpr bool _uses_area_resolution(
            effect_handler_kind handler)
    {
        return handler == effect_handler_kind::damage ||
                handler == effect_handler_kind::heal_percent ||
                handler == effect_handler_kind::status ||
                handler ==
                        effect_handler_kind::reaction_state;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static grid_point _normalized_target_position(
            const battle_session<MaxUnits>& session,
            const action_definition& action,
            grid_point requested)
    {
        if(action.target.kind ==
                        target_policy_kind::self_or_implicit_actor &&
                session.draft().active)
        {
            return session.draft().preview_position;
        }
        return requested;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_unit_id _target_id(
            const battle_session<MaxUnits>& session,
            const action_definition& action,
            grid_point target_position)
    {
        if(action.target.kind ==
                target_policy_kind::empty_tile)
        {
            return no_battle_unit;
        }
        if(action.target.kind ==
                        target_policy_kind::self_or_implicit_actor &&
                session.draft().active)
        {
            return session.draft().unit_id;
        }
        if(session.draft().active &&
                target_position ==
                        session.draft().preview_position)
        {
            return session.draft().unit_id;
        }
        const battle_unit_instance* target =
                session.active_unit_at(target_position);
        return target ? target->id : no_battle_unit;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_unit_id _summon_id(
            const battle_session<MaxUnits>& session,
            effect_handler_kind handler)
    {
        if(handler != effect_handler_kind::summon &&
                handler != effect_handler_kind::summon_variant &&
                handler != effect_handler_kind::summon_pair)
        {
            return no_battle_unit;
        }
        const battle_unit_instance* reserve =
                session.first_inactive_unit();
        return reserve ? reserve->id : no_battle_unit;
    }
};

}

#endif
