#ifndef KONOHA_BATTLE_PASSIVES_H
#define KONOHA_BATTLE_PASSIVES_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

using passive_id = std::uint8_t;

inline constexpr passive_id no_passive = 0;
inline constexpr std::uint8_t no_passive_slot = 0xFF;
inline constexpr std::uint8_t unlearned_passive_level = 0xFF;
inline constexpr std::uint8_t critical_passive_target = 0x0C;
inline constexpr std::uint8_t hp_restoration_passive_target = 0x14;
inline constexpr std::uint8_t battle_experience_passive_target = 0x15;
inline constexpr std::uint8_t current_hp_continuation_passive_target = 0x16;
inline constexpr std::uint8_t current_chakra_continuation_passive_target = 0x17;
inline constexpr std::uint8_t ninja_tool_continuation_passive_target = 0x18;
inline constexpr std::uint8_t ignore_defense_passive_target = 0x19;

struct passive_definition
{
    passive_id id = no_passive;
    std::uint8_t target_type = 0;
    std::uint8_t reserved1 = 0;
    std::uint16_t base_a = 0;
    std::uint16_t base_b = 0;
    std::uint16_t per_level_a = 0;
    std::uint16_t per_level_b = 0;
    std::uint16_t reserved_a = 0;

    constexpr bool operator==(const passive_definition&) const = default;
};

struct passive_slot_state
{
    passive_id id = no_passive;
    std::uint8_t stored_level = 0;

    constexpr bool operator==(const passive_slot_state&) const = default;
};

struct passive_query_result
{
    bool found = false;
    std::uint8_t slot_index = no_passive_slot;
    passive_id id = no_passive;
    std::uint8_t stored_level = 0;
    int value_a = 0;
    int value_b = 0;

    constexpr bool operator==(const passive_query_result&) const = default;
};

class battle_passive_state
{
public:
    static constexpr std::size_t capacity = 24;

    [[nodiscard]] constexpr const passive_slot_state& slot(
            std::size_t index) const
    {
        return _slots[index];
    }

    [[nodiscard]] constexpr bool set_slot(
            std::size_t index,
            passive_id id,
            std::uint8_t stored_level)
    {
        if(index >= capacity)
        {
            return false;
        }
        _slots[index] = { id, stored_level };
        return true;
    }

    template<std::size_t DefinitionCount>
    [[nodiscard]] constexpr passive_query_result query(
            std::uint8_t target_type,
            const std::array<passive_definition, DefinitionCount>&
                    definitions) const
    {
        for(std::size_t index = 0; index < capacity; ++index)
        {
            const passive_slot_state& candidate = _slots[index];
            if(candidate.id == no_passive ||
                    candidate.stored_level == 0 ||
                    candidate.stored_level == unlearned_passive_level ||
                    candidate.id >= DefinitionCount)
            {
                continue;
            }
            const passive_definition& definition = definitions[candidate.id];
            if(definition.id != candidate.id ||
                    definition.target_type != target_type)
            {
                continue;
            }
            const int level_minus_one =
                    static_cast<int>(candidate.stored_level) - 1;
            return {
                true,
                static_cast<std::uint8_t>(index),
                candidate.id,
                candidate.stored_level,
                static_cast<int>(definition.base_a) +
                        static_cast<int>(definition.per_level_a) *
                                level_minus_one,
                static_cast<int>(definition.base_b) +
                        static_cast<int>(definition.per_level_b) *
                                level_minus_one,
            };
        }
        return {};
    }

    constexpr bool operator==(const battle_passive_state&) const = default;

private:
    std::array<passive_slot_state, capacity> _slots = {};
};

static_assert(sizeof(passive_slot_state) == 2);
static_assert(sizeof(battle_passive_state) == 48);

}

#endif
