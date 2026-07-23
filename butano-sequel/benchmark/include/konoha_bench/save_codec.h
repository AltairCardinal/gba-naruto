#ifndef KONOHA_BENCH_SAVE_CODEC_H
#define KONOHA_BENCH_SAVE_CODEC_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha_bench
{

constexpr std::size_t save_slot_size = 32;
constexpr std::uint8_t save_version = 1;

struct save_payload
{
    std::uint16_t chapter;
    std::uint32_t experience;
    std::uint16_t training_points;
    std::uint32_t flags;

    constexpr bool operator==(const save_payload&) const = default;
};

struct save_slot
{
    std::array<std::uint8_t, save_slot_size> bytes = {};

    constexpr bool operator==(const save_slot&) const = default;
};

enum class save_error
{
    none,
    wrong_size,
    bad_magic,
    unsupported_version,
    bad_payload_size,
    bad_crc,
};

struct decode_result
{
    save_error error;
    save_payload payload;
    std::uint32_t generation;
    bool used_default;

    [[nodiscard]] constexpr bool valid() const
    {
        return error == save_error::none;
    }
};

[[nodiscard]] constexpr save_payload default_save()
{
    return { 0, 0, 0, 0 };
}

inline void write_u16(std::uint8_t* output, std::uint16_t value)
{
    output[0] = static_cast<std::uint8_t>(value);
    output[1] = static_cast<std::uint8_t>(value >> 8);
}

inline void write_u32(std::uint8_t* output, std::uint32_t value)
{
    for(int shift = 0; shift < 32; shift += 8)
    {
        output[shift / 8] = static_cast<std::uint8_t>(value >> shift);
    }
}

[[nodiscard]] inline std::uint16_t read_u16(const std::uint8_t* input)
{
    return static_cast<std::uint16_t>(input[0]) |
           static_cast<std::uint16_t>(input[1] << 8);
}

[[nodiscard]] inline std::uint32_t read_u32(const std::uint8_t* input)
{
    std::uint32_t value = 0;
    for(int shift = 0; shift < 32; shift += 8)
    {
        value |= static_cast<std::uint32_t>(input[shift / 8]) << shift;
    }
    return value;
}

[[nodiscard]] inline std::uint32_t crc32(const std::uint8_t* data, std::size_t size)
{
    std::uint32_t crc = 0xFFFFFFFF;
    for(std::size_t index = 0; index < size; ++index)
    {
        crc ^= data[index];
        for(int bit = 0; bit < 8; ++bit)
        {
            const std::uint32_t mask = 0U - (crc & 1U);
            crc = (crc >> 1) ^ (0xEDB88320U & mask);
        }
    }
    return ~crc;
}

[[nodiscard]] inline save_slot encode_slot(
        const save_payload& payload, std::uint32_t generation)
{
    save_slot slot;
    slot.bytes[0] = 'K';
    slot.bytes[1] = 'N';
    slot.bytes[2] = 'S';
    slot.bytes[3] = 'V';
    slot.bytes[4] = save_version;
    write_u16(slot.bytes.data() + 6, 12);
    write_u32(slot.bytes.data() + 8, generation);
    write_u16(slot.bytes.data() + 12, payload.chapter);
    write_u32(slot.bytes.data() + 14, payload.experience);
    write_u16(slot.bytes.data() + 18, payload.training_points);
    write_u32(slot.bytes.data() + 20, payload.flags);
    write_u32(slot.bytes.data() + 28, crc32(slot.bytes.data(), 28));
    return slot;
}

[[nodiscard]] inline decode_result decode_slot(
        const std::uint8_t* data, std::size_t size)
{
    const decode_result invalid = {
        save_error::wrong_size, default_save(), 0, false
    };
    if(size != save_slot_size)
    {
        return invalid;
    }
    if(data[0] != 'K' || data[1] != 'N' || data[2] != 'S' || data[3] != 'V')
    {
        return { save_error::bad_magic, default_save(), 0, false };
    }
    if(data[4] != save_version)
    {
        return { save_error::unsupported_version, default_save(), 0, false };
    }
    if(read_u16(data + 6) != 12)
    {
        return { save_error::bad_payload_size, default_save(), 0, false };
    }
    if(read_u32(data + 28) != crc32(data, 28))
    {
        return { save_error::bad_crc, default_save(), 0, false };
    }
    return {
        save_error::none,
        {
            read_u16(data + 12),
            read_u32(data + 14),
            read_u16(data + 18),
            read_u32(data + 20),
        },
        read_u32(data + 8),
        false,
    };
}

[[nodiscard]] inline decode_result decode_slot(const save_slot& slot)
{
    return decode_slot(slot.bytes.data(), slot.bytes.size());
}

[[nodiscard]] inline decode_result load_newest(
        const save_slot& slot_a, const save_slot& slot_b)
{
    const decode_result decoded_a = decode_slot(slot_a);
    const decode_result decoded_b = decode_slot(slot_b);
    if(decoded_a.valid() && decoded_b.valid())
    {
        return decoded_b.generation >= decoded_a.generation ? decoded_b : decoded_a;
    }
    if(decoded_a.valid())
    {
        return decoded_a;
    }
    if(decoded_b.valid())
    {
        return decoded_b;
    }
    return { save_error::none, default_save(), 0, true };
}

}

#endif
