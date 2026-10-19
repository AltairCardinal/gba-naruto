#ifndef KONOHA_BATTLE_SCENARIO_CONTENT_H
#define KONOHA_BATTLE_SCENARIO_CONTENT_H

#include "konoha/battle_unit_content.h"

#include <array>
#include <cstdint>

namespace konoha
{

enum class scenario_selector_kind : std::uint8_t
{
    fixed_character,
    deployment_placeholder,
};

struct battle_scenario_unit_runtime_config
{
    bool embedded_character_config = false;
    std::uint8_t level = 1;
    std::uint8_t unit_parameter = 0;
    std::array<action_slot_definition, 15>
            primary_action_slots = {};
    std::array<action_slot_definition, 24>
            secondary_action_slots = {};
    std::array<ninja_tool_id, battle_ninja_tool_slot_capacity>
            equipped_tools = {};

    constexpr bool operator==(
            const battle_scenario_unit_runtime_config&) const =
            default;
};

struct battle_scenario_unit_slot
{
    bool enabled = false;
    scenario_selector_kind selector_kind =
            scenario_selector_kind::fixed_character;
    std::uint8_t selector = 0;
    battle_side side = battle_side::player;
    grid_point position = {};
    battle_facing facing = battle_facing::up;
    std::uint16_t battle_experience = 0;
    battle_scenario_unit_runtime_config runtime_config = {};

    constexpr bool operator==(const battle_scenario_unit_slot&) const = default;
};

struct battle_scenario_definition
{
    std::uint8_t battle_id = 0;
    std::uint8_t grid_width = 0;
    std::uint8_t grid_height = 0;
    std::uint32_t map_flags = 0;
    std::array<std::array<battle_scenario_unit_slot, 12>, 3> variants = {};

    constexpr bool operator==(const battle_scenario_definition&) const = default;
};

}

#endif
