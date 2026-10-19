#include "konoha/battle_action_combinations.h"
#include "konoha/generated_battle_action_content.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        grid_point position)
{
    battle_unit_instance result = {
        id,
        side,
        side == battle_side::player ?
                battle_control::player :
                battle_control::ai,
        position,
        battle_facing::down,
        500,
        500,
        9,
        9,
        5,
        true,
        {},
    };
    result.attack = 50;
    result.defense = 10;
    result.agility = 20;
    return result;
}

battle_session<2> session_with_adjacent_enemy(
        int chakra = 9,
        ninja_tool_id tool_id = no_ninja_tool)
{
    battle_session<2> session;
    battle_unit_instance source = unit(
            1, battle_side::player, { 2, 2 });
    source.chakra = chakra;
    source.equipped_tools[0] = tool_id;
    assert(session.add_unit(source));
    assert(session.add_unit(unit(
            2, battle_side::enemy, { 3, 2 })));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);
    return session;
}

[[nodiscard]] battle_combination_action compose_active_pair(
        ability_id first,
        ability_id second)
{
    return battle_action_combinations::compose(
            { battle_action_component_kind::active_action,
              first,
              no_tool_slot },
            active_action_definitions[first],
            { battle_action_component_kind::active_action,
              second,
              no_tool_slot },
            active_action_definitions[second]);
}

void assert_special_pair_resolves(
        ability_id first,
        ability_id second,
        ability_id expected_result,
        int expected_hits,
        int expected_chakra)
{
    battle_session<2> session =
            session_with_adjacent_enemy();
    const battle_combination_action combination =
            compose_active_pair(first, second);
    assert(combination.valid());
    assert(combination.special());
    assert(combination.result.id == expected_result);
    const action_preview preview =
            battle_action_combinations::preview(
                    session, combination, { 3, 2 });
    assert(preview.legal());
    assert(preview.hit_count == expected_hits);
    deterministic_rng rng(
            static_cast<std::uint32_t>(
                    first * 31 + second));
    const action_result result =
            battle_action_combinations::resolve(
                    session,
                    combination,
                    { 3, 2 },
                    rng);
    assert(result.success());
    assert(result.generated_hits == expected_hits);
    assert(session.unit(1)->chakra == expected_chakra);
    assert(session.unit(1)->ledger.acted);
    assert(session.lifecycle() ==
           battle_lifecycle::effects_resolved);
}

}

