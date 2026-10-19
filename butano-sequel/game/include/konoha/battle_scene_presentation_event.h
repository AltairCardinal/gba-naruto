#ifndef KONOHA_BATTLE_SCENE_PRESENTATION_EVENT_H
#define KONOHA_BATTLE_SCENE_PRESENTATION_EVENT_H

#include "konoha/battle_resource_commands.h"

#include <array>
#include <cstdint>

namespace konoha
{

struct battle_scene_presentation_event
{
    bool valid = false;
    bool has_action = false;
    battle_unit_id actor_id = no_battle_unit;
    ability_id action_id = no_ability;
    grid_point origin = {};
    grid_point destination = {};
    grid_point target = {};
    bool ninja_tool = false;
    std::uint8_t animation_family = 0;
    bool targets_opponent = false;
    battle_unit_id target_id = no_battle_unit;
    bool actor_lunges = false;
    std::array<battle_unit_id, 12> affected_unit_ids = {};
    std::array<std::uint8_t, 12>
            affected_character_ids = {};
    int affected_unit_count = 0;
    bool affected_units_truncated = false;
    int impact_count = 0;
    bool has_combatant_vitals = false;
    int actor_hp = 0;
    int actor_max_hp = 0;
    int target_hp_before = 0;
    int target_hp_after = 0;
    int target_max_hp = 0;
    bool has_battlefield_object = false;
    battlefield_object_tick_kind battlefield_object_kind =
            battlefield_object_tick_kind::none;
    std::uint8_t battlefield_object_slot =
            no_battlefield_object;
    int battlefield_object_damage = 0;
    std::uint16_t battlefield_object_tile_index_start = 0;
    std::uint16_t battlefield_object_tile_index_end = 0;
    std::uint8_t battlefield_object_palette_bank_start = 0;
    std::uint8_t battlefield_object_palette_bank_end = 0;
    std::uint8_t battlefield_object_effect_sequence = 0;
    bool has_resource = false;
    battle_resource_command_type resource_type =
            battle_resource_command_type::replenish_chakra;
    int resource_amount = 0;
    int resource_hp_delta = 0;
    int resource_chakra_delta = 0;
    bool has_side_start_passive = false;
    passive_id passive = no_passive;
    battle_side_start_passive_kind passive_kind =
            battle_side_start_passive_kind::none;
    std::uint8_t passive_status_code = 0;
    std::uint8_t passive_status_value = 0;
    std::uint8_t passive_status_duration_ticks = 0;
    bool passive_status_applied = false;
    std::uint8_t passive_secondary_status_code = 0;
    std::uint8_t passive_secondary_status_value = 0;
    std::uint8_t passive_secondary_status_duration_ticks = 0;
    bool passive_secondary_status_applied = false;
    bool special_combination = false;
    bool direct_attack = false;
    int capture_count = 0;
};

}

#endif
