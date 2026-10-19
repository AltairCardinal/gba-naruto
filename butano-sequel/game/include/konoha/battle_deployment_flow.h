#ifndef KONOHA_BATTLE_DEPLOYMENT_FLOW_H
#define KONOHA_BATTLE_DEPLOYMENT_FLOW_H

#include "konoha/battle_scenario_loader.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_deployment_phase : std::uint8_t
{
    inactive,
    unit_confirmation,
    start_confirmation,
    complete,
    cancelled,
    error,
};

enum class battle_deployment_error : std::uint8_t
{
    none,
    invalid_variant,
    unresolved_placeholder,
    invalid_character,
    inactive_character,
    invalid_phase,
};

struct battle_deployment_result
{
    battle_deployment_error error =
            battle_deployment_error::none;
    std::uint8_t record_id = no_scenario_record;

    [[nodiscard]] constexpr bool success() const
    {
        return error == battle_deployment_error::none;
    }
};

struct battle_deployment_entry
{
    std::uint8_t record_id = no_scenario_record;
    std::uint8_t character_id = no_scenario_character;
    battle_side side = battle_side::player;
    grid_point position = {};
    battle_facing facing = battle_facing::up;
};

class battle_deployment_flow
{
public:
    [[nodiscard]] battle_deployment_result prepare(
            const battle_scenario_definition& scenario,
            std::uint8_t variant,
            const battle_scenario_load_policy& policy)
    {
        reset();
        if(variant >= scenario.variants.size())
        {
            return fail(
                    battle_deployment_error::
                            invalid_variant,
                    no_scenario_record);
        }

        const auto& slots = scenario.variants[variant];
        for(std::size_t index = 0;
                index < slots.size(); ++index)
        {
            const battle_scenario_unit_slot& slot =
                    slots[index];
            if(! battle_scenario_slot_enabled(
                       slot, policy))
            {
                continue;
            }
            const battle_scenario_character_result
                    character =
                            resolve_battle_scenario_character(
                                    slot, policy);
            if(! character.success())
            {
                return fail(
                        deployment_error(character.error),
                        static_cast<std::uint8_t>(index));
            }
            _entries[_entry_count++] = {
                static_cast<std::uint8_t>(index),
                character.character_id,
                slot.side,
                slot.position,
                slot.facing,
            };
        }

        if(_entry_count == 0)
        {
            return fail(
                    battle_deployment_error::
                            invalid_phase,
                    no_scenario_record);
        }
        _phase =
                battle_deployment_phase::
                        unit_confirmation;
        return {};
    }

    [[nodiscard]] battle_deployment_result confirm()
    {
        if(_phase ==
                battle_deployment_phase::
                        unit_confirmation)
        {
            ++_current_index;
            if(_current_index >= _entry_count)
            {
                _phase =
                        battle_deployment_phase::
                                start_confirmation;
                _current_index = _entry_count;
            }
            return {};
        }
        if(_phase ==
                battle_deployment_phase::
                        start_confirmation)
        {
            _phase = battle_deployment_phase::complete;
            return {};
        }
        return {
            battle_deployment_error::invalid_phase,
            no_scenario_record,
        };
    }

    [[nodiscard]] battle_deployment_result cancel()
    {
        if(_phase ==
                battle_deployment_phase::
                        start_confirmation)
        {
            _phase =
                    battle_deployment_phase::
                            unit_confirmation;
            _current_index = _entry_count - 1;
            return {};
        }
        if(_phase ==
                battle_deployment_phase::
                        unit_confirmation)
        {
            if(_current_index > 0)
            {
                --_current_index;
            }
            else
            {
                _phase =
                        battle_deployment_phase::
                                cancelled;
            }
            return {};
        }
        return {
            battle_deployment_error::invalid_phase,
            no_scenario_record,
        };
    }

    [[nodiscard]] constexpr
    battle_deployment_phase phase() const
    {
        return _phase;
    }

    [[nodiscard]] constexpr bool complete() const
    {
        return _phase == battle_deployment_phase::complete;
    }

    [[nodiscard]] constexpr bool cancelled() const
    {
        return _phase == battle_deployment_phase::cancelled;
    }

    [[nodiscard]] constexpr std::size_t entry_count() const
    {
        return _entry_count;
    }

    [[nodiscard]] constexpr const battle_deployment_entry*
    entry(int index) const
    {
        return index >= 0 &&
                       index <
                               static_cast<int>(
                                       _entry_count) ?
                &_entries[static_cast<std::size_t>(index)] :
                nullptr;
    }

    [[nodiscard]] constexpr const battle_deployment_entry*
    current_entry() const
    {
        return _phase ==
                               battle_deployment_phase::
                                       unit_confirmation &&
                       _current_index < _entry_count ?
                &_entries[_current_index] :
                nullptr;
    }

private:
    [[nodiscard]] static constexpr battle_deployment_error
    deployment_error(battle_scenario_load_error error)
    {
        switch(error)
        {
        case battle_scenario_load_error::
                unresolved_deployment_placeholder:
            return battle_deployment_error::
                    unresolved_placeholder;
        case battle_scenario_load_error::inactive_character:
            return battle_deployment_error::
                    inactive_character;
        default:
            return battle_deployment_error::
                    invalid_character;
        }
    }

    [[nodiscard]] battle_deployment_result fail(
            battle_deployment_error error,
            std::uint8_t record_id)
    {
        _phase = battle_deployment_phase::error;
        return { error, record_id };
    }

    void reset()
    {
        _entries = {};
        _entry_count = 0;
        _current_index = 0;
        _phase = battle_deployment_phase::inactive;
    }

    std::array<battle_deployment_entry, 12> _entries = {};
    std::size_t _entry_count = 0;
    std::size_t _current_index = 0;
    battle_deployment_phase _phase =
            battle_deployment_phase::inactive;
};

}

#endif
