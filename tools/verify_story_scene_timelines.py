#!/usr/bin/env python3
"""Verify the ROM-bound 24-row story timeline export."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
STORY_TABLE_OFFSET = 0x54229C
STORY_SIZE = 0x10
DESCRIPTOR_TABLE_OFFSET = 0x5A320C
DESCRIPTOR_SIZE = 0x44
OUTPUT_ARTIFACT = Path("artifacts/story-scene-timelines-v1")
CODE_SLICES = (
    ("story_controller", 0x08087C9C, 0x08087F24,
     "fb730c71f0d2351265b4cae19a99379c7f7c43800966fd45caa472d5a0d00fbe"),
    ("palette_transform", 0x08088008, 0x08088154,
     "be7fe314c8f1a86b3c23a4542d0855a2f654e51b89857890d3ec2be27a06b7dd"),
    ("easing", 0x080986E8, 0x080986F8,
     "5901088713ac749b5514172fde6e6a0e638cf5087ee8634483f79a2c326c7968"),
    ("visual_task", 0x0809880C, 0x08098E58,
     "070037f7c19a77e75498fbd666210ccca14ba42888ab27b227b7730f25b8b7d1"),
    ("linked_installer", 0x080990BC, 0x080995C0,
     "ce8174138ef0466c0131d0e81316e250e101206b7b5f27769bb1d642e6b52a5e"),
    ("linked_update", 0x080995E8, 0x08099ADE,
     "6748d0ebc18e537d5059d99ae09e42db60e2477da27c080069596e2b1ef6b361"),
)
SEMANTIC_RULE_SLICES = (
    ("easing_formula", 0x080986E8, 0x080986F8,
     "5901088713ac749b5514172fde6e6a0e638cf5087ee8634483f79a2c326c7968"),
    ("callback_dispatch", 0x0809880C, 0x08098A70,
     "7dd80651ac99d39c702b91371cca2fbf01adb1ebf099be72d49521cb85170956"),
    ("palette_phase_times_two", 0x08098A9E, 0x08098B5C,
     "6ba81cb41e475508a92d43e0f18538341b033429046c493d3357017cc1d46c40"),
    ("alpha_enable", 0x08098B84, 0x08098C0C,
     "ed8445f6f039fe1ac29d373cecbec9d099dd1b69be54c8db64df9d889c587b53"),
    ("resource_swap_scroll_callback", 0x08098C90, 0x08098D26,
     "0c79877f4d108d12e944af744791cef1d0017f0e16e5f05fc59ecea09b710ddb"),
    ("linked_counter_and_primary_motion", 0x08099604, 0x08099768,
     "428bce3dd47a6b29cbae81660c2f40f56b55d4b3028329503e3d073413531dd5"),
    ("resource_swap_and_fade", 0x08099770, 0x08099848,
     "7e325d8d99d5c1627d5b5903ca7f3cba4eb52c99bab6330e56d584f37ceca9eb"),
    ("scroll_commit_and_common_update", 0x080998C8, 0x08099946,
     "974d7789ae413060e5ebde0695db6ee57f514aae6bc1855a44d576b8b19f5333"),
)
CONTROLLER_TIMING = {
    "installer_prelude_frames": 21,
    "installer_internal_update_ticks": 16,
    "controller_update_ticks": 90,
    "linked_update_ticks": 106,
    "palette_transform_frames": 16,
    "overlay_visible_frames": 240,
    "total_wall_frames": 383,
    "overlay_first_wall_frame": 144,
}
CONFIG_IDS = [
    4, 10, 14, 24, 17, 18, 21, 25, 29, 28, 34, 76,
    30, 47, 48, 49, 51, 52, 58, 61, 74, 16, 77, 5,
]
EXPECTED_CONTACT_SHA256 = {
    0: "1d3e4282a1b84a6bfa7a732f72d34b502eb1007720be71842262ca68538c01a8",
    1: "6d9528a515f46794bc96b359c61134813ead82cf6e748f9962cbe552b4961498",
    2: "283edb7c2fb1e71c634643d0ab5b4ea2e5b61c1cde28ff78ce68cdaf02ea8111",
    3: "8d28ee2bed5d4501e6e3cf8142a7a5b0e579abe9097ebadd123d4c55cfdc526f",
    4: "7b130d8301762d171b7026ac8351740d1a098fbd3975d863666268d72ccd0138",
    5: "7dcbf970acd69b573b7df91d0855bf79d2b0da3077cee2208203fab1bc56f3ff",
    6: "00647caf37a650d8514afe5232f8c4f3d4256b74764b3d180907fbddcac767a5",
    7: "cd4d72f0720efe497344be13776b5533069953d16208df160b3aa312f89433ae",
    8: "e71354195ebd371b47dfec3fc896d5b1c24fb221aa23dfaf0793e522a547a349",
    9: "36ab32595903b2caf0281be612e8173aa32957ee7c03310bd956e43598ce91c4",
    10: "b00b9ef6379f38cb3ea3393fe2c49288b43c5acab156acea69b66cc7e918c026",
    11: "fc2ca140c46ba9270bde83a12408a3c0821d766e12711dadf123494bf87cf452",
    12: "4c32d1795532e93f70776b686a43ba8dab18a13fa4004bd59fa3fcc0f04bcb40",
    13: "6b706aa734ae979d74630a8b180f30037724c5f1e98efaa8e2cea72dcd4d3bf9",
    14: "998e8e3404866864769cc09ad224d9e89b9ac040be2cc9d0b180ed918f0d2cd9",
    15: "e3fd6d90b2e8292821697e522dc88739b5d3b945c81f94a37e147d309ff8134c",
    16: "1d5379964e8fe4bce89a6f44c05c27d712eba9a77f141b9c77643ce5071e4ceb",
    17: "244ccd49d8379d2b8e065e2b5bb3bed3e0d3961828fd7d20730a3f4a4a26764b",
    18: "b14b56f0f437a9e32815c8d9c4b8c9c1cf756db296fd776d6f6b289e472b96cd",
    19: "d44e0a4a37d3c48a5b7bac4eba6202d2b6e4ac3c606db456219bbb1f34e3ff92",
    20: "33ed9e94c4c25c8d17607a3ed10f8d886a5a00a845d2b0a21de8591e2edbf6e3",
    21: "54b5c4c8afa42a82b05ca6c20cc20fd5bba354395050c36d79ab2a92024ff5f4",
    22: "c2dda197c22ed00fd4aa89fbd3771e38d999c85e1765751e1079945fa6304bfc",
    23: "b6b26295e9c50413a6bb4423e932e399b2f281a98c6a87119bbac4057e6bb0f2",
}
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


def _signed_byte(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def _ease(value: int) -> int:
    signed = struct.unpack("<h", struct.pack("<H", value & 0xFFFF))[0]
    return (signed * signed) >> 8


def _expected_linked_ticks(
    rom: bytes,
    config_id: int,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Interpret the descriptor and callbacks without using the exporter."""
    descriptor_offset = (
        DESCRIPTOR_TABLE_OFFSET + config_id * DESCRIPTOR_SIZE
    )
    descriptor = rom[descriptor_offset : descriptor_offset + DESCRIPTOR_SIZE]
    words = struct.unpack("<17I", descriptor)
    anchor_x, anchor_y = descriptor[0], descriptor[1]
    direction_x = _signed_byte(descriptor[2])
    direction_y = _signed_byte(descriptor[3])
    amplitude, flags = struct.unpack_from("<HH", descriptor, 4)
    mode = {
        1: "d_bg_flicker",
        4: "secondary_x_motion",
        6: "alpha_enable_and_palette",
        7: "alpha_enable",
        8: "resource_swap_scroll",
    }.get(flags & 0xFF, "common_only")
    d_present = all(words[index] for index in (14, 15, 16))
    d_loaded = d_present and not flags & 0x0400
    state: dict[str, Any] = {
        "x": anchor_x * 8,
        "y": anchor_y * 8,
        "scroll": {
            "B": [240 << 8, -8 << 8],
            "C": [anchor_x * 8 << 8, (anchor_y * 8 - 8) << 8],
            "D": [anchor_x * 8 << 8, (anchor_y * 8 - 8) << 8],
        },
        "enabled": {
            "B": True,
            "C": not bool(flags & 0x0100),
            "D": d_loaded and not bool(flags & 0x0900),
        },
        "runtime_flags": 2,
        "c_resource": "C",
        "blend": {"mode": "none", "eva": 16, "evb": 0, "evy": 0},
        "secondary_phase": 0,
        "secondary_count": 0,
        "secondary_origin_x": 0,
        "swap_scroll_count": 0,
    }
    records: list[dict[str, Any]] = []
    for tick in range(1, 107):
        events: list[str] = []
        if tick <= 32:
            phase = _ease(256 - tick * 8)
            distance = amplitude - (amplitude * phase >> 8)
            if direction_x:
                state["x"] = (
                    anchor_x * 8
                    + (-distance if direction_x < 0 else distance)
                )
            if direction_y:
                state["y"] = (
                    anchor_y * 8
                    + (-distance if direction_y < 0 else distance)
                )
        elif flags & 0x0400:
            if tick == 33:
                state["blend"] = {
                    "mode": "brightness_decrease",
                    "eva": 16,
                    "evb": 0,
                    "evy": 0,
                }
                events.append("resource_swap_fade_start")
            elif 34 <= tick <= 49:
                state["blend"]["evy"] = tick - 33
            elif tick == 50:
                state["x"] = 0
                state["y"] = 0
                state["c_resource"] = "D"
                state["blend"]["evy"] = 16
                events.append("d_resources_installed_on_c_path")
            elif 51 <= tick <= 65:
                state["blend"]["evy"] = (66 - tick) * 2
            elif tick == 66:
                state["blend"] = {
                    "mode": "none",
                    "eva": 16,
                    "evb": 0,
                    "evy": 0,
                }
                events.append("resource_swap_fade_end")

        if not state["runtime_flags"] & 1:
            fixed = [state["x"] << 8, (state["y"] - 8) << 8]
            state["scroll"]["C"] = list(fixed)
            state["scroll"]["D"] = list(fixed)

        state["scroll"]["B"][0] += 2 << 8
        if tick & 1:
            events.append("b_palette_rotate_2_9")

        if mode == "d_bg_flicker":
            if tick & 3 == 0:
                state["enabled"]["D"] = False
                events.append("d_bg_disabled")
            elif tick & 3 == 2:
                state["enabled"]["D"] = True
                events.append("d_bg_enabled")
        elif mode == "secondary_x_motion" and tick >= 32:
            if state["secondary_phase"] == 0:
                state["secondary_phase"] = 1
                state["secondary_count"] = 0
                state["secondary_origin_x"] = state["x"]
            if state["secondary_phase"] == 1:
                state["secondary_count"] += 1
                phase = _ease(256 - state["secondary_count"] * 8)
                delta = 16 - (phase >> 4)
                state["x"] = state["secondary_origin_x"] - delta
                if state["secondary_count"] > 31:
                    state["secondary_phase"] = 2
        elif mode in {"alpha_enable", "alpha_enable_and_palette"}:
            if 32 <= tick <= 47:
                step = tick - 32
                if step == 0:
                    state["enabled"]["D"] = True
                    state["runtime_flags"] |= 1
                    state["scroll"]["D"][0] = 0
                    events.append("d_bg_enabled")
                state["blend"] = {
                    "mode": "alpha_d_over_linked",
                    "eva": step,
                    "evb": 16 - step,
                    "evy": 0,
                }
            if mode == "alpha_enable_and_palette" and tick >= 32:
                state["scroll"]["D"][1] -= 0x40
        elif mode == "resource_swap_scroll":
            if tick == 50:
                state["runtime_flags"] |= 1
                state["scroll"]["C"][1] = (-8 << 8) + 0x3000
                state["swap_scroll_count"] = 0
                events.append("c_path_scroll_override")
            elif tick >= 58 and state["swap_scroll_count"] <= 15:
                state["scroll"]["C"][1] -= 0x400
                state["swap_scroll_count"] += 1
                if state["swap_scroll_count"] == 16:
                    events.append("c_path_trailing_row_cleared")

        records.append(
            {
                "linked_tick": tick,
                "wall_frame": 21 + tick,
                "task_counter": tick,
                "position_pixels": [state["x"], state["y"]],
                "scroll_fixed_8_8": {
                    name: list(value)
                    for name, value in state["scroll"].items()
                },
                "scroll_pixels": {
                    name: [component // 256 for component in value]
                    for name, value in state["scroll"].items()
                },
                "bg_enabled": dict(state["enabled"]),
                "runtime_flags": state["runtime_flags"],
                "c_display_resource": state["c_resource"],
                "blend": dict(state["blend"]),
                "b_palette_rotation": (tick + 1) // 2 % 8,
                "d_palette_brighten": (
                    min((tick - 48) >> 3, 7) * 2
                    if mode == "alpha_enable_and_palette" and tick >= 48
                    else 0
                ),
                "events": events,
            }
        )
    return f"0x{flags:04X}", mode, records


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

    independent_ticks: dict[int, list[dict[str, Any]]] = {}
    independent_flags: dict[int, str] = {}
    independent_modes: dict[int, str] = {}
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
        for name, start, end, expected_hash in SEMANTIC_RULE_SLICES:
            actual_hash = _sha256(
                rom[start - ROM_BASE : end - ROM_BASE]
            )
            if actual_hash != expected_hash:
                errors.append(f"{name} semantic rule slice hash mismatch")
        rom_config_ids = [
            struct.unpack_from(
                "<I",
                rom,
                STORY_TABLE_OFFSET + index * STORY_SIZE + 12,
            )[0]
            & 0xFF
            for index in range(24)
        ]
        if rom_config_ids != CONFIG_IDS:
            errors.append("ROM story config sequence mismatch")
        for config_id in rom_config_ids:
            flags, mode, records = _expected_linked_ticks(rom, config_id)
            independent_flags[config_id] = flags
            independent_modes[config_id] = mode
            independent_ticks[config_id] = records
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append(f"cannot interpret ROM-derived timelines: {error}")

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
            if item.get("descriptor_flags") != independent_flags.get(
                config_id,
                DESCRIPTOR_FLAGS.get(config_id, "0x0000"),
            ):
                errors.append(
                    f"story {story_index} descriptor flags mismatch"
                )
            if item.get("callback_mode") != independent_modes.get(
                config_id,
                expected_mode,
            ):
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
            expected_records = independent_ticks.get(config_id)
            if (
                expected_records is not None
                and payload.get("linked_ticks") != expected_records
            ):
                errors.append(
                    f"{timeline_name} independent ROM state transition mismatch"
                )
            with Image.open(artifact_dir / contact_name) as image:
                if image.size != (1200, 190) or image.mode != "RGBA":
                    errors.append(f"{contact_name} image metadata mismatch")
                image.verify()
            if _sha256(contact_bytes) != EXPECTED_CONTACT_SHA256[story_index]:
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

    manifest_contract_errors = {
        "controller timing mismatch",
        "manifest does not contain 24 timelines",
        "story config sequence mismatch",
        "story callback family mapping mismatch",
    }
    if manifest_contract_errors.intersection(errors) or any(
        error.startswith("story ") for error in errors
    ):
        errors.append("manifest does not match ROM-derived timelines")

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
