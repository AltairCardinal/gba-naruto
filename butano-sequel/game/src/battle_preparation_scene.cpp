#include "konoha/battle_preparation_scene.h"

#include "bn_bg_palettes.h"
#include "bn_color.h"
#include "bn_core.h"
#include "bn_keypad.h"
#include "bn_optional.h"
#include "bn_regular_bg_ptr.h"
#include "bn_regular_bg_items_battle_01_map_chunk_0.h"
#include "bn_regular_bg_items_battle_preparation_background.h"
#include "bn_regular_bg_items_battle_preparation_overview_background.h"
#include "bn_sprite_palette_ptr.h"
#include "bn_sprite_ptr.h"
#include "bn_sprite_items_battle_ui_confirmation_cursor.h"
#include "bn_sprite_items_battle_ui_preparation_cursor.h"
#include "bn_sprite_items_battle_ui_preparation_dialog_panel.h"
#include "bn_sprite_items_battle_ui_preparation_menu_panel.h"
#include "bn_sprite_palette_items_battle_ui_preparation_accent_palette.h"
#include "bn_sprite_palette_items_battle_ui_preparation_text_palette.h"
#include "bn_sprite_palette_items_battle_ui_result_total_palette.h"
#include "bn_sprite_text_generator.h"
#include "bn_string.h"
#include "bn_vector.h"

#include "konoha/battle_preparation_sprite_font.h"
#include "konoha/battle_audio_runtime.h"
#include "konoha/battle_preparation_flow.h"

#include <cstddef>

