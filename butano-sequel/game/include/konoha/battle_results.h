#ifndef KONOHA_BATTLE_RESULTS_H
#define KONOHA_BATTLE_RESULTS_H

#include "konoha/battle_progression.h"
#include "konoha/battle_result_policy.h"
#include "konoha/battle_result_content.h"
#include "konoha/battle_session.h"
#include "konoha/generated_battle_passive_content.h"
#include "konoha/generated_battle_result_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

[[nodiscard]] constexpr std::uint8_t battle_reward_record_for_scenario(
        int battle_id, int variant)
{
    if(battle_id < 0 ||
            battle_id >= static_cast<int>(
                    scenario_reward_record_indices.size()) ||
            variant < 0 || variant >= 3)
    {
        return no_battle_reward_record;
    }
    const int record =
            scenario_reward_record_indices[
                    static_cast<std::size_t>(battle_id)] +
            variant;
    return record >= 0 &&
                   record < static_cast<int>(
                           battle_reward_definitions.size()) ?
            static_cast<std::uint8_t>(record) :
            no_battle_reward_record;
}

[[nodiscard]] constexpr character_stat_values character_stats_at_level(
        std::uint8_t character_id, int level)
{
    if(character_id >= unit_definitions.size())
    {
        return {};
    }
    return character_stats_at_level(
            unit_definitions[character_id],
            character_growth_definitions[character_id],
            level);
}

[[nodiscard]] constexpr level_settlement settle_character_progression(
        const character_progression_record& record,
        int gained_experience)
{
    if(record.character_id >=
            experience_threshold_definitions.size())
    {
        return { record, record, 0, 0, 0 };
    }
    level_settlement result = settle_character_progression(
            record,
            gained_experience,
            experience_threshold_definitions[record.character_id]);
    if(record.character_id < unit_definitions.size())
    {
        (void) synchronize_character_action_unlocks(
                result.after,
                unit_definitions[record.character_id]);
    }
    return result;
}

struct battle_result_participant
{
    std::uint8_t character_id = 0;
    int mission_experience = 0;
    int round_bonus_experience = 0;
    int battle_experience = 0;
    int total_experience = 0;
    character_progression_record before = {};
    character_progression_record after = {};
    character_stat_values stat_growth = {};

    constexpr bool operator==(const battle_result_participant&) const =
            default;
};

struct battle_result
{
    std::array<battle_result_participant, 3> participants = {};
    std::size_t participant_count = 0;

    constexpr bool operator==(const battle_result&) const = default;
};

class battle_result_system
{
public:
    template<std::size_t MaxUnits, std::size_t RosterSize>
    [[nodiscard]] static battle_result preview(
            const battle_session<MaxUnits>& session,
            const battle_reward_definition& reward,
            int battle_round,
            const std::array<
                    character_progression_record,
                    RosterSize>& roster,
            battle_result_policy policy = {})
    {
        battle_result result;
        for(const character_progression_record& progression : roster)
        {
            if(! progression.active ||
                    result.participant_count >=
                            result.participants.size())
            {
                continue;
            }
            const battle_unit_instance* unit =
                    _find_player_unit(
                            session, progression.character_id);
            if(! unit)
            {
                continue;
            }

            battle_result_participant& participant =
                    result.participants[
                            result.participant_count++];
            participant.character_id =
                    progression.character_id;
            participant.mission_experience =
                    reward.mission_experience;
            participant.round_bonus_experience =
                    battle_round <= reward.round_limit ?
                    reward.round_bonus_experience :
                    0;
            participant.battle_experience =
                    policy.award_battle_experience ?
                    _battle_experience(
                            session, *unit) :
                    0;
            participant.total_experience =
                    participant.mission_experience +
                    participant.round_bonus_experience +
                    participant.battle_experience;

            participant.before = progression;
            participant.after = progression;
        }
        return result;
    }

    template<std::size_t RosterSize>
    static bool apply_experience(
            battle_result& result,
            std::array<
                    character_progression_record,
                    RosterSize>& roster)
    {
        for(std::size_t index = 0;
                index < result.participant_count;
                ++index)
        {
            battle_result_participant& participant =
                    result.participants[index];
            character_progression_record* progression =
                    _find_progression(
                            roster, participant.character_id);
            if(! progression)
            {
                return false;
            }
            progression->experience +=
                    participant.total_experience;
            participant.after = *progression;
        }
        return true;
    }

    template<std::size_t RosterSize>
    static bool settle_levels(
            battle_result& result,
            std::array<
                    character_progression_record,
                    RosterSize>& roster)
    {
        for(std::size_t index = 0;
                index < result.participant_count;
                ++index)
        {
            battle_result_participant& participant =
                    result.participants[index];
            character_progression_record* progression =
                    _find_progression(
                            roster, participant.character_id);
            if(! progression)
            {
                return false;
            }
            const level_settlement settlement =
                    settle_character_progression(
                            *progression, 0);
            *progression = settlement.after;
            participant.after = settlement.after;
            participant.stat_growth =
                    character_stats_at_level(
                            participant.character_id,
                            participant.after.level) -
                    character_stats_at_level(
                            participant.character_id,
                            participant.before.level);
        }
        return true;
    }

    template<std::size_t MaxUnits, std::size_t RosterSize>
    [[nodiscard]] static battle_result settle(
            const battle_session<MaxUnits>& session,
            const battle_reward_definition& reward,
            int battle_round,
            std::array<
                    character_progression_record,
                    RosterSize>& roster,
            battle_result_policy policy = {})
    {
        battle_result result =
                preview(
                        session,
                        reward,
                        battle_round,
                        roster,
                        policy);
        if(! apply_experience(result, roster) ||
                ! settle_levels(result, roster))
        {
            return {};
        }
        return result;
    }

private:
    template<std::size_t RosterSize>
    [[nodiscard]] static character_progression_record*
    _find_progression(
            std::array<
                    character_progression_record,
                    RosterSize>& roster,
            std::uint8_t character_id)
    {
        for(character_progression_record& progression : roster)
        {
            if(progression.active &&
                    progression.character_id == character_id)
            {
                return &progression;
            }
        }
        return nullptr;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static int _battle_experience(
            const battle_session<MaxUnits>& session,
            const battle_unit_instance& passive_source)
    {
        int result = 0;
        for(std::size_t index = 0;
                index < session.unit_count();
                ++index)
        {
            const battle_unit_instance* unit =
                    session.unit_at(index);
            if(unit && unit->side == battle_side::player &&
                    unit->character_id ==
                            passive_source.character_id)
            {
                result += unit->carried_experience;
            }
        }
        const passive_query_result bonus =
                passive_source.passives.query(
                        battle_experience_passive_target,
                        passive_definitions);
        if(bonus.found)
        {
            result += result * bonus.value_a / 100;
        }
        return result;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static const battle_unit_instance* _find_player_unit(
            const battle_session<MaxUnits>& session,
            std::uint8_t character_id)
    {
        for(std::size_t index = 0;
                index < session.unit_count();
                ++index)
        {
            const battle_unit_instance* unit =
                    session.unit_at(index);
            if(unit && unit->side == battle_side::player &&
                    unit->character_id == character_id)
            {
                return unit;
            }
        }
        return nullptr;
    }
};

}

#endif
