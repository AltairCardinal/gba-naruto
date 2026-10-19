#include "konoha/battle_ai_turn_flow.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/generated_battle_scenario_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <cassert>

using namespace konoha;

namespace
{

template<int Width, int Height, std::size_t MaxUnits>
grid_map<Width, Height> occupied_map(
        const battle_session<MaxUnits>& session)
{
    grid_map<Width, Height> result;
    for(std::size_t index = 0;
            index < session.unit_count();
            ++index)
    {
        const battle_unit_instance* unit =
                session.unit_at(index);
        if(unit && unit->active)
        {
            assert(result.set_occupied(
                    unit->position, true));
        }
    }
    return result;
}

int distance(grid_point first, grid_point second)
{
    const int dx = first.x > second.x ?
            first.x - second.x : second.x - first.x;
    const int dy = first.y > second.y ?
            first.y - second.y : second.y - first.y;
    return dx + dy;
}

battle_session<2> tool_session()
{
    battle_unit_instance naruto = instantiate_unit(
            unit_definitions[1],
            1,
            battle_side::player,
            battle_control::ai,
            { 1, 1 },
            battle_facing::right,
            1);
    naruto.move_range = 0;
    naruto.base_move_range = 0;
    naruto.equipped_tools[2] = 1;
    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::player,
            { 3, 1 },
            battle_facing::left,
            1);
    battle_session<2> result;
    assert(result.add_unit(naruto));
    assert(result.add_unit(enemy));
    assert(result.start_round() ==
           battle_transition::unit_selection_opened);
    return result;
}

battle_session<2> resource_session(
        int hp,
        int chakra)
{
    battle_unit_instance actor = instantiate_unit(
            unit_definitions[1],
            1,
            battle_side::player,
            battle_control::ai,
            { 0, 0 },
            battle_facing::right,
            1);
    actor.hp = hp;
    actor.max_hp = 100;
    actor.base_max_hp = 100;
    actor.chakra = chakra;
    actor.max_chakra = 10;
    actor.hand_seals = 1;
    actor.move_range = 0;
    actor.base_move_range = 0;
    actor.primary_action_ids = {};
    actor.primary_action_levels = {};
    actor.equipped_tools = {};
    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::player,
            { 8, 8 },
            battle_facing::left,
            1);
    enemy.move_range = 0;
    battle_session<2> result;
    assert(result.add_unit(actor));
    assert(result.add_unit(enemy));
    assert(result.start_round() ==
           battle_transition::unit_selection_opened);
    return result;
}

battle_session<2> substitution_session()
{
    battle_unit_instance actor = instantiate_unit(
            unit_definitions[35],
            1,
            battle_side::player,
            battle_control::ai,
            { 2, 2 },
            battle_facing::right,
            1);
    actor.chakra = 5;
    actor.max_chakra = 5;
    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[1],
            2,
            battle_side::enemy,
            battle_control::player,
            { 3, 2 },
            battle_facing::left,
            1);
    battle_session<2> result;
    assert(result.add_unit(actor));
    assert(result.add_unit(enemy));
    assert(result.start_round() ==
           battle_transition::unit_selection_opened);
    return result;
}

battle_session<2> forced_combination_session()
{
    battle_unit_instance naruto = instantiate_unit(
            unit_definitions[1],
            1,
            battle_side::player,
            battle_control::ai,
            { 1, 1 },
            battle_facing::right,
            20);
    naruto.primary_action_ids = {};
    naruto.primary_action_levels = {};
    naruto.primary_action_ids[0] = 5;
    naruto.primary_action_levels[0] = 3;
    naruto.primary_action_ids[1] = 9;
    naruto.primary_action_levels[1] = 1;
    naruto.chakra = 9;
    naruto.max_chakra = 9;
    naruto.move_range = 0;
    naruto.base_move_range = 0;

    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::player,
            { 2, 1 },
            battle_facing::left,
            20);
    enemy.hp = 500;
    enemy.max_hp = 500;
    enemy.base_max_hp = 500;
    enemy.move_range = 0;
    enemy.base_move_range = 0;

    battle_session<2> result;
    assert(result.add_unit(naruto));
    assert(result.add_unit(enemy));
    assert(result.start_round() ==
           battle_transition::unit_selection_opened);
    return result;
}

