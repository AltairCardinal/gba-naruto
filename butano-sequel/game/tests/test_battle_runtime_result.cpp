#include "konoha/battle_runtime_result.h"

#include <cassert>

using namespace konoha;

int main()
{
    assert(battle_runtime_exit_for_outcome(
                   battle_condition_outcome::win) ==
           battle_runtime_scene_exit::victory);
    assert(battle_runtime_exit_for_outcome(
                   battle_condition_outcome::loss) ==
           battle_runtime_scene_exit::defeat);
    assert(battle_runtime_exit_for_outcome(
                   battle_condition_outcome::
                           equal_slot_result) ==
           battle_runtime_scene_exit::draw);
    assert(battle_runtime_exit_for_outcome(
                   battle_condition_outcome::none) ==
           battle_runtime_scene_exit::aborted);

    assert(battle_runtime_exit_resolved(
            battle_runtime_scene_exit::victory));
    assert(battle_runtime_exit_resolved(
            battle_runtime_scene_exit::defeat));
    assert(battle_runtime_exit_resolved(
            battle_runtime_scene_exit::draw));
    assert(! battle_runtime_exit_resolved(
            battle_runtime_scene_exit::aborted));

    assert(battle_runtime_exit_commits_campaign(
            battle_runtime_scene_exit::victory));
    assert(! battle_runtime_exit_commits_campaign(
            battle_runtime_scene_exit::defeat));
    assert(! battle_runtime_exit_commits_campaign(
            battle_runtime_scene_exit::draw));
    assert(! battle_runtime_exit_commits_campaign(
            battle_runtime_scene_exit::aborted));

    assert(battle_runtime_exit_advances_campaign(
            battle_runtime_scene_exit::victory));
    assert(! battle_runtime_exit_advances_campaign(
            battle_runtime_scene_exit::defeat));
    assert(! battle_runtime_exit_advances_campaign(
            battle_runtime_scene_exit::draw));
    assert(! battle_runtime_exit_advances_campaign(
            battle_runtime_scene_exit::aborted));
}
