#include "konoha/battle_player_action_flow.h"
#include "konoha/generated_battle_unit_content.h"

#include <cassert>

using namespace konoha;

namespace
{

struct combination_capture_result
{
    battle_player_action_flow_result flow = {};
    bool captured = false;
    ninja_tool_id remaining_tool = no_ninja_tool;
};

combination_capture_result run_fire_shuriken_capture(
        battle_capture_policy capture_policy)
{
    battle_unit_instance sasuke = instantiate_unit(
            unit_definitions[2],
            1,
            battle_side::player,
            battle_control::player,
            { 2, 2 },
            battle_facing::right,
            50);
    sasuke.chakra = 9;
    sasuke.max_chakra = 9;
    sasuke.equipped_tools[0] = 1;
    battle_unit_instance cat = instantiate_unit(
            unit_definitions[41],
            2,
            battle_side::enemy,
            battle_control::ai,
            { 3, 2 },
            battle_facing::left,
            1);
    cat.hp = 1;
    cat.max_hp = 1;

    battle_session<2> session;
    assert(session.add_unit(sasuke));
    assert(session.add_unit(cat));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);

    battle_player_action_flow<2> flow;
    assert(flow.begin(session).success());
    assert(flow.select_command(
                   battle_command_type::ability)
                   .success());
    battle_action_access_policy access;
    access.restrict_active_actions = true;
    access.allowed_active_actions[0] = 16;
    access.allowed_active_action_count = 1;
    access.allow_ninja_tools = true;
    assert(flow.open_action_selection(
                   session,
                   access,
                   16,
                   capture_policy)
                   .success());
    assert(flow.confirm_action_selection(session).success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::
                   combination_decision);
    assert(flow.confirm_combination_decision().success());
    assert(flow.snapshot().combination_component_count == 1);

    std::size_t cycle_guard = 0;
    while(flow.snapshot().selected_action_kind !=
                          battle_action_source_kind::ninja_tool &&
            cycle_guard++ < battle_action_catalog_capacity)
    {
        assert(flow.cycle_action(1).success());
    }
    assert(flow.snapshot().selected_action_kind ==
           battle_action_source_kind::ninja_tool);
    assert(flow.snapshot().selected_action_id == 1);
    assert(flow.confirm_action_selection(session).success());
    assert(flow.snapshot().combination_component_count == 2);
    assert(flow.snapshot().combination_result_action_id == 18);
    assert(flow.preview_target(session, { 3, 2 }).success());

    deterministic_rng rng(7);
    battle_condition_variant no_conditions;
    const battle_player_action_flow_result resolved =
            flow.confirm_target(
                    session,
                    { 3, 2 },
                    rng,
                    no_conditions,
                    capture_policy);
    return {
        resolved,
        session.unit(2)->captured,
        session.unit(1)->equipped_tools[0],
    };
}

}

int main()
{
    battle_unit_instance sasuke = instantiate_unit(
            unit_definitions[2],
            1,
            battle_side::player,
            battle_control::player,
            { 2, 2 },
            battle_facing::right,
            50);
    sasuke.chakra = 9;
    sasuke.max_chakra = 9;
    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::ai,
            { 3, 2 },
            battle_facing::left,
            1);
    enemy.hp = 500;
    enemy.max_hp = 500;

    battle_session<2> session;
    assert(session.add_unit(sasuke));
    assert(session.add_unit(enemy));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);

    battle_player_action_flow<2> flow;
    assert(flow.begin(session).success());
    assert(flow.select_command(
                   battle_command_type::ability)
                   .success());

    battle_action_access_policy pair_only;
    pair_only.restrict_active_actions = true;
    pair_only.allowed_active_actions[0] = 16;
    pair_only.allowed_active_actions[1] = 5;
    pair_only.allowed_active_action_count = 2;
    pair_only.allow_ninja_tools = false;
    assert(flow.open_action_selection(
                   session,
                   pair_only,
                   16)
                   .success());

    assert(flow.confirm_action_selection(session).success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::
                   combination_decision);
    assert(flow.snapshot().combination_component_count == 0);
    assert(flow.snapshot().combination_decision_selected);

    assert(flow.cycle_combination_decision(1).success());
    assert(! flow.snapshot().combination_decision_selected);
    assert(flow.confirm_combination_decision().success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::target_selection);
    assert(flow.snapshot().combination_component_count == 0);

    assert(flow.cancel_target_selection().success());
    assert(flow.confirm_action_selection(session).success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::
                   combination_decision);
    assert(flow.cancel_combination_decision().success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::action_selection);

    assert(flow.confirm_action_selection(session).success());
    assert(flow.snapshot().combination_decision_selected);
    assert(flow.confirm_combination_decision().success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::action_selection);
    assert(flow.snapshot().combination_component_count == 1);
    assert(flow.snapshot().combination_first_action_id == 16);
    assert(flow.snapshot().combination_reserved_chakra == 2);

    assert(flow.cycle_action(1).success());
    assert(flow.snapshot().selected_action_id == 5);
    assert(flow.confirm_action_selection(session).success());
    assert(flow.snapshot().phase ==
           battle_player_action_phase::target_selection);
    assert(flow.snapshot().combination_component_count == 2);
    assert(flow.snapshot().combination_result_action_id ==
           no_ability);
    assert(flow.preview_target(session, { 3, 2 }).success());
    assert(flow.snapshot().target_preview.hit_count == 2);

    deterministic_rng rng(29);
    battle_condition_variant no_conditions;
    const battle_player_action_flow_result resolved =
            flow.confirm_target(
                    session,
                    { 3, 2 },
                    rng,
                    no_conditions);
    assert(resolved.success());
    assert(resolved.impact_count == 2);
    assert(session.unit(1)->chakra == 7);
    assert(session.unit(1)->ledger.acted);
    assert(session.lifecycle() ==
           battle_lifecycle::facing_select);

    battle_capture_policy active_only_capture = {
        true,
        battle_side::enemy,
        41,
        true,
        false,
        false,
    };
    const combination_capture_result active_only =
            run_fire_shuriken_capture(
                    active_only_capture);
    assert(active_only.flow.success());
    assert(active_only.flow.capture_count == 0);
    assert(! active_only.captured);
    assert(active_only.remaining_tool == no_ninja_tool);

    battle_capture_policy complete_capture =
            active_only_capture;
    complete_capture.allow_ninja_tools = true;
    const combination_capture_result complete =
            run_fire_shuriken_capture(complete_capture);
    assert(complete.flow.success());
    assert(complete.flow.capture_count == 1);
    assert(complete.captured);
    assert(complete.remaining_tool == no_ninja_tool);
}
