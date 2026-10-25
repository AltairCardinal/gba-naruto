// Y1 stack-fix size probe: dump sizeof + every member offset of
// battle_scene_presentation_event so HEAD and the working tree can be
// compared byte-for-byte.
//
// Build twice:
//   g++ -std=c++23 -I <shadow> -I <real include> y1_size_probe.cpp
// The <shadow> dir (if any) must contain konoha/battle_scene_presentation_event.h
// and must come first on the include path.

#include "konoha/battle_scene_presentation_event.h"
#include "konoha/battle_scene_controller.h"

#include <cstddef>
#include <cstdio>

using konoha::battle_scene_presentation_event;
#ifdef Y1_HAS_SETTLEMENT
using konoha::battle_settlement_presentation;
#endif

#define OFF(field) \
    std::printf("%-40s %4zu %4zu\n", #field, offsetof(battle_scene_presentation_event, field), sizeof(((battle_scene_presentation_event*)0)->field))

int main()
{
    std::printf("sizeof(battle_scene_presentation_event) = %zu\n",
                sizeof(battle_scene_presentation_event));
    std::printf("alignof(battle_scene_presentation_event) = %zu\n",
                alignof(battle_scene_presentation_event));
#ifdef Y1_HAS_SETTLEMENT
    std::printf("sizeof(battle_settlement_presentation) = %zu\n",
                sizeof(battle_settlement_presentation));
    std::printf("alignof(battle_settlement_presentation) = %zu\n",
                alignof(battle_settlement_presentation));
#else
    std::printf("sizeof(battle_settlement_presentation) = n/a (HEAD)\n");
#endif
    std::printf("---- member offsets ----\n");
    OFF(valid);
    OFF(has_action);
    OFF(actor_id);
    OFF(action_id);
    OFF(origin);
    OFF(destination);
    OFF(target);
    OFF(ninja_tool);
    OFF(animation_family);
    OFF(targets_opponent);
    OFF(target_id);
    OFF(actor_lunges);
    OFF(affected_unit_ids);
    OFF(affected_character_ids);
    OFF(affected_unit_count);
    OFF(affected_units_truncated);
    OFF(impact_count);
    OFF(has_combatant_vitals);
    OFF(actor_hp);
    OFF(actor_max_hp);
    OFF(target_hp_before);
    OFF(target_hp_after);
    OFF(target_max_hp);
    OFF(has_battlefield_object);
    OFF(battlefield_object_kind);
    OFF(battlefield_object_slot);
    OFF(battlefield_object_damage);
    OFF(battlefield_object_tile_index_start);
    OFF(battlefield_object_tile_index_end);
    OFF(battlefield_object_palette_bank_start);
    OFF(battlefield_object_palette_bank_end);
    OFF(battlefield_object_effect_sequence);
    OFF(has_resource);
    OFF(resource_type);
    OFF(resource_amount);
    OFF(resource_hp_delta);
    OFF(resource_chakra_delta);
    OFF(has_side_start_passive);
    OFF(passive);
    OFF(passive_kind);
    OFF(passive_status_code);
    OFF(passive_status_value);
    OFF(passive_status_duration_ticks);
    OFF(passive_status_applied);
    OFF(passive_secondary_status_code);
    OFF(passive_secondary_status_value);
    OFF(passive_secondary_status_duration_ticks);
    OFF(passive_secondary_status_applied);
    OFF(special_combination);
    OFF(direct_attack);
    OFF(capture_count);
    std::printf("---- other stack-resident sizes ----\n");
    std::printf("%-40s %4zu\n", "sizeof(battle_scene_snapshot<12>)",
                sizeof(konoha::battle_scene_snapshot<12>));
    std::printf("%-40s %4zu\n", "sizeof(battle_scene_control_result)",
                sizeof(konoha::battle_scene_control_result));
    std::printf("%-40s %4zu\n",
                "sizeof(battle_player_action_flow_result)",
                sizeof(konoha::battle_player_action_flow_result));
    std::printf("%-40s %4zu\n", "sizeof(battle_scene_unit_view)",
                sizeof(konoha::battle_scene_unit_view));
    return 0;
}
