#include "konoha/battle_action_system.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        grid_point position,
        int hp)
{
    battle_unit_instance result = {
        id,
        side,
        side == battle_side::player ?
                battle_control::player : battle_control::ai,
        position,
        battle_facing::down,
        hp,
        hp,
        0,
        0,
        3,
        true,
        {},
    };
    result.attack = 19;
    result.defense = side == battle_side::enemy ? 14 : 0;
    result.agility = 10;
    return result;
}

action_definition one_hit_action(
        action_cost_kind cost_kind = action_cost_kind::current_hp)
{
    action_definition result;
    result.id = 1;
    result.cost = {
        cost_kind,
        0,
        static_cast<std::uint8_t>(
                cost_kind ==
                                action_cost_kind::
                                        battle_local_ninja_tool_slot ?
                        0 : no_tool_slot),
    };
    result.presentation = { 1 };
    result.effect = { 1, 0, 6, 1, 100, 0 };
    result.target = { target_policy_kind::opponent_unit, 0 };
    result.range = { 1, 1 };
    return result;
}

struct resolved_sample
{
    action_result result;
    int target_hp = 0;
    int next_rng_percent = 0;
};

resolved_sample resolve_sample(
        const battle_passive_state& passives,
        std::uint32_t seed,
        action_cost_kind cost_kind = action_cost_kind::current_hp)
{
    battle_unit_instance source =
            unit(1, battle_side::player, { 1, 1 }, 100);
    source.passives = passives;
    if(cost_kind ==
            action_cost_kind::battle_local_ninja_tool_slot)
    {
        source.equipped_tools[0] = 1;
    }
    battle_session<2> session;
    assert(session.add_unit(source));
    assert(session.add_unit(
            unit(2, battle_side::enemy, { 2, 1 }, 100)));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);

    const action_definition action = one_hit_action(cost_kind);
    const action_preview preview = battle_action_resolver::preview(
            session, 2, no_battle_unit, action, { 2, 1 });
    assert(preview.legal());
    assert(preview.damage_per_hit == 9);

    deterministic_rng rng(seed);
    const action_result result = battle_action_resolver::resolve_draft(
            session, 2, no_battle_unit, action, { 2, 1 }, rng);
    return { result, session.unit(2)->hp, rng.next_percent() };
}

int expected_next(std::uint32_t seed, int consumed)
{
    deterministic_rng rng(seed);
    for(int index = 0; index < consumed; ++index)
    {
        (void) rng.next_percent();
    }
    return rng.next_percent();
}

}

