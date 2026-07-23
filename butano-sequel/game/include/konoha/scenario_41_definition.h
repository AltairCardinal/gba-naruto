#ifndef KONOHA_SCENARIO_41_DEFINITION_H
#define KONOHA_SCENARIO_41_DEFINITION_H

#include "konoha/battle_presentation.h"
#include "konoha/battle_objectives.h"
#include "konoha/battle_action_loadout.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/generated_battle_unit_content.h"

namespace konoha
{

constexpr int scenario_41_appearance_frames = 60;
constexpr int scenario_41_start_title_frames = 60;
constexpr int scenario_41_black_frames = 30;
constexpr int scenario_41_transition_frames = 60;
constexpr battle_unit_id scenario_41_naruto_unit = 1;
constexpr battle_unit_id scenario_41_konoha_maru_unit = 2;
constexpr ability_id scenario_41_combo_ability_id = 5;

[[nodiscard]] inline bool load_scenario_41_entrance(presentation_queue<6>& queue)
{
    return queue.push_automatic(
                   presentation_cue::player_appearance, scenario_41_appearance_frames) &&
           queue.push_automatic(
                   presentation_cue::enemy_appearance, scenario_41_appearance_frames) &&
           queue.push_automatic(
                   presentation_cue::start_title, scenario_41_start_title_frames) &&
           queue.push_automatic(presentation_cue::black, scenario_41_black_frames) &&
           queue.push_wait_for_input(presentation_cue::entrance_dialogue, true) &&
           queue.push_automatic(
                   presentation_cue::shuriken_transition, scenario_41_transition_frames);
}

[[nodiscard]] constexpr action_definition_set<15> scenario_41_player_actions()
{
    const action_loadout<15> learned = build_primary_action_loadout(unit_definitions[1], 1);
    const action_loadout<15> tutorial = filter_action_loadout(
            learned, [](ability_id id) { return id == scenario_41_combo_ability_id; });
    return materialize_action_loadout(tutorial, active_action_definitions);
}

[[nodiscard]] constexpr action_definition_set<15> scenario_41_enemy_actions()
{
    return materialize_action_loadout(
            build_primary_action_loadout(unit_definitions[30], 1),
            active_action_definitions);
}

[[nodiscard]] constexpr action_definition scenario_41_combo_action()
{
    return scenario_41_player_actions().values[0];
}

[[nodiscard]] inline objective_rule<1> scenario_41_victory_objective()
{
    objective_rule<1> result;
    result.trigger = battle_domain_event::effects_resolved;
    result.outcome = battle_outcome::victory;
    result.priority = 10;
    result.nodes[0].condition = {
        objective_predicate_kind::defeated,
        scenario_41_konoha_maru_unit,
    };
    result.node_count = 1;
    return result;
}

}

#endif
