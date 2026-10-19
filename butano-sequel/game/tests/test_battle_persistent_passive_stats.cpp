#include "konoha/battle_progression.h"
#include "konoha/generated_battle_passive_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_passive_state passives;
    assert(passives.set_slot(0, 29, 1));  // target 2: max HP +10%
    assert(passives.set_slot(1, 37, 1));  // target 6: defense +10%
    assert(passives.set_slot(2, 42, 1));  // target 8: agility +10%
    assert(passives.set_slot(3, 8, 1));   // target 11: hand seals -10%
    assert(passives.set_slot(4, 1, 1));   // target 1: max HP +30
    assert(passives.set_slot(5, 2, 1));   // target 3: chakra +1
    assert(passives.set_slot(6, 3, 1));   // target 4: attack +3
    assert(passives.set_slot(7, 4, 1));   // target 5: defense +5
    assert(passives.set_slot(8, 5, 1));   // target 7: agility +4
    assert(passives.set_slot(9, 6, 1));   // target 9: movement +1
    assert(passives.set_slot(10, 7, 1));  // target 10: tool capacity +1

    const character_stat_values base = {
        100,
        8,
        90,
        80,
        80,
        8,
        8,
    };
    const persistent_passive_stat_result modified =
            apply_persistent_passive_stats(
                    base,
                    20,
                    passives,
                    passive_definitions);
    assert(modified.stats.max_hp == 140);
    assert(modified.stats.chakra_capacity == 9);
    assert(modified.stats.attack == 93);
    assert(modified.stats.defense == 93);
    assert(modified.stats.agility == 92);
    assert(modified.stats.movement == 9);
    assert(modified.stats.ninja_tool_capacity == 9);
    assert(modified.hand_seals == 18);

    battle_passive_state ordered;
    assert(ordered.set_slot(0, 29, 1));
    assert(ordered.set_slot(1, 1, 1));
    const persistent_passive_stat_result percentage_before_flat =
            apply_persistent_passive_stats(
                    {
                        100,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                    },
                    1,
                    ordered,
                    passive_definitions);
    assert(percentage_before_flat.stats.max_hp == 140);

    battle_passive_state capped;
    assert(capped.set_slot(0, 29, 3));
    assert(capped.set_slot(1, 1, 3));
    assert(capped.set_slot(2, 8, 3));
    assert(capped.set_slot(3, 7, 3));
    const persistent_passive_stat_result limits =
            apply_persistent_passive_stats(
                    {
                        980,
                        9,
                        99,
                        99,
                        99,
                        9,
                        9,
                    },
                    1,
                    capped,
                    passive_definitions);
    assert(limits.stats.max_hp == 999);
    assert(limits.stats.chakra_capacity == 9);
    assert(limits.stats.attack == 99);
    assert(limits.stats.defense == 99);
    assert(limits.stats.agility == 99);
    assert(limits.stats.movement == 9);
    assert(limits.stats.ninja_tool_capacity == 12);
    assert(limits.hand_seals == 1);
}
