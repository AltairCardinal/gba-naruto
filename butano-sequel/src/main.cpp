#include "bn_core.h"
#include "bn_assert.h"

#include "konoha/scenario_41_scene.h"
#include "konoha_bench/self_test.h"

int main()
{
    bn::core::init();

    const konoha_bench::self_test_result self_tests = konoha_bench::run_self_tests();
    BN_ASSERT(self_tests.all_passed(), "Embedded foundation self-tests failed");
    konoha::run_scenario_41_scene();
}
