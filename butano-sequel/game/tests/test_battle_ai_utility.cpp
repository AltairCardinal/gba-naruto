#include "konoha/battle_ai_utility.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        int hp,
        int max_hp,
        int chakra,
        int max_chakra)
{
    return {
        id,
        side,
        battle_control::ai,
        { 0, 0 },
        battle_facing::down,
        hp,
        max_hp,
        chakra,
        max_chakra,
        4,
        true,
        {},
    };
}

void add_status(battle_unit_instance& value, std::uint8_t code)
{
    assert(value.statuses.upsert({ code, 0, 2, 0, 0, 0, 0 }));
}

}

int main()
{
    static_assert(ai_utility_policies.size() == 8);
    const ai_utility_policy& zero_common_policy = ai_utility_policies[0];
    assert(zero_common_policy.base_weights == (std::array<int, 2>{ 0, 0 }));
    assert(zero_common_policy.actor_hp_gain_weight == 0);
    assert(zero_common_policy.actor_hp_survival_weight == 0);
    assert(zero_common_policy.actor_chakra_gain_weight == 0);
    assert(zero_common_policy.actor_chakra_retention_weight == 0);
    assert(zero_common_policy.selected_kind_1_bias_weight == 0);
    assert(zero_common_policy.selected_kind_5_bias_weight == 0);
    assert(zero_common_policy.selected_kind_4_bias_weight == 0);
    assert(zero_common_policy.no_action_candidate_kind_2_or_3_weight == 0);
    assert(zero_common_policy.no_action_other_candidate_kind_weight == 0);
    assert(zero_common_policy.kind_5_effect_low_3_weights ==
           (std::array<int, 8>{}));
    assert(zero_common_policy.hostile_target_selector_weights ==
           (std::array<int, ai_target_selector_count>{}));
    assert(zero_common_policy.friendly_target_selector_weights ==
           (std::array<int, ai_target_selector_count>{}));
    assert(zero_common_policy.damage_weight == 0);
    assert(zero_common_policy.success_rate_weight == 0);
    assert(zero_common_policy.target_coverage_weight == 0);
    assert(zero_common_policy.range_usage_weight == 0);
    assert(zero_common_policy.random_term_scale == 10);

    for(std::size_t config_id = 1;
            config_id < ai_utility_policies.size();
            ++config_id)
    {
        const ai_utility_policy& policy = ai_utility_policies[config_id];
        assert(policy.base_weights ==
               ai_utility_policy::standard().base_weights);
        assert(policy.actor_hp_gain_weight ==
               ai_utility_policy::standard().actor_hp_gain_weight);
        assert(policy.selected_kind_1_bias_weight == 8000);
        assert(policy.selected_kind_5_bias_weight == 5000);
        assert(policy.selected_kind_4_bias_weight == 2000);
        assert(policy.no_action_candidate_kind_2_or_3_weight == 8000);
        assert(policy.no_action_other_candidate_kind_weight == 3000);
        assert(policy.kind_5_effect_low_3_weights ==
               (std::array<int, 8>{
                   7000, 6000, 8000, 3000, 5000, 6000, 0, 0
               }));
        assert(policy.hostile_target_selector_weights ==
               ai_utility_policy::standard().
                       hostile_target_selector_weights);
        assert(policy.damage_weight ==
               ai_utility_policy::standard().damage_weight);
        assert(policy.random_term_scale == 10);
    }

    const ai_actor_projection unchanged_projection = {
        80, 80, 100, 5, 5, 10, 6
    };
    const ai_utility_score unchanged_projection_score =
            battle_ai_utility_scorer::score_actor_projection(
                    unchanged_projection,
                    ai_utility_policy::standard());
    assert(unchanged_projection_score.component_count == 2);
    assert(unchanged_projection_score.component_sum ==
           1000 + 2500 + 7000 + 500);

    const ai_actor_projection gain_projection = {
        40, 80, 100, 5, 9, 10, 6
    };
    const ai_utility_score gain_projection_score =
            battle_ai_utility_scorer::score_actor_projection(
                    gain_projection,
                    ai_utility_policy::standard());
    assert(gain_projection_score.component_count == 2);
    assert(gain_projection_score.component_sum ==
           1000 + 2500 + 1200 + 2400);

    const ai_actor_projection loss_projection = {
        80, 20, 100, 5, 2, 10, 6
    };
    const ai_utility_score loss_projection_score =
            battle_ai_utility_scorer::score_actor_projection(
                    loss_projection,
                    ai_utility_policy::standard());
    assert(loss_projection_score.component_count == 2);
    assert(loss_projection_score.component_sum ==
           1000 + 2500 + 1750 + 200);

    const ai_utility_score kind_1_projection_score =
            battle_ai_utility_scorer::score_action_projection(
                    { true, 1, 1, ai_candidate_kind::selected_action },
                    ai_utility_policy::standard());
    assert(kind_1_projection_score.component_count == 1);
    assert(kind_1_projection_score.component_sum == 8000);
    const ai_utility_score kind_5_projection_score =
            battle_ai_utility_scorer::score_action_projection(
                    { true, 5, 4, ai_candidate_kind::selected_action },
                    ai_utility_policy::standard());
    assert(kind_5_projection_score.component_count == 2);
    assert(kind_5_projection_score.component_sum == 5000 + 5000);
    ai_action_projection resource_projection = {};
    resource_projection.no_action_candidate_kind =
            ai_candidate_kind::replenish_chakra;
    const ai_utility_score replenish_projection_score =
            battle_ai_utility_scorer::score_action_projection(
                    resource_projection,
                    ai_utility_policy::standard());
    assert(replenish_projection_score.component_count == 1);
    assert(replenish_projection_score.component_sum == 8000);
    resource_projection.no_action_candidate_kind =
            ai_candidate_kind::rest;
    const ai_utility_score rest_projection_score =
            battle_ai_utility_scorer::score_action_projection(
                    resource_projection,
                    ai_utility_policy::standard());
    assert(rest_projection_score.component_count == 1);
    assert(rest_projection_score.component_sum == 8000);
    resource_projection.no_action_candidate_kind =
            ai_candidate_kind::move;
    const ai_utility_score move_projection_score =
            battle_ai_utility_scorer::score_action_projection(
                    resource_projection,
                    ai_utility_policy::standard());
    assert(move_projection_score.component_count == 1);
    assert(move_projection_score.component_sum == 3000);

    battle_unit_instance actor = unit(1, battle_side::enemy, 80, 100, 5, 10);
    battle_unit_instance hostile = unit(2, battle_side::player, 100, 100, 5, 10);
    battle_unit_instance other_hostile = unit(3, battle_side::player, 50, 50, 5, 10);
    battle_unit_instance friendly = unit(4, battle_side::enemy, 40, 100, 5, 10);
    std::array units = { actor, hostile, other_hostile, friendly };

    assert(ai_status_aware_score_policy::event_contributes(hostile, { 5, 0x3F, 2 }));
    add_status(hostile, 0x3E);
    assert(! ai_status_aware_score_policy::event_contributes(hostile, { 5, 0x3F, 2 }));
    assert(! ai_status_aware_score_policy::event_contributes(hostile, { 5, 0x80, 2 }));
    assert(ai_status_aware_score_policy::event_contributes(hostile, { 5, 0x40, 2 }));
    add_status(hostile, 0x21);
    assert(! ai_status_aware_score_policy::event_contributes(hostile, { 5, 0x40, 2 }));

    battle_unit_instance same_family_target = unit(
            5, battle_side::player, 100, 100, 5, 10);
    add_status(same_family_target, 0x1E);
    assert(! ai_status_aware_score_policy::event_contributes(
            same_family_target, { 5, 0x1E, 5 }));
    assert(! ai_status_aware_score_policy::event_contributes(
            same_family_target, { 5, 0x26, 5 }));
    assert(ai_status_aware_score_policy::event_contributes(
            same_family_target, { 5, 0x20, 5 }));

    ai_target_index target_index;
    target_index.opposite_side.units.fill(hostile.id);
    target_index.same_side.units.fill(friendly.id);
    const std::array events = {
        ai_queued_event{ 5, 0x01, hostile.id, 20, 2, 80, 3 },
        ai_queued_event{ 5, 0x14, hostile.id, 10, 1, 60, 2 },
    };
    const ai_actor_projection projection = {
        actor.hp,
        actor.hp,
        actor.max_hp,
        actor.chakra,
        actor.chakra,
        actor.max_chakra,
        6,
    };
    deterministic_rng rng(7);
    const ai_utility_score score = battle_ai_utility_scorer::score(
            actor,
            projection,
            { true, 1, 1, ai_candidate_kind::selected_action },
            units,
            target_index,
            events,
            events.size(),
            ai_utility_policy::standard(),
            rng);

    // Actor projection contributes two components. Runtime kind 1 contributes
    // its bias and one aggregate damage component. Effect low 3 == 1 enables
    // one same-affiliation selector component; these hostile events do not
    // match it, but the zero component remains in the denominator.
    assert(score.component_count == 5);
    assert(score.component_sum ==
            1000 + 2500 + 7000 + 500 +
            8000 +
            (3000 + 720 + 1500 + 50));
    assert(score.random_term >= 0 && score.random_term <= 9);
    assert(score.score == score.component_sum / score.component_count + score.random_term);

    ai_utility_policy selector_only;
    selector_only.hostile_target_selector_weights.fill(100);
    selector_only.friendly_target_selector_weights.fill(200);
    selector_only.random_term_scale = 0;
    const std::array repeated_hostile_events = {
        ai_queued_event{ 9, 0x06, hostile.id, 0, 1, 100, 1 },
        ai_queued_event{ 9, 0x06, hostile.id, 0, 1, 100, 1 },
    };
    deterministic_rng friendly_rng(9);
    const ai_utility_score selector_score = battle_ai_utility_scorer::score(
            actor,
            projection,
            { true, 4, 2, ai_candidate_kind::selected_action },
            units,
            target_index,
            repeated_hostile_events,
            repeated_hostile_events.size(),
            selector_only,
            friendly_rng);
    assert(selector_score.component_sum == 7 * 100);
    assert(selector_score.component_count == 4);

    add_status(actor, 0x12);
    add_status(actor, 0x0D);
    ai_utility_policy penalty_policy =
            ai_utility_policy::standard();
    penalty_policy.random_term_scale = 0;
    const std::array penalty_event = {
        ai_queued_event{ 12, 0x12, hostile.id, 0, 1, 100, 1 },
        ai_queued_event{ 13, 0x0D, hostile.id, 0, 1, 100, 1 },
    };
    deterministic_rng penalty_rng(1);
    const ai_utility_score penalty_score = battle_ai_utility_scorer::score(
            actor,
            projection,
            { true, 4, 0, ai_candidate_kind::selected_action },
            units,
            target_index,
            penalty_event,
            penalty_event.size(),
            penalty_policy,
            penalty_rng);
    assert(penalty_score.penalty == 7000 + 5000);
    assert(penalty_score.component_count == 3);
    assert(penalty_score.score ==
           (penalty_score.component_sum -
            penalty_score.penalty) /
           penalty_score.component_count);

    const std::array restore_event = {
        ai_queued_event{ 28, 0x11, actor.id, 0, 1, 100, 0 },
    };
    ai_actor_projection low_resources = projection;
    low_resources.hp_after = low_resources.max_hp / 2;
    low_resources.chakra_after = low_resources.max_chakra;
    low_resources.actor_threatened_after = false;
    deterministic_rng safe_restore_rng(2);
    const ai_utility_score safe_restore_score =
            battle_ai_utility_scorer::score(
                    actor,
                    low_resources,
                    { true, 4, 0, ai_candidate_kind::selected_action },
                    units,
                    target_index,
                    restore_event,
                    restore_event.size(),
                    penalty_policy,
                    safe_restore_rng);
    assert(safe_restore_score.penalty == 0);

    low_resources.actor_threatened_after = true;
    deterministic_rng threatened_restore_rng(2);
    const ai_utility_score threatened_restore_score =
            battle_ai_utility_scorer::score(
                    actor,
                    low_resources,
                    { true, 4, 0, ai_candidate_kind::selected_action },
                    units,
                    target_index,
                    restore_event,
                    restore_event.size(),
                    penalty_policy,
                    threatened_restore_rng);
    assert(threatened_restore_score.penalty == 7000 + 5000);
    assert(threatened_restore_score.component_count ==
           safe_restore_score.component_count);

    low_resources.actor_threatened_after = false;
    low_resources.hp_after = low_resources.max_hp / 2 + 1;
    low_resources.chakra_after = low_resources.max_chakra / 2 + 1;
    deterministic_rng unnecessary_restore_rng(2);
    const ai_utility_score unnecessary_restore_score =
            battle_ai_utility_scorer::score(
                    actor,
                    low_resources,
                    { true, 4, 0, ai_candidate_kind::selected_action },
                    units,
                    target_index,
                    restore_event,
                    restore_event.size(),
                    penalty_policy,
                    unnecessary_restore_rng);
    assert(unnecessary_restore_score.penalty == 7000 + 5000);

    ai_actor_projection safe_summon_projection = projection;
    safe_summon_projection.has_active_scenario_rule = false;
    safe_summon_projection.actor_threatened_after = false;
    std::array summon_events = {
        ai_queued_event{ 7, 0x07, no_battle_unit, 0, 1, 100, 1 },
    };
    summon_events[0].target_position_threatened = false;
    summon_events[0].position_mode_uses_actor = false;
    deterministic_rng safe_summon_rng(4);
    const ai_utility_score safe_summon_score =
            battle_ai_utility_scorer::score(
                    actor,
                    safe_summon_projection,
                    { true, 1, 7, ai_candidate_kind::selected_action },
                    units,
                    target_index,
                    summon_events,
                    summon_events.size(),
                    penalty_policy,
                    safe_summon_rng);

    summon_events[0].target_position_threatened = true;
    deterministic_rng threatened_summon_rng(4);
    const ai_utility_score threatened_summon_score =
            battle_ai_utility_scorer::score(
                    actor,
                    safe_summon_projection,
                    { true, 1, 7, ai_candidate_kind::selected_action },
                    units,
                    target_index,
                    summon_events,
                    summon_events.size(),
                    penalty_policy,
                    threatened_summon_rng);
    assert(safe_summon_score.component_count ==
           threatened_summon_score.component_count);
    assert(safe_summon_score.component_sum ==
           threatened_summon_score.component_sum + 8000);

    summon_events[0].target_position_threatened = false;
    summon_events[0].position_mode_uses_actor = true;
    safe_summon_projection.actor_threatened_after = true;
    deterministic_rng actor_position_summon_rng(4);
    const ai_utility_score actor_position_summon_score =
            battle_ai_utility_scorer::score(
                    actor,
                    safe_summon_projection,
                    { true, 1, 7, ai_candidate_kind::selected_action },
                    units,
                    target_index,
                    summon_events,
                    summon_events.size(),
                    penalty_policy,
                    actor_position_summon_rng);
    assert(actor_position_summon_score.component_sum ==
           threatened_summon_score.component_sum);

    summon_events[0].position_mode_uses_actor = false;
    safe_summon_projection.actor_threatened_after = false;
    safe_summon_projection.has_active_scenario_rule = true;
    deterministic_rng ruled_summon_rng(4);
    const ai_utility_score ruled_summon_score =
            battle_ai_utility_scorer::score(
                    actor,
                    safe_summon_projection,
                    { true, 1, 7, ai_candidate_kind::selected_action },
                    units,
                    target_index,
                    summon_events,
                    summon_events.size(),
                    penalty_policy,
                    ruled_summon_rng);
    assert(ruled_summon_score.component_sum ==
           threatened_summon_score.component_sum);

    actor.status_mask = 2;
    deterministic_rng random_only_rng(3);
    const ai_utility_score random_only = battle_ai_utility_scorer::score(
            actor,
            projection,
            { true, 1, 1, ai_candidate_kind::selected_action },
            units,
            target_index,
            events,
            events.size(),
            ai_utility_policy::standard(),
            random_only_rng);
    assert(random_only.random_only);
    assert(random_only.score >= 0 && random_only.score <= 99);
    assert(random_only.component_count == 0);
}
