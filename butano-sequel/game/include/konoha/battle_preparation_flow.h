#ifndef KONOHA_BATTLE_PREPARATION_FLOW_H
#define KONOHA_BATTLE_PREPARATION_FLOW_H

#include "konoha/battle_campaign.h"
#include "konoha/battle_campaign_equipment_service.h"
#include "konoha/ninja_tool_upgrade_service.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_preparation_phase : std::uint8_t
{
    root,
    equipment_root,
    equip,
    unequip,
    upgrade,
    feedback,
    map_preview,
    start_confirmation,
    save_requested,
    ready,
    overview,
};

enum class battle_preparation_root_option : std::uint8_t
{
    party_equipment,
    inspect_map,
    start_battle,
    save,
};

enum class battle_preparation_equipment_option :
        std::uint8_t
{
    equip,
    unequip,
    upgrade,
    back,
};

enum class battle_preparation_operation : std::uint8_t
{
    none,
    equip,
    unequip,
    upgrade,
};

struct battle_preparation_snapshot
{
    battle_preparation_phase phase =
            battle_preparation_phase::root;
    battle_preparation_root_option root_option =
            battle_preparation_root_option::
                    party_equipment;
    battle_preparation_equipment_option equipment_option =
            battle_preparation_equipment_option::equip;
    std::uint8_t character_id = 0;
    std::size_t party_count = 0;
    std::size_t party_index = 0;
    std::size_t equipment_count = 0;
    std::size_t equipment_index = 0;
    std::size_t equipment_slot = 0;
    ninja_tool_id equipment_tool_id = 0;
    std::uint8_t equipment_owned_quantity = 0;
    std::size_t equipment_equipped_quantity = 0;
    std::size_t equipment_available_quantity = 0;
    std::size_t upgrade_count = 0;
    std::size_t upgrade_index = 0;
    ninja_tool_id output_tool_id = 0;
    ninja_tool_id parent_tool_id = 0;
    std::uint8_t required_material_id = 0;
    std::uint8_t parent_quantity = 0;
    std::uint8_t material_quantity = 0;
    std::uint8_t output_quantity = 0;
    ninja_tool_upgrade_error last_upgrade_error =
            ninja_tool_upgrade_error::none;
    bool last_upgrade_succeeded = false;
    battle_preparation_operation last_operation =
            battle_preparation_operation::none;
    battle_campaign_equipment_error
            last_equipment_error =
                    battle_campaign_equipment_error::none;
    bool last_equipment_succeeded = false;
    bool start_confirmation_yes = true;
};

class battle_preparation_flow
{
public:
    [[nodiscard]] bool load(
            battle_campaign_state& campaign,
            std::uint8_t character_id,
            bool show_overview = false)
    {
        if(character_id == 0 ||
                character_id >=
                        battle_campaign_character_capacity ||
                ! campaign.characters[character_id]
                           .progression.active ||
                campaign.characters[character_id]
                           .progression.character_id !=
                        character_id)
        {
            return false;
        }
        std::size_t party_count = 0;
        std::size_t party_index =
                battle_campaign_party_capacity;
        for(std::size_t index = 0;
                index < campaign.party.size();
                ++index)
        {
            if(campaign.party[index] == 0)
            {
                break;
            }
            if(campaign.party[index] == character_id)
            {
                party_index = index;
            }
            ++party_count;
        }
        if(party_index ==
                battle_campaign_party_capacity)
        {
            return false;
        }
        _campaign = &campaign;
        _character_id = character_id;
        _party_count = party_count;
        _party_index = party_index;
        _phase = show_overview ?
                battle_preparation_phase::overview :
                battle_preparation_phase::root;
        _root_option =
                battle_preparation_root_option::
                        party_equipment;
        _equipment_option =
                battle_preparation_equipment_option::equip;
        _start_confirmation_yes = true;
        _candidate_count = 0;
        _candidate_index = 0;
        _feedback_output = 0;
        _feedback_slot = 0;
        _last_operation =
                battle_preparation_operation::none;
        _last_equipment_error =
                battle_campaign_equipment_error::none;
        _last_equipment_succeeded = false;
        _last_upgrade_error =
                ninja_tool_upgrade_error::none;
        _last_upgrade_succeeded = false;
        return true;
    }

