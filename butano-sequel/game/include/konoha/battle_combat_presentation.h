#ifndef KONOHA_BATTLE_COMBAT_PRESENTATION_H
#define KONOHA_BATTLE_COMBAT_PRESENTATION_H

#include "konoha/battle_scene_presentation_event.h"
#include "konoha/generated_battle_action_content.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_combat_presentation_kind : std::uint8_t
{
    map_effect,
    technique,
    self_technique,
    fire_projectiles,
    thrown_tool,
    control_technique,
    bomb_tool,
};

enum class battle_combat_presentation_stage : std::uint8_t
{
    transition_in,
    duel_setup,
    actor_prep,
    technique_title,
    action_movie,
    impact,
    result,
    transition_out,
    complete,
};

enum class battle_combat_presentation_track : std::uint8_t
{
    none = 0,
    map = 1 << 0,
    stage = 1 << 1,
    actor = 1 << 2,
    target = 1 << 3,
    title = 1 << 4,
    effect = 1 << 5,
    hud = 1 << 6,
};

[[nodiscard]] constexpr battle_combat_presentation_track operator|(
        battle_combat_presentation_track left,
        battle_combat_presentation_track right)
{
    return static_cast<battle_combat_presentation_track>(
            static_cast<std::uint8_t>(left) |
            static_cast<std::uint8_t>(right));
}

[[nodiscard]] constexpr bool battle_combat_track_enabled(
        battle_combat_presentation_track tracks,
        battle_combat_presentation_track track)
{
    return (static_cast<std::uint8_t>(tracks) &
            static_cast<std::uint8_t>(track)) != 0;
}

enum class battle_combat_presentation_resource : std::uint8_t
{
    none,
    action_16_fire_movie_components,
    thrown_tool,
    action_05_hit_sequence,
    action_05_dust_sequence,
    action_16_fire_hit_sequence,
    action_16_fire_cutin_components,
    ninja_tool_bomb_projectile_sequence,
    ninja_tool_bomb_smoke_sequence,
};

enum class battle_combat_presentation_duration_policy : std::uint8_t
{
    fixed,
    per_impact,
};

struct battle_combat_presentation_step
{
    battle_combat_presentation_stage stage =
            battle_combat_presentation_stage::complete;
    battle_combat_presentation_track tracks =
            battle_combat_presentation_track::none;
    battle_combat_presentation_resource resource =
            battle_combat_presentation_resource::none;
    std::uint16_t duration = 0;
    battle_combat_presentation_duration_policy duration_policy =
            battle_combat_presentation_duration_policy::fixed;
    std::uint16_t resource_frame_offset = 0;

    [[nodiscard]] constexpr bool valid() const
    {
        return stage !=
                       battle_combat_presentation_stage::complete &&
                tracks !=
                        battle_combat_presentation_track::none &&
                duration > 0 &&
                resource_frame_offset < duration;
    }
};

struct battle_combat_presentation_definition
{
    battle_combat_presentation_kind kind =
            battle_combat_presentation_kind::map_effect;
    std::array<battle_combat_presentation_step, 8> steps = {};
    std::uint8_t step_count = 0;

    [[nodiscard]] constexpr bool valid() const
    {
        if(step_count == 0 || step_count > steps.size() ||
                steps[0].stage !=
                        battle_combat_presentation_stage::
                                transition_in ||
                steps[step_count - 1].stage !=
                        battle_combat_presentation_stage::
                                transition_out)
        {
            return false;
        }
        for(std::size_t index = 0;
                index < step_count;
                ++index)
        {
            if(! steps[index].valid())
            {
                return false;
            }
        }
        return true;
    }
};

[[nodiscard]] inline constexpr bool
battle_combat_actor_lunges(
        const action_definition& action,
        bool ninja_tool)
{
    return ! ninja_tool &&
            action.presentation.animation_family == 1 &&
            action.target.kind ==
                    target_policy_kind::opponent_unit &&
            action.range.maximum_distance() <= 1;
}

[[nodiscard]] inline constexpr bool
battle_combat_is_opponent_control_technique(
        const action_definition& action)
{
    if(action.presentation.animation_family != 5 ||
            action.target.kind !=
                    target_policy_kind::opponent_unit)
    {
        return false;
    }
    // The original runtime descriptor distinguishes the shared family-5
    // display binding from the resolver effect.  Only the opponent control
    // effects use the two-combatant technique transaction; linked cleanup
    // (effect 11) remains a map action even though it shares the binding.
    return action.effect.code == 14 ||
            action.effect.code == 15 ||
            action.effect.code == 63;
}