namespace konoha
{

namespace
{

constexpr int preparation_text_sprite_capacity = 96;
constexpr int preparation_panel_sprite_capacity = 10;

bool uses_mission_background(
        battle_preparation_phase phase)
{
    return phase == battle_preparation_phase::overview ||
            phase == battle_preparation_phase::root ||
            phase ==
                    battle_preparation_phase::
                            start_confirmation;
}

const char* upgrade_error_text(
        ninja_tool_upgrade_error error)
{
    switch(error)
    {
    case ninja_tool_upgrade_error::none:
        return "UPGRADE COMPLETE";
    case ninja_tool_upgrade_error::
            invalid_output_tool:
        return "INVALID TOOL";
    case ninja_tool_upgrade_error::no_recipe:
        return "NO UPGRADE AVAILABLE";
    case ninja_tool_upgrade_error::
            missing_parent_tool:
        return "PARENT TOOL MISSING";
    case ninja_tool_upgrade_error::missing_material:
        return "MATERIAL MISSING";
    case ninja_tool_upgrade_error::output_full:
        return "OUTPUT BAG FULL";
    case ninja_tool_upgrade_error::
            invalid_character:
        return "INVALID CHARACTER";
    case ninja_tool_upgrade_error::
            inactive_character:
        return "CHARACTER INACTIVE";
    case ninja_tool_upgrade_error::
            parent_not_equipped:
        return "TOOL NOT EQUIPPED";
    case ninja_tool_upgrade_error::
            character_not_eligible:
        return "CHARACTER NOT ELIGIBLE";
    case ninja_tool_upgrade_error::
            parent_copy_equipped:
        return "NO UNEQUIPPED COPY";
    }
    return "UPGRADE ERROR";
}

const char* equipment_error_text(
        battle_preparation_operation operation,
        battle_campaign_equipment_error error)
{
    switch(error)
    {
    case battle_campaign_equipment_error::none:
        return operation ==
                        battle_preparation_operation::equip ?
                "EQUIP COMPLETE" :
                "UNEQUIP COMPLETE";
    case battle_campaign_equipment_error::
            invalid_character:
        return "INVALID CHARACTER";
    case battle_campaign_equipment_error::
            inactive_character:
        return "CHARACTER INACTIVE";
    case battle_campaign_equipment_error::invalid_tool:
        return "INVALID TOOL";
    case battle_campaign_equipment_error::invalid_slot:
        return "INVALID SLOT";
    case battle_campaign_equipment_error::
            character_not_eligible:
        return "CHARACTER NOT ELIGIBLE";
    case battle_campaign_equipment_error::
            no_available_copy:
        return "NO AVAILABLE TOOL";
    case battle_campaign_equipment_error::
            capacity_reached:
        return "TOOL CAPACITY FULL";
    case battle_campaign_equipment_error::no_empty_slot:
        return "NO EMPTY SLOT";
    case battle_campaign_equipment_error::empty_slot:
        return "NO EQUIPPED TOOL";
    }
    return "EQUIPMENT ERROR";
}

void append_tool_slots(
        const battle_campaign_state& campaign,
        std::uint8_t character_id,
        bn::string<64>& output)
{
    output = "EQUIP";
    const auto& tools =
            campaign.characters[character_id]
                    .equipped_tools;
    for(std::size_t index = 0;
            index < 3;
            ++index)
    {
        output += " ";
        output += bn::to_string<4>(tools[index]);
    }
}

void render_preparation_root_content(
        bn::sprite_text_generator& generator,
        bn::vector<
                bn::sprite_ptr,
                preparation_text_sprite_capacity>& sprites)
{
    generator.generate(
            -40, -16, "队伍·装备", sprites);
    generator.generate(
            -40, 0, "查看地图", sprites);
    generator.generate(
            -40, 16, "开始任务", sprites);
    generator.generate(
            -40, 32, "储存", sprites);
}

void render_preparation_mission_content(
        const battle_campaign_state& campaign,
        bn::sprite_text_generator& generator,
        bn::vector<
                bn::sprite_ptr,
                preparation_text_sprite_capacity>& sprites)
{
    const bool puppet_mission =
            campaign.chapter_id >= 50;
    generator.set_center_alignment();
    generator.set_palette_item(
            bn::sprite_palette_items::
                    battle_ui_preparation_accent_palette);
    generator.generate(
            0,
            -64,
            puppet_mission ?
                    "保护木叶丸不被傀儡人偶攻击！" :
                    "保护木叶丸不被蜜蜂攻击！",
            sprites);
    generator.set_left_alignment();
    generator.set_palette_item(
            bn::sprite_palette_items::
                    battle_ui_preparation_text_palette);
    generator.generate(-112, -32, "保护木叶丸不受", sprites);
    generator.set_palette_item(
            bn::sprite_palette_items::
                    battle_ui_result_total_palette);
    generator.generate(
            -56,
            -32,
            puppet_mission ? "傀儡人偶" : "蜜蜂",
            sprites);
    generator.set_palette_item(
            bn::sprite_palette_items::
                    battle_ui_preparation_text_palette);
    generator.generate(
            puppet_mission ? -24 : -40,
            -32,
            "攻击。",
            sprites);
    generator.generate(
            -112,
            -16,
            puppet_mission ?
                    "木叶丸不会攻击，" :
                    "木叶丸擅自到处跑，所以不能攻击。",
            sprites);
    generator.generate(
            -112,
            0,
            puppet_mission ?
                    "所以不要让他去接近危险品。" :
                    "蜜蜂可以通过行动影响他。",
            sprites);
    generator.generate(-112, 32, "保护", sprites);
    generator.set_palette_item(
            bn::sprite_palette_items::
                    battle_ui_preparation_accent_palette);
    generator.generate(-96, 32, "木叶丸", sprites);
    generator.set_palette_item(
            bn::sprite_palette_items::
                    battle_ui_preparation_text_palette);
    generator.generate(-72, 32, "的同时", sprites);
    generator.generate(-112, 48, "把", sprites);
    generator.set_palette_item(
            bn::sprite_palette_items::
                    battle_ui_preparation_accent_palette);
    generator.generate(
            -104,
            48,
            puppet_mission ?
                    "所有的傀儡人偶" :
                    "所有的蜜蜂",
            sprites);
    generator.set_palette_item(
            bn::sprite_palette_items::
                    battle_ui_preparation_text_palette);
    generator.generate(
            puppet_mission ? -48 : -64,
            48,
            "都赶走任务就算结束",
            sprites);
}

void add_preparation_menu_slice(
        int x,
        int y,
        int graphics_index,
        bn::vector<
                bn::sprite_ptr,
                preparation_panel_sprite_capacity>& sprites)
{
    bn::sprite_ptr sprite =
            bn::sprite_items::
                    battle_ui_preparation_menu_panel
                            .create_sprite(
                                    x,
                                    y,
                                    graphics_index);
    sprite.set_bg_priority(0);
    sprite.set_z_order(40);
    sprites.push_back(
            static_cast<bn::sprite_ptr&&>(sprite));
}

void render_preparation_menu_panel(
        bn::vector<
                bn::sprite_ptr,
                preparation_panel_sprite_capacity>& sprites)
{
    add_preparation_menu_slice(-32, -24, 0, sprites);
    add_preparation_menu_slice(32, -24, 1, sprites);
    add_preparation_menu_slice(-32, 40, 2, sprites);
    add_preparation_menu_slice(32, 40, 3, sprites);
}

void add_preparation_root_cursor(
        int x,
        int y,
        bn::vector<
                bn::sprite_ptr,
                preparation_panel_sprite_capacity>& sprites)
{
    const bn::sprite_item& item =
            bn::sprite_items::
                    battle_ui_preparation_cursor;
    bn::sprite_ptr sprite =
            item.create_sprite(x, y);
    sprite.set_palette(
            item.palette_item().create_new_palette());
    sprite.set_bg_priority(0);
    sprite.set_z_order(30);
    sprites.push_back(
            static_cast<bn::sprite_ptr&&>(sprite));
}

void render_preparation_root_cursor(
        const battle_preparation_snapshot& state,
        bn::vector<
                bn::sprite_ptr,
                preparation_panel_sprite_capacity>& sprites)
{
    switch(state.root_option)
    {
    case battle_preparation_root_option::party_equipment:
        add_preparation_root_cursor(-44, -16, sprites);
        break;
    case battle_preparation_root_option::inspect_map:
        add_preparation_root_cursor(-44, 0, sprites);
        break;
    case battle_preparation_root_option::start_battle:
        add_preparation_root_cursor(-44, 16, sprites);
        break;
    case battle_preparation_root_option::save:
        add_preparation_root_cursor(-44, 32, sprites);
        break;
    }
}

void add_preparation_dialog_slice(
        int x,
        int graphics_index,
        bn::vector<
                bn::sprite_ptr,
                preparation_panel_sprite_capacity>& sprites)
{
    bn::sprite_ptr sprite =
            bn::sprite_items::
                    battle_ui_preparation_dialog_panel
                            .create_sprite(
                                    x,
                                    8,
                                    graphics_index);
    sprite.set_bg_priority(0);
    sprite.set_z_order(20);
    sprites.push_back(
            static_cast<bn::sprite_ptr&&>(sprite));
}

void render_preparation_dialog(
        bn::vector<
                bn::sprite_ptr,
                preparation_panel_sprite_capacity>& sprites)
{
    add_preparation_dialog_slice(-64, 0, sprites);
    add_preparation_dialog_slice(-32, 1, sprites);
    add_preparation_dialog_slice(0, 1, sprites);
    add_preparation_dialog_slice(32, 1, sprites);
    add_preparation_dialog_slice(64, 2, sprites);
}

void render_preparation_confirmation_cursor(
        const battle_preparation_snapshot& state,
        bn::vector<
                bn::sprite_ptr,
                preparation_panel_sprite_capacity>& sprites)
{
    bn::sprite_ptr sprite =
            bn::sprite_items::
                    battle_ui_confirmation_cursor
                            .create_sprite(
                                    44,
                                    state.start_confirmation_yes ?
                                            0 :
                                            16);
    sprite.set_bg_priority(0);
    sprite.set_z_order(10);
    sprites.push_back(
            static_cast<bn::sprite_ptr&&>(sprite));
}

void render_preparation_text(
        const battle_preparation_snapshot& state,
        const battle_campaign_state& campaign,
        bn::sprite_text_generator& generator,
        bn::vector<
                bn::sprite_ptr,
                preparation_text_sprite_capacity>& sprites,
        bn::vector<
                bn::sprite_ptr,
                preparation_panel_sprite_capacity>& panel_sprites)
{
    sprites.clear();
    panel_sprites.clear();
    generator.set_left_alignment();

    if(state.phase == battle_preparation_phase::overview ||
            state.phase == battle_preparation_phase::root ||
            state.phase ==
                    battle_preparation_phase::
                            start_confirmation)
    {
        render_preparation_mission_content(
                campaign, generator, sprites);
    }
    const std::size_t mission_sprite_count =
            sprites.size();

    if(state.phase == battle_preparation_phase::overview)
    {
        return;
    }

    if(state.phase == battle_preparation_phase::root)
    {
        for(std::size_t index = 0;
                index < mission_sprite_count;
                ++index)
        {
            sprites[index].set_z_order(50);
        }
        render_preparation_menu_panel(panel_sprites);
        render_preparation_root_cursor(
                state, panel_sprites);
        const std::size_t root_sprite_start =
                sprites.size();
        render_preparation_root_content(
                generator, sprites);
        for(std::size_t index = root_sprite_start;
                index < sprites.size();
                ++index)
        {
            sprites[index].set_z_order(30);
        }
        return;
    }

    if(state.phase ==
            battle_preparation_phase::equipment_root)
    {
        generator.set_center_alignment();
        generator.generate(
                0, -68, "队伍·装备", sprites);
        generator.set_left_alignment();
        bn::string<64> character = "角色 ";
        character += bn::to_string<4>(
                state.character_id);
        character += "  队伍 ";
        character += bn::to_string<4>(
                static_cast<int>(state.party_index + 1));
        character += "/";
        character += bn::to_string<4>(
                static_cast<int>(state.party_count));
        generator.generate(-108, -46, character, sprites);
        bn::string<64> equipped;
        append_tool_slots(
                campaign, state.character_id, equipped);
        generator.generate(-108, -30, equipped, sprites);
        generator.generate(
                -52,
                -6,
                state.equipment_option ==
                                battle_preparation_equipment_option::
                                        equip ?
                        "> 装备忍具" :
                        "  装备忍具",
                sprites);
        generator.generate(
                -52,
                10,
                state.equipment_option ==
                                battle_preparation_equipment_option::
                                        unequip ?
                        "> 卸下忍具" :
                        "  卸下忍具",
                sprites);
        generator.generate(
                -52,
                26,
                state.equipment_option ==
                                battle_preparation_equipment_option::
                                        upgrade ?
                        "> 强化忍具" :
                        "  强化忍具",
                sprites);
        generator.generate(
                -52,
                42,
                state.equipment_option ==
                                battle_preparation_equipment_option::
                                        back ?
                        "> 返回" :
                        "  返回",
                sprites);
        generator.generate(
                -108,
                60,
                "A:确定  B:返回  L/R:角色",
                sprites);
        return;
    }

    if(state.phase ==
            battle_preparation_phase::map_preview)
    {
        generator.generate(
                -108, 60, "地图预览  A/B:返回", sprites);
        return;
    }

    if(state.phase ==
            battle_preparation_phase::
                    start_confirmation)
    {
        for(std::size_t index = 0;
                index < mission_sprite_count;
                ++index)
        {
            sprites[index].set_z_order(50);
        }
        render_preparation_dialog(panel_sprites);
        render_preparation_confirmation_cursor(
                state, panel_sprites);
        generator.generate(
                -72, 0, "开始任务吗？", sprites);
        generator.generate(
                48, 0, "是", sprites);
        generator.generate(
                48, 16, "否", sprites);
        return;
    }

    if(state.phase == battle_preparation_phase::equip ||
            state.phase ==
                    battle_preparation_phase::unequip)
    {
        bn::string<64> progress =
                state.phase ==
                                battle_preparation_phase::
                                        equip ?
                        "AVAILABLE " :
                        "EQUIPPED ";
        progress += bn::to_string<4>(
                static_cast<int>(
                        state.equipment_index + 1));
        progress += "/";
        progress += bn::to_string<4>(
                static_cast<int>(
                        state.equipment_count));
        generator.generate(
                -116, -16, progress, sprites);

        bn::string<64> tool = "TOOL ";
        tool += bn::to_string<4>(
                state.equipment_tool_id);
        if(state.phase ==
                battle_preparation_phase::unequip)
        {
            tool += "  SLOT ";
            tool += bn::to_string<4>(
                    static_cast<int>(
                            state.equipment_slot + 1));
        }
        generator.generate(-116, 2, tool, sprites);

        bn::string<64> quantities = "OWNED ";
        quantities += bn::to_string<4>(
                state.equipment_owned_quantity);
        quantities += "  USED ";
        quantities += bn::to_string<4>(
                static_cast<int>(
                        state.equipment_equipped_quantity));
        generator.generate(
                -116, 20, quantities, sprites);

        bn::string<64> action =
                state.phase ==
                                battle_preparation_phase::
                                        equip ?
                        "A:EQUIP  B:BACK" :
                        "A:UNEQUIP  B:BACK";
        generator.generate(
                -116, 56, action, sprites);
        return;
    }

    if(state.phase ==
            battle_preparation_phase::upgrade)
    {
        bn::string<64> progress = "RECIPE ";
        progress += bn::to_string<4>(
                static_cast<int>(
                        state.upgrade_index + 1));
        progress += "/";
        progress += bn::to_string<4>(
                static_cast<int>(state.upgrade_count));
        generator.generate(
                -116, -16, progress, sprites);

        bn::string<64> recipe = "TOOL ";
        recipe += bn::to_string<4>(
                state.parent_tool_id);
        recipe += " -> ";
        recipe += bn::to_string<4>(
                state.output_tool_id);
        generator.generate(
                -116, 0, recipe, sprites);

        bn::string<64> material = "MATERIAL ";
        material += bn::to_string<4>(
                state.required_material_id);
        material += "  OWNED ";
        material += bn::to_string<4>(
                state.material_quantity);
        generator.generate(
                -116, 16, material, sprites);

        bn::string<64> quantities = "BAG ";
        quantities += bn::to_string<4>(
                state.parent_quantity);
        quantities += " -> ";
        quantities += bn::to_string<4>(
                state.output_quantity);
        generator.generate(
                -116, 32, quantities, sprites);
        generator.generate(
                -116,
                56,
                "A:UPGRADE  B:BACK",
                sprites);
        return;
    }

    if(state.phase ==
            battle_preparation_phase::feedback)
    {
        generator.generate(
                -116,
                -8,
                state.last_operation ==
                                battle_preparation_operation::
                                        upgrade ?
                        upgrade_error_text(
                                state.last_upgrade_error) :
                        equipment_error_text(
                                state.last_operation,
                                state.last_equipment_error),
                sprites);
        if(state.last_operation ==
                        battle_preparation_operation::upgrade &&
                state.output_tool_id != 0)
        {
            bn::string<64> recipe = "TOOL ";
            recipe += bn::to_string<4>(
                    state.parent_tool_id);
            recipe += " -> ";
            recipe += bn::to_string<4>(
                    state.output_tool_id);
            generator.generate(
                    -116, 10, recipe, sprites);
        }
        else if(state.equipment_tool_id != 0)
        {
            bn::string<64> tool = "TOOL ";
            tool += bn::to_string<4>(
                    state.equipment_tool_id);
            generator.generate(
                    -116, 10, tool, sprites);
        }
        generator.generate(
                -116, 56, "A/B:BACK", sprites);
    }
}

}

battle_preparation_scene_exit
run_battle_preparation_scene(
        battle_campaign_state& campaign,
        bool show_overview)
{
    const battle_audio_director audio_director;
    dispatch_battle_audio(
            audio_director,
            battle_audio_event::preparation_opened);
    const std::uint8_t character_id = campaign.party[0];
    battle_preparation_flow flow;
    if(! flow.load(
               campaign,
               character_id,
               show_overview))
    {
        return battle_preparation_scene_exit::
                invalid_campaign;
    }

    bn::bg_palettes::set_transparent_color(
            bn::color(0, 0, 0));
    bn::sprite_text_generator text_generator(
            battle_preparation_sprite_font);
    text_generator.set_bg_priority(0);
    text_generator.set_palette_item(
            bn::sprite_palette_items::
                    battle_ui_preparation_text_palette);
    bn::vector<
            bn::sprite_ptr,
            preparation_text_sprite_capacity> text_sprites;
    bn::vector<
            bn::sprite_ptr,
            preparation_panel_sprite_capacity> panel_sprites;
    battle_preparation_snapshot state =
            flow.snapshot();
    bn::optional<bn::regular_bg_ptr> scene_background =
            uses_mission_background(state.phase) ?
                    bn::regular_bg_items::
                            battle_preparation_overview_background
                                    .create_bg(0, 0) :
                    bn::regular_bg_items::
                            battle_preparation_background
                                    .create_bg(0, 0);
    scene_background->set_priority(3);
    render_preparation_text(
            state,
            campaign,
            text_generator,
            text_sprites,
            panel_sprites);

    bool input_armed = false;
    while(true)
    {
        if(! input_armed)
        {
            input_armed =
                    ! bn::keypad::a_held() &&
                    ! bn::keypad::b_held() &&
                    ! bn::keypad::start_held();
        }
        else
        {
            bool handled = false;
            if(bn::keypad::a_pressed())
            {
                handled = flow.confirm();
            }
            else if(bn::keypad::b_pressed())
            {
                handled = flow.cancel();
            }
            else if(bn::keypad::up_pressed())
            {
                handled = flow.move(-1);
            }
            else if(bn::keypad::down_pressed())
            {
                handled = flow.move(1);
            }
            else if(bn::keypad::left_pressed())
            {
                handled = flow.switch_character(-1);
            }
            else if(bn::keypad::right_pressed())
            {
                handled = flow.switch_character(1);
            }
            else if(bn::keypad::start_pressed() &&
                    state.phase ==
                            battle_preparation_phase::root &&
                    state.root_option ==
                            battle_preparation_root_option::
                                    start_battle)
            {
                handled = flow.confirm();
            }

            if(handled)
            {
                state = flow.snapshot();
                if(state.phase ==
                        battle_preparation_phase::ready)
                {
                    text_sprites.clear();
                    panel_sprites.clear();
                    bn::core::update();
                    return battle_preparation_scene_exit::
                            ready;
                }
                if(state.phase ==
                        battle_preparation_phase::
                                save_requested)
                {
                    text_sprites.clear();
                    panel_sprites.clear();
                    bn::core::update();
                    return battle_preparation_scene_exit::
                            save_requested;
                }
                if(state.phase ==
                        battle_preparation_phase::
                                map_preview)
                {
                    scene_background =
                            bn::regular_bg_items::
                                    battle_01_map_chunk_0
                                            .create_bg(0, 0);
                }
                else if(uses_mission_background(
                                state.phase))
                {
                    scene_background =
                            bn::regular_bg_items::
                                    battle_preparation_overview_background
                                            .create_bg(0, 0);
                }
                else
                {
                    scene_background =
                            bn::regular_bg_items::
                                    battle_preparation_background
                                            .create_bg(0, 0);
                }
                scene_background->set_priority(3);
                render_preparation_text(
                        state,
                        campaign,
                        text_generator,
                        text_sprites,
                        panel_sprites);
            }
        }
        bn::core::update();
    }
}

}
