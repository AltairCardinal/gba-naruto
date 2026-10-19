#include "konoha/battle_action_execution.h"
#include "konoha/generated_battle_action_content.h"

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>

using namespace konoha;

namespace
{

enum class action_source : std::uint8_t
{
    active,
    ninja_tool,
};

enum class affected_unit : std::uint8_t
{
    source,
    ally,
    opponent,
};

struct status_action_expectation
{
    action_source source;
    std::uint8_t action_id;
    affected_unit affected;
    std::uint8_t status_code;
    std::uint8_t potency;
    std::uint8_t duration_ticks;
};

constexpr std::array<status_action_expectation, 33>
        expectations = {{
            { action_source::active, 14, affected_unit::source, 0x1E, 25, 0 },
            { action_source::active, 25, affected_unit::source, 0x1E, 15, 0 },
            { action_source::active, 29, affected_unit::source, 0x1E, 25, 0 },
            { action_source::active, 31, affected_unit::opponent, 0x21, 10, 6 },
            { action_source::active, 37, affected_unit::source, 0x12, 20, 8 },
            { action_source::active, 38, affected_unit::source, 0x12, 20, 8 },

            { action_source::ninja_tool, 55, affected_unit::opponent, 0x1F, 25, 8 },
            { action_source::ninja_tool, 56, affected_unit::opponent, 0x1F, 50, 8 },
            { action_source::ninja_tool, 57, affected_unit::opponent, 0x1F, 75, 8 },
            { action_source::ninja_tool, 58, affected_unit::opponent, 0x21, 25, 8 },
            { action_source::ninja_tool, 59, affected_unit::opponent, 0x21, 50, 8 },
            { action_source::ninja_tool, 60, affected_unit::opponent, 0x21, 75, 8 },
            { action_source::ninja_tool, 61, affected_unit::opponent, 0x23, 25, 8 },
            { action_source::ninja_tool, 62, affected_unit::opponent, 0x23, 50, 8 },
            { action_source::ninja_tool, 63, affected_unit::opponent, 0x23, 75, 8 },
            { action_source::ninja_tool, 64, affected_unit::opponent, 0x25, 1, 8 },
            { action_source::ninja_tool, 65, affected_unit::opponent, 0x25, 2, 8 },
            { action_source::ninja_tool, 66, affected_unit::opponent, 0x25, 3, 8 },

            { action_source::ninja_tool, 79, affected_unit::ally, 0x1E, 10, 8 },
            { action_source::ninja_tool, 80, affected_unit::ally, 0x1E, 30, 8 },
            { action_source::ninja_tool, 81, affected_unit::ally, 0x1E, 50, 8 },
            { action_source::ninja_tool, 82, affected_unit::ally, 0x20, 10, 8 },
            { action_source::ninja_tool, 83, affected_unit::ally, 0x20, 30, 8 },
            { action_source::ninja_tool, 84, affected_unit::ally, 0x20, 50, 8 },
            { action_source::ninja_tool, 85, affected_unit::ally, 0x22, 10, 8 },
            { action_source::ninja_tool, 86, affected_unit::ally, 0x22, 30, 8 },
            { action_source::ninja_tool, 87, affected_unit::ally, 0x22, 50, 8 },
            { action_source::ninja_tool, 88, affected_unit::ally, 0x24, 1, 8 },
            { action_source::ninja_tool, 89, affected_unit::ally, 0x24, 2, 8 },
            { action_source::ninja_tool, 90, affected_unit::ally, 0x24, 3, 8 },
            { action_source::ninja_tool, 91, affected_unit::ally, 0x26, 10, 8 },
            { action_source::ninja_tool, 92, affected_unit::ally, 0x26, 30, 8 },
            { action_source::ninja_tool, 93, affected_unit::ally, 0x26, 50, 8 },
        }};

constexpr battle_unit_id source_id = 1;
constexpr battle_unit_id ally_id = 2;
constexpr battle_unit_id opponent_id = 3;

battle_unit_instance make_unit(
        battle_unit_id id,
        battle_side side,
        grid_point position)
{
    battle_unit_instance result = {
        id,
        side,
        side == battle_side::player ?
                battle_control::player :
                battle_control::ai,
        position,
        battle_facing::down,
        100,
        200,
        100,
        100,
        4,
        true,
        {},
    };
    result.attack = 40;
    result.defense = 50;
    result.agility = 60;
    result.hand_seals = 20;
    battle_attribute_system::initialize_base(result);
    return result;
}

const battle_unit_instance& affected(
        const battle_session<3>& session,
        affected_unit unit)
{
    const battle_unit_id id =
            unit == affected_unit::source ?
                    source_id :
                    (unit == affected_unit::ally ?
                             ally_id :
                             opponent_id);
    const battle_unit_instance* result = session.unit(id);
    assert(result);
    return *result;
}

grid_point target_position(affected_unit unit)
{
    if(unit == affected_unit::source)
    {
        return { 4, 4 };
    }
    if(unit == affected_unit::ally)
    {
        return { 4, 5 };
    }
    return { 4, 3 };
}

int increased_percent(int value, int potency, int maximum)
{
    const int result = value + value * potency / 100;
    return result > maximum ? maximum : result;
}

int decreased_percent(int value, int potency)
{
    const int result = value - value * potency / 100;
    return result < 0 ? 0 : result;
}

void assert_status(
        const battle_unit_instance& unit,
        std::uint8_t code,
        std::uint8_t potency,
        std::uint8_t duration_ticks)
{
    const std::uint8_t slot = unit.statuses.find(code);
    assert(slot != no_status_slot);
    const status_record* status = unit.statuses.active(slot);
    assert(status);
    assert(status->code() == code);
    assert(status->value_u16 == potency);
    assert(status->duration_ticks == duration_ticks);
}

void assert_attributes(
        const battle_unit_instance& unit,
        std::uint8_t code,
        std::uint8_t potency)
{
    int expected_attack = 40;
    int expected_defense = 50;
    int expected_agility = 60;
    int expected_movement = 4;
    int expected_max_hp = 200;

    switch(code)
    {
    case 0x12:
    case 0x1E:
        expected_attack =
                increased_percent(40, potency, 99);
        break;
    case 0x1F:
        expected_attack =
                decreased_percent(40, potency);
        break;
    case 0x20:
        expected_defense =
                increased_percent(50, potency, 99);
        break;
    case 0x21:
        expected_defense =
                decreased_percent(50, potency);
        break;
    case 0x22:
        expected_agility =
                increased_percent(60, potency, 99);
        break;
    case 0x23:
        expected_agility =
                decreased_percent(60, potency);
        break;
    case 0x24:
        expected_movement = 4 + potency;
        break;
    case 0x25:
        expected_movement = 4 - potency;
        break;
    case 0x26:
        expected_attack =
                increased_percent(40, potency, 99);
        expected_defense =
                increased_percent(50, potency, 99);
        expected_agility =
                increased_percent(60, potency, 99);
        expected_max_hp =
                increased_percent(200, potency, 999);
        break;
    default:
        assert(false);
    }

    assert(unit.attack == expected_attack);
    assert(unit.defense == expected_defense);
    assert(unit.agility == expected_agility);
    assert(unit.move_range == expected_movement);
    assert(unit.max_hp == expected_max_hp);
    if(code == 0x26)
    {
        assert(unit.hp == 100 + expected_max_hp - 200);
    }
    else
    {
        assert(unit.hp == 100);
    }
}

void assert_expiry(
        const battle_unit_instance& applied,
        std::uint8_t code,
        std::uint8_t duration_ticks)
{
    battle_unit_instance ticking = applied;
    const std::array<std::uint8_t, 4> compound_codes = {
        0x1E, 0x20, 0x22, 0x1B,
    };
    if(duration_ticks == 0)
    {
        for(int tick = 0; tick < 20; ++tick)
        {
            assert(ticking.statuses.tick_side_end() == 0);
        }
        assert(ticking.statuses.find(code) != no_status_slot);
        return;
    }

    for(int tick = 1; tick < duration_ticks; ++tick)
    {
        assert(ticking.statuses.tick_side_end() == 0);
        if(code == 0x26)
        {
            for(const std::uint8_t compound :
                    compound_codes)
            {
                assert(ticking.statuses.find(compound) !=
                       no_status_slot);
            }
        }
        else
        {
            assert(ticking.statuses.find(code) !=
                   no_status_slot);
        }
    }

    const int expected_removed =
            code == 0x26 ? 4 : 1;
    assert(ticking.statuses.tick_side_end() ==
           expected_removed);
    battle_attribute_system::recompute(ticking);
    assert(ticking.attack == 40);
    assert(ticking.defense == 50);
    assert(ticking.agility == 60);
    assert(ticking.move_range == 4);
    assert(ticking.max_hp == 200);
    const int expected_hp =
            code == 0x26 ?
                    (applied.hp > 200 ?
                             200 :
                             applied.hp) :
                    100;
    assert(ticking.hp == expected_hp);
}

void verify(const status_action_expectation& expected)
{
    battle_session<3> session;
    grid_map<8, 8> map;
    assert(map.set_active_dimensions(8, 8));
    for(int y = 0; y < 8; ++y)
    {
        for(int x = 0; x < 8; ++x)
        {
            map.set_cost({ x, y }, 1);
        }
    }
    assert(session.configure_battlefield(map));

    battle_unit_instance source =
            make_unit(
                    source_id,
                    battle_side::player,
                    { 4, 4 });
    if(expected.source == action_source::ninja_tool)
    {
        source.equipped_tools[0] =
                expected.action_id;
    }
    assert(session.add_unit(source));
    assert(session.add_unit(
            make_unit(
                    ally_id,
                    battle_side::player,
                    { 4, 5 })));
    assert(session.add_unit(
            make_unit(
                    opponent_id,
                    battle_side::enemy,
                    { 4, 3 })));
    assert(session.start_round() ==
           battle_transition::unit_selection_opened);
    assert(session.select_unit(source_id) ==
           battle_transition::action_draft_opened);

    const action_definition action =
            expected.source == action_source::active ?
                    active_action_definitions[
                            expected.action_id] :
                    ninja_tool_action_for_slot(
                            expected.action_id, 0);
    assert(action.effect.code ==
           expected.status_code);
    assert(action.effect.potency ==
           expected.potency);
    assert(encode_status_duration_ticks(
                   action.effect.duration_turns) ==
           expected.duration_ticks);

    const grid_point target =
            target_position(expected.affected);
    assert(battle_action_execution::preview(
                   session, action, target).legal());
    deterministic_rng rng(expected.action_id + 1U);
    const action_result result =
            battle_action_execution::resolve(
                    session, action, target, rng);
    assert(result.success());

    const battle_unit_instance& changed =
            affected(session, expected.affected);
    if(expected.status_code == 0x26)
    {
        assert(result.applied_status_count == 4);
        assert_status(
                changed, 0x1E,
                expected.potency,
                expected.duration_ticks);
        assert_status(
                changed, 0x20,
                expected.potency,
                expected.duration_ticks);
        assert_status(
                changed, 0x22,
                expected.potency,
                expected.duration_ticks);
        assert_status(
                changed, 0x1B,
                expected.potency,
                expected.duration_ticks);
        assert(changed.statuses.find(0x26) ==
               no_status_slot);
    }
    else
    {
        assert(result.applied_status_count == 1);
        assert_status(
                changed,
                expected.status_code,
                expected.potency,
                expected.duration_ticks);
    }
    assert_attributes(
            changed,
            expected.status_code,
            expected.potency);
    assert_expiry(
            changed,
            expected.status_code,
            expected.duration_ticks);
    if(expected.source == action_source::ninja_tool)
    {
        assert(session.unit(source_id)->
                       equipped_tools[0] ==
               no_ninja_tool);
    }
}

}

int main()
{
    for(const status_action_expectation& expected :
            expectations)
    {
        verify(expected);
    }
}
