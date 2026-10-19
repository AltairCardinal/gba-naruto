#include "konoha/battle_campaign_save.h"

#include <cassert>
#include <cstddef>
#include <cstdint>

using namespace konoha;

namespace
{

std::uint32_t crc32(
        const std::uint8_t* data,
        std::size_t size)
{
    std::uint32_t crc = 0xFFFFFFFFU;
    for(std::size_t index = 0; index < size; ++index)
    {
        crc ^= data[index];
        for(int bit = 0; bit < 8; ++bit)
        {
            const std::uint32_t mask =
                    0U - (crc & 1U);
            crc = (crc >> 1) ^
                    (0xEDB88320U & mask);
        }
    }
    return ~crc;
}

void write_u32(
        std::uint8_t* output,
        std::uint32_t value)
{
    for(int shift = 0; shift < 32; shift += 8)
    {
        output[shift / 8] =
                static_cast<std::uint8_t>(
                        value >> shift);
    }
}

character_progression_record active_character(
        std::uint8_t character_id,
        int level,
        int experience,
        int training_points)
{
    character_progression_record result = {
        character_id,
        level,
        experience,
        training_points,
        true,
    };
    assert(initialize_character_action_progression(
            result,
            unit_definitions[character_id]));
    return result;
}

battle_campaign_state campaign_fixture()
{
    battle_campaign_state result =
            empty_battle_campaign();
    result.chapter_id = 12;
    result.flags = 0x10203040U;
    assert(activate_battle_campaign_character(
            result,
            active_character(1, 2, 25, 1)));
    assert(activate_battle_campaign_character(
            result,
            active_character(2, 3, 40, 2)));
    assert(activate_battle_campaign_character(
            result,
            active_character(3, 4, 60, 3)));
    assert(set_battle_campaign_party(
            result, { 1, 2, 3 }));
    result.characters[1].equipped_tools =
            { 1, 11, 67, 93, 0, 0, 0, 0, 0 };
    result.characters[2].equipped_tools =
            { 46, 47, 48, 0, 0, 0, 0, 0, 0 };
    result.characters[1]
            .progression.primary_action_levels[6] = 1;
    result.characters[2]
            .progression.secondary_action_levels[0] = 2;
    result.inventory.ninja_tools[1] = 4;
    result.inventory.ninja_tools[2] = 1;
    result.inventory.ninja_tools[11] = 1;
    result.inventory.ninja_tools[46] = 1;
    result.inventory.ninja_tools[47] = 1;
    result.inventory.ninja_tools[48] = 1;
    result.inventory.ninja_tools[67] = 1;
    result.inventory.ninja_tools[93] = 1;
    result.inventory.materials[3] = 2;
    result.inventory.materials[17] = 1;
    return result;
}

void refresh_crc(battle_campaign_save_slot& slot)
{
    write_u32(
            slot.bytes.data() +
                    battle_campaign_save_crc_offset,
            crc32(
                    slot.bytes.data(),
                    battle_campaign_save_crc_offset));
}

}

