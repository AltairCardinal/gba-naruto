#ifndef KONOHA_BATTLE_CAMPAIGN_ROUTE_H
#define KONOHA_BATTLE_CAMPAIGN_ROUTE_H

#include "konoha/battle_campaign.h"
#include "konoha/battle_runtime_result.h"

#include <array>
#include <cstdint>

namespace konoha
{

inline constexpr std::uint16_t
        battle_campaign_route_initial_scenario = 49;
inline constexpr std::uint16_t
        battle_campaign_route_complete_scenario = 56;

enum class battle_campaign_party_policy : std::uint8_t
{
    naruto,
    team_seven,
};

struct battle_campaign_stage_definition
{
    std::uint16_t scenario_id = 0;
    std::uint8_t battle_id = 0;
    std::uint8_t variant = 0;
    std::uint16_t next_scenario_id = 0;
    battle_campaign_party_policy party_policy =
            battle_campaign_party_policy::naruto;
    const char* title = "";
};

inline constexpr std::array<
        battle_campaign_stage_definition,
        9> battle_campaign_stages = {{
    { 41, 41, 0, 42,
      battle_campaign_party_policy::naruto, "S41" },
    { 42, 42, 0, 43,
      battle_campaign_party_policy::naruto, "S42" },
    { 43, 43, 0, 44,
      battle_campaign_party_policy::naruto, "S43" },
    { 44, 44, 0, 45,
      battle_campaign_party_policy::team_seven, "S44" },
    { 45, 45, 0, 46,
      battle_campaign_party_policy::team_seven, "S45" },
    { 46, 9, 0, 47,
      battle_campaign_party_policy::team_seven, "S46" },
    { 47, 13, 0, 49,
      battle_campaign_party_policy::team_seven, "S47" },
    { 49, 14, 0, 50,
      battle_campaign_party_policy::team_seven, "S49" },
    { 50, 15, 0, battle_campaign_route_complete_scenario,
      battle_campaign_party_policy::team_seven, "S50" },
}};

enum class battle_campaign_route_error : std::uint8_t
{
    none,
    unknown_scenario,
    invalid_roster,
};

struct battle_campaign_stage_result
{
    battle_campaign_route_error error =
            battle_campaign_route_error::none;
    const battle_campaign_stage_definition* stage =
            nullptr;
    bool complete = false;

    [[nodiscard]] constexpr bool success() const
    {
        return error ==
                battle_campaign_route_error::none;
    }
};

struct battle_campaign_route_result
{
    battle_campaign_route_error error =
            battle_campaign_route_error::none;
    bool changed = false;
    bool complete = false;