[[nodiscard]] inline constexpr bool
battle_combat_is_opponent_bomb_tool(
        const action_definition& action)
{
    // Natural original-ROM routes for a damage bomb (tool 49) and a
    // status bomb (tool 55) both enter the two-combatant stage, show the
    // tool title, bind a target effect sequence and return to the map.
    // All opponent-targeted family-5 tool definitions (49..66 in the
    // extracted table) share that presentation contract.
    return action.presentation.animation_family == 5 &&
            action.target.kind ==
                    target_policy_kind::opponent_unit;
}

namespace detail
{

inline constexpr battle_combat_presentation_track map_track =
        battle_combat_presentation_track::map;
inline constexpr battle_combat_presentation_track duel_tracks =
        battle_combat_presentation_track::stage |
        battle_combat_presentation_track::actor |
        battle_combat_presentation_track::target |
        battle_combat_presentation_track::hud;
inline constexpr battle_combat_presentation_track
        self_technique_tracks =
                battle_combat_presentation_track::stage |
                battle_combat_presentation_track::actor |
                battle_combat_presentation_track::hud;
inline constexpr battle_combat_presentation_track title_tracks =
        battle_combat_presentation_track::title;
inline constexpr battle_combat_presentation_track movie_tracks =
        battle_combat_presentation_track::actor |
        battle_combat_presentation_track::effect;

[[nodiscard]] constexpr battle_combat_presentation_step fixed_step(
        battle_combat_presentation_stage stage,
        battle_combat_presentation_track tracks,
        std::uint16_t duration,
        battle_combat_presentation_resource resource =
                battle_combat_presentation_resource::none)
{
    return {
        stage,
        tracks,
        resource,
        duration,
        battle_combat_presentation_duration_policy::fixed,
    };
}

[[nodiscard]] constexpr battle_combat_presentation_step impact_step(
        std::uint16_t duration,
        battle_combat_presentation_resource resource =
                battle_combat_presentation_resource::none)
{
    return {
        battle_combat_presentation_stage::impact,
        duel_tracks |
                battle_combat_presentation_track::effect,
        resource,
        duration,
        battle_combat_presentation_duration_policy::per_impact,
    };
}

[[nodiscard]] constexpr battle_combat_presentation_definition
make_map_effect_presentation()
{
    battle_combat_presentation_definition result;
    result.kind = battle_combat_presentation_kind::map_effect;
    result.steps[0] = fixed_step(
            battle_combat_presentation_stage::transition_in,
            map_track, 8);
    result.steps[1] = fixed_step(
            battle_combat_presentation_stage::actor_prep,
            map_track |
                    battle_combat_presentation_track::actor |
                    battle_combat_presentation_track::effect,
            24);
    result.steps[2] = fixed_step(
            battle_combat_presentation_stage::result,
            map_track, 12);
    result.steps[3] = fixed_step(
            battle_combat_presentation_stage::transition_out,
            map_track, 8);
    result.step_count = 4;
    return result;
}

[[nodiscard]] constexpr battle_combat_presentation_definition
make_self_technique_presentation()
{
    battle_combat_presentation_definition result;
    result.kind =
            battle_combat_presentation_kind::self_technique;
    result.steps[0] = fixed_step(
            battle_combat_presentation_stage::transition_in,
            map_track, 12);
    result.steps[1] = fixed_step(
            battle_combat_presentation_stage::duel_setup,
            self_technique_tracks, 8);
    result.steps[2] = fixed_step(
            battle_combat_presentation_stage::actor_prep,
            self_technique_tracks, 30);
    result.steps[3] = fixed_step(
            battle_combat_presentation_stage::technique_title,
            self_technique_tracks |
                    battle_combat_presentation_track::title,
            42);
    result.steps[4] = fixed_step(
            battle_combat_presentation_stage::action_movie,
            self_technique_tracks |
                    battle_combat_presentation_track::effect,
            48);
    result.steps[5] = fixed_step(
            battle_combat_presentation_stage::result,
            self_technique_tracks, 18);
    result.steps[6] = fixed_step(
            battle_combat_presentation_stage::transition_out,
            map_track, 12);
    result.step_count = 7;
    return result;
}

[[nodiscard]] constexpr battle_combat_presentation_definition
make_technique_presentation(
        battle_combat_presentation_kind kind,
        battle_combat_presentation_resource movie_resource,
        battle_combat_presentation_resource impact_resource,
        std::uint16_t impact_duration = 14)
{
    battle_combat_presentation_definition result;
    result.kind = kind;
    result.steps[0] = fixed_step(
            battle_combat_presentation_stage::transition_in,
            map_track, 12);
    result.steps[1] = fixed_step(
            battle_combat_presentation_stage::duel_setup,
            duel_tracks, 8);
    result.steps[2] = fixed_step(
            battle_combat_presentation_stage::actor_prep,
            duel_tracks, 30);
    result.steps[3] = fixed_step(
            battle_combat_presentation_stage::technique_title,
            title_tracks, 42);
    result.steps[4] = fixed_step(
            battle_combat_presentation_stage::action_movie,
            movie_tracks, 48, movie_resource);
    result.steps[5] = impact_step(
            impact_duration, impact_resource);
    result.steps[6] = fixed_step(
            battle_combat_presentation_stage::result,
            duel_tracks, 18);
    result.steps[7] = fixed_step(
            battle_combat_presentation_stage::transition_out,
            map_track, 12);
    result.step_count = 8;
    return result;
}

[[nodiscard]] constexpr battle_combat_presentation_definition
make_thrown_presentation()
{
    battle_combat_presentation_definition result;
    result.kind = battle_combat_presentation_kind::thrown_tool;
    result.steps[0] = fixed_step(
            battle_combat_presentation_stage::transition_in,
            map_track, 12);
    result.steps[1] = fixed_step(
            battle_combat_presentation_stage::duel_setup,
            duel_tracks, 8);
    result.steps[2] = fixed_step(
            battle_combat_presentation_stage::actor_prep,
            duel_tracks, 18);
    result.steps[3] = fixed_step(
            battle_combat_presentation_stage::action_movie,
            movie_tracks, 20,
            battle_combat_presentation_resource::thrown_tool);
    result.steps[4] = impact_step(
            14,
            battle_combat_presentation_resource::thrown_tool);
    result.steps[5] = fixed_step(
            battle_combat_presentation_stage::result,
            duel_tracks, 16);
    result.steps[6] = fixed_step(
            battle_combat_presentation_stage::transition_out,
            map_track, 12);
    result.step_count = 7;
    return result;
}

[[nodiscard]] constexpr battle_combat_presentation_definition
make_damage_bomb_presentation()
{
    battle_combat_presentation_definition result;
    result.kind = battle_combat_presentation_kind::bomb_tool;
    result.steps[0] = fixed_step(
            battle_combat_presentation_stage::transition_in,
            map_track, 12);
    result.steps[1] = fixed_step(
            battle_combat_presentation_stage::duel_setup,
            duel_tracks, 8);
    result.steps[2] = fixed_step(
            battle_combat_presentation_stage::actor_prep,
            duel_tracks, 20);
    result.steps[3] = fixed_step(
            battle_combat_presentation_stage::technique_title,
            duel_tracks |
                    battle_combat_presentation_track::title,
            24);
    result.steps[4] = fixed_step(
            battle_combat_presentation_stage::action_movie,
            duel_tracks |
                    battle_combat_presentation_track::effect,
            7,
            battle_combat_presentation_resource::
                    ninja_tool_bomb_projectile_sequence);
    result.steps[5] = impact_step(
            16,
            battle_combat_presentation_resource::
                    action_05_hit_sequence);
    result.steps[6] = fixed_step(
            battle_combat_presentation_stage::result,
            duel_tracks |
                    battle_combat_presentation_track::effect,
            111,
            battle_combat_presentation_resource::
                    ninja_tool_bomb_smoke_sequence);
    result.steps[7] = fixed_step(
            battle_combat_presentation_stage::transition_out,
            map_track, 12);
    result.step_count = 8;
    return result;
}

[[nodiscard]] constexpr std::array<
        battle_combat_presentation_definition,
        87> make_active_presentations()
{
    std::array<
            battle_combat_presentation_definition,
            87> result = {};
    for(std::size_t index = 1;
            index < result.size();
            ++index)
    {
        const action_definition& action =
                active_action_definitions[index];
        const bool opponent_duel =
                action.presentation.animation_family == 1 &&
                action.target.kind ==
                        target_policy_kind::opponent_unit;
        const bool self_technique =
                action.presentation.animation_family == 5 &&
                action.target.kind ==
                        target_policy_kind::
                                self_or_implicit_actor;
        if(opponent_duel)
        {
            result[index] = make_technique_presentation(
                    battle_combat_presentation_kind::
                            technique,
                    battle_combat_presentation_resource::
                            none,
                    battle_combat_presentation_resource::
                            none);
        }
        else if(battle_combat_is_opponent_control_technique(
                        action))
        {
            result[index] = make_technique_presentation(
                    battle_combat_presentation_kind::
                            control_technique,
                    battle_combat_presentation_resource::
                            none,
                    battle_combat_presentation_resource::
                            none);
        }
        else if(self_technique)
        {
            result[index] =
                    make_self_technique_presentation();
        }
        else
        {
            result[index] = make_map_effect_presentation();
        }
    }

    result[5] = make_technique_presentation(
            battle_combat_presentation_kind::technique,
            battle_combat_presentation_resource::
                    action_05_dust_sequence,
            battle_combat_presentation_resource::
                    action_05_hit_sequence,
            16);
    result[5].steps[4].duration = 71;

    battle_combat_presentation_definition fire =
            make_technique_presentation(
                    battle_combat_presentation_kind::
                            fire_projectiles,
                    battle_combat_presentation_resource::
                            action_16_fire_movie_components,
                    battle_combat_presentation_resource::
                            action_16_fire_hit_sequence,
                    79);
    // Original action 16 runtime anchors measured from the accepted final
    // target confirmation: 7 -> 51 -> 69 -> 190 -> 311 -> 438 -> 517 ->
    // 547 -> 578. The hit OAM starts 49 frames after the duel is restored.
    fire.steps[0].duration = 44;
    fire.steps[1].duration = 18;
    fire.steps[2].duration = 121;
    fire.steps[3].tracks =
            duel_tracks |
            battle_combat_presentation_track::title;
    fire.steps[3].resource =
            battle_combat_presentation_resource::
                    action_16_fire_cutin_components;
    fire.steps[3].duration = 121;
    fire.steps[4].tracks =
            battle_combat_presentation_track::effect;
    fire.steps[4].duration = 127;
    fire.steps[5].resource_frame_offset = 49;
    fire.steps[6].duration = 30;
    fire.steps[7].duration = 31;
    result[16] = fire;
    return result;
}

[[nodiscard]] constexpr std::array<
        battle_combat_presentation_definition,
        94> make_tool_presentations()
{
    std::array<
            battle_combat_presentation_definition,
            94> result = {};
    for(std::size_t index = 1;
            index < result.size();
            ++index)
    {
        const action_definition& action =
                ninja_tool_action_definitions[index];
        if(action.presentation.animation_family == 1 &&
                action.target.kind ==
                        target_policy_kind::opponent_unit)
        {
            result[index] = make_thrown_presentation();
        }
        else if(battle_combat_is_opponent_bomb_tool(action))
        {
            if(action.effect.code == 1)
            {
                result[index] =
                        make_damage_bomb_presentation();
            }
            else
            {
                result[index] =
                        make_technique_presentation(
                                battle_combat_presentation_kind::
                                        bomb_tool,
                                battle_combat_presentation_resource::
                                        none,
                                battle_combat_presentation_resource::
                                        none);
            }
        }
        else
        {
            result[index] = make_map_effect_presentation();
        }
    }
    return result;
}

}

