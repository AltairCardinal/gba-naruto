#include "konoha/battle_command_browser.h"
#include "konoha/battle_unit_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_session<2> make_session(bool moved)
{
    battle_unit_instance player = instantiate_unit(
            unit_definitions[1],
            1,
            battle_side::player,
            battle_control::player,
            { 1, 1 },
            battle_facing::right,
            6);
    player.hp = 100;
    player.max_hp = 152;
    player.base_max_hp = 152;
    player.chakra = 4;
    player.max_chakra = 5;
    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::ai,
            { 4, 1 },
            battle_facing::left,
            5);
    battle_session<2> result;
    assert(result.add_unit(player));
    assert(result.add_unit(enemy));
    assert(result.start_round() ==
           battle_transition::unit_selection_opened);
    assert(result.select_unit(1) ==
           battle_transition::action_draft_opened);
    if(moved)
    {
        assert(result.preview_move({ 2, 1 }) ==
               battle_transition::move_previewed);
    }
    return result;
}

}

int main()
{
    battle_session<2> full = make_session(false);
    const battle_command_browser_result full_menu =
            battle_command_browser::build(full);
    assert(full_menu.error ==
           battle_command_browser_error::none);
    assert(full_menu.count == 6);
    assert(full_menu.entries[0].type ==
           battle_command_type::move);
    assert(full_menu.entries[1].type ==
           battle_command_type::ability);
    assert(full_menu.entries[2].type ==
           battle_command_type::direct_attack);
    assert(full_menu.entries[3].type ==
           battle_command_type::replenish_chakra);
    assert(full_menu.entries[4].type ==
           battle_command_type::rest);
    assert(full_menu.entries[5].type ==
           battle_command_type::end_action);
    for(std::size_t index = 0; index < full_menu.count;
            ++index)
    {
        assert(full_menu.entries[index].availability.available());
    }

    battle_session<2> moved = make_session(true);
    const battle_command_browser_result moved_menu =
            battle_command_browser::build(moved);
    assert(moved_menu.count == 2);
    assert(moved_menu.entries[0].type ==
           battle_command_type::ability);
    assert(moved_menu.entries[1].type ==
           battle_command_type::end_action);

    const battle_command_browser_result
            confirmed_origin_menu =
                    battle_command_browser::build(
                            full, {}, true);
    assert(confirmed_origin_menu.count == 2);
    assert(confirmed_origin_menu.entries[0].type ==
           battle_command_type::ability);
    assert(confirmed_origin_menu.entries[1].type ==
           battle_command_type::end_action);

    battle_command_access_policy tutorial;
    tutorial.allow_move = false;
    tutorial.allow_direct_attack = false;
    tutorial.allow_replenish_chakra = false;
    tutorial.allow_rest = false;
    const battle_command_browser_result tutorial_menu =
            battle_command_browser::build(full, tutorial);
    assert(tutorial_menu.count == 2);
    assert(tutorial_menu.entries[0].type ==
           battle_command_type::ability);
    assert(tutorial_menu.entries[1].type ==
           battle_command_type::end_action);

    battle_unit_instance full_resource = *full.unit(1);
    full_resource.hp = full_resource.max_hp;
    full_resource.chakra = full_resource.max_chakra;
    battle_session<2> disabled;
    assert(disabled.add_unit(full_resource));
    battle_unit_instance enemy = *full.unit(2);
    assert(disabled.add_unit(enemy));
    assert(disabled.start_round() ==
           battle_transition::unit_selection_opened);
    assert(disabled.select_unit(1) ==
           battle_transition::action_draft_opened);
    const battle_command_browser_result disabled_menu =
            battle_command_browser::build(disabled);
    assert(disabled_menu.count == 6);
    assert(disabled_menu.entries[3].availability.disabled());
    assert(disabled_menu.entries[3].availability.reason ==
           command_rejection::full_chakra);
    assert(disabled_menu.entries[4].availability.disabled());
    assert(disabled_menu.entries[4].availability.reason ==
           command_rejection::full_health);
}
