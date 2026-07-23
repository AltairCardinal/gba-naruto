#ifndef KONOHA_SCENARIO_41_PREBATTLE_FRAMES_H
#define KONOHA_SCENARIO_41_PREBATTLE_FRAMES_H

#include "bn_regular_bg_item.h"
#include "bn_regular_bg_items_scenario_41_prebattle_menu_0.h"
#include "bn_regular_bg_items_scenario_41_prebattle_menu_1.h"
#include "bn_regular_bg_items_scenario_41_prebattle_menu_2.h"
#include "bn_regular_bg_items_scenario_41_prebattle_menu_3.h"
#include "bn_regular_bg_items_scenario_41_prebattle_confirmation_yes.h"
#include "bn_regular_bg_items_scenario_41_prebattle_confirmation_no.h"

#include <array>

namespace konoha
{

inline constexpr std::array<const bn::regular_bg_item*, 4>
scenario_41_prebattle_menu_frames = {
    &bn::regular_bg_items::scenario_41_prebattle_menu_0,
    &bn::regular_bg_items::scenario_41_prebattle_menu_1,
    &bn::regular_bg_items::scenario_41_prebattle_menu_2,
    &bn::regular_bg_items::scenario_41_prebattle_menu_3,
};

inline constexpr std::array<const bn::regular_bg_item*, 2>
scenario_41_prebattle_confirmation_frames = {
    &bn::regular_bg_items::scenario_41_prebattle_confirmation_yes,
    &bn::regular_bg_items::scenario_41_prebattle_confirmation_no,
};

}

#endif
