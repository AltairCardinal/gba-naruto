#ifndef KONOHA_BATTLE_ACTION_SYSTEM_H
#define KONOHA_BATTLE_ACTION_SYSTEM_H

#include "konoha/battle_abilities.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class action_cost_kind : std::uint8_t
{
    none = 0,
    current_chakra = 1,
    current_hp = 2,
    no_scalar_resource_special = 3,
    battle_local_ninja_tool_slot = 5,
};

struct cost_policy
{
    action_cost_kind kind = action_cost_kind::none;
    std::uint16_t scalar = 0;
    std::uint8_t tool_slot = no_tool_slot;
};

struct presentation_binding
{
    std::uint8_t animation_family = 0;
};

struct effect_descriptor
{
    std::uint8_t code = 0;
    std::uint8_t flags = 0;
    std::uint8_t potency = 0;
    std::uint8_t base_hit_count = 0;
    std::uint8_t success_rate_percent = 0;
    std::uint8_t duration_turns = 0;
};

enum class target_policy_kind : std::uint8_t
{
    self_or_implicit_actor = 0,
    friendly_unit_policy_1 = 1,
    opponent_unit = 2,
    occupied_unit = 3,
    empty_tile = 4,
    friendly_unit_policy_5 = 5,
};

struct target_policy
{
    target_policy_kind kind = target_policy_kind::self_or_implicit_actor;
    std::uint8_t flags = 0;
};

struct range_shape
{
    std::uint8_t distance_and_line_flags = 0;
    std::uint8_t area_range_and_shape_flags = 0;

    [[nodiscard]] constexpr int maximum_distance() const
    {
        return distance_and_line_flags & 0x7F;
    }
};

struct upgrade_rule
{
    std::uint8_t target_type = 7;
    std::uint16_t per_level_growth = 0;
};

struct action_definition
{
    ability_id id = no_ability;
    cost_policy cost;
    presentation_binding presentation;
    effect_descriptor effect;
    target_policy target;
    range_shape range;
    upgrade_rule upgrade;
};

enum class effect_handler_kind : std::uint8_t
{
    unimplemented,
    damage,
    summon,
    move,
    identity_transform,
    heal,
    status,
};

class effect_resolver_registry
{
public:
    [[nodiscard]] static constexpr effect_handler_kind handler_for(std::uint8_t code)
    {
        switch(code)
        {
        case 0x01:
        case 0x14:
        case 0x15:
            return effect_handler_kind::damage;
        case 0x02:
            return effect_handler_kind::summon;
        case 0x03:
            return effect_handler_kind::move;
        case 0x05:
            return effect_handler_kind::identity_transform;
        case 0x06:
        case 0x1A:
            return effect_handler_kind::heal;
        case 0x12:
        case 0x13:
        case 0x1E:
        case 0x1F:
        case 0x20:
        case 0x21:
        case 0x22:
        case 0x23:
        case 0x24:
        case 0x25:
        case 0x26:
            return effect_handler_kind::status;
        default:
            return effect_handler_kind::unimplemented;
        }
    }

    [[nodiscard]] static constexpr std::uint32_t rom_handler_address(std::uint8_t code)
    {
        return code < _rom_handlers.size() ? _rom_handlers[code] : 0;
    }

private:
    static constexpr std::array<std::uint32_t, 64> _rom_handlers = {
        0,
        0x08077040U, 0x0807706CU, 0x080770D0U, 0x08077556U,
        0x0807711AU, 0x0807718CU, 0x080771B0U, 0x0807764EU,
        0x08077556U, 0x08077556U, 0x08077214U, 0x0807726EU,
        0x08077282U, 0x0807729AU, 0x080773B4U, 0x08077556U,
        0x080773F2U, 0x08077564U, 0x08077532U, 0x08077458U,
        0x080774B4U, 0x08077556U, 0x08077508U, 0x08077514U,
        0x08077556U, 0x0807718CU, 0x0807764EU, 0x0807742EU,
        0x08077444U, 0x08077564U, 0x08077564U, 0x08077564U,
        0x08077564U, 0x08077564U, 0x08077564U, 0x08077564U,
        0x08077564U, 0x08077590U, 0x0807764EU, 0x0807764EU,
        0x0807764EU, 0x0807764EU, 0x0807764EU, 0x0807764EU,
        0x0807764EU, 0x0807764EU, 0x0807764EU, 0x0807764EU,
        0x0807764EU, 0x0807764EU, 0x0807764EU, 0x0807764EU,
        0x0807764EU, 0x0807764EU, 0x0807764EU, 0x0807764EU,
        0x0807764EU, 0x0807764EU, 0x0807764EU, 0x0807764EU,
        0x0807764EU, 0x0807764EU, 0x0807755CU,
    };
};

