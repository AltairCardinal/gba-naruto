#ifndef KONOHA_BATTLE_SESSION_H
#define KONOHA_BATTLE_SESSION_H

#include "konoha/grid_pathfinder.h"
#include "konoha/battle_attributes.h"
#include "konoha/battle_command_blockers.h"
#include "konoha/battle_status_store.h"
#include "konoha/battle_passives.h"
#include "konoha/battle_side_start_passives.h"
#include "konoha/battlefield_objects.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

class battle_action_resolver;
class battle_action_combinations;
class battle_capture_system;
class battle_defense_preparation;
class battle_resource_commands;
class battle_turn_flow;

using battle_unit_id = std::uint8_t;
using ability_id = std::uint8_t;
using ninja_tool_id = std::uint8_t;

inline constexpr battle_unit_id no_battle_unit = 0xFF;
inline constexpr ability_id no_ability = 0xFF;
inline constexpr ninja_tool_id no_ninja_tool = 0;
inline constexpr std::uint8_t no_tool_slot = 0xFF;
inline constexpr std::size_t battle_primary_action_slot_capacity = 15;
inline constexpr std::size_t battle_ninja_tool_slot_capacity = 9;
inline constexpr std::size_t battle_action_catalog_capacity =
        battle_primary_action_slot_capacity +
        battle_ninja_tool_slot_capacity;

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

enum class defense_action_kind : std::uint8_t
{
    none,
    active_action,
    ninja_tool,
};

struct prepared_defense_action
{
    defense_action_kind kind = defense_action_kind::none;
    ability_id action_id = no_ability;
    std::uint8_t tool_slot = no_tool_slot;

    constexpr bool operator==(const prepared_defense_action&) const = default;
};

enum class battle_lifecycle : std::uint8_t
{
    preparation,
    unit_select,
    action_drafting,
    effects_resolved,
    facing_select,
    defense_select,
};

enum class battle_transition : std::uint8_t
{
    none,
    invalid,
    unit_selection_opened,
    action_draft_opened,
    move_previewed,
    effects_committed,
    facing_selection_opened,
    defense_selection_opened,
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
    defense_action_kind defense_kind = defense_action_kind::none;
    std::uint8_t defense_tool_slot = no_tool_slot;

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
    std::uint32_t status_mask = 0;
    int attack = 10;
    int defense = 0;
    int agility = 0;
    int hand_seals = 0;
    std::array<ninja_tool_id, battle_ninja_tool_slot_capacity>
            equipped_tools = {};
    battle_status_store statuses = {};
    int base_attack = -1;
    int base_defense = -1;
    int base_agility = -1;
    int base_move_range = -1;
    int base_max_hp = -1;
    std::uint8_t character_id = 0;
    int level = 1;
    std::array<ability_id, battle_primary_action_slot_capacity>
            primary_action_ids = {};
    std::array<std::uint8_t, battle_primary_action_slot_capacity>
            primary_action_levels = {};
    std::uint8_t original_character_id = 0;
    std::uint8_t identity_override_character_id = no_battle_unit;
    bool special_identity_variant = false;
    std::uint8_t ai_role = 0;
    battle_unit_id ai_linked_unit = no_battle_unit;
    battle_unit_id ai_secondary_linked_unit = no_battle_unit;
    std::uint8_t ai_config_id = 1;
    std::uint8_t unit_state_code = 0;
    std::uint8_t reaction_state = 0;
    battle_passive_state passives = {};
    int carried_experience = 0;
    bool side_start_passive_latched = false;
    int ninja_tool_capacity = 0;
    std::uint8_t formation_unit_parameter = 0;

    constexpr bool operator==(const battle_unit_instance&) const = default;
};

enum class identity_restore_reason : std::uint8_t
{
    natural_expiry,
    cleanup,
};

class battle_identity_system
{
public:
    [[nodiscard]] static bool apply(
            battle_unit_instance& source,
            const battle_unit_instance& target,
            std::uint8_t duration_turns,
            std::uint8_t flags)
    {
        battle_unit_instance changed = source;
        if(! changed.statuses.upsert({
                   static_cast<std::uint8_t>(0x05 | flags),
                   0,
                   encode_status_duration_ticks(duration_turns),
                   0,
                   target.id,
                   0,
                   0,
               }))
        {
            return false;
        }
        changed.character_id = target.character_id;
        changed.identity_override_character_id = target.character_id;
        source = changed;
        return true;
    }

