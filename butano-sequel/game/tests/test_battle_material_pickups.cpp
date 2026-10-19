#include "konoha/battle_scene_controller.h"
#include "konoha/battle_runtime_grid.h"
#include "konoha/generated_battle_scenario_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_condition_content.h"
#include <cassert>
#include <cstdio>
#include "konoha/battle_campaign_save.h"
#include "konoha/battle_campaign_route.h"
#include "konoha/battle_campaign_scene_progression.h"
using namespace konoha;
int main()
{
    battle_runtime_controller controller;
    assert(controller.load(battle_scenario_definitions[14],
            battle_map_definitions[14], battle_map_cells, 0, {},
            battle_condition_variants[14][0], 49U, {}, false,
            battle_mission_rules_for(14, 0)).success());
    const auto objects = controller.object_snapshot();
    assert(objects.count == 2);
    assert(objects.objects[0].position == grid_point({4, 4}));
    assert(objects.objects[1].position == grid_point({13, 5}));
    assert(controller.start().success());
    assert(controller.tick().success()); // opening escort turn
    assert(controller.confirm().success());
    assert(controller.snapshot().phase == battle_scene_phase::command_selection);
    assert(controller.confirm().success()); // choose Move from the initial menu
    auto state = controller.snapshot();
    while(state.cursor.x != 13 || state.cursor.y != 5)
    {
        const int dx = state.cursor.x < 13 ? 1 : state.cursor.x > 13 ? -1 : 0;
        const int dy = dx ? 0 : state.cursor.y < 5 ? 1 : -1;
        assert(controller.move_cursor(dx, dy).success());
        state = controller.snapshot();
    }
    assert(controller.inventory().materials[4] == 0); // preview is not a pickup
    assert(controller.object_snapshot().count == 2);
    assert(controller.cancel().success());
    assert(controller.inventory().materials[4] == 0); // cancel is not a pickup
    assert(controller.confirm().success());
    state = controller.snapshot();
    while(state.cursor.x != 13 || state.cursor.y != 5)
    {
        const int dx = state.cursor.x < 13 ? 1 : state.cursor.x > 13 ? -1 : 0;
        assert(controller.move_cursor(dx, dx ? 0 : state.cursor.y < 5 ? 1 : -1).success());
        state = controller.snapshot();
    }
    assert(controller.confirm().success());
    for(int i = 0; controller.snapshot().player.selected_command != battle_command_type::end_action && i < 10; ++i)
        assert(controller.move_cursor(0, 1).success());
    assert(controller.confirm().success()); // end confirmation
    assert(controller.confirm().success()); // facing
    assert(controller.inventory().materials[4] == 0);
    assert(controller.confirm().success()); // defense decision
    assert(controller.move_cursor(0, 1).success()); // no defense
    assert(controller.confirm().success()); // complete action on chest cell
    assert(controller.inventory().materials[4] == 1);
    assert(controller.object_snapshot().count == 1);
    assert(controller.last_pickup().material_id == 4);
    assert(controller.last_pickup().sequence == 1);

    // Collection itself is single-use, honors the cap and never uses facing.
    battle_session<12> session;
    battle_unit_instance actor;
    actor.id = 1; actor.active = true; actor.side = battle_side::player;
    actor.hp = 100; actor.max_hp = 100;
    actor.position = {4, 4}; actor.facing = battle_facing::right;
    assert(session.add_unit(actor));
    assert(battle_material_pickups::initialize(session, 14, 0));
    battle_campaign_inventory inventory;
    inventory.materials[3] = 99;
    battle_material_pickup receipt;
    battle_material_pickups::complete_action(session, 1, inventory, receipt);
    assert(inventory.materials[3] == 99 && receipt.sequence == 1 && ! receipt.added);
    assert(session.objects().record(1)->type == 0);
    battle_material_pickups::complete_action(session, 1, inventory, receipt);
    assert(receipt.sequence == 1);

    auto campaign = empty_battle_campaign();
    battle_campaign_route_workspace workspace;
    assert(prepare_battle_campaign_stage(campaign, workspace).success());
    battle_campaign_scene_progression progression;
    assert(progression.begin(campaign) == battle_campaign_error::none);
    progression.materials() = controller.inventory().materials;
    assert(progression.commit(campaign) == battle_campaign_error::none);
    battle_campaign_save_slot bytes;
    assert(encode_battle_campaign_slot(campaign, 1, bytes) == battle_campaign_save_error::none);
    const auto restored = decode_battle_campaign_slot(bytes);
    assert(restored.valid());
    assert(restored.campaign.inventory.materials[4] == 1);
}
