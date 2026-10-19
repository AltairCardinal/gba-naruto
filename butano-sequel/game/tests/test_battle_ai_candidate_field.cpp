#include "konoha/battle_ai_candidate_field.h"
#include "konoha/generated_battle_unit_content.h"

#include <array>
#include <cassert>

using namespace konoha;

int main()
{
    grid_map<9, 22> map;
    std::array units = {
        instantiate_unit(
                unit_definitions[1],
                1,
                battle_side::player,
                battle_control::player,
                { 4, 10 },
                battle_facing::up),
        instantiate_unit(
                unit_definitions[30],
                2,
                battle_side::enemy,
                battle_control::ai,
                { 6, 4 },
                battle_facing::down),
    };
    for(const battle_unit_instance& unit : units)
    {
        assert(map.set_occupied(unit.position, unit.active));
    }

    ai_candidate_field<9, 22> field;
    reachable_cost_result<9, 22> reachable;
    assert(battle_ai_candidate_field_builder::build(
            map,
            units[1],
            units,
            field,
            reachable));

    // Original scenario-41 runtime capture at 0x08085590:
    // Naruto at (4,10), movement 3, hostile range 1.
    assert(field.flags({ 4, 6 }) == 0x11);
    assert(field.flags({ 1, 10 }) == 0x81);
    assert(field.flags({ 4, 10 }) == 0xF1);
    assert(field.flags({ 7, 10 }) == 0x21);
    assert(field.flags({ 4, 14 }) == 0x41);
    assert(field.flags({ 4, 5 }) == 0);

    // The candidate field is a derived AI workspace, not grid_map::flags.
    assert(map.flags({ 4, 10 }) == 0);
}
