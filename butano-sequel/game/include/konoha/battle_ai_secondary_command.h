#ifndef KONOHA_BATTLE_AI_SECONDARY_COMMAND_H
#define KONOHA_BATTLE_AI_SECONDARY_COMMAND_H

#include "konoha/battle_defense_browser.h"

#include <cstddef>
#include <cstdint>

namespace konoha
{

struct battle_ai_secondary_command
{
    bool planned = false;
    defense_action_kind defense_kind =
            defense_action_kind::none;
    ability_id defense_action_id = no_ability;
    std::uint8_t defense_tool_slot = no_tool_slot;
    int score = 0;
};

class battle_ai_secondary_command_planner
{
public:
    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_ai_secondary_command plan(
            const battle_session<MaxUnits>& session,
            const battle_defense_browser_result& browser)
    {
        battle_ai_secondary_command result;
        result.planned = true;
        const battle_unit_instance* actor =
                session.draft().active ?
                session.unit(session.draft().unit_id) :
                nullptr;
        if(! actor)
        {
            return result;
        }

        const int incoming_threat =
                _incoming_threat(session, *actor);
        if(incoming_threat <= 0)
        {
            return result;
        }

        int best_score = 0;
        for(std::size_t index = 0;
                index < browser.count;
                ++index)
        {
            const battle_defense_browser_entry& entry =
                    browser.entries[index];
            if(! entry.confirmable())
            {
                continue;
            }
            const int candidate_score = _score(
                    session,
                    *actor,
                    entry,
                    incoming_threat);
            if(candidate_score > best_score)
            {
                best_score = candidate_score;
                result.defense_kind = entry.kind;
                result.defense_action_id =
                        entry.action_id;
                result.defense_tool_slot =
                        entry.tool_slot;
                result.score = candidate_score;
            }
        }
        return result;
    }

private:
    template<std::size_t MaxUnits>
    [[nodiscard]] static int _incoming_threat(
            const battle_session<MaxUnits>& session,
            const battle_unit_instance& actor)
    {
        int result = 0;
        for(std::size_t index = 0;
                index < session.unit_count();
                ++index)
        {
            const battle_unit_instance* opponent =
                    session.unit_at(index);
            if(! opponent || ! opponent->active ||
                    opponent->side == actor.side)
            {
                continue;
            }
            int damage = opponent->attack - actor.defense;
            if(damage < 1)
            {
                damage = 1;
            }
            if(damage > result)
            {
                result = damage;
            }
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static int _score(
            const battle_session<MaxUnits>& session,
            const battle_unit_instance& actor,
            const battle_defense_browser_entry& entry,
            int incoming_threat)
    {
        const std::uint8_t effect_code =
                entry.action.effect.code;
        int tactical_value = 0;
        if(effect_code == 0x04 ||
                effect_code == 0x10)
        {
            tactical_value = incoming_threat * 10;
        }
        else if(effect_code == 0x19 &&
                _has_adjacent_opponent(
                        session, actor))
        {
            tactical_value =
                    incoming_threat * 6 +
                    entry.action.effect.potency * 4;
        }
        if(tactical_value == 0)
        {
            return 0;
        }

        int resource_cost = 0;
        if(entry.action.cost.kind ==
                        action_cost_kind::current_chakra ||
                entry.action.cost.kind ==
                        action_cost_kind::current_hp)
        {
            resource_cost = entry.action.cost.scalar;
        }
        else if(entry.action.cost.kind ==
                action_cost_kind::
                        battle_local_ninja_tool_slot)
        {
            resource_cost = 5;
        }
        return tactical_value - resource_cost * 3;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static bool _has_adjacent_opponent(
            const battle_session<MaxUnits>& session,
            const battle_unit_instance& actor)
    {
        for(std::size_t index = 0;
                index < session.unit_count();
                ++index)
        {
            const battle_unit_instance* opponent =
                    session.unit_at(index);
            if(opponent && opponent->active &&
                    opponent->side != actor.side &&
                    _distance(
                            opponent->position,
                            actor.position) == 1)
            {
                return true;
            }
        }
        return false;
    }

    [[nodiscard]] static int _distance(
            grid_point first, grid_point second)
    {
        const int dx = first.x > second.x ?
                first.x - second.x :
                second.x - first.x;
        const int dy = first.y > second.y ?
                first.y - second.y :
                second.y - first.y;
        return dx + dy;
    }
};

}

#endif
