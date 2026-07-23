#ifndef KONOHA_BATTLE_UNIT_CONTENT_H
#define KONOHA_BATTLE_UNIT_CONTENT_H

#include "konoha/battle_session.h"

#include <array>
#include <cstdint>

namespace konoha
{

struct action_slot_definition
{
    ability_id action = 0;
    std::uint8_t initial_state = 0;
    std::uint8_t unlock_level = 0;
    std::uint8_t reserved = 0;
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

[[nodiscard]] inline battle_unit_instance instantiate_unit(
        const unit_definition& definition,
        battle_unit_id instance_id,
        battle_side side,
        battle_control control,
        grid_point position,
        battle_facing facing)
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
    result.base_attack = definition.attack;
    result.base_defense = definition.defense;
    result.base_agility = definition.agility;
    result.base_move_range = definition.movement;
    result.base_max_hp = definition.max_hp;
    return result;
}

}

#endif
