#ifndef KONOHA_BATTLE_PROGRESSION_H
#define KONOHA_BATTLE_PROGRESSION_H

#include "konoha/battle_unit_content.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

struct character_growth_definition
{
    int max_hp = 0;
    int chakra_capacity = 0;
    int attack = 0;
    int defense = 0;
    int agility = 0;
    int movement = 0;
    int ninja_tool_capacity = 0;

    constexpr bool operator==(const character_growth_definition&) const =
            default;
};

struct experience_threshold_definition
{
    int per_level_increment = 0;
    int base_threshold = 0;

    constexpr bool operator==(const experience_threshold_definition&) const =
            default;
};

struct character_stat_values
{
    int max_hp = 0;
    int chakra_capacity = 0;
    int attack = 0;
    int defense = 0;
    int agility = 0;
    int movement = 0;
    int ninja_tool_capacity = 0;

    constexpr bool operator==(const character_stat_values&) const = default;
};

struct persistent_passive_stat_result
{
    character_stat_values stats = {};
    int hand_seals = 0;

    constexpr bool operator==(
            const persistent_passive_stat_result&) const = default;
};

struct character_progression_record
{
    std::uint8_t character_id = 0;
    int level = 1;
    int experience = 0;
    int training_points = 0;
    bool active = false;
    primary_action_state_array primary_action_levels = {};
    secondary_action_state_array secondary_action_levels = {};
    bool action_states_initialized = false;

    constexpr bool operator==(const character_progression_record&) const =
            default;
};

struct scenario_primary_action_unlock_rule
{
    int battle_id = 0;
    int variant = 0;
    std::uint8_t character_id = 0;
    ability_id action_id = no_ability;

    constexpr bool operator==(
            const scenario_primary_action_unlock_rule&) const =
                    default;
};

inline constexpr std::array<
        scenario_primary_action_unlock_rule,
        1> scenario_primary_action_unlock_rules = {{
    { 31, 0, 2, 19 },
}};

[[nodiscard]] constexpr bool initialize_character_action_progression(
        character_progression_record& record,
        const unit_definition& definition)
{
    if(! record.active ||
            record.character_id != definition.character_id ||
            ! definition.active)
    {
        return false;
    }
    record.primary_action_levels =
            initialize_primary_action_states(
                    definition, record.level);
    record.secondary_action_levels =
            initialize_secondary_action_states(
                    definition, record.level);
    record.action_states_initialized = true;
    return true;
}

[[nodiscard]] constexpr bool synchronize_character_action_unlocks(
        character_progression_record& record,
        const unit_definition& definition)
{
    if(! record.action_states_initialized)
    {
        return initialize_character_action_progression(
                record, definition);
    }
    if(! record.active ||
            record.character_id != definition.character_id ||
            ! definition.active)
    {
        return false;
    }
    for(std::size_t index = 0;
            index < definition.primary_slots.size();
            ++index)
    {
        if(record.primary_action_levels[index] ==
                        locked_action_level &&
                initialize_action_slot_state(
                        definition.primary_slots[index],
                        record.level) ==
                        unlocked_action_level)
        {
            record.primary_action_levels[index] =
                    unlocked_action_level;
        }
    }
    for(std::size_t index = 0;
            index < definition.secondary_slots.size();
            ++index)
    {
        if(record.secondary_action_levels[index] ==
                        locked_action_level &&
                initialize_action_slot_state(
                        definition.secondary_slots[index],
                        record.level) ==
                        unlocked_action_level)
        {
            record.secondary_action_levels[index] =
                    unlocked_action_level;
        }
    }
    return true;
}

[[nodiscard]] constexpr bool synchronize_scenario_action_unlocks(
        character_progression_record& record,
        const unit_definition& definition,
        int battle_id,
        int variant)
{
    if(! record.active ||
            ! record.action_states_initialized ||
            record.character_id != definition.character_id ||
            ! definition.active)
    {
        return false;
    }
    for(const scenario_primary_action_unlock_rule& rule :
            scenario_primary_action_unlock_rules)
    {
        if(rule.battle_id != battle_id ||
                rule.variant != variant ||
                rule.character_id != record.character_id)
        {
            continue;
        }
        for(std::size_t index = 0;
                index < definition.primary_slots.size();
                ++index)
        {
            if(definition.primary_slots[index].action ==
                    rule.action_id)
            {
                if(record.primary_action_levels[index] ==
                        locked_action_level)
                {
                    record.primary_action_levels[index] =
                            unlocked_action_level;
                }
                return true;
            }
        }
        return false;
    }
    return true;
}

[[nodiscard]] constexpr battle_passive_state
character_passive_state(
        const unit_definition& definition,
        const secondary_action_state_array& levels)
{
    battle_passive_state result;
    for(std::size_t index = 0;
            index < definition.secondary_slots.size();
            ++index)
    {
        (void) result.set_slot(
                index,
                definition.secondary_slots[index].action,
                levels[index]);
    }
    return result;
}