inline constexpr std::array<
        battle_combat_presentation_definition,
        87> battle_active_action_presentations =
                detail::make_active_presentations();

inline constexpr std::array<
        battle_combat_presentation_definition,
        94> battle_ninja_tool_presentations =
                detail::make_tool_presentations();

[[nodiscard]] inline constexpr const action_definition*
battle_combat_action_definition_for(
        ability_id action_id,
        bool ninja_tool)
{
    if(ninja_tool)
    {
        return action_id > 0 &&
                       action_id <
                               ninja_tool_action_definitions
                                       .size() ?
                &ninja_tool_action_definitions[action_id] :
                nullptr;
    }
    return action_id > 0 &&
                   action_id <
                           active_action_definitions.size() ?
            &active_action_definitions[action_id] :
            nullptr;
}

[[nodiscard]] inline constexpr bool
battle_combat_actor_lunges(
        ability_id action_id,
        bool ninja_tool)
{
    const action_definition* action =
            battle_combat_action_definition_for(
                    action_id, ninja_tool);
    return action &&
            battle_combat_actor_lunges(
                    *action, ninja_tool);
}

[[nodiscard]] inline constexpr
const battle_combat_presentation_definition*
battle_combat_presentation_for(
        ability_id action_id,
        bool ninja_tool,
        bool direct_attack = false)
{
    if(direct_attack)
    {
        return &battle_active_action_presentations[5];
    }
    if(ninja_tool)
    {
        return action_id > 0 &&
                       action_id <
                               battle_ninja_tool_presentations
                                       .size() ?
                &battle_ninja_tool_presentations[action_id] :
                nullptr;
    }
    return action_id > 0 &&
                   action_id <
                           battle_active_action_presentations
                                   .size() ?
            &battle_active_action_presentations[action_id] :
            nullptr;
}

