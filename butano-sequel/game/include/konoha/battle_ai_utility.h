#ifndef KONOHA_BATTLE_AI_UTILITY_H
#define KONOHA_BATTLE_AI_UTILITY_H

#include "konoha/battle_ai_target_index.h"
#include "konoha/battle_random.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

struct ai_queued_event
{
    ability_id action_id = no_ability;
    std::uint8_t code_with_flags = 0;
    battle_unit_id target_id = no_battle_unit;
    int amount_per_hit = 0;
    int hit_count = 0;
    int success_rate_percent = 0;
    int map_distance = 0;
    bool target_position_threatened = false;
    bool position_mode_uses_actor = false;

    [[nodiscard]] constexpr std::uint8_t code() const
    {
        return code_with_flags & 0x3F;
    }
};

struct ai_actor_projection
{
    int hp_before = 0;
    int hp_after = 0;
    int max_hp = 0;
    int chakra_before = 0;
    int chakra_after = 0;
    int max_chakra = 0;
    int max_action_range = 0;
    bool actor_threatened_after = false;
    bool has_active_scenario_rule = false;
};

enum class ai_candidate_kind : std::uint8_t
{
    none = 0,
    move = 1,
    replenish_chakra = 2,
    rest = 3,
    selected_action = 4,
};

struct ai_action_projection
{
    bool selected = false;
    std::uint8_t runtime_kind = 0;
    std::uint8_t effect_code = 0;
    ai_candidate_kind no_action_candidate_kind =
            ai_candidate_kind::none;
};

struct ai_utility_policy
{
    std::array<int, 2> base_weights = {};
    int actor_hp_gain_weight = 0;
    int actor_hp_survival_weight = 0;
    int actor_chakra_gain_weight = 0;
    int actor_chakra_retention_weight = 0;
    int selected_kind_1_bias_weight = 0;
    int selected_kind_5_bias_weight = 0;
    int selected_kind_4_bias_weight = 0;
    int no_action_candidate_kind_2_or_3_weight = 0;
    int no_action_other_candidate_kind_weight = 0;
    std::array<int, 8> kind_5_effect_low_3_weights = {};
    std::array<int, ai_target_selector_count> hostile_target_selector_weights = {};
    std::array<int, ai_target_selector_count> friendly_target_selector_weights = {};
    int damage_weight = 0;
    int success_rate_weight = 0;
    int target_coverage_weight = 0;
    int range_usage_weight = 0;
    int random_term_scale = 0;

    [[nodiscard]] static constexpr ai_utility_policy standard()
    {
        return {
            { 1000, 2500 },
            3000,
            7000,
            6000,
            500,
            8000,
            5000,
            2000,
            8000,
            3000,
            { 7000, 6000, 8000, 3000, 5000, 6000, 0, 0 },
            { 1700, 800, 800, 1300, 1000, 800, 3600 },
            { 4200, 2000, 1000, 1000, 1000, 800, 0 },
            6000,
            900,
            3000,
            100,
            10,
        };
    }

    [[nodiscard]] static constexpr ai_utility_policy zero_common_weights()
    {
        ai_utility_policy result;
        result.random_term_scale = 10;
        return result;
    }
};

inline constexpr std::array<ai_utility_policy, 8>
        ai_utility_policies = {{
            ai_utility_policy::zero_common_weights(),
            ai_utility_policy::standard(),
            ai_utility_policy::standard(),
            ai_utility_policy::standard(),
            ai_utility_policy::standard(),
            ai_utility_policy::standard(),
            ai_utility_policy::standard(),
            ai_utility_policy::standard(),
        }};

struct ai_utility_score
{
    int score = 0;
    int component_sum = 0;
    int component_count = 0;
    int penalty = 0;
    int random_term = 0;
    bool random_only = false;
};

struct ai_utility_components
{
    int component_sum = 0;
    int component_count = 0;
};

