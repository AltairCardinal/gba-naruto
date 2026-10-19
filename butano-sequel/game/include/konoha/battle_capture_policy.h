#ifndef KONOHA_BATTLE_CAPTURE_POLICY_H
#define KONOHA_BATTLE_CAPTURE_POLICY_H

#include "konoha/battle_action_system.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

struct battle_capture_source
{
    std::array<battle_action_source_kind, 2> component_kinds = {};
    std::size_t component_count = 0;

    [[nodiscard]] static constexpr battle_capture_source single(
            battle_action_source_kind kind)
    {
        return {
            { kind, battle_action_source_kind::active_action },
            1,
        };
    }
};

struct battle_capture_policy
{
    bool enabled = false;
    battle_side target_side = battle_side::enemy;
    std::uint8_t target_character_id = 0;
    bool allow_active_actions = false;
    bool allow_ninja_tools = false;
    bool allow_direct_attacks = false;
    std::array<ability_id, 4>
            transformed_active_actions = {};
    std::size_t transformed_active_action_count = 0;

    [[nodiscard]] constexpr bool allows(
            battle_action_source_kind source_kind) const
    {
        switch(source_kind)
        {
        case battle_action_source_kind::active_action:
            return allow_active_actions;
        case battle_action_source_kind::ninja_tool:
            return allow_ninja_tools;
        case battle_action_source_kind::direct_attack:
            return allow_direct_attacks;
        default:
            return false;
        }
    }

    [[nodiscard]] constexpr bool allows(
            const battle_capture_source& source) const
    {
        if(source.component_count == 0 ||
                source.component_count >
                        source.component_kinds.size())
        {
            return false;
        }
        for(std::size_t index = 0;
                index < source.component_count; ++index)
        {
            if(! allows(source.component_kinds[index]))
            {
                return false;
            }
        }
        return true;
    }

    [[nodiscard]] constexpr bool transforms_active_action(
            ability_id action_id) const
    {
        for(std::size_t index = 0;
                index < transformed_active_action_count &&
                index <
                        transformed_active_actions.size();
                ++index)
        {
            if(transformed_active_actions[index] ==
                    action_id)
            {
                return true;
            }
        }
        return false;
    }

    [[nodiscard]] constexpr action_definition transform(
            const action_definition& action) const
    {
        if(action.source_kind !=
                        battle_action_source_kind::
                                active_action ||
                ! transforms_active_action(action.id))
        {
            return action;
        }
        action_definition result = action;
        result.effect = {
            0x01,
            0,
            10,
            1,
            98,
            0,
        };
        result.target = {
            target_policy_kind::opponent_unit,
            0,
        };
        result.range = { 1, 1 };
        return result;
    }

    constexpr bool operator==(const battle_capture_policy&) const =
            default;
};

struct battle_capture_summary
{
    std::array<battle_unit_id, 12> unit_ids = {};
    int count = 0;
};

class battle_capture_system
{
public:
    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_capture_summary apply(
            battle_session<MaxUnits>& session,
            const battle_capture_policy& policy,
            battle_action_source_kind source_kind,
            const action_result& action)
    {
        return apply(
                session,
                policy,
                battle_capture_source::single(source_kind),
                action);
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_capture_summary apply(
            battle_session<MaxUnits>& session,
            const battle_capture_policy& policy,
            const battle_capture_source& source,
            const action_result& action)
    {
        battle_capture_summary result;
        if(! policy.enabled || ! policy.allows(source))
        {
            return result;
        }

        for(int index = 0;
                index < action.damage_step_count; ++index)
        {
            const damage_resolution_step& step =
                    action.damage_steps[
                            static_cast<std::size_t>(index)];
            if(! step.defeated || step.linked)
            {
                continue;
            }
            battle_unit_instance* target =
                    session._find_unit(step.target_id);
            if(! target || target->captured ||
                    target->side != policy.target_side ||
                    target->character_id !=
                            policy.target_character_id)
            {
                continue;
            }
            target->captured = true;
            target->character_id = 0;
            if(result.count <
                    static_cast<int>(result.unit_ids.size()))
            {
                result.unit_ids[
                        static_cast<std::size_t>(
                                result.count)] = target->id;
                ++result.count;
            }
        }
        return result;
    }
};

}

#endif
