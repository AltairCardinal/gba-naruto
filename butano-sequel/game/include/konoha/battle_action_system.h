#ifndef KONOHA_BATTLE_ACTION_SYSTEM_H
#define KONOHA_BATTLE_ACTION_SYSTEM_H

#include "konoha/battle_action_identity.h"
#include "konoha/battle_action_eligibility.h"
#include "konoha/battle_random.h"
#include "konoha/battle_status_policies.h"
#include "konoha/generated_battle_passive_content.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr std::array<std::uint8_t, 6>
        incoming_reaction_priority = {{
            0x04, 0x0A, 0x09, 0x10, 0x16, 0x19,
        }};

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
        return distance_and_line_flags & 0x1F;
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
    battle_action_source_kind source_kind =
            battle_action_source_kind::active_action;
};

template<std::size_t Capacity>
struct battle_target_set
{
    std::array<battle_unit_id, Capacity> ids = {};
    std::size_t count = 0;

    [[nodiscard]] constexpr bool contains(battle_unit_id id) const
    {
        for(std::size_t index = 0; index < count; ++index)
        {
            if(ids[index] == id)
            {
                return true;
            }
        }
        return false;
    }
};

class battle_action_targeting
{
public:
    template<std::size_t UnitCount>
    [[nodiscard]] static battle_target_set<UnitCount> collect(
            const battle_unit_instance& source,
            const std::array<battle_unit_instance, UnitCount>& units,
            target_policy policy,
            range_shape range,
            grid_point center)
    {
        battle_target_set<UnitCount> result;
        for(const battle_unit_instance& candidate : units)
        {
            if(candidate.active &&
                    _matches_policy(source, candidate, policy) &&
                    _contains(range.area_range_and_shape_flags,
                            center, candidate.position))
            {
                result.ids[result.count] = candidate.id;
                ++result.count;
            }
        }
        return result;
    }

private:
    [[nodiscard]] static constexpr bool _matches_policy(
            const battle_unit_instance& source,
            const battle_unit_instance& candidate,
            target_policy policy)
    {
        switch(policy.kind)
        {
        case target_policy_kind::self_or_implicit_actor:
            return candidate.id == source.id;
        case target_policy_kind::friendly_unit_policy_1:
        case target_policy_kind::friendly_unit_policy_5:
            return candidate.side == source.side;
        case target_policy_kind::opponent_unit:
            return candidate.side != source.side;
        case target_policy_kind::occupied_unit:
            return true;
        case target_policy_kind::empty_tile:
            return false;
        default:
            break;
        }
        return false;
    }

    [[nodiscard]] static constexpr bool _contains(
            std::uint8_t encoded_shape,
            grid_point center,
            grid_point position)
    {
        int dx = position.x - center.x;
        int dy = position.y - center.y;
        dx = dx < 0 ? -dx : dx;
        dy = dy < 0 ? -dy : dy;

        const int encoded_size = encoded_shape & 0x7F;
        const int radius = encoded_size > 0 ? encoded_size - 1 : 0;
        if((encoded_shape & 0x80) != 0)
        {
            return (dx == 0 || dy == 0) && dx + dy <= radius;
        }
        return dx + dy <= radius;
    }
};

enum class effect_handler_kind : std::uint8_t
{
    unimplemented,
    no_effect,
    damage,
    summon,
    summon_variant,
    summon_pair,
    move,
    identity_transform,
    heal_percent,
    status,
    linked_cleanup,
    restore_hp_and_chakra,
    battlefield_object_type_1,
    battlefield_object_type_2,
    chakra_restore,
    chakra_reduce,
    reaction_state,
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
        case 0x08:
            return effect_handler_kind::no_effect;
        case 0x05:
            return effect_handler_kind::identity_transform;
        case 0x06:
        case 0x1A:
            return effect_handler_kind::heal_percent;
        case 0x07:
            return effect_handler_kind::summon_variant;
        case 0x0B:
            return effect_handler_kind::linked_cleanup;
        case 0x0C:
            return effect_handler_kind::battlefield_object_type_2;
        case 0x11:
            return effect_handler_kind::restore_hp_and_chakra;
        case 0x17:
            return effect_handler_kind::summon_pair;
        case 0x18:
            return effect_handler_kind::battlefield_object_type_1;
        case 0x1C:
            return effect_handler_kind::chakra_restore;
        case 0x1D:
            return effect_handler_kind::chakra_reduce;
        case 0x3F:
            return effect_handler_kind::reaction_state;
        case 0x04:
        case 0x0A:
        case 0x0D:
        case 0x0E:
        case 0x0F:
        case 0x10:
        case 0x12:
        case 0x13:
        case 0x16:
        case 0x19:
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
    missing_required_status,
    action_requirement_not_met,
    status_capacity_exhausted,
    battlefield_object_capacity_exhausted,
    unsupported_effect,
    mission_restricted,
};

class battle_action_cost_policy
{
public:
    [[nodiscard]] static action_error validate(
            const battle_unit_instance& source,
            cost_policy cost,
            ability_id expected_tool = no_ability)
    {
        switch(cost.kind)
        {
        case action_cost_kind::none:
        case action_cost_kind::no_scalar_resource_special:
            return action_error::none;
        case action_cost_kind::current_chakra:
            return cost.scalar > source.chakra ?
                    action_error::insufficient_chakra :
                    action_error::none;
        case action_cost_kind::current_hp:
            return cost.scalar > source.hp ?
                    action_error::insufficient_hp :
                    action_error::none;
        case action_cost_kind::battle_local_ninja_tool_slot:
            if(cost.tool_slot >= source.equipped_tools.size() ||
                    source.equipped_tools[cost.tool_slot] ==
                            no_ninja_tool ||
                    (expected_tool != no_ability &&
                     source.equipped_tools[cost.tool_slot] !=
                             expected_tool))
            {
                return action_error::missing_ninja_tool;
            }
            return action_error::none;
        default:
            return action_error::invalid_definition;
        }
    }

    static void commit(
            battle_unit_instance& source, cost_policy cost)
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
};

struct action_preview
{
    action_error error = action_error::none;
    action_cost_kind cost_kind = action_cost_kind::none;
    int scalar_cost = 0;
    int hit_count = 0;
    int success_rate_percent = 0;
    int damage_per_hit = 0;
    int total_damage = 0;
    int healing = 0;
    int total_healing = 0;
    int target_count = 0;
    std::uint8_t requirement_reason_code = 0;

    [[nodiscard]] constexpr bool legal() const
    {
        return error == action_error::none;
    }
};

struct damage_resolution_step
{
    battle_unit_id target_id = no_battle_unit;
    int damage = 0;
    int hit_index = -1;
    bool linked = false;
    bool defeated = false;
    std::uint8_t hit_flags = 0;

    constexpr bool operator==(const damage_resolution_step&) const = default;
};