    [[nodiscard]] constexpr bool success() const
    {
        return error ==
                battle_campaign_route_error::none;
    }
};

struct battle_campaign_route_workspace
{
    battle_campaign_state draft;
};

[[nodiscard]] constexpr battle_campaign_stage_result
battle_campaign_stage_for(std::uint16_t scenario_id)
{
    if(scenario_id ==
            battle_campaign_route_complete_scenario)
    {
        return {
            battle_campaign_route_error::none,
            nullptr,
            true,
        };
    }
    for(const battle_campaign_stage_definition& stage :
            battle_campaign_stages)
    {
        if(stage.scenario_id == scenario_id)
        {
            return {
                battle_campaign_route_error::none,
                &stage,
                false,
            };
        }
    }
    return {
        battle_campaign_route_error::unknown_scenario,
    };
}

[[nodiscard]] constexpr bool
battle_campaign_route_accepts_saved_scenario(
        std::uint16_t scenario_id)
{
    const battle_campaign_stage_result stage =
            battle_campaign_stage_for(scenario_id);
    return stage.success() &&
            (stage.complete ||
             scenario_id >=
                     battle_campaign_route_initial_scenario);
}

[[nodiscard]] inline bool
ensure_battle_campaign_character(
        battle_campaign_state& campaign,
        std::uint8_t character_id,
        int level,
        int experience)
{
    if(character_id >= campaign.characters.size())
    {
        return false;
    }
    if(campaign.characters[character_id]
               .progression.active)
    {
        return true;
    }
    character_progression_record progression;
    progression.character_id = character_id;
    progression.level = level;
    progression.experience = experience;
    progression.active = true;
    return activate_battle_campaign_character(
            campaign,
            progression);
}

[[nodiscard]] inline battle_campaign_route_result
prepare_battle_campaign_stage_in_place(
        battle_campaign_state& campaign)
{
    const bool initialize_defaults =
            campaign.chapter_id == 0;
    if(campaign.chapter_id == 0)
    {
        campaign.chapter_id =
                battle_campaign_route_initial_scenario;
    }
    const battle_campaign_stage_result resolved =
            battle_campaign_stage_for(
                    campaign.chapter_id);
    if(! resolved.success())
    {
        return {
            resolved.error,
        };
    }
    if(resolved.complete)
    {
        return {
            battle_campaign_route_error::none,
            false,
            true,
        };
    }

    if(! ensure_battle_campaign_character(
               campaign,
               1,
               initialize_defaults ? 5 : 1,
               // The original's battle 14 entry carries 160 experience for
               // Naruto (read from the original's unit pool at the entry
               // checkpoint); 85 was a guess that left the party short.
               initialize_defaults ? 160 : 100))
    {
        return {
            battle_campaign_route_error::
                    invalid_roster,
        };
    }
    std::array<std::uint8_t, 3> party = {
        1,
        0,
        0,
    };
    if(resolved.stage->party_policy ==
            battle_campaign_party_policy::team_seven)
    {
        if(! ensure_battle_campaign_character(
                   campaign,
                   2,
                   initialize_defaults ? 4 : 1,
                   // The original's battle 14 entry carries 100 experience for
                   // Sasuke (same read as Naruto's, above).
                   initialize_defaults ? 100 : 100) ||
                ! ensure_battle_campaign_character(
                        campaign,
                        3,
                        initialize_defaults ? 5 : 1,
                        // The original's battle 14 entry carries 190
                        // experience for Sakura (same read as above).
                        initialize_defaults ? 190 : 0))
        {
            return {
                battle_campaign_route_error::
                        invalid_roster,
            };
        }
        party = { 1, 2, 3 };
    }
    if(! set_battle_campaign_party(campaign, party))
    {
        return {
            battle_campaign_route_error::
                    invalid_roster,
        };
    }
    if(initialize_defaults)
    {
        campaign.characters[1]
                .progression.training_points = 4;
        campaign.characters[2]
                .progression.training_points = 3;
        campaign.characters[3]
                .progression.training_points = 4;
        campaign.characters[1].equipped_tools = {
            1,
            11,
            37,
        };
        campaign.inventory.ninja_tools[1] = 1;
        campaign.inventory.ninja_tools[11] = 1;
        campaign.inventory.ninja_tools[37] = 1;
        campaign.inventory.ninja_tools[67] = 1;
        campaign.inventory.materials[6] = 1;
    }

    return {
        battle_campaign_route_error::none,
        false,
        false,
    };
}

[[nodiscard]] inline battle_campaign_route_result
prepare_battle_campaign_stage(
        battle_campaign_state& campaign,
        battle_campaign_route_workspace& workspace)
{
    workspace.draft = campaign;
    const battle_campaign_route_result prepared =
            prepare_battle_campaign_stage_in_place(
                    workspace.draft);
    if(! prepared.success())
    {
        return prepared;
    }
    const bool changed =
            workspace.draft != campaign;
    campaign = workspace.draft;
    return {
        battle_campaign_route_error::none,
        changed,
        prepared.complete,
    };
}

[[nodiscard]] inline battle_campaign_route_result
prepare_battle_campaign_stage(
        battle_campaign_state& campaign)
{
    battle_campaign_route_workspace workspace;
    return prepare_battle_campaign_stage(
            campaign,
            workspace);
}

[[nodiscard]] inline battle_campaign_route_result
advance_battle_campaign_stage(
        battle_campaign_state& campaign,
        battle_runtime_scene_exit exit,
        battle_campaign_route_workspace& workspace)
{
    const battle_campaign_stage_result current =
            battle_campaign_stage_for(
                    campaign.chapter_id);
    if(! current.success())
    {
        return {
            current.error,
        };
    }
    if(current.complete ||
            ! battle_runtime_exit_advances_campaign(
                    exit))
    {
        return {
            battle_campaign_route_error::none,
            false,
            current.complete,
        };
    }

    workspace.draft = campaign;
    workspace.draft.chapter_id =
            current.stage->next_scenario_id;
    const battle_campaign_route_result prepared =
            prepare_battle_campaign_stage_in_place(
                    workspace.draft);
    if(! prepared.success())
    {
        return prepared;
    }
    campaign = workspace.draft;
    return {
        battle_campaign_route_error::none,
        true,
        prepared.complete,
    };
}

[[nodiscard]] inline battle_campaign_route_result
advance_battle_campaign_stage(
        battle_campaign_state& campaign,
        battle_runtime_scene_exit exit)
{
    battle_campaign_route_workspace workspace;
    return advance_battle_campaign_stage(
            campaign,
            exit,
            workspace);
}

}

#endif
