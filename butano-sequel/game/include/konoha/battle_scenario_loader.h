#ifndef KONOHA_BATTLE_SCENARIO_LOADER_H
#define KONOHA_BATTLE_SCENARIO_LOADER_H

#include "konoha/battle_scenario_content.h"
#include "konoha/battle_progression.h"
#include "konoha/battle_unit_content.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/generated_battle_passive_content.h"
#include "konoha/generated_battle_result_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr std::uint8_t no_scenario_character = 0xFF;
inline constexpr std::uint8_t no_scenario_record = 0xFF;

enum class battle_scenario_load_error : std::uint8_t
{
    none,
    invalid_variant,
    capacity_exceeded,
    unresolved_deployment_placeholder,
    invalid_character,
    inactive_character,
    invalid_ninja_tool,
    duplicate_unit,
};

struct battle_scenario_load_policy
{
    std::array<std::uint8_t, 6> placeholder_characters = {
        no_scenario_character,
        no_scenario_character,
        no_scenario_character,
        no_scenario_character,
        no_scenario_character,
        no_scenario_character,
    };
    // Arena and link-style formations can explicitly disable any of the
    // six deployment records. An override is separate from the value so an
    // unresolved story placeholder still fails closed.
    std::array<bool, 6>
            placeholder_enabled_overridden = {};
    std::array<bool, 6> placeholder_enabled = {
        true,
        true,
        true,
        true,
        true,
        true,
    };
    // Per-placeholder configuration is required for symmetric matches:
    // both sides may select the same character with different progression
    // and equipment, so character-indexed overrides are insufficient.
    // Non-owning references keep the load policy small enough for the GBA
    // stack. The mode-owned roster must outlive deployment and session load.
    std::array<
            const character_progression_record*,
            6>
            placeholder_progression = {};
    std::array<
            const std::array<
                    ninja_tool_id,
                    battle_ninja_tool_slot_capacity>*,
            6>
            placeholder_equipped_tools = {};
    std::array<bool, 63> scripted_characters = {};
    std::array<bool, 63> ai_characters = {};
    // Zero means the story/deployment layer did not provide a level.
    // Battle instances use level 1 as the safe baseline in that case.
    std::array<std::uint8_t, 63> character_levels = {};
    // A true override can explicitly clear all nine slots. For compatibility,
    // any nonzero tool entry also opts into the override.
    std::array<bool, 63>
            character_equipped_tools_overridden = {};
    std::array<
            std::array<
                    ninja_tool_id,
                    battle_ninja_tool_slot_capacity>,
            63>
            character_equipped_tools = {};
    bool preserve_empty_unit_slots = false;
};

struct battle_scenario_load_result
{
    battle_scenario_load_error error = battle_scenario_load_error::none;
    std::uint8_t record_id = no_scenario_record;
    std::uint8_t loaded_unit_count = 0;
};

struct battle_scenario_character_result
{
    battle_scenario_load_error error =
            battle_scenario_load_error::none;
    std::uint8_t character_id = no_scenario_character;

    [[nodiscard]] constexpr bool success() const
    {
        return error == battle_scenario_load_error::none;
    }
};

[[nodiscard]] constexpr std::size_t
battle_scenario_placeholder_index(
        const battle_scenario_unit_slot& slot)
{
    return slot.selector_kind ==
                           scenario_selector_kind::
                                   deployment_placeholder &&
                   slot.selector >= 0xFA ?
            static_cast<std::size_t>(0xFF - slot.selector) :
            6;
}

[[nodiscard]] constexpr bool
battle_scenario_slot_enabled(
        const battle_scenario_unit_slot& slot,
        const battle_scenario_load_policy& policy)
{
    if(! slot.enabled)
    {
        return false;
    }
    const std::size_t placeholder_index =
            battle_scenario_placeholder_index(slot);
    return placeholder_index >=
                           policy.placeholder_enabled.size() ||
                   ! policy.placeholder_enabled_overridden[
                           placeholder_index] ?
            true :
            policy.placeholder_enabled[placeholder_index];
}