    [[nodiscard]] bool switch_character(int delta)
    {
        if(! _campaign ||
                delta == 0 ||
                _phase !=
                        battle_preparation_phase::
                                equipment_root ||
                _party_count < 2)
        {
            return false;
        }
        if(delta > 0)
        {
            _party_index =
                    (_party_index + 1) % _party_count;
        }
        else
        {
            _party_index =
                    (_party_index +
                     _party_count - 1) % _party_count;
        }
        _character_id =
                _campaign->party[_party_index];
        _candidate_count = 0;
        _candidate_index = 0;
        _feedback_output = 0;
        _feedback_slot = 0;
        _last_operation =
                battle_preparation_operation::none;
        _last_equipment_error =
                battle_campaign_equipment_error::none;
        _last_equipment_succeeded = false;
        _last_upgrade_error =
                ninja_tool_upgrade_error::none;
        _last_upgrade_succeeded = false;
        return true;
    }

    [[nodiscard]] bool move(int delta)
    {
        if(! _campaign || delta == 0)
        {
            return false;
        }
        if(_phase == battle_preparation_phase::root)
        {
            constexpr int option_count = 4;
            int option = static_cast<int>(_root_option);
            option = (option +
                      (delta > 0 ? 1 : option_count - 1)) %
                    option_count;
            _root_option =
                    static_cast<
                            battle_preparation_root_option>(
                            option);
            return true;
        }
        if(_phase ==
                battle_preparation_phase::equipment_root)
        {
            constexpr int option_count = 4;
            int option =
                    static_cast<int>(_equipment_option);
            option = (option +
                      (delta > 0 ? 1 : option_count - 1)) %
                    option_count;
            _equipment_option =
                    static_cast<
                            battle_preparation_equipment_option>(
                            option);
            return true;
        }
        if(_phase ==
                battle_preparation_phase::
                        start_confirmation)
        {
            _start_confirmation_yes =
                    ! _start_confirmation_yes;
            return true;
        }
        if((_phase != battle_preparation_phase::equip &&
            _phase != battle_preparation_phase::unequip &&
            _phase != battle_preparation_phase::upgrade) ||
                _candidate_count == 0)
        {
            return false;
        }
        if(delta > 0)
        {
            _candidate_index =
                    (_candidate_index + 1) %
                    _candidate_count;
        }
        else
        {
            _candidate_index =
                    (_candidate_index +
                     _candidate_count - 1) %
                    _candidate_count;
        }
        return true;
    }

