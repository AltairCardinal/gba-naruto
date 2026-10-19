#include "konoha/battle_content_catalog.h"
#include "konoha/generated_battle_action_content.h"
#include "konoha/generated_battle_condition_content.h"
#include "konoha/generated_battle_map_content.h"
#include "konoha/generated_battle_passive_content.h"
#include "konoha/generated_battle_scenario_content.h"
#include "konoha/generated_battle_unit_content.h"

#include <cassert>

using namespace konoha;

namespace
{

template<
        std::size_t ScenarioCount,
        std::size_t CellCount,
        std::size_t UnitCount,
        std::size_t ActiveActionCount,
        std::size_t NinjaToolCount,
        std::size_t PassiveCount>
battle_content_catalog_result validate(
        const std::array<battle_scenario_definition, ScenarioCount>&
                scenarios,
        const std::array<battle_map_definition, ScenarioCount>& maps,
        const std::array<battle_map_cell, CellCount>& cells,
        const std::array<
                std::array<battle_condition_variant, 3>,
                ScenarioCount>& conditions,
        const std::array<unit_definition, UnitCount>& units,
        const std::array<action_definition, ActiveActionCount>&
                active_actions,
        const std::array<action_definition, NinjaToolCount>&
                ninja_tools,
        const std::array<passive_definition, PassiveCount>& passives)
{
    return validate_battle_content_catalog(
            scenarios,
            maps,
            cells,
            conditions,
            units,
            active_actions,
            ninja_tools,
            passives);
}

}

