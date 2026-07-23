#include "konoha/battle_effects.h"
#include "konoha/grid_pathfinder.h"

#include <array>
#include <cassert>

int main()
{
    konoha::grid_map<3, 3> map;
    const auto path = konoha::find_path<3, 3, 8>(map, { 0, 0 }, { 2, 0 }, 2);
    assert(path.found && path.total_cost == 2);
    const auto costs = konoha::compute_reachable_costs(map, konoha::grid_point{ 0, 0 }, 2);
    assert(costs.valid);
    assert(costs.cost({ 2, 0 }) == 2);
    assert(costs.cost({ 2, 2 }) == -1);

    konoha::unit_state source{ 20, 20, 4, 0, 0, 0, true };
    konoha::unit_state target{ 10, 10, 0, 1, 0, 0, true };
    const std::array effects = {
        konoha::effect{ konoha::effect_kind::damage, 10, 0 }
    };
    assert(konoha::apply_effect_chain(source, target, effects).success());
    assert(target.hp == 0);

    konoha::unit_state captor{ 20, 20, 4, 0, 0, 0, true };
    konoha::unit_state captured{ 10, 10, 0, 1, 0, 0, true };
    const std::array capture = {
        konoha::effect{ konoha::effect_kind::spend_chakra, 2, 0 },
        konoha::effect{ konoha::effect_kind::capture, 0, 0 },
    };
    assert(konoha::apply_effect_chain(captor, captured, capture).success());
    assert(captor.chakra == 2);
    assert(captured.captured && ! captured.active);

    konoha::unit_state guarded{ 10, 10, 0, 1, 0, 0, true };
    guarded.substitution_ready = true;
    const std::array guarded_hit = {
        konoha::effect{ konoha::effect_kind::damage, 6, 0 },
    };
    assert(konoha::apply_effect_chain(captor, guarded, guarded_hit).success());
    assert(guarded.hp == 10);
    assert(! guarded.substitution_ready);
}
