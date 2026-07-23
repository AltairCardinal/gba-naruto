#include "konoha/scenario_41_scene.h"

#include "bn_blending.h"
#include "bn_camera_ptr.h"
#include "bn_core.h"
#include "bn_keypad.h"
#ifndef KONOHA_DIAGNOSTIC_WAV_BGM
#include "bn_music_items.h"
#endif
#include "bn_optional.h"
#include "bn_regular_bg_items_scenario_41_clean_map.h"
#include "bn_regular_bg_items_scenario_41_tutorial_bg.h"
#include "bn_regular_bg_items_scenario_41_tutorial_portraits.h"
#include "bn_regular_bg_items_scenario_41_tutorial_ui.h"
#include "bn_regular_bg_items_scenario_41_victory_actor.h"
#include "bn_regular_bg_items_scenario_41_victory_bg.h"
#include "bn_regular_bg_items_scenario_41_victory_title.h"
#include "bn_regular_bg_items_scenario_41_postbattle_bg.h"
#include "bn_regular_bg_items_scenario_41_postbattle_ui.h"
#include "bn_regular_bg_ptr.h"
#include "bn_sprite_items_scenario_41_cursor.h"
#include "bn_sprite_items_scenario_41_cursor_shadow.h"
#include "bn_sprite_items_scenario_41_enemy.h"
#include "bn_sprite_items_scenario_41_naruto.h"
#include "bn_sprite_items_scenario_41_select_label.h"
#include "bn_sprite_ptr.h"
#include "bn_sprite_text_generator.h"
#include "bn_string.h"
#ifdef KONOHA_DIAGNOSTIC_WAV_BGM
#include "bn_sound_handle.h"
#endif
#include "bn_sound_items.h"
#include "bn_vector.h"

#include "common_variable_8x16_sprite_font.h"
#include "konoha/scenario_41_battle.h"
#include "konoha/scenario_41_attack_animation_frames.h"
#include "konoha/scenario_41_extended_layers.h"
#include "konoha/scenario_41_prebattle_frames.h"
#include "konoha/scenario_41_presenter.h"

#ifdef KONOHA_DIAGNOSTIC_WAV_BGM
#define KONOHA_MUSIC_ITEM(name) bn::sound_items::name
#else
#define KONOHA_MUSIC_ITEM(name) bn::music_items::name
#endif

