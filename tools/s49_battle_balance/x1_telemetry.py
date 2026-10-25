#!/usr/bin/env python3
"""X1 (wave 12): read the remake ROM's battle telemetry out of EWRAM.

The remake's runtime scene publishes one ``battle_runtime_scene_telemetry``
struct (``konoha_battle_runtime_telemetry``) that carries the battle state
machine's own view of the world: the phase, the round, the selected unit,
the cursor, the command, the action index, every unit's position and hit
points, and the battle's outcome.

That struct is what a **closed loop** driver needs: instead of replaying a
blind key script (which goes out of step on the very first presentation),
the driver reads the phase and decides what to press.

The struct's address moves between builds, so it is **found by its magic**
(``0x4B42544C`` = "KBTL") rather than hard coded.

Usage::

    python tools/s49_battle_balance/x1_telemetry.py \\
        --rom build/s49-w1/rom-before.gba
"""

from __future__ import annotations

import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import w1_probe as probe_module  # noqa: E402

MAGIC = 0x4B42544C

# The field order of ``battle_runtime_scene_telemetry``
# (butano-sequel/game/include/konoha/battle_runtime_scene.h).  Every member
# is a 32 bit word, so the word index *is* the byte offset / 4.
FIELDS = [
    "magic", "battle_id", "phase", "round", "current_side", "selected_unit",
    "active_unit_count", "unit_count", "selected_command", "player_completed",
    "enemy_completed", "scene_frame", "cursor_x", "cursor_y",
    "last_control_error", "last_player_error", "render_stage",
    "presentation_busy", "selected_character_id", "action_count",
    "action_index", "selected_action_id", "selected_action_error",
    "last_resolved_action_id", "background_chunk_index",
    "background_chunk_count", "selected_action_kind", "selected_action_tool_slot",
    "result_participant_count", "result_mission_experience",
    "result_battle_experience", "result_round_bonus_experience",
    "result_total_experience", "result_level_before", "result_level_after",
    "result_experience_after", "result_hp_growth", "script_phase",
    "script_selector", "script_command_index", "script_text_address",
    "script_message_window_visible", "script_portrait_0_visible",
    "script_portrait_0_focused", "script_portrait_0_id",
    "script_portrait_0_expression", "script_portrait_0_motion",
    "script_portrait_1_visible", "script_portrait_1_focused",
    "script_portrait_1_id", "script_portrait_1_expression",
    "script_portrait_1_motion", "presentation_resource_resolved",
    "presentation_resource_type", "presentation_resource_amount",
    "presentation_resource_hp_delta", "presentation_resource_chakra_delta",
    "ai_secondary_planned", "ai_defense_kind", "ai_defense_action_id",
    "ai_defense_tool_slot", "ai_defense_score", "presentation_passive_resolved",
    "presentation_passive_id", "presentation_passive_kind",
    "presentation_passive_hp_delta", "presentation_passive_chakra_delta",
    "presentation_passive_status_code", "presentation_passive_status_value",
    "presentation_passive_status_duration_ticks",
    # Z1 (wave 14): this field was missing from the list, so **every field
    # from here on was read one word too early** -- the unit positions, the
    # hit points and ``condition_outcome`` included.  The closed-loop driver
    # picked its targets from the shifted values.
    "presentation_passive_status_applied",
    "battlefield_object_count",
    "presentation_battlefield_object", "presentation_battlefield_object_kind",
    "presentation_battlefield_object_slot", "presentation_battlefield_object_damage",
    "cursor_unit_id", "cursor_unit_attack", "cursor_unit_defense",
    "cursor_unit_agility", "cursor_unit_status_count", "cursor_unit_active",
    "cursor_unit_hp", "selected_action_level", "training_character_id",
    "training_action_id", "training_action_level", "training_points",
    "training_error", "training_entry_kind", "presentation_combat_schema_version",
    "presentation_combat_stage", "presentation_combat_stage_frame",
    "presentation_combat_impact_index", "presentation_combat_tracks",
    "presentation_combat_resource", "selected_unit_x", "selected_unit_y",
    "first_active_enemy_x", "first_active_enemy_y",
    "selected_action_effect_code", "selected_action_target_kind",
    "selected_unit_chakra", "move_preview_x", "move_preview_y",
]
for _index in range(12):
    FIELDS.append(f"unit_character_ids[{_index}]")
for _index in range(12):
    FIELDS.append(f"unit_active[{_index}]")
for _index in range(12):
    FIELDS.append(f"unit_x[{_index}]")
for _index in range(12):
    FIELDS.append(f"unit_y[{_index}]")
FIELDS.extend([
    "selected_unit_hp", "selected_unit_max_hp",
])
for _index in range(12):
    FIELDS.append(f"unit_hp[{_index}]")
