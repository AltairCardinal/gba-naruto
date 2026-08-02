#!/usr/bin/env python3
"""Build profile-driven production-relocated battle-effect pixel A/B ROMs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from tools.build_mod import apply_patch
from tools.image_resource_regions import ImageResourceRegions
from tools.import_battle_effect_resource_relocations import (
    REGION_REGISTRY_PATH,
    SPEC_SCHEMA,
    resolve_battle_effect_resource_relocation_patches,
)
from tools.import_battle_effect_resources import ROM_SHA256
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


PROFILE_SCHEMA = "battle-effect-pixel-ab-profile-v1"
BUILD_SCHEMA = "battle-effect-pixel-ab-build-v1"
FULL_SPEC = Path(
    "artifacts/battle-effect-resource-relocation-v1/full-relocation-spec.json"
)
VARIANTS = ("baseline", "candidate")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid battle-effect pixel profile input {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"battle-effect pixel JSON must be an object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _require_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"battle-effect pixel {label} must be an integer")
    return value


def _require_int_pair(value: object, label: str) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"battle-effect pixel {label} must contain two integers")
    return (_require_int(value[0], label), _require_int(value[1], label))


def _profile_screen_pixels(profile: Mapping[str, Any]) -> list[tuple[int, int]]:
    primary = _require_int_pair(profile.get("screen_xy"), "screen_xy")
    raw = profile.get("screen_pixels", [list(primary)])
    if not isinstance(raw, list) or not raw:
        raise ValueError("battle-effect pixel screen_pixels must be nonempty")
    pixels = [_require_int_pair(value, "screen_pixels") for value in raw]
    if (
        pixels[0] != primary
        or len(set(pixels)) != len(pixels)
        or any(not 0 <= x < 240 or not 0 <= y < 160 for x, y in pixels)
    ):
        raise ValueError("battle-effect pixel screen_pixels contract mismatch")
    return pixels


def _runtime_component_obj_tile_base(
    profile: Mapping[str, Any], component_tile_index: int
) -> int:
    runtime_oam = profile.get("runtime_oam")
    if not isinstance(runtime_oam, dict):
        raise ValueError("battle-effect pixel runtime_oam must be an object")
    try:
        address = int(runtime_oam.get("obj_vram_address"), 16)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "battle-effect pixel runtime component tile mapping mismatch"
        ) from error
    if (
        not isinstance(component_tile_index, int)
        or isinstance(component_tile_index, bool)
    ):
        raise ValueError("battle-effect pixel runtime component tile mapping mismatch")
    delta = address - 0x06010000
    expected = delta // 32 + component_tile_index
    if (
        delta < 0
        or delta % 32
        or not 0 <= expected < 1024
        or runtime_oam.get("obj_tile_base") != expected
    ):
        raise ValueError("battle-effect pixel runtime component tile mapping mismatch")
    return expected


def _runtime_oam_instances(
    profile: Mapping[str, Any],
    pixel_x: int,
    pixel_y: int,
    *,
    component_width: int | None = None,
    component_height: int | None = None,
) -> list[dict[str, Any]]:
    runtime_oam = profile.get("runtime_oam")
    if not isinstance(runtime_oam, dict):
        raise ValueError("battle-effect pixel runtime_oam must be an object")
    primary_attributes = runtime_oam.get("attributes")
    if not isinstance(primary_attributes, list) or len(primary_attributes) != 3:
        raise ValueError("battle-effect pixel runtime OAM attributes are invalid")
    raw_instances = runtime_oam.get("instances")
    if raw_instances is None:
        raw_instances = [
            {
                "oam_index": runtime_oam.get("oam_index"),
                "attributes": primary_attributes,
                "frame_id": profile.get("frame_id"),
                "component_index": profile.get("component_index"),
                "component_pixel_xy": profile.get("component_pixel_xy"),
                "source_pixel_screen_xy": profile.get("screen_xy"),
                "visible_in_final_difference": True,
            }
        ]
    if not isinstance(raw_instances, list) or not raw_instances:
        raise ValueError("battle-effect pixel runtime OAM instances are invalid")

    screen_pixels = _profile_screen_pixels(profile)
    instances: list[dict[str, Any]] = []
    indices: set[int] = set()
    for raw in raw_instances:
        if not isinstance(raw, dict):
            raise ValueError("battle-effect pixel runtime OAM instance is invalid")
        index = _require_int(raw.get("oam_index"), "runtime OAM instance index")
        attributes = raw.get("attributes")
        if not isinstance(attributes, list) or len(attributes) != 3:
            raise ValueError("battle-effect pixel runtime OAM instance attributes are invalid")
        try:
            attr0, attr1, attr2 = (int(value, 16) for value in attributes)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "battle-effect pixel runtime OAM instance attributes are invalid"
            ) from error
        source_xy = _require_int_pair(
            raw.get("source_pixel_screen_xy"), "runtime OAM instance screen pixel"
        )
        component_xy = _require_int_pair(
            raw.get("component_pixel_xy"), "runtime OAM instance component pixel"
        )
        visible = raw.get("visible_in_final_difference")
        affine = bool(attr0 & 0x0100)
        flip_x = not affine and bool(attr1 & 0x1000)
        flip_y = not affine and bool(attr1 & 0x2000)
        if (flip_x and component_width is None) or (
            flip_y and component_height is None
        ):
            raise ValueError(
                "battle-effect pixel flipped OAM instance requires component dimensions"
            )
        screen_pixel_x = (
            component_width - 1 - pixel_x if flip_x else pixel_x
        )
        screen_pixel_y = (
            component_height - 1 - pixel_y if flip_y else pixel_y
        )
        if (
            not 0 <= index < 128
            or index in indices
            or component_xy != (pixel_x, pixel_y)
            or raw.get("frame_id") != profile.get("frame_id")
            or raw.get("component_index") != profile.get("component_index")
            or attr2 & 0x3FF != runtime_oam.get("obj_tile_base")
            or attr2 >> 12 != runtime_oam.get("palette_bank")
            or not isinstance(visible, bool)
        ):
            raise ValueError("battle-effect pixel runtime OAM instance contract mismatch")
        if (
            (attr1 & 0x1FF) + screen_pixel_x,
            (attr0 & 0xFF) + screen_pixel_y,
        ) != source_xy:
            raise ValueError("battle-effect pixel runtime OAM instance screen mapping mismatch")
        indices.add(index)
        instances.append(dict(raw))

    primary = instances[0]
    if (
        primary["oam_index"] != runtime_oam.get("oam_index")
        or primary["attributes"] != primary_attributes
        or tuple(primary["source_pixel_screen_xy"])
        != _require_int_pair(profile.get("screen_xy"), "screen_xy")
        or primary["visible_in_final_difference"] is not True
        or [
            tuple(item["source_pixel_screen_xy"])
            for item in instances
            if item["visible_in_final_difference"]
        ]
        != screen_pixels
        or any(
            tuple(item["source_pixel_screen_xy"]) in screen_pixels
            for item in instances
            if not item["visible_in_final_difference"]
        )
    ):
        raise ValueError("battle-effect pixel runtime OAM instance visibility mismatch")
    return instances


def _require_relative_file(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"battle-effect pixel {label} must be a repository path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"battle-effect pixel {label} must be a safe relative path")
    path = (root / relative).resolve(strict=True)
    if root not in path.parents or not path.is_file():
        raise ValueError(f"battle-effect pixel {label} must stay inside the repository")
    return path


def _require_sha(path: Path, expected: object, label: str) -> str:
    if (
        not isinstance(expected, str)
        or len(expected) != 64
        or any(character not in "0123456789abcdef" for character in expected)
    ):
        raise ValueError(f"battle-effect pixel {label} SHA-256 is invalid")
    actual = _sha256_file(path)
    if actual != expected:
        raise ValueError(
            f"battle-effect pixel {label} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return actual


def _ledger(patches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for patch in patches:
        allocation = patch.get("allocation")
        after = bytes.fromhex(patch["after_hex"])
        rows.append(
            {
                "id": patch["id"],
                "kind": "allocation" if allocation is not None else "redirect",
                "asset_type": patch["asset_type"],
                "resource_type": patch["resource_type"],
                "resource_sha256": patch["resource_sha256"],
                "replacement_sha256": patch.get("replacement_sha256"),
                "offset": patch["offset"],
                "size": len(after),
                "after_sha256": _sha256(after),
                "after_hex": None if allocation is not None else patch["after_hex"],
                "new_pointer": patch["new_pointer"],
                "target_pointer_offsets": patch["target_pointer_offsets"],
                "allocation": allocation,
                "decompressed_size": patch.get("decompressed_size"),
            }
        )
    return rows


def _topology(ledger: list[dict[str, Any]]) -> list[tuple[object, ...]]:
    return [
        (
            row["kind"],
            row["asset_type"],
            row["resource_type"],
            row["offset"],
            row["size"],
            row["new_pointer"],
            tuple(row["target_pointer_offsets"]),
        )
        for row in ledger
    ]


def _apply(
    base: bytes,
    layout: RomLayout,
    regions: ImageResourceRegions,
    patches: list[dict[str, Any]],
) -> bytes:
    output = bytearray(layout.expanded_base())
    gate = PatchSafetyGate(base, layout=layout, image_regions=regions)
    for patch in patches:
        apply_patch(output, patch, gate=gate)
    return bytes(output)


def _find(rows: object, label: str, **criteria: object) -> dict[str, Any]:
    if not isinstance(rows, list):
        raise ValueError(f"battle-effect pixel {label} is not a list")
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and all(row.get(key) == value for key, value in criteria.items())
    ]
    if len(matches) != 1:
        raise ValueError(
            f"battle-effect pixel {label} expected one match for {criteria}; found {len(matches)}"
        )
    return matches[0]


def _resolve_selector_binding(
    selector: object,
    sequence_bindings: Mapping[str, Any],
    *,
    sequence_id: int,
    trigger_sequence_id: int | None = None,
    hardcoded_selector_producers: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve the natural selector and retain the distinct resource sequence."""

    if not isinstance(selector, dict):
        raise ValueError("battle-effect pixel selector contract mismatch")
    kind = selector.get("kind")
    selector_id = _require_int(selector.get("id"), "selector id")
    encoded_action_id = _require_int(
        selector.get("encoded_action_id"), "encoded_action_id"
    )
    if kind == "ninja_tool_handler_immediate":
        if (
            trigger_sequence_id not in (None, sequence_id)
            or not isinstance(hardcoded_selector_producers, Mapping)
            or hardcoded_selector_producers.get("schema")
            != "battle-effect-hardcoded-selector-producers-v1"
        ):
            raise ValueError(
                "battle-effect pixel ninja-tool hardcoded handler binding mismatch"
            )
        ninja_tool_binding = _find(
            sequence_bindings.get("ninja_tool_bindings"),
            "ninja-tool binding",
            ninja_tool_id=selector_id,
        )
        if ninja_tool_binding.get("encoded_action_id") != encoded_action_id:
            raise ValueError(
                "battle-effect pixel ninja-tool hardcoded handler binding mismatch"
            )
        sequence_row = hardcoded_selector_producers.get("by_sequence", {}).get(
            str(sequence_id)
        )
        if not isinstance(sequence_row, dict):
            raise ValueError(
                "battle-effect pixel ninja-tool hardcoded handler binding mismatch"
            )
        callsite = selector.get("selector_callsite")
        pair_slot = selector.get("pair_slot")
        handler_start = selector.get("handler_start")
        calls = [
            row
            for row in sequence_row.get("callsites", [])
            if isinstance(row, dict)
            and row.get("selector_callsite") == callsite
            and row.get("selector_kind") == "immediate_movs_r0"
            and row.get("hardcoded_sequence_id") == sequence_id
            and row.get("association_status") == "static_handler_linked"
        ]
        links = [
            link
            for row in calls
            for link in row.get("handler_links", [])
            if isinstance(link, dict)
            and link.get("pair_index") == encoded_action_id
            and link.get("pair_slot") == pair_slot
            and link.get("handler_start") == handler_start
            and link.get("identity_kind") == "unidentified_runtime_action_byte"
        ]
        if len(calls) != 1 or len(links) != 1 or pair_slot not in {
            "primary",
            "secondary",
        }:
            raise ValueError(
                "battle-effect pixel ninja-tool hardcoded handler binding mismatch"
            )
        binding = links[0]
        return binding, {
            "ninja_tool_id": selector_id,
            "encoded_action_id": encoded_action_id,
            "sequence_id": sequence_id,
            "selector_kind": kind,
            "pair_slot": pair_slot,
            "handler_start": handler_start,
            "selector_callsite": callsite,
            "dynamic_ninja_tool_sequence_id": ninja_tool_binding["sequence_id"],
        }
    if kind == "active_action_handler_immediate":
        if (
            trigger_sequence_id not in (None, sequence_id)
            or not isinstance(hardcoded_selector_producers, Mapping)
            or hardcoded_selector_producers.get("schema")
            != "battle-effect-hardcoded-selector-producers-v1"
            or encoded_action_id != selector_id
        ):
            raise ValueError(
                "battle-effect pixel hardcoded handler binding mismatch"
            )
        sequence_row = hardcoded_selector_producers.get("by_sequence", {}).get(
            str(sequence_id)
        )
        if not isinstance(sequence_row, dict):
            raise ValueError(
                "battle-effect pixel hardcoded handler binding mismatch"
            )
        callsite = selector.get("selector_callsite")
        pair_slot = selector.get("pair_slot")
        handler_start = selector.get("handler_start")
        calls = [
            row
            for row in sequence_row.get("callsites", [])
            if isinstance(row, dict)
            and row.get("selector_callsite") == callsite
            and row.get("selector_kind") == "immediate_movs_r0"
            and row.get("hardcoded_sequence_id") == sequence_id
            and row.get("association_status") == "static_handler_linked"
        ]
        links = [
            link
            for row in calls
            for link in row.get("handler_links", [])
            if isinstance(link, dict)
            and link.get("action_id") == selector_id
            and link.get("pair_index") == selector_id
            and link.get("pair_slot") == pair_slot
            and link.get("handler_start") == handler_start
            and link.get("identity_kind") == "active_action"
            and link.get("hardcoded_and_dynamic_sequences_are_distinct") is True
        ]
        action_binding = _find(
            sequence_bindings.get("active_action_bindings"),
            "active-action binding",
            action_id=selector_id,
        )
        if (
            len(calls) != 1
            or len(links) != 1
            or pair_slot not in {"primary", "secondary"}
            or links[0].get("dynamic_action_sequence_id")
            != action_binding.get("sequence_id")
        ):
            raise ValueError(
                "battle-effect pixel hardcoded handler binding mismatch"
            )
        binding = links[0]
        return binding, {
            "active_action_id": selector_id,
            "encoded_action_id": encoded_action_id,
            "sequence_id": sequence_id,
            "selector_kind": kind,
            "pair_slot": pair_slot,
            "handler_start": handler_start,
            "selector_callsite": callsite,
            "dynamic_action_sequence_id": binding["dynamic_action_sequence_id"],
        }
    if kind == "ninja_tool":
        binding = _find(
            sequence_bindings.get("ninja_tool_bindings"),
            "ninja-tool binding",
            ninja_tool_id=selector_id,
        )
        id_key = "ninja_tool_id"
        binding_encoded_action_id = binding.get("encoded_action_id")
    elif kind == "active_action":
        binding = _find(
            sequence_bindings.get("active_action_bindings"),
            "active-action binding",
            action_id=selector_id,
        )
        id_key = "active_action_id"
        binding_encoded_action_id = selector_id
    else:
        raise ValueError("battle-effect pixel selector contract mismatch")
    actual_trigger_sequence_id = (
        sequence_id if trigger_sequence_id is None else trigger_sequence_id
    )
    if (
        binding_encoded_action_id != encoded_action_id
        or binding.get("sequence_id") != actual_trigger_sequence_id
    ):
        raise ValueError(f"battle-effect pixel {kind} binding mismatch")
    build_binding = {
        id_key: selector_id,
        "encoded_action_id": encoded_action_id,
        "sequence_id": sequence_id,
    }
    if actual_trigger_sequence_id != sequence_id:
        build_binding["trigger_sequence_id"] = actual_trigger_sequence_id
    return binding, build_binding