[[nodiscard]] inline bool apply_character_action_progression(
        const character_progression_record& record,
        const unit_definition& definition,
        battle_unit_instance& unit)
{
    if(! record.active ||
            ! record.action_states_initialized ||
            record.character_id != definition.character_id ||
            unit.character_id != definition.character_id)
    {
        return false;
    }
    unit.level = record.level > 0 ? record.level : 1;
    unit.primary_action_levels =
            record.primary_action_levels;
    unit.passives = character_passive_state(
            definition,
            record.secondary_action_levels);
    return true;
}

struct level_settlement
{
    character_progression_record before = {};
    character_progression_record after = {};
    int gained_experience = 0;
    int spent_experience = 0;
    int levels_gained = 0;

    constexpr bool operator==(const level_settlement&) const = default;
};

[[nodiscard]] constexpr int progression_clamp(
        int value, int maximum)
{
    if(value < 0)
    {
        return 0;
    }
    return value > maximum ? maximum : value;
}

[[nodiscard]] constexpr int grown_value(
        int base, int growth_per_hundred_levels, int level, int maximum)
{
    const int normalized_level = level > 0 ? level : 1;
    return progression_clamp(
            base +
                    growth_per_hundred_levels *
                            (normalized_level - 1) /
                            100,
            maximum);
}

[[nodiscard]] constexpr character_stat_values character_stats_at_level(
        const unit_definition& base,
        const character_growth_definition& growth,
        int level)
{
    return {
        grown_value(base.max_hp, growth.max_hp, level, 999),
        grown_value(
                base.chakra_capacity,
                growth.chakra_capacity,
                level,
                9),
        grown_value(base.attack, growth.attack, level, 99),
        grown_value(base.defense, growth.defense, level, 99),
        grown_value(base.agility, growth.agility, level, 99),
        grown_value(base.movement, growth.movement, level, 5),
        grown_value(
                base.ninja_tool_capacity,
                growth.ninja_tool_capacity,
                level,
                9),
    };
}

template<std::size_t DefinitionCount>
[[nodiscard]] constexpr persistent_passive_stat_result
apply_persistent_passive_stats(
        const character_stat_values& base,
        int hand_seals,
        const battle_passive_state& passives,
        const std::array<
                passive_definition,
                DefinitionCount>& definitions)
{
    persistent_passive_stat_result result = {
        base,
        hand_seals > 0 ? hand_seals : 0,
    };
    const auto definition_for_slot =
            [&passives, &definitions](
                    std::size_t index)
                    -> const passive_definition*
            {
                const passive_slot_state& slot =
                        passives.slot(index);
                if(slot.id == no_passive ||
                        slot.stored_level == 0 ||
                        slot.stored_level ==
                                unlearned_passive_level ||
                        slot.id >= DefinitionCount)
                {
                    return nullptr;
                }
                const passive_definition& definition =
                        definitions[slot.id];
                return definition.id == slot.id ?
                        &definition :
                        nullptr;
            };
    const auto value_a =
            [&passives](
                    std::size_t index,
                    const passive_definition& definition)
            {
                return static_cast<int>(definition.base_a) +
                        static_cast<int>(
                                definition.per_level_a) *
                                (static_cast<int>(
                                         passives.slot(index)
                                                 .stored_level) -
                                 1);
            };
    const auto increase_percentage =
            [](int current, int percentage, int maximum)
            {
                return progression_clamp(
                        current +
                                current * percentage /
                                        100,
                        maximum);
            };

    // The original performs percentage-based modifiers in a complete
    // first pass, then applies fixed additions in a second pass.
    for(std::size_t index = 0;
            index < battle_passive_state::capacity;
            ++index)
    {
        const passive_definition* definition =
                definition_for_slot(index);
        if(! definition)
        {
            continue;
        }
        const int value =
                value_a(index, *definition);
        switch(definition->target_type)
        {
        case 2:
            result.stats.max_hp =
                    increase_percentage(
                            result.stats.max_hp,
                            value,
                            999);
            break;
        case 6:
            result.stats.defense =
                    increase_percentage(
                            result.stats.defense,
                            value,
                            99);
            break;
        case 8:
            result.stats.agility =
                    increase_percentage(
                            result.stats.agility,
                            value,
                            99);
            break;
        case 11:
        {
            int reduction =
                    result.hand_seals * value / 100;
            if(result.hand_seals - reduction <= 0)
            {
                reduction = result.hand_seals - 1;
            }
            result.hand_seals -= reduction;
            break;
        }
        default:
            break;
        }
    }

    for(std::size_t index = 0;
            index < battle_passive_state::capacity;
            ++index)
    {
        const passive_definition* definition =
                definition_for_slot(index);
        if(! definition)
        {
            continue;
        }
        const int value =
                value_a(index, *definition);
        switch(definition->target_type)
        {
        case 1:
            result.stats.max_hp =
                    progression_clamp(
                            result.stats.max_hp + value,
                            999);
            break;
        case 3:
            result.stats.chakra_capacity =
                    progression_clamp(
                            result.stats.chakra_capacity +
                                    value,
                            9);
            break;
        case 4:
            result.stats.attack =
                    progression_clamp(
                            result.stats.attack + value,
                            99);
            break;
        case 5:
            result.stats.defense =
                    progression_clamp(
                            result.stats.defense + value,
                            99);
            break;
        case 7:
            result.stats.agility =
                    progression_clamp(
                            result.stats.agility + value,
                            99);
            break;
        case 9:
            result.stats.movement =
                    progression_clamp(
                            result.stats.movement + value,
                            9);
            break;
        case 10:
            result.stats.ninja_tool_capacity =
                    progression_clamp(
                            result.stats.ninja_tool_capacity +
                                    value,
                            99);
            break;
        default:
            break;
        }
    }
    return result;
}

