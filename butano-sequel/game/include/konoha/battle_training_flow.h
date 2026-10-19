#ifndef KONOHA_BATTLE_TRAINING_FLOW_H
#define KONOHA_BATTLE_TRAINING_FLOW_H

#include "konoha/battle_action_progression.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_training_entry_kind : std::uint8_t
{
    primary_action,
    secondary_passive,
};

struct battle_training_entry
{
    battle_training_entry_kind kind =
            battle_training_entry_kind::primary_action;
    std::uint8_t slot_index = 0;
    std::uint8_t definition_id = 0;
    std::uint8_t level = 0;
    std::uint8_t unlock_level = 0;

    constexpr bool operator==(
            const battle_training_entry&) const = default;
};

struct battle_training_snapshot
{
    bool active = false;
    std::uint8_t participant_index = 0;
    std::uint8_t character_id = 0;
    int training_points = 0;
    std::size_t entry_index = 0;
    std::size_t entry_count = 0;
    battle_training_entry_kind selected_kind =
            battle_training_entry_kind::primary_action;
    std::uint8_t selected_slot_index = 0;
    std::uint8_t selected_definition_id = 0;
    ability_id selected_action_id = no_ability;
    passive_id selected_passive_id = no_passive;
    std::uint8_t selected_level = 0;
    std::uint8_t selected_unlock_level = 0;
    action_training_error selected_error =
            action_training_error::none;
    action_training_error last_error =
            action_training_error::none;
};

class battle_training_flow
{
public:
    [[nodiscard]] bool begin(
            const std::array<
                    character_progression_record,
                    3>& roster)
    {
        clear();
        for(std::size_t index = 0;
                index < roster.size(); ++index)
        {
            if(_eligible_character(roster[index]))
            {
                _participant_index =
                        static_cast<std::uint8_t>(index);
                _active = true;
                return true;
            }
        }
        return false;
    }

    [[nodiscard]] battle_training_snapshot snapshot(
            const std::array<
                    character_progression_record,
                    3>& roster) const
    {
        battle_training_snapshot result;
        result.active = _active;
        result.participant_index = _participant_index;
        result.entry_index = _entry_index;
        result.last_error = _last_error;
        if(! _active ||
                _participant_index >= roster.size())
        {
            return result;
        }

        const character_progression_record& record =
                roster[_participant_index];
        result.character_id = record.character_id;
        result.training_points = record.training_points;
        if(record.character_id >= unit_definitions.size())
        {
            return result;
        }

        const unit_definition& definition =
                unit_definitions[record.character_id];
        result.entry_count =
                _non_empty_count(definition.primary_slots) +
                _non_empty_count(definition.secondary_slots);
        if(result.entry_count == 0)
        {
            result.entry_index = 0;
            return result;
        }
        result.entry_index %= result.entry_count;

        std::size_t entry_index = 0;
        if(! _select_from_slots(
                   definition.primary_slots,
                   battle_training_entry_kind::primary_action,
                   result.entry_index,
                   entry_index,
                   result))
        {
            (void) _select_from_slots(
                    definition.secondary_slots,
                    battle_training_entry_kind::
                            secondary_passive,
                    result.entry_index,
                    entry_index,
                    result);
        }

        character_progression_record preview = record;
        if(result.selected_kind ==
                battle_training_entry_kind::primary_action)
        {
            result.selected_level =
                    record.primary_action_levels[
                            result.selected_slot_index];
            result.selected_error =
                    train_primary_action(
                            preview,
                            result.selected_slot_index).error;
        }
        else
        {
            result.selected_level =
                    record.secondary_action_levels[
                            result.selected_slot_index];
            result.selected_error =
                    train_secondary_passive(
                            preview,
                            result.selected_slot_index).error;
        }
        return result;
    }

    [[nodiscard]] bool cycle_entry(
            int direction,
            const std::array<
                    character_progression_record,
                    3>& roster)
    {
        const battle_training_snapshot state =
                snapshot(roster);
        if(! state.active || state.entry_count == 0 ||
                direction == 0)
        {
            return false;
        }
        if(direction > 0)
        {
            _entry_index =
                    (_entry_index + 1) %
                    state.entry_count;
        }
        else
        {
            _entry_index =
                    (_entry_index +
                            state.entry_count - 1) %
                    state.entry_count;
        }
        _last_error = action_training_error::none;
        return true;
    }

