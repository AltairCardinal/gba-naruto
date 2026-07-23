#ifndef KONOHA_BATTLE_AI_H
#define KONOHA_BATTLE_AI_H

#include "konoha/battle_action_system.h"
#include "konoha/battle_commands.h"
#include "konoha/grid_pathfinder.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace konoha
{

enum class ai_action : std::uint8_t
{
    end_action,
    move,
    ability,
};

enum class ai_error : std::uint8_t
{
    none,
    invalid_unit,
    invalid_objective,
};

struct ai_objective
{
    bool has_focus_position = false;
    grid_point focus_position = {};
    battle_unit_id target_unit = no_battle_unit;
    battle_unit_id protected_unit = no_battle_unit;
};

struct ai_candidate
{
    ai_action action = ai_action::end_action;
    grid_point destination = {};
    battle_unit_id target_unit = no_battle_unit;
    ability_id ability = no_ability;
    int score = 0;
};

struct ai_plan : ai_candidate
{
    ai_error error = ai_error::none;
};

class battle_ai
{
public:
    template<int Width, int Height, std::size_t UnitCount>
    [[nodiscard]] static ai_plan plan(
            const grid_map<Width, Height>& map,
            const battle_unit_instance& acting_unit,
            const std::array<battle_unit_instance, UnitCount>& units,
            std::nullptr_t,
            ai_objective objective,
            deterministic_rng& rng)
    {
        return plan(map, acting_unit, units,
                static_cast<const ability_definition<1>*>(nullptr), objective, rng);
    }

    template<int Width, int Height, std::size_t UnitCount, std::size_t MaxEffects = 1>
    [[nodiscard]] static ai_plan plan(
            const grid_map<Width, Height>& map,
            const battle_unit_instance& acting_unit,
            const std::array<battle_unit_instance, UnitCount>& units,
            const ability_definition<MaxEffects>* ability,
            ai_objective objective,
            deterministic_rng& rng)
    {
        static_assert(UnitCount > 0);
        (void) rng;
        if(! acting_unit.active || acting_unit.ledger.completed)
        {
            ai_plan result;
            result.error = ai_error::invalid_unit;
            return result;
        }

        const battle_unit_instance* target = _find_unit(units, objective.target_unit);
        if(objective.target_unit != no_battle_unit && (! target || ! target->active))
        {
            ai_plan result;
            result.error = ai_error::invalid_objective;
            return result;
        }
        if(objective.protected_unit != no_battle_unit &&
                ! _find_unit(units, objective.protected_unit))
        {
            ai_plan result;
            result.error = ai_error::invalid_objective;
            return result;
        }
        ai_plan best;
        best.destination = acting_unit.position;
        best.score = std::numeric_limits<int>::min();
        const reachable_cost_result<Width, Height> reachable = compute_reachable_costs(
                map, acting_unit.position, acting_unit.move_range);
        if(! reachable.valid)
        {
            best.error = ai_error::invalid_unit;
            return best;
        }
        const command_availability move_availability = command_eligibility_service::query(
                acting_unit, { battle_command_type::move });

        for(int destination_index = 0; destination_index < Width * Height; ++destination_index)
        {
            const grid_point destination = map.from_index(destination_index);
            if(reachable.cost(destination) < 0)
            {
                continue;
            }
            if(destination != acting_unit.position && ! move_availability.available())
            {
                continue;
            }

            battle_unit_instance simulated = acting_unit;
            simulated.position = destination;
            const int position_score = objective.has_focus_position ?
                    100 - _distance(destination, objective.focus_position) : 0;

            if(ability && target)
            {
                const command_availability ability_availability =
                        command_eligibility_service::query(simulated, {
                            battle_command_type::ability,
                            ability->cost.chakra,
                            ability->cost.inventory == 0,
                        });
                if(ability_availability.available())
                {
                    const ability_preview preview = ability_resolver::preview(
                            simulated, target, nullptr, *ability, target->position);
                    if(preview.legal())
                    {
                        ai_candidate candidate;
                        candidate.action = ai_action::ability;
                        candidate.destination = destination;
                        candidate.target_unit = target->id;
                        candidate.ability = ability->id;
                        candidate.score = 1000 + preview.damage * 100 + position_score;
                        _consider(candidate, best);
                    }
                }
            }

            if(objective.has_focus_position && destination != acting_unit.position)
            {
                ai_candidate candidate;
                candidate.action = ai_action::move;
                candidate.destination = destination;
                candidate.score = position_score;
                _consider(candidate, best);
            }
        }

        if(best.score == std::numeric_limits<int>::min())
        {
            best.action = ai_action::end_action;
            best.destination = acting_unit.position;
            best.score = 0;
        }
        return best;
    }

    template<int Width, int Height, std::size_t UnitCount>
    [[nodiscard]] static ai_plan plan(
            const grid_map<Width, Height>& map,
            const battle_unit_instance& acting_unit,
            const std::array<battle_unit_instance, UnitCount>& units,
            const action_definition* action,
            ai_objective objective,
            deterministic_rng& rng)
    {
        std::array<action_definition, 1> choices = {};
        std::size_t choice_count = 0;
        if(action)
        {
            choices[0] = *action;
            choice_count = 1;
        }
        return plan(map, acting_unit, units, choices, choice_count, objective, rng);
    }

    template<int Width, int Height, std::size_t UnitCount, std::size_t ActionCapacity>
    [[nodiscard]] static ai_plan plan(
            const grid_map<Width, Height>& map,
            const battle_unit_instance& acting_unit,
            const std::array<battle_unit_instance, UnitCount>& units,
            const std::array<action_definition, ActionCapacity>& actions,
            std::size_t action_count,
            ai_objective objective,
            deterministic_rng& rng)
    {
        static_assert(UnitCount > 0);
        static_assert(ActionCapacity > 0);
        (void) rng;
        if(! acting_unit.active || acting_unit.ledger.completed)
        {
            ai_plan result;
            result.error = ai_error::invalid_unit;
            return result;
        }
        const battle_unit_instance* target = _find_unit(units, objective.target_unit);
        if(objective.target_unit != no_battle_unit && (! target || ! target->active))
        {
            ai_plan result;
            result.error = ai_error::invalid_objective;
            return result;
        }
        if(objective.protected_unit != no_battle_unit &&
                ! _find_unit(units, objective.protected_unit))
        {
            ai_plan result;
            result.error = ai_error::invalid_objective;
            return result;
        }
        if(action_count > ActionCapacity)
        {
            ai_plan result;
            result.error = ai_error::invalid_objective;
            return result;
        }

        ai_plan best;
        best.destination = acting_unit.position;
        best.score = std::numeric_limits<int>::min();
        const reachable_cost_result<Width, Height> reachable = compute_reachable_costs(
                map, acting_unit.position, acting_unit.move_range);
        if(! reachable.valid)
        {
            best.error = ai_error::invalid_unit;
            return best;
        }
        const command_availability move_availability = command_eligibility_service::query(
                acting_unit, { battle_command_type::move });
        for(int destination_index = 0; destination_index < Width * Height; ++destination_index)
        {
            const grid_point destination = map.from_index(destination_index);
            if(reachable.cost(destination) < 0 ||
                    (destination != acting_unit.position && ! move_availability.available()))
            {
                continue;
            }
            battle_unit_instance simulated = acting_unit;
            simulated.position = destination;
            const int position_score = objective.has_focus_position ?
                    100 - _distance(destination, objective.focus_position) : 0;
            if(target)
            {
                for(std::size_t action_index = 0; action_index < action_count; ++action_index)
                {
                    const action_definition& action = actions[action_index];
                    const action_preview preview = battle_action_resolver::preview_units(
                            simulated, target, nullptr, true, action, target->position);
                    if(preview.legal())
                    {
                        ai_candidate candidate;
                        candidate.action = ai_action::ability;
                        candidate.destination = destination;
                        candidate.target_unit = target->id;
                        candidate.ability = action.id;
                        candidate.score = 1000 + preview.total_damage * 100 + position_score;
                        _consider(candidate, best);
                    }
                }
            }
            if(objective.has_focus_position && destination != acting_unit.position)
            {
                ai_candidate candidate;
                candidate.action = ai_action::move;
                candidate.destination = destination;
                candidate.score = position_score;
                _consider(candidate, best);
            }
        }
        if(best.score == std::numeric_limits<int>::min())
        {
            best.action = ai_action::end_action;
            best.destination = acting_unit.position;
            best.score = 0;
        }
        return best;
    }

private:
    template<std::size_t UnitCount>
    [[nodiscard]] static const battle_unit_instance* _find_unit(
            const std::array<battle_unit_instance, UnitCount>& units,
            battle_unit_id id)
    {
        if(id == no_battle_unit)
        {
            return nullptr;
        }
        for(const battle_unit_instance& unit : units)
        {
            if(unit.id == id)
            {
                return &unit;
            }
        }
        return nullptr;
    }

    static void _consider(const ai_candidate& candidate, ai_plan& best)
    {
        if(candidate.score > best.score)
        {
            static_cast<ai_candidate&>(best) = candidate;
        }
    }

    [[nodiscard]] static int _distance(grid_point first, grid_point second)
    {
        const int dx = first.x > second.x ? first.x - second.x : second.x - first.x;
        const int dy = first.y > second.y ? first.y - second.y : second.y - first.y;
        return dx + dy;
    }
};

}

#endif
