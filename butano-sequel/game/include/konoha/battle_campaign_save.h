#ifndef KONOHA_BATTLE_CAMPAIGN_SAVE_H
#define KONOHA_BATTLE_CAMPAIGN_SAVE_H

#include "konoha/battle_campaign.h"
#include "konoha/battle_campaign_equipment_service.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace konoha
{

inline constexpr std::size_t
        battle_campaign_save_slot_size = 4096;
inline constexpr std::size_t
        battle_campaign_save_payload_offset = 12;
inline constexpr std::size_t
        battle_campaign_save_campaign_header_size = 10;
inline constexpr std::size_t
        battle_campaign_save_inventory_size =
                battle_campaign_ninja_tool_quantity_capacity +
                battle_campaign_material_quantity_capacity;
inline constexpr std::size_t
        battle_campaign_save_campaign_prefix_size =
                battle_campaign_save_campaign_header_size +
                battle_campaign_save_inventory_size;
inline constexpr std::size_t
        battle_campaign_save_character_size = 54;
inline constexpr std::size_t
        battle_campaign_save_payload_size =
                battle_campaign_save_campaign_prefix_size +
                battle_campaign_character_capacity *
                        battle_campaign_save_character_size;
inline constexpr std::size_t
        battle_campaign_save_crc_offset =
                battle_campaign_save_slot_size - 4;
inline constexpr std::uint8_t
        battle_campaign_save_version = 2;

static_assert(
        battle_campaign_save_payload_offset +
                        battle_campaign_save_payload_size <=
                battle_campaign_save_crc_offset);

struct battle_campaign_save_slot
{
    std::array<
            std::uint8_t,
            battle_campaign_save_slot_size>
            bytes = {};

    constexpr bool operator==(
            const battle_campaign_save_slot&) const =
                    default;
};

enum class battle_campaign_save_error : std::uint8_t
{
    none,
    bad_magic,
    unsupported_version,
    bad_payload_size,
    bad_crc,
    invalid_state,
};

struct battle_campaign_save_decode_result
{
    battle_campaign_save_error error =
            battle_campaign_save_error::none;
    battle_campaign_state campaign = {};
    std::uint32_t generation = 0;
    int source_slot = -1;
    bool used_default = false;

    [[nodiscard]] constexpr bool valid() const
    {
        return error ==
                battle_campaign_save_error::none;
    }
};

struct battle_campaign_save_target
{
    int slot_index = 0;
    std::uint32_t generation = 1;
};

namespace battle_campaign_save_detail
{

inline void write_u16(
        std::uint8_t* output,
        std::uint16_t value)
{
    output[0] = static_cast<std::uint8_t>(value);
    output[1] =
            static_cast<std::uint8_t>(value >> 8);
}

inline void write_u32(
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

[[nodiscard]] inline std::uint16_t read_u16(
        const std::uint8_t* input)
{
    return static_cast<std::uint16_t>(input[0]) |
            static_cast<std::uint16_t>(
                    static_cast<std::uint16_t>(
                            input[1])
                    << 8);
}

[[nodiscard]] inline std::uint32_t read_u32(
        const std::uint8_t* input)
{
    std::uint32_t result = 0;
    for(int shift = 0; shift < 32; shift += 8)
    {
        result |=
                static_cast<std::uint32_t>(
                        input[shift / 8])
                << shift;
    }
    return result;
}

[[nodiscard]] inline std::uint32_t crc32(
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

[[nodiscard]] constexpr bool valid_action_state(
        std::uint8_t state)
{
    return state <= maximum_action_level ||
            state == locked_action_level;
}

[[nodiscard]] inline bool valid_campaign(
        const battle_campaign_state& campaign)
{
    if(campaign.inventory.ninja_tools[0] != 0 ||
            campaign.inventory.materials[0] != 0)
    {
        return false;
    }
    for(std::size_t index = 0;
            index < campaign.characters.size();
            ++index)
    {
        const battle_campaign_character_record&
                character = campaign.characters[index];
        const character_progression_record& progression =
                character.progression;
        if(progression.character_id != index ||
                progression.level < 1 ||
                progression.level > 50 ||
                progression.experience < 0 ||
                progression.experience >
                        std::numeric_limits<
                                std::uint16_t>::max() ||
                progression.training_points < 0 ||
                progression.training_points >
                        std::numeric_limits<
                                std::uint8_t>::max())
        {
            return false;
        }
        if(progression.active &&
                (index == 0 ||
                 ! unit_definitions[index].active ||
                 ! progression.action_states_initialized))
        {
            return false;
        }
        for(const std::uint8_t state :
                progression.primary_action_levels)
        {
            if(! valid_action_state(state))
            {
                return false;
            }
        }
        for(const std::uint8_t state :
                progression.secondary_action_levels)
        {
            if(! valid_action_state(state))
            {
                return false;
            }
        }
        for(const std::uint8_t tool :
                character.equipped_tools)
        {
            if(tool > 93)
            {
                return false;
            }
        }
    }
    return valid_battle_campaign_equipment(campaign) &&
            project_battle_campaign_party(
                    campaign).success();
}

[[nodiscard]] constexpr std::uint32_t
next_generation(std::uint32_t generation)
{
    return generation ==
                    std::numeric_limits<
                            std::uint32_t>::max() ?
            1 :
            generation + 1;
}

[[nodiscard]] constexpr bool generation_is_newer(
        std::uint32_t candidate,
        std::uint32_t reference)
{
    return candidate != reference &&
            candidate - reference <
                    (std::uint32_t{1} << 31);
}

inline void reset_campaign(
        battle_campaign_state& campaign)
{
    campaign.chapter_id = 0;
    campaign.flags = 0;
    campaign.party.fill(0);
    campaign.inventory.ninja_tools.fill(0);
    campaign.inventory.materials.fill(0);
    for(std::size_t index = 0;
            index < campaign.characters.size();
            ++index)
    {
        campaign.characters[index] = {};
        campaign.characters[index]
                .progression.character_id =
                        static_cast<std::uint8_t>(
                                index);
    }
}

inline void reset_decode_result(
        battle_campaign_save_decode_result& output,
        battle_campaign_save_error error)
{
    output.error = error;
    reset_campaign(output.campaign);
    output.generation = 0;
    output.source_slot = -1;
    output.used_default = false;
}

}

[[nodiscard]] inline battle_campaign_save_error
encode_battle_campaign_slot(
        const battle_campaign_state& campaign,
        std::uint32_t generation,
        battle_campaign_save_slot& output)
{
    using namespace battle_campaign_save_detail;
    if(! valid_campaign(campaign))
    {
        return battle_campaign_save_error::
                invalid_state;
    }

    output.bytes.fill(0);
    output.bytes[0] = 'K';
    output.bytes[1] = 'B';
    output.bytes[2] = 'C';
    output.bytes[3] = 'S';
    output.bytes[4] =
            battle_campaign_save_version;
    write_u16(
            output.bytes.data() + 6,
            static_cast<std::uint16_t>(
                    battle_campaign_save_payload_size));
    write_u32(
            output.bytes.data() + 8,
            generation);

    std::size_t offset =
            battle_campaign_save_payload_offset;
    write_u16(
            output.bytes.data() + offset,
            campaign.chapter_id);
    offset += 2;
    write_u32(
            output.bytes.data() + offset,
            campaign.flags);
    offset += 4;
    for(const std::uint8_t character_id :
            campaign.party)
    {
        output.bytes[offset++] = character_id;
    }
    ++offset;

    for(const std::uint8_t quantity :
            campaign.inventory.ninja_tools)
    {
        output.bytes[offset++] = quantity;
    }
    for(const std::uint8_t quantity :
            campaign.inventory.materials)
    {
        output.bytes[offset++] = quantity;
    }

    for(const battle_campaign_character_record&
            character : campaign.characters)
    {
        const character_progression_record& progression =
                character.progression;
        output.bytes[offset++] =
                progression.active ? 1 : 0;
        output.bytes[offset++] =
                static_cast<std::uint8_t>(
                        progression.level);
        write_u16(
                output.bytes.data() + offset,
                static_cast<std::uint16_t>(
                        progression.experience));
        offset += 2;
        output.bytes[offset++] =
                static_cast<std::uint8_t>(
                        progression.training_points);
        output.bytes[offset++] =
                progression.action_states_initialized ?
                        1 :
                        0;
        for(const std::uint8_t state :
                progression.primary_action_levels)
        {
            output.bytes[offset++] = state;
        }
        for(const std::uint8_t state :
                progression.secondary_action_levels)
        {
            output.bytes[offset++] = state;
        }
        for(const std::uint8_t tool :
                character.equipped_tools)
        {
            output.bytes[offset++] = tool;
        }
    }
    if(offset !=
            battle_campaign_save_payload_offset +
                    battle_campaign_save_payload_size)
    {
        return battle_campaign_save_error::
                invalid_state;
    }
    write_u32(
            output.bytes.data() +
                    battle_campaign_save_crc_offset,
            crc32(
                    output.bytes.data(),
                    battle_campaign_save_crc_offset));
    return battle_campaign_save_error::none;
}

inline void decode_battle_campaign_slot_into(
        const battle_campaign_save_slot& slot,
        battle_campaign_save_decode_result& output)
{
    using namespace battle_campaign_save_detail;
    reset_decode_result(
            output,
            battle_campaign_save_error::none);
    const std::uint8_t* bytes = slot.bytes.data();
    if(bytes[0] != 'K' ||
            bytes[1] != 'B' ||
            bytes[2] != 'C' ||
            bytes[3] != 'S')
    {
        output.error =
                battle_campaign_save_error::bad_magic;
        return;
    }
    if(bytes[4] != battle_campaign_save_version)
    {
        output.error = battle_campaign_save_error::
                unsupported_version;
        return;
    }
    if(bytes[5] != 0 ||
            read_u16(bytes + 6) !=
                    battle_campaign_save_payload_size)
    {
        output.error = battle_campaign_save_error::
                bad_payload_size;
        return;
    }
    if(read_u32(
               bytes +
                       battle_campaign_save_crc_offset) !=
            crc32(
                    bytes,
                    battle_campaign_save_crc_offset))
    {
        output.error =
                battle_campaign_save_error::bad_crc;
        return;
    }

    battle_campaign_state& campaign = output.campaign;
    std::size_t offset =
            battle_campaign_save_payload_offset;
    campaign.chapter_id = read_u16(bytes + offset);
    offset += 2;
    campaign.flags = read_u32(bytes + offset);
    offset += 4;
    for(std::uint8_t& character_id : campaign.party)
    {
        character_id = bytes[offset++];
    }
    if(bytes[offset++] != 0)
    {
        reset_decode_result(
                output,
                battle_campaign_save_error::
                        invalid_state);
        return;
    }

    for(std::uint8_t& quantity :
            campaign.inventory.ninja_tools)
    {
        quantity = bytes[offset++];
    }
    for(std::uint8_t& quantity :
            campaign.inventory.materials)
    {
        quantity = bytes[offset++];
    }

    for(battle_campaign_character_record& character :
            campaign.characters)
    {
        character_progression_record& progression =
                character.progression;
        const std::uint8_t active = bytes[offset++];
        progression.level = bytes[offset++];
        progression.experience =
                read_u16(bytes + offset);
        offset += 2;
        progression.training_points =
                bytes[offset++];
        const std::uint8_t initialized =
                bytes[offset++];
        if(active > 1 || initialized > 1)
        {
            reset_decode_result(
                    output,
                    battle_campaign_save_error::
                            invalid_state);
            return;
        }
        progression.active = active != 0;
        progression.action_states_initialized =
                initialized != 0;
        for(std::uint8_t& state :
                progression.primary_action_levels)
        {
            state = bytes[offset++];
        }
        for(std::uint8_t& state :
                progression.secondary_action_levels)
        {
            state = bytes[offset++];
        }
        for(std::uint8_t& tool :
                character.equipped_tools)
        {
            tool = bytes[offset++];
        }
    }
    if(offset !=
            battle_campaign_save_payload_offset +
                    battle_campaign_save_payload_size)
    {
        reset_decode_result(
                output,
                battle_campaign_save_error::
                        invalid_state);
        return;
    }
    while(offset < battle_campaign_save_crc_offset)
    {
        if(bytes[offset++] != 0)
        {
            reset_decode_result(
                    output,
                    battle_campaign_save_error::
                            invalid_state);
            return;
        }
    }
    if(! valid_campaign(campaign))
    {
        reset_decode_result(
                output,
                battle_campaign_save_error::
                        invalid_state);
        return;
    }
    output.generation = read_u32(bytes + 8);
}

[[nodiscard]] inline battle_campaign_save_decode_result
decode_battle_campaign_slot(
        const battle_campaign_save_slot& slot)
{
    battle_campaign_save_decode_result result;
    decode_battle_campaign_slot_into(slot, result);
    return result;
}

[[nodiscard]] inline
const battle_campaign_save_decode_result&
load_latest_battle_campaign_slot_into(
        const battle_campaign_save_slot& slot_a,
        const battle_campaign_save_slot& slot_b,
        const battle_campaign_state& default_campaign,
        battle_campaign_save_decode_result& decoded_a,
        battle_campaign_save_decode_result& decoded_b)
{
    decode_battle_campaign_slot_into(
            slot_a, decoded_a);
    decode_battle_campaign_slot_into(
            slot_b, decoded_b);
    if(decoded_a.valid() && decoded_b.valid())
    {
        if(decoded_b.generation ==
                        decoded_a.generation ||
                battle_campaign_save_detail::
                        generation_is_newer(
                                decoded_b.generation,
                                decoded_a.generation))
        {
            decoded_b.source_slot = 1;
            return decoded_b;
        }
        decoded_a.source_slot = 0;
        return decoded_a;
    }
    if(decoded_a.valid())
    {
        decoded_a.source_slot = 0;
        return decoded_a;
    }
    if(decoded_b.valid())
    {
        decoded_b.source_slot = 1;
        return decoded_b;
    }
    if(! battle_campaign_save_detail::valid_campaign(
               default_campaign))
    {
        battle_campaign_save_detail::
                reset_decode_result(
                        decoded_a,
                        battle_campaign_save_error::
                                invalid_state);
        return decoded_a;
    }
    battle_campaign_save_detail::reset_decode_result(
            decoded_a,
            battle_campaign_save_error::none);
    decoded_a.campaign = default_campaign;
    decoded_a.used_default = true;
    return decoded_a;
}

[[nodiscard]] inline battle_campaign_save_decode_result
load_latest_battle_campaign_slot(
        const battle_campaign_save_slot& slot_a,
        const battle_campaign_save_slot& slot_b,
        const battle_campaign_state& default_campaign)
{
    battle_campaign_save_decode_result decoded_a =
            {};
    battle_campaign_save_decode_result decoded_b =
            {};
    return load_latest_battle_campaign_slot_into(
            slot_a,
            slot_b,
            default_campaign,
            decoded_a,
            decoded_b);
}

[[nodiscard]] inline battle_campaign_save_target
next_battle_campaign_save_target_into(
        const battle_campaign_save_slot& slot_a,
        const battle_campaign_save_slot& slot_b,
        battle_campaign_save_decode_result& decoded_a,
        battle_campaign_save_decode_result& decoded_b)
{
    decode_battle_campaign_slot_into(
            slot_a, decoded_a);
    decode_battle_campaign_slot_into(
            slot_b, decoded_b);
    if(decoded_a.valid() && decoded_b.valid())
    {
        if(decoded_b.generation ==
                        decoded_a.generation ||
                battle_campaign_save_detail::
                        generation_is_newer(
                                decoded_b.generation,
                                decoded_a.generation))
        {
            return {
                0,
                battle_campaign_save_detail::
                        next_generation(
                                decoded_b.generation),
            };
        }
        return {
            1,
            battle_campaign_save_detail::
                    next_generation(
                            decoded_a.generation),
        };
    }
    if(decoded_a.valid())
    {
        return {
            1,
            battle_campaign_save_detail::
                    next_generation(
                            decoded_a.generation),
        };
    }
    if(decoded_b.valid())
    {
        return {
            0,
            battle_campaign_save_detail::
                    next_generation(
                            decoded_b.generation),
        };
    }
    return {};
}

[[nodiscard]] inline battle_campaign_save_target
next_battle_campaign_save_target(
        const battle_campaign_save_slot& slot_a,
        const battle_campaign_save_slot& slot_b)
{
    battle_campaign_save_decode_result decoded_a;
    battle_campaign_save_decode_result decoded_b;
    return next_battle_campaign_save_target_into(
            slot_a,
            slot_b,
            decoded_a,
            decoded_b);
}

}

#endif
