#ifndef KONOHA_BATTLE_ABILITIES_H
#define KONOHA_BATTLE_ABILITIES_H

#include "konoha/battle_session.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class target_rule : std::uint8_t
{
    self,
    ally_unit,
    enemy_unit,
    empty_tile,
};

struct ability_cost
{
    int chakra = 0;
    int inventory = 0;
};

enum class effect_node_kind : std::uint8_t
{
    damage,
    heal,
    add_status,
    move,
    summon,
    capture,
    prepare_defense,
    substitute,
    scripted_event,
};

struct effect_node
{
    effect_node_kind kind = effect_node_kind::damage;
    int value = 0;
    int secondary = 0;
};

template<std::size_t MaxEffects>
struct ability_definition
{
    static_assert(MaxEffects > 0);

    ability_id id = no_ability;
    target_rule target = target_rule::enemy_unit;
    int minimum_range = 0;
    int maximum_range = 1;
    ability_cost cost;
    int hit_percent = 100;
    std::array<effect_node, MaxEffects> effects = {};
    std::size_t effect_count = 0;
};

enum class ability_error : std::uint8_t
{
    none,
    invalid_definition,
    invalid_source,
    action_already_used,
    insufficient_chakra,
    invalid_target,
    target_out_of_range,
    summon_slot_unavailable,
};

struct ability_preview
{
    ability_error error = ability_error::none;
    int chakra_cost = 0;
    int damage = 0;
    int healing = 0;

    [[nodiscard]] constexpr bool legal() const
    {
        return error == ability_error::none;
    }
};

struct ability_result
{
    ability_error error = ability_error::none;
    std::size_t applied_effects = 0;
    bool hit = false;
    bool defeated = false;
    bool summoned = false;
    bool captured = false;
    bool substituted = false;
    int scripted_event = 0;

    [[nodiscard]] constexpr bool success() const
    {
        return error == ability_error::none;
    }
};

class deterministic_rng
{
public:
    explicit constexpr deterministic_rng(std::uint32_t seed) : _state(seed ? seed : 1)
    {
    }

    [[nodiscard]] int next_percent()
    {
        _state = _state * 1664525U + 1013904223U;
        return static_cast<int>((_state >> 16U) % 100U);
    }

private:
    std::uint32_t _state;
};

class ability_resolver
{
public:
    template<std::size_t MaxUnits, std::size_t MaxEffects>
    [[nodiscard]] static ability_result resolve_draft(
            battle_session<MaxUnits>& session,
            battle_unit_id target_id,
            battle_unit_id summon_id,
            const ability_definition<MaxEffects>& ability,
            grid_point target_position,
            deterministic_rng& rng)
    {
        if(session._lifecycle != battle_lifecycle::action_drafting || ! session._draft.active)
        {
            return { ability_error::invalid_source };
        }

        battle_session<MaxUnits> next = session;
        battle_unit_instance* source = next._find_unit(next._draft.unit_id);
        battle_unit_instance* target = target_id == no_battle_unit ?
                nullptr : next._find_unit(target_id);
        battle_unit_instance* summon = summon_id == no_battle_unit ?
                nullptr : next._find_unit(summon_id);
        if(! source)
        {
            return { ability_error::invalid_source };
        }
        source->position = next._draft.preview_position;
        const ability_result result = resolve(
                *source, target, summon, ability, target_position, rng);
        if(! result.success())
        {
            return result;
        }
        const battle_transition transition = next.commit_action(source->facing, no_ability);
        if(transition == battle_transition::invalid)
        {
            return { ability_error::invalid_source };
        }
        session = next;
        return result;
    }

    template<std::size_t MaxEffects>
    [[nodiscard]] static ability_preview preview(
            const battle_unit_instance& source,
            const battle_unit_instance* target,
            const battle_unit_instance* summon_slot,
            const ability_definition<MaxEffects>& ability,
            grid_point target_position)
    {
        ability_preview result;
        result.error = _validate(source, target, summon_slot, ability, target_position);
        if(result.error != ability_error::none)
        {
            return result;
        }

        result.chakra_cost = ability.cost.chakra;
        for(std::size_t index = 0; index < ability.effect_count; ++index)
        {
            const effect_node& node = ability.effects[index];
            if(node.kind == effect_node_kind::damage)
            {
                result.damage += node.value;
            }
            else if(node.kind == effect_node_kind::heal)
            {
                result.healing += node.value;
            }
        }
        return result;
    }