    [[nodiscard]] bool confirm()
    {
        if(! _campaign)
        {
            return false;
        }
        switch(_phase)
        {
        case battle_preparation_phase::overview:
            _phase = battle_preparation_phase::root;
            return true;
        case battle_preparation_phase::root:
            if(_root_option ==
                    battle_preparation_root_option::
                            party_equipment)
            {
                _phase =
                        battle_preparation_phase::
                                equipment_root;
                _equipment_option =
                        battle_preparation_equipment_option::
                                equip;
                return true;
            }
            if(_root_option ==
                    battle_preparation_root_option::
                            inspect_map)
            {
                _phase =
                        battle_preparation_phase::
                                map_preview;
                return true;
            }
            if(_root_option ==
                    battle_preparation_root_option::
                            start_battle)
            {
                _phase =
                        battle_preparation_phase::
                                start_confirmation;
                _start_confirmation_yes = true;
                return true;
            }
            _phase =
                    battle_preparation_phase::
                            save_requested;
            return true;
        case battle_preparation_phase::equipment_root:
            if(_equipment_option ==
                    battle_preparation_equipment_option::
                            equip)
            {
                rebuild_equip_candidates();
                if(_candidate_count == 0)
                {
                    show_equipment_feedback(
                            battle_preparation_operation::
                                    equip,
                            0,
                            0,
                            battle_campaign_equipment_error::
                                    no_available_copy);
                }
                else
                {
                    _phase =
                            battle_preparation_phase::equip;
                }
            }
            else if(_equipment_option ==
                    battle_preparation_equipment_option::
                            unequip)
            {
                rebuild_unequip_candidates();
                if(_candidate_count == 0)
                {
                    show_equipment_feedback(
                            battle_preparation_operation::
                                    unequip,
                            0,
                            0,
                            battle_campaign_equipment_error::
                                    empty_slot);
                }
                else
                {
                    _phase =
                            battle_preparation_phase::unequip;
                }
            }
            else if(_equipment_option ==
                    battle_preparation_equipment_option::
                            upgrade)
            {
                rebuild_upgrade_candidates();
                if(_candidate_count == 0)
                {
                    show_upgrade_feedback(
                            0,
                            ninja_tool_upgrade_error::
                                    no_recipe);
                }
                else
                {
                    _phase =
                            battle_preparation_phase::upgrade;
                }
            }
            else
            {
                _phase = battle_preparation_phase::root;
            }
            return true;
        case battle_preparation_phase::equip:
        {
            if(_candidate_count == 0)
            {
                return false;
            }
            const ninja_tool_id tool_id =
                    _candidates[_candidate_index];
            const battle_campaign_equipment_error error =
                    equip_campaign_ninja_tool(
                            *_campaign,
                            _character_id,
                            tool_id);
            show_equipment_feedback(
                    battle_preparation_operation::equip,
                    tool_id,
                    0,
                    error);
            return true;
        }
        case battle_preparation_phase::unequip:
        {
            if(_candidate_count == 0)
            {
                return false;
            }
            const std::size_t slot =
                    _candidates[_candidate_index];
            const ninja_tool_id tool_id =
                    _campaign->characters[_character_id]
                            .equipped_tools[slot];
            const battle_campaign_equipment_error error =
                    unequip_campaign_ninja_tool(
                            *_campaign,
                            _character_id,
                            slot);
            show_equipment_feedback(
                    battle_preparation_operation::unequip,
                    tool_id,
                    slot,
                    error);
            return true;
        }
        case battle_preparation_phase::upgrade:
        {
            if(_candidate_count == 0)
            {
                return false;
            }
            const ninja_tool_id output =
                    _candidates[_candidate_index];
            const ninja_tool_upgrade_error error =
                    upgrade_ninja_tool(
                            *_campaign,
                            output,
                            _character_id);
            show_upgrade_feedback(
                    output,
                    error);
            return true;
        }
        case battle_preparation_phase::feedback:
            return close_feedback();
        case battle_preparation_phase::map_preview:
            _phase = battle_preparation_phase::root;
            return true;
        case battle_preparation_phase::
                start_confirmation:
            _phase = _start_confirmation_yes ?
                    battle_preparation_phase::ready :
                    battle_preparation_phase::root;
            return true;
        case battle_preparation_phase::ready:
        case battle_preparation_phase::save_requested:
            return false;
        }
        return false;
    }

    [[nodiscard]] bool cancel()
    {
        if(! _campaign)
        {
            return false;
        }
        switch(_phase)
        {
        case battle_preparation_phase::equipment_root:
        case battle_preparation_phase::map_preview:
            _phase = battle_preparation_phase::root;
            return true;
        case battle_preparation_phase::equip:
        case battle_preparation_phase::unequip:
        case battle_preparation_phase::upgrade:
            _phase =
                    battle_preparation_phase::
                            equipment_root;
            return true;
        case battle_preparation_phase::feedback:
            return close_feedback();
        case battle_preparation_phase::
                start_confirmation:
            _phase = battle_preparation_phase::root;
            return true;
        case battle_preparation_phase::root:
        case battle_preparation_phase::overview:
        case battle_preparation_phase::save_requested:
        case battle_preparation_phase::ready:
            return false;
        }
        return false;
    }

