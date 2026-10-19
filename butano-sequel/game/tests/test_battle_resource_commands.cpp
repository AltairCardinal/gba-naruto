#include "konoha/battle_resource_commands.h"
#include "konoha/battle_unit_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <cassert>

using namespace konoha;

namespace
{

battle_session<2> session_with(
        const battle_unit_instance& player)
{
    battle_session<2> result;
    battle_unit_instance enemy = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::ai,
            { 4, 1 },
            battle_facing::left,
            5);
    assert(result.add_unit(player));
    assert(result.add_unit(enemy));
    assert(result.start_round() ==
           battle_transition::unit_selection_opened);
    assert(result.select_unit(player.id) ==
           battle_transition::action_draft_opened);
    return result;
}

}

int main()
{
    battle_unit_instance naruto = instantiate_unit(
            unit_definitions[1],
            1,
            battle_side::player,
            battle_control::player,
            { 1, 1 },
            battle_facing::right,
            6);
    naruto.hp = 134;
    naruto.max_hp = 152;
    naruto.base_max_hp = 152;
    naruto.chakra = 4;
    naruto.max_chakra = 5;
    assert(naruto.hand_seals == 15);

    const battle_resource_command_preview pure_chakra_preview =
            battle_resource_commands::preview(
                    naruto,
                    battle_resource_command_type::
                            replenish_chakra,
                    1,
                    false);
    assert(pure_chakra_preview.legal());
    assert(pure_chakra_preview.hp_delta == -15);
    assert(pure_chakra_preview.chakra_delta == 1);
    assert(pure_chakra_preview.maximum_amount == 1);
    assert(battle_resource_commands::preview(
                   naruto,
                   battle_resource_command_type::
                           replenish_chakra,
                   1,
                   true)
                   .error ==
           battle_resource_command_error::already_moved);

    battle_session<2> chakra_session =
            session_with(naruto);
    const battle_session<2> before_chakra_preview =
            chakra_session;
    const battle_resource_command_preview chakra_preview =
            battle_resource_commands::preview(
                    chakra_session,
                    battle_resource_command_type::
                            replenish_chakra,
                    1);
    assert(chakra_preview.legal());
    assert(chakra_preview.hp_delta == -15);
    assert(chakra_preview.chakra_delta == 1);
    assert(chakra_preview.maximum_amount == 1);
    assert(chakra_preview.error ==
           pure_chakra_preview.error);
    assert(chakra_preview.amount ==
           pure_chakra_preview.amount);
    assert(chakra_preview.hp_delta ==
           pure_chakra_preview.hp_delta);
    assert(chakra_preview.chakra_delta ==
           pure_chakra_preview.chakra_delta);
    assert(chakra_session == before_chakra_preview);

    assert(battle_resource_commands::commit(
                   chakra_session,
                   battle_resource_command_type::
                           replenish_chakra,
                   1)
                   .legal());
    assert(chakra_session.unit(1)->hp == 119);
    assert(chakra_session.unit(1)->chakra == 5);
    assert(chakra_session.unit(1)->ledger.acted);
    assert(chakra_session.lifecycle() ==
           battle_lifecycle::action_drafting);

    naruto.hp = 31;
    naruto.chakra = 1;
    naruto.max_chakra = 5;
    battle_session<2> amount_session =
            session_with(naruto);
    const battle_resource_command_preview maximum =
            battle_resource_commands::preview(
                    amount_session,
                    battle_resource_command_type::
                            replenish_chakra,
                    2);
    assert(maximum.legal());
    assert(maximum.maximum_amount == 2);
    assert(maximum.hp_delta == -30);
    assert(maximum.chakra_delta == 2);
    const battle_session<2> before_excess =
            amount_session;
    const battle_resource_command_preview excess =
            battle_resource_commands::commit(
                    amount_session,
                    battle_resource_command_type::
                            replenish_chakra,
                    3);
    assert(excess.error ==
           battle_resource_command_error::invalid_amount);
    assert(amount_session == before_excess);

    naruto.hp = 15;
    naruto.chakra = 4;
    naruto.max_chakra = 5;
    battle_session<2> lethal_session =
            session_with(naruto);
    const battle_resource_command_preview lethal =
            battle_resource_commands::preview(
                    lethal_session,
                    battle_resource_command_type::
                            replenish_chakra,
                    1);
    assert(lethal.error ==
           battle_resource_command_error::
                   insufficient_health);

    battle_unit_instance sasuke = instantiate_unit(
            unit_definitions[2],
            1,
            battle_side::player,
            battle_control::player,
            { 1, 1 },
            battle_facing::right,
            3);
    sasuke.hp = 24;
    sasuke.max_hp = 89;
    sasuke.base_max_hp = 89;
    battle_session<2> rest_session =
            session_with(sasuke);
    const battle_session<2> before_rest_preview =
            rest_session;
    const battle_resource_command_preview rest_preview =
            battle_resource_commands::preview(
                    rest_session,
                    battle_resource_command_type::rest);
    assert(rest_preview.legal());
    assert(rest_preview.hp_delta == 17);
    assert(rest_preview.chakra_delta == 0);
    assert(rest_session == before_rest_preview);
    assert(battle_resource_commands::commit(
                   rest_session,
                   battle_resource_command_type::rest)
                   .legal());
    assert(rest_session.unit(1)->hp == 41);
    assert(rest_session.unit(1)->chakra ==
           sasuke.chakra);
    assert(rest_session.unit(1)->ledger.acted);

    sasuke.hp = 85;
    battle_session<2> clamped_session =
            session_with(sasuke);
    const battle_resource_command_preview clamped =
            battle_resource_commands::preview(
                    clamped_session,
                    battle_resource_command_type::rest);
    assert(clamped.legal());
    assert(clamped.hp_delta == 4);
    assert(battle_resource_commands::commit(
                   clamped_session,
                   battle_resource_command_type::rest)
                   .legal());
    assert(clamped_session.unit(1)->hp == 89);
}