struct reaction_resolution_event
{
    bool triggered = false;
    std::uint8_t code = 0;
    defense_action_kind action_kind = defense_action_kind::none;
    ability_id action_id = no_ability;
    std::uint8_t tool_slot = no_tool_slot;
    battle_unit_id source_id = no_battle_unit;
    battle_unit_id target_id = no_battle_unit;
    int incoming_hit_index = -1;
    int damage = 0;
    bool defeated = false;
    bool moved = false;
    grid_point movement_origin = {};
    grid_point movement_destination = {};

    constexpr bool operator==(const reaction_resolution_event&) const =
            default;
};

struct action_result
{
    action_error error = action_error::none;
    int generated_hits = 0;
    int effective_hits = 0;
    int total_damage = 0;
    int total_healing = 0;
    int chakra_delta = 0;
    int applied_status_count = 0;
    int target_count = 0;
    bool source_status_0x0d_consumed = false;
    bool target_status_0x0d_consumed = false;
    bool defeated = false;
    bool summoned = false;
    int summon_count = 0;
    std::uint8_t battlefield_object_slot = no_battlefield_object;
    bool reaction_state_changed = false;
    bool moved = false;
    grid_point movement_origin = {};
    grid_point movement_destination = {};
    bool identity_overridden = false;
    std::uint8_t identity_before = 0;
    std::uint8_t identity_after = 0;
    battle_unit_id identity_linked_unit = no_battle_unit;
    int linked_resolution_count = 0;
    std::array<damage_resolution_step, 32> damage_steps = {};
    int damage_step_count = 0;
    bool damage_steps_truncated = false;
    std::uint8_t reaction_code = 0;
    ability_id reaction_action_id = no_ability;
    int reaction_hit_index = -1;
    reaction_resolution_event reaction_event = {};
    std::array<battle_unit_id, 12> affected_unit_ids = {};
    int affected_unit_count = 0;
    bool affected_units_truncated = false;

    [[nodiscard]] constexpr bool success() const
    {
        return error == action_error::none;
    }
};

