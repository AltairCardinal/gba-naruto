#include "konoha/battle_action_system.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        grid_point position,
        int hp,
        int max_hp,
        int chakra)
{
    battle_unit_instance result = {
        id,
        side,
        battle_control::player,
        position,
        battle_facing::down,
        hp,
        max_hp,
        chakra,
        chakra,
        3,
        true,
        {},
    };
    result.attack = 10;
    return result;
}

}

int main()
{
    battle_session<4> healing_session;
    assert(healing_session.add_unit(unit(
            1, battle_side::player, { 0, 0 }, 100, 100, 5)));
    assert(healing_session.add_unit(unit(
            2, battle_side::player, { 2, 1 }, 50, 100, 0)));
    assert(healing_session.add_unit(unit(
            3, battle_side::player, { 2, 2 }, 80, 100, 0)));
    assert(healing_session.add_unit(unit(
            4, battle_side::enemy, { 3, 1 }, 40, 100, 0)));
    assert(healing_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(healing_session.select_unit(1) ==
           battle_transition::action_draft_opened);

    const action_definition area_heal = {
        90,
        { action_cost_kind::current_chakra, 2, no_tool_slot },
        {},
        { 0x1A, 0, 30, 1, 100, 0 },
        { target_policy_kind::friendly_unit_policy_1, 0 },
        { 3, 2 },
        {},
    };
    const action_preview healing_preview =
            battle_action_resolver::preview_area(
                    healing_session, area_heal, { 2, 1 });
    assert(healing_preview.legal());
    assert(healing_preview.target_count == 2);
    assert(healing_preview.total_healing == 50);
    assert(healing_session.unit(1)->chakra == 5);
    assert(healing_session.unit(2)->hp == 50);
    assert(healing_session.unit(3)->hp == 80);

    deterministic_rng healing_rng(3);
    const action_result healing_result =
            battle_action_resolver::resolve_area_draft(
                    healing_session,
                    area_heal,
                    { 2, 1 },
                    healing_rng);
    assert(healing_result.success());
    assert(healing_result.target_count == 2);
    assert(healing_result.affected_unit_count == 2);
    assert(healing_result.affected_unit_ids[0] == 2);
    assert(healing_result.affected_unit_ids[1] == 3);
    assert(healing_result.total_healing == 50);
    assert(healing_session.unit(1)->chakra == 3);
    assert(healing_session.unit(2)->hp == 80);
    assert(healing_session.unit(3)->hp == 100);
    assert(healing_session.unit(4)->hp == 40);

    battle_session<4> damage_session;
    battle_unit_instance area_source = unit(
            10, battle_side::player, { 0, 0 }, 100, 100, 5);
    area_source.attack = 19;
    assert(area_source.passives.set_slot(0, 9, 17));
    battle_unit_instance first_area_target = unit(
            11, battle_side::enemy, { 2, 1 }, 100, 100, 0);
    first_area_target.defense = 14;
    battle_unit_instance second_area_target = unit(
            12, battle_side::enemy, { 2, 2 }, 100, 100, 0);
    second_area_target.defense = 14;
    assert(damage_session.add_unit(area_source));
    assert(damage_session.add_unit(first_area_target));
    assert(damage_session.add_unit(second_area_target));
    assert(damage_session.add_unit(unit(
            13, battle_side::player, { 3, 1 }, 100, 100, 0)));
    assert(damage_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(damage_session.select_unit(10) ==
           battle_transition::action_draft_opened);

    const action_definition area_damage = {
        91,
        { action_cost_kind::current_chakra, 1, no_tool_slot },
        {},
        { 0x01, 0, 6, 1, 100, 0 },
        { target_policy_kind::opponent_unit, 0 },
        { 3, 2 },
        {},
    };
    const action_preview damage_preview =
            battle_action_resolver::preview_area(
                    damage_session, area_damage, { 2, 1 });
    assert(damage_preview.legal());
    assert(damage_preview.target_count == 2);
    assert(damage_preview.damage_per_hit == 9);
    assert(damage_preview.total_damage == 18);

    deterministic_rng damage_rng(1);
    const action_result damage_result =
            battle_action_resolver::resolve_area_draft(
                    damage_session,
                    area_damage,
                    { 2, 1 },
                    damage_rng);
    assert(damage_result.success());
    assert(damage_result.target_count == 2);
    assert(damage_result.affected_unit_count == 2);
    assert(damage_result.affected_unit_ids[0] == 11);
    assert(damage_result.affected_unit_ids[1] == 12);
    assert(damage_result.total_damage == 26);
    assert(damage_result.damage_step_count == 2);
    assert(damage_result.damage_steps[0].hit_flags == 2);
    assert(damage_result.damage_steps[1].hit_flags == 2);
    assert(damage_session.unit(10)->chakra == 4);
    assert(damage_session.unit(11)->hp == 87);
    assert(damage_session.unit(12)->hp == 87);
    assert(damage_session.unit(13)->hp == 100);

}
