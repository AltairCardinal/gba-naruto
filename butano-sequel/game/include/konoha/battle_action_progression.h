#ifndef KONOHA_BATTLE_ACTION_PROGRESSION_H
#define KONOHA_BATTLE_ACTION_PROGRESSION_H

#include "konoha/battle_progression.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/generated_battle_passive_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class action_training_error : std::uint8_t
{
    none,
    invalid_character,
    invalid_slot,
    empty_slot,
    locked,
    no_training_points,
    maximum_level,
    not_trainable,
};

struct action_training_result
{
    action_training_error error =
            action_training_error::none;
    ability_id action_id = no_ability;
    std::uint8_t before_level = 0;
    std::uint8_t after_level = 0;
    passive_id trained_passive_id = no_passive;

    [[nodiscard]] constexpr bool success() const
    {
        return error == action_training_error::none;
    }
};

[[nodiscard]] constexpr action_training_result
train_primary_action(
        character_progression_record& record,
        std::size_t slot_index)
{
    if(! record.active ||
            record.character_id >= unit_definitions.size() ||
            ! record.action_states_initialized)
    {
        return {
            action_training_error::invalid_character,
        };
    }
    if(slot_index >= record.primary_action_levels.size())
    {
        return {
            action_training_error::invalid_slot,
        };
    }
    const action_slot_definition& slot =
            unit_definitions[record.character_id]
                    .primary_slots[slot_index];
    if(slot.action == 0 || slot.action == no_ability)
    {
        return {
            action_training_error::empty_slot,
        };
    }
    const std::uint8_t current =
            record.primary_action_levels[slot_index];
    if(current == locked_action_level)
    {
        return {
            action_training_error::locked,
            slot.action,
            current,
            current,
        };
    }
    if(current >= maximum_action_level)
    {
        return {
            action_training_error::maximum_level,
            slot.action,
            current,
            current,
        };
    }
    if(record.training_points <= 0)
    {
        return {
            action_training_error::no_training_points,
            slot.action,
            current,
            current,
        };
    }
    if(slot.action >= active_action_definitions.size())
    {
        return {
            action_training_error::invalid_character,
            slot.action,
            current,
            current,
        };
    }
    --record.training_points;
    record.primary_action_levels[slot_index] =
            static_cast<std::uint8_t>(current + 1);
    return {
        action_training_error::none,
        slot.action,
        current,
        record.primary_action_levels[slot_index],
    };
}

[[nodiscard]] constexpr action_training_result
train_secondary_passive(
        character_progression_record& record,
        std::size_t slot_index)
{
    if(! record.active ||
            record.character_id >= unit_definitions.size() ||
            ! record.action_states_initialized)
    {
        return {
            action_training_error::invalid_character,
        };
    }
    if(slot_index >= record.secondary_action_levels.size())
    {
        return {
            action_training_error::invalid_slot,
        };
    }
    const action_slot_definition& slot =
            unit_definitions[record.character_id]
                    .secondary_slots[slot_index];
    if(slot.action == 0 || slot.action == no_ability)
    {
        return {
            action_training_error::empty_slot,
        };
    }
    const std::uint8_t current =
            record.secondary_action_levels[slot_index];
    if(current == locked_action_level)
    {
        return {
            action_training_error::locked,
            no_ability,
            current,
            current,
            slot.action,
        };
    }
    if(current >= maximum_action_level)
    {
        return {
            action_training_error::maximum_level,
            no_ability,
            current,
            current,
            slot.action,
        };
    }
    if(record.training_points <= 0)
    {
        return {
            action_training_error::no_training_points,
            no_ability,
            current,
            current,
            slot.action,
        };
    }
    if(slot.action >= passive_definitions.size())
    {
        return {
            action_training_error::invalid_character,
            no_ability,
            current,
            current,
            slot.action,
        };
    }
    const passive_definition& passive =
            passive_definitions[slot.action];
    if(passive.id != slot.action ||
            passive.target_type == 0 ||
            (passive.per_level_a == 0 &&
                    passive.per_level_b == 0))
    {
        return {
            action_training_error::not_trainable,
            no_ability,
            current,
            current,
            slot.action,
        };
    }

    --record.training_points;
    record.secondary_action_levels[slot_index] =
            static_cast<std::uint8_t>(current + 1);
    return {
        action_training_error::none,
        no_ability,
        current,
        record.secondary_action_levels[slot_index],
        slot.action,
    };
}

}

#endif