class ai_status_aware_score_policy
{
public:
    [[nodiscard]] static bool event_contributes(
            const battle_unit_instance& target,
            const ai_queued_event& event)
    {
        const std::uint8_t code = event.code();
        if((code == 0x3F || code == 0x0F || code == 0x0E ||
            (event.code_with_flags & 0x80) != 0) &&
                _has_any(target, { 0x3F, 0x3E, 0x3D, 0x0F, 0x11 }))
        {
            return false;
        }
        if((event.code_with_flags & 0x40) != 0 &&
                _has_any(target, { 0x1F, 0x21, 0x23, 0, 0 }))
        {
            return false;
        }
        switch(code)
        {
        case 0x1E:
            return target.statuses.find(0x1E) == no_status_slot;
        case 0x20:
            return target.statuses.find(0x20) == no_status_slot;
        case 0x22:
            return target.statuses.find(0x22) == no_status_slot;
        case 0x24:
            return target.statuses.find(0x24) == no_status_slot;
        case 0x26:
            return ! _has_any(target, { 0x1E, 0x20, 0x22, 0x1B, 0 });
        default:
            return true;
        }
    }

private:
    [[nodiscard]] static bool _has_any(
            const battle_unit_instance& target,
            std::array<std::uint8_t, 5> codes)
    {
        for(std::uint8_t code : codes)
        {
            if(code != 0 && target.statuses.find(code) != no_status_slot)
            {
                return true;
            }
        }
        return false;
    }
};

class battle_ai_utility_scorer
{
public:
    inline static constexpr int effect_7_safe_position_bonus = 8000;

    [[nodiscard]] static ai_utility_score score_actor_projection(
            const ai_actor_projection& projection,
            const ai_utility_policy& policy)
    {
        ai_utility_score result;
        result.component_sum =
                policy.base_weights[0] + policy.base_weights[1];
        if(projection.hp_after > projection.hp_before)
        {
            _add_component(
                    _ratio(
                            policy.actor_hp_gain_weight,
                            projection.hp_after - projection.hp_before,
                            projection.max_hp),
                    result);
        }
        else
        {
            _add_component(
                    _ratio(
                            policy.actor_hp_survival_weight,
                            projection.hp_after,
                            projection.hp_before),
                    result);
        }
        if(projection.chakra_after > projection.chakra_before)
        {
            _add_component(
                    _ratio(
                            policy.actor_chakra_gain_weight,
                            projection.chakra_after -
                                    projection.chakra_before,
                            projection.max_chakra),
                    result);
        }
        else
        {
            _add_component(
                    _ratio(
                            policy.actor_chakra_retention_weight,
                            projection.chakra_after,
                            projection.chakra_before),
                    result);
        }
        return result;
    }

    [[nodiscard]] static ai_utility_score score_action_projection(
            const ai_action_projection& projection,
            const ai_utility_policy& policy)
    {
        ai_utility_score result;
        if(! projection.selected)
        {
            const bool resource_command =
                    projection.no_action_candidate_kind ==
                            ai_candidate_kind::replenish_chakra ||
                    projection.no_action_candidate_kind ==
                            ai_candidate_kind::rest;
            _add_component(
                    resource_command ?
                    policy.no_action_candidate_kind_2_or_3_weight :
                    policy.no_action_other_candidate_kind_weight,
                    result);
            return result;
        }

        switch(projection.runtime_kind)
        {
        case 1:
            _add_component(policy.selected_kind_1_bias_weight, result);
            break;
        case 4:
            _add_component(policy.selected_kind_4_bias_weight, result);
            break;
        case 5:
            _add_component(policy.selected_kind_5_bias_weight, result);
            _add_component(
                    policy.kind_5_effect_low_3_weights[
                            projection.effect_code & 7],
                    result);
            break;
        default:
            _add_component(0, result);
            break;
        }
        return result;
    }

