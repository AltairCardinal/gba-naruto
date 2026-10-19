#include "konoha/battle_mission_rules.h"
#include "konoha/generated_battle_action_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    const battle_mission_rules tutorial =
            battle_mission_rules_for(41, 0);
    assert(tutorial.action_access.restrict_active_actions);
    assert(tutorial.action_access.allowed_active_action_count == 1);
    assert(tutorial.action_access.allowed_active_actions[0] == 5);
    assert(! tutorial.action_access.allow_ninja_tools);
    assert(tutorial.confirm_targets);
    assert(tutorial.open_command_before_move);
    assert(tutorial.command_access.allow_move);
    assert(tutorial.command_access.allow_ability);
    assert(! tutorial.command_access.allow_direct_attack);
    assert(tutorial.command_access.allow_replenish_chakra);
    assert(tutorial.command_access.allow_rest);
    assert(tutorial.command_access.allow_end_action);
    assert(
            tutorial.command_access
                    .confirm_move_consumes_movement);

    const battle_action_browser_entry tutorial_taijutsu = {
        battle_action_source_kind::active_action,
        5,
    };
    const battle_action_browser_entry other_ninjutsu = {
        battle_action_source_kind::active_action,
        2,
    };
    const battle_action_browser_entry ninja_tool = {
        battle_action_source_kind::ninja_tool,
        1,
    };
    assert(tutorial.action_access.allows(tutorial_taijutsu));
    assert(! tutorial.action_access.allows(other_ninjutsu));
    assert(! tutorial.action_access.allows(ninja_tool));

    const battle_mission_rules cat_capture =
            battle_mission_rules_for(9, 0);
    assert(! cat_capture.action_access.restrict_active_actions);
    assert(cat_capture.action_access.allow_ninja_tools);
    assert(! cat_capture.open_command_before_move);
    assert(! cat_capture.command_access.allow_direct_attack);
    assert(cat_capture.action_access.allows(other_ninjutsu));
    assert(cat_capture.action_access.allows(ninja_tool));
    assert(cat_capture.capture.enabled);
    assert(cat_capture.capture.target_side == battle_side::enemy);
    assert(cat_capture.capture.target_character_id == 41);
    assert(cat_capture.capture.allow_active_actions);
    assert(cat_capture.capture.allow_ninja_tools);
    assert(! cat_capture.capture.allow_direct_attacks);
    assert(cat_capture.capture.transforms_active_action(7));
    const action_definition capture_shadow_clone =
            cat_capture.capture.transform(
                    active_action_definitions[7]);
    assert(capture_shadow_clone.id == 7);
    assert(capture_shadow_clone.cost.kind ==
           action_cost_kind::current_chakra);
    assert(capture_shadow_clone.cost.scalar == 3);
    assert(capture_shadow_clone.effect.code == 1);
    assert(capture_shadow_clone.effect.potency == 10);
    assert(capture_shadow_clone.effect.base_hit_count == 1);
    assert(capture_shadow_clone.effect.success_rate_percent == 98);
    assert(capture_shadow_clone.target.kind ==
           target_policy_kind::opponent_unit);
    assert(capture_shadow_clone.range.maximum_distance() == 1);

    const battle_mission_rules bells =
            battle_mission_rules_for(44, 0);
    assert(bells.objective.enabled);
    assert(bells.objective.object_slot == 1);
    assert(bells.objective.object.type == 3);
    assert(bells.objective.object.x == 4);
    assert(bells.objective.object.y == 4);
    assert(bells.objective.actor_side ==
           battle_side::player);
    assert(bells.objective.interaction_position ==
           grid_point({ 4, 3 }));
    assert(bells.objective.interaction_facing ==
           battle_facing::down);
    assert(bells.objective.require_side_inactive);
    assert(bells.objective.required_inactive_side ==
           battle_side::enemy);
    assert(! bells.result.award_battle_experience);

    const battle_mission_rules team_seven_training =
            battle_mission_rules_for(45, 0);
    assert(! team_seven_training.objective.enabled);
    assert(! team_seven_training
                    .action_access
                    .restrict_active_actions);
    assert(team_seven_training
                   .action_access
                   .allow_ninja_tools);
    assert(team_seven_training
                   .result
                   .award_battle_experience);

    const battle_mission_rules escort_mission =
            battle_mission_rules_for(14, 0);
    assert(escort_mission.control.ai_unit_count == 1);
    assert(escort_mission.control.allied_ai_before_first_player_turn);
    assert(! battle_mission_rules_for(14, 1).control.allied_ai_before_first_player_turn);
    assert(escort_mission.control.ai_units[0].character_id == 30);
    assert(escort_mission.control.ai_units[0]
                   .has_focus_position);
    assert(escort_mission.control.ai_units[0]
                   .focus_position ==
           grid_point({ 12, 3 }));

    const battle_mission_rules second_escort_mission =
            battle_mission_rules_for(15, 0);
    assert(second_escort_mission.control.ai_unit_count == 1);
    assert(! second_escort_mission.control.allied_ai_before_first_player_turn);
    assert(second_escort_mission.control.ai_units[0]
                   .character_id == 30);
    assert(! second_escort_mission.control.ai_units[0]
                    .has_focus_position);

    assert(battle_mission_rules_for(-1, 0) ==
           battle_mission_rules{});
    assert(battle_mission_rules_for(41, 3) ==
           battle_mission_rules{});
}
