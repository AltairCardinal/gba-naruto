#ifndef KONOHA_BATTLE_BACKGROUND_STREAM_H
#define KONOHA_BATTLE_BACKGROUND_STREAM_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr int battle_background_chunk_width = 512;
inline constexpr std::size_t
        battle_background_max_chunks = 4;

enum class battle_background_stream_error :
        std::uint8_t
{
    none,
    invalid_map_width,
    invalid_viewport,
    invalid_chunk_count,
    invalid_origin,
    viewport_gap,
    map_not_covered,
};

struct battle_background_stream_result
{
    battle_background_stream_error error =
            battle_background_stream_error::none;

    [[nodiscard]] constexpr bool success() const
    {
        return error ==
                battle_background_stream_error::none;
    }
};

struct battle_background_stream_update
{
    std::size_t chunk_index = 0;
    bool changed = false;
};

class battle_background_stream
{
public:
    [[nodiscard]] battle_background_stream_result
    prepare(
            int map_width,
            int viewport_width,
            const std::array<
                    int,
                    battle_background_max_chunks>&
                    origins,
            std::size_t chunk_count)
    {
        if(map_width <= 0)
        {
            return {
                battle_background_stream_error::
                        invalid_map_width,
            };
        }
        if(viewport_width <= 0 ||
                viewport_width >
                        battle_background_chunk_width)
        {
            return {
                battle_background_stream_error::
                        invalid_viewport,
            };
        }
        if(chunk_count == 0 ||
                chunk_count > origins.size())
        {
            return {
                battle_background_stream_error::
                        invalid_chunk_count,
            };
        }
        if(origins[0] != 0)
        {
            return {
                battle_background_stream_error::
                        invalid_origin,
            };
        }
        const int maximum_step =
                battle_background_chunk_width -
                viewport_width;
        for(std::size_t index = 1;
                index < chunk_count;
                ++index)
        {
            if(origins[index] <=
                       origins[index - 1] ||
                    origins[index] >= map_width)
            {
                return {
                    battle_background_stream_error::
                            invalid_origin,
                };
            }
            if(origins[index] -
                            origins[index - 1] >
                    maximum_step)
            {
                return {
                    battle_background_stream_error::
                            viewport_gap,
                };
            }
        }
        if(origins[chunk_count - 1] +
                        battle_background_chunk_width <
                map_width)
        {
            return {
                battle_background_stream_error::
                        map_not_covered,
            };
        }

        _map_width = map_width;
        _viewport_width = viewport_width;
        _origins = origins;
        _chunk_count = chunk_count;
        _chunk_index = 0;
        return {};
    }

    [[nodiscard]] std::size_t chunk_count() const
    {
        return _chunk_count;
    }

    [[nodiscard]] std::size_t chunk_index() const
    {
        return _chunk_index;
    }

    [[nodiscard]] int chunk_origin() const
    {
        return _origins[_chunk_index];
    }

    [[nodiscard]] battle_background_stream_update
    update(int camera_center)
    {
        const std::size_t before = _chunk_index;
        const int half_viewport = _viewport_width / 2;
        if(camera_center < half_viewport)
        {
            camera_center = half_viewport;
        }
        const int maximum_center =
                _map_width - half_viewport;
        if(camera_center > maximum_center)
        {
            camera_center = maximum_center;
        }

        while(_chunk_index + 1 < _chunk_count &&
                camera_center + half_viewport >
                        _origins[_chunk_index] +
                                battle_background_chunk_width)
        {
            ++_chunk_index;
        }
        while(_chunk_index > 0 &&
                camera_center - half_viewport <
                        _origins[_chunk_index])
        {
            --_chunk_index;
        }
        return {
            _chunk_index,
            _chunk_index != before,
        };
    }

private:
    int _map_width = battle_background_chunk_width;
    int _viewport_width = 240;
    std::array<
            int,
            battle_background_max_chunks> _origins = {};
    std::size_t _chunk_count = 1;
    std::size_t _chunk_index = 0;
};

}

#endif
