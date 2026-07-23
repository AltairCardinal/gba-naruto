#ifndef KONOHA_BATTLE_SESSION_H
#define KONOHA_BATTLE_SESSION_H

#include "konoha/grid_pathfinder.h"
#include "konoha/battle_attributes.h"
#include "konoha/battle_status_store.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

class ability_resolver;
class battle_action_resolver;

using battle_unit_id = std::uint8_t;
using ability_id = std::uint8_t;
using ninja_tool_id = std::uint8_t;

inline constexpr battle_unit_id no_battle_unit = 0xFF;
inline constexpr ability_id no_ability = 0xFF;
inline constexpr ninja_tool_id no_ninja_tool = 0;
inline constexpr std::uint8_t no_tool_slot = 0xFF;

enum class battle_side : std::uint8_t
{
    player,
    enemy,
};

enum class battle_control : std::uint8_t
{
    player,
    ai,
    scripted,
};

enum class battle_facing : std::uint8_t
{
    up,
    right,
    down,
    left,
};

enum class battle_lifecycle : std::uint8_t
{
    preparation,
    unit_select,
    action_drafting,
};

enum class battle_transition : std::uint8_t
{
    none,
    invalid,
    unit_selection_opened,
    action_draft_opened,
    move_previewed,
    unit_completed,
    side_changed,
    round_advanced,
};

struct unit_action_ledger
{
    bool moved = false;
    bool acted = false;
    bool completed = false;
    ability_id defense_ability = no_ability;

    constexpr bool operator==(const unit_action_ledger&) const = default;
};

struct battle_unit_instance
{
    battle_unit_id id;
    battle_side side;
    battle_control control;
    grid_point position;
    battle_facing facing;
    int hp;
    int max_hp;
    int chakra;
    int max_chakra;
    int move_range;
    bool active;
    unit_action_ledger ledger;
    battle_unit_id summoner = no_battle_unit;
    bool captured = false;
    bool substitution_ready = false;
    std::uint32_t status_mask = 0;
    int attack = 10;
    int defense = 0;
    int agility = 0;
    std::array<ninja_tool_id, 4> equipped_tools = {};
    battle_status_store statuses = {};
    int base_attack = -1;
    int base_defense = -1;
    int base_agility = -1;
    int base_move_range = -1;
    int base_max_hp = -1;

    constexpr bool operator==(const battle_unit_instance&) const = default;
};

struct action_draft
{
    bool active = false;
    battle_unit_id unit_id = 0;
    grid_point origin = {};
    grid_point preview_position = {};
    bool move_previewed = false;

    constexpr bool operator==(const action_draft&) const = default;
};

template<std::size_t MaxUnits>
class battle_session
{
    static_assert(MaxUnits > 0);

public:
    [[nodiscard]] bool add_unit(const battle_unit_instance& unit)
    {
        if(_unit_count == MaxUnits || _find_unit(unit.id))
        {
            return false;
        }
        _units[_unit_count] = unit;
        battle_attribute_system::initialize_base(_units[_unit_count]);
        battle_attribute_system::recompute(_units[_unit_count]);
        ++_unit_count;
        return true;
    }

    [[nodiscard]] battle_transition start_round()
    {
        if(_lifecycle != battle_lifecycle::preparation || ! _has_available(battle_side::player))
        {
            return battle_transition::invalid;
        }
        _round_index = 1;
        _current_side = battle_side::player;
        _reset_ledgers();
        _lifecycle = battle_lifecycle::unit_select;
        return battle_transition::unit_selection_opened;
    }

    [[nodiscard]] battle_transition select_unit(battle_unit_id id)
    {
        battle_unit_instance* selected = _find_unit(id);
        if(_lifecycle != battle_lifecycle::unit_select || ! selected || ! selected->active ||
                selected->side != _current_side || selected->ledger.completed)
        {
            return battle_transition::invalid;
        }
        _draft = {
            true,
            selected->id,
            selected->position,
            selected->position,
            false,
        };
        _lifecycle = battle_lifecycle::action_drafting;
        return battle_transition::action_draft_opened;
    }

    [[nodiscard]] battle_transition preview_move(grid_point destination)
    {
        if(_lifecycle != battle_lifecycle::action_drafting || ! _draft.active)
        {
            return battle_transition::invalid;
        }
        _draft.preview_position = destination;
        _draft.move_previewed = destination != _draft.origin;
        return battle_transition::move_previewed;
    }

