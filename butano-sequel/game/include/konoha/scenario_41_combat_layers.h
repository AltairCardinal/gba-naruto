#ifndef KONOHA_SCENARIO_41_COMBAT_LAYERS_H
#define KONOHA_SCENARIO_41_COMBAT_LAYERS_H

#include "bn_regular_bg_items_scenario_41_action_menu_0_bottom.h"
#include "bn_regular_bg_items_scenario_41_action_menu_0_middle.h"
#include "bn_regular_bg_items_scenario_41_action_menu_0_top.h"
#include "bn_regular_bg_items_scenario_41_action_menu_1_bottom.h"
#include "bn_regular_bg_items_scenario_41_action_menu_1_middle.h"
#include "bn_regular_bg_items_scenario_41_action_menu_1_top.h"
#include "bn_regular_bg_items_scenario_41_end_confirmation_bottom.h"
#include "bn_regular_bg_items_scenario_41_end_confirmation_middle.h"
#include "bn_regular_bg_items_scenario_41_end_confirmation_top.h"
#include "bn_regular_bg_items_scenario_41_defense_confirmation_bottom.h"
#include "bn_regular_bg_items_scenario_41_defense_confirmation_middle.h"
#include "bn_regular_bg_items_scenario_41_defense_confirmation_top.h"
#include "bn_regular_bg_items_scenario_41_target_select_bottom.h"
#include "bn_regular_bg_items_scenario_41_target_select_middle.h"
#include "bn_regular_bg_items_scenario_41_target_select_top.h"
#include "bn_regular_bg_items_scenario_41_attack_confirmation_bottom.h"
#include "bn_regular_bg_items_scenario_41_attack_confirmation_middle.h"
#include "bn_regular_bg_items_scenario_41_attack_confirmation_top.h"
#include "bn_regular_bg_items_scenario_41_combat_dialogue_bottom.h"
#include "bn_regular_bg_items_scenario_41_combat_dialogue_middle.h"
#include "bn_regular_bg_items_scenario_41_combat_dialogue_top.h"
#include "bn_regular_bg_items_scenario_41_combat_popup_bottom.h"
#include "bn_regular_bg_items_scenario_41_combat_popup_middle.h"
#include "bn_regular_bg_items_scenario_41_combat_popup_top.h"

#include "konoha/scenario_41_extended_layers.h"

namespace konoha
{

[[nodiscard]] inline scenario_41_extended_layers scenario_41_combat_layers_for(
        battle_phase phase, int menu_index)
{
    if(phase == battle_phase::action_menu)
    {
        if(menu_index == 0)
        {
            return { &bn::regular_bg_items::scenario_41_action_menu_0_bottom,
                     &bn::regular_bg_items::scenario_41_action_menu_0_middle,
                     &bn::regular_bg_items::scenario_41_action_menu_0_top };
        }
        return { &bn::regular_bg_items::scenario_41_action_menu_1_bottom,
                 &bn::regular_bg_items::scenario_41_action_menu_1_middle,
                 &bn::regular_bg_items::scenario_41_action_menu_1_top };
    }
    if(phase == battle_phase::end_confirmation)
    {
        return { &bn::regular_bg_items::scenario_41_end_confirmation_bottom,
                 &bn::regular_bg_items::scenario_41_end_confirmation_middle,
                 &bn::regular_bg_items::scenario_41_end_confirmation_top };
    }
    if(phase == battle_phase::defense_confirmation)
    {
        return { &bn::regular_bg_items::scenario_41_defense_confirmation_bottom,
                 &bn::regular_bg_items::scenario_41_defense_confirmation_middle,
                 &bn::regular_bg_items::scenario_41_defense_confirmation_top };
    }
    if(phase == battle_phase::target_select)
    {
        return { &bn::regular_bg_items::scenario_41_target_select_bottom,
                 &bn::regular_bg_items::scenario_41_target_select_middle,
                 &bn::regular_bg_items::scenario_41_target_select_top };
    }
    if(phase == battle_phase::attack_confirmation)
    {
        return { &bn::regular_bg_items::scenario_41_attack_confirmation_bottom,
                 &bn::regular_bg_items::scenario_41_attack_confirmation_middle,
                 &bn::regular_bg_items::scenario_41_attack_confirmation_top };
    }
    if(phase == battle_phase::combat_dialogue)
    {
        return { &bn::regular_bg_items::scenario_41_combat_dialogue_bottom,
                 &bn::regular_bg_items::scenario_41_combat_dialogue_middle,
                 &bn::regular_bg_items::scenario_41_combat_dialogue_top };
    }
    return { &bn::regular_bg_items::scenario_41_combat_popup_bottom,
             &bn::regular_bg_items::scenario_41_combat_popup_middle,
             &bn::regular_bg_items::scenario_41_combat_popup_top };
}

[[nodiscard]] inline bool scenario_41_has_combat_layers(battle_phase phase)
{
    return phase == battle_phase::action_menu ||
           phase == battle_phase::end_confirmation ||
           phase == battle_phase::defense_confirmation ||
           phase == battle_phase::target_select ||
           phase == battle_phase::attack_confirmation ||
           phase == battle_phase::combat_dialogue ||
           phase == battle_phase::combat_popup;
}

}

#endif
