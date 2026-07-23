#ifndef KONOHA_SCENARIO_41_EXTENDED_LAYERS_H
#define KONOHA_SCENARIO_41_EXTENDED_LAYERS_H

#include "bn_regular_bg_item.h"
#include "bn_regular_bg_items_scenario_41_result_bottom.h"
#include "bn_regular_bg_items_scenario_41_result_middle.h"
#include "bn_regular_bg_items_scenario_41_result_top.h"
#include "bn_regular_bg_items_scenario_41_level_up_1_bottom.h"
#include "bn_regular_bg_items_scenario_41_level_up_1_middle.h"
#include "bn_regular_bg_items_scenario_41_level_up_1_top.h"
#include "bn_regular_bg_items_scenario_41_level_up_2_bottom.h"
#include "bn_regular_bg_items_scenario_41_level_up_2_middle.h"
#include "bn_regular_bg_items_scenario_41_level_up_2_top.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_1_bottom.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_1_middle.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_1_top.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_2_bottom.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_2_middle.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_2_top.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_3_bottom.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_3_middle.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_3_top.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_4_bottom.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_4_middle.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_4_top.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_5_bottom.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_5_middle.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_5_top.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_6_bottom.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_6_middle.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_6_top.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_7_bottom.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_7_middle.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_7_top.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_8_bottom.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_8_middle.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_8_top.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_9_bottom.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_9_middle.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_9_top.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_10_bottom.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_10_middle.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_10_top.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_11_bottom.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_11_middle.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_11_top.h"

#include "konoha/scenario_41_battle.h"

namespace konoha
{

struct scenario_41_extended_layers
{
    const bn::regular_bg_item* bottom;
    const bn::regular_bg_item* middle;
    const bn::regular_bg_item* top;
};

[[nodiscard]] inline scenario_41_extended_layers scenario_41_extended_layers_for(
        battle_phase phase, int page)
{
    if(phase == battle_phase::result)
    {
        return { &bn::regular_bg_items::scenario_41_result_bottom,
                 &bn::regular_bg_items::scenario_41_result_middle,
                 &bn::regular_bg_items::scenario_41_result_top };
    }
    if(phase == battle_phase::level_up)
    {
        if(page == 0)
        {
            return { &bn::regular_bg_items::scenario_41_level_up_1_bottom,
                     &bn::regular_bg_items::scenario_41_level_up_1_middle,
                     &bn::regular_bg_items::scenario_41_level_up_1_top };
        }
        return { &bn::regular_bg_items::scenario_41_level_up_2_bottom,
                 &bn::regular_bg_items::scenario_41_level_up_2_middle,
                 &bn::regular_bg_items::scenario_41_level_up_2_top };
    }
    switch(page)
    {
    case 0:
        return { &bn::regular_bg_items::scenario_41_postbattle_dialogue_1_bottom,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_1_middle,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_1_top };
    case 1:
        return { &bn::regular_bg_items::scenario_41_postbattle_dialogue_2_bottom,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_2_middle,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_2_top };
    case 2:
        return { &bn::regular_bg_items::scenario_41_postbattle_dialogue_3_bottom,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_3_middle,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_3_top };
    case 3:
        return { &bn::regular_bg_items::scenario_41_postbattle_dialogue_4_bottom,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_4_middle,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_4_top };
    case 4:
        return { &bn::regular_bg_items::scenario_41_postbattle_dialogue_5_bottom,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_5_middle,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_5_top };
    case 5:
        return { &bn::regular_bg_items::scenario_41_postbattle_dialogue_6_bottom,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_6_middle,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_6_top };
    case 6:
        return { &bn::regular_bg_items::scenario_41_postbattle_dialogue_7_bottom,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_7_middle,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_7_top };
    case 7:
        return { &bn::regular_bg_items::scenario_41_postbattle_dialogue_8_bottom,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_8_middle,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_8_top };
    case 8:
        return { &bn::regular_bg_items::scenario_41_postbattle_dialogue_9_bottom,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_9_middle,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_9_top };
    case 9:
        return { &bn::regular_bg_items::scenario_41_postbattle_dialogue_10_bottom,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_10_middle,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_10_top };
    case 10:
        return { &bn::regular_bg_items::scenario_41_postbattle_dialogue_11_bottom,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_11_middle,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_11_top };
    default:
        return { &bn::regular_bg_items::scenario_41_postbattle_dialogue_11_bottom,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_11_middle,
                 &bn::regular_bg_items::scenario_41_postbattle_dialogue_11_top };
    }
}

}

#endif
