#include "konoha/battle_action_execution.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>

using namespace konoha;

namespace
{

constexpr grid_point source_position = { 8, 8 };

battle_unit_instance unit(
        battle_unit_id id,
        battle_side side,
        grid_point position,
        bool active = true)
{
    battle_unit_instance result = {
        id,
        side,
        side == battle_side::player ?
                battle_control::player :
                battle_control::ai,
        position,
        battle_facing::down,
        800,
        1000,
        80,
        100,
        6,
        active,
        {},
    };
    result.attack = 120;
    result.defense = 40;
    result.agility = 80;
    result.hand_seals = 20;
    result.character_id = id;
    result.original_character_id = id;
    result.level = 99;
    return result;
}

void prepare_action_requirement(
        battle_unit_instance& source,
        const action_definition& action)
{
    std::uint16_t stage = 0;
    if(action.id >= 44 && action.id <= 47)
    {
        stage = static_cast<std::uint16_t>(action.id - 43);
    }
    else if(action.id == 48)
    {
        stage = 1;
    }
    else if(action.id == 49)
    {
        stage = 3;
    }
    else if(action.effect.code == 0x14)
    {
        stage = 1;
    }
    if(stage > 0)
    {
        assert(source.statuses.upsert({
            0x13, 0, 0, 0, 0, 0, stage,
        }));
    }
}

template<std::size_t MaxUnits>
bool add_test_units(
        battle_session<MaxUnits>& session,
        const action_definition& action,
        ninja_tool_id tool_id)
{
    battle_unit_instance source = unit(
            1, battle_side::player, source_position);
    source.agility = 99;
    prepare_action_requirement(source, action);
    if(tool_id != no_ninja_tool)
    {
        source.equipped_tools[0] = tool_id;
    }

    battle_unit_instance friendly_a = unit(
            2, battle_side::player, { 8, 9 });
    battle_unit_instance friendly_b = unit(
            3, battle_side::player, { 9, 8 });
    battle_unit_instance enemy_a = unit(
            4, battle_side::enemy, { 8, 7 });
    battle_unit_instance enemy_b = unit(
            5, battle_side::enemy, { 7, 8 });
    battle_unit_instance enemy_c = unit(
            6, battle_side::enemy, { 9, 9 });
    enemy_a.agility = 0;
    enemy_b.agility = 0;
    enemy_c.agility = 0;
    if(effect_resolver_registry::handler_for(
               action.effect.code) ==
            effect_handler_kind::linked_cleanup)
    {
        source.ai_linked_unit = enemy_a.id;
        for(battle_unit_instance* candidate :
                { &friendly_a, &friendly_b,
                  &enemy_a, &enemy_b, &enemy_c })
        {
            candidate->unit_state_code = 0x02;
            candidate->summoner = source.id;
        }
    }

    return session.add_unit(source) &&
            session.add_unit(friendly_a) &&
            session.add_unit(friendly_b) &&
            session.add_unit(enemy_a) &&
            session.add_unit(enemy_b) &&
            session.add_unit(enemy_c) &&
            session.add_unit(unit(
                    7, battle_side::player, { 0, 0 }, false)) &&
            session.add_unit(unit(
                    8, battle_side::player, { 0, 0 }, false));
}

template<std::size_t MaxUnits>
bool find_legal_target(
        const battle_session<MaxUnits>& session,
        const action_definition& action,
        grid_point& target)
{
    for(int y = 0; y < 16; ++y)
    {
        for(int x = 0; x < 16; ++x)
        {
            const grid_point candidate = { x, y };
            if(battle_action_execution::preview(
                       session, action, candidate).legal())
            {
                target = candidate;
                return true;
            }
        }
    }
    return false;
}

void require_runtime_success(
        const action_definition& action,
        bool ninja_tool)
{
    battle_session<8> session;
    grid_map<16, 16> map;
    assert(map.set_active_dimensions(16, 16));
    for(int y = 0; y < 16; ++y)
    {
        for(int x = 0; x < 16; ++x)
        {
            map.set_cost({ x, y }, 1);
        }
    }
    assert(session.configure_battlefield(map));
    assert(add_test_units(
            session,
            action,
            ninja_tool ?
                    static_cast<ninja_tool_id>(action.id) :
                    no_ninja_tool));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(1) ==
           battle_transition::action_draft_opened);

    grid_point target = {};
    if(! find_legal_target(session, action, target))
    {
        std::fprintf(
                stderr,
                "%s id=%u has no legal target: effect=%u target=%u "
                "distance=0x%02X area=0x%02X\n",
                ninja_tool ? "ninja-tool" : "active-action",
                static_cast<unsigned>(action.id),
                static_cast<unsigned>(action.effect.code),
                static_cast<unsigned>(action.target.kind),
                static_cast<unsigned>(
                        action.range.distance_and_line_flags),
                static_cast<unsigned>(
                        action.range.area_range_and_shape_flags));
        assert(false);
    }