[[nodiscard]] inline battle_scenario_character_result
resolve_battle_scenario_character(
        const battle_scenario_unit_slot& slot,
        const battle_scenario_load_policy& policy)
{
    std::uint8_t character_id = slot.selector;
    if(slot.selector_kind ==
            scenario_selector_kind::deployment_placeholder)
    {
        if(slot.selector < 0xFA)
        {
            return {
                battle_scenario_load_error::invalid_character,
                no_scenario_character,
            };
        }
        const std::size_t placeholder_index =
                static_cast<std::size_t>(
                        0xFF - slot.selector);
        character_id =
                policy.placeholder_characters[
                        placeholder_index];
        if(character_id == no_scenario_character)
        {
            return {
                battle_scenario_load_error::
                        unresolved_deployment_placeholder,
                no_scenario_character,
            };
        }
    }
    if(character_id >= unit_definitions.size())
    {
        return {
            battle_scenario_load_error::invalid_character,
            no_scenario_character,
        };
    }
    if(! unit_definitions[character_id].active)
    {
        return {
            battle_scenario_load_error::inactive_character,
            character_id,
        };
    }
    return {
        battle_scenario_load_error::none,
        character_id,
    };
}

template<std::size_t MaxUnits>
[[nodiscard]] battle_scenario_load_result
load_battle_scenario_into_empty(
        const battle_scenario_definition& scenario,
        std::uint8_t variant,
        const battle_scenario_load_policy& policy,
        battle_session<MaxUnits>& destination,
        const character_progression_record*
                progression_records = nullptr,
        std::size_t progression_record_count = 0)
{
    destination = {};
    battle_scenario_load_result result;
    if(variant >= scenario.variants.size())
    {
        result.error = battle_scenario_load_error::invalid_variant;
        return result;
    }
    destination.set_battle_id(scenario.battle_id);

        const auto& slots = scenario.variants[variant];
    for(std::size_t index = 0; index < slots.size(); ++index)
    {
        const battle_scenario_unit_slot& slot = slots[index];
        const bool slot_enabled =
                battle_scenario_slot_enabled(slot, policy);
        if(! slot_enabled)
        {
            if(policy.preserve_empty_unit_slots)
            {
                if(destination.unit_count() == MaxUnits)
                {
                    result.error =
                            battle_scenario_load_error::
                                    capacity_exceeded;
                    return result;
                }
                battle_unit_instance reserve{};
                reserve.id =
                        static_cast<battle_unit_id>(index + 1);
                reserve.active = false;
                if(! destination.add_unit(reserve))
                {
                    result.error =
                            battle_scenario_load_error::
                                    duplicate_unit;
                    return result;
                }
            }
            continue;
        }
        result.record_id = static_cast<std::uint8_t>(index);
        if(destination.unit_count() == MaxUnits)
        {
            result.error = battle_scenario_load_error::capacity_exceeded;
            return result;
        }

        const battle_scenario_character_result
                character_result =
                        resolve_battle_scenario_character(
                                slot, policy);
        if(! character_result.success())
        {
            result.error = character_result.error;
            return result;
        }
        const std::uint8_t character_id =
                character_result.character_id;
        const unit_definition& definition =
                unit_definitions[character_id];
        const std::size_t placeholder_index =
                battle_scenario_placeholder_index(slot);
        const character_progression_record* progression =
                nullptr;
        if(placeholder_index <
                           policy.placeholder_progression.size() &&
                policy.placeholder_progression[
                        placeholder_index])
        {
            progression =
                    policy.placeholder_progression[
                            placeholder_index];
        }
        else if(slot.side == battle_side::player)
        {
            for(std::size_t progression_index = 0;
                    progression_records &&
                    progression_index <
                            progression_record_count;
                    ++progression_index)
            {
                const character_progression_record&
                        candidate =
                                progression_records[
                                        progression_index];
                if(candidate.active &&
                        candidate.character_id ==
                                character_id)
                {
                    progression = &candidate;
                    break;
                }
            }
        }
        bool has_embedded_action = false;
        for(const action_slot_definition& action_slot :
                slot.runtime_config.primary_action_slots)
        {
            if(action_slot.action != no_ability &&
                    action_slot.action != 0)
            {
                has_embedded_action = true;
                break;
            }
        }
        const bool formation_owns_character_config =
                slot.runtime_config.embedded_character_config &&
                (slot.side == battle_side::enemy ||
                 policy.ai_characters[character_id] ||
                 policy.scripted_characters[character_id] ||
                 has_embedded_action);
        const bool placeholder_tools_overridden =
                placeholder_index <
                                policy.placeholder_equipped_tools
                                        .size() &&
                policy.placeholder_equipped_tools[
                        placeholder_index];
        bool tools_overridden =
                placeholder_tools_overridden ||
                policy.character_equipped_tools_overridden[
                        character_id];
        if(! tools_overridden)
        {
            for(const ninja_tool_id tool :
                    policy.character_equipped_tools[
                            character_id])
            {
                if(tool != no_ninja_tool)
                {
                    tools_overridden = true;
                    break;
                }
            }
        }
        const auto& equipped_tools =
                placeholder_tools_overridden ?
                *policy.placeholder_equipped_tools[
                         placeholder_index] :
                tools_overridden ?
                policy.character_equipped_tools[character_id] :
                formation_owns_character_config ?
                        slot.runtime_config.equipped_tools :
                        policy.character_equipped_tools[
                                character_id];
        for(const ninja_tool_id tool : equipped_tools)
        {
            if(tool >= ninja_tool_action_definitions.size() ||
                    ninja_tool_action_definitions[tool].id != tool)
            {
                result.error =
                        battle_scenario_load_error::
                                invalid_ninja_tool;
                return result;
            }
        }

        battle_control control = slot.side == battle_side::player ?
                battle_control::player : battle_control::ai;
        if(policy.ai_characters[character_id])
        {
            control = battle_control::ai;
        }
        else if(policy.scripted_characters[character_id])
        {
            control = battle_control::scripted;
        }
        int unit_level = 1;
        if(formation_owns_character_config)
        {
            unit_level = slot.runtime_config.level;
        }
        if(policy.character_levels[character_id] > 0)
        {
            unit_level =
                    policy.character_levels[character_id];
        }
        if(progression)
        {
            unit_level = progression->level;
        }
        battle_unit_instance unit = instantiate_unit(
                definition,
                static_cast<battle_unit_id>(index + 1),
                slot.side,
                control,
                slot.position,
                slot.facing,
                unit_level);
        if(progression &&
                progression->action_states_initialized)
        {
            if(! apply_character_action_progression(
                       *progression,
                       definition,
                       unit))
            {
                result.error =
                        battle_scenario_load_error::
                                invalid_character;
                return result;
            }
        }
        else if(formation_owns_character_config)
        {
            for(std::size_t action_index = 0;
                    action_index <
                            slot.runtime_config.
                                    primary_action_slots.size();
                    ++action_index)
            {
                const action_slot_definition& action_slot =
                        slot.runtime_config.
                                primary_action_slots[
                                        action_index];
                unit.primary_action_ids[action_index] =
                        action_slot.action;
                unit.primary_action_levels[action_index] =
                        action_slot.initial_state;
            }
            unit.passives = {};
            for(std::size_t passive_index = 0;
                    passive_index <
                            slot.runtime_config.
                                    secondary_action_slots.size();
                    ++passive_index)
            {
                const action_slot_definition& passive_slot =
                        slot.runtime_config.
                                secondary_action_slots[
                                        passive_index];
                if(! unit.passives.set_slot(
                           passive_index,
                           passive_slot.action,
                           passive_slot.initial_state))
                {
                    result.error =
                            battle_scenario_load_error::
                                    invalid_character;
                    return result;
                }
            }
        }
        if(! apply_character_level_stats(
                   unit,
                   definition,
                   character_growth_definitions[
                           character_id],
                   unit_level,
                   passive_definitions))
        {
            result.error =
                    battle_scenario_load_error::
                            invalid_character;
            return result;
        }
        unit.equipped_tools = equipped_tools;
        unit.formation_unit_parameter =
                slot.runtime_config.unit_parameter;
        if(formation_owns_character_config)
        {
            unit.ai_config_id =
                    slot.runtime_config.unit_parameter;
        }
        unit.carried_experience =
                static_cast<int>(slot.battle_experience);
        if(! destination.add_unit(unit))
        {
            result.error = battle_scenario_load_error::duplicate_unit;
            return result;
        }
        ++result.loaded_unit_count;
    }

    result.record_id = no_scenario_record;
    return result;
}

template<std::size_t MaxUnits>
[[nodiscard]] battle_scenario_load_result load_battle_scenario(
        const battle_scenario_definition& scenario,
        std::uint8_t variant,
        const battle_scenario_load_policy& policy,
        battle_session<MaxUnits>& destination,
        const character_progression_record*
                progression_records = nullptr,
        std::size_t progression_record_count = 0)
{
    battle_session<MaxUnits> candidate;
    const battle_scenario_load_result result =
            load_battle_scenario_into_empty(
                    scenario,
                    variant,
                    policy,
                    candidate,
                    progression_records,
                    progression_record_count);
    if(result.error == battle_scenario_load_error::none)
    {
        destination = candidate;
    }
    return result;
}

}

#endif
