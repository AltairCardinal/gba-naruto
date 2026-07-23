#ifndef KONOHA_BENCH_SELF_TEST_H
#define KONOHA_BENCH_SELF_TEST_H

#include <cstdint>

namespace konoha_bench
{

struct self_test_result
{
    std::uint8_t pass_mask;

    [[nodiscard]] constexpr bool passed(int index) const
    {
        return (pass_mask & (1U << index)) != 0;
    }

    [[nodiscard]] constexpr bool all_passed() const
    {
        return pass_mask == 0x1F;
    }
};

[[gnu::noinline]] self_test_result run_self_tests();

}

#endif
