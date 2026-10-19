#include "konoha/battle_session.h"
#include "konoha/battle_scene_presentation.h"
#include "konoha/battle_side_start_passives.h"

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
    battle_unit_instance result = {
        id,
        side,
        side == battle_side::player ?
                battle_control::player :
                battle_control::ai,
        { static_cast<int>(id), 1 },
        battle_facing::down,
        hp,
        max_hp,
        chakra,
        max_chakra,
        3,
        true,
        {},
    };
    result.attack = 20;
    result.base_attack = 20;
    result.agility = 20;
    result.base_agility = 20;
    result.character_id = id;
    result.original_character_id = id;
    return result;
}

void learn(
        battle_unit_instance& unit,
        std::size_t slot,
        passive_id id,
        std::uint8_t stored_level = 1)
{
    assert(unit.passives.set_slot(slot, id, stored_level));
}

}

int main()
{
    battle_unit_instance naruto = unit(
            1, battle_side::player, 9, 80, 1, 5);
    learn(naruto, 0, 24);
    const battle_side_start_passive_event nine_tail =
            battle_side_start_passive_system::apply(naruto);
    assert(nine_tail.valid);
    assert(nine_tail.kind ==
           battle_side_start_passive_kind::nine_tail_chakra);
    assert(nine_tail.unit_id == 1);
    assert(nine_tail.passive == 24);
    assert(nine_tail.hp_delta == 71);
    assert(nine_tail.chakra_delta == 4);
    assert(nine_tail.status_code == 0);
    assert(naruto.hp == 80);
    assert(naruto.chakra == 5);
    assert(naruto.side_start_passive_latched);

    // The original unit+0xBE byte is a hysteresis latch: remaining under
    // the threshold does not retrigger, crossing above it rearms.
    assert(! battle_side_start_passive_system::apply(naruto).valid);
    naruto.hp = 10;
    assert(! battle_side_start_passive_system::apply(naruto).valid);
    assert(! naruto.side_start_passive_latched);
    naruto.hp = 9;
    naruto.chakra = 0;
    assert(battle_side_start_passive_system::apply(naruto).valid);

    battle_unit_instance sasuke = unit(
            2, battle_side::player, 9, 200, 3, 4);
    learn(sasuke, 0, 25, 2);
    const battle_side_start_passive_event berserk =
            battle_side_start_passive_system::apply(sasuke);
    assert(berserk.valid);
    assert(berserk.kind ==
           battle_side_start_passive_kind::berserk_symbol);
    assert(berserk.hp_delta == 150);
    assert(sasuke.hp == 159);
    assert(berserk.status_code == 0x1E);
    assert(berserk.status_value == 30);
    assert(berserk.status_duration_ticks ==
           encode_status_duration_ticks(5));
    const status_record* sasuke_attack =
            sasuke.statuses.active(
                    sasuke.statuses.find(0x1E));
    assert(sasuke_attack);
    assert(sasuke_attack->duration_ticks ==
           encode_status_duration_ticks(5));
    assert(sasuke_attack->raw_parameter_4 == sasuke.id);
    assert(sasuke_attack->value_u16 == 30);
    assert(sasuke.attack == 26);

    battle_unit_instance sakura = unit(
            3, battle_side::player, 25, 100, 2, 3);
    learn(sakura, 0, 26, 3);
    const battle_side_start_passive_event inner =
            battle_side_start_passive_system::apply(sakura);
    assert(inner.valid);
    assert(inner.kind ==
           battle_side_start_passive_kind::inner_sakura);
    assert(inner.hp_delta == 0);
    assert(inner.chakra_delta == 0);
    assert(inner.status_value == 20);
    assert(inner.status_duration_ticks ==
           encode_status_duration_ticks(3));
    assert(sakura.attack == 24);

    battle_unit_instance above_quarter = unit(
            4, battle_side::player, 26, 100, 3, 3);
    learn(above_quarter, 0, 26);
    assert(! battle_side_start_passive_system::apply(
                    above_quarter).valid);

    // Query priority matches the original 0x1D -> 0x1E -> 0x1F chain:
    // the first learned family owns the shared latch.
    battle_unit_instance priority = unit(
            5, battle_side::player, 9, 100, 0, 4);
    learn(priority, 0, 26);
    learn(priority, 1, 24);
    assert(battle_side_start_passive_system::apply(priority).kind ==
           battle_side_start_passive_kind::nine_tail_chakra);

    // Target type 0x20 has a battle-11 gate and creates two permanent
    // attribute statuses in the original's fixed order.
    battle_unit_instance battle_11_boost = unit(
            6, battle_side::player, 9, 100, 0, 4);
    learn(battle_11_boost, 0, 35, 2);
    const battle_unit_instance outside_battle_11 =
            battle_11_boost;
    assert(! battle_side_start_passive_system::apply(
                    battle_11_boost, 10).valid);
    assert(battle_11_boost == outside_battle_11);
    const battle_side_start_passive_event dual_boost =
            battle_side_start_passive_system::apply(
                    battle_11_boost, 11);
    assert(dual_boost.valid);
    assert(dual_boost.kind ==
           battle_side_start_passive_kind::
                   battle_11_dual_boost);
    assert(dual_boost.passive == 35);
    assert(dual_boost.status_code == 0x1E);
    assert(dual_boost.status_value == 15);
    assert(dual_boost.status_duration_ticks == 0);
    assert(dual_boost.status_applied);
    assert(dual_boost.secondary_status_code == 0x22);
    assert(dual_boost.secondary_status_value == 15);
    assert(dual_boost.secondary_status_duration_ticks == 0);
    assert(dual_boost.secondary_status_applied);
    assert(battle_11_boost.statuses.active_count() == 2);
    assert(battle_11_boost.attack == 23);
    assert(battle_11_boost.agility == 23);
    assert(battle_11_boost.side_start_passive_latched);
    const battle_scene_presentation_event dual_boost_presentation =
            make_side_start_presentation_event(
                    dual_boost,
                    battle_11_boost.position);
    assert(dual_boost_presentation.has_side_start_passive);
    assert(
            dual_boost_presentation.passive_secondary_status_code ==
            0x22);
    assert(
            dual_boost_presentation.passive_secondary_status_value ==
            15);
    assert(
            dual_boost_presentation.
                    passive_secondary_status_applied);
    assert(! battle_side_start_passive_system::apply(
                    battle_11_boost, 11).valid);

    // Both status writes are one transaction. With one free slot, the
    // first write could fit but the second cannot, so neither may remain.
    battle_unit_instance full_statuses = unit(
            9, battle_side::player, 9, 100, 0, 4);
    learn(full_statuses, 0, 35, 2);
    for(std::uint8_t code = 1; code <= 15; ++code)
    {
        assert(full_statuses.statuses.upsert({
            code, 0, 0, 0, full_statuses.id, 0, 1,
        }));
    }
    const battle_unit_instance full_statuses_before =
            full_statuses;
    assert(! battle_side_start_passive_system::apply(
                    full_statuses, 11).valid);
    assert(full_statuses == full_statuses_before);

    battle_unit_instance player = unit(
            7, battle_side::player, 9, 100, 0, 4);
    learn(player, 0, 24);
    battle_unit_instance enemy = unit(
            8, battle_side::enemy, 9, 100, 0, 4);
    learn(enemy, 0, 25);
    battle_session<2> session;
    assert(session.add_unit(player));
    assert(session.add_unit(enemy));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.side_start_sequence() == 1);
    assert(session.side_start_event_count() == 1);
    assert(session.side_start_event_at(0)->unit_id == 7);
    assert(session.unit(7)->hp == 100);
    assert(session.unit(8)->hp == 9);
    battle_scene_presentation_queue<4> presentations;
    std::uint32_t observed_sequence = 0;
    assert(queue_new_side_start_presentations(
            session,
            observed_sequence,
            presentations));
    assert(observed_sequence == 1);
    assert(presentations.count() == 1);
    const battle_scene_presentation_event player_passive =
            presentations.pop();
    assert(player_passive.has_side_start_passive);
    assert(player_passive.actor_id == 7);
    assert(player_passive.origin == grid_point({ 7, 1 }));
    assert(queue_new_side_start_presentations(
            session,
            observed_sequence,
            presentations));
    assert(presentations.empty());

    assert(session.select_unit(7) ==
           battle_transition::action_draft_opened);
    assert(session.commit_action(
                   battle_facing::right,
                   no_ability) ==
           battle_transition::side_changed);
    assert(session.side_start_sequence() == 2);
    assert(session.side_start_event_count() == 1);
    assert(session.side_start_event_at(0)->unit_id == 8);
    assert(session.unit(8)->hp == 100);
    assert(queue_new_side_start_presentations(
            session,
            observed_sequence,
            presentations));
    assert(observed_sequence == 2);
    assert(presentations.pop().actor_id == 8);

    assert(session.select_unit(8) ==
           battle_transition::action_draft_opened);
    assert(session.commit_action(
                   battle_facing::left,
                   no_ability) ==
           battle_transition::round_advanced);
    assert(session.side_start_sequence() == 3);
    assert(session.side_start_event_count() == 0);
    assert(queue_new_side_start_presentations(
            session,
            observed_sequence,
            presentations));
    assert(observed_sequence == 3);
    assert(presentations.empty());
    assert(session.round_index() == 2);
    assert(session.current_side() == battle_side::player);
}