def _validate_profile(
    root: Path, profile_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = _json(profile_path)
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ValueError("battle-effect pixel profile schema mismatch")

    group_id = _require_int(profile.get("group_id"), "group_id")
    sequence_id = _require_int(profile.get("sequence_id"), "sequence_id")
    trigger_sequence_id = profile.get("trigger_sequence_id", sequence_id)
    trigger_sequence_id = _require_int(
        trigger_sequence_id, "trigger_sequence_id"
    )
    trigger_group_id = profile.get("trigger_group_id", group_id)
    trigger_group_id = _require_int(trigger_group_id, "trigger_group_id")
    if (trigger_sequence_id == sequence_id) != (trigger_group_id == group_id):
        raise ValueError(
            "battle-effect pixel trigger sequence/group distinction mismatch"
        )
    frame_id = _require_int(profile.get("frame_id"), "frame_id")
    component_index = _require_int(profile.get("component_index"), "component_index")
    pixel_x, pixel_y = _require_int_pair(
        profile.get("component_pixel_xy"), "component_pixel_xy"
    )
    screen_x, screen_y = _profile_screen_pixels(profile)[0]
    graphics_byte_offset = _require_int(
        profile.get("graphics_byte_offset"), "graphics_byte_offset"
    )
    before_byte = _require_int(profile.get("before_byte"), "before_byte")
    after_byte = _require_int(profile.get("after_byte"), "after_byte")
    before_index = _require_int(profile.get("before_index"), "before_index")
    after_index = _require_int(profile.get("after_index"), "after_index")
    pair_pointer_offset = _require_int(
        profile.get("pair_pointer_offset"), "pair_pointer_offset"
    )
    allocation_offset = _require_int(
        profile.get("graphics_allocation_offset"), "graphics_allocation_offset"
    )
    expected_encoded_size = _require_int(
        profile.get("expected_encoded_size"), "expected_encoded_size"
    )
    if not all(0 <= value <= 0xFF for value in (before_byte, after_byte)):
        raise ValueError("battle-effect pixel mutation bytes are out of range")
    if not all(0 <= value <= 0xF for value in (before_index, after_index)):
        raise ValueError("battle-effect pixel palette indices are out of range")

    catalogs = profile.get("catalogs")
    if not isinstance(catalogs, dict):
        raise ValueError("battle-effect pixel catalogs must be an object")
    catalog_payloads: dict[str, dict[str, Any]] = {}
    catalog_keys = ["resource_pairs", "animations", "sequence_bindings"]
    if profile.get("selector", {}).get("kind") in {
        "active_action_handler_immediate",
        "ninja_tool_handler_immediate",
    }:
        catalog_keys.append("hardcoded_selector_producers")
    for key in catalog_keys:
        path = _require_relative_file(root, catalogs.get(key), key)
        _require_sha(path, catalogs.get(f"{key}_sha256"), key)
        catalog_payloads[key] = _json(path)

    source_path = _require_relative_file(
        root, profile.get("source_graphics"), "source_graphics"
    )
    source_sha = _require_sha(
        source_path, profile.get("source_graphics_sha256"), "source_graphics"
    )
    input_state = _require_relative_file(root, profile.get("input_state"), "input_state")
    _require_sha(input_state, profile.get("input_state_sha256"), "input_state")
    input_evidence = _require_relative_file(
        root, profile.get("input_evidence"), "input_evidence"
    )
    _require_sha(
        input_evidence,
        profile.get("input_evidence_sha256"),
        "input_evidence",
    )

    resource = _find(
        catalog_payloads["resource_pairs"].get("entries"),
        "resource pair",
        group_id=group_id,
    )
    graphics = resource.get("graphics")
    if (
        not isinstance(graphics, dict)
        or graphics.get("decompressed_sha256") != source_sha
        or resource.get("table_entry_file_offset") != pair_pointer_offset
        or graphics.get("compressed_size") != expected_encoded_size
    ):
        raise ValueError("battle-effect pixel resource-pair contract mismatch")

    animation_group = _find(
        catalog_payloads["animations"].get("groups"),
        "animation group",
        group_id=group_id,
    )
    if sequence_id not in animation_group.get("sequence_ids", []):
        raise ValueError("battle-effect pixel animation sequence binding mismatch")
    frame = _find(animation_group.get("frames"), "animation frame", frame_id=frame_id)
    component = _find(
        frame.get("components"),
        "animation component",
        component_index=component_index,
    )
    width = _require_int(component.get("width"), "component width")
    height = _require_int(component.get("height"), "component height")
    tile_index = _require_int(component.get("tile_index"), "component tile_index")
    if not 0 <= pixel_x < width or not 0 <= pixel_y < height:
        raise ValueError("battle-effect pixel lies outside the component")
    tiles_per_row = width // 8
    pixel_tile_index = tile_index + (pixel_y // 8) * tiles_per_row + pixel_x // 8
    calculated_offset = (
        pixel_tile_index * 32 + (pixel_y % 8) * 4 + (pixel_x % 8) // 2
    )
    if calculated_offset != graphics_byte_offset:
        raise ValueError("battle-effect pixel graphics byte mapping mismatch")

    source = source_path.read_bytes()
    if graphics_byte_offset >= len(source) or source[graphics_byte_offset] != before_byte:
        raise ValueError("battle-effect pixel source byte mismatch")
    low_nibble = pixel_x % 2 == 0
    actual_before_index = before_byte & 0xF if low_nibble else before_byte >> 4
    actual_after_index = after_byte & 0xF if low_nibble else after_byte >> 4
    preserved_mask = 0xF0 if low_nibble else 0x0F
    if (
        actual_before_index != before_index
        or actual_after_index != after_index
        or before_byte & preserved_mask != after_byte & preserved_mask
    ):
        raise ValueError("battle-effect pixel nibble isolation mismatch")

    binding, build_binding = _resolve_selector_binding(
        profile.get("selector"),
        catalog_payloads["sequence_bindings"],
        sequence_id=sequence_id,
        trigger_sequence_id=trigger_sequence_id,
        hardcoded_selector_producers=catalog_payloads.get(
            "hardcoded_selector_producers"
        ),
    )
    sequence = _find(
        catalog_payloads["sequence_bindings"].get("sequences"),
        "sequence descriptor",
        sequence_id=sequence_id,
    )
    if group_id not in sequence.get("nonzero_resource_group_ids", []):
        raise ValueError("battle-effect pixel sequence group mismatch")
    trigger_sequence = _find(
        catalog_payloads["sequence_bindings"].get("sequences"),
        "trigger sequence descriptor",
        sequence_id=trigger_sequence_id,
    )
    if trigger_group_id not in trigger_sequence.get(
        "nonzero_resource_group_ids", []
    ):
        raise ValueError("battle-effect pixel trigger sequence group mismatch")

    _runtime_component_obj_tile_base(profile, component.get("tile_index"))
    _runtime_oam_instances(
        profile,
        pixel_x,
        pixel_y,
        component_width=width,
        component_height=height,
    )

    runtime_input = profile.get("runtime_input")
    if (
        not isinstance(runtime_input, dict)
        or runtime_input.get("key") != "A"
        or not 0
        < _require_int(runtime_input.get("down_frame"), "runtime down frame")
        < _require_int(runtime_input.get("up_frame"), "runtime up frame")
        < _require_int(runtime_input.get("capture_frame"), "runtime capture frame")
    ):
        raise ValueError("battle-effect pixel runtime input contract mismatch")

    return profile, {
        "source_path": source_path,
        "input_state": input_state,
        "input_evidence": input_evidence,
        "resource": resource,
        "animation_group": animation_group,
        "frame": frame,
        "component": component,
        "binding": binding,
        "build_binding": build_binding,
        "sequence": sequence,
        "trigger_sequence": trigger_sequence,
        "allocation_offset": allocation_offset,
        "expected_encoded_size": expected_encoded_size,
    }


def build_pair(root: Path, profile_path: Path, output: Path) -> dict[str, Any]:
    """Build a preservation baseline and a one-pixel candidate from a fixed profile."""

    root = Path(root).resolve(strict=True)
    profile_path = Path(profile_path).resolve(strict=True)
    output = Path(output).resolve()
    if root not in profile_path.parents:
        raise ValueError("battle-effect pixel profile must stay inside the repository")
    if output.exists() and any(output.iterdir()):
        raise ValueError("battle-effect pixel A/B output directory must be empty")
    profile, contract = _validate_profile(root, profile_path)

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("battle-effect pixel base ROM identity mismatch")
    source = contract["source_path"].read_bytes()
    offset = profile["graphics_byte_offset"]
    candidate = bytearray(source)
    candidate[offset] = profile["after_byte"]
    candidate = bytes(candidate)
    if [
        index
        for index, (before, after) in enumerate(zip(source, candidate))
        if before != after
    ] != [offset]:
        raise ValueError("battle-effect pixel decoded graphics isolation mismatch")

    parent_spec = _json(root / FULL_SPEC)
    source_edit = _find(
        parent_spec.get("edits"),
        "parent relocation edit",
        resource_type="graphics",
        resource_sha256=profile["source_graphics_sha256"],
    )
    if parent_spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("battle-effect pixel parent relocation schema mismatch")

    output.mkdir(parents=True, exist_ok=True)
    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    regions = ImageResourceRegions.from_path(root / REGION_REGISTRY_PATH, layout)
    variants: dict[str, dict[str, Any]] = {}
    for variant, graphics in (("baseline", source), ("candidate", candidate)):
        variant_dir = output / variant
        variant_dir.mkdir()
        graphics_name = f"group-{profile['group_id']:02d}-graphics-4bpp.bin"
        graphics_path = variant_dir / graphics_name
        graphics_path.write_bytes(graphics)

        spec = {key: value for key, value in parent_spec.items() if key != "edits"}
        edit = json.loads(json.dumps(source_edit))
        edit["id"] = f"{profile['profile_id']}-{variant}"
        edit["source_file"] = str(graphics_path)
        edit["target_pointer_offsets"] = [profile["pair_pointer_offset"]]
        spec["edits"] = [edit]
        spec_path = variant_dir / "spec.json"
        _write_json(spec_path, spec)

        patches = resolve_battle_effect_resource_relocation_patches(
            root,
            spec_path,
            rom=base,
            layout=layout,
            regions=regions,
        )
        ledger = _ledger(patches)
        if (
            len(ledger) != 2
            or ledger[0]["kind"] != "allocation"
            or ledger[0]["offset"] != contract["allocation_offset"]
            or ledger[0]["size"] != contract["expected_encoded_size"]
            or ledger[0]["decompressed_size"] != len(graphics)
            or ledger[0]["replacement_sha256"] != _sha256(graphics)
            or ledger[1]["kind"] != "redirect"
            or ledger[1]["offset"] != profile["pair_pointer_offset"]
        ):
            raise ValueError("battle-effect pixel patch topology mismatch")

        rom = _apply(base, layout, regions, patches)
        rom_path = variant_dir / f"{variant}.gba"
        rom_path.write_bytes(rom)
        variants[variant] = {
            "rom_path": rom_path.relative_to(output).as_posix(),
            "rom_sha256": _sha256(rom),
            "rom_size": len(rom),
            "spec_path": spec_path.relative_to(output).as_posix(),
            "graphics_path": graphics_path.relative_to(output).as_posix(),
            "graphics_sha256": _sha256(graphics),
            "encoded_graphics_size": ledger[0]["size"],
            "graphics_allocation_offset": ledger[0]["offset"],
            "patch_ledger": ledger,
        }

    baseline_ledger = variants["baseline"]["patch_ledger"]
    candidate_ledger = variants["candidate"]["patch_ledger"]
    result = {
        "schema": BUILD_SCHEMA,
        "profile": profile_path.relative_to(root).as_posix(),
        "profile_sha256": _sha256_file(profile_path),
        "profile_id": profile["profile_id"],
        "base_rom": "rom/base.gba",
        "base_rom_sha256": ROM_SHA256,
        "input_state": profile["input_state"],
        "input_state_sha256": profile["input_state_sha256"],
        "input_evidence": profile["input_evidence"],
        "input_evidence_sha256": profile["input_evidence_sha256"],
        "runtime_input": profile["runtime_input"],
        "runtime_oam": profile["runtime_oam"],
        "binding": {**contract["build_binding"], "group_id": profile["group_id"]},
        "edit": {
            "frame_id": profile["frame_id"],
            "component_index": profile["component_index"],
            "component_pixel_xy": profile["component_pixel_xy"],
            "graphics_byte_offset": profile["graphics_byte_offset"],
            "before_byte": profile["before_byte"],
            "after_byte": profile["after_byte"],
            "before_index": profile["before_index"],
            "after_index": profile["after_index"],
            "screen_xy": profile["screen_xy"],
            "before_rgb": profile["before_rgb"],
            "after_rgb": profile["after_rgb"],
            **(
                {"screen_pixels": profile["screen_pixels"]}
                if "screen_pixels" in profile
                else {}
            ),
        },
        "catalogs": profile["catalogs"],
        "same_patch_topology": _topology(baseline_ledger)
        == _topology(candidate_ledger),
        "same_encoded_size": variants["baseline"]["encoded_graphics_size"]
        == variants["candidate"]["encoded_graphics_size"],
        "variants": variants,
    }
    if not result["same_patch_topology"] or not result["same_encoded_size"]:
        raise ValueError("battle-effect pixel A/B topology is not stable")
    _write_json(output / "build-manifest.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = build_pair(args.root, args.profile, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
