#include "konoha/battle_deployment_flow.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_deployment_flow battle_09;
    const battle_deployment_result prepared =
            battle_09.prepare(
                    battle_scenario_definitions[9],
                    0,
                    {});
    assert(prepared.success());
    assert(battle_09.phase() ==
           battle_deployment_phase::unit_confirmation);
    assert(battle_09.entry_count() == 8);
    assert(battle_09.current_entry()->record_id == 0);
    assert(battle_09.current_entry()->character_id == 1);
    assert(battle_09.current_entry()->side ==
           battle_side::player);

    for(int expected = 1; expected < 8; ++expected)
    {
        assert(battle_09.confirm().success());
        assert(battle_09.phase() ==
               battle_deployment_phase::unit_confirmation);
        assert(battle_09.current_entry()->record_id == expected);
    }
    assert(battle_09.confirm().success());
    assert(battle_09.phase() ==
           battle_deployment_phase::start_confirmation);
    assert(! battle_09.complete());

    assert(battle_09.cancel().success());
    assert(battle_09.phase() ==
           battle_deployment_phase::unit_confirmation);
    assert(battle_09.current_entry()->record_id == 7);
    assert(battle_09.confirm().success());
    assert(battle_09.confirm().success());
    assert(battle_09.complete());
    assert(battle_09.phase() ==
           battle_deployment_phase::complete);

    battle_deployment_flow unresolved;
    const battle_deployment_result unresolved_result =
            unresolved.prepare(
                    battle_scenario_definitions[32],
                    0,
                    {});
    assert(unresolved_result.error ==
           battle_deployment_error::unresolved_placeholder);
    assert(unresolved_result.record_id == 0);
    assert(unresolved.phase() ==
           battle_deployment_phase::error);

    battle_scenario_load_policy deployment_policy;
    deployment_policy.placeholder_characters =
            { 1, 2, 3, 35, 35, 35 };
    battle_deployment_flow dynamic;
    assert(dynamic.prepare(
                    battle_scenario_definitions[32],
                    0,
                    deployment_policy).success());
    assert(dynamic.entry_count() == 6);
    for(int index = 0; index < 6; ++index)
    {
        assert(dynamic.entry(index)->character_id ==
               deployment_policy.placeholder_characters[
                       static_cast<std::size_t>(index)]);
    }

    battle_deployment_flow invalid_variant;
    assert(invalid_variant.prepare(
                    battle_scenario_definitions[9],
                    3,
                    {}).error ==
           battle_deployment_error::invalid_variant);
}
