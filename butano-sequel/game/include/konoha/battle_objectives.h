#ifndef KONOHA_BATTLE_OBJECTIVES_H
#define KONOHA_BATTLE_OBJECTIVES_H

#include "konoha/battle_session.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_domain_event : std::uint8_t
{
    movement_committed,
    effects_resolved,
    unit_completed,
    side_ended,
    round_ended,
    script_event,
};

enum class battle_outcome : std::uint8_t
{
    none,
    victory,
    failure,
};

enum class objective_predicate_kind : std::uint8_t
{
    defeated,
    alive,
    captured,
    at_position,
    facing,
    completed,
    round_at_least,
    script_variable_equals,
};

struct objective_predicate
{
    objective_predicate_kind kind = objective_predicate_kind::alive;
    battle_unit_id unit = no_battle_unit;
    grid_point position = {};
    battle_facing facing_value = battle_facing::up;
    std::size_t variable_index = 0;
    int value = 0;
};

enum class objective_node_kind : std::uint8_t
{
    predicate,
    all,
    any,
    negate,
    count_at_least,
};

struct objective_node
{
    objective_node_kind kind = objective_node_kind::predicate;
    objective_predicate condition;
    std::size_t operand_count = 0;
    std::size_t threshold = 0;
};

template<std::size_t MaxNodes>
struct objective_rule
{
    static_assert(MaxNodes > 0);

    battle_domain_event trigger = battle_domain_event::effects_resolved;
    battle_outcome outcome = battle_outcome::none;
    int priority = 0;
    std::array<objective_node, MaxNodes> nodes = {};
    std::size_t node_count = 0;
    bool enabled = true;
};

enum class objective_error : std::uint8_t
{
    none,
    malformed_expression,
    invalid_predicate,
};

struct objective_result
{
    objective_error error = objective_error::none;
    battle_outcome outcome = battle_outcome::none;
    int priority = 0;
    std::size_t rule_index = 0;
    bool interrupts_action_tail = false;

    [[nodiscard]] constexpr bool success() const
    {
        return error == objective_error::none;
    }
};

template<std::size_t MaxUnits, std::size_t MaxVariables>
class objective_context
{
    static_assert(MaxUnits > 0);
    static_assert(MaxVariables > 0);

public:
    [[nodiscard]] bool add_unit(const battle_unit_instance& unit)
    {
        if(_unit_count == MaxUnits || this->unit(unit.id))
        {
            return false;
        }
        _units[_unit_count] = unit;
        ++_unit_count;
        return true;
    }

    [[nodiscard]] const battle_unit_instance* unit(battle_unit_id id) const
    {
        for(std::size_t index = 0; index < _unit_count; ++index)
        {
            if(_units[index].id == id)
            {
                return &_units[index];
            }
        }
        return nullptr;
    }

    [[nodiscard]] battle_unit_instance* mutable_unit(battle_unit_id id)
    {
        for(std::size_t index = 0; index < _unit_count; ++index)
        {
            if(_units[index].id == id)
            {
                return &_units[index];
            }
        }
        return nullptr;
    }

    [[nodiscard]] bool set_script_variable(std::size_t index, int value)
    {
        if(index >= MaxVariables)
        {
            return false;
        }
        _script_variables[index] = value;
        return true;
    }

    [[nodiscard]] const int* script_variable(std::size_t index) const
    {
        return index < MaxVariables ? &_script_variables[index] : nullptr;
    }

    void set_round(int round)
    {
        _round = round;
    }

    [[nodiscard]] int round() const
    {
        return _round;
    }

private:
    std::array<battle_unit_instance, MaxUnits> _units = {};
    std::array<int, MaxVariables> _script_variables = {};
    std::size_t _unit_count = 0;
    int _round = 1;
};

