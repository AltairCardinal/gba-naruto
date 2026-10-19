#include "konoha/battle_combat_presentation.h"
#include "konoha/battle_direct_attack.h"

#include <array>
#include <cassert>
#include <cstddef>

using namespace konoha;

namespace
{

void advance_to_next_stage(
        battle_combat_presentation& presentation)
{
    const battle_combat_presentation_stage initial =
            presentation.stage();
    int guard = 0;
    while(presentation.busy() &&
            presentation.stage() == initial)
    {
        presentation.advance();
        ++guard;
        assert(guard < 512);
    }
}

}

int main()
{
    assert(battle_combat_actor_lunges(
            active_action_definitions[5], false));
    assert(! battle_combat_actor_lunges(
            active_action_definitions[16], false));
    assert(! battle_combat_actor_lunges(
            active_action_definitions[2], false));
    assert(! battle_combat_actor_lunges(
            ninja_tool_action_definitions[1], true));

    const battle_combat_presentation_definition*
            action_05_definition =
                    battle_combat_presentation_for(5, false);
    assert(action_05_definition);
    assert(action_05_definition->steps[4].resource ==
           battle_combat_presentation_resource::
                   action_05_dust_sequence);
    assert(action_05_definition->steps[4].duration == 71);
    assert(action_05_definition->steps[5].resource ==
           battle_combat_presentation_resource::
                   action_05_hit_sequence);
    assert(action_05_definition->steps[5].duration == 16);
    const battle_combat_presentation_definition*
            direct_attack_definition =
                    battle_combat_presentation_for(
                            direct_attack_ability_id,
                            false,
                            true);
    assert(direct_attack_definition ==
           action_05_definition);

    for(std::size_t action_id = 1;
            action_id < 87;
            ++action_id)
    {
        const battle_combat_presentation_definition*
                definition =
                        battle_combat_presentation_for(
                                static_cast<ability_id>(
                                        action_id),
                                false);
        assert(definition);
        assert(definition->valid());
        const action_definition& action =
                active_action_definitions[action_id];
        const bool opponent_duel =
                action.presentation.animation_family == 1 &&
                action.target.kind ==
                        target_policy_kind::opponent_unit;
        const bool opponent_control_technique =
                action.presentation.animation_family == 5 &&
                action.target.kind ==
                        target_policy_kind::opponent_unit &&
                (action.effect.code == 14 ||
                 action.effect.code == 15 ||
                 action.effect.code == 63);
        const bool self_technique =
                action.presentation.animation_family == 5 &&
                action.target.kind ==
                        target_policy_kind::
                                self_or_implicit_actor;
        assert((definition->kind !=
                battle_combat_presentation_kind::
                        map_effect) ==
               (opponent_duel ||
                opponent_control_technique ||
                self_technique));
    }
    for(std::size_t tool_id = 1;
            tool_id < 94;
            ++tool_id)
    {
        const battle_combat_presentation_definition*
                definition =
                        battle_combat_presentation_for(
                                static_cast<ability_id>(
                                        tool_id),
                                true);
        assert(definition);
        assert(definition->valid());
        const action_definition& action =
                ninja_tool_action_definitions[tool_id];
        const bool opponent_duel =
                action.presentation.animation_family == 1 &&
                action.target.kind ==
                        target_policy_kind::opponent_unit;
        const bool opponent_bomb_tool =
                action.presentation.animation_family == 5 &&
                action.target.kind ==
                        target_policy_kind::opponent_unit;
        assert((definition->kind !=
                battle_combat_presentation_kind::
                        map_effect) ==
               (opponent_duel || opponent_bomb_tool));
    }

    const battle_combat_presentation_definition*
            fire_definition =
                    battle_combat_presentation_for(16, false);
    assert(fire_definition);
    assert(fire_definition->kind ==
           battle_combat_presentation_kind::
                   fire_projectiles);
    assert(fire_definition->step_count == 8);
    assert(fire_definition->steps[3].stage ==
           battle_combat_presentation_stage::
                   technique_title);
    assert(fire_definition->steps[3].resource ==
           battle_combat_presentation_resource::
                   action_16_fire_cutin_components);
    assert(fire_definition->steps[3].tracks ==
           (detail::duel_tracks |
            battle_combat_presentation_track::title));
    assert(fire_definition->steps[4].stage ==
           battle_combat_presentation_stage::
                   action_movie);
    assert(fire_definition->steps[4].tracks ==
           battle_combat_presentation_track::effect);
    assert(fire_definition->steps[4].resource ==
           battle_combat_presentation_resource::
                   action_16_fire_movie_components);
    assert(fire_definition->steps[4].duration == 127);
    assert(fire_definition->steps[5].resource ==
           battle_combat_presentation_resource::
                   action_16_fire_hit_sequence);
    assert(fire_definition->steps[5].duration == 79);
    assert(fire_definition->steps[5].resource_frame_offset == 49);
    assert(fire_definition->steps[5].duration_policy ==
           battle_combat_presentation_duration_policy::
                   per_impact);
    const battle_combat_presentation_definition*
            teleport_definition =
                    battle_combat_presentation_for(2, false);
    assert(teleport_definition);
    assert(teleport_definition->kind ==
           battle_combat_presentation_kind::map_effect);
    for(std::size_t index = 0;
            index < teleport_definition->step_count;
            ++index)
    {
        assert(! battle_combat_track_enabled(
                teleport_definition->steps[index].tracks,
                battle_combat_presentation_track::stage));
        assert(! battle_combat_track_enabled(
                teleport_definition->steps[index].tracks,
                battle_combat_presentation_track::hud));
    }

    for(const ability_id self_technique_id :
            std::array<ability_id, 2>{ 38, 43 })
    {
        const battle_combat_presentation_definition*
                self_technique_definition =
                        battle_combat_presentation_for(
                                self_technique_id,
                                false);
        assert(self_technique_definition);
        assert(self_technique_definition->kind ==
               battle_combat_presentation_kind::
                       self_technique);
        assert(self_technique_definition->step_count == 7);
        assert(self_technique_definition->steps[1].stage ==
               battle_combat_presentation_stage::
                       duel_setup);
        assert(self_technique_definition->steps[3].stage ==
               battle_combat_presentation_stage::
                       technique_title);
        assert(self_technique_definition->steps[4].stage ==
               battle_combat_presentation_stage::
                       action_movie);
        for(std::size_t index = 1;
                index + 1 <
                        self_technique_definition->step_count;
                ++index)
        {
            const battle_combat_presentation_track tracks =
                    self_technique_definition->steps[index].
                            tracks;
            assert(battle_combat_track_enabled(
                    tracks,
                    battle_combat_presentation_track::stage));
            assert(battle_combat_track_enabled(
                    tracks,
                    battle_combat_presentation_track::actor));
            assert(battle_combat_track_enabled(
                    tracks,
                    battle_combat_presentation_track::hud));
            assert(! battle_combat_track_enabled(
                    tracks,
                    battle_combat_presentation_track::target));
            assert(! battle_combat_track_enabled(
                    tracks,
                    battle_combat_presentation_track::map));
        }
        assert(battle_combat_track_enabled(
                self_technique_definition->steps[3].tracks,
                battle_combat_presentation_track::title));
        assert(battle_combat_track_enabled(
                self_technique_definition->steps[4].tracks,
                battle_combat_presentation_track::effect));
    }

    for(const ability_id control_technique_id :
            std::array<ability_id, 3>{ 23, 24, 80 })
    {
        const battle_combat_presentation_definition*
                control_definition =
                        battle_combat_presentation_for(
                                control_technique_id,
                                false);
        assert(control_definition);
        assert(control_definition->kind ==
               battle_combat_presentation_kind::
                       control_technique);
        assert(control_definition->step_count == 8);
        assert(battle_combat_track_enabled(
                control_definition->steps[1].tracks,
                battle_combat_presentation_track::actor));
        assert(battle_combat_track_enabled(
                control_definition->steps[1].tracks,
                battle_combat_presentation_track::target));
        assert(battle_combat_track_enabled(
                control_definition->steps[3].tracks,
                battle_combat_presentation_track::title));
        assert(control_definition->steps[5].stage ==
               battle_combat_presentation_stage::impact);
    }
    assert(! battle_combat_is_opponent_control_technique(
            active_action_definitions[22]));
    assert(battle_combat_presentation_for(22, false)->kind ==
           battle_combat_presentation_kind::map_effect);

    for(const ability_id bomb_tool_id :
            std::array<ability_id, 3>{ 49, 55, 64 })
    {
        const battle_combat_presentation_definition*
                bomb_definition =
                        battle_combat_presentation_for(
                                bomb_tool_id,
                                true);
        assert(bomb_definition);
        assert(bomb_definition->kind ==
               battle_combat_presentation_kind::bomb_tool);
        assert(bomb_definition->step_count == 8);
        assert(battle_combat_track_enabled(
                bomb_definition->steps[1].tracks,
                battle_combat_presentation_track::actor));
        assert(battle_combat_track_enabled(
                bomb_definition->steps[1].tracks,
                battle_combat_presentation_track::target));
        assert(battle_combat_track_enabled(
                bomb_definition->steps[3].tracks,
                battle_combat_presentation_track::title));
        assert(bomb_definition->steps[5].stage ==
               battle_combat_presentation_stage::impact);
    }
    const battle_combat_presentation_definition*
            damage_bomb_definition =
                    battle_combat_presentation_for(49, true);
    assert(damage_bomb_definition->steps[4].resource ==
           battle_combat_presentation_resource::
                   ninja_tool_bomb_projectile_sequence);
    assert(damage_bomb_definition->steps[4].duration == 7);
    assert(damage_bomb_definition->steps[5].resource ==
           battle_combat_presentation_resource::
                   action_05_hit_sequence);
    assert(damage_bomb_definition->steps[5].duration == 16);
    assert(damage_bomb_definition->steps[6].resource ==
           battle_combat_presentation_resource::
                   ninja_tool_bomb_smoke_sequence);
    assert(damage_bomb_definition->steps[6].duration == 111);
    assert(battle_combat_track_enabled(
            damage_bomb_definition->steps[6].tracks,
            battle_combat_presentation_track::effect));
    assert(battle_combat_presentation_for(55, true)
                   ->steps[4].resource ==
           battle_combat_presentation_resource::none);
    assert(battle_combat_presentation_for(39, true)->kind ==
           battle_combat_presentation_kind::map_effect);
    assert(battle_combat_presentation_for(73, true)->kind ==
           battle_combat_presentation_kind::map_effect);

    battle_scene_presentation_event fire;
    fire.valid = true;
    fire.has_action = true;
    fire.actor_id = 2;
    fire.action_id = 16;
    fire.origin = { 3, 4 };
    fire.destination = { 3, 4 };
    fire.target = { 7, 4 };
    fire.target_id = 9;
    fire.targets_opponent = true;
    fire.affected_unit_ids[0] = 9;
    fire.affected_unit_count = 1;
    fire.impact_count = 1;
    fire.has_combatant_vitals = true;
    fire.actor_hp = 60;
    fire.actor_max_hp = 60;
    fire.target_hp_before = 25;
    fire.target_hp_after = 0;
    fire.target_max_hp = 25;

    battle_combat_presentation presentation;
    assert(presentation.begin(fire));
    assert(presentation.busy());
    assert(presentation.event().action_id == 16);
    assert(presentation.event().actor_id == 2);
    assert(presentation.event().target_id == 9);
    // The timeline consumes the resolver's actual hit count.  A single-hit
    // fire action must never be inflated into three fake damage impacts just
    // because its movie happens to draw several projectiles.
    assert(presentation.impact_count() == 1);
    assert(presentation.stage() ==
           battle_combat_presentation_stage::
                   transition_in);
    assert(presentation.map_visible());
    assert(! presentation.duel_stage_visible());

    const std::array<
            battle_combat_presentation_stage,
            7> expected_stages = {{
        battle_combat_presentation_stage::duel_setup,
        battle_combat_presentation_stage::actor_prep,
        battle_combat_presentation_stage::technique_title,
        battle_combat_presentation_stage::action_movie,
        battle_combat_presentation_stage::impact,
        battle_combat_presentation_stage::result,
        battle_combat_presentation_stage::transition_out,
    }};
    for(const battle_combat_presentation_stage expected :
            expected_stages)
    {
        advance_to_next_stage(presentation);
        assert(presentation.stage() == expected);
        assert(! presentation.map_controls_enabled());
        if(expected ==
                battle_combat_presentation_stage::duel_setup)
        {
            assert(presentation.displayed_actor_hp() == 60);
            assert(presentation.displayed_target_hp() == 25);
            assert(! presentation.single_actor_stage());
            assert(presentation.versus_divider_visible());
        }
        if(expected ==
                battle_combat_presentation_stage::impact)
        {
            assert(presentation.displayed_target_hp() == 25);
            assert(presentation.resource_frame() == -49);
            for(int frame = 0; frame < 49; ++frame)
            {
                assert(! presentation.play_impact_cue());
                presentation.advance();
            }
            assert(presentation.resource_frame() == 0);
            assert(presentation.play_impact_cue());
            for(int frame = 0; frame < 15; ++frame)
            {
                presentation.advance();
            }
            assert(presentation.displayed_target_hp() == 0);
        }
        if(expected ==
                battle_combat_presentation_stage::result)
        {
            assert(presentation.displayed_target_hp() == 0);
        }
    }

    assert(presentation.map_visible());
    assert(! presentation.duel_stage_visible());
    advance_to_next_stage(presentation);
    assert(! presentation.busy());
    assert(presentation.map_controls_enabled());

    battle_scene_presentation_event melee = fire;
    melee.action_id = 5;
    melee.impact_count = 1;
    assert(presentation.begin(melee));
    assert(presentation.definition().kind ==
           battle_combat_presentation_kind::technique);
    bool saw_title = false;
    bool saw_movie = false;
    bool saw_impact = false;
    while(presentation.busy())
    {
        saw_title = saw_title ||
                presentation.stage() ==
                        battle_combat_presentation_stage::
                                technique_title;
        saw_movie = saw_movie ||
                presentation.stage() ==
                        battle_combat_presentation_stage::
                                action_movie;
        saw_impact = saw_impact ||
                presentation.stage() ==
                        battle_combat_presentation_stage::
                                impact;
        presentation.advance();
    }
    assert(saw_title);
    assert(saw_movie);
    assert(saw_impact);

    battle_scene_presentation_event teleport = fire;
    teleport.action_id = 2;
    teleport.animation_family =
            active_action_definitions[2]
                    .presentation.animation_family;
    teleport.targets_opponent = false;
    teleport.target_id = no_battle_unit;
    teleport.impact_count = 0;
    assert(presentation.begin(teleport));
    assert(presentation.definition().kind ==
           battle_combat_presentation_kind::map_effect);
    while(presentation.busy())
    {
        assert(presentation.map_visible());
        assert(! presentation.duel_stage_visible());
        assert(! presentation.title_visible());
        presentation.advance();
    }

    battle_scene_presentation_event byakugan = fire;
    byakugan.action_id = 38;
    byakugan.animation_family =
            active_action_definitions[38]
                    .presentation.animation_family;
    byakugan.targets_opponent = false;
    byakugan.target_id = no_battle_unit;
    byakugan.impact_count = 1;
    assert(presentation.begin(byakugan));
    assert(presentation.definition().kind ==
           battle_combat_presentation_kind::
                   self_technique);
    bool saw_self_technique_title = false;
    bool saw_self_technique_effect = false;
    while(presentation.busy())
    {
        if(! presentation.map_visible())
        {
            assert(presentation.duel_stage_visible());
            assert(presentation.actor_visible());
            assert(! presentation.target_visible());
            assert(presentation.hud_visible());
            assert(presentation.single_actor_stage());
            assert(! presentation.versus_divider_visible());
        }
        saw_self_technique_title =
                saw_self_technique_title ||
                presentation.title_visible();
        saw_self_technique_effect =
                saw_self_technique_effect ||
                presentation.effect_visible();
        presentation.advance();
    }
    assert(saw_self_technique_title);
    assert(saw_self_technique_effect);
    assert(presentation.map_visible());

    battle_scene_presentation_event shadow_imitation = fire;
    shadow_imitation.action_id = 24;
    shadow_imitation.animation_family =
            active_action_definitions[24]
                    .presentation.animation_family;
    shadow_imitation.impact_count = 1;
    assert(presentation.begin(shadow_imitation));
    assert(presentation.definition().kind ==
           battle_combat_presentation_kind::
                   control_technique);
    bool saw_control_title = false;
    bool saw_control_impact = false;
    while(presentation.busy())
    {
        const battle_combat_presentation_stage stage =
                presentation.stage();
        if(stage ==
                        battle_combat_presentation_stage::
                                duel_setup ||
                stage ==
                        battle_combat_presentation_stage::
                                actor_prep ||
                stage ==
                        battle_combat_presentation_stage::
                                impact ||
                stage ==
                        battle_combat_presentation_stage::
                                result)
        {
            assert(presentation.duel_stage_visible());
            assert(presentation.actor_visible());
            assert(presentation.target_visible());
            assert(! presentation.single_actor_stage());
        }
        saw_control_title =
                saw_control_title ||
                presentation.title_visible();
        saw_control_impact =
                saw_control_impact ||
                stage ==
                        battle_combat_presentation_stage::
                                impact;
        presentation.advance();
    }
    assert(saw_control_title);
    assert(saw_control_impact);
    assert(presentation.map_visible());

    battle_scene_presentation_event missed = fire;
    missed.impact_count = 0;
    assert(presentation.begin(missed));
    bool missed_saw_impact = false;
    while(presentation.busy())
    {
        missed_saw_impact = missed_saw_impact ||
                presentation.stage() ==
                        battle_combat_presentation_stage::
                                impact;
        presentation.advance();
    }
    assert(! missed_saw_impact);

    battle_scene_presentation_event captured = fire;
    captured.capture_count = 1;
    assert(presentation.begin(captured));
    assert(presentation.event().capture_count == 1);
    while(presentation.busy())
    {
        presentation.advance();
    }

    battle_scene_presentation_event phoenix = fire;
    phoenix.action_id = 18;
    phoenix.impact_count = 4;
    assert(presentation.begin(phoenix));
    while(presentation.stage() !=
            battle_combat_presentation_stage::impact)
    {
        presentation.advance();
    }
    for(int impact = 0; impact < 4; ++impact)
    {
        assert(presentation.current_impact_index() ==
               impact);
        for(int frame = 0;
                frame <
                        presentation.current_step().
                                duration;
                ++frame)
        {
            presentation.advance();
        }
    }
    assert(presentation.stage() ==
           battle_combat_presentation_stage::result);
}
