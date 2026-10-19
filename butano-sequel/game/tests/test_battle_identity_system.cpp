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
        std::uint8_t character_id)
{
    battle_unit_instance result = {
        id,
        side,
        side == battle_side::player ? battle_control::player : battle_control::ai,
        position,
        battle_facing::down,
        hp,
        hp,
        10,
        10,
        3,
        true,
        {},
    };
    result.attack = 20;
    result.character_id = character_id;
    result.original_character_id = character_id;
    return result;
}

}

int main()
{
    battle_unit_instance transformed = unit(
            1, battle_side::player, { 1, 1 }, 40, 1);
    const battle_unit_instance linked = unit(
            2, battle_side::enemy, { 2, 1 }, 80, 30);
    assert(battle_identity_system::apply(transformed, linked, 1, 0));
    assert(transformed.character_id == 30);
    assert(transformed.statuses.active(
                   transformed.statuses.find(0x05))->duration_ticks == 2);

    battle_session<2> expiry_session;
    assert(expiry_session.add_unit(transformed));
    assert(expiry_session.add_unit(linked));
    assert(expiry_session.start_round() == battle_transition::unit_selection_opened);
    assert(expiry_session.select_unit(1) == battle_transition::action_draft_opened);
    assert(expiry_session.commit_action(battle_facing::down, no_ability) ==
           battle_transition::side_changed);
    assert(expiry_session.unit(1)->character_id == 30);
    assert(expiry_session.unit(1)->statuses.active(
                   expiry_session.unit(1)->statuses.find(0x05))->duration_ticks == 1);
    assert(expiry_session.select_unit(2) == battle_transition::action_draft_opened);
    assert(expiry_session.commit_action(battle_facing::up, no_ability) ==
           battle_transition::round_advanced);
    assert(expiry_session.unit(1)->character_id == 1);
    assert(expiry_session.unit(1)->identity_override_character_id == no_battle_unit);
    assert(expiry_session.unit(1)->statuses.find(0x05) == no_status_slot);
    assert(expiry_session.unit(1)->statuses.removed_count() == 1);

    battle_unit_instance special = unit(
            3, battle_side::player, { 1, 1 }, 40, 8);
    special.special_identity_variant = true;
    assert(battle_identity_system::apply(special, linked, 3, 0));
    assert(battle_identity_system::cleanup(
            special, identity_restore_reason::cleanup));
    assert(special.character_id == 0x39);
    assert(special.statuses.find(0x05) == no_status_slot);
    assert(special.statuses.removed_count() == 1);

    battle_unit_instance crowded = unit(
            4, battle_side::player, { 1, 1 }, 40, 1);
    for(std::uint8_t code = 1; code <= 16; ++code)
    {
        if(code != 5)
        {
            assert(crowded.statuses.upsert({ code, 0, 0, 0, 0, 0, 0 }));
        }
    }
    assert(crowded.statuses.upsert({ 17, 0, 0, 0, 0, 0, 0 }));
    const battle_unit_instance before_crowded = crowded;
    assert(! battle_identity_system::apply(crowded, linked, 3, 0));
    assert(crowded == before_crowded);

    battle_unit_instance attacker = unit(
            5, battle_side::player, { 1, 1 }, 40, 1);
    battle_unit_instance defeated_transform = unit(
            6, battle_side::enemy, { 2, 1 }, 10, 30);
    const battle_unit_instance disguise = unit(
            7, battle_side::player, { 4, 4 }, 40, 4);
    assert(battle_identity_system::apply(defeated_transform, disguise, 3, 0));
    battle_session<2> defeat_session;
    assert(defeat_session.add_unit(attacker));
    assert(defeat_session.add_unit(defeated_transform));
    assert(defeat_session.start_round() == battle_transition::unit_selection_opened);
    assert(defeat_session.select_unit(5) == battle_transition::action_draft_opened);
    action_definition damage;
    damage.id = 19;
    damage.effect = { 1, 0, 10, 1, 100, 0 };
    damage.target = { target_policy_kind::opponent_unit, 0 };
    damage.range = { 1, 0 };
    deterministic_rng rng(7);
    const action_result result = battle_action_resolver::resolve_draft(
            defeat_session,
            6,
            no_battle_unit,
            damage,
            { 2, 1 },
            rng);
    assert(result.success());
    assert(result.defeated);
    assert(defeat_session.unit(6)->character_id == 30);
    assert(defeat_session.unit(6)->statuses.find(0x05) == no_status_slot);
    assert(defeat_session.unit(6)->statuses.removed_count() == 1);
}