    [[nodiscard]] bool cycle_action(
            int direction,
            const std::array<
                    character_progression_record,
                    3>& roster)
    {
        return cycle_entry(direction, roster);
    }

    [[nodiscard]] bool cycle_character(
            int direction,
            const std::array<
                    character_progression_record,
                    3>& roster)
    {
        if(! _active || direction == 0)
        {
            return false;
        }
        for(std::size_t offset = 1;
                offset <= roster.size(); ++offset)
        {
            const std::size_t index =
                    direction > 0 ?
                        (_participant_index + offset) %
                                roster.size() :
                        (_participant_index +
                                roster.size() -
                                (offset % roster.size())) %
                                roster.size();
            if(_eligible_character(roster[index]))
            {
                _participant_index =
                        static_cast<std::uint8_t>(index);
                _entry_index = 0;
                _last_error =
                        action_training_error::none;
                return true;
            }
        }
        return false;
    }

    [[nodiscard]] action_training_result confirm(
            std::array<
                    character_progression_record,
                    3>& roster)
    {
        if(! _active ||
                _participant_index >= roster.size())
        {
            _last_error =
                    action_training_error::
                            invalid_character;
            return {
                _last_error,
            };
        }
        const battle_training_snapshot state =
                snapshot(roster);
        if(state.entry_count == 0)
        {
            _last_error =
                    action_training_error::empty_slot;
            return {
                _last_error,
            };
        }

        const action_training_result result =
                state.selected_kind ==
                        battle_training_entry_kind::
                                primary_action ?
                    train_primary_action(
                            roster[_participant_index],
                            state.selected_slot_index) :
                    train_secondary_passive(
                            roster[_participant_index],
                            state.selected_slot_index);
        _last_error = result.error;
        return result;
    }

    void clear()
    {
        _active = false;
        _participant_index = 0;
        _entry_index = 0;
        _last_error = action_training_error::none;
    }

private:
    template<std::size_t SlotCount>
    [[nodiscard]] static constexpr std::size_t
    _non_empty_count(
            const std::array<
                    action_slot_definition,
                    SlotCount>& slots)
    {
        std::size_t result = 0;
        for(const action_slot_definition& slot : slots)
        {
            if(slot.action != 0 &&
                    slot.action != no_ability)
            {
                ++result;
            }
        }
        return result;
    }

    template<std::size_t SlotCount>
    [[nodiscard]] static bool _select_from_slots(
            const std::array<
                    action_slot_definition,
                    SlotCount>& slots,
            battle_training_entry_kind kind,
            std::size_t selected_entry,
            std::size_t& entry_index,
            battle_training_snapshot& output)
    {
        for(std::size_t slot_index = 0;
                slot_index < slots.size(); ++slot_index)
        {
            const action_slot_definition& slot =
                    slots[slot_index];
            if(slot.action == 0 ||
                    slot.action == no_ability)
            {
                continue;
            }
            if(entry_index++ != selected_entry)
            {
                continue;
            }
            output.selected_kind = kind;
            output.selected_slot_index =
                    static_cast<std::uint8_t>(slot_index);
            output.selected_definition_id = slot.action;
            output.selected_unlock_level =
                    slot.unlock_level;
            if(kind ==
                    battle_training_entry_kind::
                            primary_action)
            {
                output.selected_action_id = slot.action;
            }
            else
            {
                output.selected_passive_id = slot.action;
            }
            return true;
        }
        return false;
    }

    [[nodiscard]] static bool _eligible_character(
            const character_progression_record& record)
    {
        return record.active &&
                record.action_states_initialized &&
                record.training_points > 0 &&
                record.character_id <
                        unit_definitions.size();
    }

    bool _active = false;
    std::uint8_t _participant_index = 0;
    std::size_t _entry_index = 0;
    action_training_error _last_error =
            action_training_error::none;
};

}

#endif
