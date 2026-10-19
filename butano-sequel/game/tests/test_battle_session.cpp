#include "konoha/battle_session.h"

#include <array>
#include <cassert>
#include <cstddef>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id, battle_side side, battle_control control, grid_point position)
{
    return {
        id,
        side,
        control,
        position,
        battle_facing::down,
        80,
        80,
        40,
        40,
        3,
        true,
        {},
    };
}

}

int main()
{
    static_assert(sizeof(battlefield_object_record) == 16);
    static_assert(offsetof(battlefield_object_record, payload_id) == 4);
    static_assert(offsetof(battlefield_object_record, duration_ticks) == 6);
    static_assert(offsetof(battlefield_object_record, source_unit_id) == 8);
    static_assert(offsetof(battlefield_object_record, auxiliary) == 10);
    static_assert(offsetof(battlefield_object_record, runtime_handle) == 12);

    battle_session<3> session;
    assert(session.add_unit(unit(1, battle_side::player, battle_control::player, { 2, 4 })));
    assert(session.add_unit(unit(2, battle_side::player, battle_control::player, { 3, 4 })));
    assert(session.add_unit(unit(3, battle_side::enemy, battle_control::ai, { 6, 4 })));
    assert(! session.add_unit(unit(3, battle_side::enemy, battle_control::ai, { 7, 4 })));
    assert(session.unit_count() == 3);

    assert(session.start_round() == battle_transition::unit_selection_opened);
    assert(session.round_index() == 1);
    assert(session.current_side() == battle_side::player);
    assert(session.lifecycle() == battle_lifecycle::unit_select);
    assert(session.cycle_available_unit(1, 1)->id == 2);
    assert(session.cycle_available_unit(2, 1)->id == 1);
    assert(session.cycle_available_unit(1, -1)->id == 2);
    assert(session.cycle_available_unit(1, 0) == nullptr);
    assert(session.select_unit(3) == battle_transition::invalid);

    assert(session.select_unit(1) == battle_transition::action_draft_opened);
    assert(session.lifecycle() == battle_lifecycle::action_drafting);
    assert(session.preview_move({ 2, 2 }) == battle_transition::move_previewed);
    assert((session.unit(1)->position == grid_point{ 2, 4 }));
    assert(session.draft().active);
    assert((session.draft().origin == grid_point{ 2, 4 }));
    assert((session.draft().preview_position == grid_point{ 2, 2 }));

    assert(session.cancel_action() == battle_transition::unit_selection_opened);
    assert(session.lifecycle() == battle_lifecycle::unit_select);
    assert((session.unit(1)->position == grid_point{ 2, 4 }));
    assert(! session.draft().active);

    assert(session.select_unit(1) == battle_transition::action_draft_opened);
    assert(session.preview_move({ 2, 2 }) == battle_transition::move_previewed);
    assert(session.commit_action(battle_facing::left, 7) == battle_transition::unit_completed);
    assert((session.unit(1)->position == grid_point{ 2, 2 }));
    assert(session.unit(1)->facing == battle_facing::left);
    assert(session.unit(1)->ledger.moved);
    assert(session.unit(1)->ledger.completed);
    assert(session.unit(1)->ledger.defense_ability == 7);
    assert(session.lifecycle() == battle_lifecycle::unit_select);
    assert(session.select_unit(1) == battle_transition::invalid);

    assert(session.select_unit(2) == battle_transition::action_draft_opened);
    assert(session.commit_action(battle_facing::up, no_ability) ==
           battle_transition::side_changed);
    assert(session.current_side() == battle_side::enemy);
    assert(session.lifecycle() == battle_lifecycle::unit_select);

    assert(session.select_unit(3) == battle_transition::action_draft_opened);
    assert(session.commit_action(battle_facing::right, no_ability) ==
           battle_transition::round_advanced);
    assert(session.round_index() == 2);
    assert(session.current_side() == battle_side::player);
    assert(! session.unit(1)->ledger.completed);
    assert(! session.unit(2)->ledger.completed);
    assert(! session.unit(3)->ledger.completed);

    constexpr std::array<std::uint8_t, 6> command_blocker_codes = {
        0x3F, 0x3E, 0x3D, 0x0F, 0x11, 0x15,
    };
    for(const std::uint8_t blocker_code : command_blocker_codes)
    {
        battle_session<3> blocked_session;
        assert(blocked_session.add_unit(unit(
                10,
                battle_side::player,
                battle_control::player,
                { 1, 1 })));
        battle_unit_instance blocked = unit(
                11,
                battle_side::enemy,
                battle_control::ai,
                { 4, 1 });
        assert(blocked.statuses.upsert({
            blocker_code,
            0,
            encode_status_duration_ticks(2),
            0,
            10,
            0,
            0,
        }));
        assert(blocked_session.add_unit(blocked));
        assert(blocked_session.add_unit(unit(
                12,
                battle_side::enemy,
                battle_control::ai,
                { 5, 1 })));

        assert(blocked_session.start_round() ==
               battle_transition::unit_selection_opened);
        assert(blocked_session.select_unit(10) ==
               battle_transition::action_draft_opened);
        assert(blocked_session.commit_action(
                       battle_facing::right,
                       no_ability) ==
               battle_transition::side_changed);
        assert(blocked_session.select_unit(11) ==
               battle_transition::invalid);
        const battle_unit_instance* next =
                blocked_session.cycle_available_unit(11, 1);
        assert(next && next->id == 12);
    }

    battle_session<3> restraint_expiry_session;
    assert(restraint_expiry_session.add_unit(unit(
            20,
            battle_side::player,
            battle_control::player,
            { 1, 2 })));
    battle_unit_instance restrained = unit(
            21,
            battle_side::enemy,
            battle_control::ai,
            { 4, 2 });
    assert(restrained.statuses.upsert({
        0x3F,
        0,
        2,
        0,
        20,
        0,
        0,
    }));
    assert(restraint_expiry_session.add_unit(restrained));
    assert(restraint_expiry_session.add_unit(unit(
            22,
            battle_side::enemy,
            battle_control::ai,
            { 5, 2 })));
    assert(restraint_expiry_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(restraint_expiry_session.select_unit(20) ==
           battle_transition::action_draft_opened);
    assert(restraint_expiry_session.commit_action(
                   battle_facing::right,
                   no_ability) ==
           battle_transition::side_changed);
    assert(restraint_expiry_session.select_unit(21) ==
           battle_transition::invalid);
    assert(restraint_expiry_session.select_unit(22) ==
           battle_transition::action_draft_opened);
    assert(restraint_expiry_session.commit_action(
                   battle_facing::left,
                   no_ability) ==
           battle_transition::round_advanced);
    assert(restraint_expiry_session.unit(21)->statuses.find(0x3F) ==
           no_status_slot);
    assert(restraint_expiry_session.select_unit(20) ==
           battle_transition::action_draft_opened);
    assert(restraint_expiry_session.commit_action(
                   battle_facing::right,
                   no_ability) ==
           battle_transition::side_changed);
    assert(restraint_expiry_session.select_unit(21) ==
           battle_transition::action_draft_opened);

    battle_session<2> object_session;
    assert(object_session.add_unit(unit(
            4,
            battle_side::player,
            battle_control::player,
            { 1, 1 })));
    assert(object_session.add_unit(unit(
            5,
            battle_side::enemy,
            battle_control::ai,
            { 5, 5 })));
    battlefield_object_record explosive;
    explosive.type = 1;
    explosive.x = 3;
    explosive.y = 3;
    explosive.payload_id = 67;
    explosive.duration_ticks = 2;
    explosive.source_unit_id = 4;
    const std::uint8_t explosive_slot =
            object_session.objects().allocate(explosive);
    assert(explosive_slot == 1);
    battlefield_object_record visual;
    visual.type = 2;
    visual.x = 2;
    visual.y = 2;
    visual.payload_id = 37;
    visual.duration_ticks = 4;
    const std::uint8_t visual_slot =
            object_session.objects().allocate(visual);
    assert(visual_slot == 2);

    assert(object_session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(object_session.select_unit(4) ==
           battle_transition::action_draft_opened);
    assert(object_session.commit_action(
                   battle_facing::down,
                   no_ability) == battle_transition::side_changed);
    assert(object_session.objects().record(
                   explosive_slot)->duration_ticks == 1);
    assert(object_session.objects().record(
                   visual_slot)->duration_ticks == 3);
    assert(object_session.object_tick_event_count() == 0);

    assert(object_session.select_unit(5) ==
           battle_transition::action_draft_opened);
    assert(object_session.commit_action(
                   battle_facing::up,
                   no_ability) == battle_transition::round_advanced);
    assert(object_session.objects().record(explosive_slot)->type == 0);
    assert(object_session.objects().record(
                   visual_slot)->duration_ticks == 2);
    assert(object_session.object_tick_event_count() == 1);
    const battlefield_object_tick_event* due =
            object_session.object_tick_event_at(0);
    assert(due && due->kind ==
           battlefield_object_tick_kind::type_1_due);
    assert(due->slot == explosive_slot);
    assert(due->object.payload_id == 67);
    assert(due->object.source_unit_id == 4);
}