    [[nodiscard]] battle_preparation_snapshot
    snapshot() const
    {
        battle_preparation_snapshot result;
        result.phase = _phase;
        result.root_option = _root_option;
        result.equipment_option = _equipment_option;
        result.character_id = _character_id;
        result.party_count = _party_count;
        result.party_index = _party_index;
        result.last_operation = _last_operation;
        result.last_equipment_error =
                _last_equipment_error;
        result.last_equipment_succeeded =
                _last_equipment_succeeded;
        result.start_confirmation_yes =
                _start_confirmation_yes;
        result.last_upgrade_error =
                _last_upgrade_error;
        result.last_upgrade_succeeded =
                _last_upgrade_succeeded;
        if(! _campaign)
        {
            return result;
        }

        if(_phase == battle_preparation_phase::equip ||
                _phase == battle_preparation_phase::unequip ||
                (_phase ==
                         battle_preparation_phase::feedback &&
                 (_last_operation ==
                          battle_preparation_operation::equip ||
                  _last_operation ==
                          battle_preparation_operation::
                                  unequip)))
        {
            result.equipment_count = _candidate_count;
            result.equipment_index = _candidate_index;
            if(_phase ==
                    battle_preparation_phase::feedback)
            {
                result.equipment_tool_id =
                        _feedback_output;
                result.equipment_slot = _feedback_slot;
            }
            else if(_candidate_index < _candidate_count)
            {
                if(_phase ==
                        battle_preparation_phase::equip)
                {
                    result.equipment_tool_id =
                            _candidates[_candidate_index];
                }
                else
                {
                    result.equipment_slot =
                            _candidates[_candidate_index];
                    result.equipment_tool_id =
                            _campaign
                                    ->characters[_character_id]
                                    .equipped_tools[
                                            result.equipment_slot];
                }
            }
            const ninja_tool_id tool_id =
                    result.equipment_tool_id;
            if(tool_id != no_ninja_tool &&
                    tool_id <
                            battle_campaign_ninja_tool_quantity_capacity)
            {
                result.equipment_owned_quantity =
                        _campaign->inventory.ninja_tools[
                                tool_id];
                result.equipment_equipped_quantity =
                        equipped_campaign_ninja_tool_count(
                                *_campaign,
                                tool_id);
                result.equipment_available_quantity =
                        available_campaign_ninja_tool_count(
                                *_campaign,
                                tool_id);
            }
            return result;
        }

        result.upgrade_count = _candidate_count;
        result.upgrade_index = _candidate_index;
        ninja_tool_id output = 0;
        if(_phase == battle_preparation_phase::feedback)
        {
            output = _feedback_output;
        }
        else if(_candidate_index < _candidate_count)
        {
            output = _candidates[_candidate_index];
        }
        result.output_tool_id = output;
        if(output == 0 ||
                output >= ninja_tool_upgrade_recipes.size())
        {
            return result;
        }
        const ninja_tool_upgrade_recipe& recipe =
                ninja_tool_upgrade_recipes[output];
        result.parent_tool_id = recipe.parent_tool_id;
        result.required_material_id =
                recipe.required_material_id;
        result.parent_quantity =
                _campaign->inventory.ninja_tools[
                        recipe.parent_tool_id];
        result.material_quantity =
                _campaign->inventory.materials[
                        recipe.required_material_id];
        result.output_quantity =
                _campaign->inventory.ninja_tools[output];
        return result;
    }

private:
    void rebuild_equip_candidates()
    {
        _candidate_count = 0;
        _candidate_index = 0;
        if(! _campaign)
        {
            return;
        }
        for(std::size_t tool = 1;
                tool <
                        battle_campaign_ninja_tool_quantity_capacity;
                ++tool)
        {
            if(available_campaign_ninja_tool_count(
                       *_campaign,
                       static_cast<ninja_tool_id>(tool)) >
                            0 &&
                    character_is_eligible(
                            ninja_tool_upgrade_recipes[tool],
                            _character_id))
            {
                _candidates[_candidate_count++] =
                        static_cast<ninja_tool_id>(tool);
            }
        }
    }

    void rebuild_unequip_candidates()
    {
        _candidate_count = 0;
        _candidate_index = 0;
        if(! _campaign)
        {
            return;
        }
        const auto& equipped =
                _campaign->characters[_character_id]
                        .equipped_tools;
        for(std::size_t slot = 0;
                slot < equipped.size();
                ++slot)
        {
            if(equipped[slot] != no_ninja_tool)
            {
                _candidates[_candidate_count++] =
                        static_cast<ninja_tool_id>(slot);
            }
        }
    }

