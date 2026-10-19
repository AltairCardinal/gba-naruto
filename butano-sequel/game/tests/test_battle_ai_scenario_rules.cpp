#include "konoha/battle_ai_scenario_rules.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        std::uint8_t character,
        grid_point position)
{
    battle_unit_instance result = {
        id,
        side,
        battle_control::ai,
        position,
        battle_facing::down,
        20,
        20,
        5,
        5,
        3,
        true,
        {},
    };
    result.character_id = character;
    return result;
}

}

int main()
{
    assert(ai_scenario_rule_configs.size() == 8);
    assert(ai_scenario_rule_configs[0].rules[0].kind == 0);
    assert(ai_scenario_rule_configs[2].rules[0] ==
            (ai_scenario_rule{ 1, 0, 10000 }));
    assert(ai_scenario_rule_configs[3].rules[0] ==
            (ai_scenario_rule{ 2, 31, 10000 }));
    assert(ai_scenario_rule_configs[3].rules[1] ==
            (ai_scenario_rule{ 3, 74, 10000 }));
    assert(ai_scenario_rule_configs[3].rules[2] ==
            (ai_scenario_rule{ 3, 75, 10000 }));
    assert(ai_scenario_rule_configs[7].rules[0] ==
            (ai_scenario_rule{ 4, 0, 10000 }));

    battle_unit_instance actor = unit(
            1, battle_side::enemy, 30, { 0, 0 });
    battle_unit_instance target = unit(
            2, battle_side::player, 31, { 3, 0 });
    std::array units = { actor, target };
    const std::array damage_event = {
        ai_queued_event{ 74, 0x01, target.id, 5, 1, 90, 2 },
    };

    ai_scenario_rule_context context;
    context.origin = actor.position;
    context.destination = { -1, 0 };
    context.move_range = 3;
    context.tile_flags = 0;
    context.tile_class = 6;
    context.tile_side = battle_side::enemy;
    context.active_side = battle_side::enemy;

    const auto kind_1_score =
            battle_ai_scenario_rule_scorer::score(
                    actor,
                    units,
                    damage_event,
                    damage_event.size(),
                    ai_scenario_rule_configs[2],
                    context);
    assert(kind_1_score.component_sum == 10000 + 10000 / 3);
    assert(kind_1_score.component_count == 2);

    std::array scenario_41_units = {
        unit(10, battle_side::enemy, 30, { 4, 4 }),
        unit(11, battle_side::player, 31, { 4, 10 }),
    };
    const std::array<ai_queued_event, 1> no_events = {};
    ai_scenario_rule_context scenario_41_context;
    scenario_41_context.origin = { 4, 4 };
    scenario_41_context.destination = { 6, 4 };
    scenario_41_context.move_range = 5;
    scenario_41_context.active_side =
            battle_side::enemy;
    scenario_41_context.battle_id = 41;
    const ai_utility_components scenario_41_kind_1_score =
            battle_ai_scenario_rule_scorer::score(
                    scenario_41_units[0],
                    scenario_41_units,
                    no_events,
                    0,
                    ai_scenario_rule_configs[2],
                    scenario_41_context);
    assert(scenario_41_kind_1_score.component_sum ==
           10000 + 2 * 10000 / 5);
    assert(scenario_41_kind_1_score.component_count == 2);

    scenario_41_context.destination = { 4, 5 };
    const ai_utility_components toward_opponent_kind_1_score =
            battle_ai_scenario_rule_scorer::score(
                    scenario_41_units[0],
                    scenario_41_units,
                    no_events,
                    0,
                    ai_scenario_rule_configs[2],
                    scenario_41_context);
    assert(toward_opponent_kind_1_score.component_sum ==
           10000);
    assert(toward_opponent_kind_1_score.component_count ==
           2);

    context.destination = { 1, 0 };
    const auto kinds_2_and_3_score =
            battle_ai_scenario_rule_scorer::score(
                    actor,
                    units,
                    damage_event,
                    damage_event.size(),
                    ai_scenario_rule_configs[3],
                    context);
    assert(kinds_2_and_3_score.component_sum ==
           10000 / 3 + 10000 + 10000);
    assert(kinds_2_and_3_score.component_count == 3);

    const auto kind_4_score =
            battle_ai_scenario_rule_scorer::score(
                    actor,
                    units,
                    damage_event,
                    damage_event.size(),
                    ai_scenario_rule_configs[7],
                    context);
    assert(kind_4_score.component_sum == 10000);
    assert(kind_4_score.component_count == 1);

    actor.ai_linked_unit = 0;
    const std::array summon_event = {
        ai_queued_event{ 20, 0x02, target.id, 0, 1, 100, 1 },
    };
    const auto kind_5_score =
            battle_ai_scenario_rule_scorer::score(
                    actor,
                    units,
                    summon_event,
                    summon_event.size(),
                    ai_scenario_rule_configs[5],
                    context);
    assert(kind_5_score.component_sum == 10000);
    assert(kind_5_score.component_count == 1);

    context.tile_flags = 1;
    context.destination = { 1, 0 };
    const auto zero_safe_component =
            battle_ai_scenario_rule_scorer::score(
                    actor,
                    units,
                    damage_event,
                    damage_event.size(),
                    ai_scenario_rule_configs[2],
                    context);
    assert(zero_safe_component.component_sum == 0);
    assert(zero_safe_component.component_count == 2);
}