class battle_combat_presentation
{
public:
    [[nodiscard]] bool begin(
            const battle_scene_presentation_event& event)
    {
        if(! event.valid || ! event.has_action ||
                event.actor_id == no_battle_unit ||
                event.action_id == no_ability ||
                event.impact_count < 0)
        {
            return false;
        }
        const battle_combat_presentation_definition*
                definition =
                        battle_combat_presentation_for(
                                event.action_id,
                                event.ninja_tool,
                                event.direct_attack);
        if(! definition || ! definition->valid())
        {
            return false;
        }
        _event = event;
        _definition = *definition;
        _impact_count = event.impact_count;
        _step_index = 0;
        _stage_frame = 0;
        _total_frame = 0;
        _active = true;
        _skip_empty_runtime_steps();
        return _active;
    }

    [[nodiscard]] constexpr bool busy() const
    {
        return _active;
    }

    [[nodiscard]] constexpr
    battle_combat_presentation_stage stage() const
    {
        return _active ?
                current_step().stage :
                battle_combat_presentation_stage::complete;
    }

    [[nodiscard]] constexpr
    const battle_combat_presentation_step& current_step() const
    {
        return _definition.steps[_step_index];
    }

    [[nodiscard]] constexpr int stage_frame() const
    {
        return _stage_frame;
    }

