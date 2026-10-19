#include "konoha/battle_action_system.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_session<2> session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[41],
                   0,
                   {},
                   session)
                   .error == battle_scenario_load_error::none);
    assert(session.unit(1)->carried_experience == 0);
    assert(session.unit(2)->carried_experience == 50);
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);

    action_definition lethal;
    lethal.id = 1;
    lethal.effect = { 1, 0, 100, 1, 100, 0 };
    lethal.target = { target_policy_kind::opponent_unit, 0 };
    lethal.range = { 9, 0 };

    deterministic_rng rng(7);
    const action_result resolved =
            battle_action_resolver::resolve_draft(
                    session,
                    2,
                    no_battle_unit,
                    lethal,
                    session.unit(2)->position,
                    rng);
    assert(resolved.success());
    assert(resolved.defeated);
    assert(session.unit(1)->carried_experience == 50);
    assert(session.unit(2)->carried_experience == 0);
}