    const action_preview preview =
            battle_action_execution::preview(
                    session, action, target);
    assert(preview.legal());
    const effect_handler_kind handler =
            effect_resolver_registry::handler_for(
                    action.effect.code);
    deterministic_rng rng(
            static_cast<std::uint32_t>(action.id) + 1U);
    const action_result result =
            battle_action_execution::resolve(
                    session, action, target, rng);
    if(! result.success())
    {
        std::fprintf(
                stderr,
                "%s id=%u failed resolve: error=%u target=(%d,%d)\n",
                ninja_tool ? "ninja-tool" : "active-action",
                static_cast<unsigned>(action.id),
                static_cast<unsigned>(result.error),
                target.x,
                target.y);
        assert(false);
    }
    assert(session.lifecycle() ==
           battle_lifecycle::effects_resolved);
    assert(session.unit(1)->ledger.acted);
    switch(handler)
    {
    case effect_handler_kind::damage:
        assert(preview.total_damage > 0);
        assert(result.generated_hits > 0);
        assert(result.effective_hits > 0);
        assert(result.total_damage > 0);
        assert(result.damage_step_count > 0);
        break;
    case effect_handler_kind::summon:
    case effect_handler_kind::summon_variant:
        assert(result.summoned);
        assert(result.summon_count == 1);
        break;
    case effect_handler_kind::summon_pair:
        assert(result.summoned);
        assert(result.summon_count == 2);
        break;
    case effect_handler_kind::move:
        assert(result.moved);
        assert(
                result.movement_origin !=
                result.movement_destination);
        break;
    case effect_handler_kind::identity_transform:
        assert(result.identity_overridden);
        assert(
                result.identity_before !=
                result.identity_after);
        break;
    case effect_handler_kind::heal_percent:
        assert(preview.healing > 0);
        assert(result.total_healing > 0);
        break;
    case effect_handler_kind::status:
        assert(result.applied_status_count > 0);
        break;
    case effect_handler_kind::linked_cleanup:
        assert(
                ! session.unit(2)->active ||
                ! session.unit(3)->active ||
                ! session.unit(4)->active ||
                ! session.unit(5)->active ||
                ! session.unit(6)->active);
        break;
    case effect_handler_kind::restore_hp_and_chakra:
        assert(result.applied_status_count == 1);
        assert(result.total_healing > 0);
        assert(result.chakra_delta > 0);
        break;
    case effect_handler_kind::battlefield_object_type_1:
    case effect_handler_kind::battlefield_object_type_2:
        assert(
                result.battlefield_object_slot !=
                no_battlefield_object);
        break;
    case effect_handler_kind::chakra_restore:
    case effect_handler_kind::chakra_reduce:
        assert(result.chakra_delta != 0);
        break;
    case effect_handler_kind::reaction_state:
        assert(result.applied_status_count > 0);
        assert(result.reaction_state_changed);
        break;
    case effect_handler_kind::no_effect:
        assert(! ninja_tool);
        assert(action.id == 9);
        break;
    case effect_handler_kind::unimplemented:
        assert(false);
        break;
    }
    if(ninja_tool)
    {
        assert(session.unit(1)->equipped_tools[0] ==
               no_ninja_tool);
    }
}

}

int main()
{
    // This is a definition-level resolver sweep, so it deliberately
    // includes primary-template IDs independent of their learned,
    // unlocked-unlearned, or locked progression state. Natural
    // production reachability is guarded separately by the
    // fail-closed reachability manifest and scenario-loader tests.
    std::array<bool, active_action_definitions.size()>
            primary_template_action_ids = {};
    for(const unit_definition& definition :
            unit_definitions)
    {
        if(! definition.active)
        {
            continue;
        }
        for(const action_slot_definition& slot :
                definition.primary_slots)
        {
            if(slot.action != 0)
            {
                primary_template_action_ids[slot.action] = true;
            }
        }
    }

    int active_action_count = 0;
    for(std::size_t index = 1;
            index < active_action_definitions.size();
            ++index)
    {
        if(! primary_template_action_ids[index])
        {
            continue;
        }
        const action_definition& action =
                active_action_definitions[index];
        assert(action.effect.code != 0);
        ++active_action_count;
        require_runtime_success(action, false);
    }
    assert(active_action_count == 76);

    // Mist Concealment is absent from base unit templates, but battle
    // 8 formation records naturally supply it at level 3. Its exact
    // production catalog route is covered by the scenario-loader
    // integration test; this sweep covers the shared resolver.
    assert(! primary_template_action_ids[62]);
    require_runtime_success(
            active_action_definitions[62], false);

    int ninja_tool_count = 0;
    for(std::size_t index = 1;
            index < ninja_tool_action_definitions.size();
            ++index)
    {
        const action_definition action =
                ninja_tool_action_for_slot(
                        static_cast<ninja_tool_id>(index),
                        0);
        assert(action.effect.code != 0);
        ++ninja_tool_count;
        require_runtime_success(action, true);
    }
    assert(ninja_tool_count == 93);
}
