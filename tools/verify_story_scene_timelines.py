#!/usr/bin/env python3
"""Verify the ROM-bound 24-row story timeline export."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.export_story_scene_timelines import (
    CODE_SLICES,
    CONTROLLER_TIMING,
    OUTPUT_ARTIFACT,
    ROM_BASE,
    ROM_SHA256,
    _build_outputs,
)


CONFIG_IDS = [
    4, 10, 14, 24, 17, 18, 21, 25, 29, 28, 34, 76,
    30, 47, 48, 49, 51, 52, 58, 61, 74, 16, 77, 5,
]
SPECIAL_MODES = {
    4: "resource_swap_scroll",
    10: "alpha_enable_and_palette",
    17: "secondary_x_motion",
    61: "alpha_enable",
    74: "alpha_enable",
    16: "d_bg_flicker",
}
DESCRIPTOR_FLAGS = {
    4: "0x2408",
    10: "0x0806",
    17: "0x0004",
    61: "0x0A07",
    74: "0x0807",
    16: "0x0001",
}
EXPECTED_PHASES = [
    {
        "name": "installer_prelude",
        "start_wall_frame": 1,
        "end_wall_frame": 21,
    },
    {
        "name": "installer_internal_linked_updates",
        "start_wall_frame": 22,
        "end_wall_frame": 37,
        "linked_ticks": [1, 16],
    },
    {
        "name": "controller_linked_updates",
        "start_wall_frame": 38,
        "end_wall_frame": 127,
        "linked_ticks": [17, 106],
    },
    {
        "name": "linked_palette_grayscale_transform",
        "start_wall_frame": 128,
        "end_wall_frame": 143,
    },
    {
        "name": "story_overlay_visible",
        "start_wall_frame": 144,
        "end_wall_frame": 383,
    },
]
EXPECTED_OVERLAY = {
    "first_wall_frame": 144,
    "last_wall_frame": 383,
    "linked_state_frozen_at_tick": 106,
    "linked_palette_state": "grayscale_transform_complete",
}
ALLOWED_EVENTS = {
    "resource_swap_fade_start",
    "d_resources_installed_on_c_path",
    "resource_swap_fade_end",
    "d_bg_enabled",
    "d_bg_disabled",
    "b_palette_rotate_2_9",
    "c_path_scroll_override",
    "c_path_trailing_row_cleared",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _timeline_semantic_errors(
    timeline_name: str,
    payload: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != "story-scene-timeline-entry-v1":
        errors.append(f"{timeline_name} entry schema mismatch")
    if payload.get("phases") != EXPECTED_PHASES:
        errors.append(f"{timeline_name} phase schedule mismatch")
    if payload.get("overlay") != EXPECTED_OVERLAY:
        errors.append(f"{timeline_name} overlay metadata mismatch")

    ticks = payload.get("linked_ticks")
    if not isinstance(ticks, list):
        return errors + [f"{timeline_name} linked ticks are not a list"]
    expected_ticks = list(range(1, 107))
    if [state.get("linked_tick") for state in ticks] != expected_ticks:
        errors.append(f"{timeline_name} linked tick sequence mismatch")
    if [state.get("wall_frame") for state in ticks] != [
        21 + tick for tick in expected_ticks
    ]:
        errors.append(f"{timeline_name} wall frame sequence mismatch")
    if [state.get("task_counter") for state in ticks] != expected_ticks:
        errors.append(f"{timeline_name} task counter sequence mismatch")

    for index, state in enumerate(ticks):
        label = f"{timeline_name} tick {index + 1}"
        position = state.get("position_pixels")
        if (
            not isinstance(position, list)
            or len(position) != 2
            or not all(isinstance(value, int) for value in position)
        ):
            errors.append(f"{label} position schema mismatch")
        fixed = state.get("scroll_fixed_8_8")
        pixels = state.get("scroll_pixels")
        if (
            not isinstance(fixed, dict)
            or set(fixed) != {"B", "C", "D"}
            or not all(
                isinstance(value, list)
                and len(value) == 2
                and all(isinstance(component, int) for component in value)
                for value in fixed.values()
            )
        ):
            errors.append(f"{label} fixed scroll schema mismatch")
        elif (
            not isinstance(pixels, dict)
            or set(pixels) != {"B", "C", "D"}
            or any(
                pixels[layer]
                != [component // 256 for component in fixed[layer]]
                for layer in ("B", "C", "D")
            )
        ):
            errors.append(f"{label} pixel scroll mismatch")
        enabled = state.get("bg_enabled")
        if (
            not isinstance(enabled, dict)
            or set(enabled) != {"B", "C", "D"}
            or not all(isinstance(value, bool) for value in enabled.values())
        ):
            errors.append(f"{label} BG enable schema mismatch")
        if state.get("runtime_flags") not in {2, 3}:
            errors.append(f"{label} runtime flags mismatch")
        if state.get("c_display_resource") not in {"C", "D"}:
            errors.append(f"{label} C display resource mismatch")

        blend = state.get("blend")
        if not isinstance(blend, dict) or set(blend) != {
            "mode",
            "eva",
            "evb",
            "evy",
        }:
            errors.append(f"{label} blend schema mismatch")
        else:
            mode = blend["mode"]
            coefficients = (blend["eva"], blend["evb"], blend["evy"])
            if (
                mode not in {
                    "none",
                    "brightness_decrease",
                    "alpha_d_over_linked",
                }
                or not all(isinstance(value, int) for value in coefficients)
                or not 0 <= blend["eva"] <= 16
                or not 0 <= blend["evb"] <= 16
                or not 0 <= blend["evy"] <= 31
                or (
                    mode == "alpha_d_over_linked"
                    and blend["eva"] + blend["evb"] != 16
                )
            ):
                errors.append(f"{label} blend values mismatch")
        expected_rotation = (index + 2) // 2 % 8
        if state.get("b_palette_rotation") != expected_rotation:
            errors.append(f"{label} B palette rotation mismatch")
        brighten = state.get("d_palette_brighten")
        expected_brighten = (
            min(((index + 1) - 48) >> 3, 7) * 2
            if payload.get("config_id") == 10 and index + 1 >= 48
            else 0
        )
        if brighten != expected_brighten:
            errors.append(f"{label} D palette brighten mismatch")
        events = state.get("events")
        if (
            not isinstance(events, list)
            or not all(
                isinstance(event, str) and event in ALLOWED_EVENTS
                for event in events
            )
        ):
            errors.append(f"{label} event schema mismatch")
    return errors


def verify_story_scene_timelines(
    root: Path,
    artifact_dir: Path = OUTPUT_ARTIFACT,
) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact_dir = Path(artifact_dir)
    if not artifact_dir.is_absolute():
        artifact_dir = root / artifact_dir
    errors: list[str] = []
    manifest_path = artifact_dir / "manifest.json"
    try:
        actual_bytes = manifest_path.read_bytes()
        actual = json.loads(actual_bytes)
    except (OSError, json.JSONDecodeError) as error:
        return {
            "schema": "story-scene-timelines-verification-v1",
            "verified_timelines": 0,
            "errors": [f"cannot read manifest: {error}"],
        }

    try:
        rom = (root / "rom/base.gba").read_bytes()
        if _sha256(rom) != ROM_SHA256:
            errors.append("base ROM SHA-256 mismatch")
        for name, start, end, expected_hash in CODE_SLICES:
            actual_hash = _sha256(
                rom[start - ROM_BASE : end - ROM_BASE]
            )
            if actual_hash != expected_hash:
                errors.append(f"{name} code slice hash mismatch")
        expected, expected_files = _build_outputs(root)
        if actual != expected:
            errors.append("manifest does not match ROM-derived timelines")
    except (OSError, ValueError, KeyError, TypeError) as error:
        expected_files = {}
        errors.append(f"cannot rebuild ROM-derived timelines: {error}")

    timelines = actual.get("timelines")
    if actual.get("schema") != "story-scene-timelines-v1":
        errors.append("unexpected manifest schema")
    if actual.get("controller_timing") != CONTROLLER_TIMING:
        errors.append("controller timing mismatch")
    if not isinstance(timelines, list) or len(timelines) != 24:
        errors.append("manifest does not contain 24 timelines")
        timelines = []
    if [item.get("config_id") for item in timelines] != CONFIG_IDS:
        errors.append("story config sequence mismatch")
    observed_special = {
        item.get("config_id"): item.get("callback_mode")
        for item in timelines
        if item.get("callback_mode") != "common_only"
    }
    if observed_special != SPECIAL_MODES:
        errors.append("story callback family mapping mismatch")

    referenced_files = {"manifest.json"}
    verified = 0
    for story_index, item in enumerate(timelines):
        try:
            timeline_name = item["timeline_json"]
            contact_name = item["contact_sheet_png"]
            config_id = CONFIG_IDS[story_index]
            expected_mode = SPECIAL_MODES.get(config_id, "common_only")
            expected_previous = (
                CONFIG_IDS[story_index - 1] if story_index else config_id
            )
            if item.get("story_index") != story_index:
                errors.append(f"story {story_index} manifest index mismatch")
            if item.get("previous_config_id") != expected_previous:
                errors.append(
                    f"story {story_index} previous config mismatch"
                )
            if item.get("descriptor_flags") != DESCRIPTOR_FLAGS.get(
                config_id,
                "0x0000",
            ):
                errors.append(
                    f"story {story_index} descriptor flags mismatch"
                )
            if item.get("callback_mode") != expected_mode:
                errors.append(
                    f"story {story_index} callback mode mismatch"
                )
            expected_d_first = (
                0
                if config_id == 16
                else 32
                if config_id in {10, 61, 74}
                else None
            )
            if item.get("d_first_enabled_tick") != expected_d_first:
                errors.append(
                    f"story {story_index} D first enable mismatch"
                )
            expected_flicker = (
                {
                    "modulus": 4,
                    "enabled_residues": [2],
                    "disabled_residues": [0],
                }
                if config_id == 16
                else None
            )
            if item.get("d_flicker_task_counter_modulo") != expected_flicker:
                errors.append(f"story {story_index} D flicker schema mismatch")
            expected_switch_tick = 50 if config_id == 4 else None
            expected_switch_resource = "D" if config_id == 4 else None
            if item.get("c_resource_switch_tick") != expected_switch_tick:
                errors.append(f"story {story_index} C switch tick mismatch")
            if item.get("c_resource_after_switch") != expected_switch_resource:
                errors.append(
                    f"story {story_index} C switch resource mismatch"
                )
            if Path(timeline_name).name != timeline_name:
                errors.append(f"story {story_index} unsafe timeline path")
            if Path(contact_name).name != contact_name:
                errors.append(f"story {story_index} unsafe contact path")
            referenced_files.update((timeline_name, contact_name))
            timeline_bytes = (artifact_dir / timeline_name).read_bytes()
            contact_bytes = (artifact_dir / contact_name).read_bytes()
            if _sha256(timeline_bytes) != item["timeline_json_sha256"]:
                errors.append(f"{timeline_name} hash mismatch")
            if _sha256(contact_bytes) != item["contact_sheet_png_sha256"]:
                errors.append(f"{contact_name} hash mismatch")
            payload = json.loads(timeline_bytes)
            if payload.get("story_index") != story_index:
                errors.append(f"{timeline_name} story index mismatch")
            if payload.get("config_id") != config_id:
                errors.append(f"{timeline_name} config ID mismatch")
            if payload.get("previous_config_id") != expected_previous:
                errors.append(f"{timeline_name} previous config mismatch")
            if payload.get("callback_mode") != expected_mode:
                errors.append(f"{timeline_name} callback mode mismatch")
            errors.extend(_timeline_semantic_errors(timeline_name, payload))
            with Image.open(artifact_dir / contact_name) as image:
                if image.size != (1200, 190) or image.mode != "RGBA":
                    errors.append(f"{contact_name} image metadata mismatch")
                image.verify()
            if expected_files:
                if timeline_bytes != expected_files.get(timeline_name):
                    errors.append(f"{timeline_name} pixel-state rebuild mismatch")
                if contact_bytes != expected_files.get(contact_name):
                    errors.append(f"{contact_name} composite rebuild mismatch")
            verified += 1
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            errors.append(
                f"timeline {item.get('story_index', '?')} invalid: {error}"
            )

    try:
        actual_files = {
            path.name for path in artifact_dir.iterdir() if path.is_file()
        }
        if actual_files != referenced_files:
            errors.append("artifact file set does not match manifest")
    except OSError as error:
        errors.append(f"cannot enumerate artifact files: {error}")

    return {
        "schema": "story-scene-timelines-verification-v1",
        "verified_timelines": verified,
        "manifest_sha256": _sha256(actual_bytes),
        "errors": sorted(set(errors)),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=OUTPUT_ARTIFACT,
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = verify_story_scene_timelines(args.root, args.artifact_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
