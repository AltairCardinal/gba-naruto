#include "konoha/generated_battle_action_05_effect_content.h"
#include "konoha/generated_battle_action_05_dust_effect_content.h"
#include "konoha/generated_battle_action_16_fire_effect_content.h"
#include "konoha/generated_battle_ninja_tool_bomb_projectile_content.h"
#include "konoha/generated_battle_ninja_tool_bomb_smoke_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    static_assert(battle_effect_maximum_components == 16);
    static_assert(battle_effect_maximum_frames == 96);
    static_assert(battle_action_05_hit_assets.size() == 14);
    static_assert(battle_action_05_hit_sequence.frame_count == 11);
    static_assert(battle_action_05_hit_sequence.total_duration() == 16);
    static_assert(battle_action_05_dust_assets.size() == 8);
    static_assert(battle_action_05_dust_sequence.frame_count == 26);
    static_assert(battle_action_05_dust_sequence.total_duration() == 59);
    static_assert(battle_action_16_fire_hit_assets.size() == 10);
    static_assert(battle_action_16_fire_hit_sequence.frame_count == 12);
    static_assert(
            battle_action_16_fire_hit_sequence.total_duration() == 30);
    static_assert(
            battle_action_16_fire_hit_sequence.frames[0]
                    .component_count == 1);
    static_assert(
            battle_action_16_fire_hit_sequence.frames[7]
                    .component_count == 4);
    static_assert(
            battle_ninja_tool_bomb_projectile_assets.size() == 4);
    static_assert(
            battle_ninja_tool_bomb_projectile_sequence.frame_count == 4);
    static_assert(
            battle_ninja_tool_bomb_projectile_sequence
                    .total_duration() == 7);
    static_assert(
            battle_ninja_tool_bomb_smoke_assets.size() == 25);
    static_assert(
            battle_ninja_tool_bomb_smoke_sequence.frame_count == 70);
    static_assert(
            battle_ninja_tool_bomb_smoke_sequence
                    .total_duration() == 111);
    static_assert(
            battle_ninja_tool_bomb_smoke_sequence.frames[0]
                    .components[0].semi_transparent);
    static_assert(
            battle_ninja_tool_bomb_smoke_sequence.frames[6]
                    .component_count > 8);

    const battle_effect_frame& first =
            battle_action_05_hit_sequence.frames[0];
    assert(first.component_count == 1);
    assert(first.components[0].x == 160);
    assert(first.components[0].y == 48);
    assert(first.components[0].asset_index == 0);
    assert(first.components[0].priority == 2);

    const battle_effect_frame& compound =
            *battle_action_05_hit_sequence.frame_at(4);
    assert(compound.component_count == 8);
    assert(compound.components[0].x == 164);
    assert(compound.components[0].y == 40);
    assert(compound.components[0].asset_index == 2);
    assert(compound.components[1].horizontal_flip);

    const battle_effect_frame* clamped =
            battle_action_05_hit_sequence.frame_at(16);
    assert(! clamped);

    const battle_effect_frame* first_dust =
            battle_action_05_dust_sequence.frame_at(0);
    assert(first_dust);
    assert(first_dust->component_count == 3);
    assert(first_dust->components[0].x == 54);
    assert(first_dust->components[0].y == 86);
    const battle_effect_frame* held_dust =
            battle_action_05_dust_sequence.frame_at(58);
    assert(held_dust);
    assert(held_dust->duration == 10);
    assert(held_dust->components[0].asset_index == 7);
    assert(! battle_action_05_dust_sequence.frame_at(59));
    return 0;
}