enum class action_error : std::uint8_t
{
    none,
    invalid_definition,
    invalid_source,
    action_already_used,
    insufficient_chakra,
    insufficient_hp,
    missing_ninja_tool,
    invalid_target,
    occupied_target_tile,
    target_out_of_range,
    summon_slot_unavailable,
    status_capacity_exhausted,
    unsupported_effect,
};

struct action_preview
{
    action_error error = action_error::none;
    action_cost_kind cost_kind = action_cost_kind::none;
    int scalar_cost = 0;
    int hit_count = 0;
    int damage_per_hit = 0;
    int total_damage = 0;
    int healing = 0;

    [[nodiscard]] constexpr bool legal() const
    {
        return error == action_error::none;
    }
};

struct action_result
{
    action_error error = action_error::none;
    int generated_hits = 0;
    int effective_hits = 0;
    int total_damage = 0;
    int total_healing = 0;
    int applied_status_count = 0;
    bool defeated = false;
    bool summoned = false;
    std::uint8_t reaction_code = 0;
    ability_id reaction_action_id = no_ability;
    int reaction_hit_index = -1;

    [[nodiscard]] constexpr bool success() const
    {
        return error == action_error::none;
    }
};

class battle_action_resolver
{
public:
    [[nodiscard]] static action_preview preview_units(
            const battle_unit_instance& source,
            const battle_unit_instance* target,
            const battle_unit_instance* summon,
            bool target_tile_occupied,
            const action_definition& action,
            grid_point target_position)
    {
        return _preview(
                source, target, summon, target_tile_occupied, action, target_position);
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_preview preview(
            const battle_session<MaxUnits>& session,
            battle_unit_id target_id,
            battle_unit_id summon_id,
            const action_definition& action,
            grid_point target_position)
    {
        if(session._lifecycle != battle_lifecycle::action_drafting || ! session._draft.active)
        {
            return { action_error::invalid_source };
        }
        battle_unit_instance source = *session._find_unit(session._draft.unit_id);
        source.position = session._draft.preview_position;
        const battle_unit_instance* target = target_id == no_battle_unit ?
                nullptr : session._find_unit(target_id);
        if(action.target.kind == target_policy_kind::self_or_implicit_actor && ! target)
        {
            target = &source;
        }
        const battle_unit_instance* summon = summon_id == no_battle_unit ?
                nullptr : session._find_unit(summon_id);
        return _preview(source, target, summon, session.occupied(target_position), action,
                target_position);
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_result resolve_draft(
            battle_session<MaxUnits>& session,
            battle_unit_id target_id,
            battle_unit_id summon_id,
            const action_definition& action,
            grid_point target_position,
            deterministic_rng& rng)
    {
        const battle_unit_instance* source = session._draft.active ?
                session._find_unit(session._draft.unit_id) : nullptr;
        const battle_facing facing = source ? source->facing : battle_facing::down;
        return resolve_draft(
                session, target_id, summon_id, action, target_position, facing, rng);
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_result resolve_draft(
            battle_session<MaxUnits>& session,
            battle_unit_id target_id,
            battle_unit_id summon_id,
            const action_definition& action,
            grid_point target_position,
            battle_facing facing,
            deterministic_rng& rng)
    {
        const action_preview checked = preview(
                session, target_id, summon_id, action, target_position);
        if(! checked.legal())
        {
            return { checked.error };
        }

        battle_session<MaxUnits> next = session;
        battle_unit_instance* source = next._find_unit(next._draft.unit_id);
        source->position = next._draft.preview_position;
        battle_unit_instance* target = target_id == no_battle_unit ?
                nullptr : next._find_unit(target_id);
        if(action.target.kind == target_policy_kind::self_or_implicit_actor && ! target)
        {
            target = source;
        }
        battle_unit_instance* summon = summon_id == no_battle_unit ?
                nullptr : next._find_unit(summon_id);

        _commit_cost(*source, action.cost);
        action_result result = _resolve_effect(
                *source, target, summon, action, target_position, rng);
        if(! result.success())
        {
            return result;
        }
        source->ledger.acted = true;
        if(next.commit_action(facing, no_ability) == battle_transition::invalid)
        {
            return { action_error::invalid_source };
        }
        session = next;
        return result;
    }

private:
    [[nodiscard]] static action_preview _preview(
            const battle_unit_instance& source,
            const battle_unit_instance* target,
            const battle_unit_instance* summon,
            bool target_tile_occupied,
            const action_definition& action,
            grid_point target_position)
    {
        action_preview result;
        result.cost_kind = action.cost.kind;
        result.scalar_cost = action.cost.scalar;
        if(action.id == no_ability || action.effect.code == 0 ||
                action.effect.base_hit_count == 0 || action.effect.success_rate_percent > 100 ||
                effect_resolver_registry::rom_handler_address(action.effect.code) == 0)
        {
            result.error = action_error::invalid_definition;
            return result;
        }
        const effect_handler_kind handler = effect_resolver_registry::handler_for(action.effect.code);
        if(handler == effect_handler_kind::unimplemented)
        {
            result.error = action_error::unsupported_effect;
            return result;
        }
        if(! source.active)
        {
            result.error = action_error::invalid_source;
            return result;
        }
        if(source.ledger.acted)
        {
            result.error = action_error::action_already_used;
            return result;
        }
        result.error = _validate_cost(source, action.cost);
        if(result.error != action_error::none)
        {
            return result;
        }
        result.error = _validate_target(
                source, target, target_tile_occupied, action.target, target_position);
        if(result.error != action_error::none)
        {
            return result;
        }
        if(handler == effect_handler_kind::summon && (! summon || summon->active))
        {
            result.error = action_error::summon_slot_unavailable;
            return result;
        }

        const int distance = _distance(source.position, target_position);
        if(distance > action.range.maximum_distance())
        {
            result.error = action_error::target_out_of_range;
            return result;
        }
        result.hit_count = action.effect.base_hit_count;
        if(handler == effect_handler_kind::damage)
        {
            result.damage_per_hit = _damage_per_hit(source, *target, action.effect.potency);
            result.total_damage = result.damage_per_hit * result.hit_count;
        }
        else if(handler == effect_handler_kind::heal)
        {
            result.healing = action.effect.potency;
        }
        return result;
    }

    [[nodiscard]] static action_error _validate_cost(
            const battle_unit_instance& source, cost_policy cost)
    {
        switch(cost.kind)
        {
        case action_cost_kind::none:
        case action_cost_kind::no_scalar_resource_special:
            return action_error::none;
        case action_cost_kind::current_chakra:
            return cost.scalar > source.chakra ?
                    action_error::insufficient_chakra : action_error::none;
        case action_cost_kind::current_hp:
            return cost.scalar > source.hp ? action_error::insufficient_hp : action_error::none;
        case action_cost_kind::battle_local_ninja_tool_slot:
            if(cost.tool_slot >= source.equipped_tools.size() ||
                    source.equipped_tools[cost.tool_slot] == no_ninja_tool)
            {
                return action_error::missing_ninja_tool;
            }
            return action_error::none;
        default:
            return action_error::invalid_definition;
        }
    }

    [[nodiscard]] static action_error _validate_target(
            const battle_unit_instance& source,
            const battle_unit_instance* target,
            bool target_tile_occupied,
            target_policy policy,
            grid_point target_position)
    {
        if(policy.kind == target_policy_kind::empty_tile)
        {
            return target || target_tile_occupied ?
                    action_error::occupied_target_tile : action_error::none;
        }
        if(! target || ! target->active || target->position != target_position)
        {
            return action_error::invalid_target;
        }
        switch(policy.kind)
        {
        case target_policy_kind::self_or_implicit_actor:
            return target->id == source.id ? action_error::none : action_error::invalid_target;
        case target_policy_kind::friendly_unit_policy_1:
        case target_policy_kind::friendly_unit_policy_5:
            return target->side == source.side ? action_error::none : action_error::invalid_target;
        case target_policy_kind::opponent_unit:
            return target->side != source.side ? action_error::none : action_error::invalid_target;
        case target_policy_kind::occupied_unit:
            return action_error::none;
        case target_policy_kind::empty_tile:
            break;
        }
        return action_error::invalid_definition;
    }

    static void _commit_cost(battle_unit_instance& source, cost_policy cost)
    {
        switch(cost.kind)
        {
        case action_cost_kind::current_chakra:
            source.chakra -= cost.scalar;
            break;
        case action_cost_kind::current_hp:
            source.hp -= cost.scalar;
            break;
        case action_cost_kind::battle_local_ninja_tool_slot:
            source.equipped_tools[cost.tool_slot] = no_ninja_tool;
            break;
        default:
            break;
        }
    }

    [[nodiscard]] static action_result _resolve_effect(
            battle_unit_instance& source,
            battle_unit_instance* target,
            battle_unit_instance* summon,
            const action_definition& action,
            grid_point target_position,
            deterministic_rng& rng)
    {
        action_result result;
        const effect_handler_kind handler = effect_resolver_registry::handler_for(action.effect.code);
        if(handler == effect_handler_kind::damage)
        {
            const int success_rate = _success_rate(source, *target, action.effect.success_rate_percent);
            const int damage = _damage_per_hit(source, *target, action.effect.potency);
            result.generated_hits = action.effect.base_hit_count;
            for(int index = 0; index < result.generated_hits && target->active; ++index)
            {
                if(rng.next_percent() >= success_rate)
                {
                    continue;
                }
                ++result.effective_hits;
                const std::uint8_t sharingan_slot = target->statuses.find(0x10);
                if(sharingan_slot != no_status_slot)
                {
                    const status_record* reaction = target->statuses.active(sharingan_slot);
                    result.reaction_code = 0x10;
                    result.reaction_action_id = reaction->raw_parameter_1;
                    result.reaction_hit_index = index;
                    (void) target->statuses.remove(
                            0x10, status_remove_mode::consume_without_event);
                    break;
                }
                if(target->substitution_ready)
                {
                    target->substitution_ready = false;
                    continue;
                }
                const int applied = damage > target->hp ? target->hp : damage;
                target->hp -= applied;
                result.total_damage += applied;
                if(target->hp == 0)
                {
                    target->active = false;
                    result.defeated = true;
                }
            }
        }
        else if(handler == effect_handler_kind::heal)
        {
            result.generated_hits = action.effect.base_hit_count;
            result.effective_hits = result.generated_hits;
            const int missing = target->max_hp - target->hp;
            result.total_healing = action.effect.potency > missing ? missing : action.effect.potency;
            target->hp += result.total_healing;
        }
        else if(handler == effect_handler_kind::summon)
        {
            summon->active = true;
            summon->side = source.side;
            summon->control = source.control;
            summon->position = target_position;
            summon->summoner = source.id;
            result.summoned = true;
        }
        else if(handler == effect_handler_kind::status)
        {
            battle_unit_instance changed = *target;
            const int previous_max_hp = changed.max_hp;
            const int previous_hp = changed.hp;
            const std::uint8_t code_with_flags =
                    (action.effect.code & 0x3F) | action.effect.flags;
            if(action.effect.code == 0x26)
            {
                constexpr std::array<std::uint8_t, 4> compound_codes = {
                    0x1E, 0x20, 0x22, 0x1B,
                };
                for(std::uint8_t status_code : compound_codes)
                {
                    if(! changed.statuses.upsert({
                               status_code,
                               0,
                               action.effect.duration_turns,
                               0,
                               0,
                               0,
                               action.effect.potency,
                           }))
                    {
                        result.error = action_error::status_capacity_exhausted;
                        return result;
                    }
                    ++result.applied_status_count;
                }
            }
            else
            {
                if(! changed.statuses.upsert({
                           code_with_flags,
                           0,
                           action.effect.duration_turns,
                           0,
                           0,
                           0,
                           action.effect.potency,
                       }))
                {
                    result.error = action_error::status_capacity_exhausted;
                    return result;
                }
                result.applied_status_count = 1;
            }
            battle_attribute_system::recompute(changed);
            if(action.effect.code == 0x26 && changed.max_hp > previous_max_hp)
            {
                const int increased_hp = previous_hp + changed.max_hp - previous_max_hp;
                changed.hp = increased_hp > changed.max_hp ? changed.max_hp : increased_hp;
            }
            *target = changed;
        }
        else
        {
            result.error = action_error::unsupported_effect;
        }
        return result;
    }

    [[nodiscard]] static int _success_rate(
            const battle_unit_instance& source,
            const battle_unit_instance& target,
            int base_rate)
    {
        int result = base_rate + (source.agility - target.agility) / 2;
        if(result > 99)
        {
            result = 99;
        }
        if(result < 0)
        {
            result = 0;
        }
        return result;
    }

    [[nodiscard]] static int _damage_per_hit(
            const battle_unit_instance& source,
            const battle_unit_instance& target,
            int potency)
    {
        const battle_attribute_view source_attributes = battle_attribute_system::view(source);
        const battle_attribute_view target_attributes = battle_attribute_system::view(target);
        const int scaled_attack = source_attributes.attack;
        const int raw = potency * scaled_attack / 10;
        int defense_factor = 100 - 5 * _integer_sqrt(target_attributes.defense);
        if(defense_factor < 0)
        {
            defense_factor = 0;
        }
        return raw * defense_factor / 100;
    }

    [[nodiscard]] static int _integer_sqrt(int value)
    {
        int root = 0;
        while((root + 1) * (root + 1) <= value)
        {
            ++root;
        }
        return root;
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
