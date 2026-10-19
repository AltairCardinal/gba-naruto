#ifndef KONOHA_BATTLE_UNIT_CONTENT_H
#define KONOHA_BATTLE_UNIT_CONTENT_H

#include "konoha/battle_session.h"

#include <array>
#include <cstdint>

namespace konoha
{

inline constexpr std::uint8_t unlocked_action_level = 0;
inline constexpr std::uint8_t locked_action_level = 0xFF;
inline constexpr std::uint8_t maximum_action_level = 3;

struct action_slot_definition
{
    ability_id action = 0;
    std::uint8_t initial_state = 0;
    std::uint8_t unlock_level = 0;
    std::uint8_t reserved = 0;

    constexpr bool operator==(
            const action_slot_definition&) const = default;
};

struct unit_definition
{
    std::uint8_t character_id = 0;
    bool active = false;
    int attack = 0;
    int defense = 0;
    int agility = 0;
    int movement = 0;
    int ninja_tool_capacity = 0;
    int chakra_capacity = 0;
    int hand_seals = 0;
    int max_hp = 0;
    std::array<action_slot_definition, 15> primary_slots = {};
    std::array<action_slot_definition, 24> secondary_slots = {};
};

using primary_action_state_array = std::array<std::uint8_t, 15>;
using secondary_action_state_array = std::array<std::uint8_t, 24>;

[[nodiscard]] constexpr std::uint8_t initialize_action_slot_state(
        const action_slot_definition& slot, int unit_level)
{
    if(slot.action == 0 || slot.action == no_ability)
    {
        return unlocked_action_level;
    }
    if(slot.initial_state == locked_action_level &&
            slot.unlock_level > 0 &&
            unit_level >= slot.unlock_level)
    {
        return unlocked_action_level;
    }
    return slot.initial_state;
}

[[nodiscard]] constexpr primary_action_state_array
initialize_primary_action_states(
        const unit_definition& definition, int unit_level)
{
    primary_action_state_array result = {};
    for(std::size_t index = 0;
            index < definition.primary_slots.size();
            ++index)
    {
        result[index] = initialize_action_slot_state(
                definition.primary_slots[index], unit_level);
    }
    return result;
}

[[nodiscard]] constexpr secondary_action_state_array
initialize_secondary_action_states(
        const unit_definition& definition, int unit_level)
{
    secondary_action_state_array result = {};
    for(std::size_t index = 0;
            index < definition.secondary_slots.size();
            ++index)
    {
        result[index] = initialize_action_slot_state(
                definition.secondary_slots[index], unit_level);
    }
    return result;
}

[[nodiscard]] inline battle_unit_instance instantiate_unit(
        const unit_definition& definition,
        battle_unit_id instance_id,
        battle_side side,
        battle_control control,
        grid_point position,
        battle_facing facing,
        int level = 1)
{
    battle_unit_instance result = {
        instance_id,
        side,
        control,
        position,
        facing,
        definition.max_hp,
        definition.max_hp,
        definition.chakra_capacity,
        definition.chakra_capacity,
        definition.movement,
        definition.active,
        {},
    };
    result.attack = definition.attack;
    result.defense = definition.defense;
    result.agility = definition.agility;
    result.hand_seals = definition.hand_seals;
    result.base_attack = definition.attack;
    result.base_defense = definition.defense;
    result.base_agility = definition.agility;
    result.base_move_range = definition.movement;
    result.base_max_hp = definition.max_hp;
    result.character_id = definition.character_id;
    result.level = level > 0 ? level : 1;
    for(std::size_t index = 0;
            index < definition.primary_slots.size();
            ++index)
    {
        result.primary_action_ids[index] =
                definition.primary_slots[index].action;
    }
    result.primary_action_levels =
            initialize_primary_action_states(
                    definition, result.level);
    result.original_character_id = definition.character_id;
    for(std::size_t index = 0; index < definition.secondary_slots.size(); ++index)
    {
        const action_slot_definition& slot = definition.secondary_slots[index];
        (void) result.passives.set_slot(
                index,
                slot.action,
                initialize_action_slot_state(
                        slot, result.level));
    }
    return result;
}

}

#endif
