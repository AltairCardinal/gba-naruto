#include "konoha/battle_unit_visual_animation.h"

#include <cassert>

using namespace konoha;

int main()
{
    {
        const battle_unit_combat_visual cast =
                battle_unit_visual_animation::combat(
                        battle_unit_combat_motion::cast,
                        false,
                        true);
        assert(cast.slot == 1);
        assert(! cast.horizontal_flip);
    }
    {
        const battle_unit_combat_visual melee =
                battle_unit_visual_animation::combat(
                        battle_unit_combat_motion::melee,
                        true,
                        true);
        assert(melee.slot == 7);
        assert(! melee.horizontal_flip);
    }
    {
        const battle_unit_combat_visual mirrored =
                battle_unit_visual_animation::combat(
                        battle_unit_combat_motion::melee,
                        true,
                        false);
        assert(mirrored.slot == 3);
        assert(mirrored.horizontal_flip);
    }
    assert(battle_unit_visual_animation::motion_for(
                   false, 1, true) ==
            battle_unit_combat_motion::melee);
    assert(battle_unit_visual_animation::motion_for(
                   false, 5, true) ==
            battle_unit_combat_motion::cast);
    assert(battle_unit_visual_animation::motion_for(
                   false, 1, false) ==
            battle_unit_combat_motion::cast);
    assert(battle_unit_visual_animation::motion_for(
                   true, 1, true) ==
            battle_unit_combat_motion::throw_projectile);

    assert(battle_unit_visual_animation::facing_toward(
                   { 2, 2 }, { 5, 3 }, battle_facing::up) ==
            battle_facing::right);
    assert(battle_unit_visual_animation::facing_toward(
                   { 5, 2 }, { 2, 3 }, battle_facing::up) ==
            battle_facing::left);
    assert(battle_unit_visual_animation::facing_toward(
                   { 2, 5 }, { 3, 1 }, battle_facing::right) ==
            battle_facing::up);
    assert(battle_unit_visual_animation::facing_toward(
                   { 2, 1 }, { 3, 5 }, battle_facing::left) ==
            battle_facing::down);
    assert(battle_unit_visual_animation::facing_toward(
                   { 2, 2 }, { 2, 2 }, battle_facing::left) ==
            battle_facing::left);

    assert(battle_unit_visual_animation::idle_sequence(
                   battle_facing::down) == 0);
    assert(battle_unit_visual_animation::idle_sequence(
                   battle_facing::up) == 1);
    assert(battle_unit_visual_animation::idle_sequence(
                   battle_facing::right) == 2);
    assert(battle_unit_visual_animation::idle_sequence(
                   battle_facing::left) == 3);
    assert(battle_unit_visual_animation::departure_sequence(
                   battle_facing::right) == 6);
    assert(battle_unit_visual_animation::arrival_sequence(
                   battle_facing::right) == 10);
    assert(
            battle_unit_visual_animation::
                    idle_phase_offset(1) == 0);
    assert(
            battle_unit_visual_animation::
                    idle_phase_offset(2) == 16);
    assert(
            battle_unit_visual_animation::
                    idle_phase_offset(3) == 0);
    assert(
            battle_unit_visual_animation::
                    idle_phase_offset(4) == 16);

    constexpr battle_unit_visual_timeline_step steps[] = {
        { 0, 2 },
        { 3, 4 },
        { 4, 8 },
    };
    assert(battle_unit_visual_animation::frame_at(
                   steps, 3, 0, false) == 0);
    assert(battle_unit_visual_animation::frame_at(
                   steps, 3, 1, false) == 0);
    assert(battle_unit_visual_animation::frame_at(
                   steps, 3, 2, false) == 3);
    assert(battle_unit_visual_animation::frame_at(
                   steps, 3, 5, false) == 3);
    assert(battle_unit_visual_animation::frame_at(
                   steps, 3, 6, false) == 4);
    assert(battle_unit_visual_animation::frame_at(
                   steps, 3, 99, false) == 4);
    assert(battle_unit_visual_animation::frame_at(
                   steps, 3, 14, true) == 0);

    return 0;
}
