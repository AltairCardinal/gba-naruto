#include "konoha/battle_campaign_sram.h"

#include "bn_common.h"
#include "bn_sram.h"

#include "konoha/battle_campaign_route.h"

namespace konoha
{

extern "C"
{
    BN_DATA_EWRAM_BSS volatile
            battle_campaign_runtime_telemetry
                    konoha_battle_campaign_runtime_telemetry;
}

namespace
{

constexpr int slot_offset(int slot_index)
{
    return slot_index *
            static_cast<int>(
                    battle_campaign_save_slot_size);
}

void read_slots(
        battle_campaign_sram_workspace& workspace)
{
    bn::sram::read_offset(
            workspace.slots[0],
            slot_offset(0));
    bn::sram::read_offset(
            workspace.slots[1],
            slot_offset(1));
}

void capture_campaign(
        const battle_campaign_state& campaign)
{
    volatile battle_campaign_runtime_telemetry& output =
            konoha_battle_campaign_runtime_telemetry;
    const character_progression_record& naruto =
            campaign.characters[1].progression;
    output.naruto_level =
            static_cast<std::uint32_t>(naruto.level);
    output.naruto_experience =
            static_cast<std::uint32_t>(
                    naruto.experience);
    output.naruto_training_points =
            static_cast<std::uint32_t>(
                    naruto.training_points);
    output.naruto_action_8_level =
            naruto.primary_action_levels[6];
    const auto& tools =
            campaign.characters[1].equipped_tools;
    output.naruto_tool_0 = tools[0];
    output.naruto_tool_1 = tools[1];
    output.naruto_tool_2 = tools[2];
    output.owned_tool_67 =
            campaign.inventory.ninja_tools[67];
    output.owned_tool_68 =
            campaign.inventory.ninja_tools[68];
    output.material_6 =
            campaign.inventory.materials[6];
    output.owned_tool_1 =
            campaign.inventory.ninja_tools[1];
    output.scenario_id = campaign.chapter_id;
    output.route_complete =
            campaign.chapter_id ==
                    battle_campaign_route_complete_scenario ?
            1U :
            0U;
}

void capture_load(
        const battle_campaign_state& campaign,
        const battle_campaign_sram_result& result)
{
    volatile battle_campaign_runtime_telemetry& output =
            konoha_battle_campaign_runtime_telemetry;
    output.magic = 0;
    output.load_generation = result.generation;
    output.load_slot =
            static_cast<std::uint32_t>(
                    result.slot_index + 1);
    output.load_used_default =
            result.used_default ? 1U : 0U;
    output.save_generation = 0;
    output.save_slot = 0;
    output.save_verified = 0;
    output.last_error =
            static_cast<std::uint32_t>(result.error);
    capture_campaign(campaign);
    output.magic = battle_campaign_runtime_telemetry::magic_value;
}

void capture_save(
        const battle_campaign_state& campaign,
        const battle_campaign_sram_result& result)
{
    volatile battle_campaign_runtime_telemetry& output =
            konoha_battle_campaign_runtime_telemetry;
    output.magic = 0;
    output.save_generation = result.generation;
    output.save_slot =
            static_cast<std::uint32_t>(
                    result.slot_index + 1);
    output.save_verified =
            result.verified ? 1U : 0U;
    output.last_error =
            static_cast<std::uint32_t>(result.error);
    capture_campaign(campaign);
    output.magic = battle_campaign_runtime_telemetry::magic_value;
}

}

battle_campaign_sram_result
load_battle_campaign_from_sram(
        const battle_campaign_state& default_campaign,
        battle_campaign_state& campaign,
        battle_campaign_sram_workspace& workspace)
{
    read_slots(workspace);
    const battle_campaign_save_decode_result& loaded =
            load_latest_battle_campaign_slot_into(
                    workspace.slots[0],
                    workspace.slots[1],
                    default_campaign,
                    workspace.decoded_slots[0],
                    workspace.decoded_slots[1]);
    if(! loaded.valid())
    {
        const battle_campaign_sram_result result = {
            loaded.error,
        };
        capture_load(default_campaign, result);
        return result;
    }
    campaign = loaded.campaign;
    const battle_campaign_sram_result result = {
        battle_campaign_save_error::none,
        loaded.generation,
        loaded.source_slot,
        loaded.used_default,
        ! loaded.used_default,
    };
    capture_load(campaign, result);
    return result;
}

battle_campaign_sram_result
save_battle_campaign_to_sram(
        const battle_campaign_state& campaign,
        battle_campaign_sram_workspace& workspace)
{
    read_slots(workspace);
    const battle_campaign_save_target target =
            next_battle_campaign_save_target_into(
                    workspace.slots[0],
                    workspace.slots[1],
                    workspace.decoded_slots[0],
                    workspace.decoded_slots[1]);
    battle_campaign_save_slot& encoded =
            workspace.slots[target.slot_index];
    const battle_campaign_save_error encoded_error =
            encode_battle_campaign_slot(
                    campaign,
                    target.generation,
                    encoded);
    if(encoded_error !=
            battle_campaign_save_error::none)
    {
        const battle_campaign_sram_result result = {
            encoded_error,
        };
        capture_save(campaign, result);
        return result;
    }

    bn::sram::write_offset(
            encoded,
            slot_offset(target.slot_index));
    bn::sram::read_offset(
            encoded,
            slot_offset(target.slot_index));
    battle_campaign_save_decode_result& verified =
            workspace.decoded_slots[0];
    decode_battle_campaign_slot_into(
            encoded, verified);
    if(! verified.valid() ||
            verified.generation != target.generation ||
            verified.campaign != campaign)
    {
        const battle_campaign_sram_result result = {
            verified.valid() ?
                    battle_campaign_save_error::
                            invalid_state :
                    verified.error,
            target.generation,
            target.slot_index,
            false,
            false,
        };
        capture_save(campaign, result);
        return result;
    }
    const battle_campaign_sram_result result = {
        battle_campaign_save_error::none,
        target.generation,
        target.slot_index,
        false,
        true,
    };
    capture_save(campaign, result);
    return result;
}

}
