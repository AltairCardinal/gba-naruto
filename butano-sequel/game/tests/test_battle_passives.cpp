#include "konoha/generated_battle_passive_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    static_assert(passive_definitions.size() == 45);
    static_assert(battle_passive_state::capacity == 24);
    static_assert(sizeof(battle_passive_state) == 48);
    assert(passive_definitions[9] ==
           (passive_definition{ 9, 0x0C, 0, 10, 0, 5, 0, 0 }));
    assert(passive_definitions[20] ==
           (passive_definition{ 20, 0x19, 0, 20, 0, 5, 0, 0 }));
    assert(passive_definitions[35].base_b == 10);
    assert(passive_definitions[35].per_level_b == 5);

    battle_passive_state state;
    assert(state.set_slot(0, 9, 0));
    assert(state.set_slot(1, 9, unlearned_passive_level));
    assert(state.set_slot(2, 20, 3));
    assert(state.set_slot(3, 9, 17));
    assert(state.set_slot(4, 9, 2));
    assert(! state.set_slot(24, 9, 1));

    const passive_query_result critical =
            state.query(0x0C, passive_definitions);
    assert(critical.found);
    assert(critical.slot_index == 3);
    assert(critical.id == 9);
    assert(critical.stored_level == 17);
    assert(critical.value_a == 90);
    assert(critical.value_b == 0);
    const passive_query_result ignore_defense =
            state.query(0x19, passive_definitions);
    assert(ignore_defense.found);
    assert(ignore_defense.slot_index == 2);
    assert(ignore_defense.value_a == 30);
    assert(! state.query(0x7F, passive_definitions).found);

    const battle_unit_instance sakura = instantiate_unit(
            unit_definitions[3],
            3,
            battle_side::player,
            battle_control::player,
            { 2, 2 },
            battle_facing::down);
    assert(sakura.passives.slot(21) == (passive_slot_state{ 26, 1 }));

    const battle_unit_instance template_62 = instantiate_unit(
            unit_definitions[62],
            62,
            battle_side::enemy,
            battle_control::ai,
            { 3, 2 },
            battle_facing::up);
    assert(template_62.passives.slot(0) == (passive_slot_state{ 2, 3 }));
    assert(template_62.passives.slot(11) == (passive_slot_state{ 20, 3 }));
    assert(template_62.passives.query(0x19, passive_definitions).value_a == 30);

    const battle_unit_instance naruto = instantiate_unit(
            unit_definitions[1],
            1,
            battle_side::player,
            battle_control::player,
            { 1, 1 },
            battle_facing::down);
    assert(naruto.passives.slot(0) ==
           (passive_slot_state{ 1, unlearned_passive_level }));
    assert(! naruto.passives.query(0x01, passive_definitions).found);

    const battle_unit_instance scenario_enemy = instantiate_unit(
            unit_definitions[30],
            30,
            battle_side::enemy,
            battle_control::ai,
            { 4, 4 },
            battle_facing::up);
    assert(scenario_enemy.passives.slot(0) ==
           (passive_slot_state{ 1, 0 }));
    assert(! scenario_enemy.passives.query(0x01, passive_definitions).found);
}