int main()
{
    static_assert(battle_campaign_save_slot_size ==
                  4096);
    static_assert(battle_campaign_save_version == 2);
    static_assert(
            battle_campaign_save_payload_size <
            battle_campaign_save_crc_offset);

    const battle_campaign_state campaign =
            campaign_fixture();
    battle_campaign_save_slot first;
    assert(encode_battle_campaign_slot(
                   campaign, 7, first) ==
           battle_campaign_save_error::none);
    battle_campaign_save_slot second;
    assert(encode_battle_campaign_slot(
                   campaign, 7, second) ==
           battle_campaign_save_error::none);
    assert(first == second);
    constexpr std::size_t inventory_offset =
            battle_campaign_save_payload_offset + 10;
    constexpr std::size_t material_offset =
            inventory_offset +
            battle_campaign_ninja_tool_quantity_capacity;
    assert(first.bytes[inventory_offset + 1] == 4);
    assert(first.bytes[inventory_offset + 2] == 1);
    assert(first.bytes[inventory_offset + 67] == 1);
    assert(first.bytes[material_offset + 3] == 2);
    assert(first.bytes[material_offset + 17] == 1);

    const battle_campaign_save_decode_result decoded =
            decode_battle_campaign_slot(first);
    assert(decoded.error ==
           battle_campaign_save_error::none);
    assert(! decoded.used_default);
    assert(decoded.generation == 7);
    assert(decoded.campaign == campaign);

    battle_campaign_save_decode_result decoded_in_place;
    decode_battle_campaign_slot_into(
            first, decoded_in_place);
    assert(decoded_in_place.valid());
    assert(decoded_in_place.generation == 7);
    assert(decoded_in_place.campaign == campaign);

    battle_campaign_save_slot bad_magic = first;
    bad_magic.bytes[0] = 0;
    assert(decode_battle_campaign_slot(bad_magic).error ==
           battle_campaign_save_error::bad_magic);

    battle_campaign_save_slot bad_version = first;
    bad_version.bytes[4] =
            battle_campaign_save_version + 1;
    assert(decode_battle_campaign_slot(bad_version).error ==
           battle_campaign_save_error::
                   unsupported_version);

    battle_campaign_save_slot bad_payload_size = first;
    bad_payload_size.bytes[6] ^= 1;
    assert(
            decode_battle_campaign_slot(
                    bad_payload_size).error ==
            battle_campaign_save_error::
                    bad_payload_size);

    battle_campaign_save_slot bad_crc = first;
    bad_crc.bytes[50] ^= 0x80;
    assert(decode_battle_campaign_slot(bad_crc).error ==
           battle_campaign_save_error::bad_crc);

    battle_campaign_state invalid_level = campaign;
    invalid_level.characters[1].progression.level = 0;
    battle_campaign_save_slot invalid_output = first;
    assert(encode_battle_campaign_slot(
                   invalid_level, 8, invalid_output) ==
           battle_campaign_save_error::invalid_state);
    assert(invalid_output == first);

    battle_campaign_state invalid_action = campaign;
    invalid_action.characters[1]
            .progression.primary_action_levels[0] = 4;
    assert(encode_battle_campaign_slot(
                   invalid_action, 8, invalid_output) ==
           battle_campaign_save_error::invalid_state);
    assert(invalid_output == first);

    battle_campaign_state invalid_tool = campaign;
    invalid_tool.characters[1].equipped_tools[0] = 94;
    assert(encode_battle_campaign_slot(
                   invalid_tool, 8, invalid_output) ==
           battle_campaign_save_error::invalid_state);
    assert(invalid_output == first);

    battle_campaign_state overallocated_tool = campaign;
    overallocated_tool.inventory.ninja_tools[11] = 0;
    assert(encode_battle_campaign_slot(
                   overallocated_tool, 8, invalid_output) ==
           battle_campaign_save_error::invalid_state);
    assert(invalid_output == first);

    battle_campaign_state over_capacity = campaign;
    over_capacity.inventory.ninja_tools[1] = 6;
    over_capacity.characters[1].equipped_tools =
            { 1, 1, 1, 1, 1, 1, 0, 0, 0 };
    assert(encode_battle_campaign_slot(
                   over_capacity, 8, invalid_output) ==
           battle_campaign_save_error::invalid_state);
    assert(invalid_output == first);

    battle_campaign_state ineligible_tool = campaign;
    ineligible_tool.inventory.ninja_tools[14] = 1;
    ineligible_tool.characters[1].equipped_tools[0] = 14;
    assert(encode_battle_campaign_slot(
                   ineligible_tool, 8, invalid_output) ==
           battle_campaign_save_error::invalid_state);
    assert(invalid_output == first);

    battle_campaign_state duplicate_party = campaign;
    duplicate_party.party = { 1, 1, 3 };
    assert(encode_battle_campaign_slot(
                   duplicate_party, 8, invalid_output) ==
           battle_campaign_save_error::invalid_state);
    assert(invalid_output == first);

    battle_campaign_state invalid_tool_sentinel =
            campaign;
    invalid_tool_sentinel.inventory.ninja_tools[0] = 1;
    assert(encode_battle_campaign_slot(
                   invalid_tool_sentinel,
                   8,
                   invalid_output) ==
           battle_campaign_save_error::invalid_state);
    assert(invalid_output == first);

    battle_campaign_state invalid_material_sentinel =
            campaign;
    invalid_material_sentinel.inventory.materials[0] =
            1;
    assert(encode_battle_campaign_slot(
                   invalid_material_sentinel,
                   8,
                   invalid_output) ==
           battle_campaign_save_error::invalid_state);
    assert(invalid_output == first);

    battle_campaign_save_slot invalid_saved_tool_sentinel =
            first;
    invalid_saved_tool_sentinel
            .bytes[inventory_offset] = 1;
    refresh_crc(invalid_saved_tool_sentinel);
    assert(decode_battle_campaign_slot(
                   invalid_saved_tool_sentinel)
                   .error ==
           battle_campaign_save_error::invalid_state);

    battle_campaign_save_slot
            invalid_saved_material_sentinel = first;
    invalid_saved_material_sentinel
            .bytes[material_offset] = 1;
    refresh_crc(invalid_saved_material_sentinel);
    assert(decode_battle_campaign_slot(
                   invalid_saved_material_sentinel)
                   .error ==
           battle_campaign_save_error::invalid_state);

    battle_campaign_save_slot valid_crc_invalid_state =
            first;
    constexpr std::size_t first_character_level_offset =
            battle_campaign_save_payload_offset +
            battle_campaign_save_campaign_prefix_size +
            battle_campaign_save_character_size +
            1;
    valid_crc_invalid_state.bytes[
            first_character_level_offset] = 0;
    refresh_crc(valid_crc_invalid_state);
    assert(
            decode_battle_campaign_slot(
                    valid_crc_invalid_state).error ==
            battle_campaign_save_error::invalid_state);

    battle_campaign_save_slot older;
    battle_campaign_save_slot newer;
    battle_campaign_state newer_campaign = campaign;
    newer_campaign.characters[1].progression.level = 3;
    assert(encode_battle_campaign_slot(
                   campaign, 10, older) ==
           battle_campaign_save_error::none);
    assert(encode_battle_campaign_slot(
                   newer_campaign, 11, newer) ==
           battle_campaign_save_error::none);
    const battle_campaign_save_decode_result latest =
            load_latest_battle_campaign_slot(
                    older,
                    newer,
                    empty_battle_campaign());
    assert(latest.error ==
           battle_campaign_save_error::none);
    assert(latest.source_slot == 1);
    assert(latest.generation == 11);
    assert(latest.campaign == newer_campaign);

    battle_campaign_save_decode_result latest_workspace_a;
    battle_campaign_save_decode_result latest_workspace_b;
    const battle_campaign_save_decode_result&
            latest_in_place =
                    load_latest_battle_campaign_slot_into(
                            older,
                            newer,
                            empty_battle_campaign(),
                            latest_workspace_a,
                            latest_workspace_b);
    assert(&latest_in_place == &latest_workspace_b);
    assert(latest_in_place.source_slot == 1);
    assert(latest_in_place.generation == 11);
    assert(latest_in_place.campaign == newer_campaign);

    newer.bytes[battle_campaign_save_crc_offset] ^= 1;
    const battle_campaign_save_decode_result recovered =
            load_latest_battle_campaign_slot(
                    older,
                    newer,
                    empty_battle_campaign());
    assert(recovered.error ==
           battle_campaign_save_error::none);
    assert(recovered.source_slot == 0);
    assert(recovered.generation == 10);
    assert(recovered.campaign == campaign);

    const battle_campaign_save_slot erased = [] {
        battle_campaign_save_slot value;
        value.bytes.fill(0xFF);
        return value;
    }();
    const battle_campaign_state default_campaign =
            campaign_fixture();
    const battle_campaign_save_decode_result defaults =
            load_latest_battle_campaign_slot(
                    erased,
                    erased,
                    default_campaign);
    assert(defaults.error ==
           battle_campaign_save_error::none);
    assert(defaults.used_default);
    assert(defaults.source_slot == -1);
    assert(defaults.generation == 0);
    assert(defaults.campaign == default_campaign);

    const battle_campaign_save_target both_valid =
            next_battle_campaign_save_target(
                    older,
                    [] {
                        battle_campaign_save_slot value;
                        assert(encode_battle_campaign_slot(
                                       campaign_fixture(),
                                       11,
                                       value) ==
                               battle_campaign_save_error::
                                       none);
                        return value;
                    }());
    assert(both_valid.slot_index == 0);
    assert(both_valid.generation == 12);

    const battle_campaign_save_target one_valid =
            next_battle_campaign_save_target(
                    older, erased);
    assert(one_valid.slot_index == 1);
    assert(one_valid.generation == 11);

    const battle_campaign_save_target
            one_valid_in_place =
                    next_battle_campaign_save_target_into(
                            older,
                            erased,
                            latest_workspace_a,
                            latest_workspace_b);
    assert(one_valid_in_place.slot_index == 1);
    assert(one_valid_in_place.generation == 11);

    const battle_campaign_save_target both_invalid =
            next_battle_campaign_save_target(
                    erased, erased);
    assert(both_invalid.slot_index == 0);
    assert(both_invalid.generation == 1);

    battle_campaign_save_slot generation_max;
    battle_campaign_save_slot generation_wrapped;
    assert(encode_battle_campaign_slot(
                   campaign,
                   std::numeric_limits<
                           std::uint32_t>::max(),
                   generation_max) ==
           battle_campaign_save_error::none);
    assert(encode_battle_campaign_slot(
                   newer_campaign,
                   1,
                   generation_wrapped) ==
           battle_campaign_save_error::none);
    const battle_campaign_save_decode_result
            wrapped_latest =
                    load_latest_battle_campaign_slot(
                            generation_max,
                            generation_wrapped,
                            empty_battle_campaign());
    assert(wrapped_latest.source_slot == 1);
    assert(wrapped_latest.generation == 1);
    assert(wrapped_latest.campaign == newer_campaign);
    const battle_campaign_save_target wrapped_target =
            next_battle_campaign_save_target(
                    generation_max,
                    generation_wrapped);
    assert(wrapped_target.slot_index == 0);
    assert(wrapped_target.generation == 2);
}
