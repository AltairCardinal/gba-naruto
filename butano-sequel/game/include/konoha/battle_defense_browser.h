#ifndef KONOHA_BATTLE_DEFENSE_BROWSER_H
#define KONOHA_BATTLE_DEFENSE_BROWSER_H

#include "konoha/battle_action_catalog.h"
#include "konoha/battle_defense_preparation.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_defense_browser_error : std::uint8_t
{
    none,
    invalid_phase,
    invalid_character,
    invalid_action_reference,
    capacity_exhausted,
};

struct battle_defense_browser_entry
{
    defense_action_kind kind = defense_action_kind::none;
    ability_id action_id = no_ability;
    std::uint8_t tool_slot = no_tool_slot;
    action_definition action = {};
    defense_preparation_error confirmation_error =
            defense_preparation_error::invalid_definition;

    [[nodiscard]] constexpr bool confirmable() const
    {
        return confirmation_error == defense_preparation_error::none;
    }
};

struct battle_defense_browser_result
{
    battle_defense_browser_error error =
            battle_defense_browser_error::none;
    std::array<
            battle_defense_browser_entry,
            battle_action_catalog_capacity> entries = {};
    std::size_t count = 0;

    [[nodiscard]] const battle_defense_browser_entry* find(
            defense_action_kind kind,
            ability_id action_id,
            std::uint8_t tool_slot = no_tool_slot) const
    {
        for(std::size_t index = 0; index < count; ++index)
        {
            const battle_defense_browser_entry& entry =
                    entries[index];
            if(entry.kind == kind &&
                    entry.action_id == action_id &&
                    (kind != defense_action_kind::ninja_tool ||
                     entry.tool_slot == tool_slot))
            {
                return &entry;
            }
        }
        return nullptr;
    }
};

class battle_defense_browser
{
public:
    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_defense_browser_result build(
            const battle_session<MaxUnits>& session)
    {
        if(session.lifecycle() != battle_lifecycle::defense_select ||
                ! session.draft().active)
        {
            return {
                battle_defense_browser_error::invalid_phase,
            };
        }
        const battle_unit_instance* actor =
                session.unit(session.draft().unit_id);
        if(! actor)
        {
            return {
                battle_defense_browser_error::invalid_character,
            };
        }

        battle_defense_browser_result result;
        const battle_action_catalog_result catalog =
                battle_action_catalog::build(*actor);
        if(catalog.error != battle_action_catalog_error::none)
        {
            return {
                _browser_error(catalog.error),
            };
        }
        for(std::size_t index = 0; index < catalog.count; ++index)
        {
            const battle_action_catalog_entry& source =
                    catalog.entries[index];
            const defense_action_kind kind =
                    source.kind ==
                            battle_action_source_kind::ninja_tool ?
                    defense_action_kind::ninja_tool :
                    defense_action_kind::active_action;
            if(! _add(
                       session,
                       source.action,
                       kind,
                       source.tool_slot,
                       result))
            {
                return {
                    battle_defense_browser_error::
                            capacity_exhausted,
                };
            }
        }

        return result;
    }

private:
    [[nodiscard]] static constexpr battle_defense_browser_error
    _browser_error(battle_action_catalog_error error)
    {
        switch(error)
        {
        case battle_action_catalog_error::none:
            return battle_defense_browser_error::none;
        case battle_action_catalog_error::invalid_character:
            return battle_defense_browser_error::
                    invalid_character;
        case battle_action_catalog_error::invalid_action_reference:
            return battle_defense_browser_error::
                    invalid_action_reference;
        case battle_action_catalog_error::capacity_exhausted:
            return battle_defense_browser_error::
                    capacity_exhausted;
        default:
            break;
        }
        return battle_defense_browser_error::invalid_character;
    }

    template<std::size_t MaxUnits>
    [[nodiscard]] static bool _add(
            const battle_session<MaxUnits>& session,
            const action_definition& action,
            defense_action_kind kind,
            std::uint8_t tool_slot,
            battle_defense_browser_result& result)
    {
        if(result.count == result.entries.size())
        {
            return false;
        }
        const defense_preparation_preview preview =
                battle_defense_preparation::preview(
                        session, action);
        result.entries[result.count] = {
            kind,
            action.id,
            tool_slot,
            action,
            preview.error,
        };
        ++result.count;
        return true;
    }
};

}

#endif