namespace konoha
{
namespace
{

constexpr int map_center_x = 256;
constexpr int map_center_y = 256;
constexpr int cell_width = 32;
constexpr int cell_height = 16;
constexpr int initial_camera_x = -112;

template<typename AudioItem>
void play_audio_item(const AudioItem& item)
{
#ifndef KONOHA_DIAGNOSTIC_NO_AUDIO
    item.play();
#else
    (void) item;
#endif
}

#ifdef KONOHA_DIAGNOSTIC_WAV_BGM
bn::optional<bn::sound_handle> wav_bgm_handle;
#endif

template<typename MusicItem>
void play_music_item(const MusicItem& item)
{
#ifndef KONOHA_DIAGNOSTIC_NO_AUDIO
#ifdef KONOHA_DIAGNOSTIC_WAV_BGM
    if(wav_bgm_handle)
    {
        wav_bgm_handle->stop();
    }
    wav_bgm_handle = item.play();
#else
    item.play();
#endif
#else
    (void) item;
#endif
}

int world_x(grid_point point)
{
    return point.x * cell_width + cell_width / 2 - map_center_x;
}

int world_y(grid_point point)
{
    return point.y * cell_height + cell_height / 2 - map_center_y;
}

int camera_y(grid_point point)
{
    int result = world_y(point);
    if(result < -176)
    {
        result = -176;
    }
    else if(result > 16)
    {
        result = 16;
    }
    return result;
}

void generate_centered(
        bn::sprite_text_generator& generator, int y, const char* text,
        bn::vector<bn::sprite_ptr, 128>& sprites)
{
    generator.set_center_alignment();
    generator.generate(0, y, text, sprites);
}

[[nodiscard]] bool is_live_battle_phase(battle_phase phase)
{
    switch(phase)
    {
    case battle_phase::unit_select:
    case battle_phase::move_select:
    case battle_phase::action_menu:
    case battle_phase::end_confirmation:
    case battle_phase::facing_select:
    case battle_phase::defense_confirmation:
    case battle_phase::technique_menu:
    case battle_phase::target_select:
    case battle_phase::attack_confirmation:
    case battle_phase::enemy_turn:
    case battle_phase::combat_dialogue:
    case battle_phase::combat_popup:
        return true;
    default:
        return false;
    }
}

void render_battle_overlay(
        const battle_snapshot& state,
        const battle_presentation& presentation,
        bn::sprite_text_generator& generator,
        bn::vector<bn::sprite_ptr, 128>& sprites)
{
    generator.set_left_alignment();
    bn::string<32> player_status = "NARUTO HP ";
    player_status += bn::to_string<8>(state.naruto.hp);
    player_status += "/";
    player_status += bn::to_string<8>(state.naruto.max_hp);
    generator.generate(-116, -72, player_status, sprites);

    bn::string<32> enemy_status = "ENEMY HP ";
    enemy_status += bn::to_string<8>(state.konoha_maru.hp);
    enemy_status += "/";
    enemy_status += bn::to_string<8>(state.konoha_maru.max_hp);
    generator.generate(-116, -60, enemy_status, sprites);
    generator.generate(-116, 32, presentation.line1, sprites);
    generator.generate(-116, 44, presentation.line2, sprites);
    generator.generate(-116, 56, presentation.line3, sprites);
    generator.generate(-116, 68, presentation.line4, sprites);
}

void render_text(
        const battle_snapshot& state, battle_event feedback,
        bn::sprite_text_generator& generator, bn::vector<bn::sprite_ptr, 128>& sprites)
{
    sprites.clear();
    const battle_presentation presentation = present_scenario_41(state, feedback);
    if(is_live_battle_phase(state.phase))
    {
        render_battle_overlay(state, presentation, generator, sprites);
        return;
    }
    if(state.phase == battle_phase::intro)
    {
        generate_centered(generator, -32, presentation.line1, sprites);
        generate_centered(generator, -12, presentation.line2, sprites);
        generate_centered(generator, 32, presentation.line3, sprites);
        return;
    }
    if(state.phase == battle_phase::victory)
    {
        generate_centered(generator, -16, presentation.line1, sprites);
        generate_centered(generator, 20, presentation.line3, sprites);
        return;
    }
    if(state.phase == battle_phase::result)
    {
        generate_centered(generator, -40, presentation.line1, sprites);
        generate_centered(generator, -12, presentation.line2, sprites);
        generate_centered(generator, 12, presentation.line3, sprites);
        generate_centered(generator, 44, presentation.line4, sprites);
        return;
    }

    // Active battle UI is rendered by the original BG3 tile/palette layer.
}

battle_event read_input(scenario_41_battle& battle)
{
    if(bn::keypad::l_pressed())
    {
        const battle_event event = battle.dispatch({ command_kind::cycle_previous_unit });
        play_audio_item(event == battle_event::invalid ? bn::sound_items::sound_105 :
                                                        bn::sound_items::sound_104);
        return event;
    }
    if(bn::keypad::r_pressed())
    {
        const battle_event event = battle.dispatch({ command_kind::cycle_next_unit });
        play_audio_item(event == battle_event::invalid ? bn::sound_items::sound_105 :
                                                        bn::sound_items::sound_104);
        return event;
    }
    if(bn::keypad::a_pressed())
    {
        const battle_event event = battle.dispatch({ command_kind::confirm });
        if(event == battle_event::invalid)
        {
            play_audio_item(bn::sound_items::sound_105);
        }
        else
        {
            play_audio_item(bn::sound_items::sound_102);
        }
        return event;
    }
    if(bn::keypad::b_pressed())
    {
        const battle_event event = battle.dispatch({ command_kind::cancel });
        if(event == battle_event::invalid)
        {
            play_audio_item(bn::sound_items::sound_105);
        }
        else
        {
            play_audio_item(bn::sound_items::sound_103);
        }
        return event;
    }
    if(bn::keypad::start_pressed())
    {
        const battle_event event = battle.dispatch({ command_kind::wait });
        play_audio_item(bn::sound_items::sound_105);
        return event;
    }
    if(bn::keypad::left_pressed())
    {
        const battle_event event = battle.dispatch({ command_kind::move_cursor, -1, 0 });
        if(event == battle_event::invalid)
        {
            play_audio_item(bn::sound_items::sound_105);
        }
        else
        {
            play_audio_item(bn::sound_items::sound_104);
        }
        return event;
    }
    if(bn::keypad::right_pressed())
    {
        const battle_event event = battle.dispatch({ command_kind::move_cursor, 1, 0 });
        play_audio_item(event == battle_event::invalid ? bn::sound_items::sound_105 :
                                                        bn::sound_items::sound_104);
        return event;
    }
    if(bn::keypad::up_pressed())
    {
        const battle_event event = battle.dispatch({ command_kind::move_cursor, 0, -1 });
        play_audio_item(event == battle_event::invalid ? bn::sound_items::sound_105 :
                                                        bn::sound_items::sound_104);
        return event;
    }
    if(bn::keypad::down_pressed())
    {
        const battle_event event = battle.dispatch({ command_kind::move_cursor, 0, 1 });
        play_audio_item(event == battle_event::invalid ? bn::sound_items::sound_105 :
                                                        bn::sound_items::sound_104);
        return event;
    }
    return battle_event::none;
}

void update_scenario_41_audio(battle_event event, const battle_snapshot& state)
{
    if(event == battle_event::intro_dismissed)
    {
        play_music_item(KONOHA_MUSIC_ITEM(sound_014));
        play_audio_item(bn::sound_items::sound_126);
    }
    else if(event == battle_event::attack_confirmation_opened)
    {
        play_audio_item(bn::sound_items::sound_117);
    }
    else if(state.phase == battle_phase::combat_animation && state.animation_frame == 47)
    {
        play_music_item(KONOHA_MUSIC_ITEM(sound_015));
    }
    else if(state.phase == battle_phase::combat_animation && state.animation_frame == 64)
    {
        play_audio_item(bn::sound_items::sound_116);
    }
    else if(state.phase == battle_phase::combat_animation && state.animation_frame == 140)
    {
        play_audio_item(bn::sound_items::sound_138);
    }
    else if(event == battle_event::combat_popup_opened)
    {
        play_music_item(KONOHA_MUSIC_ITEM(sound_014));
        play_audio_item(bn::sound_items::sound_149);
    }
    else if(event == battle_event::victory_shown)
    {
        play_audio_item(bn::sound_items::sound_158);
        play_audio_item(bn::sound_items::sound_051);
    }
    else if(event == battle_event::result_shown)
    {
        play_audio_item(bn::sound_items::sound_157);
        play_audio_item(bn::sound_items::sound_112);
    }
    else if(event == battle_event::level_up_shown)
    {
        play_audio_item(bn::sound_items::sound_052);
    }
    else if(event == battle_event::postbattle_dialogue_opened)
    {
        play_music_item(KONOHA_MUSIC_ITEM(sound_008));
    }
    else if(event == battle_event::postbattle_opened)
    {
        play_music_item(KONOHA_MUSIC_ITEM(sound_002));
    }
}

}

void run_scenario_41_scene()
{
    // Runtime player-state evidence identifies cue 5 as the preparation BGM.
    play_music_item(KONOHA_MUSIC_ITEM(sound_005));
    scenario_41_battle battle;
    bn::optional<bn::regular_bg_ptr> map;
    bn::optional<bn::regular_bg_ptr> move_overlay;
    bn::optional<bn::regular_bg_ptr> hud;
    map.emplace(scenario_41_prebattle_menu_frames[0]->create_bg(8, 48));
    map->set_priority(3);
    bn::camera_ptr camera = bn::camera_ptr::create(
            initial_camera_x, camera_y(battle.snapshot().cursor));

    bn::sprite_ptr cursor_shadow = bn::sprite_items::scenario_41_cursor_shadow.create_sprite(
            world_x(battle.snapshot().cursor), world_y(battle.snapshot().cursor) - 23);
    bn::sprite_ptr naruto = bn::sprite_items::scenario_41_naruto.create_sprite(
            world_x(battle.snapshot().naruto.position),
            world_y(battle.snapshot().naruto.position) - 24);
    bn::sprite_ptr enemy = bn::sprite_items::scenario_41_enemy.create_sprite(
            world_x(battle.snapshot().konoha_maru.position),
            world_y(battle.snapshot().konoha_maru.position) - 16);
    bn::sprite_ptr cursor = bn::sprite_items::scenario_41_cursor.create_sprite(
            world_x(battle.snapshot().cursor), world_y(battle.snapshot().cursor) - 24);
    bn::sprite_ptr select_label =
            bn::sprite_items::scenario_41_select_label.create_sprite(96, -64);
    naruto.set_camera(camera);
    enemy.set_camera(camera);
    cursor.set_camera(camera);
    cursor_shadow.set_camera(camera);
    naruto.set_bg_priority(2);
    naruto.set_z_order(0);
    enemy.set_bg_priority(2);
    enemy.set_z_order(0);
    cursor.set_bg_priority(1);
    cursor_shadow.set_bg_priority(2);
    cursor_shadow.set_z_order(1);
    select_label.set_bg_priority(0);
    select_label.set_visible(false);
    naruto.set_visible(false);
    enemy.set_visible(false);
    cursor.set_visible(false);
    cursor_shadow.set_visible(false);

    bn::sprite_text_generator text_generator(common::variable_8x16_sprite_font);
    text_generator.set_bg_priority(0);
    bn::vector<bn::sprite_ptr, 128> text_sprites;
    battle_event feedback = battle_event::none;
    int automatic_frames = 0;
    int feedback_frames = 0;
    battle_phase loaded_phase = battle.snapshot().phase;
    int loaded_page = battle.snapshot().dialogue_page;
    int loaded_menu_index = battle.snapshot().menu_index;
    int loaded_confirmation_index = battle.snapshot().confirmation_index;
    int loaded_animation_frame = battle.snapshot().animation_frame;
    presentation_cue loaded_presentation = battle.snapshot().presentation;
    render_text(battle.snapshot(), feedback, text_generator, text_sprites);

    while(true)
    {
        const battle_snapshot before = battle.snapshot();
        battle_event event = battle_event::none;
        bool render_dirty = false;
        if(before.phase == battle_phase::combat_animation)
        {
            event = battle.dispatch({ command_kind::tick });
        }
        else if(before.phase == battle_phase::intro &&
                before.presentation_mode_value == presentation_mode::automatic)
        {
            event = battle.dispatch({ command_kind::tick });
        }
        else if(before.phase == battle_phase::enemy_turn)
        {
            ++automatic_frames;
            if(automatic_frames >= 45)
            {
                event = battle.dispatch({ command_kind::tick });
                automatic_frames = 0;
            }
        }
        else
        {
            automatic_frames = 0;
            event = read_input(battle);
        }

        if(event != battle_event::none)
        {
            feedback = event;
            feedback_frames = 60;
            render_dirty = true;
        }
        else if(feedback_frames > 0)
        {
            --feedback_frames;
            if(feedback_frames == 0)
            {
                feedback = battle_event::none;
                render_dirty = true;
            }
        }

        const battle_snapshot state = battle.snapshot();
        update_scenario_41_audio(event, state);
        if(state != before)
        {
            render_dirty = true;
        }
        if(render_dirty)
        {
            const bool extended_page_changed =
                    state.dialogue_page != loaded_page &&
                    (state.phase == battle_phase::level_up ||
                     state.phase == battle_phase::postbattle_dialogue);
            const bool combat_menu_changed =
                    state.phase == battle_phase::action_menu &&
                    state.menu_index != loaded_menu_index;
            const bool prebattle_menu_changed =
                    state.phase == battle_phase::prebattle_menu &&
                    state.menu_index != loaded_menu_index;
            const bool prebattle_confirmation_changed =
                    state.phase == battle_phase::prebattle_confirmation &&
                    state.confirmation_index != loaded_confirmation_index;
            const bool animation_frame_changed =
                    state.phase == battle_phase::combat_animation &&
                    state.animation_frame != loaded_animation_frame;
            const bool presentation_changed =
                    state.presentation != loaded_presentation;
            if(state.phase != loaded_phase || extended_page_changed || combat_menu_changed ||
                    prebattle_menu_changed || prebattle_confirmation_changed ||
                    animation_frame_changed || presentation_changed)
            {
                bn::blending::restore();
                hud.reset();
                move_overlay.reset();
                map.reset();
                if(state.phase == battle_phase::prebattle_menu)
                {
                    map.emplace(
                            scenario_41_prebattle_menu_frames[state.menu_index]->create_bg(8, 48));
                }
                else if(state.phase == battle_phase::prebattle_confirmation)
                {
                    map.emplace(
                            scenario_41_prebattle_confirmation_frames[state.confirmation_index]->create_bg(8, 48));
                }
                else if(state.phase == battle_phase::intro)
                {
                    if(state.presentation != presentation_cue::black)
                    {
                        map.emplace(bn::regular_bg_items::scenario_41_clean_map.create_bg(0, 0));
                        map->set_camera(camera);
                    }
                }
                else if(state.phase == battle_phase::combat_animation)
                {
                    if(state.animation_frame < 4)
                    {
                        map.emplace(
                                scenario_41_attack_alpha_bottom[state.animation_frame]->create_bg(8, 48));
                        move_overlay.emplace(
                                scenario_41_attack_alpha_middle[state.animation_frame]->create_bg(8, 48));
                        hud.emplace(
                                scenario_41_attack_alpha_top[state.animation_frame]->create_bg(8, 48));
                        map->set_blending_bottom_enabled(true);
                        move_overlay->set_blending_enabled(true);
                        bn::blending::set_transparency_weights(0.625, 0.625);
                    }
                    else
                    {
                        map.emplace(
                                scenario_41_attack_animation_frames[state.animation_frame]->create_bg(8, 48));
                        const int dark_fade =
                                scenario_41_attack_animation_dark_fade[state.animation_frame];
                        if(dark_fade)
                        {
                            map->set_blending_enabled(true);
                            bn::blending::set_black_fade_color();
                            bn::blending::set_fade_alpha(bn::fixed(dark_fade) / 16);
                        }
                    }
                }
                else if(is_live_battle_phase(state.phase))
                {
                    map.emplace(
                            bn::regular_bg_items::scenario_41_clean_map.create_bg(0, 0));
                    map->set_camera(camera);
                }
                else if(state.phase == battle_phase::tutorial_dialogue)
                {
                    map.emplace(
                            bn::regular_bg_items::scenario_41_tutorial_bg.create_bg(8, 48));
                    move_overlay.emplace(
                            bn::regular_bg_items::scenario_41_tutorial_portraits.create_bg(8, 48));
                    hud.emplace(
                            bn::regular_bg_items::scenario_41_tutorial_ui.create_bg(8, 48));
                }
                else if(state.phase == battle_phase::victory)
                {
                    map.emplace(
                            bn::regular_bg_items::scenario_41_victory_bg.create_bg(8, 48));
                    move_overlay.emplace(
                            bn::regular_bg_items::scenario_41_victory_actor.create_bg(8, 48));
                    hud.emplace(
                            bn::regular_bg_items::scenario_41_victory_title.create_bg(8, 48));
                }
                else if(state.phase == battle_phase::postbattle)
                {
                    map.emplace(
                            bn::regular_bg_items::scenario_41_postbattle_bg.create_bg(8, 48));
                    hud.emplace(
                            bn::regular_bg_items::scenario_41_postbattle_ui.create_bg(8, 48));
                }
                else if(state.phase == battle_phase::result ||
                        state.phase == battle_phase::level_up ||
                        state.phase == battle_phase::postbattle_dialogue)
                {
                    const scenario_41_extended_layers layers =
                            scenario_41_extended_layers_for(state.phase, state.dialogue_page);
                    map.emplace(layers.bottom->create_bg(8, 48));
                    move_overlay.emplace(layers.middle->create_bg(8, 48));
                    hud.emplace(layers.top->create_bg(8, 48));
                }
                else
                {
                    map.emplace(
                            bn::regular_bg_items::scenario_41_clean_map.create_bg(0, 0));
                    map->set_camera(camera);
                }
                if(map)
                {
                    map->set_priority(3);
                }
                if(move_overlay)
                {
                    move_overlay->set_priority(2);
                }
                if(hud)
                {
                    hud->set_priority(0);
                }
                loaded_phase = state.phase;
                loaded_page = state.dialogue_page;
                loaded_menu_index = state.menu_index;
                loaded_confirmation_index = state.confirmation_index;
                loaded_animation_frame = state.animation_frame;
                loaded_presentation = state.presentation;
            }
            naruto.set_position(
                    world_x(state.naruto.position), world_y(state.naruto.position) - 24);
            enemy.set_position(
                    world_x(state.konoha_maru.position),
                    world_y(state.konoha_maru.position) - 16);
            cursor.set_position(world_x(state.cursor), world_y(state.cursor) - 24);
            cursor_shadow.set_position(world_x(state.cursor), world_y(state.cursor) - 23);
            const bool facing_visible = state.phase == battle_phase::facing_select;
            const bool technique_visible = state.phase == battle_phase::technique_menu;
            const bool tutorial_visible = state.phase == battle_phase::tutorial_dialogue;
            const bool victory_visible = state.phase == battle_phase::victory;
            const bool postbattle_visible = state.phase == battle_phase::postbattle;
            const bool extended_visible =
                    state.phase == battle_phase::result ||
                    state.phase == battle_phase::level_up ||
                    state.phase == battle_phase::postbattle_dialogue;
            const bool combat_visible = is_live_battle_phase(state.phase);
            const bool animation_visible = state.phase == battle_phase::combat_animation;
            const bool prebattle_visible =
                    state.phase == battle_phase::prebattle_menu ||
                    state.phase == battle_phase::prebattle_confirmation;
            const bool intro_visible =
                    state.phase == battle_phase::intro && state.presentation_visible;
            const bool intro_actor_visible = intro_visible &&
                    state.presentation == presentation_cue::player_appearance;
            const bool battle_visible = combat_visible;
            const bool cursor_visible =
                    state.phase == battle_phase::unit_select ||
                    state.phase == battle_phase::move_select ||
                    state.phase == battle_phase::target_select ||
                    state.phase == battle_phase::facing_select;
            naruto.set_visible(battle_visible || intro_actor_visible);
            const bool intro_enemy_visible = intro_visible &&
                    state.presentation != presentation_cue::player_appearance;
            enemy.set_visible((battle_visible && state.konoha_maru.active) ||
                              intro_enemy_visible);
            cursor.set_visible(cursor_visible);
            cursor_shadow.set_visible(cursor_visible);
            if(map)
            {
                map->set_visible(
                        battle_visible || facing_visible || technique_visible || tutorial_visible ||
                        victory_visible || postbattle_visible || extended_visible || combat_visible ||
                        animation_visible || prebattle_visible || intro_visible);
            }
            if(hud)
            {
                hud->set_visible(
                        battle_visible || facing_visible || technique_visible || tutorial_visible ||
                        victory_visible || postbattle_visible || extended_visible || combat_visible ||
                        animation_visible);
            }
            if(move_overlay)
            {
                move_overlay->set_visible(
                        state.phase == battle_phase::move_select || tutorial_visible ||
                        victory_visible || extended_visible || combat_visible || animation_visible);
            }
            select_label.set_visible(state.phase == battle_phase::move_select);
            camera.set_y(camera_y(state.cursor));
            render_text(state, feedback, text_generator, text_sprites);
        }

        bn::core::update();
    }
}

}
