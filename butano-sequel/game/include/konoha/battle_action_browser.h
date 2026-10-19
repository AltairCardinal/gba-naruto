#ifndef KONOHA_BATTLE_ACTION_BROWSER_H
#define KONOHA_BATTLE_ACTION_BROWSER_H

#include "konoha/battle_action_catalog.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_action_browser_error : std::uint8_t
{
    none,
    invalid_phase,
    invalid_character,
    invalid_action_reference,
    capacity_exhausted,
};

struct battle_action_browser_entry
{
    battle_action_source_kind kind =
            battle_action_source_kind::active_action;
    ability_id action_id = no_ability;
    std::uint8_t action_level = 0;
    std::uint8_t tool_slot = no_tool_slot;
    action_definition action = {};
    action_error selection_error =
            action_error::invalid_definition;
    std::uint8_t requirement_reason_code = 0;

    [[nodiscard]] constexpr bool selectable() const
    {
        return selection_error == action_error::none;
    }
};

struct battle_action_browser_result
{
    battle_action_browser_error error =
            battle_action_browser_error::none;
    std::array<
            battle_action_browser_entry,
            battle_action_catalog_capacity> entries = {};
    std::size_t count = 0;

    [[nodiscard]] const battle_action_browser_entry* find(
            battle_action_source_kind kind,
            ability_id action_id,
            std::uint8_t tool_slot = no_tool_slot) const
    {
        for(std::size_t index = 0; index < count; ++index)
        {
            const battle_action_browser_entry& entry =
                    entries[index];
            if(entry.kind == kind &&
                    entry.action_id == action_id &&
                    (kind !=
                             battle_action_source_kind::ninja_tool ||
                     entry.tool_slot == tool_slot))
            {
                return &entry;
            }
        }
        return nullptr;
    }
};

class battle_action_browser
{
public:
    template<std::size_t MaxUnits>
    [[nodiscard]] static battle_action_browser_result build(
            const battle_session<MaxUnits>& session)
    {
        if(session.lifecycle() !=
                        battle_lifecycle::action_drafting ||
                ! session.draft().active)
        {
            return {
                battle_action_browser_error::invalid_phase,
            };
        }
        const battle_unit_instance* actor =
                session.unit(session.draft().unit_id);
        if(! actor)
        {
            return {
                battle_action_browser_error::invalid_phase,
            };
        }

        const battle_action_catalog_result catalog =
                battle_action_catalog::build(*actor);
        if(catalog.error != battle_action_catalog_error::none)
        {
            return {
                _browser_error(catalog.error),
            };
        }

        battle_action_browser_result result;
        for(std::size_t index = 0; index < catalog.count; ++index)
        {
            const battle_action_catalog_entry& source =
                    catalog.entries[index];
            battle_action_browser_entry entry = {
                source.kind,
                source.action_id,
                source.action_level,
                source.tool_slot,
                source.action,
                action_error::none,
                0,
            };
            if(source.kind ==
                    battle_action_source_kind::active_action)
            {
                const action_requirement requirement =
                        battle_action_eligibility::query(
                                *actor, source.action_id);
                if(! requirement.available())
                {
                    entry.selection_error =
                            action_error::
                                    action_requirement_not_met;
                    entry.requirement_reason_code =
                            requirement.reason_code;
                }
            }
            if(entry.selection_error == action_error::none)
            {
                entry.selection_error =
                        battle_action_cost_policy::validate(
                                *actor,
                                source.action.cost,
                                source.action_id);
            }
            if(entry.selection_error == action_error::none &&
                    (source.action.effect.code == 0 ||
                     effect_resolver_registry::handler_for(
                             source.action.effect.code) ==
                             effect_handler_kind::unimplemented))
            {
                entry.selection_error =
                        action_error::unsupported_effect;
            }
            result.entries[result.count] = entry;
            ++result.count;
        }
        return result;
    }

private:
    [[nodiscard]] static constexpr battle_action_browser_error
    _browser_error(battle_action_catalog_error error)
    {
        switch(error)
        {
        case battle_action_catalog_error::none:
            return battle_action_browser_error::none;
        case battle_action_catalog_error::invalid_character:
            return battle_action_browser_error::invalid_character;
        case battle_action_catalog_error::invalid_action_reference:
            return battle_action_browser_error::
                    invalid_action_reference;
        case battle_action_catalog_error::capacity_exhausted:
            return battle_action_browser_error::
                    capacity_exhausted;
        default:
            break;
        }
        return battle_action_browser_error::invalid_character;
    }
};

}

#endif
