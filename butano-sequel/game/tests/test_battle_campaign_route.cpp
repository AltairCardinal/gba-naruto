#include "konoha/battle_campaign_route.h"

#include <array>
#include <cassert>
#include <cstdint>

using namespace konoha;

namespace
{

struct expected_stage
{
    std::uint16_t scenario_id;
    std::uint8_t battle_id;
    std::uint16_t next_scenario_id;
};

}

int main()
{
    // This acceptance ROM is scoped to the Konohamaru escort mission.
    // An empty/new campaign must therefore enter scenario 49 / battle 14,
    // rather than the earlier Naruto-versus-Konohamaru tutorial.
    static_assert(battle_campaign_route_initial_scenario == 49);
    const battle_campaign_stage_result initial_stage =
            battle_campaign_stage_for(
                    battle_campaign_route_initial_scenario);
    assert(initial_stage.success());
    assert(initial_stage.stage);
    assert(initial_stage.stage->battle_id == 14);
    assert(! battle_campaign_route_accepts_saved_scenario(41));
    assert(! battle_campaign_route_accepts_saved_scenario(47));
    assert(battle_campaign_route_accepts_saved_scenario(49));
    assert(battle_campaign_route_accepts_saved_scenario(50));
    assert(battle_campaign_route_accepts_saved_scenario(
            battle_campaign_route_complete_scenario));

    constexpr std::array<expected_stage, 9> expected = {{
        { 41, 41, 42 },
        { 42, 42, 43 },
        { 43, 43, 44 },
        { 44, 44, 45 },
        { 45, 45, 46 },
        { 46, 9, 47 },
        { 47, 13, 49 },
        { 49, 14, 50 },
        { 50, 15, battle_campaign_route_complete_scenario },
    }};

    for(const expected_stage& item : expected)
    {
        const battle_campaign_stage_result resolved =
                battle_campaign_stage_for(item.scenario_id);
        assert(resolved.success());
        assert(! resolved.complete);
        assert(resolved.stage);
        assert(resolved.stage->scenario_id ==
               item.scenario_id);
        assert(resolved.stage->battle_id ==
               item.battle_id);
        assert(resolved.stage->variant == 0);
        assert(resolved.stage->next_scenario_id ==
               item.next_scenario_id);
    }

    const battle_campaign_stage_result terminal =
            battle_campaign_stage_for(
                    battle_campaign_route_complete_scenario);
    assert(terminal.success());
    assert(terminal.complete);
    assert(! terminal.stage);

    const battle_campaign_stage_result unknown =
            battle_campaign_stage_for(40);
    assert(! unknown.success());
    assert(unknown.error ==
           battle_campaign_route_error::unknown_scenario);

    battle_campaign_state campaign =
            empty_battle_campaign();
    const battle_campaign_route_result prepared =
            prepare_battle_campaign_stage(campaign);
    assert(prepared.success());
    assert(prepared.changed);
    assert(campaign.chapter_id == 49);
    assert(campaign.party ==
           (std::array<std::uint8_t, 3>{ 1, 2, 3 }));
    assert(campaign.characters[1].progression.active);
    assert(campaign.characters[1].progression.level == 5);
    assert(campaign.characters[1].progression.experience ==
           85);
    assert(campaign.characters[1].progression.training_points ==
           4);
    assert(campaign.characters[2].progression.active);
    assert(campaign.characters[2].progression.level == 4);
    assert(campaign.characters[2].progression.experience ==
           150);
    assert(campaign.characters[2].progression.training_points ==
           3);
    assert(campaign.characters[3].progression.active);
    assert(campaign.characters[3].progression.level == 5);
    assert(campaign.characters[3].progression.experience ==
           115);
    assert(campaign.characters[3].progression.training_points ==
           4);
    assert(campaign.characters[1].equipped_tools[0] == 1);
    assert(campaign.characters[1].equipped_tools[1] == 11);
    assert(campaign.characters[1].equipped_tools[2] == 37);
    assert(campaign.inventory.ninja_tools[1] == 1);
    assert(campaign.inventory.ninja_tools[11] == 1);
    assert(campaign.inventory.ninja_tools[37] == 1);
    assert(campaign.inventory.ninja_tools[67] == 1);
    assert(campaign.inventory.materials[6] == 1);

    const battle_campaign_state before_abort = campaign;
    const battle_campaign_route_result aborted =
            advance_battle_campaign_stage(
                    campaign,
                    battle_runtime_scene_exit::aborted);
    assert(aborted.success());
    assert(! aborted.changed);
    assert(campaign == before_abort);

    const battle_campaign_route_result defeated =
            advance_battle_campaign_stage(
                    campaign,
                    battle_runtime_scene_exit::defeat);
    assert(defeated.success());
    assert(! defeated.changed);
    assert(campaign == before_abort);

    const battle_campaign_route_result drawn =
            advance_battle_campaign_stage(
                    campaign,
                    battle_runtime_scene_exit::draw);
    assert(drawn.success());
    assert(! drawn.changed);
    assert(campaign == before_abort);

    const battle_campaign_route_result won =
            advance_battle_campaign_stage(
                    campaign,
                    battle_runtime_scene_exit::victory);
    assert(won.success());
    assert(won.changed);
    assert(campaign.chapter_id == 50);

    character_progression_record sasuke;
    sasuke.character_id = 2;
    sasuke.level = 5;
    sasuke.experience = 27;
    sasuke.training_points = 3;
    sasuke.active = true;
    assert(initialize_character_action_progression(
            sasuke,
            unit_definitions[2]));
    assert(activate_battle_campaign_character(
            campaign,
            sasuke));
    campaign.chapter_id = 44;

    const battle_campaign_route_result team_seven =
            prepare_battle_campaign_stage(campaign);
    assert(team_seven.success());
    assert(! team_seven.changed);
    assert(campaign.party ==
           (std::array<std::uint8_t, 3>{ 1, 2, 3 }));
    assert(campaign.characters[2].progression == sasuke);
    assert(campaign.characters[3].progression.active);
    assert(campaign.characters[3].progression.level == 5);

    campaign.chapter_id = 47;
    assert(advance_battle_campaign_stage(
                   campaign,
                   battle_runtime_scene_exit::victory)
                   .success());
    assert(campaign.chapter_id == 49);

    campaign.chapter_id = 50;
    const battle_campaign_route_result completed =
            advance_battle_campaign_stage(
                    campaign,
                    battle_runtime_scene_exit::victory);
    assert(completed.success());
    assert(completed.changed);
    assert(completed.complete);
    assert(campaign.chapter_id ==
           battle_campaign_route_complete_scenario);
}