class objective_engine
{
public:
    template<std::size_t MaxUnits, std::size_t MaxVariables,
             std::size_t MaxNodes, std::size_t RuleCount>
    [[nodiscard]] static objective_result evaluate(
            const objective_context<MaxUnits, MaxVariables>& context,
            battle_domain_event event,
            const std::array<objective_rule<MaxNodes>, RuleCount>& rules)
    {
        objective_result best;
        bool has_outcome = false;
        for(std::size_t index = 0; index < RuleCount; ++index)
        {
            const objective_rule<MaxNodes>& rule = rules[index];
            if(! rule.enabled || rule.trigger != event)
            {
                continue;
            }
            if(rule.outcome == battle_outcome::none || rule.node_count == 0 ||
                    rule.node_count > MaxNodes)
            {
                return { objective_error::malformed_expression };
            }

            bool matched = false;
            const objective_error error = _evaluate_expression(context, rule, matched);
            if(error != objective_error::none)
            {
                return { error };
            }
            if(! matched)
            {
                continue;
            }

            const bool wins_tie = has_outcome && rule.priority == best.priority &&
                    rule.outcome == battle_outcome::failure &&
                    best.outcome != battle_outcome::failure;
            if(! has_outcome || rule.priority > best.priority || wins_tie)
            {
                best.outcome = rule.outcome;
                best.priority = rule.priority;
                best.rule_index = index;
                has_outcome = true;
            }
        }
        best.interrupts_action_tail = has_outcome &&
                (event == battle_domain_event::movement_committed ||
                 event == battle_domain_event::effects_resolved);
        return best;
    }

private:
    template<std::size_t MaxUnits, std::size_t MaxVariables, std::size_t MaxNodes>
    [[nodiscard]] static objective_error _evaluate_expression(
            const objective_context<MaxUnits, MaxVariables>& context,
            const objective_rule<MaxNodes>& rule,
            bool& result)
    {
        std::array<bool, MaxNodes> stack = {};
        std::size_t size = 0;
        for(std::size_t index = 0; index < rule.node_count; ++index)
        {
            const objective_node& node = rule.nodes[index];
            if(node.kind == objective_node_kind::predicate)
            {
                bool value = false;
                const objective_error error = _evaluate_predicate(context, node.condition, value);
                if(error != objective_error::none)
                {
                    return error;
                }
                stack[size] = value;
                ++size;
                continue;
            }

            if(node.kind == objective_node_kind::negate)
            {
                if(size == 0)
                {
                    return objective_error::malformed_expression;
                }
                stack[size - 1] = ! stack[size - 1];
                continue;
            }

            if(node.operand_count == 0 || node.operand_count > size ||
                    (node.kind == objective_node_kind::count_at_least &&
                     node.threshold > node.operand_count))
            {
                return objective_error::malformed_expression;
            }
            const std::size_t begin = size - node.operand_count;
            std::size_t true_count = 0;
            for(std::size_t operand = begin; operand < size; ++operand)
            {
                true_count += stack[operand] ? 1U : 0U;
            }
            bool combined = false;
            if(node.kind == objective_node_kind::all)
            {
                combined = true_count == node.operand_count;
            }
            else if(node.kind == objective_node_kind::any)
            {
                combined = true_count > 0;
            }
            else if(node.kind == objective_node_kind::count_at_least)
            {
                combined = true_count >= node.threshold;
            }
            else
            {
                return objective_error::malformed_expression;
            }
            size = begin;
            stack[size] = combined;
            ++size;
        }

        if(size != 1)
        {
            return objective_error::malformed_expression;
        }
        result = stack[0];
        return objective_error::none;
    }

    template<std::size_t MaxUnits, std::size_t MaxVariables>
    [[nodiscard]] static objective_error _evaluate_predicate(
            const objective_context<MaxUnits, MaxVariables>& context,
            const objective_predicate& predicate,
            bool& result)
    {
        if(predicate.kind == objective_predicate_kind::round_at_least)
        {
            result = context.round() >= predicate.value;
            return objective_error::none;
        }
        if(predicate.kind == objective_predicate_kind::script_variable_equals)
        {
            const int* variable = context.script_variable(predicate.variable_index);
            if(! variable)
            {
                return objective_error::invalid_predicate;
            }
            result = *variable == predicate.value;
            return objective_error::none;
        }

        const battle_unit_instance* unit = context.unit(predicate.unit);
        if(! unit)
        {
            return objective_error::invalid_predicate;
        }
        switch(predicate.kind)
        {
        case objective_predicate_kind::defeated:
            result = ! unit->active || unit->hp <= 0;
            break;
        case objective_predicate_kind::alive:
            result = unit->active && unit->hp > 0;
            break;
        case objective_predicate_kind::captured:
            result = unit->captured;
            break;
        case objective_predicate_kind::at_position:
            result = unit->position == predicate.position;
            break;
        case objective_predicate_kind::facing:
            result = unit->facing == predicate.facing_value;
            break;
        case objective_predicate_kind::completed:
            result = unit->ledger.completed;
            break;
        default:
            return objective_error::invalid_predicate;
        }
        return objective_error::none;
    }
};

}

#endif
