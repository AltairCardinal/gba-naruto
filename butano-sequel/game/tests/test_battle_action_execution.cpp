#include "konoha/battle_action_browser.h"
#include "konoha/battle_action_execution.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_scenario_load_policy fixed_pool;
    fixed_pool.preserve_empty_unit_slots = true;

    battle_session<12> session;
    const battle_scenario_load_result loaded =
            load_battle_scenario(
                    battle_scenario_definitions[43],
                    0,
                    fixed_pool,
                    session);
    assert(loaded.error == battle_scenario_load_error::none);
    assert(loaded.loaded_unit_count == 4);
    assert(session.unit_count() == 12);
    assert(session.unit(5));
    assert(! session.unit(5)->active);
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);

    const battle_action_browser_result browser =
            battle_action_browser::build(session);
    const battle_action_browser_entry* shadow_clone =
            browser.find(
                    battle_action_source_kind::active_action,
                    7);
    assert(shadow_clone);
    assert(shadow_clone->selectable());

    const battle_session<12> before_preview = session;
    const action_preview preview =
            battle_action_execution::preview(
                    session,
                    shadow_clone->action,
                    { 4, 16 });
    assert(preview.legal());
    assert(session == before_preview);

    const action_preview occupied =
            battle_action_execution::preview(
                    session,
                    shadow_clone->action,
                    { 2, 11 });
    assert(occupied.error == action_error::occupied_target_tile);
    assert(session == before_preview);

    deterministic_rng rng(7);
    const action_result result =
            battle_action_execution::resolve(
                    session,
                    shadow_clone->action,
                    { 4, 16 },
                    rng);
    assert(result.success());
    assert(result.summoned);
    assert(result.summon_count == 1);
    assert(session.lifecycle() ==
           battle_lifecycle::effects_resolved);
    assert(session.unit(1)->chakra ==
           unit_definitions[1].chakra_capacity - 3);
    assert(session.unit(5)->active);
    assert(session.unit(5)->character_id == 1);
    assert(session.unit(5)->summoner == 1);
    assert(session.unit(5)->ledger.completed);
    assert(session.unit(5)->position == grid_point({ 4, 16 }));

    battle_session<4> no_reserve;
    assert(load_battle_scenario(
                   battle_scenario_definitions[43],
                   0,
                   {},
                   no_reserve)
                   .error == battle_scenario_load_error::none);
    assert(no_reserve.start_round() ==
           battle_transition::unit_selection_opened);
    assert(no_reserve.select_unit(1) ==
           battle_transition::action_draft_opened);
    const battle_session<4> before_no_reserve = no_reserve;
    const action_preview unavailable =
            battle_action_execution::preview(
                    no_reserve,
                    shadow_clone->action,
                    { 4, 16 });
    assert(unavailable.error ==
           action_error::summon_slot_unavailable);
    assert(no_reserve == before_no_reserve);
}