    template<std::size_t MaxEffects>
    [[nodiscard]] static ability_result resolve(
            battle_unit_instance& source,
            battle_unit_instance* target,
            battle_unit_instance* summon_slot,
            const ability_definition<MaxEffects>& ability,
            grid_point target_position,
            deterministic_rng& rng)
    {
        const ability_preview checked = preview(
                source, target, summon_slot, ability, target_position);
        if(! checked.legal())
        {
            return { checked.error };
        }

        battle_unit_instance next_source = source;
        battle_unit_instance next_target = target ? *target : battle_unit_instance{};
        battle_unit_instance next_summon = summon_slot ? *summon_slot : battle_unit_instance{};
        battle_unit_instance* target_state = target == &source ? &next_source :
                (target ? &next_target : nullptr);

        ability_result result;
        next_source.chakra -= ability.cost.chakra;
        next_source.ledger.acted = true;
        result.hit = rng.next_percent() < ability.hit_percent;
        if(result.hit)
        {
            bool suppress_damage = target_state && target_state->substitution_ready;
            if(suppress_damage)
            {
                target_state->substitution_ready = false;
                result.substituted = true;
            }
            for(std::size_t index = 0; index < ability.effect_count; ++index)
            {
                const effect_node& node = ability.effects[index];
                switch(node.kind)
                {
                case effect_node_kind::damage:
                    if(! suppress_damage)
                    {
                        target_state->hp = node.value >= target_state->hp ?
                                0 : target_state->hp - node.value;
                        if(target_state->hp == 0)
                        {
                            target_state->active = false;
                            result.defeated = true;
                        }
                    }
                    break;
                case effect_node_kind::heal:
                    target_state->hp = node.value >= target_state->max_hp - target_state->hp ?
                            target_state->max_hp : target_state->hp + node.value;
                    break;
                case effect_node_kind::add_status:
                    target_state->status_mask |= static_cast<std::uint32_t>(node.value);
                    break;
                case effect_node_kind::move:
                    target_state->position.x += node.value;
                    target_state->position.y += node.secondary;
                    break;
                case effect_node_kind::summon:
                    next_summon.active = true;
                    next_summon.side = next_source.side;
                    next_summon.position = target_position;
                    next_summon.summoner = next_source.id;
                    result.summoned = true;
                    break;
                case effect_node_kind::capture:
                    target_state->captured = true;
                    target_state->active = false;
                    result.captured = true;
                    break;
                case effect_node_kind::prepare_defense:
                    next_source.ledger.defense_ability = static_cast<ability_id>(node.value);
                    break;
                case effect_node_kind::substitute:
                    next_source.substitution_ready = true;
                    break;
                case effect_node_kind::scripted_event:
                    result.scripted_event = node.value;
                    break;
                }
                ++result.applied_effects;
            }
        }

        source = next_source;
        if(target && target != &source)
        {
            *target = next_target;
        }
        if(summon_slot)
        {
            *summon_slot = next_summon;
        }
        return result;
    }

private:
    template<std::size_t MaxEffects>
    [[nodiscard]] static ability_error _validate(
            const battle_unit_instance& source,
            const battle_unit_instance* target,
            const battle_unit_instance* summon_slot,
            const ability_definition<MaxEffects>& ability,
            grid_point target_position)
    {
        if(ability.id == no_ability || ability.effect_count == 0 ||
                ability.effect_count > MaxEffects || ability.minimum_range < 0 ||
                ability.maximum_range < ability.minimum_range || ability.cost.chakra < 0 ||
                ability.hit_percent < 0 || ability.hit_percent > 100)
        {
            return ability_error::invalid_definition;
        }
        bool has_unit_target_effect = false;
        bool has_summon_effect = false;
        for(std::size_t index = 0; index < ability.effect_count; ++index)
        {
            const effect_node& node = ability.effects[index];
            if((node.kind == effect_node_kind::damage || node.kind == effect_node_kind::heal ||
                    node.kind == effect_node_kind::add_status) && node.value < 0)
            {
                return ability_error::invalid_definition;
            }
            if(node.kind == effect_node_kind::add_status && node.value == 0)
            {
                return ability_error::invalid_definition;
            }
            has_unit_target_effect = has_unit_target_effect ||
                    node.kind == effect_node_kind::damage ||
                    node.kind == effect_node_kind::heal ||
                    node.kind == effect_node_kind::add_status ||
                    node.kind == effect_node_kind::move ||
                    node.kind == effect_node_kind::capture;
            has_summon_effect = has_summon_effect || node.kind == effect_node_kind::summon;
        }
        if(ability.target == target_rule::empty_tile && has_unit_target_effect)
        {
            return ability_error::invalid_definition;
        }
        if(has_summon_effect && (! summon_slot || summon_slot->active))
        {
            return ability_error::summon_slot_unavailable;
        }
        if(! source.active)
        {
            return ability_error::invalid_source;
        }
        if(source.ledger.acted)
        {
            return ability_error::action_already_used;
        }
        if(source.chakra < ability.cost.chakra)
        {
            return ability_error::insufficient_chakra;
        }

        if(ability.target == target_rule::empty_tile)
        {
            if(target)
            {
                return ability_error::invalid_target;
            }
        }
        else
        {
            if(! target || ! target->active || target->position != target_position)
            {
                return ability_error::invalid_target;
            }
            if(ability.target == target_rule::self && target != &source)
            {
                return ability_error::invalid_target;
            }
            if(ability.target == target_rule::ally_unit && target->side != source.side)
            {
                return ability_error::invalid_target;
            }
            if(ability.target == target_rule::enemy_unit && target->side == source.side)
            {
                return ability_error::invalid_target;
            }
        }

        const int dx = source.position.x > target_position.x ?
                source.position.x - target_position.x : target_position.x - source.position.x;
        const int dy = source.position.y > target_position.y ?
                source.position.y - target_position.y : target_position.y - source.position.y;
        const int distance = dx + dy;
        if(distance < ability.minimum_range || distance > ability.maximum_range)
        {
            return ability_error::target_out_of_range;
        }
        return ability_error::none;
    }
};

}

#endif