for _index in range(12):
    FIELDS.append(f"unit_chakra[{_index}]")
for _index in range(12):
    FIELDS.append(f"unit_side[{_index}]")
for _index in range(12):
    FIELDS.append(f"unit_control[{_index}]")
FIELDS.extend([
    "resource_preview_amount", "resource_preview_maximum_amount",
    "condition_outcome", "training_detail_page", "map_movement_active",
    "map_movement_sequence", "map_movement_elapsed", "map_movement_offset_x",
    "map_movement_offset_y", "map_visual_facing", "map_graphics_frame",
    "pickup_sequence", "material_3", "material_4",
])

WORD_COUNT = len(FIELDS)
BYTE_COUNT = WORD_COUNT * 4

# The scene's own phase enum (battle_scene_controller.h).  The two settlement
# phases were appended at the end, so the old ordinals are stable.
PHASES = [
    "preparation", "unit_selection", "move_selection", "command_selection",
    "chakra_selection", "rest_confirmation", "action_selection",
    "combination_decision", "target_selection", "facing_selection",
    "defense_decision", "defense_selection", "enemy_turn", "outcome",
    "result", "level_up", "complete", "error", "script_blocked", "training",
    "target_confirmation", "end_confirmation", "target_preview",
    "turn_banner", "post_battle_dialogue", "task_menu",
]
PHASE_INDEX = {name: index for index, name in enumerate(PHASES)}


def phase_name(value: int) -> str:
    if 0 <= value < len(PHASES):
        return PHASES[value]
    return f"phase_{value}"


class Telemetry:
    """Reads the battle telemetry struct out of the emulated EWRAM."""

    def __init__(self, probe: probe_module.Probe) -> None:
        self.probe = probe
        self.address: int | None = None

    # ------------------------------------------------------------- locating
    def _dump(self, address: int, length: int) -> bytes:
        # The probe's `dump` parses its address as a decimal integer, so the
        # address is written in base ten.
        lines = self.probe.run(f"dump {address} {length}")
        hex_text = "".join(line for line in lines
                           if not line.startswith("DUMP") and line != "ENDDUMP")
        return bytes.fromhex(hex_text)

    def locate(self, verbose: bool = False) -> int:
        """Find the telemetry struct by its magic and remember its address."""
        if self.address is not None:
            return self.address
        magic_bytes = struct.pack("<I", MAGIC)
        # EWRAM is 0x02000000..0x0203FFFF.
        chunk = 0x8000
        for base in range(0x02000000, 0x02040000, chunk):
            blob = self._dump(base, chunk)
            offset = blob.find(magic_bytes)
            while offset >= 0:
                # The struct is 4 byte aligned, so a hit on an odd byte is
                # part of some other word.
                if offset % 4 == 0:
                    self.address = base + offset
                    if verbose:
                        print(f"telemetry at 0x{self.address:08X}")
                    return self.address
                offset = blob.find(magic_bytes, offset + 1)
        raise RuntimeError("the battle telemetry struct was not found in EWRAM")

    # -------------------------------------------------------------- reading
    def read(self) -> dict[str, int]:
        address = self.locate()
        blob = self._dump(address, BYTE_COUNT)
        words = struct.unpack(f"<{WORD_COUNT}I", blob)
        return dict(zip(FIELDS, words))

    def units(self, values: dict[str, int]) -> list[dict[str, int]]:
        count = min(values["unit_count"], 12)
        return [{
            "index": index,
            "character_id": values[f"unit_character_ids[{index}]"],
            "active": values[f"unit_active[{index}]"],
            "x": values[f"unit_x[{index}]"],
            "y": values[f"unit_y[{index}]"],
            "hp": values[f"unit_hp[{index}]"],
            "chakra": values[f"unit_chakra[{index}]"],
            "side": values[f"unit_side[{index}]"],
        } for index in range(count)]


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=HERE.parents[1] / "build" / "mgba-probe-x1" /
                        "mgba-probe.exe")
    parser.add_argument("--frames", type=int, default=300)
    args = parser.parse_args(argv)
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.run(f"frames {args.frames} 0x00000000")
        telemetry = Telemetry(probe)
        values = telemetry.read()
        print(f"address 0x{telemetry.address:08X}")
        for name in ("magic", "battle_id", "phase", "round", "current_side",
                     "selected_unit", "unit_count", "active_unit_count",
                     "selected_command", "cursor_x", "cursor_y",
                     "presentation_busy", "map_movement_active",
                     "condition_outcome", "script_phase", "scene_frame"):
            print(f"{name:28s} {values[name]}")
        for unit in telemetry.units(values):
            print(unit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