int main()
{
    battle_passive_state none;
    const resolved_sample ordinary = resolve_sample(none, 1);
    assert(ordinary.result.success());
    assert(ordinary.result.effective_hits == 1);
    assert(ordinary.result.total_damage == 9);
    assert(ordinary.target_hp == 91);
    assert(ordinary.result.damage_step_count == 1);
    assert(ordinary.result.damage_steps[0].hit_flags == 1);
    assert(ordinary.next_rng_percent == expected_next(1, 1));

    battle_passive_state critical_100;
    assert(critical_100.set_slot(0, 9, 17));
    const resolved_sample critical = resolve_sample(critical_100, 1);
    assert(critical.result.total_damage == 13);
    assert(critical.target_hp == 87);
    assert(critical.result.damage_steps[0].hit_flags == 2);
    assert(critical.next_rng_percent == expected_next(1, 2));

    battle_passive_state ignore_100;
    assert(ignore_100.set_slot(0, 20, 17));
    const resolved_sample ignored = resolve_sample(ignore_100, 1);
    assert(ignored.result.total_damage == 11);
    assert(ignored.target_hp == 89);
    assert(ignored.result.damage_steps[0].hit_flags == 5);
    assert(ignored.next_rng_percent == expected_next(1, 2));

    battle_passive_state both_100;
    assert(both_100.set_slot(0, 9, 17));
    assert(both_100.set_slot(1, 20, 17));
    const resolved_sample strongest = resolve_sample(both_100, 1);
    assert(strongest.result.total_damage == 16);
    assert(strongest.target_hp == 84);
    assert(strongest.result.damage_steps[0].hit_flags == 6);
    assert(strongest.next_rng_percent == expected_next(1, 3));

    // Seed 8 yields battle percentages [23, 0, 29, ...]. With both level-1 passives
    // (20% each), critical must consume the second value and ignore-defense
    // the third. Reversing the ROM order would produce flag 5 instead.
    battle_passive_state ordered;
    assert(ordered.set_slot(0, 9, 1));
    assert(ordered.set_slot(1, 20, 1));
    const resolved_sample ordered_result = resolve_sample(ordered, 8);
    assert(ordered_result.result.damage_steps[0].hit_flags == 2);
    assert(ordered_result.result.total_damage == 13);
    assert(ordered_result.next_rng_percent == expected_next(8, 3));

    battle_passive_state melee_continuation_100;
    assert(melee_continuation_100.set_slot(0, 17, 19));
    const resolved_sample melee_continuation =
            resolve_sample(melee_continuation_100, 1);
    assert(melee_continuation.result.generated_hits == 2);
    assert(melee_continuation.result.effective_hits == 2);
    assert(melee_continuation.result.total_damage == 18);
    assert(melee_continuation.target_hp == 82);
    assert(melee_continuation.result.damage_step_count == 2);
    assert(melee_continuation.result.damage_steps[0].hit_flags == 1);
    assert(melee_continuation.result.damage_steps[1].hit_flags == 1);
    assert(melee_continuation.next_rng_percent == expected_next(1, 3));

    battle_passive_state ninjutsu_continuation_100;
    assert(ninjutsu_continuation_100.set_slot(0, 18, 19));
    const resolved_sample ninjutsu_continuation =
            resolve_sample(
                    ninjutsu_continuation_100,
                    1,
                    action_cost_kind::current_chakra);
    assert(ninjutsu_continuation.result.generated_hits == 2);
    assert(ninjutsu_continuation.result.total_damage == 18);
    assert(ninjutsu_continuation.next_rng_percent ==
           expected_next(1, 3));

    battle_passive_state tool_continuation_100;
    assert(tool_continuation_100.set_slot(0, 19, 19));
    const resolved_sample tool_continuation =
            resolve_sample(
                    tool_continuation_100,
                    1,
                    action_cost_kind::battle_local_ninja_tool_slot);
    assert(tool_continuation.result.generated_hits == 2);
    assert(tool_continuation.result.total_damage == 18);
    assert(tool_continuation.next_rng_percent == expected_next(1, 3));

    const resolved_sample wrong_category =
            resolve_sample(
                    melee_continuation_100,
                    1,
                    action_cost_kind::current_chakra);
    assert(wrong_category.result.generated_hits == 1);
    assert(wrong_category.result.total_damage == 9);
    assert(wrong_category.next_rng_percent == expected_next(1, 1));

    battle_passive_state complete_chain;
    assert(complete_chain.set_slot(0, 17, 19));
    assert(complete_chain.set_slot(1, 9, 17));
    assert(complete_chain.set_slot(2, 20, 17));
    const resolved_sample chained = resolve_sample(complete_chain, 1);
    assert(chained.result.generated_hits == 2);
    assert(chained.result.effective_hits == 2);
    assert(chained.result.total_damage == 32);
    assert(chained.result.damage_step_count == 2);
    assert(chained.result.damage_steps[0].hit_flags == 6);
    assert(chained.result.damage_steps[1].hit_flags == 6);
    assert(chained.next_rng_percent == expected_next(1, 7));

    battle_unit_instance area_source =
            unit(10, battle_side::player, { 0, 0 }, 100);
    area_source.passives = melee_continuation_100;
    battle_session<3> area_session;
    assert(area_session.add_unit(area_source));
    assert(area_session.add_unit(
            unit(11, battle_side::enemy, { 2, 1 }, 100)));
    assert(area_session.add_unit(
            unit(12, battle_side::enemy, { 2, 2 }, 100)));
    assert(area_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(area_session.select_unit(10) ==
           battle_transition::action_draft_opened);
    action_definition area_action = one_hit_action();
    area_action.id = 2;
    area_action.range = { 3, 2 };
    deterministic_rng area_rng(1);
    const action_result area = battle_action_resolver::resolve_area_draft(
            area_session, area_action, { 2, 1 }, area_rng);
    assert(area.success());
    assert(area.target_count == 2);
    assert(area.generated_hits == 4);
    assert(area.effective_hits == 4);
    assert(area.total_damage == 36);
    assert(area_session.unit(11)->hp == 82);
    assert(area_session.unit(12)->hp == 82);
    assert(area_rng.next_percent() == expected_next(1, 5));
}
