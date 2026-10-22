#!/usr/bin/env python3
"""Bind persisted battle-effect OAM content to live sprite tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
from typing import Any
import uuid

try:
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state


SCHEMA = "battle-effect-runtime-oam-task-bindings-v1"
ROM_RELATIVE = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PARENT_DIRECTORY = Path("artifacts/battle-effect-runtime-oam-bindings-v1")
PARENT_PAYLOAD_RELATIVE = PARENT_DIRECTORY / "bindings.json"
PARENT_MANIFEST_RELATIVE = PARENT_DIRECTORY / "manifest.json"
PARENT_SCHEMA = "battle-effect-runtime-oam-bindings-v1"
SOURCE_RELATIVE = Path("artifacts/battle-effect-sprite-animations-v1/manifest.json")
SOURCE_SCHEMA = "battle-effect-sprite-animations-v1"

TASK_POOL_BASE = 0x03003BB8
TASK_RECORD_SIZE = 0x3C
TASK_SLOT_COUNT = 128
TASK_POOL_SIZE = TASK_RECORD_SIZE * TASK_SLOT_COUNT
ACTIVE_TASK_COUNT_ADDRESS = 0x03005BB8
ACTIVE_TASK_POINTER_LIST_ADDRESS = 0x030059B8
RUNTIME_OFFSET_TABLE_ADDRESS = 0x03000054
RUNTIME_OFFSET_TABLE_SIZE = 32
SHADOW_OAM_BASE = 0x0300027C
HARDWARE_OAM_BASE = 0x07000000
OAM_RECORD_SIZE = 8
OAM_RECORD_COUNT = 128
OAM_BUFFER_SIZE = OAM_RECORD_SIZE * OAM_RECORD_COUNT
SUBMISSION_PENDING_ADDRESS = 0x0300067C
SUBMISSION_FRAME_COUNTER_ADDRESS = 0x0300067D
SUBMISSION_WAIT_START = 0x08061126
SUBMISSION_WAIT_END = 0x0806112C
DYNAMIC_OBJ_COPY_FLAG = 0x00400000

SHAPE_SIZE_BY_DIMENSIONS = {
    (8, 8): (0, 0),
    (16, 16): (0, 1),
    (32, 32): (0, 2),
    (64, 64): (0, 3),
    (16, 8): (1, 0),
    (32, 8): (1, 1),
    (32, 16): (1, 2),
    (64, 32): (1, 3),
    (8, 16): (2, 0),
    (8, 32): (2, 1),
    (16, 32): (2, 2),
    (32, 64): (2, 3),
}

CODE_SLICES = {
    "frame_wait": (0x080610E8, 0x0806114A, "931ab756083f41deb5f80be9d2346ce681c9bbdedc27d3f0387cc3e58b6734fb"),
    "vblank_callback": (0x080612BC, 0x080614EC, "682fb5e1ca18c9155ce5f7541d152cb925c4046d9371b79a85cac4b12bc37d42"),
    "renderer_driver": (0x08062924, 0x08063338, "5e29f07126eb06c69170c5c15a2ab28fe0e1ad86ffdd85f6dfbd4601defbee36"),
    "dispatcher": (0x080627B0, 0x0806291A, "2a9a970b7cd4227b53d46ee2274e38c0fe0927919d4fd6611923aad81355857a"),
    "allocator": (0x080625A4, 0x080626B0, "e238cd1ee159265fb8b718766f336f8d5462596954f93c7805d1bf33dd6b3c54"),
    "renderer": (0x08062982, 0x08063278, "ffc3fc22d05d94a21ebb1f6de147a891fc791d4ad35505d5a5712dd0791ddb87"),
}


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_digest(value: Any) -> str:
    return _digest(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )


def _h16(value: int) -> str:
    return f"0x{value:04X}"


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _static_contract(rom: bytes) -> dict[str, Any]:
    slices = {}
    for name, (start, end, expected) in CODE_SLICES.items():
        payload = rom[start - 0x08000000 : end - 0x08000000]
        if len(payload) != end - start or _digest(payload) != expected:
            raise ValueError(f"{name} code slice mismatch")
        slices[name] = {
            "start": _address(start),
            "end_exclusive": _address(end),
            "size": len(payload),
            "sha256": expected,
        }
    return {
        "code_slices": slices,
        "task_pool": {
            "base": _address(TASK_POOL_BASE),
            "record_size": TASK_RECORD_SIZE,
            "slot_count": TASK_SLOT_COUNT,
            "size": TASK_POOL_SIZE,
        },
        "task_group_identity": {
            "definition_pointer_field": "+0x1C",
            "animation_pointer_field": "+0x20",
            "identity": "unique (definition_pointer, animation_pointer) pair",
            "dynamic_tile_source_field": "+0x24",
            "dynamic_tile_source_is_group_identity": False,
        },
        "runtime_offsets": {
            "address": _address(RUNTIME_OFFSET_TABLE_ADDRESS),
            "entry_count": 4,
            "entry_stride": 8,
            "selection": "(task.flags & 0x00006000) >> 13 when bit 0x1000 is set",
        },
        "submission": {
            "shadow_oam": _address(SHADOW_OAM_BASE),
            "hardware_oam": _address(HARDWARE_OAM_BASE),
            "pending_flag": _address(SUBMISSION_PENDING_ADDRESS),
            "frame_counter": _address(SUBMISSION_FRAME_COUNTER_ADDRESS),
            "pending_wait": f"{_address(SUBMISSION_WAIT_START)}..{_address(SUBMISSION_WAIT_END)}",
        },
    }


def _validated_parent(root: Path) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    payload_path = root / PARENT_PAYLOAD_RELATIVE
    manifest_path = root / PARENT_MANIFEST_RELATIVE
    payload_raw = payload_path.read_bytes()
    manifest_raw = manifest_path.read_bytes()
    payload = json.loads(payload_raw)
    manifest = json.loads(manifest_raw)
    payload_hash = _digest(payload_raw)
    if not isinstance(payload, dict) or payload.get("schema") != PARENT_SCHEMA:
        raise ValueError("battle-effect OAM parent schema mismatch")
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("artifact_schema") != PARENT_SCHEMA
        or manifest.get("files", {}).get("bindings.json") != payload_hash
    ):
        raise ValueError("battle-effect OAM parent promotion mismatch")
    if len(payload.get("tracked_checkpoints", [])) != 93:
        raise ValueError("battle-effect OAM tracked denominator mismatch")
    if len(payload.get("supplemental_states", [])) != 5:
        raise ValueError("battle-effect OAM supplemental denominator mismatch")
    return payload, manifest, payload_hash, _digest(manifest_raw)


def _source_groups(
    root: Path,
) -> tuple[dict[str, Any], str, dict[tuple[int, int], dict[str, Any]]]:
    path = root / SOURCE_RELATIVE
    raw = path.read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or manifest.get("schema") != SOURCE_SCHEMA:
        raise ValueError("battle-effect animation source schema mismatch")
    groups: dict[tuple[int, int], dict[str, Any]] = {}
    for group in manifest.get("groups", []):
        pair = (
            int(group["definition_pointer_table"], 16),
            int(group["animation_pointer_table"], 16),
        )
        if pair in groups:
            raise ValueError("battle-effect task pointer pair is not unique")
        groups[pair] = group
    if len(groups) != 18 or len(groups) != manifest.get("group_count"):
        raise ValueError("battle-effect group denominator mismatch")
    return manifest, _digest(raw), groups


def _validate_source_provenance(
    parent: dict[str, Any],
    parent_manifest: dict[str, Any],
    source: dict[str, Any],
    source_hash: str,
) -> None:
    required_scope = (
        "all_nonzero_resource_groups_complete",
        "component_lists_complete",
        "component_local_geometry_complete",
        "source_tile_coverage_complete",
        "oam_shape_size_encoding_complete",
        "normal_oam_tile_palette_priority_formula_complete",
    )
    if any(not source.get("scope", {}).get(name) for name in required_scope):
        raise ValueError("battle-effect source scope is incomplete")
    expected = {
        "path": "artifacts/battle-effect-sprite-animations-v1",
        "schema": SOURCE_SCHEMA,
        "manifest_sha256": source_hash,
        "group_count": source.get("group_count"),
        "frame_count": source.get("frame_definition_count"),
        "component_count": source.get("component_count"),
        "source_component_record_count": source.get("component_count"),
    }
    if parent.get("source_artifact") != expected:
        raise ValueError("parent source provenance differs from current source")
    promotion_source = parent_manifest.get("source", {})
    if (
        promotion_source.get("source_artifact") != expected["path"]
        or promotion_source.get("source_artifact_manifest_sha256") != source_hash
    ):
        raise ValueError("parent promotion source provenance differs")


def _parse_effect_tasks(
    pool: bytes,
    groups: dict[tuple[int, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(pool) != TASK_POOL_SIZE:
        raise ValueError("task pool byte length mismatch")
    result = []
    for slot in range(TASK_SLOT_COUNT):
        record = pool[slot * TASK_RECORD_SIZE : (slot + 1) * TASK_RECORD_SIZE]
        flags = struct.unpack_from("<I", record, 0)[0]
        anchor_x, anchor_y, delta_x, delta_y, scale_x, scale_y = struct.unpack_from(
            "<hhhhhh", record, 0x04
        )
        tile_base = struct.unpack_from("<H", record, 0x10)[0]
        palette_bank = record[0x12]
        angle = record[0x13]
        animation_id, keyframe_index, hold_timer = struct.unpack_from(
            "<HHH", record, 0x14
        )
        definition, animation, dynamic_source = struct.unpack_from("<III", record, 0x1C)
        group = groups.get((definition, animation))
        selected_frame = None
        selected_hold = None
        if group is not None and animation_id < len(group["animations"]):
            timeline = group["animations"][animation_id]
            if keyframe_index < len(timeline["keyframes"]):
                keyframe = timeline["keyframes"][keyframe_index]
                selected_frame = keyframe["frame_id"]
                selected_hold = keyframe["hold_frames"]
        result.append(
            {
                "slot": slot,
                "address": _address(TASK_POOL_BASE + slot * TASK_RECORD_SIZE),
                "raw_sha256": _digest(record),
                "active_flag": bool(flags & 1),
                "flags": _address(flags),
                "anchor": {"x": anchor_x, "y": anchor_y},
                "follow_delta": {"x": delta_x, "y": delta_y},
                "scale_q8_8": {"x": scale_x, "y": scale_y},
                "tile_base": tile_base,
                "palette_bank": palette_bank,
                "angle": angle,
                "animation_state": {
                    "animation_id": animation_id,
                    "keyframe_index": keyframe_index,
                    "hold_timer": hold_timer,
                    "selected_frame_id": selected_frame,
                    "selected_hold_frames": selected_hold,
                },
                "resource_pointers": {
                    "definition_pointer_table": _address(definition),
                    "animation_pointer_table": _address(animation),
                },
                "dynamic_tile_source": _address(dynamic_source),
                "group_id": group["group_id"] if group is not None else None,
                "callback": _address(struct.unpack_from("<I", record, 0x28)[0]),
                "context": _address(struct.unpack_from("<I", record, 0x2C)[0]),
                "context_index": struct.unpack_from("<I", record, 0x30)[0],
                "_flags_int": flags,
                "_sort_y": struct.unpack_from(
                    "<h", record, 0x1A if flags & 0x02000000 else 0x06
                )[0],
            }
        )
    return result


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in task.items() if not key.startswith("_")}


def _dispatcher_precedes(current: dict[str, Any], previous: dict[str, Any]) -> bool:
    for mask in (0xC0, 0x300):
        current_key = current["_flags_int"] & mask
        previous_key = previous["_flags_int"] & mask
        if current_key != previous_key:
            return current_key < previous_key
    current_depth = bool(current["_flags_int"] & 0x00040000)
    previous_depth = bool(previous["_flags_int"] & 0x00040000)
    if current_depth != previous_depth:
        return current_depth and not previous_depth
    if current_depth:
        return current["_sort_y"] > previous["_sort_y"]
    return False


def _reconstruct_active_slots(tasks: list[dict[str, Any]]) -> list[int]:
    ordered: list[dict[str, Any]] = []
    for task in tasks:
        if not task["_flags_int"] & 1:
            continue
        index = len(ordered)
        ordered.append(task)
        while index and _dispatcher_precedes(task, ordered[index - 1]):
            ordered[index] = ordered[index - 1]
            index -= 1
        ordered[index] = task
    return [task["slot"] for task in ordered]


def _dispatcher_state(state: Any, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    active_count = state.read_memory(ACTIVE_TASK_COUNT_ADDRESS, 1)[0]
    if active_count > TASK_SLOT_COUNT:
        raise ValueError("active task count exceeds pool")
    pointer_bytes = state.read_memory(ACTIVE_TASK_POINTER_LIST_ADDRESS, active_count * 4)
    pointers = struct.unpack(f"<{active_count}I", pointer_bytes) if active_count else ()
    slots = []
    for pointer in pointers:
        delta = pointer - TASK_POOL_BASE
        if delta < 0 or delta % TASK_RECORD_SIZE or delta // TASK_RECORD_SIZE >= TASK_SLOT_COUNT:
            raise ValueError("active task pointer is outside pool")
        slots.append(delta // TASK_RECORD_SIZE)
    reconstructed = _reconstruct_active_slots(tasks)
    return {
        "active_count": active_count,
        "pointer_list_sha256": _digest(pointer_bytes),
        "active_task_slots": slots,
        "reconstructed_active_task_slots": reconstructed,
        "exact_reconstruction": slots == reconstructed,
    }


def _runtime_offsets(state: Any) -> tuple[dict[str, Any], list[tuple[int, int]]]:
    raw = state.read_memory(RUNTIME_OFFSET_TABLE_ADDRESS, RUNTIME_OFFSET_TABLE_SIZE)
    values = struct.unpack("<8i", raw)
    pairs = [(values[index], values[index + 1]) for index in range(0, 8, 2)]
    return (
        {
            "address": _address(RUNTIME_OFFSET_TABLE_ADDRESS),
            "size": len(raw),
            "sha256": _digest(raw),
            "entries": [
                {"x_q8_8": x_value, "y_q8_8": y_value}
                for x_value, y_value in pairs
            ],
        },
        pairs,
    )


def _oam_phase(state: Any) -> tuple[dict[str, Any], bytes, bytes]:
    shadow = state.read_memory(SHADOW_OAM_BASE, OAM_BUFFER_SIZE)
    hardware = state.read_memory(HARDWARE_OAM_BASE, OAM_BUFFER_SIZE)
    differing = [
        index
        for index in range(OAM_RECORD_COUNT)
        if shadow[index * 8 : index * 8 + 8] != hardware[index * 8 : index * 8 + 8]
    ]
    thumb = bool(state.cpsr & 0x20)
    current_pc = (state.registers[15] - (4 if thumb else 8)) & 0xFFFFFFFF
    pending = state.read_memory(SUBMISSION_PENDING_ADDRESS, 1)[0]
    in_wait = SUBMISSION_WAIT_START <= current_pc <= SUBMISSION_WAIT_END
    return (
        {
            "shadow_sha256": _digest(shadow),
            "hardware_sha256": _digest(hardware),
            "full_buffer_matches_hardware": not differing,
            "differing_object_indices": differing,
            "current_pc": _address(current_pc),
            "pending_flag": pending,
            "frame_counter": state.read_memory(SUBMISSION_FRAME_COUNTER_ADDRESS, 1)[0],
            "in_pending_wait_loop": in_wait,
            "difference_inside_code_proven_pending_window": (
                bool(differing) and pending in (1, 2) and in_wait
            ),
        },
        shadow,
        hardware,
    )


def _component_for_candidate(group: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    frame = next(
        item for item in group["frames"] if item["frame_id"] == candidate["frame_id"]
    )
    return next(
        item
        for item in frame["components"]
        if item["component_index"] == candidate["component_index"]
    )


def _renderer_prediction(
    task: dict[str, Any],
    component: dict[str, Any],
    match: dict[str, Any],
    offsets: list[tuple[int, int]],
) -> dict[str, Any]:
    flags = task["_flags_int"]
    dynamic_copy = bool(flags & DYNAMIC_OBJ_COPY_FLAG)
    affine = bool(match["affine"])
    default_scale = task["scale_q8_8"] == {"x": 256, "y": 256}
    component_default_scale = (
        component["scale_x"] == 256 and component["scale_y"] == 256
    )
    runtime_x_q8_8 = 0
    runtime_y_q8_8 = 0
    offset_index = None
    if flags & 0x1000:
        offset_index = (flags & 0x6000) >> 13
        runtime_x_q8_8, runtime_y_q8_8 = offsets[offset_index]
    runtime_x = runtime_x_q8_8 >> 8
    runtime_y = runtime_y_q8_8 >> 8
    predicted_x = (
        task["anchor"]["x"]
        + task["follow_delta"]["x"]
        + component["x"]
        - runtime_x
    ) & 0x1FF
    predicted_y = (
        task["anchor"]["y"]
        + task["follow_delta"]["y"]
        + component["y"]
        - runtime_y
    ) & 0xFF
    shape_size = SHAPE_SIZE_BY_DIMENSIONS.get((component["width"], component["height"]))
    if shape_size is None:
        raise ValueError("component dimensions are not encodable")
    shape, size = shape_size
    flip_x = bool(component["horizontal_flip"] ^ bool(flags & 0x8000))
    flip_y = bool(component["vertical_flip"] ^ bool(flags & 0x10000))
    predicted_tile = (
        task["tile_base"]
        if dynamic_copy
        else task["tile_base"] + component["tile_index"]
    ) & 0x3FF
    predicted_priority = (flags >> 6) & 3
    predicted_attr0 = predicted_y | (flags & 0x0C00) | (shape << 14)
    predicted_attr1 = (
        predicted_x
        | (int(flip_x) << 12)
        | (int(flip_y) << 13)
        | (size << 14)
    )
    predicted_attr2 = (
        predicted_tile
        | (predicted_priority << 10)
        | (task["palette_bank"] << 12)
    )
    checks = {
        "unique_parent_frame_component": (
            match["frame_component_resolution"] == "unique_best_frame_component"
        ),
        "selected_frame": (
            task["animation_state"]["selected_frame_id"]
            == match["best_candidates"][0]["frame_id"]
        ),
        "non_affine": not affine,
        "default_task_scale": default_scale,
        "default_component_scale": component_default_scale,
        "zero_angles": task["angle"] == 0 and component["angle_offset"] == 0,
        "dynamic_copy_component_zero": (
            not dynamic_copy or component["component_index"] == 0
        ),
        "attr0": _h16(predicted_attr0) == match["attr0"],
        "attr1": _h16(predicted_attr1) == match["attr1"],
        "attr2": _h16(predicted_attr2) == match["attr2"],
    }
    return {
        "runtime_offset_index": offset_index,
        "runtime_offset_x_q8_8": runtime_x_q8_8,
        "runtime_offset_y_q8_8": runtime_y_q8_8,
        "runtime_offset_x": runtime_x,
        "runtime_offset_y": runtime_y,
        "dynamic_obj_copy": dynamic_copy,
        "predicted_x_raw": predicted_x,
        "predicted_y_raw": predicted_y,
        "predicted_tile_index": predicted_tile,
        "predicted_priority": predicted_priority,
        "predicted_palette_bank": task["palette_bank"],
        "predicted_attr0": _h16(predicted_attr0),
        "predicted_attr1": _h16(predicted_attr1),
        "predicted_attr2": _h16(predicted_attr2),
        "checks": checks,
        "matches_parent_oam": all(checks.values()),
    }


def _oam_view(match: dict[str, Any]) -> dict[str, Any]:
    return {
        key: match[key]
        for key in (
            "oam_index",
            "attr0",
            "attr1",
            "attr2",
            "affine",
            "width",
            "height",
            "tile_index",
            "priority",
            "palette_bank",
            "group_resolution",
            "frame_component_resolution",
        )
    }


def _correlate_matches(
    parent_matches: list[dict[str, Any]],
    active_tasks: list[dict[str, Any]],
    groups_by_id: dict[int, dict[str, Any]],
    dispatcher: dict[str, Any],
    offsets: list[tuple[int, int]],
    shadow: bytes,
    hardware: bytes,
    *,
    allow_accept: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted = []
    observations = []
    for match in parent_matches:
        group_ids = match.get("best_group_ids", [])
        candidate_rows = []
        if len(group_ids) == 1 and match.get("best_candidates"):
            group_id = group_ids[0]
            group = groups_by_id[group_id]
            for task in active_tasks:
                if task["group_id"] != group_id:
                    continue
                for candidate in match["best_candidates"]:
                    if candidate["group_id"] != group_id:
                        continue
                    component = _component_for_candidate(group, candidate)
                    prediction = _renderer_prediction(task, component, match, offsets)
                    candidate_rows.append(
                        {
                            "task": task,
                            "candidate": candidate,
                            "component": component,
                            "prediction": prediction,
                        }
                    )
        exact = [row for row in candidate_rows if row["prediction"]["matches_parent_oam"]]
        if allow_accept and len(exact) == 1:
            row = exact[0]
            task = row["task"]
            oam_index = match["oam_index"]
            start = oam_index * OAM_RECORD_SIZE
            shadow_entry = shadow[start : start + OAM_RECORD_SIZE]
            hardware_entry = hardware[start : start + OAM_RECORD_SIZE]
            ordinals = [
                index
                for index, slot in enumerate(dispatcher["active_task_slots"])
                if slot == task["slot"]
            ]
            if len(ordinals) != 1:
                raise ValueError("accepted effect task lacks unique dispatch membership")
            accepted.append(
                {
                    "resolution": "frame_consistent_renderer_identity",
                    "parent_match_sha256": _canonical_digest(match),
                    "task": _public_task(task),
                    "source": {
                        "group_id": row["candidate"]["group_id"],
                        "frame_id": row["candidate"]["frame_id"],
                        "component_index": row["candidate"]["component_index"],
                        "component_tile_index": row["component"]["tile_index"],
                    },
                    "oam": _oam_view(match),
                    "renderer_prediction": row["prediction"],
                    "dispatch_ordinal": ordinals[0],
                    "shadow_entry_hex": shadow_entry.hex(),
                    "hardware_entry_hex": hardware_entry.hex(),
                    "shadow_matches_hardware": shadow_entry == hardware_entry,
                }
            )
        else:
            observations.append(
                {
                    "resolution": (
                        "supplemental_phase_observation_not_promoted"
                        if not allow_accept
                        else "no_unique_frame_consistent_renderer_identity"
                    ),
                    "parent_match_sha256": _canonical_digest(match),
                    "oam": _oam_view(match),
                    "candidate_count": len(candidate_rows),
                    "exact_candidate_count": len(exact),
                    "task_slots": sorted({row["task"]["slot"] for row in candidate_rows}),
                }
            )
    accepted.sort(key=lambda item: item["oam"]["oam_index"])
    return accepted, observations


def _scan_state(
    root: Path,
    parent_state: dict[str, Any],
    groups: dict[tuple[int, int], dict[str, Any]],
    *,
    allow_accept: bool,
) -> dict[str, Any]:
    path = root / parent_state["path"]
    container = path.read_bytes()
    if _digest(container) != parent_state["sha256"]:
        raise ValueError(f"checkpoint differs from OAM parent: {path}")
    state = load_gba_state(path)
    pool = state.read_memory(TASK_POOL_BASE, TASK_POOL_SIZE)
    tasks = _parse_effect_tasks(pool, groups)
    dispatcher = _dispatcher_state(state, tasks)
    if not dispatcher["exact_reconstruction"]:
        raise ValueError(f"dispatcher reconstruction differs: {path}")
    offset_record, offsets = _runtime_offsets(state)
    phase, shadow, hardware = _oam_phase(state)
    active_tasks = [
        task for task in tasks if task["active_flag"] and task["group_id"] is not None
    ]
    groups_by_id = {group["group_id"]: group for group in groups.values()}
    accepted, observations = _correlate_matches(
        parent_state.get("matches", []),
        active_tasks,
        groups_by_id,
        dispatcher,
        offsets,
        shadow,
        hardware,
        allow_accept=allow_accept,
    )
    return {
        "path": parent_state["path"],
        "sha256": parent_state["sha256"],
        "parent_state_sha256": _canonical_digest(parent_state),
        "parent_match_count": len(parent_state.get("matches", [])),
        "task_pool": {
            "address": _address(TASK_POOL_BASE),
            "size": len(pool),
            "sha256": _digest(pool),
        },
        "dispatcher": dispatcher,
        "runtime_offset_table": offset_record,
        "submission_phase": phase,
        "active_effect_task_slots": [task["slot"] for task in active_tasks],
        "active_effect_tasks": [_public_task(task) for task in active_tasks],
        "accepted_binding_count": len(accepted),
        "accepted_bindings": accepted,
        "unresolved_or_phase_observations": observations,
    }


def build_bindings(root: Path | str) -> dict[str, Any]:
    root = Path(root).resolve()
    rom_path = root / ROM_RELATIVE
    rom = rom_path.read_bytes()
    if _digest(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    parent, parent_manifest, parent_hash, parent_manifest_hash = _validated_parent(root)
    source, source_hash, groups = _source_groups(root)
    _validate_source_provenance(parent, parent_manifest, source, source_hash)
    static_contract = _static_contract(rom)
    tracked = []
    supplemental = []
    errors = []
    for parent_state, destination, allow_accept in (
        *[(item, tracked, True) for item in parent["tracked_checkpoints"]],
        *[(item, supplemental, False) for item in parent["supplemental_states"]],
    ):
        try:
            destination.append(
                _scan_state(root, parent_state, groups, allow_accept=allow_accept)
            )
        except (OSError, ValueError, struct.error) as error:
            errors.append({"path": parent_state.get("path"), "error": str(error)})
    tracked.sort(key=lambda item: item["path"])
    supplemental.sort(key=lambda item: item["path"])
    all_states = tracked + supplemental
    active_tasks = [task for state in all_states for task in state["active_effect_tasks"]]
    tracked_tasks = [task for state in tracked for task in state["active_effect_tasks"]]
    supplemental_tasks = [task for state in supplemental for task in state["active_effect_tasks"]]
    accepted = [binding for state in all_states for binding in state["accepted_bindings"]]
    tracked_groups = sorted({task["group_id"] for task in tracked_tasks})
    supplemental_groups = sorted({task["group_id"] for task in supplemental_tasks})
    all_groups = sorted(set(tracked_groups) | set(supplemental_groups))
    summary = {
        "tracked_checkpoint_count": len(tracked),
        "supplemental_state_count": len(supplemental),
        "parse_error_count": len(errors),
        "tracked_parent_match_count": sum(item["parent_match_count"] for item in tracked),
        "supplemental_parent_match_count": sum(
            item["parent_match_count"] for item in supplemental
        ),
        "tracked_recognized_effect_task_count": len(tracked_tasks),
        "supplemental_recognized_effect_task_count": len(supplemental_tasks),
        "recognized_effect_task_count": len(active_tasks),
        "accepted_binding_count": len(accepted),
        "exact_dispatch_reconstruction_count": sum(
            state["dispatcher"]["exact_reconstruction"] for state in all_states
        ),
        "shadow_hardware_full_match_count": sum(
            state["submission_phase"]["full_buffer_matches_hardware"]
            for state in all_states
        ),
        "code_proven_pending_difference_count": sum(
            state["submission_phase"][
                "difference_inside_code_proven_pending_window"
            ]
            for state in all_states
        ),
        "unexplained_submission_difference_count": sum(
            not state["submission_phase"]["full_buffer_matches_hardware"]
            and not state["submission_phase"][
                "difference_inside_code_proven_pending_window"
            ]
            for state in all_states
        ),
        "tracked_observed_group_ids": tracked_groups,
        "supplemental_observed_group_ids": supplemental_groups,
        "all_persisted_observed_group_ids": all_groups,
    }
    return {
        "schema": SCHEMA,
        "rom": {
            "path": ROM_RELATIVE.as_posix(),
            "size": len(rom),
            "sha256": _digest(rom),
        },
        "parent_artifact": {
            "path": PARENT_DIRECTORY.as_posix(),
            "schema": parent["schema"],
            "payload_sha256": parent_hash,
            "manifest_sha256": parent_manifest_hash,
        },
        "source_artifact": {
            "path": SOURCE_RELATIVE.as_posix(),
            "schema": source["schema"],
            "manifest_sha256": source_hash,
            "group_count": len(groups),
        },
        "static_contract": static_contract,
        "binding_contract": {
            "group_identity": (
                "task +0x1C definition pointer and +0x20 animation pointer; "
                "+0x24 is a dynamic tile source and is excluded"
            ),
            "strict_identity": (
                "same group and selected frame, unique parent frame/component, "
                "unique active dispatcher membership, and complete attr0/1/2 reconstruction"
            ),
            "supplemental_policy": (
                "record task/frame/OAM phase correlations but do not promote supplemental "
                "pixel-A/B or affine states into the tracked natural denominator"
            ),
        },
        "scope": {
            "all_parent_states_scanned": not errors and len(all_states) == 98,
            "parent_oam_content_matches_preserved": True,
            "task_group_identity_uses_pointer_pair": True,
            "tracked_unique_non_affine_parent_matches_bound": (
                summary["accepted_binding_count"]
                == summary["tracked_parent_match_count"]
            ),
            "all_submission_differences_inside_code_proven_pending_window": (
                summary["unexplained_submission_difference_count"] == 0
            ),
            "affine_task_binding_complete": False,
            "multi_component_dynamic_copy_binding_complete": False,
            "task_to_oam_writer_or_allocation_index_traced": False,
            "all_effect_groups_runtime_observed": len(all_groups) == 18,
            "all_group_frames_runtime_observed": False,
            "cross_frame_timing_complete": False,
            "physical_gba_verified": False,
        },
        "parse_errors": errors,
        "summary": summary,
        "tracked_checkpoints": tracked,
        "supplemental_states": supplemental,
    }


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def export_bindings(root: Path | str, output: Path | str) -> dict[str, Any]:
    result = build_bindings(root)
    _write_json_atomic(Path(output), result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = export_bindings(args.root, args.output)
    except (OSError, ValueError, json.JSONDecodeError, struct.error) as error:
        print(f"battle-effect-runtime-oam-task-bindings: {error}")
        return 1
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