class battle_action_resolver
{
public:
    static void merge_results(
            const action_result& source,
            action_result& destination)
    {
        _merge_result(source, destination);
        for(int index = 0;
                index < source.affected_unit_count; ++index)
        {
            _record_affected(
                    source.affected_unit_ids[
                            static_cast<std::size_t>(index)],
                    destination);
        }
        destination.affected_units_truncated |=
                source.affected_units_truncated;
        destination.target_count += source.target_count;
        if(destination.battlefield_object_slot ==
                        no_battlefield_object &&
                source.battlefield_object_slot !=
                        no_battlefield_object)
        {
            destination.battlefield_object_slot =
                    source.battlefield_object_slot;
        }
    }

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
        const battle_unit_instance* selected =
                session._find_unit(session._draft.unit_id);
        if(! selected)
        {
            return { action_error::invalid_source };
        }
        battle_unit_instance source = *selected;
        source.position = session._draft.preview_position;
        const battle_unit_instance* target = target_id == no_battle_unit ?
                nullptr : session._find_unit(target_id);
        if(target_id == source.id)
        {
            target = &source;
        }
        if(action.target.kind == target_policy_kind::self_or_implicit_actor && ! target)
        {
            target = &source;
        }
        const battle_unit_instance* summon = summon_id == no_battle_unit ?
                nullptr : session._find_unit(summon_id);
        action_preview result = _preview(
                source,
                target,
                summon,
                _occupied_after_preview_move(
                        session,
                        target_position),
                action,
                target_position);
        if(result.legal() &&
                effect_resolver_registry::handler_for(action.effect.code) ==
                        effect_handler_kind::summon_pair)
        {
            std::size_t inactive_count = 0;
            for(std::size_t index = 0; index < session._unit_count; ++index)
            {
                inactive_count += ! session._units[index].active;
            }
            if(inactive_count < 2)
            {
                result.error = action_error::summon_slot_unavailable;
            }
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_preview preview_area(
            const battle_session<MaxUnits>& session,
            const action_definition& action,
            grid_point center)
    {
        if(session._lifecycle != battle_lifecycle::action_drafting ||
                ! session._draft.active)
        {
            return { action_error::invalid_source };
        }

        std::array<battle_unit_instance, MaxUnits> units = session._units;
        battle_unit_instance* source = _find_unit_in_array(
                units, session._draft.unit_id);
        if(! source)
        {
            return { action_error::invalid_source };
        }
        source->position = session._draft.preview_position;
        if(_distance(source->position, center) > action.range.maximum_distance())
        {
            return { action_error::target_out_of_range };
        }
        const effect_handler_kind handler =
                effect_resolver_registry::handler_for(action.effect.code);
        if(handler != effect_handler_kind::damage &&
                handler != effect_handler_kind::heal_percent &&
                handler != effect_handler_kind::status &&
                handler !=
                        effect_handler_kind::reaction_state)
        {
            return { action_error::invalid_definition };
        }

        const battle_target_set<MaxUnits> targets =
                battle_action_targeting::collect(
                        *source, units, action.target, action.range, center);
        if(targets.count == 0)
        {
            return { action_error::invalid_target };
        }

        action_preview aggregate;
        aggregate.error = action_error::none;
        aggregate.cost_kind = action.cost.kind;
        aggregate.scalar_cost = action.cost.scalar;
        action_definition per_target_action = action;
        per_target_action.range.distance_and_line_flags = 0x7F;
        for(std::size_t index = 0; index < targets.count; ++index)
        {
            const battle_unit_instance* target =
                    _find_unit_in_array(units, targets.ids[index]);
            if(! target)
            {
                return { action_error::invalid_target };
            }
            const action_preview item = _preview(
                    *source,
                    target,
                    nullptr,
                    true,
                    per_target_action,
                    target->position);
            if(! item.legal())
            {
                return item;
            }
            if(index == 0)
            {
                aggregate.hit_count = item.hit_count;
                aggregate.damage_per_hit = item.damage_per_hit;
            }
            if(item.success_rate_percent > aggregate.success_rate_percent)
            {
                aggregate.success_rate_percent = item.success_rate_percent;
            }
            aggregate.total_damage += item.total_damage;
            if(handler == effect_handler_kind::heal_percent)
            {
                const int missing = target->max_hp - target->hp;
                aggregate.total_healing += item.healing > missing ?
                        missing : item.healing;
            }
            ++aggregate.target_count;
        }
        aggregate.healing = action.effect.potency;
        return aggregate;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_result resolve_area_draft(
            battle_session<MaxUnits>& session,
            const action_definition& action,
            grid_point center,
            deterministic_rng& rng)
    {
        battle_session<MaxUnits> next = session;
        deterministic_rng next_rng = rng;
        const action_result result =
                resolve_area_draft_in_place(
                        next, action, center, next_rng);
        if(result.success())
        {
            session = next;
            rng = next_rng;
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_result
    resolve_area_draft_in_place(
            battle_session<MaxUnits>& session,
            const action_definition& action,
            grid_point center,
            deterministic_rng& rng)
    {
        const action_preview checked = preview_area(session, action, center);
        if(! checked.legal())
        {
            return { checked.error };
        }

        battle_unit_instance* source =
                session._find_unit(session._draft.unit_id);
        if(! source)
        {
            return { action_error::invalid_source };
        }
        source->position = session._draft.preview_position;
        const battle_target_set<MaxUnits> targets =
                battle_action_targeting::collect(
                        *source,
                        session._units,
                        action.target,
                        action.range,
                        center);

        const int continuation_bonus_hits =
                _roll_continuation_hit(*source, action, rng);
        battle_action_cost_policy::commit(*source, action.cost);
        action_result aggregate;
        for(std::size_t index = 0; index < targets.count; ++index)
        {
            battle_unit_instance* target =
                    session._find_unit(targets.ids[index]);
            const status_consumption_result consumed =
                    status_consumption_policy::apply(
                            *source, target, action.effect.code);
            action_result item = _resolve_effect(
                    session,
                    *source,
                    target,
                    nullptr,
                    action,
                    target->position,
                    rng,
                    continuation_bonus_hits,
                    false);
            if(! item.success())
            {
                return item;
            }
            _record_affected(target->id, aggregate);
            item.source_status_0x0d_consumed = consumed.source_consumed;
            item.target_status_0x0d_consumed = consumed.target_consumed;
            _merge_result(item, aggregate);
            ++aggregate.target_count;
        }
        if(action.effect.code == 0x14)
        {
            (void) source->statuses.remove(
                    0x13, status_remove_mode::preserve_removed_event);
        }
        source->ledger.acted = true;
        if(session.commit_resolved_effects() !=
                battle_transition::effects_committed)
        {
            return { action_error::invalid_source };
        }
        return aggregate;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_result
    resolve_battlefield_object_event(
            battle_session<MaxUnits>& session,
            const battlefield_object_tick_event& event,
            const action_definition& payload,
            deterministic_rng& rng)
    {
        battle_session<MaxUnits> next = session;
        deterministic_rng next_rng = rng;
        const action_result result =
                _resolve_battlefield_object_event_in_place(
                        next, event, payload, next_rng);
        if(result.success())
        {
            session = next;
            rng = next_rng;
        }
        return result;
    }

private:
    template<std::size_t MaxUnits>
    [[nodiscard]] static action_result
    _resolve_battlefield_object_event_in_place(
            battle_session<MaxUnits>& session,
            const battlefield_object_tick_event& event,
            const action_definition& payload,
            deterministic_rng& rng)
    {
        if(! event.valid() ||
                event.kind !=
                        battlefield_object_tick_kind::type_1_due ||
                event.object.type != 1 ||
                event.object.payload_id != payload.id ||
                payload.effect.code != 0x18 ||
                event.object.source_unit_id > 0xFF)
        {
            return { action_error::invalid_definition };
        }
        battle_unit_instance* source =
                session._find_unit(
                        static_cast<battle_unit_id>(
                                event.object.source_unit_id));
        if(! source)
        {
            return { action_error::invalid_source };
        }

        const int encoded_area =
                payload.range.area_range_and_shape_flags & 0x7F;
        const int radius =
                encoded_area > 0 ? encoded_area - 1 : 0;
        const grid_point center = {
            event.object.x,
            event.object.y,
        };
        std::array<battle_unit_id, MaxUnits> target_ids = {};
        std::size_t target_count = 0;
        for(const battle_unit_instance& candidate :
                session._units)
        {
            if(! candidate.active)
            {
                continue;
            }
            int dx = candidate.position.x - center.x;
            int dy = candidate.position.y - center.y;
            dx = dx < 0 ? -dx : dx;
            dy = dy < 0 ? -dy : dy;
            if(dx <= radius && dy <= radius)
            {
                target_ids[target_count] = candidate.id;
                ++target_count;
            }
        }

        action_definition explosion = payload;
        explosion.cost = {};
        explosion.effect.code = 1;
        explosion.target = {
            target_policy_kind::occupied_unit,
            0,
        };
        action_result aggregate;
        aggregate.battlefield_object_slot = event.slot;
        for(std::size_t index = 0;
                index < target_count; ++index)
        {
            battle_unit_instance* target =
                    session._find_unit(target_ids[index]);
            if(! target || ! target->active)
            {
                continue;
            }
            action_result item = _resolve_effect(
                    session,
                    *source,
                    target,
                    nullptr,
                    explosion,
                    target->position,
                    rng);
            if(! item.success())
            {
                return item;
            }
            _record_affected(target->id, aggregate);
            _merge_result(item, aggregate);
            ++aggregate.target_count;
        }
        return aggregate;
    }

public:
    template<std::size_t MaxUnits>
    [[nodiscard]] static action_result resolve_draft(
            battle_session<MaxUnits>& session,
            battle_unit_id target_id,
            battle_unit_id summon_id,
            const action_definition& action,
            grid_point target_position,
            deterministic_rng& rng)
    {
        battle_session<MaxUnits> next = session;
        deterministic_rng next_rng = rng;
        const action_result result = resolve_draft_in_place(
                next,
                target_id,
                summon_id,
                action,
                target_position,
                next_rng);
        if(result.success())
        {
            session = next;
            rng = next_rng;
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_result resolve_draft_in_place(
            battle_session<MaxUnits>& session,
            battle_unit_id target_id,
            battle_unit_id summon_id,
            const action_definition& action,
            grid_point target_position,
            deterministic_rng& rng)
    {
        const action_preview checked = preview(
                session, target_id, summon_id, action, target_position);
        if(! checked.legal())
        {
            return { checked.error };
        }

        battle_unit_instance* source =
                session._find_unit(session._draft.unit_id);
        if(! source)
        {
            return { action_error::invalid_source };
        }
        source->position = session._draft.preview_position;
        battle_unit_instance* target = target_id == no_battle_unit ?
                nullptr : session._find_unit(target_id);
        if(action.target.kind == target_policy_kind::self_or_implicit_actor && ! target)
        {
            target = source;
        }
        battle_unit_instance* summon = summon_id == no_battle_unit ?
                nullptr : session._find_unit(summon_id);

        const int continuation_bonus_hits =
                _roll_continuation_hit(*source, action, rng);
        battle_action_cost_policy::commit(*source, action.cost);
        const status_consumption_result consumed = status_consumption_policy::apply(
                *source, target, action.effect.code);
        action_result result = _resolve_effect(
                session,
                *source,
                target,
                summon,
                action,
                target_position,
                rng,
                continuation_bonus_hits);
        if(! result.success())
        {
            return result;
        }
        if(target)
        {
            _record_affected(target->id, result);
        }
        if(result.summoned && summon)
        {
            _record_affected(summon->id, result);
        }
        if(result.moved)
        {
            session._draft.preview_position = source->position;
            session._draft.move_previewed =
                    source->position != session._draft.origin;
        }
        result.source_status_0x0d_consumed = consumed.source_consumed;
        result.target_status_0x0d_consumed = consumed.target_consumed;
        source->ledger.acted = true;
        if(session.commit_resolved_effects() !=
                battle_transition::effects_committed)
        {
            return { action_error::invalid_source };
        }
        return result;
    }

private:
    template<std::size_t MaxUnits>
    [[nodiscard]] static bool _occupied_after_preview_move(
            const battle_session<MaxUnits>& session,
            grid_point position)
    {
        for(std::size_t index = 0;
                index < session._unit_count;
                ++index)
        {
            const battle_unit_instance& unit =
                    session._units[index];
            if(! unit.active)
            {
                continue;
            }
            const grid_point projected_position =
                    unit.id == session._draft.unit_id ?
                    session._draft.preview_position :
                    unit.position;
            if(projected_position == position)
            {
                return true;
            }
        }
        return false;
    }

    static void _record_affected(
            battle_unit_id unit_id,
            action_result& result)
    {
        if(unit_id == no_battle_unit)
        {
            return;
        }
        for(int index = 0;
                index < result.affected_unit_count;
                ++index)
        {
            if(result.affected_unit_ids[
                       static_cast<std::size_t>(index)] ==
                    unit_id)
            {
                return;
            }
        }
        if(result.affected_unit_count <
                static_cast<int>(
                        result.affected_unit_ids.size()))
        {
            result.affected_unit_ids[
                    static_cast<std::size_t>(
                            result.affected_unit_count)] =
                    unit_id;
            ++result.affected_unit_count;
        }
        else
        {
            result.affected_units_truncated = true;
        }
    }

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
                (action.effect.base_hit_count == 0 && action.effect.code != 0x14) ||
                action.effect.success_rate_percent > 100 ||
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
        const action_requirement requirement =
                battle_action_eligibility::query(
                        source,
                        action.id,
                        action.source_kind);
        if(! requirement.available())
        {
            result.error = action_error::action_requirement_not_met;
            result.requirement_reason_code = requirement.reason_code;
            return result;
        }
        result.error = battle_action_cost_policy::validate(
                source, action.cost, action.id);
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
        if((handler == effect_handler_kind::summon ||
                   handler == effect_handler_kind::summon_variant ||
                   handler == effect_handler_kind::summon_pair) &&
                (! summon || summon->active))
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
        result.hit_count = _hit_count(source, action);
        if(result.hit_count < 0)
        {
            result.error = action_error::missing_required_status;
            return result;
        }
        if(handler == effect_handler_kind::damage)
        {
            result.success_rate_percent = _success_rate(
                    source, *target, action.effect.success_rate_percent);
            result.damage_per_hit = _damage_per_hit(source, *target, action.effect.potency);
            result.total_damage = result.damage_per_hit * result.hit_count;
        }
        else if(handler == effect_handler_kind::heal_percent)
        {
            result.healing =
                    target->max_hp * action.effect.potency / 100;
        }
        else if((handler == effect_handler_kind::status ||
                    handler ==
                            effect_handler_kind::reaction_state) &&
                action.target.kind ==
                        target_policy_kind::opponent_unit)
        {
            result.success_rate_percent = _success_rate(
                    source,
                    *target,
                    action.effect.success_rate_percent);
        }
        return result;
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
        default:
            break;
        }
        return action_error::invalid_definition;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static action_result _resolve_effect(
            battle_session<MaxUnits>& session,
            battle_unit_instance& source,
            battle_unit_instance* target,
            battle_unit_instance* summon,
            const action_definition& action,
            grid_point target_position,
            deterministic_rng& rng,
            int continuation_bonus_hits = 0,
            bool finalize_source_status = true)
    {
        action_result result;
        const effect_handler_kind handler = effect_resolver_registry::handler_for(action.effect.code);
        if((handler == effect_handler_kind::status ||
                    handler ==
                            effect_handler_kind::reaction_state) &&
                action.target.kind ==
                        target_policy_kind::opponent_unit)
        {
            result.generated_hits = _hit_count(source, action);
            const int success_rate = _success_rate(
                    source,
                    *target,
                    action.effect.success_rate_percent);
            for(int index = 0;
                    index < result.generated_hits;
                    ++index)
            {
                if(_next_battle_percent(rng) < success_rate)
                {
                    ++result.effective_hits;
                }
            }
            if(result.effective_hits == 0)
            {
                return result;
            }
        }
        if(handler == effect_handler_kind::damage)
        {
            const int success_rate = _success_rate(source, *target, action.effect.success_rate_percent);
            const damage_candidates candidates =
                    _damage_candidates(source, *target, action.effect.potency);
            result.generated_hits =
                    _hit_count(source, action) +
                    continuation_bonus_hits;
            bool effect_flag_followups_applied = false;
            for(int index = 0; index < result.generated_hits && target->active; ++index)
            {
                if(_next_battle_percent(rng) >= success_rate)
                {
                    continue;
                }
                const std::uint8_t hit_flags =
                        _resolve_hit_flags(source, rng);
                const int damage =
                        _select_damage(candidates, hit_flags);
                ++result.effective_hits;
                const incoming_reaction_flow reaction_flow =
                        _resolve_incoming_reaction(
                                session,
                                source,
                                *target,
                                index,
                                rng,
                                result);
                if(! result.success())
                {
                    return result;
                }
                if(reaction_flow ==
                        incoming_reaction_flow::
                                cancel_remaining_hits)
                {
                    break;
                }
                _apply_damage_resolution(
                        session,
                        source,
                        *target,
                        damage,
                        action.effect.code,
                        false,
                        index,
                        false,
                        hit_flags,
                        result);
                if(! effect_flag_followups_applied &&
                        ! _apply_effect_flag_followups(
                                *target,
                                source.id,
                                action.effect.flags,
                                action.effect.potency,
                                result))
                {
                    result.error =
                            action_error::
                                    status_capacity_exhausted;
                    return result;
                }
                effect_flag_followups_applied = true;
            }
            if(action.effect.code == 0x14 && finalize_source_status)
            {
                (void) source.statuses.remove(
                        0x13, status_remove_mode::preserve_removed_event);
            }
            if(action.effect.code == 0x15 &&
                    result.effective_hits > 0 && target->active)
            {
                if(! _upsert_status(
                           *target,
                           action,
                           static_cast<std::uint8_t>(
                                   action.effect.code |
                                   action.effect.flags)))
                {
                    result.error = action_error::status_capacity_exhausted;
                    return result;
                }
                result.applied_status_count = 1;
                const std::uint8_t before = target->reaction_state;
                _set_reaction_state(*target, 0x40);
                result.reaction_state_changed =
                        target->reaction_state != before;
            }
        }
        else if(handler == effect_handler_kind::heal_percent)
        {
            result.generated_hits = action.effect.base_hit_count;
            result.effective_hits = result.generated_hits;
            const int missing = target->max_hp - target->hp;
            const int requested =
                    target->max_hp * action.effect.potency / 100;
            result.total_healing =
                    requested > missing ? missing : requested;
            target->hp += result.total_healing;
        }
        else if(handler == effect_handler_kind::summon ||
                handler == effect_handler_kind::summon_variant)
        {
            if(handler == effect_handler_kind::summon_variant)
            {
                if(source.character_id == 8)
                {
                    source.character_id = 0x39;
                }
                else if(source.character_id == 15)
                {
                    source.character_id = 0x3A;
                }
            }
            const battle_unit_id summon_id = summon->id;
            *summon = source;
            summon->id = summon_id;
            summon->active = true;
            summon->position = target_position;
            summon->summoner = source.id;
            summon->ai_linked_unit = source.id;
            summon->unit_state_code =
                    handler == effect_handler_kind::summon ? 0x02 : 0x04;
            summon->ledger.acted = true;
            summon->ledger.completed = true;
            source.ai_linked_unit = summon_id;
            result.summoned = true;
            result.summon_count = 1;
        }
        else if(handler == effect_handler_kind::summon_pair)
        {
            battle_unit_instance* auxiliary = nullptr;
            for(std::size_t index = 0; index < session._unit_count; ++index)
            {
                battle_unit_instance& candidate = session._units[index];
                if(! candidate.active && candidate.id != summon->id)
                {
                    auxiliary = &candidate;
                    break;
                }
            }
            if(! auxiliary)
            {
                result.error = action_error::summon_slot_unavailable;
                return result;
            }
            const battle_unit_id primary_id = summon->id;
            const battle_unit_id auxiliary_id = auxiliary->id;
            *summon = source;
            summon->id = primary_id;
            summon->active = true;
            summon->position = target_position;
            summon->summoner = source.id;
            summon->ai_linked_unit = auxiliary_id;
            summon->unit_state_code = 0x06;
            summon->ledger.acted = true;
            summon->ledger.completed = true;
            *auxiliary = source;
            auxiliary->id = auxiliary_id;
            auxiliary->active = true;
            auxiliary->position = target_position;
            auxiliary->summoner = source.id;
            auxiliary->ai_linked_unit = source.id;
            auxiliary->ai_secondary_linked_unit = primary_id;
            auxiliary->unit_state_code = 0x06;
            auxiliary->ledger.acted = true;
            auxiliary->ledger.completed = true;
            source.ai_linked_unit = primary_id;
            source.unit_state_code = 0x06;
            result.summoned = true;
            result.summon_count = 2;
        }
        else if(handler == effect_handler_kind::move)
        {
            result.movement_origin = source.position;
            result.movement_destination = target_position;
            result.moved = result.movement_origin != result.movement_destination;
            source.position = target_position;
        }
        else if(handler == effect_handler_kind::identity_transform)
        {
            result.identity_before = source.character_id;
            result.identity_after = target->character_id;
            result.identity_linked_unit = target->id;
            if(! battle_identity_system::apply(
                       source,
                       *target,
                       action.effect.duration_turns,
                       action.effect.flags))
            {
                result.error = action_error::status_capacity_exhausted;
                return result;
            }
            result.identity_overridden = true;
        }
        else if(handler == effect_handler_kind::no_effect)
        {
        }
        else if(handler == effect_handler_kind::linked_cleanup)
        {
            if(target->unit_state_code == 0x02 ||
                    target->unit_state_code == 0x04 ||
                    target->unit_state_code == 0x06)
            {
                target->active = false;
                target->ai_linked_unit = no_battle_unit;
                source.ai_linked_unit = no_battle_unit;
            }
            else if(target->unit_state_code == 0x08)
            {
                (void) battle_identity_system::cleanup(
                        *target, identity_restore_reason::cleanup);
            }
        }
        else if(handler == effect_handler_kind::restore_hp_and_chakra)
        {
            battle_unit_instance changed = *target;
            if(! _upsert_status(changed, action, 0x02))
            {
                result.error = action_error::status_capacity_exhausted;
                return result;
            }
            result.applied_status_count = 1;
            const passive_query_result restoration_bonus =
                    changed.passives.query(
                            hp_restoration_passive_target,
                            passive_definitions);
            const int requested_healing =
                    changed.max_hp / 5 +
                    (restoration_bonus.found ?
                             restoration_bonus.value_a :
                             0);
            const int missing = changed.max_hp - changed.hp;
            result.total_healing = requested_healing > missing ?
                    missing : requested_healing;
            changed.hp += result.total_healing;
            const int missing_chakra = changed.max_chakra - changed.chakra;
            result.chakra_delta = action.effect.potency > missing_chakra ?
                    missing_chakra : action.effect.potency;
            changed.chakra += result.chakra_delta;
            *target = changed;
        }
        else if(handler == effect_handler_kind::battlefield_object_type_1 ||
                handler == effect_handler_kind::battlefield_object_type_2)
        {
            battlefield_object_record object;
            object.type = handler == effect_handler_kind::battlefield_object_type_1 ?
                    1 : 2;
            object.x = static_cast<std::uint8_t>(target_position.x);
            object.y = static_cast<std::uint8_t>(target_position.y);
            object.payload_id = action.id;
            object.duration_ticks =
                    encode_status_duration_ticks(action.effect.duration_turns);
            if(handler == effect_handler_kind::battlefield_object_type_1)
            {
                object.source_unit_id = source.id;
            }
            result.battlefield_object_slot = session._objects.allocate(object);
            if(result.battlefield_object_slot == no_battlefield_object)
            {
                result.error =
                        action_error::battlefield_object_capacity_exhausted;
                return result;
            }
        }
        else if(handler == effect_handler_kind::chakra_restore ||
                handler == effect_handler_kind::chakra_reduce)
        {
            if(handler == effect_handler_kind::chakra_restore)
            {
                const int missing = target->max_chakra - target->chakra;
                result.chakra_delta = action.effect.potency > missing ?
                        missing : action.effect.potency;
            }
            else
            {
                const int removed = action.effect.potency > target->chakra ?
                        target->chakra : action.effect.potency;
                result.chakra_delta = -removed;
            }
            target->chakra += result.chakra_delta;
        }
        else if(handler == effect_handler_kind::reaction_state)
        {
            if(! _upsert_status(
                       *target,
                       action,
                       static_cast<std::uint8_t>(
                               action.effect.code |
                               action.effect.flags)))
            {
                result.error =
                        action_error::status_capacity_exhausted;
                return result;
            }
            result.applied_status_count = 1;
            const std::uint8_t before = target->reaction_state;
            _set_reaction_state(*target, 0x30);
            result.reaction_state_changed =
                    target->reaction_state != before;
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
                               encode_status_duration_ticks(action.effect.duration_turns),
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
                if(! _upsert_status(changed, action, code_with_flags))
                {
                    result.error = action_error::status_capacity_exhausted;
                    return result;
                }
                result.applied_status_count = 1;
            }
            if(action.effect.code == 0x0E)
            {
                if(! _upsert_status(changed, action, 0x3E))
                {
                    result.error = action_error::status_capacity_exhausted;
                    return result;
                }
                ++result.applied_status_count;
            }
            else if(action.effect.code == 0x0F)
            {
                if(! _upsert_status(changed, action, 0x3D))
                {
                    result.error = action_error::status_capacity_exhausted;
                    return result;
                }
                ++result.applied_status_count;
                const std::uint8_t before = changed.reaction_state;
                _set_reaction_state(changed, 0x30);
                result.reaction_state_changed =
                        changed.reaction_state != before;
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

    [[nodiscard]] static bool _upsert_status(
            battle_unit_instance& target,
            const action_definition& action,
            std::uint8_t code_with_flags)
    {
        return target.statuses.upsert({
            code_with_flags,
            0,
            encode_status_duration_ticks(action.effect.duration_turns),
            0,
            0,
            0,
            action.effect.potency,
        });
    }

    [[nodiscard]] static bool _apply_effect_flag_followups(
            battle_unit_instance& target,
            battle_unit_id source_id,
            std::uint8_t effect_flags,
            std::uint8_t potency,
            action_result& result)
    {
        battle_unit_instance changed = target;
        int applied = 0;
        if((effect_flags & 0x80) != 0)
        {
            if(! changed.statuses.upsert({
                       0x3F,
                       potency,
                       encode_status_duration_ticks(1),
                       0,
                       source_id,
                       0,
                       0,
                   }))
            {
                return false;
            }
            _set_reaction_state(changed, 0x30);
            result.reaction_state_changed |=
                    changed.reaction_state !=
                    target.reaction_state;
            ++applied;
        }
        if((effect_flags & 0x40) != 0)
        {
            constexpr std::array<std::uint8_t, 3>
                    poison_status_codes = {{
                        0x1F, 0x21, 0x23,
                    }};
            for(const std::uint8_t status_code :
                    poison_status_codes)
            {
                if(! changed.statuses.upsert({
                           status_code,
                           potency,
                           encode_status_duration_ticks(3),
                           0,
                           source_id,
                           0,
                           10,
                       }))
                {
                    return false;
                }
                ++applied;
            }
            battle_attribute_system::recompute(changed);
        }
        target = changed;
        result.applied_status_count += applied;
        return true;
    }

    static void _set_reaction_state(
            battle_unit_instance& target, std::uint8_t requested)
    {
        std::uint8_t state = requested;
        if(target.statuses.find(0x15) != no_status_slot)
        {
            state = 0x40;
        }
        else if(target.statuses.find(0x11) != no_status_slot &&
                requested != 0x40)
        {
            state = 0x20;
        }
        else if(requested != 0x40 && requested != 0x20 &&
                (target.statuses.find(0x0F) != no_status_slot ||
                 target.statuses.find(0x3F) != no_status_slot ||
                 target.statuses.find(0x3E) != no_status_slot ||
                 target.statuses.find(0x3D) != no_status_slot))
        {
            state = 0x30;
        }
        target.reaction_state = state;
    }

    template<std::size_t UnitCount>
    [[nodiscard]] static battle_unit_instance* _find_unit_in_array(
            std::array<battle_unit_instance, UnitCount>& units,
            battle_unit_id id)
    {
        for(battle_unit_instance& unit : units)
        {
            if(unit.id == id)
            {
                return &unit;
            }
        }
        return nullptr;
    }

    template<std::size_t UnitCount>
    [[nodiscard]] static const battle_unit_instance* _find_unit_in_array(
            const std::array<battle_unit_instance, UnitCount>& units,
            battle_unit_id id)
    {
        for(const battle_unit_instance& unit : units)
        {
            if(unit.id == id)
            {
                return &unit;
            }
        }
        return nullptr;
    }

    static void _merge_result(
            const action_result& source,
            action_result& destination)
    {
        destination.generated_hits += source.generated_hits;
        destination.effective_hits += source.effective_hits;
        destination.total_damage += source.total_damage;
        destination.total_healing += source.total_healing;
        destination.chakra_delta += source.chakra_delta;
        destination.applied_status_count += source.applied_status_count;
        destination.reaction_state_changed |=
                source.reaction_state_changed;
        destination.source_status_0x0d_consumed |=
                source.source_status_0x0d_consumed;
        destination.target_status_0x0d_consumed |=
                source.target_status_0x0d_consumed;
        destination.defeated |= source.defeated;
        destination.linked_resolution_count += source.linked_resolution_count;
        destination.damage_steps_truncated |= source.damage_steps_truncated;
        for(int index = 0; index < source.damage_step_count; ++index)
        {
            if(destination.damage_step_count <
                    static_cast<int>(destination.damage_steps.size()))
            {
                destination.damage_steps[
                        static_cast<std::size_t>(
                                destination.damage_step_count)] =
                        source.damage_steps[static_cast<std::size_t>(index)];
                ++destination.damage_step_count;
            }
            else
            {
                destination.damage_steps_truncated = true;
            }
        }
        if(destination.reaction_code == 0 && source.reaction_code != 0)
        {
            destination.reaction_code = source.reaction_code;
            destination.reaction_action_id = source.reaction_action_id;
            destination.reaction_hit_index = source.reaction_hit_index;
            destination.reaction_event = source.reaction_event;
        }
    }

    enum class incoming_reaction_flow : std::uint8_t
    {
        not_triggered,
        continue_incoming_damage,
        cancel_remaining_hits,
    };

    template<std::size_t MaxUnits>
    [[nodiscard]] static incoming_reaction_flow
    _resolve_incoming_reaction(
            battle_session<MaxUnits>& session,
            battle_unit_instance& incoming_source,
            battle_unit_instance& defending_target,
            int hit_index,
            deterministic_rng& rng,
            action_result& result)
    {
        const incoming_reaction_selection selected =
                _select_incoming_reaction(defending_target);
        if(! selected)
        {
            return incoming_reaction_flow::not_triggered;
        }
        const status_record* stored =
                defending_target.statuses.active(selected.slot);
        if(! stored)
        {
            return incoming_reaction_flow::not_triggered;
        }
        const status_record reaction = *stored;

        if(selected.code == 0x04)
        {
            if(_distance(
                       incoming_source.position,
                       defending_target.position) != 1)
            {
                return incoming_reaction_flow::not_triggered;
            }
            result.reaction_code = 0x04;
            result.reaction_action_id = reaction.raw_parameter_1;
            result.reaction_hit_index = hit_index;
            result.reaction_event = {
                true,
                0x04,
                defense_action_kind::active_action,
                reaction.raw_parameter_1,
                no_tool_slot,
                defending_target.id,
                incoming_source.id,
                hit_index,
                0,
                false,
            };
            (void) defending_target.statuses.remove(
                    0x04,
                    status_remove_mode::consume_without_event);
            return incoming_reaction_flow::
                    cancel_remaining_hits;
        }

        if(selected.code == 0x0A || selected.code == 0x09)
        {
            if(_distance(
                       incoming_source.position,
                       defending_target.position) >
                    reaction.raw_parameter_3_low5)
            {
                return incoming_reaction_flow::not_triggered;
            }

            _resolve_counter_reaction(
                    session,
                    incoming_source,
                    defending_target,
                    selected.code,
                    reaction,
                    hit_index,
                    result);
            if(! _apply_effect_flag_followups(
                       incoming_source,
                       defending_target.id,
                       reaction.code_with_flags & 0xC0,
                       static_cast<std::uint8_t>(
                               reaction.value_u16),
                       result))
            {
                result.error =
                        action_error::
                                status_capacity_exhausted;
            }
            return selected.code == 0x09 ?
                    incoming_reaction_flow::
                            cancel_remaining_hits :
                    incoming_reaction_flow::
                            continue_incoming_damage;
        }

        if(selected.code == 0x10)
        {
            result.reaction_code = 0x10;
            result.reaction_action_id = reaction.raw_parameter_1;
            result.reaction_hit_index = hit_index;
            result.reaction_event = {
                true,
                0x10,
                defense_action_kind::active_action,
                reaction.raw_parameter_1,
                no_tool_slot,
                defending_target.id,
                incoming_source.id,
                hit_index,
                0,
                false,
            };
            (void) defending_target.statuses.remove(
                    0x10,
                    status_remove_mode::consume_without_event);
            return incoming_reaction_flow::
                    cancel_remaining_hits;
        }

        if(selected.code == 0x16)
        {
            if(_distance(
                       incoming_source.position,
                       defending_target.position) != 1)
            {
                return incoming_reaction_flow::not_triggered;
            }
            grid_point destination = {};
            if(_substitution_destination(
                               session,
                               defending_target,
                               rng,
                               destination))
            {
                const grid_point origin =
                        defending_target.position;
                defending_target.position = destination;
                result.reaction_code = 0x16;
                result.reaction_action_id =
                        reaction.raw_parameter_1;
                result.reaction_hit_index = hit_index;
                result.moved = true;
                result.movement_origin = origin;
                result.movement_destination = destination;
                const bool ninja_tool =
                        (reaction.raw_parameter_1 & 0x80) != 0;
                result.reaction_event = {
                    true,
                    0x16,
                    ninja_tool ?
                            defense_action_kind::ninja_tool :
                            defense_action_kind::active_action,
                    static_cast<ability_id>(
                            reaction.raw_parameter_1 & 0x7F),
                    ninja_tool ?
                            reaction.raw_parameter_3_low5 :
                            no_tool_slot,
                    defending_target.id,
                    incoming_source.id,
                    hit_index,
                    0,
                    false,
                    true,
                    origin,
                    destination,
                };
                if(! _apply_effect_flag_followups(
                           incoming_source,
                           defending_target.id,
                           reaction.code_with_flags & 0xC0,
                           static_cast<std::uint8_t>(
                                   reaction.value_u16),
                           result))
                {
                    result.error =
                            action_error::
                                    status_capacity_exhausted;
                    return incoming_reaction_flow::
                            cancel_remaining_hits;
                }
                (void) defending_target.statuses.remove(
                        0x16,
                        status_remove_mode::
                                consume_without_event);
                return incoming_reaction_flow::
                        cancel_remaining_hits;
            }
            return incoming_reaction_flow::not_triggered;
        }

        if(selected.code != 0x19 ||
                _distance(
                        incoming_source.position,
                        defending_target.position) != 1)
        {
            return incoming_reaction_flow::not_triggered;
        }

        _resolve_counter_reaction(
                session,
                incoming_source,
                defending_target,
                0x19,
                reaction,
                hit_index,
                result);
        if(! _apply_effect_flag_followups(
                   incoming_source,
                   defending_target.id,
                   reaction.code_with_flags & 0xC0,
                   static_cast<std::uint8_t>(
                           reaction.value_u16),
                   result))
        {
            result.error =
                    action_error::
                            status_capacity_exhausted;
        }
        return incoming_reaction_flow::cancel_remaining_hits;
    }

    template<std::size_t MaxUnits>
    static void _resolve_counter_reaction(
            battle_session<MaxUnits>& session,
            battle_unit_instance& incoming_source,
            battle_unit_instance& defending_target,
            std::uint8_t reaction_code,
            const status_record& reaction,
            int hit_index,
            action_result& result)
    {
        result.reaction_code = reaction_code;
        result.reaction_action_id = reaction.raw_parameter_1;
        result.reaction_hit_index = hit_index;
        (void) defending_target.statuses.remove(
                reaction_code,
                status_remove_mode::consume_without_event);

        const int counter_damage = _damage_per_hit(
                defending_target,
                incoming_source,
                reaction.value_u16);
        const int hp_before = incoming_source.hp;
        _apply_damage_resolution(
                session,
                defending_target,
                incoming_source,
                counter_damage,
                reaction_code,
                false,
                hit_index,
                false,
                1,
                result);
        const bool ninja_tool =
                (reaction.raw_parameter_1 & 0x80) != 0;
        result.reaction_event = {
            true,
            reaction_code,
            ninja_tool ?
                    defense_action_kind::ninja_tool :
                    defense_action_kind::active_action,
            static_cast<ability_id>(
                    reaction.raw_parameter_1 & 0x7F),
            ninja_tool ?
                    reaction.raw_parameter_3_low5 :
                    no_tool_slot,
            defending_target.id,
            incoming_source.id,
            hit_index,
            hp_before - incoming_source.hp,
            ! incoming_source.active,
        };
    }

    struct incoming_reaction_selection
    {
        std::uint8_t code = 0;
        std::uint8_t slot = no_status_slot;

        [[nodiscard]] constexpr explicit operator bool() const
        {
            return slot != no_status_slot;
        }
    };

    [[nodiscard]] static incoming_reaction_selection
    _select_incoming_reaction(
            const battle_unit_instance& target)
    {
        for(const std::uint8_t code :
                incoming_reaction_priority)
        {
            const std::uint8_t slot =
                    target.statuses.find(code);
            if(slot != no_status_slot)
            {
                return { code, slot };
            }
        }
        return {};
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static bool _substitution_destination(
            const battle_session<MaxUnits>& session,
            const battle_unit_instance& defender,
            deterministic_rng& rng,
            grid_point& destination)
    {
        // These offsets are the complete Manhattan-distance 1–2 ring
        // represented by the natural Kawarimi samples. Starting at an
        // RNG-selected offset preserves the original non-fixed landing.
        static constexpr std::array<grid_point, 12> offsets = {{
            { -1, -1 },
            { 0, -2 },
            { 0, 1 },
            { -1, 1 },
            { 1, 0 },
            { 0, -1 },
            { 0, 2 },
            { 1, 1 },
            { -1, 0 },
            { 1, -1 },
            { -2, 0 },
            { 2, 0 },
        }};
        const std::size_t start =
                static_cast<std::size_t>(rng.next_u15()) %
                offsets.size();
        for(std::size_t index = 0;
                index < offsets.size();
                ++index)
        {
            const grid_point offset =
                    offsets[(start + index) % offsets.size()];
            const grid_point candidate = {
                defender.position.x + offset.x,
                defender.position.y + offset.y,
            };
            const bool traversable =
                    session._battlefield.configured ?
                    session._battlefield.contains(candidate) :
                    candidate.x >= 0 && candidate.y >= 0;
            if(traversable &&
                    ! session.active_unit_at(candidate))
            {
                destination = candidate;
                return true;
            }
        }
        return false;
    }

    template<std::size_t MaxUnits>
    static void _apply_damage_resolution(
            battle_session<MaxUnits>& session,
            battle_unit_instance& experience_recipient,
            battle_unit_instance& target,
            int damage,
            std::uint8_t event_type,
            bool recursion_guard,
            int hit_index,
            bool linked_step,
            std::uint8_t hit_flags,
            action_result& result)
    {
        if(! recursion_guard && event_type != 0x1F)
        {
            const std::uint8_t status_index = target.statuses.find(0x0E);
            if(status_index != no_status_slot)
            {
                const status_record* linked_status =
                        target.statuses.active(status_index);
                battle_unit_instance* linked = linked_status ?
                        session._find_unit(
                                linked_status->raw_parameter_4) :
                        nullptr;
                if(linked && linked->active &&
                        linked->id != target.id)
                {
                    ++result.linked_resolution_count;
                    _apply_damage_resolution(
                            session,
                            experience_recipient,
                            *linked,
                            damage,
                            event_type,
                            true,
                            hit_index,
                            true,
                            hit_flags,
                            result);
                }
            }
        }

        if(! target.active)
        {
            return;
        }
        const int applied = damage > target.hp ? target.hp : damage;
        target.hp -= applied;
        result.total_damage += applied;
        const bool defeated = target.hp == 0;
        if(defeated)
        {
            (void) battle_identity_system::cleanup(
                    target, identity_restore_reason::cleanup);
            target.active = false;
            if(target.id != experience_recipient.id)
            {
                experience_recipient.carried_experience +=
                        target.carried_experience;
                target.carried_experience = 0;
            }
            if(! linked_step)
            {
                result.defeated = true;
            }
        }

        if(result.damage_step_count < static_cast<int>(result.damage_steps.size()))
        {
            result.damage_steps[static_cast<std::size_t>(result.damage_step_count)] = {
                target.id,
                applied,
                hit_index,
                linked_step,
                defeated,
                hit_flags,
            };
            ++result.damage_step_count;
        }
        else
        {
            result.damage_steps_truncated = true;
        }
    }

    [[nodiscard]] static int _success_rate(
            const battle_unit_instance& source,
            const battle_unit_instance& target,
            int base_rate)
    {
        const battle_attribute_view source_attributes = battle_attribute_system::view(source);
        const battle_attribute_view target_attributes = battle_attribute_system::view(target);
        int result = base_rate +
                (source_attributes.agility - target_attributes.agility) / 2;
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

    [[nodiscard]] static int _hit_count(
            const battle_unit_instance& source, const action_definition& action)
    {
        int result = action.effect.base_hit_count;
        if(action.effect.code == 0x14)
        {
            const std::uint8_t status_index = source.statuses.find(0x13);
            if(status_index == no_status_slot)
            {
                return -1;
            }
            const status_record* status =
                    source.statuses.active(status_index);
            if(! status)
            {
                return -1;
            }
            result += status->value_u16 & 0xFF;
        }
        return result;
    }

    [[nodiscard]] static int _roll_continuation_hit(
            const battle_unit_instance& source,
            const action_definition& action,
            deterministic_rng& rng)
    {
        if(action.effect.code != 0x01 &&
                action.effect.code != 0x14 &&
                action.effect.code != 0x15)
        {
            return 0;
        }

        std::uint8_t passive_target = 0;
        switch(action.cost.kind)
        {
        case action_cost_kind::current_hp:
            passive_target =
                    current_hp_continuation_passive_target;
            break;
        case action_cost_kind::current_chakra:
            passive_target =
                    current_chakra_continuation_passive_target;
            break;
        case action_cost_kind::battle_local_ninja_tool_slot:
            passive_target =
                    ninja_tool_continuation_passive_target;
            break;
        default:
            return 0;
        }

        const passive_query_result continuation =
                source.passives.query(
                        passive_target,
                        passive_definitions);
        return continuation.found &&
                       _next_battle_percent(rng) <
                               continuation.value_a ?
                1 : 0;
    }

    [[nodiscard]] static int _damage_per_hit(
            const battle_unit_instance& source,
            const battle_unit_instance& target,
            int potency)
    {
        return _damage_candidates(source, target, potency).normal_defended;
    }

    struct damage_candidates
    {
        int normal_defended = 0;
        int critical_defended = 0;
        int normal_ignore_defense = 0;
        int critical_ignore_defense = 0;
    };

    [[nodiscard]] static damage_candidates _damage_candidates(
            const battle_unit_instance& source,
            const battle_unit_instance& target,
            int potency)
    {
        const battle_attribute_view source_attributes = battle_attribute_system::view(source);
        const battle_attribute_view target_attributes = battle_attribute_system::view(target);
        const int scaled_attack = source_attributes.attack;
        const int raw = potency * scaled_attack / 10;
        const int critical_raw = raw * 3 / 2;
        int defense_factor = 100 - 5 * _integer_sqrt(target_attributes.defense);
        if(defense_factor < 0)
        {
            defense_factor = 0;
        }
        return {
            raw * defense_factor / 100,
            critical_raw * defense_factor / 100,
            raw,
            critical_raw,
        };
    }

    [[nodiscard]] static int _next_battle_percent(
            deterministic_rng& rng)
    {
        return rng.next_u15() * 100 / 32768;
    }

    [[nodiscard]] static std::uint8_t _resolve_hit_flags(
            const battle_unit_instance& source,
            deterministic_rng& rng)
    {
        std::uint8_t result = 1;
        const passive_query_result critical =
                source.passives.query(
                        critical_passive_target,
                        passive_definitions);
        if(critical.found)
        {
            int chance = critical.value_a + 10;
            if(chance > 100)
            {
                chance = 100;
            }
            if(_next_battle_percent(rng) < chance)
            {
                result = 2;
            }
        }

        const passive_query_result ignore_defense =
                source.passives.query(
                        ignore_defense_passive_target,
                        passive_definitions);
        if(ignore_defense.found &&
                _next_battle_percent(rng) < ignore_defense.value_a)
        {
            result |= 4;
        }
        return result;
    }

    [[nodiscard]] static int _select_damage(
            const damage_candidates& candidates,
            std::uint8_t hit_flags)
    {
        switch(hit_flags & 6)
        {
        case 2:
            return candidates.critical_defended;
        case 4:
            return candidates.normal_ignore_defense;
        case 6:
            return candidates.critical_ignore_defense;
        default:
            return candidates.normal_defended;
        }
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