battle_session<2> forced_tool_combination_session()
{
    battle_session<2> result =
            forced_combination_session();
    battle_unit_instance naruto = *result.unit(1);
    naruto.primary_action_ids = {};
    naruto.primary_action_levels = {};
    naruto.primary_action_ids[0] = 9;
    naruto.primary_action_levels[0] = 1;
    naruto.equipped_tools[0] = 18;

    battle_session<2> rebuilt;
    assert(rebuilt.add_unit(naruto));
    assert(rebuilt.add_unit(*result.unit(2)));
    assert(rebuilt.start_round() ==
           battle_transition::unit_selection_opened);
    return rebuilt;
}

battle_session<2> optional_combination_session()
{
    battle_unit_instance sasuke = instantiate_unit(
            unit_definitions[2],
            1,
            battle_side::player,
            battle_control::ai,
            { 1, 1 },
            battle_facing::right,
            20);
    sasuke.primary_action_ids = {};
    sasuke.primary_action_levels = {};
    sasuke.primary_action_ids[0] = 12;
    sasuke.primary_action_levels[0] = 1;
    sasuke.chakra = 9;
    sasuke.max_chakra = 9;
    sasuke.move_range = 0;
    sasuke.base_move_range = 0;

    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::player,
            { 2, 1 },
            battle_facing::left,
            20);
    enemy.hp = 500;
    enemy.max_hp = 500;
    enemy.base_max_hp = 500;
    enemy.move_range = 0;
    enemy.base_move_range = 0;

    battle_session<2> result;
    assert(result.add_unit(sasuke));
    assert(result.add_unit(enemy));
    assert(result.start_round() ==
           battle_transition::unit_selection_opened);
    return result;
}

battle_session<2> forced_buff_combination_session()
{
    battle_session<2> result =
            forced_combination_session();
    battle_unit_instance actor = *result.unit(1);
    actor.primary_action_ids = {};
    actor.primary_action_levels = {};
    actor.primary_action_ids[0] = 14;
    actor.primary_action_levels[0] = 1;
    actor.primary_action_ids[1] = 5;
    actor.primary_action_levels[1] = 1;
    actor.chakra = 99;
    actor.max_chakra = 99;

    battle_session<2> rebuilt;
    assert(rebuilt.add_unit(actor));
    battle_unit_instance enemy = *result.unit(2);
    enemy.hp = 50;
    enemy.max_hp = 50;
    enemy.base_max_hp = 50;
    assert(rebuilt.add_unit(enemy));
    assert(rebuilt.start_round() ==
           battle_transition::unit_selection_opened);
    return rebuilt;
}

battle_session<2> fully_loaded_sasuke_session()
{
    battle_unit_instance sasuke = instantiate_unit(
            unit_definitions[2],
            1,
            battle_side::player,
            battle_control::ai,
            { 1, 1 },
            battle_facing::right,
            99);
    sasuke.primary_action_ids = {};
    sasuke.primary_action_levels = {};
    constexpr std::array<ability_id, 11> actions = {
        1, 2, 3, 4, 5, 6, 12, 14, 15, 16, 19,
    };
    for(std::size_t index = 0;
            index < actions.size();
            ++index)
    {
        sasuke.primary_action_ids[index] = actions[index];
        sasuke.primary_action_levels[index] = 1;
    }
    for(std::size_t index = 0;
            index < sasuke.equipped_tools.size();
            ++index)
    {
        sasuke.equipped_tools[index] =
                static_cast<ninja_tool_id>(index + 1);
    }
    sasuke.chakra = 99;
    sasuke.max_chakra = 99;
    sasuke.move_range = 0;
    sasuke.base_move_range = 0;

    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::player,
            { 2, 1 },
            battle_facing::left,
            99);
    enemy.hp = 999;
    enemy.max_hp = 999;
    enemy.base_max_hp = 999;
    enemy.move_range = 0;
    enemy.base_move_range = 0;

    battle_session<2> result;
    assert(result.add_unit(sasuke));
    assert(result.add_unit(enemy));
    assert(result.start_round() ==
           battle_transition::unit_selection_opened);
    return result;
}

}