    [[nodiscard]] static bool cleanup(
            battle_unit_instance& unit, identity_restore_reason reason)
    {
        if(unit.statuses.find(0x05) == no_status_slot)
        {
            return false;
        }
        _restore_identity(unit, reason);
        return unit.statuses.remove(0x05, status_remove_mode::preserve_removed_event);
    }

    static void restore_after_natural_expiry(battle_unit_instance& unit)
    {
        _restore_identity(unit, identity_restore_reason::natural_expiry);
    }

private:
    static void _restore_identity(
            battle_unit_instance& unit, identity_restore_reason)
    {
        if(unit.special_identity_variant && unit.original_character_id == 8)
        {
            unit.character_id = 0x39;
        }
        else if(unit.special_identity_variant && unit.original_character_id == 15)
        {
            unit.character_id = 0x3A;
        }
        else
        {
            unit.character_id = unit.original_character_id;
        }
        unit.identity_override_character_id = no_battle_unit;
    }
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
    struct battlefield_topology;

public:
    [[nodiscard]] constexpr std::uint8_t battle_id() const
    {
        return _battle_id;
    }

    constexpr void set_battle_id(std::uint8_t battle_id)
    {
        _battle_id = battle_id;
    }

    template<int Width, int Height>
    [[nodiscard]] bool configure_battlefield(
            const grid_map<Width, Height>& map)
    {
        if(map.active_width() > 32 ||
                map.active_height() > 32)
        {
            return false;
        }
        battlefield_topology next;
        next.configured = true;
        next.width = static_cast<std::uint8_t>(
                map.active_width());
        next.height = static_cast<std::uint8_t>(
                map.active_height());
        for(int y = 0; y < map.active_height(); ++y)
        {
            for(int x = 0;
                    x < map.active_width();
                    ++x)
            {
                if(map.cost({ x, y }) > 0 &&
                        map.terrain_class(
                                { x, y }) !=
                                grid_fully_closed)
                {
                    next.traversable_rows[
                            static_cast<std::size_t>(y)] |=
                            static_cast<std::uint32_t>(
                                    1U << x);
                }
            }
        }
        _battlefield = next;
        return true;
    }

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
        _full_round_boundary = false;
        _reset_ledgers();
        _apply_side_start_passives(_current_side);
        _lifecycle = battle_lifecycle::unit_select;
        return battle_transition::unit_selection_opened;
    }

    [[nodiscard]] battle_transition select_unit(battle_unit_id id)
    {
        battle_unit_instance* selected = _find_unit(id);
        if(_lifecycle != battle_lifecycle::unit_select || ! selected ||
                ! _can_issue_commands(*selected))
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
        _full_round_boundary = false;
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

    [[nodiscard]] battle_transition open_facing_selection()
    {
        battle_unit_instance* selected = _find_unit(_draft.unit_id);
        if((_lifecycle != battle_lifecycle::action_drafting &&
                   _lifecycle != battle_lifecycle::effects_resolved) ||
                ! _draft.active || ! selected)
        {
            return battle_transition::invalid;
        }

        if(_lifecycle == battle_lifecycle::action_drafting)
        {
            selected->position = _draft.preview_position;
            selected->ledger.moved = _draft.move_previewed;
        }
        _lifecycle = battle_lifecycle::facing_select;
        return battle_transition::facing_selection_opened;
    }

    [[nodiscard]] battle_transition select_facing(battle_facing facing)
    {
        battle_unit_instance* selected = _find_unit(_draft.unit_id);
        if(_lifecycle != battle_lifecycle::facing_select ||
                ! _draft.active || ! selected)
        {
            return battle_transition::invalid;
        }

        selected->facing = facing;
        _lifecycle = battle_lifecycle::defense_select;
        return battle_transition::defense_selection_opened;
    }

    [[nodiscard]] battle_transition reopen_facing_selection()
    {
        battle_unit_instance* selected = _find_unit(_draft.unit_id);
        if(_lifecycle != battle_lifecycle::defense_select ||
                ! _draft.active || ! selected)
        {
            return battle_transition::invalid;
        }

        _lifecycle = battle_lifecycle::facing_select;
        return battle_transition::facing_selection_opened;
    }

    [[nodiscard]] battle_transition complete_action(
            prepared_defense_action defense)
    {
        battle_unit_instance* selected = _find_unit(_draft.unit_id);
        if(_lifecycle != battle_lifecycle::defense_select ||
                ! _draft.active || ! selected)
        {
            return battle_transition::invalid;
        }
        return _finish_selected_action(
                *selected, defense, true);
    }

    [[nodiscard]] battle_transition complete_action(
            ability_id defense_ability)
    {
        return complete_action({
            defense_ability == no_ability ?
                    defense_action_kind::none :
                    defense_action_kind::active_action,
            defense_ability,
            no_tool_slot,
        });
    }

    [[nodiscard]] battle_transition commit_action(
            battle_facing facing, ability_id defense_ability)
    {
        if(open_facing_selection() !=
                battle_transition::facing_selection_opened ||
                select_facing(facing) !=
                        battle_transition::defense_selection_opened)
        {
            return battle_transition::invalid;
        }
        return complete_action(defense_ability);
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
            if(_can_issue_commands(unit))
            {
                return &unit;
            }
        }
        return nullptr;
    }

    [[nodiscard]] const battle_unit_instance* cycle_roster_unit(
            battle_unit_id current, int direction) const
    {
        if(_lifecycle != battle_lifecycle::unit_select || direction == 0 ||
                _unit_count == 0)
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
            int candidate = static_cast<int>(start) +
                    step * static_cast<int>(offset);
            candidate %= static_cast<int>(_unit_count);
            if(candidate < 0)
            {
                candidate += static_cast<int>(_unit_count);
            }
            const battle_unit_instance& unit =
                    _units[static_cast<std::size_t>(candidate)];
            if(unit.active && unit.side == _current_side)
            {
                return &unit;
            }
        }
        return nullptr;
    }

    [[nodiscard]] bool can_issue_commands(battle_unit_id id) const
    {
        const battle_unit_instance* candidate = _find_unit(id);
        return _lifecycle == battle_lifecycle::unit_select &&
                candidate && _can_issue_commands(*candidate);
    }

    [[nodiscard]] std::size_t unit_count() const
    {
        return _unit_count;
    }

    [[nodiscard]] const battle_unit_instance* unit_at(
            std::size_t index) const
    {
        return index < _unit_count ? &_units[index] : nullptr;
    }

    [[nodiscard]] const battle_unit_instance* active_unit_at(
            grid_point position) const
    {
        for(std::size_t index = 0; index < _unit_count; ++index)
        {
            const battle_unit_instance& candidate = _units[index];
            if(candidate.active && candidate.position == position)
            {
                return &candidate;
            }
        }
        return nullptr;
    }

    [[nodiscard]] const battle_unit_instance* first_inactive_unit() const
    {
        for(std::size_t index = 0; index < _unit_count; ++index)
        {
            if(! _units[index].active)
            {
                return &_units[index];
            }
        }
        return nullptr;
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
        if(! value || value->type == 0 || value->behavior != 9 ||
                ! _objects.free(slot))
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

    [[nodiscard]] std::size_t object_tick_event_count() const
    {
        return _object_tick_event_count;
    }

    [[nodiscard]] const battlefield_object_tick_event*
    object_tick_event_at(std::size_t index) const
    {
        return index < _object_tick_event_count ?
                &_object_tick_events[index] : nullptr;
    }

    [[nodiscard]] bool record_object_tick_resolution(
            std::size_t index,
            const std::array<battle_unit_id, 12>& affected_unit_ids,
            int affected_unit_count,
            bool affected_units_truncated,
            int impact_count,
            int total_damage)
    {
        if(index >= _object_tick_event_count ||
                affected_unit_count < 0 ||
                affected_unit_count >
                        static_cast<int>(
                                affected_unit_ids.size()) ||
                impact_count < 0 ||
                total_damage < 0)
        {
            return false;
        }
        battlefield_object_tick_event& event =
                _object_tick_events[index];
        event.affected_unit_ids = affected_unit_ids;
        event.affected_unit_count = affected_unit_count;
        event.affected_units_truncated =
                affected_units_truncated;
        event.impact_count = impact_count;
        event.total_damage = total_damage;
        return true;
    }

    [[nodiscard]] std::uint32_t object_tick_sequence() const
    {
        return _object_tick_sequence;
    }

    [[nodiscard]] int round_index() const
    {
        return _round_index;
    }

    [[nodiscard]] bool full_round_boundary() const
    {
        return _full_round_boundary;
    }

    [[nodiscard]] battle_side current_side() const
    {
        return _current_side;
    }

    [[nodiscard]] battle_lifecycle lifecycle() const
    {
        return _lifecycle;
    }

    [[nodiscard]] std::uint32_t side_start_sequence() const
    {
        return _side_start_sequence;
    }

    [[nodiscard]] std::size_t
    side_start_event_count() const
    {
        return _side_start_event_count;
    }

    [[nodiscard]] const battle_side_start_passive_event*
    side_start_event_at(std::size_t index) const
    {
        return index < _side_start_event_count ?
                &_side_start_events[index] :
                nullptr;
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
    struct battlefield_topology
    {
        bool configured = false;
        std::uint8_t width = 0;
        std::uint8_t height = 0;
        std::array<std::uint32_t, 32>
                traversable_rows = {};

        [[nodiscard]] bool contains(
                grid_point position) const
        {
            return configured &&
                    position.x >= 0 &&
                    position.x < width &&
                    position.y >= 0 &&
                    position.y < height &&
                    (traversable_rows[
                             static_cast<std::size_t>(
                                     position.y)] &
                     static_cast<std::uint32_t>(
                             1U << position.x)) != 0;
        }

        constexpr bool operator==(
                const battlefield_topology&) const =
                default;
    };

    friend class battle_action_resolver;
    friend class battle_action_combinations;
    friend class battle_capture_system;
    friend class battle_defense_preparation;
    friend class battle_resource_commands;
    friend class battle_turn_flow;

    [[nodiscard]] battle_transition
    complete_non_target_action()
    {
        battle_unit_instance* selected =
                _find_unit(_draft.unit_id);
        if(_lifecycle !=
                        battle_lifecycle::action_drafting ||
                ! _draft.active || ! selected ||
                ! selected->ledger.acted)
        {
            return battle_transition::invalid;
        }
        selected->position = _draft.preview_position;
        selected->ledger.moved = _draft.move_previewed;
        return _finish_selected_action(
                *selected,
                prepared_defense_action{},
                false);
    }

    [[nodiscard]] battle_transition
    complete_action_before_boundary(
            prepared_defense_action defense)
    {
        battle_unit_instance* selected =
                _find_unit(_draft.unit_id);
        if(_lifecycle !=
                        battle_lifecycle::defense_select ||
                ! _draft.active || ! selected)
        {
            return battle_transition::invalid;
        }
        return _finish_selected_action(
                *selected, defense, false);
    }

    [[nodiscard]] battle_transition
    complete_action_before_boundary(
            ability_id defense_ability)
    {
        return complete_action_before_boundary({
            defense_ability == no_ability ?
                    defense_action_kind::none :
                    defense_action_kind::active_action,
            defense_ability,
            no_tool_slot,
        });
    }

    [[nodiscard]] battle_transition
    advance_empty_side_before_boundary()
    {
        if(_lifecycle != battle_lifecycle::unit_select ||
                _has_available(_current_side))
        {
            return battle_transition::invalid;
        }
        _tick_all_statuses();
        return _current_side == battle_side::player ?
                battle_transition::side_changed :
                battle_transition::round_advanced;
    }

    [[nodiscard]] battle_transition _finish_selected_action(
            battle_unit_instance& selected,
            prepared_defense_action defense,
            bool finalize_boundary)
    {
        selected.ledger.completed = true;
        selected.ledger.defense_ability = defense.action_id;
        selected.ledger.defense_kind = defense.kind;
        selected.ledger.defense_tool_slot = defense.tool_slot;
        _draft = {};
        _lifecycle = battle_lifecycle::unit_select;
        _full_round_boundary = false;

        if(_has_available(_current_side))
        {
            return battle_transition::unit_completed;
        }
        _tick_all_statuses();
        if(_current_side == battle_side::player &&
                _has_living_participant(
                        battle_side::enemy))
        {
            if(finalize_boundary)
            {
                _finalize_action_boundary(
                        battle_transition::side_changed);
            }
            return battle_transition::side_changed;
        }

        if(finalize_boundary)
        {
            _finalize_action_boundary(
                    battle_transition::round_advanced);
        }
        return battle_transition::round_advanced;
    }

    void _finalize_action_boundary(
            battle_transition transition)
    {
        if(transition == battle_transition::side_changed)
        {
            _current_side = battle_side::enemy;
            _apply_side_start_passives(_current_side);
        }
        else if(transition ==
                battle_transition::round_advanced)
        {
            ++_round_index;
            _current_side = battle_side::player;
            _reset_ledgers();
            _apply_side_start_passives(_current_side);
            _full_round_boundary = true;
        }
    }

    [[nodiscard]] battle_transition commit_resolved_effects()
    {
        battle_unit_instance* selected = _find_unit(_draft.unit_id);
        if(_lifecycle != battle_lifecycle::action_drafting ||
                ! _draft.active || ! selected)
        {
            return battle_transition::invalid;
        }

        selected->position = _draft.preview_position;
        selected->ledger.moved = _draft.move_previewed;
        _lifecycle = battle_lifecycle::effects_resolved;
        _full_round_boundary = false;
        return battle_transition::effects_committed;
    }

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
            if(unit.side == side && _is_command_eligible(unit))
            {
                return true;
            }
        }
        return false;
    }

    [[nodiscard]] bool _has_living_participant(
            battle_side side) const
    {
        for(std::size_t index = 0;
                index < _unit_count;
                ++index)
        {
            const battle_unit_instance& unit =
                    _units[index];
            if(unit.side == side && unit.active &&
                    unit.hp > 0)
            {
                return true;
            }
        }
        return false;
    }

    [[nodiscard]] bool _can_issue_commands(
            const battle_unit_instance& unit) const
    {
        return unit.side == _current_side && _is_command_eligible(unit);
    }

    [[nodiscard]] static bool _is_command_eligible(
            const battle_unit_instance& unit)
    {
        return unit.active && unit.hp > 0 &&
                unit.control != battle_control::scripted &&
                ! battle_commands_blocked(unit.statuses) &&
                ! unit.ledger.completed;
    }

    [[nodiscard]] static constexpr std::size_t _side_index(
            battle_side side)
    {
        return side == battle_side::player ? 0 : 1;
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
                const bool identity_override_active =
                        _units[index].statuses.find(0x05) != no_status_slot;
                (void) _units[index].statuses.tick_side_end();
                if(identity_override_active &&
                        _units[index].statuses.find(0x05) == no_status_slot)
                {
                    battle_identity_system::restore_after_natural_expiry(_units[index]);
                }
                battle_attribute_system::recompute(_units[index]);
            }
        }
        _object_tick_event_count =
                _objects.tick_side_end(_object_tick_events);
        ++_object_tick_sequence;
    }

    void _apply_side_start_passives(battle_side side)
    {
        _side_start_event_count = 0;
        ++_side_start_sequence;
        for(std::size_t index = 0;
                index < _unit_count; ++index)
        {
            battle_unit_instance& unit = _units[index];
            if(! unit.active || unit.side != side)
            {
                continue;
            }
            const battle_side_start_passive_event event =
                    battle_side_start_passive_system::
                            apply(unit, _battle_id);
            if(event.valid &&
                    _side_start_event_count <
                            _side_start_events.size())
            {
                _side_start_events[
                        _side_start_event_count] = event;
                ++_side_start_event_count;
            }
        }
    }

    std::array<battle_unit_instance, MaxUnits> _units = {};
    std::uint8_t _battle_id = 0;
    std::size_t _unit_count = 0;
    int _round_index = 0;
    battle_side _current_side = battle_side::player;
    battle_lifecycle _lifecycle = battle_lifecycle::preparation;
    bool _full_round_boundary = false;
    action_draft _draft;
    battlefield_topology _battlefield;
    battlefield_object_table _objects;
    std::array<int, 2> _resolved_object_counts = {};
    std::array<
            battlefield_object_tick_event,
            battlefield_object_table::usable_capacity>
            _object_tick_events = {};
    std::size_t _object_tick_event_count = 0;
    std::uint32_t _object_tick_sequence = 0;
    std::array<
            battle_side_start_passive_event,
            MaxUnits> _side_start_events = {};
    std::size_t _side_start_event_count = 0;
    std::uint32_t _side_start_sequence = 0;
};

}

#endif
