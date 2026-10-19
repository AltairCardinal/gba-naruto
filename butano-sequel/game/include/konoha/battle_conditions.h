#ifndef KONOHA_BATTLE_CONDITIONS_H
#define KONOHA_BATTLE_CONDITIONS_H

#include "konoha/battle_session.h"
#include "konoha/battlefield_objects.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr std::uint8_t no_condition_slot = 0xFF;

enum class battle_condition_type : std::uint8_t
{
    empty = 0,
    no_valid_unit_for_side = 1,
    round_limit_reached = 2,
    no_valid_character_for_side = 3,
    unused_4 = 4,
    unused_5 = 5,
    object_slot_inactive = 6,
    side_hp_sum_greater = 7,
    side_unit_count_greater = 8,
    side_resolved_object_count_greater = 9,
};

struct battle_condition_predicate
{
    battle_condition_type type = battle_condition_type::empty;
    std::uint8_t arg0 = 0;
    std::uint8_t arg1 = 0;
    std::uint32_t script_address = 0;
};

struct battle_condition_variant
{
    std::array<std::uint8_t, 4> header = {};
    std::array<battle_condition_predicate, 4> win = {};
    std::array<battle_condition_predicate, 4> lose = {};
};

enum class battle_condition_outcome : std::uint8_t
{
    none = 0,
    win = 1,
    loss = 2,
    equal_slot_result = 5,
};

enum class battle_condition_error : std::uint8_t
{
    none,
    invalid_side,
    invalid_object_slot,
    unsupported_type,
};

struct battle_condition_result
{
    battle_condition_error error = battle_condition_error::none;
    battle_condition_outcome outcome = battle_condition_outcome::none;
    std::uint8_t first_win_slot = no_condition_slot;
    std::uint8_t first_loss_slot = no_condition_slot;
    std::uint8_t presentation_id = 0;
    bool ends_battle = false;
};

template<std::size_t MaxUnits>
class battle_condition_context
{
    static_assert(MaxUnits > 0);

public:
    battle_condition_context() = default;

    explicit battle_condition_context(
            const battle_session<MaxUnits>& session) :
        _round_index(session.round_index()),
        _full_round_boundary(session.full_round_boundary()),
        _objects(session.objects())
    {
        for(std::size_t index = 0; index < session.unit_count(); ++index)
        {
            (void) add_unit(*session.unit_at(index));
        }
        _resolved_object_counts[0] =
                session.resolved_object_count(battle_side::player);
        _resolved_object_counts[1] =
                session.resolved_object_count(battle_side::enemy);
    }

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

    void set_round_limit(int value)
    {
        _round_limit = value;
    }

    void set_round_index(int value)
    {
        _round_index = value;
    }

    void set_full_round_boundary(bool value)
    {
        _full_round_boundary = value;
    }

    [[nodiscard]] int round_limit() const
    {
        return _round_limit;
    }

    [[nodiscard]] int round_index() const
    {
        return _round_index;
    }

    [[nodiscard]] bool full_round_boundary() const
    {
        return _full_round_boundary;
    }

    [[nodiscard]] battlefield_object_table& objects()
    {
        return _objects;
    }

    [[nodiscard]] const battlefield_object_table& objects() const
    {
        return _objects;
    }

    [[nodiscard]] bool resolve_behavior_9(
            std::uint8_t slot, battle_side resolving_side)
    {
        const battlefield_object_record* value = _objects.record(slot);
        if(! value || value->type == 0 || value->behavior != 9)
        {
            return false;
        }
        if(! _objects.free(slot))
        {
            return false;
        }
        ++_resolved_object_counts[_side_index(resolving_side)];
        return true;
    }

    [[nodiscard]] int resolved_object_count(battle_side side) const
    {
        return _resolved_object_counts[_side_index(side)];
    }

private:
    friend class battle_condition_interpreter;

    [[nodiscard]] static constexpr std::size_t _side_index(battle_side side)
    {
        return side == battle_side::player ? 0 : 1;
    }

    std::array<battle_unit_instance, MaxUnits> _units = {};
    std::size_t _unit_count = 0;
    int _round_limit = 0;
    int _round_index = 1;
    bool _full_round_boundary = false;
    battlefield_object_table _objects;
    std::array<int, 2> _resolved_object_counts = {};
};