    template<std::size_t UnitCount, std::size_t EventCapacity>
    [[nodiscard]] static ai_utility_score score(
            const battle_unit_instance& actor,
            const ai_actor_projection& projection,
            const ai_action_projection& action_projection,
            const std::array<battle_unit_instance, UnitCount>& units,
            const ai_target_index& target_index,
            const std::array<ai_queued_event, EventCapacity>& events,
            std::size_t event_count,
            const ai_utility_policy& policy,
            deterministic_rng& rng,
            const ai_utility_components& scenario_rule_components = {})
    {
        static_assert(UnitCount > 0);
        static_assert(EventCapacity > 0);
        if((actor.status_mask & 0x0E) == 2)
        {
            const int random_only_score = _scaled_random(rng, 100);
            return { random_only_score, 0, 0, 0, random_only_score, true };
        }

        if(event_count > EventCapacity)
        {
            event_count = EventCapacity;
        }
        ai_utility_score result =
                score_actor_projection(projection, policy);
        const ai_utility_score action_score =
                score_action_projection(action_projection, policy);
        result.component_sum += action_score.component_sum;
        result.component_count += action_score.component_count;

        std::array<int, UnitCount> damage_by_unit = {};
        std::array<bool, UnitCount> damaged_unit = {};
        int distinct_damaged_targets = 0;
        int maximum_success = 0;
        int maximum_range = 0;

        for(std::size_t event_index = 0; event_index < event_count; ++event_index)
        {
            const ai_queued_event& event = events[event_index];
            const std::size_t target_slot = _find_unit_slot(units, event.target_id);
            if(target_slot == UnitCount)
            {
                continue;
            }

            if(event.code() == 0x01 || event.code() == 0x14 || event.code() == 0x15)
            {
                const int event_damage = event.amount_per_hit * event.hit_count;
                if(event_damage > 0)
                {
                    damage_by_unit[target_slot] += event_damage;
                    if(! damaged_unit[target_slot])
                    {
                        damaged_unit[target_slot] = true;
                        ++distinct_damaged_targets;
                    }
                    if(event.success_rate_percent > maximum_success)
                    {
                        maximum_success = event.success_rate_percent;
                    }
                    if(event.map_distance > maximum_range)
                    {
                        maximum_range = event.map_distance;
                    }
                }
            }
        }

        if(action_projection.selected)
        {
            const std::uint8_t effect_low_3 =
                    action_projection.effect_code & 7;
            if(effect_low_3 == 2 || effect_low_3 == 3)
            {
                _add_component(
                        _target_selector_component(
                                units,
                                target_index.opposite_side,
                                events,
                                event_count,
                                policy.hostile_target_selector_weights),
                        result);
            }
            if(effect_low_3 == 1 || effect_low_3 == 3 ||
                    effect_low_3 == 5)
            {
                _add_component(
                        _target_selector_component(
                                units,
                                target_index.same_side,
                                events,
                                event_count,
                                policy.friendly_target_selector_weights),
                        result);
            }
        }

        if(action_projection.selected &&
                action_projection.runtime_kind == 1)
        {
            int largest_damage = 0;
            int selected_target_hp = 0;
            for(std::size_t unit_index = 0; unit_index < UnitCount; ++unit_index)
            {
                if(damage_by_unit[unit_index] > largest_damage)
                {
                    largest_damage = damage_by_unit[unit_index];
                    selected_target_hp = units[unit_index].hp;
                }
            }
            const int capped_damage = selected_target_hp > 0 &&
                    largest_damage > selected_target_hp ?
                    selected_target_hp : largest_damage;
            const int aggregate_damage_component =
                    _ratio(
                            policy.damage_weight,
                            capped_damage,
                            selected_target_hp) +
                    _ratio(
                            policy.success_rate_weight,
                            maximum_success,
                            100) +
                    _ratio(
                            policy.target_coverage_weight,
                            distinct_damaged_targets,
                            _active_opponent_count(actor, units)) +
                    _ratio(
                            policy.range_usage_weight,
                            maximum_range,
                            projection.max_action_range);
            _add_component(aggregate_damage_component, result);
        }

        for(std::size_t event_index = 0; event_index < event_count; ++event_index)
        {
            const std::uint8_t code = events[event_index].code();
            if((code == 0x12 &&
                    actor.statuses.find(0x12) != no_status_slot) ||
                    (code == 0x0D &&
                     actor.statuses.find(0x0D) != no_status_slot) ||
                    (code == 0x11 &&
                     ((projection.hp_after > projection.max_hp / 2 &&
                       projection.chakra_after >
                               projection.max_chakra / 2) ||
                      projection.actor_threatened_after)))
            {
                result.penalty =
                        policy.kind_5_effect_low_3_weights[0] +
                        policy.selected_kind_5_bias_weight;
                break;
            }
        }

        result.component_sum +=
                scenario_rule_components.component_sum;
        result.component_count +=
                scenario_rule_components.component_count;

        if(action_projection.selected &&
                ! projection.has_active_scenario_rule &&
                event_count > 0 &&
                events[0].code() == 0x07)
        {
            const bool selected_position_threatened =
                    events[0].position_mode_uses_actor ?
                    projection.actor_threatened_after :
                    events[0].target_position_threatened;
            if(! selected_position_threatened)
            {
                result.component_sum +=
                        effect_7_safe_position_bonus;
            }
        }

        result.random_term = _scaled_random(rng, policy.random_term_scale);
        const int mean = result.component_count > 0 ?
                (result.component_sum - result.penalty) /
                result.component_count : 0;
        result.score = mean + result.random_term;
        return result;
    }

private:
    static void _add_component(int value, ai_utility_score& result)
    {
        result.component_sum += value;
        ++result.component_count;
    }

