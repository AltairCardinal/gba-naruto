#ifndef KONOHA_BATTLE_RANDOM_H
#define KONOHA_BATTLE_RANDOM_H

#include <cstdint>

namespace konoha
{

class deterministic_rng
{
public:
    explicit constexpr deterministic_rng(std::uint32_t seed) :
        _state(seed ? seed : 1)
    {
    }

    [[nodiscard]] int next_percent()
    {
        _state = _state * 1664525U + 1013904223U;
        return static_cast<int>((_state >> 16U) % 100U);
    }

    [[nodiscard]] int next_u15()
    {
        _state = _state * 1664525U + 1013904223U;
        return static_cast<int>((_state >> 17U) & 0x7FFFU);
    }

private:
    std::uint32_t _state;
};

}

#endif