class battle_condition_interpreter
{
public:
    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_condition_result evaluate_session(
            const battle_session<MaxUnits>& session,
            const battle_condition_variant& variant)
    {
        const battle_condition_context<MaxUnits> context(session);
        return evaluate(context, variant);
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_condition_result evaluate(
            const battle_condition_context<MaxUnits>& context,
            const battle_condition_variant& variant)
    {
        battle_condition_result result;
        const int round_limit = variant.header[0] != 0 ?
                variant.header[0] : context._round_limit;
        result.error = _first_match(
                context, variant.win, round_limit, result.first_win_slot);
        if(result.error != battle_condition_error::none)
        {
            return result;
        }
        result.error = _first_match(
                context, variant.lose, round_limit, result.first_loss_slot);
        if(result.error != battle_condition_error::none)
        {
            return result;
        }

        const bool win = result.first_win_slot != no_condition_slot;
        const bool loss = result.first_loss_slot != no_condition_slot;
        if(win && loss)
        {
            if(result.first_win_slot < result.first_loss_slot)
            {
                result.outcome = battle_condition_outcome::win;
            }
            else if(result.first_loss_slot < result.first_win_slot)
            {
                result.outcome = battle_condition_outcome::loss;
            }
            else
            {
                result.outcome = battle_condition_outcome::equal_slot_result;
            }
        }
        else if(win)
        {
            result.outcome = battle_condition_outcome::win;
        }
        else if(loss)
        {
            result.outcome = battle_condition_outcome::loss;
        }

        result.presentation_id = _presentation_id(result.outcome);
        result.ends_battle = result.outcome != battle_condition_outcome::none;
        return result;
    }

private:
    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_condition_error _first_match(
            const battle_condition_context<MaxUnits>& context,
            const std::array<battle_condition_predicate, 4>& predicates,
            int round_limit,
            std::uint8_t& first_slot)
    {
        for(std::uint8_t index = 0; index < predicates.size(); ++index)
        {
            if(predicates[index].type == battle_condition_type::empty)
            {
                continue;
            }
            bool matched = false;
            const battle_condition_error error =
                    _evaluate_predicate(
                            context, predicates[index], round_limit, matched);
            if(error != battle_condition_error::none)
            {
                return error;
            }
            if(matched)
            {
                first_slot = index;
                return battle_condition_error::none;
            }
        }
        return battle_condition_error::none;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_condition_error _evaluate_predicate(
            const battle_condition_context<MaxUnits>& context,
            const battle_condition_predicate& predicate,
            int round_limit,
            bool& result)
    {
        result = false;
        if(predicate.type == battle_condition_type::round_limit_reached)
        {
            result = _at_round_limit(context, round_limit);
            return battle_condition_error::none;
        }
        if(predicate.type == battle_condition_type::object_slot_inactive)
        {
            const unsigned slot = static_cast<unsigned>(predicate.arg0) + 1;
            const battlefield_object_record* object =
                    context._objects.record(static_cast<std::uint8_t>(slot));
            if(slot >= 32 || ! object)
            {
                return battle_condition_error::invalid_object_slot;
            }
            result = object->type == 0;
            return battle_condition_error::none;
        }
        if(predicate.type == battle_condition_type::unused_4 ||
                predicate.type == battle_condition_type::unused_5)
        {
            return battle_condition_error::unsupported_type;
        }

        battle_side side;
        const battle_condition_error side_error = _decode_side(predicate.arg0, side);
        if(side_error != battle_condition_error::none)
        {
            return side_error;
        }
        switch(predicate.type)
        {
        case battle_condition_type::no_valid_unit_for_side:
            result = _valid_unit_count(context, side) == 0;
            break;
        case battle_condition_type::no_valid_character_for_side:
            result = ! _has_valid_character(context, side, predicate.arg1);
            break;
        case battle_condition_type::side_hp_sum_greater:
            result = _at_round_limit(context, round_limit) &&
                    _hp_sum(context, side) > _hp_sum(context, _other_side(side));
            break;
        case battle_condition_type::side_unit_count_greater:
            result = _at_round_limit(context, round_limit) &&
                    _valid_unit_count(context, side) >
                    _valid_unit_count(context, _other_side(side));
            break;
        case battle_condition_type::side_resolved_object_count_greater:
            result = _at_round_limit(context, round_limit) &&
                    context.resolved_object_count(side) >
                    context.resolved_object_count(_other_side(side));
            break;
        default:
            return battle_condition_error::unsupported_type;
        }
        return battle_condition_error::none;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static bool _at_round_limit(
            const battle_condition_context<MaxUnits>& context,
            int round_limit)
    {
        return context._full_round_boundary && round_limit != 0 &&
                round_limit == context._round_index;
    }

    [[nodiscard]] static battle_condition_error _decode_side(
            std::uint8_t raw, battle_side& side)
    {
        if(raw > 1)
        {
            return battle_condition_error::invalid_side;
        }
        side = raw == 0 ? battle_side::player : battle_side::enemy;
        return battle_condition_error::none;
    }

    [[nodiscard]] static constexpr battle_side _other_side(battle_side side)
    {
        return side == battle_side::player ? battle_side::enemy : battle_side::player;
    }

    [[nodiscard]] static bool _valid(const battle_unit_instance& unit)
    {
        const std::uint32_t state = unit.status_mask & 0x0E;
        return unit.active && unit.hp > 0 && (state == 0 || state == 8);
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static int _valid_unit_count(
            const battle_condition_context<MaxUnits>& context, battle_side side)
    {
        int result = 0;
        for(std::size_t index = 0; index < context._unit_count; ++index)
        {
            const battle_unit_instance& unit = context._units[index];
            result += unit.side == side && _valid(unit);
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static bool _has_valid_character(
            const battle_condition_context<MaxUnits>& context,
            battle_side side,
            std::uint8_t character)
    {
        for(std::size_t index = 0; index < context._unit_count; ++index)
        {
            const battle_unit_instance& unit = context._units[index];
            if(unit.side == side && unit.character_id == character && _valid(unit))
            {
                return true;
            }
        }
        return false;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static int _hp_sum(
            const battle_condition_context<MaxUnits>& context, battle_side side)
    {
        int result = 0;
        for(std::size_t index = 0; index < context._unit_count; ++index)
        {
            const battle_unit_instance& unit = context._units[index];
            if(unit.side == side && _valid(unit))
            {
                result += unit.hp;
            }
        }
        return result;
    }

    [[nodiscard]] static constexpr std::uint8_t _presentation_id(
            battle_condition_outcome outcome)
    {
        switch(outcome)
        {
        case battle_condition_outcome::win:
            return 1;
        case battle_condition_outcome::loss:
            return 2;
        case battle_condition_outcome::equal_slot_result:
            return 3;
        case battle_condition_outcome::none:
            return 0;
        default:
            break;
        }
        return 0;
    }
};

}

#endif