template<std::size_t DefinitionCount>
[[nodiscard]] constexpr persistent_passive_stat_result
character_stats_at_progression(
        const character_progression_record& record,
        const unit_definition& definition,
        const character_growth_definition& growth,
        const std::array<
                passive_definition,
                DefinitionCount>& definitions)
{
    const int level = record.level > 0 ?
            record.level :
            1;
    const secondary_action_state_array levels =
            record.action_states_initialized ?
            record.secondary_action_levels :
            initialize_secondary_action_states(
                    definition,
                    level);
    return apply_persistent_passive_stats(
            character_stats_at_level(
                    definition,
                    growth,
                    level),
            definition.hand_seals,
            character_passive_state(
                    definition,
                    levels),
            definitions);
}

inline void assign_character_level_stats(
        battle_unit_instance& unit,
        const character_stat_values& stats,
        int hand_seals,
        int level)
{
    unit.level = level;
    unit.hp = stats.max_hp;
    unit.max_hp = stats.max_hp;
    unit.chakra = stats.chakra_capacity;
    unit.max_chakra = stats.chakra_capacity;
    unit.attack = stats.attack;
    unit.base_attack = stats.attack;
    unit.defense = stats.defense;
    unit.base_defense = stats.defense;
    unit.agility = stats.agility;
    unit.base_agility = stats.agility;
    unit.move_range = stats.movement;
    unit.base_move_range = stats.movement;
    unit.base_max_hp = stats.max_hp;
    unit.ninja_tool_capacity =
            stats.ninja_tool_capacity;
    unit.hand_seals = hand_seals;
}

[[nodiscard]] inline bool apply_character_level_stats(
        battle_unit_instance& unit,
        const unit_definition& definition,
        const character_growth_definition& growth,
        int level)
{
    if(! definition.active ||
            unit.character_id != definition.character_id)
    {
        return false;
    }

    const int normalized_level = level > 0 ? level : 1;
    const character_stat_values stats =
            character_stats_at_level(
                    definition, growth, normalized_level);
    assign_character_level_stats(
            unit,
            stats,
            definition.hand_seals,
            normalized_level);
    return true;
}

template<std::size_t DefinitionCount>
[[nodiscard]] inline bool apply_character_level_stats(
        battle_unit_instance& unit,
        const unit_definition& definition,
        const character_growth_definition& growth,
        int level,
        const std::array<
                passive_definition,
                DefinitionCount>& definitions)
{
    if(! definition.active ||
            unit.character_id != definition.character_id)
    {
        return false;
    }

    const int normalized_level = level > 0 ? level : 1;
    const persistent_passive_stat_result stats =
            apply_persistent_passive_stats(
                    character_stats_at_level(
                            definition,
                            growth,
                            normalized_level),
                    definition.hand_seals,
                    unit.passives,
                    definitions);
    assign_character_level_stats(
            unit,
            stats.stats,
            stats.hand_seals,
            normalized_level);
    return true;
}

[[nodiscard]] constexpr character_stat_values operator-(
        const character_stat_values& left,
        const character_stat_values& right)
{
    return {
        left.max_hp - right.max_hp,
        left.chakra_capacity - right.chakra_capacity,
        left.attack - right.attack,
        left.defense - right.defense,
        left.agility - right.agility,
        left.movement - right.movement,
        left.ninja_tool_capacity - right.ninja_tool_capacity,
    };
}

[[nodiscard]] constexpr level_settlement settle_character_progression(
        const character_progression_record& record,
        int gained_experience,
        const experience_threshold_definition& threshold)
{
    level_settlement result;
    result.before = record;
    result.after = record;
    result.gained_experience =
            gained_experience > 0 ? gained_experience : 0;
    result.after.experience += result.gained_experience;
    while(result.after.level < 50)
    {
        const int required =
                threshold.base_threshold +
                threshold.per_level_increment *
                        (result.after.level - 1);
        if(required <= 0 || result.after.experience < required)
        {
            break;
        }
        result.after.experience -= required;
        result.spent_experience += required;
        ++result.after.level;
        ++result.after.training_points;
        ++result.levels_gained;
    }
    if(result.after.level >= 50 &&
            result.after.experience > 999)
    {
        result.after.experience = 999;
    }
    return result;
}

}

#endif
