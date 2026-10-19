#include "konoha/battle_visual_resource_coordinator.h"

#include <cassert>

using namespace konoha;

int main()
{
    static_assert(
            battle_visual_resource_contract(
                    battle_visual_resource_cohort::map)
                    .map_units);
    static_assert(
            battle_visual_resource_contract(
                    battle_visual_resource_cohort::map)
                    .map_ui);
    static_assert(
            battle_visual_resource_contract(
                    battle_visual_resource_cohort::map)
                    .map_cursor);
    static_assert(
            battle_visual_resource_contract(
                    battle_visual_resource_cohort::map)
                    .combat_stage);
    static_assert(
            ! battle_visual_resource_contract(
                    battle_visual_resource_cohort::map)
                    .portrait);
    static_assert(
            battle_visual_resource_contract(
                    battle_visual_resource_cohort::
                            combat_portrait)
                    .portrait);
    static_assert(
            battle_visual_resource_contract(
                    battle_visual_resource_cohort::
                            script_dialogue)
                    .script_message_window);
    static_assert(
            ! battle_visual_resource_contract(
                    battle_visual_resource_cohort::
                            combat_portrait)
                    .map_ui);
    static_assert(
            ! battle_visual_resource_contract(
                    battle_visual_resource_cohort::
                            combat_portrait)
                    .map_units);
    static_assert(
            ! battle_visual_resource_contract(
                    battle_visual_resource_cohort::
                            combat_portrait)
                    .map_cursor);
    static_assert(
            ! battle_visual_resource_contract(
                    battle_visual_resource_cohort::
                            combat_portrait)
                    .combat_stage);

    assert(select_battle_visual_resource_cohort(
                   false, false) ==
           battle_visual_resource_cohort::map);
    assert(select_battle_visual_resource_cohort(
                   true, false) ==
           battle_visual_resource_cohort::
                   script_dialogue);
    assert(select_battle_visual_resource_cohort(
                   true, true) ==
           battle_visual_resource_cohort::
                   combat_portrait);

    battle_visual_resource_coordinator coordinator;
    battle_visual_resource_transition transition =
            coordinator.transition_to(
                    battle_visual_resource_cohort::map);
    assert(transition.changed);
    assert(transition.release_map);
    assert(transition.commit_before_allocate);

    transition = coordinator.transition_to(
            battle_visual_resource_cohort::map);
    assert(! transition.changed);
    assert(! transition.commit_before_allocate);

    transition = coordinator.transition_to(
            battle_visual_resource_cohort::
                    combat_portrait);
    assert(transition.changed);
    assert(transition.release_map);
    assert(! transition.release_portrait);
    assert(transition.commit_before_allocate);

    transition = coordinator.transition_to(
            battle_visual_resource_cohort::
                    combat_portrait);
    assert(! transition.changed);
    assert(! transition.commit_before_allocate);

    transition = coordinator.transition_to(
            battle_visual_resource_cohort::map);
    assert(transition.changed);
    assert(transition.release_portrait);
    assert(! transition.release_map);
    assert(transition.commit_before_allocate);

    transition = coordinator.transition_to(
            battle_visual_resource_cohort::
                    script_dialogue);
    assert(transition.release_map);
    assert(transition.commit_before_allocate);

    transition = coordinator.transition_to(
            battle_visual_resource_cohort::map);
    assert(transition.release_script);
    assert(transition.commit_before_allocate);
}
