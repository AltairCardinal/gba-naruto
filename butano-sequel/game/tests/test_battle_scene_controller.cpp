#include "konoha/battle_scene_controller.h"
#include "konoha/battle_map_visual_projection.h"
#include "konoha/battle_mission_rules.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_scenario_content.h"

#include <cassert>
#include <type_traits>
#include <utility>

using namespace konoha;

int main()
{
    using runtime_type =
            battle_encounter_runtime<12, 9, 22>;
    static_assert(std::is_lvalue_reference_v<
            decltype(std::declval<const runtime_type&>()
                             .reachable_costs())>);
    static_assert(
            battle_map_unit_z_order({ 4, 11 }) <
            battle_map_unit_z_order({ 4, 10 }));

    battle_scenario_load_policy fixed_pool;
    fixed_pool.preserve_empty_unit_slots = true;
    battle_mission_rules confirmation_rules;
    confirmation_rules.confirm_targets = true;

    battle_scene_controller<12, 9, 22> controller;
    assert(controller.load(
                   battle_scenario_definitions[43],
                   battle_map_definitions[43],
                   battle_map_cells,
                   0,
                   fixed_pool,
                   battle_condition_variants[43][0],
                   0x43U,
                   {},
                   false,
                   confirmation_rules)
                   .success());
    assert(controller.start().success());

    battle_scene_snapshot<12> state = controller.snapshot();
    assert(state.phase == battle_scene_phase::unit_selection);
    assert(state.round == 1);
    assert(state.current_side == battle_side::player);
    assert(state.cursor == grid_point({ 4, 17 }));
    assert(state.unit_count == 12);
    assert(state.active_unit_count == 4);
    assert(state.units[0].id == 1);
    assert(state.units[0].character_id == 1);
    assert(state.units[0].hp > 0);
    assert(state.units[1].side == battle_side::enemy);
    assert(state.units[4].id == 5);
    assert(! state.units[4].active);
    assert(battle_map_cursor_facing(state) ==
           state.units[0].facing);

    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::move_selection);
    assert(state.selected_unit == 1);
    assert(state.overlay_width == 9);
    assert(state.overlay_height == 22);
    assert((state.range_overlay_rows[17] &
            (std::uint32_t(1) << 4)) != 0);
    assert((state.range_overlay_rows[16] &
            (std::uint32_t(1) << 4)) != 0);
    // The original range BG also projects collision/occupancy so the
    // renderer can show the full grid and dark blocked cells.  The
    // selected unit is highlighted separately, while the enemy at
    // (2,11) remains blocked.
    assert((state.blocked_overlay_rows[11] &
            (std::uint32_t(1) << 2)) != 0);

    // Moving the cursor in move selection updates a legal draft preview
    // without mutating the authoritative unit until the action commits.
    assert(controller.move_cursor(0, -1).success());
    state = controller.snapshot();
    assert(state.cursor == grid_point({ 4, 16 }));
    assert(state.player.move_position == state.cursor);
    assert(state.player.move_cost > 0);
    assert(state.units[0].position == grid_point({ 4, 17 }));
    assert(battle_map_visual_position(
                   state, state.units[0]) ==
           grid_point({ 4, 17 })); // selection moves the cursor, not the actor
    assert(controller.move_cursor(0, 1).success());
    state = controller.snapshot();
    assert(state.cursor == grid_point({ 4, 17 }));
    assert(state.player.move_position == state.cursor);
    assert(state.player.move_cost == 0);

    // Confirm the current cell: movement is a real zero-distance preview,
    // not a scene-side coordinate write.
    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::command_selection);
    assert(state.player.selected_command ==
           battle_command_type::ability);

    // MOVE remains actionable even after confirming a zero-distance
    // preview: it reopens movement instead of silently rejecting.
    assert(controller.move_cursor(0, -1).success());
    assert(controller.snapshot().player.selected_command ==
           battle_command_type::move);
    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::move_selection);
    assert(state.player.move_position == grid_point({ 4, 17 }));
    assert(state.player.move_cost == 0);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    assert(controller.snapshot().player.selected_command ==
           battle_command_type::ability);

    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::action_selection);
    assert(state.player.action_count == 3);
    assert(state.player.selected_action_id == 2);

    assert(controller.move_cursor(0, 1).success());
    state = controller.snapshot();
    assert(state.player.selected_action_id == 7);
    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::target_selection);
    assert((state.range_overlay_rows[17] &
            (std::uint32_t(1) << 4)) != 0);
    assert((state.target_overlay_rows[16] &
            (std::uint32_t(1) << 4)) != 0);
    // The original target-selection screen keeps the movement footprint
    // visible underneath the smaller attack footprint.
    bool has_move_only_target_cell = false;
    for(std::size_t row = 0;
            row < state.move_overlay_rows.size();
            ++row)
    {
        has_move_only_target_cell =
                has_move_only_target_cell ||
                (state.move_overlay_rows[row] &
                 ~state.range_overlay_rows[row]) != 0;
    }
    assert(has_move_only_target_cell);

    assert(controller.move_cursor(0, -1).success());
    state = controller.snapshot();
    assert(state.cursor == grid_point({ 4, 16 }));
    const battle_scene_snapshot<12> before_preview = state;
    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(state.phase ==
           battle_scene_phase::target_preview);
    assert(state.overlay_width == 9);
    assert(state.overlay_height == 22);
    assert((state.range_overlay_rows[17] &
            (std::uint32_t(1) << 4)) != 0);
    assert(state.units[0].chakra ==
           before_preview.units[0].chakra);
    assert(! controller.presentation_pending());
    assert(battle_map_visual_position(
                   state, state.units[0]) ==
           state.player.move_position);
    assert(controller.confirm().success());
    state = controller.snapshot();
    assert(state.phase ==
           battle_scene_phase::target_confirmation);
    assert(state.target_confirmation_yes);
    assert(state.overlay_width == 9);
    assert(state.overlay_height == 22);
    assert((state.range_overlay_rows[17] &
            (std::uint32_t(1) << 4)) != 0);
    assert(state.units[0].chakra ==
           before_preview.units[0].chakra);
    assert(! controller.presentation_pending());
    assert(battle_map_visual_position(
                   state, state.units[0]) ==
           state.player.move_position);
    assert(controller.move_cursor(0, 1).success());
    assert(! controller.snapshot().target_confirmation_yes);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_preview);
    assert(controller.cancel().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_preview);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_confirmation);
    assert(controller.cancel().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_preview);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_confirmation);
    assert(controller.cancel().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_preview);
    assert(controller.cancel().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_selection);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_preview);
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::target_confirmation);
    const battle_scene_control_result clone_action =
            controller.confirm();
    assert(clone_action.success());
    assert(controller.presentation_pending());
    const battle_scene_presentation_event clone_presentation =
            controller.take_presentation_event();
    assert(clone_presentation.valid);
    assert(clone_presentation.actor_id == 1);
    assert(clone_presentation.action_id == 7);
    assert(clone_presentation.origin ==
           grid_point({ 4, 17 }));
    assert(clone_presentation.destination ==
           grid_point({ 4, 17 }));
    assert(clone_presentation.target ==
           grid_point({ 4, 16 }));
    assert(clone_presentation.has_action);
    assert(! clone_presentation.ninja_tool);
    assert(clone_presentation.animation_family ==
           active_action_definitions[7]
                   .presentation.animation_family);
    assert(! clone_presentation.targets_opponent);
    assert(clone_presentation.target_id == no_battle_unit);
    assert(clone_presentation.affected_unit_count == 1);
    assert(clone_presentation.affected_unit_ids[0] == 5);
    assert(clone_presentation.impact_count ==
           clone_action.player.impact_count);
    assert(! controller.presentation_pending());
    assert(! controller.take_presentation_event().valid);
    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::facing_selection);
    assert(state.cursor == state.player.move_position);
    assert(battle_map_visual_facing(
                   state, state.units[0]) ==
           state.selected_facing);
    assert(battle_map_cursor_facing(state) ==
           state.selected_facing);
    assert(controller.move_cursor(-1, 0).success());
    state = controller.snapshot();
    assert(state.selected_facing == battle_facing::left);
    assert(battle_map_visual_facing(
                   state, state.units[0]) ==
           battle_facing::left);
    assert(state.units[0].chakra ==
           before_preview.units[0].chakra - 3);
    assert(state.active_unit_count == 5);
    assert(state.units[4].active);
    assert(state.units[4].summoner == 1);
    assert(state.units[4].position ==
           grid_point({ 4, 16 }));

    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::defense_decision);
    assert(controller.move_cursor(0, 1).success());
    assert(controller.confirm().success());
    assert(controller.snapshot().phase ==
           battle_scene_phase::enemy_turn);

    const battle_scene_control_result first_enemy =
            controller.tick();
    assert(first_enemy.success());
    const battle_scene_presentation_event enemy_presentation =
            controller.take_presentation_event();
    assert(enemy_presentation.valid);
    assert(enemy_presentation.actor_id == 2);
    assert(enemy_presentation.origin ==
           grid_point({ 2, 11 }));
    assert(enemy_presentation.destination ==
           first_enemy.ai.plan.destination);
    assert(enemy_presentation.has_action ==
           first_enemy.ai.action_resolved);
    assert(enemy_presentation.ninja_tool ==
           (first_enemy.ai.action_kind ==
                    battle_action_source_kind::ninja_tool));
    assert(enemy_presentation.animation_family ==
           first_enemy.ai.animation_family);
    assert(enemy_presentation.targets_opponent ==
           first_enemy.ai.targets_opponent);
    assert(enemy_presentation.target_id ==
           first_enemy.ai.target_id);
    assert(enemy_presentation.affected_unit_count ==
           first_enemy.ai.affected_unit_count);
    assert(enemy_presentation.affected_unit_ids ==
           first_enemy.ai.affected_unit_ids);
    assert(enemy_presentation.impact_count ==
           first_enemy.ai.impact_count);
    assert(enemy_presentation.has_resource ==
           first_enemy.ai.resource_resolved);
    assert(enemy_presentation.resource_type ==
           first_enemy.ai.resource_type);
    assert(enemy_presentation.resource_amount ==
           first_enemy.ai.resource_amount);
    assert(enemy_presentation.resource_hp_delta ==
           first_enemy.ai.resource_hp_delta);
    assert(enemy_presentation.resource_chakra_delta ==
           first_enemy.ai.resource_chakra_delta);
    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::enemy_turn);
    assert(state.units[1].completed);
    assert(! state.units[2].completed);

    assert(controller.tick().success());
    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::enemy_turn);
    assert(state.units[2].completed);
    assert(! state.units[3].completed);

    assert(controller.tick().success());
    state = controller.snapshot();
    assert(state.phase == battle_scene_phase::unit_selection);
    assert(state.round == 2);
    assert(state.current_side == battle_side::player);
    assert(state.selected_unit == 1);
    assert(state.cursor == state.units[0].position);
    assert(state.active_unit_count == 5);
    assert(! state.units[4].completed);

    // Renderer-facing snapshots are copies. Changing one cannot mutate
    // the authoritative encounter.
    state.units[0].hp = 0;
    state.units[0].position = { 0, 0 };
    const battle_scene_snapshot<12> unchanged =
            controller.snapshot();
    assert(unchanged.units[0].hp > 0);
    assert(unchanged.units[0].position != grid_point({ 0, 0 }));

    battle_scene_controller<12, 9, 22>
            tutorial_controller;
    assert(tutorial_controller.load(
                   battle_scenario_definitions[41],
                   battle_map_definitions[41],
                   battle_map_cells,
                   0,
                   fixed_pool,
                   battle_condition_variants[41][0],
                   0x41U,
                   {},
                   false,
                   battle_mission_rules_for(41, 0))
                   .success());
    assert(tutorial_controller.start().success());
    assert(tutorial_controller.confirm().success());
    assert(tutorial_controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    assert(tutorial_controller.snapshot().player.command_count == 5);
    assert(tutorial_controller.snapshot().player.selected_command ==
           battle_command_type::move);
    assert(tutorial_controller.confirm().success());
    assert(tutorial_controller.snapshot().phase ==
           battle_scene_phase::move_selection);
    assert(tutorial_controller.confirm().success());
    assert(tutorial_controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    assert(tutorial_controller.snapshot().player.command_count == 2);
    assert(tutorial_controller.snapshot().player.command_entries[0].type ==
           battle_command_type::ability);
    assert(tutorial_controller.snapshot().player.command_entries[1].type ==
           battle_command_type::end_action);
    assert(tutorial_controller.snapshot().player.selected_command ==
           battle_command_type::ability);
    assert(tutorial_controller.confirm().success());
    const battle_scene_snapshot<12> tutorial_actions =
            tutorial_controller.snapshot();
    assert(tutorial_actions.phase ==
           battle_scene_phase::action_selection);
    assert(tutorial_actions.player.action_count == 1);
    assert(tutorial_actions.player.selected_action_kind ==
           battle_action_source_kind::active_action);
    assert(tutorial_actions.player.selected_action_id == 5);

    // Scenario 41 keeps the original action-tail transaction boundaries:
    // ending an action first opens a side-effect-free yes/no dialog, facing
    // can be revisited from defense confirmation, and selecting "no defense"
    // is the point that completes the unit.
    battle_scene_controller<12, 9, 22>
            action_tail_controller;
    assert(action_tail_controller.load(
                   battle_scenario_definitions[41],
                   battle_map_definitions[41],
                   battle_map_cells,
                   0,
                   fixed_pool,
                   battle_condition_variants[41][0],
                   0x4101U,
                   {},
                   false,
                   battle_mission_rules_for(41, 0))
                   .success());
    assert(action_tail_controller.start().success());
    assert(action_tail_controller.confirm().success());
    while(action_tail_controller.snapshot().player.selected_command !=
            battle_command_type::end_action)
    {
        assert(action_tail_controller
                       .move_cursor(0, 1)
                       .success());
    }
    const battle_scene_snapshot<12> before_end_confirmation =
            action_tail_controller.snapshot();
    assert(action_tail_controller.confirm().success());
    state = action_tail_controller.snapshot();
    assert(state.phase ==
           battle_scene_phase::end_confirmation);
    assert(state.end_confirmation_yes);
    assert(state.player.phase ==
           before_end_confirmation.player.phase);
    assert(state.units[0].position ==
           before_end_confirmation.units[0].position);
    assert(! state.units[0].completed);

    assert(action_tail_controller.move_cursor(0, 1).success());
    assert(! action_tail_controller.snapshot().end_confirmation_yes);
    assert(action_tail_controller.confirm().success());
    assert(action_tail_controller.snapshot().phase ==
           battle_scene_phase::command_selection);
    assert(! action_tail_controller.snapshot().units[0].completed);

    assert(action_tail_controller.confirm().success());
    assert(action_tail_controller.snapshot().phase ==
           battle_scene_phase::end_confirmation);
    assert(action_tail_controller.cancel().success());
    assert(action_tail_controller.snapshot().phase ==
           battle_scene_phase::command_selection);

    assert(action_tail_controller.confirm().success());
    assert(action_tail_controller.snapshot().end_confirmation_yes);
    assert(action_tail_controller.confirm().success());
    assert(action_tail_controller.snapshot().phase ==
           battle_scene_phase::facing_selection);
    assert(! action_tail_controller.snapshot().units[0].completed);
    assert(action_tail_controller.confirm().success());
    state = action_tail_controller.snapshot();
    assert(state.phase ==
           battle_scene_phase::defense_decision);
    assert(state.defense_confirmation_yes);
    assert(action_tail_controller.cancel().success());
    assert(action_tail_controller.snapshot().phase ==
           battle_scene_phase::facing_selection);
    assert(action_tail_controller.confirm().success());
    assert(action_tail_controller.snapshot().phase ==
           battle_scene_phase::defense_decision);
    assert(action_tail_controller.move_cursor(0, 1).success());
    assert(! action_tail_controller.snapshot().defense_confirmation_yes);
    assert(action_tail_controller.confirm().success());
    assert(action_tail_controller.snapshot().phase ==
           battle_scene_phase::enemy_turn);
    assert(action_tail_controller.snapshot().units[0].completed);

    battle_scenario_load_policy object_policy;
    object_policy.preserve_empty_unit_slots = true;
    object_policy.character_equipped_tools[1][0] = 67;
    battle_scene_controller<12, 9, 22> object_controller;
    assert(object_controller.load(
                   battle_scenario_definitions[41],
                   battle_map_definitions[41],
                   battle_map_cells,
                   0,
                   object_policy,
                   battle_condition_variants[41][0],
                   0x41U)
                   .success());
    assert(object_controller.start().success());
    assert(object_controller.confirm().success());
    assert(object_controller.confirm().success());
    assert(object_controller.confirm().success());
    for(int index = 0;
            index < 19 &&
            (object_controller.snapshot().player
                             .selected_action_kind !=
                     battle_action_source_kind::ninja_tool ||
             object_controller.snapshot().player
                             .selected_action_id != 67);
            ++index)
    {
        assert(object_controller.move_cursor(0, 1).success());
    }
    assert(object_controller.snapshot().player
                   .selected_action_kind ==
           battle_action_source_kind::ninja_tool);
    assert(object_controller.snapshot().player
                   .selected_action_id == 67);
    assert(object_controller.confirm().success());
    assert(object_controller.move_cursor(0, -1).success());
    assert(object_controller.confirm().success());
    const battle_scene_presentation_event placement =
            object_controller.take_presentation_event();
    assert(placement.valid);
    assert(placement.action_id == 67);
    const battle_scene_object_snapshot placed_objects =
            object_controller.object_snapshot();
    assert(placed_objects.count == 1);
    assert(placed_objects.objects[0].slot == 1);
    assert(placed_objects.objects[0].type == 1);
    assert(placed_objects.objects[0].position ==
           placement.target);
    assert(placed_objects.objects[0].payload_id == 67);
    assert(placed_objects.objects[0].duration_ticks == 2);
    assert(object_controller.confirm().success());
    assert(object_controller.move_cursor(0, 1).success());
    assert(object_controller.confirm().success());
    assert(object_controller.snapshot().phase ==
           battle_scene_phase::enemy_turn);

    const battle_scene_control_result object_enemy =
            object_controller.tick();
    assert(object_enemy.success());
    assert(object_controller.take_presentation_event().valid);
    const battle_scene_presentation_event explosion =
            object_controller.take_presentation_event();
    assert(explosion.valid);
    assert(explosion.has_battlefield_object);
    assert(explosion.battlefield_object_kind ==
           battlefield_object_tick_kind::type_1_due);
    assert(explosion.battlefield_object_slot == 1);
    assert(explosion.action_id == 67);
    assert(explosion.target == placement.target);
    assert(explosion.affected_unit_count == 1);
    assert(explosion.affected_unit_ids[0] == 1);
    assert(explosion.impact_count == 1);
    assert(explosion.battlefield_object_damage > 0);
    assert(object_controller.object_snapshot().count == 0);

    battle_scenario_load_policy scroll_policy;
    scroll_policy.preserve_empty_unit_slots = true;
    scroll_policy.character_equipped_tools[1][0] = 37;
    battle_scene_controller<12, 9, 22> scroll_controller;
    assert(scroll_controller.load(
                   battle_scenario_definitions[41],
                   battle_map_definitions[41],
                   battle_map_cells,
                   0,
                   scroll_policy,
                   battle_condition_variants[41][0],
                   0x37U)
                   .success());
    assert(scroll_controller.start().success());
    assert(scroll_controller.confirm().success());
    assert(scroll_controller.confirm().success());
    assert(scroll_controller.confirm().success());
    for(int index = 0;
            index < 19 &&
            (scroll_controller.snapshot().player
                             .selected_action_kind !=
                     battle_action_source_kind::ninja_tool ||
             scroll_controller.snapshot().player
                             .selected_action_id != 37);
            ++index)
    {
        assert(scroll_controller.move_cursor(0, 1).success());
    }
    assert(scroll_controller.snapshot().player
                   .selected_action_id == 37);
    assert(scroll_controller.confirm().success());
    assert(scroll_controller.move_cursor(0, -1).success());
    assert(scroll_controller.confirm().success());
    const battle_scene_presentation_event scroll_placement =
            scroll_controller.take_presentation_event();
    assert(scroll_placement.valid);
    const grid_point scroll_position =
            scroll_placement.target;
    assert(scroll_controller.confirm().success());
    assert(scroll_controller.move_cursor(0, 1).success());
    assert(scroll_controller.confirm().success());
    assert(scroll_controller.snapshot().phase ==
           battle_scene_phase::enemy_turn);
    assert(scroll_controller.tick().success());
    assert(scroll_controller.snapshot().round == 2);

    assert(scroll_controller.confirm().success());
    assert(scroll_controller.confirm().success());
    while(scroll_controller.snapshot().player.selected_command !=
            battle_command_type::end_action)
    {
        assert(scroll_controller.move_cursor(0, 1).success());
    }
    assert(scroll_controller.confirm().success());
    assert(scroll_controller.confirm().success());
    assert(scroll_controller.confirm().success());
    assert(scroll_controller.move_cursor(0, 1).success());
    assert(scroll_controller.confirm().success());
    assert(scroll_controller.snapshot().phase ==
           battle_scene_phase::enemy_turn);
    assert(scroll_controller.tick().success());
    assert(scroll_controller.object_snapshot().count == 0);

    battle_scene_presentation_event scroll_expiry;
    while(true)
    {
        const battle_scene_presentation_event event =
                scroll_controller.take_presentation_event();
        if(! event.valid)
        {
            break;
        }
        if(event.has_battlefield_object &&
                event.battlefield_object_kind ==
                        battlefield_object_tick_kind::
                                type_2_expired)
        {
            scroll_expiry = event;
        }
    }
    assert(scroll_expiry.valid);
    assert(! scroll_expiry.has_action);
    assert(scroll_expiry.action_id == 37);
    assert(scroll_expiry.target == scroll_position);
    assert(scroll_expiry.battlefield_object_slot == 1);
    assert(scroll_expiry.battlefield_object_damage == 0);
    assert(scroll_expiry.battlefield_object_tile_index_start ==
           0x0300);
    assert(scroll_expiry.battlefield_object_tile_index_end ==
           0x037F);
    assert(scroll_expiry.battlefield_object_palette_bank_start == 12);
    assert(scroll_expiry.battlefield_object_palette_bank_end == 14);
    assert(scroll_expiry.battlefield_object_effect_sequence == 7);

    battle_scenario_load_policy poison_policy;
    poison_policy.preserve_empty_unit_slots = true;
    poison_policy.character_equipped_tools[1][0] = 11;
    battle_scene_controller<12, 9, 22> poison_controller;
    assert(poison_controller.load(
                   battle_scenario_definitions[41],
                   battle_map_definitions[41],
                   battle_map_cells,
                   0,
                   poison_policy,
                   battle_condition_variants[41][0],
                   17U)
                   .success());
    assert(poison_controller.start().success());
    assert(poison_controller.confirm().success());
    assert(poison_controller.move_cursor(0, -1).success());
    assert(poison_controller.move_cursor(0, -1).success());
    assert(poison_controller.move_cursor(0, -1).success());
    assert(poison_controller.confirm().success());
    assert(poison_controller.confirm().success());
    for(int index = 0;
            index < 19 &&
            (poison_controller.snapshot().player
                             .selected_action_kind !=
                     battle_action_source_kind::ninja_tool ||
             poison_controller.snapshot().player
                             .selected_action_id != 11);
            ++index)
    {
        assert(poison_controller.move_cursor(0, 1).success());
    }
    assert(poison_controller.snapshot().player
                   .selected_action_kind ==
           battle_action_source_kind::ninja_tool);
    assert(poison_controller.snapshot().player
                   .selected_action_id == 11);
    assert(poison_controller.confirm().success());
    assert(poison_controller.move_cursor(0, -1).success());
    assert(poison_controller.move_cursor(0, -1).success());
    assert(poison_controller.move_cursor(0, -1).success());
    const battle_scene_snapshot<12> before_poison =
            poison_controller.snapshot();
    const battle_scene_control_result poison_action =
            poison_controller.confirm();
    assert(poison_action.success());
    const battle_scene_presentation_event poison_presentation =
            poison_controller.take_presentation_event();
    assert(poison_presentation.valid);
    assert(poison_presentation.ninja_tool);
    assert(poison_presentation.action_id == 11);
    const battle_scene_snapshot<12> after_poison =
            poison_controller.snapshot();
    assert(after_poison.units[1].status_count ==
           before_poison.units[1].status_count + 3);

    character_progression_record locked_sasuke = {
        2, 50, 0, 1, true,
    };
    assert(initialize_character_action_progression(
            locked_sasuke, unit_definitions[2]));
    assert(
            locked_sasuke.primary_action_levels[10] ==
            locked_action_level);
    std::array<character_progression_record, 3>
            battle_31_roster = {{
                locked_sasuke,
                {},
                {},
            }};
    battle_scene_controller<12, 11, 21>
            battle_31_controller;
    assert(battle_31_controller.load(
                   battle_scenario_definitions[31],
                   battle_map_definitions[31],
                   battle_map_cells,
                   0,
                   fixed_pool,
                   battle_condition_variants[31][0],
                   0x31U,
                   battle_31_roster)
                   .success());
    assert(
            battle_31_controller.progression_roster()[0]
                    .primary_action_levels[10] ==
            unlocked_action_level);

    battle_scenario_load_policy escort_policy;
    escort_policy.preserve_empty_unit_slots = true;
    battle_scene_controller<12, 15, 19>
            escort_controller;
    assert(escort_controller.load(
                   battle_scenario_definitions[14],
                   battle_map_definitions[14],
                   battle_map_cells,
                   0,
                   escort_policy,
                   battle_condition_variants[14][0],
                   0x49U,
                   {},
                   false,
                   battle_mission_rules_for(14, 0))
                   .success());
    assert(escort_controller.start().success());
    assert(escort_controller.tick().success());
    const battle_scene_snapshot<12> escort_start =
            escort_controller.snapshot();
    assert(escort_start.units[3].character_id == 30);
    assert(escort_start.units[3].control ==
           battle_control::ai);
    while(escort_controller.snapshot().cursor.x != 10)
    {
        assert(escort_controller.move_cursor(-1, 0).success());
    }
    while(escort_controller.snapshot().cursor.y != 7)
    {
        assert(escort_controller.move_cursor(0, 1).success());
    }
    const battle_scene_snapshot<12> before_escort_confirm =
            escort_controller.snapshot();
    assert(! escort_controller.confirm().success());
    const battle_scene_snapshot<12> after_escort_confirm =
            escort_controller.snapshot();
    assert(after_escort_confirm.phase ==
           before_escort_confirm.phase);
    assert(after_escort_confirm.cursor ==
           before_escort_confirm.cursor);
    assert(after_escort_confirm.selected_unit ==
           before_escort_confirm.selected_unit);

    // Preserve the generic players-first policy outside the S49 opening rule.
    auto players_first_rules = battle_mission_rules_for(14, 0);
    players_first_rules.control.allied_ai_before_first_player_turn = false;
    battle_scene_controller<12, 15, 19>
            allied_ai_controller;
    assert(allied_ai_controller.load(
                   battle_scenario_definitions[14],
                   battle_map_definitions[14],
                   battle_map_cells,
                   0,
                   escort_policy,
                   battle_condition_variants[14][0],
                   0x49U,
                   {},
                   false,
                   players_first_rules)
                   .success());
    assert(allied_ai_controller.start().success());
    for(int player_index = 0;
            player_index < 3;
            ++player_index)
    {
        assert(allied_ai_controller.snapshot().phase ==
               battle_scene_phase::unit_selection);
        assert(allied_ai_controller.confirm().success());
        assert(allied_ai_controller.confirm().success());
        assert(allied_ai_controller.confirm().success()); // confirm unchanged move
        for(int command_step = 0;
                command_step < 8 &&
                allied_ai_controller.snapshot()
                                .player
                                .selected_command !=
                        battle_command_type::end_action;
                ++command_step)
        {
            assert(allied_ai_controller
                           .move_cursor(0, 1)
                           .success());
        }
        assert(allied_ai_controller.snapshot()
                       .player
                       .selected_command ==
               battle_command_type::end_action);
        assert(allied_ai_controller.confirm().success());
        assert(allied_ai_controller.confirm().success());
        assert(allied_ai_controller.confirm().success());
        assert(allied_ai_controller
                       .move_cursor(0, 1)
                       .success());
        assert(allied_ai_controller.confirm().success());
    }
    const battle_scene_snapshot<12> before_allied_ai =
            allied_ai_controller.snapshot();
    assert(before_allied_ai.phase ==
           battle_scene_phase::enemy_turn);
    assert(before_allied_ai.current_side ==
           battle_side::player);
    assert(! before_allied_ai.units[3].completed);
    const battle_scene_control_result allied_ai_turn =
            allied_ai_controller.tick();
    assert(allied_ai_turn.success());
    const battle_scene_snapshot<12> after_allied_ai =
            allied_ai_controller.snapshot();
    assert(after_allied_ai.units[3].completed);
    assert(after_allied_ai.current_side ==
           battle_side::enemy);
}