    void rebuild_upgrade_candidates()
    {
        _candidate_count = 0;
        _candidate_index = 0;
        if(! _campaign)
        {
            return;
        }
        const auto& equipped =
                _campaign->characters[_character_id]
                        .equipped_tools;
        for(std::size_t output = 1;
                output <
                        ninja_tool_upgrade_recipes.size();
                ++output)
        {
            const ninja_tool_upgrade_recipe& recipe =
                    ninja_tool_upgrade_recipes[output];
            if(recipe.parent_tool_id == 0 ||
                    recipe.required_material_id == 0 ||
                    ! character_is_eligible(
                              recipe,
                              _character_id))
            {
                continue;
            }
            bool parent_equipped = false;
            for(const ninja_tool_id equipped_tool :
                    equipped)
            {
                if(equipped_tool ==
                        recipe.parent_tool_id)
                {
                    parent_equipped = true;
                    break;
                }
            }
            if(parent_equipped &&
                    _campaign->inventory.ninja_tools[
                            recipe.parent_tool_id] > 0)
            {
                _candidates[_candidate_count++] =
                        static_cast<ninja_tool_id>(
                                output);
            }
        }
    }

    void show_upgrade_feedback(
            ninja_tool_id output,
            ninja_tool_upgrade_error error)
    {
        _feedback_output = output;
        _feedback_slot = 0;
        _last_operation =
                battle_preparation_operation::upgrade;
        _last_upgrade_error = error;
        _last_upgrade_succeeded =
                error ==
                ninja_tool_upgrade_error::none;
        _last_equipment_error =
                battle_campaign_equipment_error::none;
        _last_equipment_succeeded = false;
        _phase = battle_preparation_phase::feedback;
    }

    void show_equipment_feedback(
            battle_preparation_operation operation,
            ninja_tool_id tool_id,
            std::size_t slot,
            battle_campaign_equipment_error error)
    {
        _feedback_output = tool_id;
        _feedback_slot = slot;
        _last_operation = operation;
        _last_equipment_error = error;
        _last_equipment_succeeded =
                error ==
                battle_campaign_equipment_error::none;
        _last_upgrade_error =
                ninja_tool_upgrade_error::none;
        _last_upgrade_succeeded = false;
        _phase = battle_preparation_phase::feedback;
    }

    [[nodiscard]] bool close_feedback()
    {
        switch(_last_operation)
        {
        case battle_preparation_operation::equip:
            rebuild_equip_candidates();
            _phase = _candidate_count == 0 ?
                    battle_preparation_phase::
                            equipment_root :
                    battle_preparation_phase::equip;
            break;
        case battle_preparation_operation::unequip:
            rebuild_unequip_candidates();
            _phase = _candidate_count == 0 ?
                    battle_preparation_phase::
                            equipment_root :
                    battle_preparation_phase::unequip;
            break;
        case battle_preparation_operation::upgrade:
            rebuild_upgrade_candidates();
            _phase = _candidate_count == 0 ?
                    battle_preparation_phase::
                            equipment_root :
                    battle_preparation_phase::upgrade;
            break;
        case battle_preparation_operation::none:
            _phase =
                    battle_preparation_phase::
                            equipment_root;
            break;
        }
        return true;
    }

    battle_campaign_state* _campaign = nullptr;
    std::uint8_t _character_id = 0;
    std::size_t _party_count = 0;
    std::size_t _party_index = 0;
    battle_preparation_phase _phase =
            battle_preparation_phase::root;
    battle_preparation_root_option _root_option =
            battle_preparation_root_option::
                    party_equipment;
    battle_preparation_equipment_option _equipment_option =
            battle_preparation_equipment_option::equip;
    std::array<
            ninja_tool_id,
            battle_campaign_ninja_tool_quantity_capacity>
            _candidates = {};
    std::size_t _candidate_count = 0;
    std::size_t _candidate_index = 0;
    ninja_tool_id _feedback_output = 0;
    std::size_t _feedback_slot = 0;
    battle_preparation_operation _last_operation =
            battle_preparation_operation::none;
    battle_campaign_equipment_error
            _last_equipment_error =
                    battle_campaign_equipment_error::none;
    bool _last_equipment_succeeded = false;
    ninja_tool_upgrade_error _last_upgrade_error =
            ninja_tool_upgrade_error::none;
    bool _last_upgrade_succeeded = false;
    bool _start_confirmation_yes = true;
};

}

#endif
