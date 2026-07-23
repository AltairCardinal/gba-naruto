#include "konoha_bench/battle_effects.h"

#include <array>
#include <cassert>

using namespace konoha_bench;

int main()
{
    unit_state source{ 40, 40, 10, 1, 1, 0, true };
    unit_state target{ 30, 40, 4, 5, 5, 0, true };
    const std::array chain = {
        effect{ effect_kind::spend_chakra, 3, 0 },
        effect{ effect_kind::damage, 12, 0 },
        effect{ effect_kind::add_status, 4, 0 },
        effect{ effect_kind::move, 1, -1 },
    };
    const effect_chain_result applied = apply_effect_chain(source, target, chain);
    assert(applied.success());
    assert(applied.applied_count == 4);
    assert(source.chakra == 7);
    assert(target.hp == 18);
    assert(target.status_mask == 4);
    assert(target.x == 6 && target.y == 4);

    const std::array healing = { effect{ effect_kind::heal, 99, 0 } };
    assert(apply_effect_chain(source, target, healing).success());
    assert(target.hp == target.max_hp);

    const std::array lethal = { effect{ effect_kind::damage, 999, 0 } };
    assert(apply_effect_chain(source, target, lethal).success());
    assert(target.hp == 0);

    unit_state rollback_source{ 20, 20, 2, 0, 0, 0, true };
    unit_state rollback_target{ 15, 15, 0, 2, 2, 0, true };
    const unit_state original_source = rollback_source;
    const unit_state original_target = rollback_target;
    const std::array rollback_chain = {
        effect{ effect_kind::damage, 5, 0 },
        effect{ effect_kind::spend_chakra, 3, 0 },
    };
    const effect_chain_result rejected =
            apply_effect_chain(rollback_source, rollback_target, rollback_chain);
    assert(rejected.error == effect_error::insufficient_chakra);
    assert(rejected.applied_count == 0);
    assert(rollback_source == original_source);
    assert(rollback_target == original_target);

    rollback_target.active = false;
    assert(apply_effect_chain(rollback_source, rollback_target, lethal).error ==
           effect_error::invalid_target);

    rollback_target.active = true;
    const std::array invalid = { effect{ effect_kind::damage, -1, 0 } };
    assert(apply_effect_chain(rollback_source, rollback_target, invalid).error ==
           effect_error::invalid_effect);

    const std::array unknown = {
        effect{ static_cast<effect_kind>(255), 0, 0 }
    };
    assert(apply_effect_chain(rollback_source, rollback_target, unknown).error ==
           effect_error::invalid_effect);
}