    [[nodiscard]] constexpr int resource_frame() const
    {
        if(! _active)
        {
            return -1;
        }
        const battle_combat_presentation_step& step =
                current_step();
        const int stage_local_frame =
                step.duration_policy ==
                                battle_combat_presentation_duration_policy::
                                        per_impact ?
                        _stage_frame % step.duration :
                        _stage_frame;
        return stage_local_frame -
                step.resource_frame_offset;
    }

    [[nodiscard]] constexpr int frame() const
    {
        return _total_frame;
    }

    [[nodiscard]] constexpr int impact_count() const
    {
        return _impact_count;
    }

    [[nodiscard]] constexpr int displayed_actor_hp() const
    {
        return _event.has_combatant_vitals ?
                _event.actor_hp :
                -1;
    }

    [[nodiscard]] constexpr int displayed_actor_max_hp() const
    {
        return _event.has_combatant_vitals ?
                _event.actor_max_hp :
                -1;
    }

    [[nodiscard]] constexpr int displayed_target_hp() const
    {
        if(! _event.has_combatant_vitals)
        {
            return -1;
        }
        if(stage() !=
                        battle_combat_presentation_stage::impact &&
                stage() !=
                        battle_combat_presentation_stage::result &&
                stage() !=
                        battle_combat_presentation_stage::
                                transition_out &&
                stage() !=
                        battle_combat_presentation_stage::complete)
        {
            return _event.target_hp_before;
        }
        if(stage() ==
                    battle_combat_presentation_stage::impact &&
                _impact_count > 0)
        {
            const int effect_duration =
                    current_step().duration -
                    current_step().resource_frame_offset;
            const int effect_frame = resource_frame();
            int completed =
                    effect_frame < 0 ?
                            0 :
                            (effect_frame +
                             effect_duration / 2) /
                                    effect_duration;
            if(completed > _impact_count)
            {
                completed = _impact_count;
            }
            return _event.target_hp_before +
                    (_event.target_hp_after -
                     _event.target_hp_before) *
                            completed /
                            _impact_count;
        }
        return _event.target_hp_after;
    }

