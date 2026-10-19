#include "konoha/battle_results.h"
#include "konoha/battle_scenario_loader.h"
#include "konoha/generated_battle_result_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <array>
#include <cassert>

using namespace konoha;

int main()
{
    assert(battle_reward_definitions[104].mission_experience == 100);
    assert(battle_reward_definitions[104].round_bonus_experience == 25);
    assert(battle_reward_definitions[104].round_limit == 3);
    assert(battle_reward_record_for_scenario(41, 0) == 104);
    assert(battle_reward_record_for_scenario(9, 0) == 24);
    assert(experience_threshold_definitions[1].base_threshold == 250);
    assert(experience_threshold_definitions[2].base_threshold == 180);
    assert(experience_threshold_definitions[3].base_threshold == 150);

    const character_stat_values naruto_level_1 =
            character_stats_at_level(1, 1);
    const character_stat_values naruto_level_2 =
            character_stats_at_level(1, 2);
    assert(naruto_level_1.max_hp == 80);
    assert(naruto_level_2.max_hp == 94);
    assert(naruto_level_2.attack == naruto_level_1.attack + 1);
    assert(naruto_level_2.defense == naruto_level_1.defense + 1);
    assert(naruto_level_2.agility == naruto_level_1.agility + 1);

    battle_session<2> session;
    battle_scenario_load_policy policy;
    policy.character_levels[1] = 1;
    assert(load_battle_scenario(
                   battle_scenario_definitions[41],
                   0,
                   policy,
                   session)
                   .error == battle_scenario_load_error::none);
    assert(session.unit(1)->carried_experience == 0);
    assert(session.unit(2)->carried_experience == 50);

    battle_unit_instance* naruto =
            const_cast<battle_unit_instance*>(session.unit(1));
    naruto->carried_experience = 50;

    std::array<character_progression_record, 3> roster = {{
        { 1, 1, 100, 0, true },
        {},
        {},
    }};
    const auto result = battle_result_system::settle(
            session,
            battle_reward_definitions[
                    battle_reward_record_for_scenario(41, 0)],
            4,
            roster);
    assert(result.participant_count == 1);
    const battle_result_participant& participant =
            result.participants[0];
    assert(participant.character_id == 1);
    assert(participant.mission_experience == 100);
    assert(participant.round_bonus_experience == 0);
    assert(participant.battle_experience == 50);
    assert(participant.total_experience == 150);
    assert(participant.before.level == 1);
    assert(participant.before.experience == 100);
    assert(participant.after.level == 2);
    assert(participant.after.experience == 0);
    assert(participant.after.training_points == 1);
    assert(participant.after.action_states_initialized);
    assert(
            participant.after.primary_action_levels[6] ==
            unlocked_action_level);
    assert(participant.stat_growth.max_hp == 14);
    assert(roster[0] == participant.after);

    std::array<character_progression_record, 3> round_bonus_roster = {{
        { 1, 1, 0, 0, true },
        {},
        {},
    }};
    naruto->carried_experience = 0;
    const auto round_bonus = battle_result_system::settle(
            session,
            battle_reward_definitions[104],
            3,
            round_bonus_roster);
    assert(round_bonus.participants[0].round_bonus_experience == 25);
    assert(round_bonus.participants[0].total_experience == 125);

    naruto->carried_experience = 100;
    const battle_result mission_only =
            battle_result_system::preview(
                    session,
                    battle_reward_definitions[104],
                    4,
                    round_bonus_roster,
                    { false });
    assert(mission_only.participants[0]
                   .mission_experience == 100);
    assert(mission_only.participants[0]
                   .battle_experience == 0);
    assert(mission_only.participants[0]
                   .total_experience == 100);

    battle_session<3> passive_session;
    assert(load_battle_scenario(
                   battle_scenario_definitions[41],
                   0,
                   policy,
                   passive_session)
                   .error == battle_scenario_load_error::none);
    battle_unit_instance* passive_naruto =
            const_cast<battle_unit_instance*>(passive_session.unit(1));
    passive_naruto->carried_experience = 50;
    assert(passive_naruto->passives.set_slot(0, 16, 1));
    battle_unit_instance clone = *passive_naruto;
    clone.id = 3;
    clone.position = { 5, 10 };
    clone.carried_experience = 10;
    assert(passive_session.add_unit(clone));
    std::array<character_progression_record, 3> experience_passive_roster = {{
        { 1, 1, 0, 0, true },
        {},
        {},
    }};
    const auto experience_passive = battle_result_system::settle(
            passive_session,
            battle_reward_definitions[104],
            4,
            experience_passive_roster);
    assert(experience_passive.participants[0].mission_experience == 100);
    assert(experience_passive.participants[0].round_bonus_experience == 0);
    assert(experience_passive.participants[0].battle_experience == 63);
    assert(experience_passive.participants[0].total_experience == 163);

    character_progression_record later_naruto =
            { 1, 2, 110, 1, true };
    const level_settlement later = settle_character_progression(
            later_naruto, 155);
    assert(later.after.level == 3);
    assert(later.after.experience == 0);
    assert(later.after.training_points == 2);

    character_progression_record sasuke =
            { 2, 4, 170, 3, true };
    const level_settlement multi_level =
            settle_character_progression(sasuke, 500);
    assert(multi_level.after.level == 6);
    assert(multi_level.after.training_points == 5);
}
