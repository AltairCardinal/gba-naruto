#ifndef KONOHA_BATTLE_MISSION_RULES_H
#define KONOHA_BATTLE_MISSION_RULES_H

#include "konoha/battle_capture_policy.h"
#include "konoha/battle_mission_objective.h"
#include "konoha/battle_player_action_flow.h"
#include "konoha/battle_result_policy.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr std::size_t
        battle_mission_ai_character_capacity = 6;

struct battle_mission_ai_unit_policy
{
    std::uint8_t character_id = 0;
    bool has_focus_position = false;
    grid_point focus_position = {};
    int focus_position_weight = 1;

    constexpr bool operator==(
            const battle_mission_ai_unit_policy&) const = default;
};

struct battle_mission_control_policy
{
    std::array<
            battle_mission_ai_unit_policy,
            battle_mission_ai_character_capacity>
            ai_units = {};
    std::uint8_t ai_unit_count = 0;
    bool allied_ai_before_first_player_turn = false;

    constexpr bool operator==(
            const battle_mission_control_policy&) const = default;

    [[nodiscard]] constexpr const battle_mission_ai_unit_policy*
    ai_unit(std::uint8_t character_id) const
    {
        const std::size_t count =
                ai_unit_count < ai_units.size() ?
                        ai_unit_count :
                        ai_units.size();
        for(std::size_t index = 0; index < count; ++index)
        {
            if(ai_units[index].character_id == character_id)
            {
                return &ai_units[index];
            }
        }
        return nullptr;
    }
};

struct battle_mission_rules
{
    battle_action_access_policy action_access = {};
    battle_command_access_policy command_access = {};
    battle_capture_policy capture = {};
    battle_mission_control_policy control = {};
    battle_mission_objective objective = {};
    battle_result_policy result = {};
    bool confirm_targets = false;
    bool open_command_before_move = false;
    bool show_turn_banner = false;

    [[nodiscard]] constexpr bool operator==(
            const battle_mission_rules& other) const
    {
        return action_access.restrict_active_actions ==
                       other.action_access
                               .restrict_active_actions &&
                action_access.allowed_active_actions ==
                        other.action_access
                                .allowed_active_actions &&
                action_access.allowed_active_action_count ==
                        other.action_access
                                .allowed_active_action_count &&
                action_access.allow_ninja_tools ==
                        other.action_access.allow_ninja_tools &&
                action_access.allow_direct_attack ==
                        other.action_access.allow_direct_attack &&
                command_access.allow_move ==
                        other.command_access.allow_move &&
                command_access.allow_ability ==
                        other.command_access.allow_ability &&
                command_access.allow_direct_attack ==
                        other.command_access.allow_direct_attack &&
                command_access.allow_replenish_chakra ==
                        other.command_access
                                .allow_replenish_chakra &&
                command_access.allow_rest ==
                        other.command_access.allow_rest &&
                command_access.allow_end_action ==
                        other.command_access.allow_end_action &&
                command_access.confirm_move_consumes_movement ==
                        other.command_access
                                .confirm_move_consumes_movement &&
                capture == other.capture &&
                control == other.control &&
                objective == other.objective &&
                result == other.result &&
                confirm_targets == other.confirm_targets &&
                open_command_before_move ==
                        other.open_command_before_move &&
                show_turn_banner == other.show_turn_banner;
    }
};

[[nodiscard]] constexpr battle_mission_rules
battle_mission_rules_for(int battle_id, int variant)
{
    if(battle_id < 0 || battle_id >= 47 ||
            variant < 0 || variant >= 3)
    {
        return {};
    }

    battle_mission_rules result;
    if(battle_id == 9 && variant == 0)
    {
        result.capture.enabled = true;
        result.capture.target_side = battle_side::enemy;
        result.capture.target_character_id = 41;
        result.capture.allow_active_actions = true;
        result.capture.allow_ninja_tools = true;
        result.capture.allow_direct_attacks = false;
        result.capture.transformed_active_actions[0] = 7;
        result.capture.transformed_active_action_count = 1;
        result.action_access.allow_direct_attack = false;
        result.command_access.allow_direct_attack = false;
    }
    else if((battle_id == 14 || battle_id == 15) &&
            variant == 0)
    {
        result.confirm_targets = battle_id == 14;
        if(battle_id == 14)
        {
            result.control.allied_ai_before_first_player_turn = true;
            // The original shows the command menu (original frame 18, five
            // items including 移動) BEFORE the destination grid (frame 19),
            // and the grid again after the move (frame 19) ends in the two
            // item menu (frame 20).  The remake therefore keeps the menu
            // before the move selection, and the move consumes the movement
            // so that the second menu drops 移動.
            // 4.3.85 measured the other order: it puts the five item menu
            // after the grid, which is the opposite of the original.
            result.open_command_before_move = true;
            result.action_access.allow_direct_attack = false;
            result.command_access.allow_direct_attack = false;
            result.command_access.confirm_move_consumes_movement = true;
            // The original shows a round banner between the opening dialogue
            // and the first command (original frame 15: 回合 1 / 玩家 的行动).
            result.show_turn_banner = true;
        }
        result.control.ai_units[0] = {
            30,
            battle_id == 14,
            battle_id == 14 ?
                    grid_point({ 12, 3 }) :
                    grid_point{},
            battle_id == 14 ? 10000 : 1,
        };
        result.control.ai_unit_count = 1;
    }
    else if(battle_id == 41 && variant == 0)
    {
        result.action_access.restrict_active_actions = true;
        result.action_access.allowed_active_actions[0] = 5;
        result.action_access.allowed_active_action_count = 1;
        result.action_access.allow_ninja_tools = false;
        result.action_access.allow_direct_attack = false;
        result.command_access.allow_direct_attack = false;
        result.command_access.confirm_move_consumes_movement =
                true;
        result.confirm_targets = true;
        result.open_command_before_move = true;
    }
    else if(battle_id == 44 && variant == 0)
    {
        result.objective.enabled = true;
        result.objective.object_slot = 1;
        result.objective.object.type = 3;
        result.objective.object.x = 4;
        result.objective.object.y = 4;
        result.objective.actor_side =
                battle_side::player;
        result.objective.interaction_position = { 4, 3 };
        result.objective.interaction_facing =
                battle_facing::down;
        result.objective.require_side_inactive = true;
        result.objective.required_inactive_side =
                battle_side::enemy;
        result.result.award_battle_experience = false;
    }
    return result;
}

}

#endif