int main()
{
    battle_session<2> fully_loaded =
            fully_loaded_sasuke_session();
    deterministic_rng fully_loaded_rng(43);
    battle_ai_turn_workspace<2, 5, 5>
            fully_loaded_workspace;
    const battle_ai_turn_flow_result fully_loaded_result =
            battle_ai_turn_flow::execute(
                    fully_loaded,
                    occupied_map<5, 5>(fully_loaded),
                    1,
                    {
                        true,
                        fully_loaded.unit(2)->position,
                        2,
                        no_battle_unit,
                    },
                    {},
                    fully_loaded_rng,
                    fully_loaded_workspace);
    assert(fully_loaded_result.success());
    int fully_loaded_option_count = 0;
    for(const battle_ai_action_option_source& source :
            fully_loaded_workspace.action_sources)
    {
        if(source.browser_entry_index != 0xFF)
        {
            ++fully_loaded_option_count;
        }
    }
    // 18 selectable ordinary candidates plus 3 combination
    // starters times 12 selectable damage actions/tools.
    assert(fully_loaded_option_count == 54);

    battle_session<2> optional_combination =
            optional_combination_session();
    deterministic_rng optional_rng(31);
    const battle_ai_turn_flow_result optional =
            battle_ai_turn_flow::execute(
                    optional_combination,
                    occupied_map<5, 5>(
                            optional_combination),
                    1,
                    {
                        true,
                        optional_combination.unit(2)->
                                position,
                        2,
                        no_battle_unit,
                    },
                    {},
                    optional_rng);
    assert(optional.success());
    assert(optional.combination_resolved);
    assert(optional.combination_first_action_id == 12);
    assert(optional.combination_second_action_id == 12);
    assert(optional.combination_result_action_id == 13);
    assert(optional.action_id == 13);

    bool found_forced_buff_candidate = false;
    bool selected_forced_buff_candidate = false;
    for(std::uint32_t seed = 1;
            seed <= 256 &&
            ! selected_forced_buff_candidate;
            ++seed)
    {
        battle_session<2> forced_buff =
                forced_buff_combination_session();
        deterministic_rng forced_buff_rng(seed);
        battle_ai_turn_workspace<2, 5, 5>
                forced_buff_workspace;
        const battle_ai_turn_flow_result forced_buff_result =
                battle_ai_turn_flow::execute(
                        forced_buff,
                        occupied_map<5, 5>(forced_buff),
                        1,
                        {
                            true,
                            forced_buff.unit(2)->position,
                            2,
                            no_battle_unit,
                        },
                        {},
                        forced_buff_rng,
                        forced_buff_workspace);
        assert(forced_buff_result.success());
        for(std::size_t option_index = 0;
                option_index <
                        forced_buff_workspace.action_sources.size();
                ++option_index)
        {
            const battle_ai_action_option_source& source =
                    forced_buff_workspace.action_sources[
                            option_index];
            if(! source.combination() ||
                    source.first_component_entry_index >=
                            forced_buff_workspace.browser.count ||
                    source.browser_entry_index >=
                            forced_buff_workspace.browser.count)
            {
                continue;
            }
            const battle_action_browser_entry& first =
                    forced_buff_workspace.browser.entries[
                            source.first_component_entry_index];
            const battle_action_browser_entry& second =
                    forced_buff_workspace.browser.entries[
                            source.browser_entry_index];
            if(first.action_id == 14 &&
                    second.action_id == 5)
            {
                found_forced_buff_candidate = true;
                break;
            }
        }
        if(forced_buff_result.combination_resolved &&
                forced_buff_result.
                        combination_first_action_id == 14 &&
                forced_buff_result.
                        combination_second_action_id == 5)
        {
            selected_forced_buff_candidate = true;
        }
    }
    assert(found_forced_buff_candidate);
    assert(selected_forced_buff_candidate);

    battle_session<2> forced_combination =
            forced_combination_session();
    const int combination_enemy_hp_before =
            forced_combination.unit(2)->hp;
    deterministic_rng combination_rng(7);
    const battle_ai_turn_flow_result combined =
            battle_ai_turn_flow::execute(
                    forced_combination,
                    occupied_map<5, 5>(
                            forced_combination),
                    1,
                    {
                        true,
                        forced_combination.unit(2)->
                                position,
                        2,
                        no_battle_unit,
                    },
                    {},
                    combination_rng);
    assert(combined.success());
    assert(combined.action_resolved);
    assert(combined.combination_resolved);
    assert(combined.combination_first_action_id == 9);
    assert(combined.combination_second_action_id == 5);
    assert(combined.combination_result_action_id == 11);
    assert(combined.action_id == 11);
    assert(combined.impact_count ==
           active_action_definitions[11]
                   .effect.base_hit_count);
    assert(forced_combination.unit(1)->chakra == 4);
    assert(forced_combination.unit(2)->hp <
           combination_enemy_hp_before);
    assert(forced_combination.unit(1)->ledger.completed);

    battle_session<2> forced_tool_combination =
            forced_tool_combination_session();
    deterministic_rng tool_combination_rng(19);
    const battle_ai_turn_flow_result combined_tool =
            battle_ai_turn_flow::execute(
                    forced_tool_combination,
                    occupied_map<5, 5>(
                            forced_tool_combination),
                    1,
                    {
                        true,
                        forced_tool_combination.unit(2)->
                                position,
                        2,
                        no_battle_unit,
                    },
                    {},
                    tool_combination_rng);
    assert(combined_tool.success());
    assert(combined_tool.combination_resolved);
    assert(combined_tool.combination_first_action_id ==
           9);
    assert(combined_tool.combination_second_action_id ==
           18);
    assert(combined_tool.combination_result_action_id ==
           no_ability);
    assert(combined_tool.action_kind ==
           battle_action_source_kind::ninja_tool);
    assert(combined_tool.action_id == 18);
    assert(combined_tool.tool_slot == 0);
    assert(combined_tool.impact_count == 2);
    assert(forced_tool_combination.unit(1)->chakra == 4);
    assert(forced_tool_combination.unit(1)->
                   equipped_tools[0] == no_ninja_tool);

    battle_session<2> tools = tool_session();
    const int enemy_hp_before = tools.unit(2)->hp;
    const grid_map<5, 5> tool_map =
            occupied_map<5, 5>(tools);
    deterministic_rng tool_rng(7);
    const battle_ai_turn_flow_result used_tool =
            battle_ai_turn_flow::execute(
                    tools,
                    tool_map,
                    1,
                    {
                        true,
                        tools.unit(2)->position,
                        2,
                        no_battle_unit,
                    },
                    {},
                    tool_rng);
    assert(used_tool.success());
    assert(used_tool.action_resolved);
    assert(used_tool.plan.action ==
           ai_action::ability);
    assert(used_tool.action_kind ==
           battle_action_source_kind::ninja_tool);
    assert(used_tool.action_id == 1);
    assert(used_tool.tool_slot == 2);
    assert(used_tool.animation_family ==
           ninja_tool_action_definitions[1]
                   .presentation.animation_family);
    assert(used_tool.effect_code ==
           ninja_tool_action_definitions[1].effect.code);
    assert(used_tool.targets_opponent);
    assert(used_tool.target_id == 2);
    assert(tools.unit(1)->equipped_tools[2] ==
           no_ninja_tool);
    assert(tools.unit(2)->hp < enemy_hp_before);
    assert(tools.unit(1)->facing ==
           used_tool.plan.facing);
    assert(tools.unit(1)->ledger.completed);
    assert(tools.current_side() == battle_side::enemy);

    battle_session<2> substitution =
            substitution_session();
    deterministic_rng substitution_rng(19);
    const battle_ai_turn_flow_result
            substitution_turn =
                    battle_ai_turn_flow::execute(
                            substitution,
                            occupied_map<5, 5>(
                                    substitution),
                            1,
                            {
                                true,
                                substitution.unit(2)->
                                        position,
                                2,
                                no_battle_unit,
                            },
                            {},
                            substitution_rng);
    assert(substitution_turn.success());
    assert(substitution_turn.secondary_planned);
    assert(substitution_turn.defense_kind ==
           defense_action_kind::active_action);
    assert(substitution_turn.defense_action_id == 3);
    assert(substitution_turn.defense_tool_slot ==
           no_tool_slot);
    assert(substitution.unit(1)->ledger.defense_kind ==
           defense_action_kind::active_action);
    assert(substitution.unit(1)->ledger.defense_ability ==
           3);
    assert(substitution.unit(1)->chakra <= 2);
    assert(substitution.unit(1)->statuses.find(0x16) !=
           no_status_slot);
    assert(substitution.current_side() ==
           battle_side::enemy);

    battle_session<2> wrong_control = tool_session();
    battle_unit_instance player_actor =
            *wrong_control.unit(1);
    player_actor.control = battle_control::player;
    battle_session<2> invalid_session;
    assert(invalid_session.add_unit(player_actor));
    assert(invalid_session.add_unit(
            *wrong_control.unit(2)));
    assert(invalid_session.start_round() ==
           battle_transition::unit_selection_opened);
    const battle_session<2> before_invalid =
            invalid_session;
    deterministic_rng invalid_rng(99);
    deterministic_rng invalid_rng_control(99);
    const battle_ai_turn_flow_result invalid_actor =
            battle_ai_turn_flow::execute(
                    invalid_session,
                    occupied_map<5, 5>(
                            invalid_session),
                    1,
                    {},
                    {},
                    invalid_rng);
    assert(invalid_actor.error ==
           battle_ai_turn_flow_error::invalid_actor);

    battle_unit_instance blocked_ai_actor =
            *wrong_control.unit(1);
    assert(blocked_ai_actor.statuses.upsert({
        0x3F,
        0,
        encode_status_duration_ticks(2),
        0,
        2,
        0,
        0,
    }));
    battle_unit_instance available_player =
            *wrong_control.unit(2);
    available_player.id = 3;
    available_player.side = battle_side::player;
    available_player.control = battle_control::player;
    available_player.position = { 1, 2 };
    battle_session<3> blocked_ai_session;
    assert(blocked_ai_session.add_unit(blocked_ai_actor));
    assert(blocked_ai_session.add_unit(available_player));
    assert(blocked_ai_session.add_unit(
            *wrong_control.unit(2)));
    assert(blocked_ai_session.start_round() ==
           battle_transition::unit_selection_opened);
    const battle_session<3> before_blocked_ai =
            blocked_ai_session;
    deterministic_rng blocked_ai_rng(101);
    deterministic_rng blocked_ai_rng_control(101);
    const battle_ai_turn_flow_result blocked_ai =
            battle_ai_turn_flow::execute(
                    blocked_ai_session,
                    occupied_map<5, 5>(
                            blocked_ai_session),
                    1,
                    {},
                    {},
                    blocked_ai_rng);
    assert(blocked_ai.error ==
           battle_ai_turn_flow_error::invalid_actor);
    assert(blocked_ai_session == before_blocked_ai);
    assert(blocked_ai_rng.next_u15() ==
           blocked_ai_rng_control.next_u15());
    assert(invalid_session == before_invalid);
    assert(invalid_rng.next_u15() ==
           invalid_rng_control.next_u15());

    battle_session<2> invalid_condition_session =
            tool_session();
    const battle_session<2> before_bad_condition =
            invalid_condition_session;
    battle_condition_variant invalid_conditions;
    invalid_conditions.win[0] = {
        battle_condition_type::no_valid_unit_for_side,
        2,
        0,
        0,
    };
    deterministic_rng invalid_condition_rng(41);
    deterministic_rng invalid_condition_control(41);
    const battle_ai_turn_flow_result bad_condition =
            battle_ai_turn_flow::execute(
                    invalid_condition_session,
                    occupied_map<5, 5>(
                            invalid_condition_session),
                    1,
                    {
                        true,
                        invalid_condition_session.unit(2)->
                                position,
                        2,
                        no_battle_unit,
                    },
                    invalid_conditions,
                    invalid_condition_rng);
    assert(bad_condition.error ==
           battle_ai_turn_flow_error::
                   turn_flow_failed);
    assert(invalid_condition_session ==
           before_bad_condition);
    assert(invalid_condition_rng.next_u15() ==
           invalid_condition_control.next_u15());

    battle_session<2> lethal = tool_session();
    battle_unit_instance fragile_enemy =
            *lethal.unit(2);
    fragile_enemy.hp = 1;
    battle_session<2> lethal_session;
    assert(lethal_session.add_unit(
            *lethal.unit(1)));
    assert(lethal_session.add_unit(fragile_enemy));
    assert(lethal_session.start_round() ==
           battle_transition::unit_selection_opened);
    battle_condition_variant win_on_enemy_clear;
    win_on_enemy_clear.win[0] = {
        battle_condition_type::no_valid_unit_for_side,
        1,
        0,
        0,
    };
    deterministic_rng lethal_rng(7);
    const battle_ai_turn_flow_result won =
            battle_ai_turn_flow::execute(
                    lethal_session,
                    occupied_map<5, 5>(lethal_session),
                    1,
                    {
                        true,
                        fragile_enemy.position,
                        2,
                        no_battle_unit,
                    },
                    win_on_enemy_clear,
                    lethal_rng);
    assert(won.success());
    assert(won.turn.ends_battle);
    assert(won.turn.outcome ==
           battle_condition_outcome::win);
    assert(won.target_id == 2);
    assert(won.affected_unit_count == 1);
    assert(won.affected_unit_ids[0] == 2);
    assert(won.action_kind ==
           battle_action_source_kind::ninja_tool);
    assert(won.action_id == 1);
    assert(won.impact_count ==
           ninja_tool_action_definitions[1]
                   .effect.base_hit_count);
    assert(lethal_session.lifecycle() ==
           battle_lifecycle::effects_resolved);
    assert(! lethal_session.unit(1)->
                    ledger.completed);

    battle_session<2> replenish =
            resource_session(100, 0);
    deterministic_rng replenish_rng(101);
    const battle_ai_turn_flow_result replenished =
            battle_ai_turn_flow::execute(
                    replenish,
                    occupied_map<9, 9>(replenish),
                    1,
                    {},
                    {},
                    replenish_rng);
    assert(replenished.success());
    assert(replenished.plan.action ==
           ai_action::replenish_chakra);
    assert(replenished.resource_resolved);
    assert(replenished.resource_type ==
           battle_resource_command_type::
                   replenish_chakra);
    assert(replenished.resource_amount == 10);
    assert(replenished.resource_hp_delta == -10);
    assert(replenished.resource_chakra_delta == 10);
    assert(replenish.unit(1)->hp == 90);
    assert(replenish.unit(1)->chakra == 10);
    assert(replenish.unit(1)->ledger.completed);
    assert(replenish.current_side() ==
           battle_side::enemy);

    battle_session<2> resting =
            resource_session(10, 10);
    deterministic_rng rest_rng(102);
    const battle_ai_turn_flow_result rested =
            battle_ai_turn_flow::execute(
                    resting,
                    occupied_map<9, 9>(resting),
                    1,
                    {},
                    {},
                    rest_rng);
    assert(rested.success());
    assert(rested.plan.action == ai_action::rest);
    assert(rested.resource_resolved);
    assert(rested.resource_type ==
           battle_resource_command_type::rest);
    assert(rested.resource_amount == 1);
    assert(rested.resource_hp_delta == 20);
    assert(rested.resource_chakra_delta == 0);
    assert(resting.unit(1)->hp == 30);
    assert(resting.unit(1)->chakra == 10);
    assert(resting.unit(1)->ledger.completed);

    battle_session<2> rejected_resource =
            resource_session(10, 10);
    const battle_session<2>
            before_rejected_resource =
                    rejected_resource;
    battle_condition_variant invalid_resource_conditions;
    invalid_resource_conditions.win[0] = {
        battle_condition_type::no_valid_unit_for_side,
        2,
        0,
        0,
    };
    deterministic_rng rejected_resource_rng(102);
    deterministic_rng rejected_resource_control(102);
    const battle_ai_turn_flow_result
            rejected_resource_turn =
                    battle_ai_turn_flow::execute(
                            rejected_resource,
                            occupied_map<9, 9>(
                                    rejected_resource),
                            1,
                            {},
                            invalid_resource_conditions,
                            rejected_resource_rng);
    assert(rejected_resource_turn.error ==
           battle_ai_turn_flow_error::
                   turn_flow_failed);
    assert(rejected_resource ==
           before_rejected_resource);
    assert(rejected_resource_rng.next_u15() ==
           rejected_resource_control.next_u15());

    battle_scenario_load_policy fixed_pool;
    fixed_pool.preserve_empty_unit_slots = true;
    battle_session<12> scenario_43;
    assert(load_battle_scenario(
                   battle_scenario_definitions[43],
                   0,
                   fixed_pool,
                   scenario_43)
                   .error ==
           battle_scenario_load_error::none);
    assert(scenario_43.start_round() ==
           battle_transition::unit_selection_opened);
    assert(scenario_43.select_unit(1) ==
           battle_transition::action_draft_opened);
    assert(scenario_43.open_facing_selection() ==
           battle_transition::facing_selection_opened);
    assert(scenario_43.select_facing(
                   battle_facing::up) ==
           battle_transition::defense_selection_opened);
    assert(scenario_43.complete_action(no_ability) ==
           battle_transition::side_changed);
    const grid_point scenario_enemy_origin =
            scenario_43.unit(2)->position;
    deterministic_rng scenario_rng(17);
    battle_ai_turn_workspace<12, 9, 22> scenario_workspace;
    const battle_ai_turn_flow_result scenario_turn =
            battle_ai_turn_flow::execute(
                    scenario_43,
                    occupied_map<9, 22>(scenario_43),
                    2,
                    {
                        true,
                        scenario_43.unit(1)->position,
                        1,
                        no_battle_unit,
                    },
                    {},
                    scenario_rng,
                    scenario_workspace);
    assert(scenario_turn.success());
    assert(scenario_43.unit_count() == 12);
    assert(scenario_43.unit(2)->ledger.completed);
    assert(distance(
                   scenario_enemy_origin,
                   scenario_turn.plan.destination) <=
           unit_definitions[35].movement);
    assert(scenario_43.current_side() ==
           battle_side::enemy);
}
