#include "konoha/battle_presentation_projection.h"

#include <cassert>

using namespace konoha;

int main()
{
    // The focused cell is centered vertically unless the map boundary
    // makes that impossible. HUD layout must not bias it downward.
    assert(battle_camera_focus_y(
                   { 4, 10 },
                   22 * 16,
                   160) ==
           10 * 16 + 8 - 256);
    // The lower Sasuke positions used by the multi-unit battlefield still
    // target the physical screen center; the bottom HUD does not subtract
    // another 32 pixels and push the unit behind itself.
    assert(battle_camera_focus_y(
                   { 9, 15 },
                   32 * 16,
                   160) ==
           15 * 16 + 8 - 256);

    // The original duel stage is faction-stable: the player is always on
    // the left facing right and the enemy is always on the right facing
    // left. Enemy-initiated combat changes the attacker, not the sides.
    assert(battle_duel_screen_x(battle_side::player) == -56);
    assert(battle_duel_screen_x(battle_side::enemy) == 56);
    assert(battle_duel_facing(battle_side::player) ==
           battle_facing::right);
    assert(battle_duel_facing(battle_side::enemy) ==
           battle_facing::left);

    assert(battle_facing_indicator_angle(
                   battle_facing::up) == 0);
    assert(battle_facing_indicator_angle(
                   battle_facing::right) == 270);
    assert(battle_facing_indicator_angle(
                   battle_facing::down) == 180);
    assert(battle_facing_indicator_angle(
                   battle_facing::left) == 90);
    assert(battle_facing_indicator_graphics_index(
                   battle_facing::up, 11) == 0);
    assert(battle_facing_indicator_graphics_index(
                   battle_facing::right, 11) == 3);
    assert(battle_facing_indicator_graphics_index(
                   battle_facing::down, 11) == 6);
    assert(battle_facing_indicator_graphics_index(
                   battle_facing::left, 11) == 9);
    assert(battle_facing_indicator_pulse_phase(0) == 1);
    assert(battle_facing_indicator_pulse_phase(3) == 1);
    assert(battle_facing_indicator_pulse_phase(4) == 2);
    assert(battle_facing_indicator_pulse_phase(10) == 2);
    assert(battle_facing_indicator_pulse_phase(11) == 0);
    assert(battle_facing_indicator_pulse_phase(15) == 0);
    assert(battle_facing_indicator_pulse_phase(16) == 1);
    assert(battle_facing_indicator_graphics_index(
                   battle_facing::up, 11) == 0);
    assert(battle_facing_indicator_graphics_index(
                   battle_facing::right, 0) == 4);
    assert(battle_facing_indicator_graphics_index(
                   battle_facing::down, 4) == 8);
    assert(battle_facing_indicator_graphics_index(
                   battle_facing::left, 11) == 9);
}