int main()
{
    const battle_content_catalog_result generated =
            validate_generated_battle_content_catalog();
    assert(generated.success());
    assert(generated.scenario_count == 47);
    assert(generated.variant_count == 141);
    assert(generated.playable_variant_count == 85);
    assert(generated.deployment_variant_count == 41);
    assert(generated.fixed_unit_record_count == 329);
    assert(generated.placeholder_record_count == 147);
    assert(generated.active_character_count == 62);
    assert(generated.active_action_count == 82);
    assert(generated.ninja_tool_action_count == 93);
    assert(generated.passive_count == 44);

    const battle_content_entry battle_09 =
            generated_battle_content_entry(9, 0);
    assert(battle_09.valid());
    assert(battle_09.kind ==
           battle_content_entry_kind::fixed_roster);
    assert(battle_09.scenario->battle_id == 9);
    assert(battle_09.map->battle_id == 9);
    assert(battle_09.conditions ==
           &battle_condition_variants[9][0]);

    const battle_content_entry battle_32 =
            generated_battle_content_entry(32, 0);
    assert(battle_32.valid());
    assert(battle_32.kind ==
           battle_content_entry_kind::deployment_required);

    const battle_content_entry empty =
            generated_battle_content_entry(0, 0);
    assert(empty.valid());
    assert(empty.kind == battle_content_entry_kind::empty);
    assert(! generated_battle_content_entry(-1, 0).valid());
    assert(! generated_battle_content_entry(47, 0).valid());
    assert(! generated_battle_content_entry(9, -1).valid());
    assert(! generated_battle_content_entry(9, 3).valid());

    auto bad_ids = battle_map_definitions;
    bad_ids[3].battle_id = 2;
    battle_content_catalog_result invalid = validate(
            battle_scenario_definitions,
            bad_ids,
            battle_map_cells,
            battle_condition_variants,
            unit_definitions,
            active_action_definitions,
            ninja_tool_action_definitions,
            passive_definitions);
    assert(invalid.error ==
           battle_content_catalog_error::invalid_battle_id);
    assert(invalid.battle_id == 3);

    auto bad_slice = battle_map_definitions;
    bad_slice[2].cell_offset =
            static_cast<std::uint16_t>(
                    battle_map_cells.size());
    invalid = validate(
            battle_scenario_definitions,
            bad_slice,
            battle_map_cells,
            battle_condition_variants,
            unit_definitions,
            active_action_definitions,
            ninja_tool_action_definitions,
            passive_definitions);
    assert(invalid.error ==
           battle_content_catalog_error::
                   map_content_out_of_bounds);
    assert(invalid.battle_id == 2);

    auto blocked_cells = battle_map_cells;
    const battle_scenario_unit_slot& first_09 =
            battle_scenario_definitions[9].variants[0][0];
    const battle_map_definition& map_09 =
            battle_map_definitions[9];
    blocked_cells[
            map_09.cell_offset +
            first_09.position.y * map_09.width +
            first_09.position.x].raw_attributes |=
                    battle_map_fully_closed;
    invalid = validate(
            battle_scenario_definitions,
            battle_map_definitions,
            blocked_cells,
            battle_condition_variants,
            unit_definitions,
            active_action_definitions,
            ninja_tool_action_definitions,
            passive_definitions);
    assert(invalid.error ==
           battle_content_catalog_error::
                   unit_on_blocked_cell);
    assert(invalid.battle_id == 9);
    assert(invalid.variant == 0);
    assert(invalid.slot == 0);

    auto duplicate_position = battle_scenario_definitions;
    duplicate_position[9].variants[0][1].position =
            duplicate_position[9].variants[0][0].position;
    invalid = validate(
            duplicate_position,
            battle_map_definitions,
            battle_map_cells,
            battle_condition_variants,
            unit_definitions,
            active_action_definitions,
            ninja_tool_action_definitions,
            passive_definitions);
    assert(invalid.error ==
           battle_content_catalog_error::
                   duplicate_unit_position);
    assert(invalid.battle_id == 9);
    assert(invalid.variant == 0);
    assert(invalid.slot == 1);

    auto invalid_character = battle_scenario_definitions;
    invalid_character[9].variants[0][0].selector = 63;
    invalid = validate(
            invalid_character,
            battle_map_definitions,
            battle_map_cells,
            battle_condition_variants,
            unit_definitions,
            active_action_definitions,
            ninja_tool_action_definitions,
            passive_definitions);
    assert(invalid.error ==
           battle_content_catalog_error::invalid_character);
    assert(invalid.battle_id == 9);

    auto invalid_action = unit_definitions;
    invalid_action[1].primary_slots[0].action =
            static_cast<ability_id>(
                    active_action_definitions.size());
    invalid = validate(
            battle_scenario_definitions,
            battle_map_definitions,
            battle_map_cells,
            battle_condition_variants,
            invalid_action,
            active_action_definitions,
            ninja_tool_action_definitions,
            passive_definitions);
    assert(invalid.error ==
           battle_content_catalog_error::
                   invalid_active_action);
    assert(invalid.character_id == 1);
    assert(invalid.slot == 0);

    auto invalid_passive = unit_definitions;
    invalid_passive[1].secondary_slots[0].action =
            static_cast<ability_id>(
                    passive_definitions.size());
    invalid = validate(
            battle_scenario_definitions,
            battle_map_definitions,
            battle_map_cells,
            battle_condition_variants,
            invalid_passive,
            active_action_definitions,
            ninja_tool_action_definitions,
            passive_definitions);
    assert(invalid.error ==
           battle_content_catalog_error::invalid_passive);
    assert(invalid.character_id == 1);
    assert(invalid.slot == 0);

    auto unsupported_conditions =
            battle_condition_variants;
    unsupported_conditions[9][0].win[0].type =
            battle_condition_type::unused_4;
    invalid = validate(
            battle_scenario_definitions,
            battle_map_definitions,
            battle_map_cells,
            unsupported_conditions,
            unit_definitions,
            active_action_definitions,
            ninja_tool_action_definitions,
            passive_definitions);
    assert(invalid.error ==
           battle_content_catalog_error::
                   unsupported_condition);
    assert(invalid.battle_id == 9);
    assert(invalid.variant == 0);
    assert(invalid.slot == 0);
}
