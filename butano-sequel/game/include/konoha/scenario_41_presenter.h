#ifndef KONOHA_SCENARIO_41_PRESENTER_H
#define KONOHA_SCENARIO_41_PRESENTER_H

#include "konoha/scenario_41_battle.h"

namespace konoha
{

struct battle_presentation
{
    const char* line1;
    const char* line2;
    const char* line3;
    const char* line4;
};

[[nodiscard]] inline battle_presentation present_scenario_41(
        const battle_snapshot& state, battle_event)
{
    switch(state.phase)
    {
    case battle_phase::unit_select:
        return { "SELECT UNIT", "A:SELECT", "L/R:CYCLE", "" };
    case battle_phase::move_select:
        return { "MOVE", "DPAD:DESTINATION", "A:CONFIRM", "B:BACK" };
    case battle_phase::action_menu:
        return state.menu_index == 0 ?
                battle_presentation{ "ACTION", "> TECHNIQUE", "  END ACTION", "A:SELECT" } :
                battle_presentation{ "ACTION", "  TECHNIQUE", "> END ACTION", "A:SELECT" };
    case battle_phase::technique_menu:
        return { "TECHNIQUE", "> COMBO #5", "RANGE 1 / HIT 98%", "A:SELECT  B:BACK" };
    case battle_phase::target_select:
        return { "SELECT TARGET", "ACTION #5", "A:CONFIRM", "B:BACK" };
    case battle_phase::attack_confirmation:
        return { "USE COMBO #5?", "A:YES", "B:NO", "" };
    case battle_phase::end_confirmation:
        return { "END ACTION?", "UP:YES  DOWN:NO", "A:CONFIRM", "" };
    case battle_phase::facing_select:
        return { "SELECT FACING", "DPAD:DIRECTION", "A:CONFIRM", "" };
    case battle_phase::defense_confirmation:
        return { "DEFENSE PREP", "A:CONFIRM", "", "" };
    case battle_phase::enemy_turn:
        return { "ENEMY PHASE", "", "", "" };
    case battle_phase::combat_dialogue:
        return { "HIT CONFIRMED", "A:CONTINUE", "", "" };
    case battle_phase::combat_popup:
        return { "TARGET DEFEATED", "A:CONTINUE", "", "" };
    case battle_phase::victory:
        return { "VICTORY", "", "A:RESULTS", "" };
    case battle_phase::result:
        return { "MISSION COMPLETE", "MISSION EXP 100", "BATTLE EXP 50", "TOTAL EXP 150" };
    default:
        return { "", "", "", "" };
    }
}

}

#endif
