#ifndef KONOHA_SCENARIO_41_DEFINITION_H
#define KONOHA_SCENARIO_41_DEFINITION_H

#include "konoha/battle_conditions.h"
#include "konoha/battle_presentation.h"
#include "konoha/battle_objectives.h"
#include "konoha/battle_action_catalog.h"
#include "konoha/battle_action_loadout.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/battle_progression.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_scenario_content.h"
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

[[nodiscard]] constexpr std::array<
        character_progression_record,
        3> scenario_41_initial_roster()
{
    return {{
        { 1, 1, 100, 0, true },
        {},
        {},
    }};
}

[[nodiscard]] inline bool load_scenario_41_units(battle_session<2>& session)
{
    const battle_scenario_load_result loaded = load_battle_scenario(
            battle_scenario_definitions[41], 0, {}, session);
    return loaded.error == battle_scenario_load_error::none &&
           loaded.loaded_unit_count == 2;
}

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

[[nodiscard]] inline action_definition scenario_41_tutorial_action(
        const battle_unit_instance& actor)
{
    const battle_action_catalog_result catalog =
            battle_action_catalog::build(actor);
    if(catalog.error != battle_action_catalog_error::none)
    {
        return {};
    }
    const battle_action_catalog_entry* tutorial =
            catalog.find(
                    battle_action_source_kind::active_action,
                    scenario_41_combo_ability_id);
    return tutorial ? tutorial->action : action_definition{};
}

[[nodiscard]] constexpr battle_condition_variant scenario_41_condition_variant()
{
    return battle_condition_variants[9][0];
}

}

#endif
