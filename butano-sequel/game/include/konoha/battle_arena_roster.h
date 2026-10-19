#ifndef KONOHA_BATTLE_ARENA_ROSTER_H
#define KONOHA_BATTLE_ARENA_ROSTER_H

#include "konoha/battle_scenario_loader.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr std::size_t
        battle_arena_team_capacity = 3;

struct battle_arena_combatant
{
    character_progression_record progression = {};
    std::array<
            ninja_tool_id,
            battle_ninja_tool_slot_capacity>
            equipped_tools = {};

    constexpr bool operator==(
            const battle_arena_combatant&) const = default;
};

struct battle_arena_match_roster
{
    std::array<
            battle_arena_combatant,
            battle_arena_team_capacity>
            player = {};
    std::array<
            battle_arena_combatant,
            battle_arena_team_capacity>
            opponent = {};

    constexpr bool operator==(
            const battle_arena_match_roster&) const = default;
};

enum class battle_arena_roster_error : std::uint8_t
{
    none,
    empty_player,
    empty_opponent,
    invalid_character,
    inactive_character,
    invalid_level,
    invalid_progression,
    invalid_ninja_tool,
};

[[nodiscard]] constexpr battle_arena_roster_error
apply_battle_arena_scene_policy(
        const battle_arena_match_roster& roster,
        battle_scenario_load_policy& policy)
{
    battle_scenario_load_policy draft = policy;
    bool player_active = false;
    bool opponent_active = false;

    for(std::size_t side_index = 0;
            side_index < 2;
            ++side_index)
    {
        const auto& team = side_index == 0 ?
                roster.player : roster.opponent;
        for(std::size_t team_index = 0;
                team_index < team.size();
                ++team_index)
        {
            const std::size_t placeholder_index =
                    side_index *
                            battle_arena_team_capacity +
                    team_index;
            const battle_arena_combatant& combatant =
                    team[team_index];
            draft.placeholder_enabled_overridden[
                    placeholder_index] = true;
            if(! combatant.progression.active)
            {
                draft.placeholder_enabled[
                        placeholder_index] = false;
                draft.placeholder_characters[
                        placeholder_index] =
                                no_scenario_character;
                draft.placeholder_progression[
                        placeholder_index] = nullptr;
                draft.placeholder_equipped_tools[
                        placeholder_index] = nullptr;
                continue;
            }

            if(side_index == 0)
            {
                player_active = true;
            }
            else
            {
                opponent_active = true;
            }

            const std::size_t character_id =
                    combatant.progression.character_id;
            if(character_id == 0 ||
                    character_id >=
                            unit_definitions.size())
            {
                return battle_arena_roster_error::
                        invalid_character;
            }
            if(! unit_definitions[character_id].active)
            {
                return battle_arena_roster_error::
                        inactive_character;
            }
            if(combatant.progression.level < 1 ||
                    combatant.progression.level > 50)
            {
                return battle_arena_roster_error::
                        invalid_level;
            }

            character_progression_record progression =
                    combatant.progression;
            if(! progression.action_states_initialized ||
                    ! synchronize_character_action_unlocks(
                       progression,
                       unit_definitions[character_id]))
            {
                return battle_arena_roster_error::
                        invalid_progression;
            }
            for(const ninja_tool_id tool :
                    combatant.equipped_tools)
            {
                if(tool >=
                                ninja_tool_action_definitions
                                        .size() ||
                        ninja_tool_action_definitions[tool]
                                        .id != tool)
                {
                    return battle_arena_roster_error::
                            invalid_ninja_tool;
                }
            }

            draft.placeholder_enabled[
                    placeholder_index] = true;
            draft.placeholder_characters[
                    placeholder_index] =
                            static_cast<std::uint8_t>(
                                    character_id);
            draft.placeholder_progression[
                    placeholder_index] =
                            &combatant.progression;
            draft.placeholder_equipped_tools[
                    placeholder_index] =
                            &combatant.equipped_tools;
        }
    }

    if(! player_active)
    {
        return battle_arena_roster_error::empty_player;
    }
    if(! opponent_active)
    {
        return battle_arena_roster_error::empty_opponent;
    }

    policy = draft;
    return battle_arena_roster_error::none;
}

}

#endif
