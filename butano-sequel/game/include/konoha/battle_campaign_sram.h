#ifndef KONOHA_BATTLE_CAMPAIGN_SRAM_H
#define KONOHA_BATTLE_CAMPAIGN_SRAM_H

#include "konoha/battle_campaign_save.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

struct battle_campaign_sram_workspace
{
    std::array<battle_campaign_save_slot, 2> slots = {};
    std::array<
            battle_campaign_save_decode_result,
            2>
            decoded_slots = {};
};

struct battle_campaign_sram_result
{
    battle_campaign_save_error error =
            battle_campaign_save_error::none;
    std::uint32_t generation = 0;
    int slot_index = -1;
    bool used_default = false;
    bool verified = false;

    [[nodiscard]] constexpr bool success() const
    {
        return error ==
                battle_campaign_save_error::none;
    }
};

struct battle_campaign_runtime_telemetry
{
    static constexpr std::uint32_t magic_value =
            0x4B43414DU;

    std::uint32_t magic = 0;
    std::uint32_t load_generation = 0;
    std::uint32_t load_slot = 0;
    std::uint32_t load_used_default = 0;
    std::uint32_t save_generation = 0;
    std::uint32_t save_slot = 0;
    std::uint32_t save_verified = 0;
    std::uint32_t naruto_level = 0;
    std::uint32_t naruto_experience = 0;
    std::uint32_t naruto_training_points = 0;
    std::uint32_t naruto_action_8_level = 0;
    std::uint32_t naruto_tool_0 = 0;
    std::uint32_t naruto_tool_1 = 0;
    std::uint32_t naruto_tool_2 = 0;
    std::uint32_t owned_tool_67 = 0;
    std::uint32_t owned_tool_68 = 0;
    std::uint32_t material_6 = 0;
    std::uint32_t last_error = 0;
    std::uint32_t owned_tool_1 = 0;
    std::uint32_t scenario_id = 0;
    std::uint32_t route_complete = 0;
};

static_assert(sizeof(battle_campaign_runtime_telemetry) == 84);
static_assert(
        offsetof(
                battle_campaign_runtime_telemetry,
                load_generation) == 4);
static_assert(
        offsetof(
                battle_campaign_runtime_telemetry,
                save_generation) == 16);
static_assert(
        offsetof(
                battle_campaign_runtime_telemetry,
                naruto_level) == 28);
static_assert(
        offsetof(
                battle_campaign_runtime_telemetry,
                naruto_action_8_level) == 40);
static_assert(
        offsetof(
                battle_campaign_runtime_telemetry,
                naruto_tool_0) == 44);
static_assert(
        offsetof(
                battle_campaign_runtime_telemetry,
                owned_tool_67) == 56);
static_assert(
        offsetof(
                battle_campaign_runtime_telemetry,
                material_6) == 64);
static_assert(
        offsetof(
                battle_campaign_runtime_telemetry,
                last_error) == 68);
static_assert(
        offsetof(
                battle_campaign_runtime_telemetry,
                owned_tool_1) == 72);
static_assert(
        offsetof(
                battle_campaign_runtime_telemetry,
                scenario_id) == 76);
static_assert(
        offsetof(
                battle_campaign_runtime_telemetry,
                route_complete) == 80);

extern "C"
{
    extern volatile battle_campaign_runtime_telemetry
            konoha_battle_campaign_runtime_telemetry;
}

[[nodiscard]] battle_campaign_sram_result
load_battle_campaign_from_sram(
        const battle_campaign_state& default_campaign,
        battle_campaign_state& campaign,
        battle_campaign_sram_workspace& workspace);

[[nodiscard]] battle_campaign_sram_result
save_battle_campaign_to_sram(
        const battle_campaign_state& campaign,
        battle_campaign_sram_workspace& workspace);

}

#endif
