#ifndef KONOHA_BATTLE_EFFECT_SEQUENCE_H
#define KONOHA_BATTLE_EFFECT_SEQUENCE_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr std::size_t battle_effect_maximum_components = 16;
inline constexpr std::size_t battle_effect_maximum_frames = 96;

struct battle_effect_asset
{
    std::uint16_t tile_offset = 0;
    std::uint8_t width = 0;
    std::uint8_t height = 0;
};

struct battle_effect_component
{
    std::int16_t x = 0;
    std::int16_t y = 0;
    std::uint8_t asset_index = 0;
    bool horizontal_flip = false;
    bool vertical_flip = false;
    std::uint8_t priority = 0;
    bool semi_transparent = false;
};

struct battle_effect_frame
{
    std::array<
            battle_effect_component,
            battle_effect_maximum_components> components = {};
    std::uint8_t component_count = 0;
    std::uint8_t duration = 0;
};

struct battle_effect_sequence
{
    std::array<
            battle_effect_frame,
            battle_effect_maximum_frames> frames = {};
    std::uint8_t frame_count = 0;

    [[nodiscard]] constexpr const battle_effect_frame* frame_at(
            int frame) const
    {
        if(frame < 0)
        {
            return nullptr;
        }
        for(std::size_t index = 0;
                index < frame_count;
                ++index)
        {
            const battle_effect_frame& candidate =
                    frames[index];
            if(frame < candidate.duration)
            {
                return &candidate;
            }
            frame -= candidate.duration;
        }
        return nullptr;
    }

    [[nodiscard]] constexpr int total_duration() const
    {
        int result = 0;
        for(std::size_t index = 0;
                index < frame_count;
                ++index)
        {
            result += frames[index].duration;
        }
        return result;
    }
};

}

#endif
