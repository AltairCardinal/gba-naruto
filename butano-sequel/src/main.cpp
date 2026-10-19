#include "bn_core.h"
#include "bn_assert.h"
#include "bn_common.h"

#include "konoha/battle_campaign_route.h"
#include "konoha/battle_campaign_sram.h"
#include "konoha/battle_preparation_scene.h"
#include "konoha/battle_runtime_scene.h"
#include "konoha_bench/self_test.h"

#include <cstddef>
#include <new>

int main()
{
    bn::core::init();

    const konoha_bench::self_test_result self_tests = konoha_bench::run_self_tests();
    BN_ASSERT(self_tests.all_passed(), "Embedded foundation self-tests failed");

    alignas(konoha::battle_campaign_state)
            BN_DATA_EWRAM_BSS static unsigned char
                    campaign_storage[
                            sizeof(konoha::
                                           battle_campaign_state)];
    alignas(konoha::battle_campaign_state)
            BN_DATA_EWRAM_BSS static unsigned char
                    campaign_checkpoint_storage[
                            sizeof(konoha::
                                           battle_campaign_state)];
    constexpr std::size_t campaign_shared_workspace_size =
            sizeof(konoha::battle_campaign_sram_workspace) >
                            sizeof(konoha::
                                           battle_campaign_route_workspace) ?
                    sizeof(konoha::
                                   battle_campaign_sram_workspace) :
                    sizeof(konoha::
                                   battle_campaign_route_workspace);
    alignas(konoha::battle_campaign_sram_workspace)
    alignas(konoha::battle_campaign_route_workspace)
            BN_DATA_EWRAM_BSS static unsigned char
                    campaign_shared_workspace_storage[
                            campaign_shared_workspace_size];
    konoha::battle_campaign_state& campaign =
            *::new(static_cast<void*>(campaign_storage))
                    konoha::battle_campaign_state;
    konoha::battle_campaign_state&
            campaign_checkpoint =
                    *::new(static_cast<void*>(
                                   campaign_checkpoint_storage))
                            konoha::battle_campaign_state;
    konoha::battle_campaign_route_workspace&
            campaign_route_workspace =
                    *reinterpret_cast<konoha::
                            battle_campaign_route_workspace*>(
                                    campaign_shared_workspace_storage);
    konoha::battle_campaign_sram_workspace&
            campaign_sram_workspace =
                    *reinterpret_cast<konoha::
                            battle_campaign_sram_workspace*>(
                                    campaign_shared_workspace_storage);
    campaign_checkpoint =
            konoha::empty_battle_campaign();
    BN_ASSERT(
            konoha::prepare_battle_campaign_stage(
                    campaign_checkpoint,
                    campaign_route_workspace)
                    .success(),
            "Invalid default campaign route");
    BN_ASSERT(
            campaign_checkpoint.party[0] == 1,
            "Invalid default campaign party");
    const konoha::battle_campaign_sram_result loaded =
            konoha::load_battle_campaign_from_sram(
                    campaign_checkpoint,
                    campaign,
                    campaign_sram_workspace);
    BN_ASSERT(
            loaded.success(),
            "Battle campaign SRAM load failed");
    if(! konoha::battle_campaign_route_accepts_saved_scenario(
               campaign.chapter_id))
    {
        campaign = campaign_checkpoint;
    }
    BN_ASSERT(
            konoha::prepare_battle_campaign_stage(
                    campaign,
                    campaign_route_workspace)
                    .success(),
            "Invalid loaded campaign route");

    bool show_preparation_overview = false;
    while(true)
    {
        const konoha::battle_campaign_route_result
                prepared =
                        konoha::
                                prepare_battle_campaign_stage(
                                        campaign,
                                        campaign_route_workspace);
        BN_ASSERT(
                prepared.success(),
                "Invalid battle campaign stage");
        if(prepared.complete)
        {
            bn::core::update();
            continue;
        }
        bool preparation_ready = false;
        while(! preparation_ready)
        {
            campaign_checkpoint = campaign;
            const konoha::battle_preparation_scene_exit
                    preparation_exit =
                            konoha::run_battle_preparation_scene(
                                    campaign,
                                    show_preparation_overview);
            show_preparation_overview = false;
            BN_ASSERT(
                    preparation_exit !=
                            konoha::
                                    battle_preparation_scene_exit::
                                            invalid_campaign,
                    "Invalid battle preparation campaign");
            if(preparation_exit ==
                    konoha::
                            battle_preparation_scene_exit::
                                    save_requested)
            {
                const konoha::battle_campaign_sram_result
                        saved =
                                konoha::
                                        save_battle_campaign_to_sram(
                                                campaign,
                                                campaign_sram_workspace);
                BN_ASSERT(
                        saved.success() && saved.verified,
                        "Battle preparation explicit save failed");
            }
            else
            {
                preparation_ready = true;
            }
        }
        if(campaign != campaign_checkpoint)
        {
            const konoha::battle_campaign_sram_result
                    saved =
                            konoha::
                                    save_battle_campaign_to_sram(
                                            campaign,
                                            campaign_sram_workspace);
            BN_ASSERT(
                    saved.success() && saved.verified,
                    "Battle preparation SRAM save failed");
        }
        campaign_checkpoint = campaign;
        const konoha::battle_runtime_scene_exit
                battle_exit =
                        konoha::run_battle_campaign_stage(
                                campaign);
        const konoha::battle_campaign_route_result
                advanced =
                        konoha::
                                advance_battle_campaign_stage(
                                        campaign,
                                        battle_exit,
                                        campaign_route_workspace);
        if(! advanced.success())
        {
            campaign = campaign_checkpoint;
            BN_ASSERT(
                    false,
                    "Battle campaign route advance failed");
        }
        show_preparation_overview =
                campaign != campaign_checkpoint;
        if(campaign != campaign_checkpoint)
        {
            const konoha::battle_campaign_sram_result
                    saved =
                            konoha::
                                    save_battle_campaign_to_sram(
                                            campaign,
                                            campaign_sram_workspace);
            BN_ASSERT(
                    saved.success() && saved.verified,
                    "Battle campaign SRAM save failed");
        }
    }
}