    [[nodiscard]] constexpr int displayed_target_max_hp() const
    {
        return _event.has_combatant_vitals ?
                _event.target_max_hp :
                -1;
    }

    [[nodiscard]] constexpr
    const battle_scene_presentation_event& event() const
    {
        return _event;
    }

    [[nodiscard]] constexpr
    const battle_combat_presentation_definition&
    definition() const
    {
        return _definition;
    }

    [[nodiscard]] constexpr bool track_visible(
            battle_combat_presentation_track track) const
    {
        return _active &&
                battle_combat_track_enabled(
                        current_step().tracks, track);
    }

    [[nodiscard]] constexpr bool map_visible() const
    {
        return ! _active ||
                track_visible(
                        battle_combat_presentation_track::map);
    }

    [[nodiscard]] constexpr bool duel_stage_visible() const
    {
        return track_visible(
                battle_combat_presentation_track::stage);
    }

    [[nodiscard]] constexpr bool title_visible() const
    {
        return track_visible(
                battle_combat_presentation_track::title);
    }

    [[nodiscard]] constexpr bool movie_visible() const
    {
        return _active &&
                stage() ==
                        battle_combat_presentation_stage::
                                action_movie;
    }

    [[nodiscard]] constexpr bool actor_visible() const
    {
        return track_visible(
                battle_combat_presentation_track::actor);
    }

    [[nodiscard]] constexpr bool target_visible() const
    {
        return track_visible(
                battle_combat_presentation_track::target);
    }

    [[nodiscard]] constexpr bool single_actor_stage() const
    {
        return duel_stage_visible() &&
                actor_visible() &&
                ! target_visible();
    }

    [[nodiscard]] constexpr bool versus_divider_visible() const
    {
        return duel_stage_visible() &&
                actor_visible() &&
                target_visible();
    }

    [[nodiscard]] constexpr bool hud_visible() const
    {
        return track_visible(
                battle_combat_presentation_track::hud);
    }

    [[nodiscard]] constexpr bool effect_visible() const
    {
        return track_visible(
                battle_combat_presentation_track::effect);
    }

    [[nodiscard]] constexpr
    battle_combat_presentation_resource resource() const
    {
        return _active ?
                current_step().resource :
                battle_combat_presentation_resource::none;
    }

    [[nodiscard]] constexpr bool map_controls_enabled() const
    {
        return ! _active;
    }

    [[nodiscard]] constexpr int current_impact_index() const
    {
        if(stage() !=
                battle_combat_presentation_stage::impact)
        {
            return -1;
        }
        return _stage_frame / current_step().duration;
    }

    [[nodiscard]] constexpr bool play_impact_cue() const
    {
        return stage() ==
                       battle_combat_presentation_stage::
                               impact &&
                _stage_frame % current_step().duration ==
                        current_step().resource_frame_offset;
    }

    void advance()
    {
        if(! _active)
        {
            return;
        }
        ++_stage_frame;
        ++_total_frame;
        if(_stage_frame >= _current_duration())
        {
            ++_step_index;
            _stage_frame = 0;
            _skip_empty_runtime_steps();
        }
    }

private:
    [[nodiscard]] constexpr int _current_duration() const
    {
        const battle_combat_presentation_step& step =
                current_step();
        return step.duration_policy ==
                               battle_combat_presentation_duration_policy::
                                       per_impact ?
                step.duration * _impact_count :
                step.duration;
    }

    void _skip_empty_runtime_steps()
    {
        while(_step_index < _definition.step_count)
        {
            const battle_combat_presentation_step& step =
                    current_step();
            if(step.duration_policy !=
                            battle_combat_presentation_duration_policy::
                                    per_impact ||
                    _impact_count > 0)
            {
                return;
            }
            ++_step_index;
        }
        if(_step_index >= _definition.step_count)
        {
            _active = false;
        }
    }

    battle_scene_presentation_event _event;
    battle_combat_presentation_definition _definition;
    std::size_t _step_index = 0;
    int _stage_frame = 0;
    int _total_frame = 0;
    int _impact_count = 0;
    bool _active = false;
};

}

#endif