int main()
{
    assert(battle_action_combinations::recipes.size() == 5);
    for(const ability_id action_id :
            std::array<ability_id, 6>{ 9, 12, 14, 16, 25, 29 })
    {
        assert(battle_action_combinations::can_start(
                {
                    battle_action_component_kind::active_action,
                    action_id,
                    no_tool_slot,
                },
                active_action_definitions[action_id]));
    }
    for(const ability_id action_id :
            std::array<ability_id, 4>{ 9, 14, 25, 29 })
    {
        assert(battle_action_combinations::requires_follow(
                {
                    battle_action_component_kind::active_action,
                    action_id,
                    no_tool_slot,
                },
                active_action_definitions[action_id]));
    }
    for(const ability_id action_id :
            std::array<ability_id, 2>{ 12, 16 })
    {
        assert(! battle_action_combinations::requires_follow(
                {
                    battle_action_component_kind::active_action,
                    action_id,
                    no_tool_slot,
                },
                active_action_definitions[action_id]));
    }
    assert(battle_action_combinations::result_for(
                   { battle_action_component_kind::active_action,
                     9,
                     no_tool_slot },
                   { battle_action_component_kind::active_action,
                     8,
                     no_tool_slot }) == 10);
    assert(battle_action_combinations::result_for(
                   { battle_action_component_kind::active_action,
                     9,
                     no_tool_slot },
                   { battle_action_component_kind::active_action,
                     5,
                     no_tool_slot }) == 11);
    assert(battle_action_combinations::result_for(
                   { battle_action_component_kind::active_action,
                     12,
                     no_tool_slot },
                   { battle_action_component_kind::active_action,
                     12,
                     no_tool_slot }) == 13);
    assert(battle_action_combinations::result_for(
                   { battle_action_component_kind::active_action,
                     16,
                     no_tool_slot },
                   { battle_action_component_kind::active_action,
                     16,
                     no_tool_slot }) == 17);
    assert(battle_action_combinations::result_for(
                   { battle_action_component_kind::active_action,
                     16,
                     no_tool_slot },
                   { battle_action_component_kind::ninja_tool,
                     1,
                     0 }) == 18);
    assert(battle_action_combinations::result_for(
                   { battle_action_component_kind::ninja_tool,
                     1,
                     0 },
                   { battle_action_component_kind::active_action,
                     16,
                     no_tool_slot }) == no_ability);
    assert(battle_action_combinations::result_for(
                   { battle_action_component_kind::active_action,
                     16,
                     no_tool_slot },
                   { battle_action_component_kind::ninja_tool,
                     18,
                     0 }) == no_ability);

    battle_session<2> naruto = session_with_adjacent_enemy();
    const battle_combination_action naruto_combo =
            battle_action_combinations::compose(
                    { battle_action_component_kind::active_action,
                      9,
                      no_tool_slot },
                    active_action_definitions[9],
                    { battle_action_component_kind::active_action,
                      5,
                      no_tool_slot },
                    active_action_definitions[5]);
    assert(naruto_combo.valid());
    assert(naruto_combo.result.id == 11);
    assert(naruto_combo.result.range.maximum_distance() == 1);
    const action_preview naruto_preview =
            battle_action_combinations::preview(
                    naruto, naruto_combo, { 3, 2 });
    assert(naruto_preview.legal());
    assert(naruto_preview.scalar_cost == 5);
    deterministic_rng naruto_rng(7);
    const action_result naruto_result =
            battle_action_combinations::resolve(
                    naruto,
                    naruto_combo,
                    { 3, 2 },
                    naruto_rng);
    assert(naruto_result.success());
    assert(naruto.unit(1)->chakra == 4);
    assert(naruto.unit(1)->ledger.acted);
    assert(naruto.lifecycle() ==
           battle_lifecycle::effects_resolved);

    assert_special_pair_resolves(9, 8, 10, 5, 3);
    assert_special_pair_resolves(12, 12, 13, 2, 5);
    assert_special_pair_resolves(16, 16, 17, 1, 5);

    battle_session<2> insufficient =
            session_with_adjacent_enemy(3);
    const battle_combination_action double_fire =
            battle_action_combinations::compose(
                    { battle_action_component_kind::active_action,
                      16,
                      no_tool_slot },
                    active_action_definitions[16],
                    { battle_action_component_kind::active_action,
                      16,
                      no_tool_slot },
                    active_action_definitions[16]);
    assert(double_fire.valid());
    assert(double_fire.result.id == 17);
    assert(battle_action_combinations::preview(
                   insufficient,
                   double_fire,
                   { 3, 2 }).error ==
           action_error::insufficient_chakra);

    battle_session<2> tool_combo =
            session_with_adjacent_enemy(9, 1);
    const battle_combination_action phoenix_fire =
            battle_action_combinations::compose(
                    { battle_action_component_kind::active_action,
                      16,
                      no_tool_slot },
                    active_action_definitions[16],
                    { battle_action_component_kind::ninja_tool,
                      1,
                      0 },
                    ninja_tool_action_for_slot(1, 0));
    assert(phoenix_fire.valid());
    assert(phoenix_fire.result.id == 18);
    deterministic_rng tool_rng(11);
    const action_result phoenix_result =
            battle_action_combinations::resolve(
                    tool_combo,
                    phoenix_fire,
                    { 3, 2 },
                    tool_rng);
    assert(phoenix_result.success());
    assert(tool_combo.unit(1)->chakra == 7);
    assert(tool_combo.unit(1)->equipped_tools[0] ==
           no_ninja_tool);

    battle_session<2> multi_tool_session =
            session_with_adjacent_enemy(9, 18);
    const battle_combination_action multi_tool =
            battle_action_combinations::compose(
                    { battle_action_component_kind::active_action,
                      9,
                      no_tool_slot },
                    active_action_definitions[9],
                    { battle_action_component_kind::ninja_tool,
                      18,
                      0 },
                    ninja_tool_action_for_slot(18, 0));
    assert(multi_tool.valid());
    assert(! multi_tool.special());
    assert(multi_tool.result.id == no_ability);
    const action_preview multi_tool_preview =
            battle_action_combinations::preview(
                    multi_tool_session,
                    multi_tool,
                    { 3, 2 });
    assert(multi_tool_preview.legal());
    assert(multi_tool_preview.hit_count == 2);
    assert(multi_tool_preview.scalar_cost == 5);
    deterministic_rng multi_tool_rng(19);
    const action_result multi_tool_result =
            battle_action_combinations::resolve(
                    multi_tool_session,
                    multi_tool,
                    { 3, 2 },
                    multi_tool_rng);
    assert(multi_tool_result.success());
    assert(multi_tool_result.generated_hits == 2);
    assert(multi_tool_session.unit(1)->chakra == 4);
    assert(multi_tool_session.unit(1)->equipped_tools[0] ==
           no_ninja_tool);

    battle_session<2> generic_pair_session =
            session_with_adjacent_enemy();
    const battle_combination_action generic_pair =
            compose_active_pair(16, 5);
    assert(generic_pair.valid());
    assert(! generic_pair.special());
    const action_preview generic_pair_preview =
            battle_action_combinations::preview(
                    generic_pair_session,
                    generic_pair,
                    { 3, 2 });
    assert(generic_pair_preview.legal());
    assert(generic_pair_preview.hit_count == 2);
    deterministic_rng generic_pair_rng(23);
    const action_result generic_pair_result =
            battle_action_combinations::resolve(
                    generic_pair_session,
                    generic_pair,
                    { 3, 2 },
                    generic_pair_rng);
    assert(generic_pair_result.success());
    assert(generic_pair_result.generated_hits == 2);
    assert(generic_pair_session.unit(1)->chakra == 7);
    assert(generic_pair_session.unit(1)->ledger.acted);
    assert(generic_pair_session.lifecycle() ==
           battle_lifecycle::effects_resolved);

    const battle_combination_action forced_buff_pair =
            compose_active_pair(14, 5);
    assert(forced_buff_pair.valid());
    assert(! forced_buff_pair.special());
    const action_definition forced_buff_planning =
            battle_action_combinations::planning_action(
                    forced_buff_pair);
    assert(forced_buff_planning.id == 5);
    assert(forced_buff_planning.effect.potency == 12);
    battle_session<2> forced_buff_session =
            session_with_adjacent_enemy();
    const int forced_buff_enemy_hp =
            forced_buff_session.unit(2)->hp;
    const action_preview forced_buff_preview =
            battle_action_combinations::preview(
                    forced_buff_session,
                    forced_buff_pair,
                    { 3, 2 });
    assert(forced_buff_preview.legal());
    assert(forced_buff_preview.scalar_cost == 2);
    assert(forced_buff_preview.total_damage > 0);
    deterministic_rng forced_buff_rng(29);
    const action_result forced_buff_result =
            battle_action_combinations::resolve(
                    forced_buff_session,
                    forced_buff_pair,
                    { 3, 2 },
                    forced_buff_rng);
    assert(forced_buff_result.success());
    assert(forced_buff_result.applied_status_count == 1);
    assert(forced_buff_session.unit(1)->
                   statuses.find(0x1E) !=
           no_status_slot);
    assert(forced_buff_session.unit(1)->chakra == 7);
    assert(forced_buff_session.unit(2)->hp <
           forced_buff_enemy_hp);
    assert(forced_buff_session.unit(1)->ledger.acted);

    assert(! compose_active_pair(5, 16).valid());
    assert(! compose_active_pair(16, 2).valid());
}