    [[nodiscard]] battle_transition cancel_action()
    {
        if(_lifecycle != battle_lifecycle::action_drafting || ! _draft.active)
        {
            return battle_transition::invalid;
        }
        _draft = {};
        _lifecycle = battle_lifecycle::unit_select;
        return battle_transition::unit_selection_opened;
    }

    [[nodiscard]] battle_transition commit_action(
            battle_facing facing, ability_id defense_ability)
    {
        battle_unit_instance* selected = _find_unit(_draft.unit_id);
        if(_lifecycle != battle_lifecycle::action_drafting || ! _draft.active || ! selected)
        {
            return battle_transition::invalid;
        }

        selected->position = _draft.preview_position;
        selected->facing = facing;
        selected->ledger.moved = _draft.move_previewed;
        selected->ledger.completed = true;
        selected->ledger.defense_ability = defense_ability;
        _draft = {};
        _lifecycle = battle_lifecycle::unit_select;

        if(_has_available(_current_side))
        {
            return battle_transition::unit_completed;
        }
        _tick_all_statuses();
        if(_current_side == battle_side::player && _has_available(battle_side::enemy))
        {
            _current_side = battle_side::enemy;
            return battle_transition::side_changed;
        }

        ++_round_index;
        _current_side = battle_side::player;
        _reset_ledgers();
        return battle_transition::round_advanced;
    }

    [[nodiscard]] const battle_unit_instance* unit(battle_unit_id id) const
    {
        return _find_unit(id);
    }

    [[nodiscard]] const battle_unit_instance* cycle_available_unit(
            battle_unit_id current, int direction) const
    {
        if(_lifecycle != battle_lifecycle::unit_select || direction == 0 || _unit_count == 0)
        {
            return nullptr;
        }
        std::size_t start = _unit_count;
        for(std::size_t index = 0; index < _unit_count; ++index)
        {
            if(_units[index].id == current)
            {
                start = index;
                break;
            }
        }
        if(start == _unit_count)
        {
            return nullptr;
        }
        const int step = direction > 0 ? 1 : -1;
        for(std::size_t offset = 1; offset <= _unit_count; ++offset)
        {
            int candidate = static_cast<int>(start) + step * static_cast<int>(offset);
            candidate %= static_cast<int>(_unit_count);
            if(candidate < 0)
            {
                candidate += static_cast<int>(_unit_count);
            }
            const battle_unit_instance& unit = _units[static_cast<std::size_t>(candidate)];
            if(unit.active && unit.side == _current_side && ! unit.ledger.completed)
            {
                return &unit;
            }
        }
        return nullptr;
    }

    [[nodiscard]] std::size_t unit_count() const
    {
        return _unit_count;
    }

    [[nodiscard]] int round_index() const
    {
        return _round_index;
    }

    [[nodiscard]] battle_side current_side() const
    {
        return _current_side;
    }

    [[nodiscard]] battle_lifecycle lifecycle() const
    {
        return _lifecycle;
    }

    [[nodiscard]] const action_draft& draft() const
    {
        return _draft;
    }

    [[nodiscard]] bool occupied(grid_point position) const
    {
        for(std::size_t index = 0; index < _unit_count; ++index)
        {
            if(_units[index].active && _units[index].position == position)
            {
                return true;
            }
        }
        return false;
    }

    constexpr bool operator==(const battle_session&) const = default;

private:
    friend class ability_resolver;
    friend class battle_action_resolver;

    [[nodiscard]] battle_unit_instance* _find_unit(battle_unit_id id)
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

    [[nodiscard]] const battle_unit_instance* _find_unit(battle_unit_id id) const
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

    [[nodiscard]] bool _has_available(battle_side side) const
    {
        for(std::size_t index = 0; index < _unit_count; ++index)
        {
            const battle_unit_instance& unit = _units[index];
            if(unit.active && unit.side == side && ! unit.ledger.completed)
            {
                return true;
            }
        }
        return false;
    }

    void _reset_ledgers()
    {
        for(std::size_t index = 0; index < _unit_count; ++index)
        {
            _units[index].ledger = {};
        }
    }

    void _tick_all_statuses()
    {
        for(std::size_t index = 0; index < _unit_count; ++index)
        {
            if(_units[index].active)
            {
                (void) _units[index].statuses.tick_side_end();
                battle_attribute_system::recompute(_units[index]);
            }
        }
    }

    std::array<battle_unit_instance, MaxUnits> _units = {};
    std::size_t _unit_count = 0;
    int _round_index = 0;
    battle_side _current_side = battle_side::player;
    battle_lifecycle _lifecycle = battle_lifecycle::preparation;
    action_draft _draft;
};

}

#endif