    [[nodiscard]] static int _ratio(int weight, int numerator, int denominator)
    {
        if(weight == 0 || numerator <= 0 || denominator <= 0)
        {
            return 0;
        }
        if(numerator > denominator)
        {
            numerator = denominator;
        }
        return weight * numerator / denominator;
    }

    [[nodiscard]] static int _scaled_random(deterministic_rng& rng, int scale)
    {
        return scale > 0 ? (rng.next_u15() * scale) >> 15 : 0;
    }

    template<std::size_t UnitCount>
    [[nodiscard]] static std::size_t _find_unit_slot(
            const std::array<battle_unit_instance, UnitCount>& units,
            battle_unit_id id)
    {
        for(std::size_t index = 0; index < UnitCount; ++index)
        {
            if(units[index].id == id)
            {
                return index;
            }
        }
        return UnitCount;
    }

    template<std::size_t UnitCount, std::size_t EventCapacity>
    [[nodiscard]] static int _target_selector_component(
            const std::array<battle_unit_instance, UnitCount>& units,
            const ai_target_bank& bank,
            const std::array<ai_queued_event, EventCapacity>& events,
            std::size_t event_count,
            const std::array<int, ai_target_selector_count>& weights)
    {
        int result = 0;
        for(std::size_t selector = 0;
                selector < ai_target_selector_count;
                ++selector)
        {
            const battle_unit_id indexed_unit = bank.units[selector];
            const std::size_t target_slot =
                    _find_unit_slot(units, indexed_unit);
            if(target_slot == UnitCount)
            {
                continue;
            }
            const battle_unit_instance& target = units[target_slot];
            for(std::size_t event_index = 0;
                    event_index < event_count;
                    ++event_index)
            {
                const ai_queued_event& event = events[event_index];
                if(event.target_id == indexed_unit &&
                        ai_status_aware_score_policy::event_contributes(
                                target,
                                event))
                {
                    result += weights[selector];
                    break;
                }
            }
        }
        return result;
    }

    template<std::size_t UnitCount>
    [[nodiscard]] static int _active_opponent_count(
            const battle_unit_instance& actor,
            const std::array<battle_unit_instance, UnitCount>& units)
    {
        int result = 0;
        for(const battle_unit_instance& unit : units)
        {
            result += unit.active && unit.side != actor.side;
        }
        return result;
    }
};

}

#endif
