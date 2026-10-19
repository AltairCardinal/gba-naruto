#include "konoha/battle_action_catalog.h"
#include "konoha/battle_action_system.h"
#include "konoha/generated_battle_passive_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    battle_passive_state physical;
    assert(physical.set_slot(0, 36, 1));  // target 14: +10%
    assert(physical.set_slot(1, 10, 1));  // target 13: +2
    const action_definition physical_attack =
            apply_persistent_passive_action_modifiers(
                    active_action_definitions[5],
                    physical,
                    passive_definitions);
    assert(physical_attack.effect.potency == 13);

    action_definition excluded_effect =
            active_action_definitions[5];
    excluded_effect.effect.code = 0x21;
    assert(
            apply_persistent_passive_action_modifiers(
                    excluded_effect,
                    physical,
                    passive_definitions)
                    .effect.potency ==
            excluded_effect.effect.potency);

    action_definition effect_0a =
            active_action_definitions[14];
    effect_0a.effect.code = 0x0A;
    const action_definition effect_0a_modified =
            apply_persistent_passive_action_modifiers(
                    effect_0a,
                    physical,
                    passive_definitions);
    assert(
            effect_0a_modified.effect.potency ==
            effect_0a.effect.potency +
                    effect_0a.effect.potency / 10 +
                    2);

    battle_passive_state chakra;
    assert(chakra.set_slot(0, 31, 1));  // target 16: +10%
    assert(chakra.set_slot(1, 11, 1));  // target 15: +2
    const action_definition chakra_attack =
            apply_persistent_passive_action_modifiers(
                    active_action_definitions[16],
                    chakra,
                    passive_definitions);
    assert(chakra_attack.effect.potency == 18);

    battle_passive_state tools;
    assert(tools.set_slot(0, 12, 1));  // target 17: +2
    assert(tools.set_slot(1, 13, 1));  // target 18: +10
    assert(tools.set_slot(2, 14, 1));  // target 19: accuracy +5
    const action_definition damaging_tool =
            apply_persistent_passive_action_modifiers(
                    ninja_tool_action_for_slot(1, 0),
                    tools,
                    passive_definitions);
    assert(
            damaging_tool.effect.potency ==
            ninja_tool_action_definitions[1].effect.potency + 2);
    assert(
            damaging_tool.effect.success_rate_percent ==
            ninja_tool_action_definitions[1]
                            .effect.success_rate_percent +
                    5);
    const action_definition healing_tool =
            apply_persistent_passive_action_modifiers(
                    ninja_tool_action_for_slot(73, 1),
                    tools,
                    passive_definitions);
    assert(
            healing_tool.effect.potency ==
            ninja_tool_action_definitions[73].effect.potency + 10);
    assert(
            healing_tool.effect.success_rate_percent ==
            ninja_tool_action_definitions[73]
                            .effect.success_rate_percent +
                    5);

    battle_passive_state capped;
    assert(capped.set_slot(0, 32, 3));  // target 16: +40%
    assert(capped.set_slot(1, 11, 3));  // target 15: +4
    action_definition high_potency =
            active_action_definitions[16];
    high_potency.effect.potency = 98;
    assert(
            apply_persistent_passive_action_modifiers(
                    high_potency,
                    capped,
                    passive_definitions)
                    .effect.potency == 99);

    battle_unit_instance sasuke = instantiate_unit(
            unit_definitions[2],
            1,
            battle_side::player,
            battle_control::player,
            { 0, 0 },
            battle_facing::right);
    sasuke.passives = chakra;
    sasuke.equipped_tools[0] = 1;
    const battle_action_catalog_result catalog =
            battle_action_catalog::build(sasuke);
    assert(
            catalog.error ==
            battle_action_catalog_error::none);
    const battle_action_catalog_entry* catalog_action =
            catalog.find(
                    battle_action_source_kind::active_action,
                    16);
    assert(catalog_action);
    assert(catalog_action->action.effect.potency == 18);
    battle_unit_instance adjacent_target = instantiate_unit(
            unit_definitions[35],
            2,
            battle_side::enemy,
            battle_control::ai,
            { 1, 0 },
            battle_facing::left);
    adjacent_target.defense = 0;
    adjacent_target.base_defense = 0;
    const action_preview unmodified_preview =
            battle_action_resolver::preview_units(
                    sasuke,
                    &adjacent_target,
                    nullptr,
                    true,
                    action_definition_at_level(
                            active_action_definitions[16],
                            1),
                    adjacent_target.position);
    const action_preview catalog_preview =
            battle_action_resolver::preview_units(
                    sasuke,
                    &adjacent_target,
                    nullptr,
                    true,
                    catalog_action->action,
                    adjacent_target.position);
    assert(unmodified_preview.legal());
    assert(catalog_preview.legal());
    assert(
            catalog_preview.damage_per_hit >
            unmodified_preview.damage_per_hit);

    sasuke.passives = tools;
    const battle_action_catalog_result tool_catalog =
            battle_action_catalog::build(sasuke);
    const battle_action_catalog_entry* catalog_tool =
            tool_catalog.find(
                    battle_action_source_kind::ninja_tool,
                    1,
                    0);
    assert(catalog_tool);
    assert(
            catalog_tool->action.effect.potency ==
            ninja_tool_action_definitions[1].effect.potency + 2);
    assert(
            catalog_tool->action.effect.success_rate_percent ==
            ninja_tool_action_definitions[1]
                            .effect.success_rate_percent +
                    5);
}
