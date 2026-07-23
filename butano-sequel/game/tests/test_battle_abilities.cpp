#include "konoha/battle_abilities.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id, battle_side side, grid_point position, int hp, int chakra)
{
    return {
        id,
        side,
        side == battle_side::player ? battle_control::player : battle_control::ai,
        position,
        battle_facing::down,
        hp,
        hp,
        chakra,
        chakra,
        3,
        true,
        {},
    };
}

ability_definition<4> combo_ability()
{
    ability_definition<4> result;
    result.id = 1;
    result.target = target_rule::enemy_unit;
    result.minimum_range = 1;
    result.maximum_range = 1;
    result.cost.chakra = 3;
    result.effects[0] = { effect_node_kind::damage, 7, 0 };
    result.effects[1] = { effect_node_kind::damage, 9, 0 };
    result.effect_count = 2;
    return result;
}

}

int main()
{
    battle_unit_instance source = unit(1, battle_side::player, { 2, 2 }, 30, 8);
    battle_unit_instance target = unit(2, battle_side::enemy, { 3, 2 }, 40, 0);
    const ability_definition<4> combo = combo_ability();

    const ability_preview preview = ability_resolver::preview(source, &target, nullptr, combo, { 3, 2 });
    assert(preview.legal());
    assert(preview.chakra_cost == 3);
    assert(preview.damage == 16);

    deterministic_rng rng(7);
    const ability_result resolved =
            ability_resolver::resolve(source, &target, nullptr, combo, { 3, 2 }, rng);
    assert(resolved.success());
    assert(resolved.applied_effects == 2);
    assert(source.chakra == 5);
    assert(source.ledger.acted);
    assert(target.hp == 24);

    battle_unit_instance exhausted = unit(3, battle_side::player, { 2, 2 }, 30, 2);
    battle_unit_instance untouched = unit(4, battle_side::enemy, { 3, 2 }, 40, 0);
    const battle_unit_instance exhausted_before = exhausted;
    const battle_unit_instance untouched_before = untouched;
    const ability_result rejected =
            ability_resolver::resolve(exhausted, &untouched, nullptr, combo, { 3, 2 }, rng);
    assert(rejected.error == ability_error::insufficient_chakra);
    assert(exhausted == exhausted_before);
    assert(untouched == untouched_before);

    ability_definition<4> summon;
    summon.id = 2;
    summon.target = target_rule::empty_tile;
    summon.maximum_range = 2;
    summon.effects[0] = { effect_node_kind::summon, 0, 0 };
    summon.effect_count = 1;
    battle_unit_instance summoner = unit(7, battle_side::player, { 2, 2 }, 30, 8);
    battle_unit_instance clone = unit(5, battle_side::player, { 0, 0 }, 10, 0);
    clone.active = false;
    const ability_result summoned =
            ability_resolver::resolve(summoner, nullptr, &clone, summon, { 2, 3 }, rng);
    assert(summoned.success() && summoned.summoned);
    assert(clone.active);
    assert((clone.position == grid_point{ 2, 3 }));
    assert(clone.summoner == summoner.id);

    battle_unit_instance substitute_target = unit(6, battle_side::enemy, { 3, 2 }, 20, 0);
    substitute_target.substitution_ready = true;
    battle_unit_instance second_source = unit(8, battle_side::player, { 2, 2 }, 30, 8);
    const ability_result substituted = ability_resolver::resolve(
            second_source, &substitute_target, nullptr, combo, { 3, 2 }, rng);
    assert(substituted.success() && substituted.substituted);
    assert(substitute_target.hp == 20);
    assert(! substitute_target.substitution_ready);

    ability_definition<1> malformed_empty_damage;
    malformed_empty_damage.id = 9;
    malformed_empty_damage.target = target_rule::empty_tile;
    malformed_empty_damage.effects[0] = { effect_node_kind::damage, 1, 0 };
    malformed_empty_damage.effect_count = 1;
    assert(ability_resolver::preview(
                   second_source,
                   nullptr,
                   &clone,
                   malformed_empty_damage,
                   { 2, 3 }).error == ability_error::invalid_definition);

    ability_definition<4> missing_summon_slot = combo_ability();
    missing_summon_slot.effects[1] = { effect_node_kind::summon, 0, 0 };
    missing_summon_slot.effect_count = 2;
    battle_unit_instance third_source = unit(9, battle_side::player, { 2, 2 }, 30, 8);
    assert(ability_resolver::preview(
                   third_source,
                   &target,
                   nullptr,
                   missing_summon_slot,
                   target.position).error == ability_error::summon_slot_unavailable);
}
