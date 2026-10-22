#!/usr/bin/env python3
"""Independently verify battle-effect task-to-OAM runtime bindings."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

try:
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state


SCHEMA = "battle-effect-runtime-oam-task-bindings-v1"
PARENT_SCHEMA = "battle-effect-runtime-oam-bindings-v1"
SOURCE_SCHEMA = "battle-effect-sprite-animations-v1"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PARENT_PAYLOAD = Path("artifacts/battle-effect-runtime-oam-bindings-v1/bindings.json")
PARENT_MANIFEST = Path("artifacts/battle-effect-runtime-oam-bindings-v1/manifest.json")
SOURCE_MANIFEST = Path("artifacts/battle-effect-sprite-animations-v1/manifest.json")
TASK_BASE = 0x03003BB8
TASK_SIZE = 0x3C
TASK_COUNT = 128
POOL_SIZE = TASK_SIZE * TASK_COUNT
ACTIVE_COUNT = 0x03005BB8
ACTIVE_POINTERS = 0x030059B8
OFFSET_TABLE = 0x03000054
SHADOW_OAM = 0x0300027C
HARDWARE_OAM = 0x07000000
OAM_SIZE = 1024
PENDING = 0x0300067C
FRAME_COUNTER = 0x0300067D
WAIT_START = 0x08061126
WAIT_END = 0x0806112C
DYNAMIC_COPY = 0x00400000
SHAPES = {
    (8, 8): (0, 0), (16, 16): (0, 1), (32, 32): (0, 2), (64, 64): (0, 3),
    (16, 8): (1, 0), (32, 8): (1, 1), (32, 16): (1, 2), (64, 32): (1, 3),
    (8, 16): (2, 0), (8, 32): (2, 1), (16, 32): (2, 2), (32, 64): (2, 3),
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


def _canonical(value: Any) -> str:
    return _digest(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    )


def _addr(value: int) -> str:
    return f"0x{value:08X}"


def _h16(value: int) -> str:
    return f"0x{value:04X}"


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not an object")
    return value


def _public(task: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in task.items() if not key.startswith("_")}


def _groups(source: dict[str, Any]) -> dict[tuple[int, int], dict[str, Any]]:
    result = {}
    for group in source.get("groups", []):
        pair = (
            int(group["definition_pointer_table"], 16),
            int(group["animation_pointer_table"], 16),
        )
        if pair in result:
            raise ValueError("duplicate effect pointer pair")
        result[pair] = group
    if len(result) != 18 or source.get("group_count") != 18:
        raise ValueError("effect group denominator mismatch")
    return result


def _validate_provenance(
    parent: dict[str, Any],
    parent_manifest: dict[str, Any],
    source: dict[str, Any],
    parent_hash: str,
    source_hash: str,
) -> None:
    if parent.get("schema") != PARENT_SCHEMA:
        raise ValueError("parent payload schema mismatch")
    if len(parent.get("tracked_checkpoints", [])) != 93:
        raise ValueError("parent tracked denominator is not 93")
    if len(parent.get("supplemental_states", [])) != 5:
        raise ValueError("parent supplemental denominator is not 5")
    if (
        parent_manifest.get("schema") != "git-artifact-promotion-v1"
        or parent_manifest.get("artifact_status") != "accepted"
        or parent_manifest.get("artifact_schema") != PARENT_SCHEMA
        or parent_manifest.get("files", {}).get("bindings.json") != parent_hash
    ):
        raise ValueError("parent promotion is not accepted or hash-locked")
    if source.get("schema") != SOURCE_SCHEMA:
        raise ValueError("battle-effect source schema mismatch")
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
    expected_parent_source = {
        "path": "artifacts/battle-effect-sprite-animations-v1",
        "schema": SOURCE_SCHEMA,
        "manifest_sha256": source_hash,
        "group_count": source.get("group_count"),
        "frame_count": source.get("frame_definition_count"),
        "component_count": source.get("component_count"),
        "source_component_record_count": source.get("component_count"),
    }
    if parent.get("source_artifact") != expected_parent_source:
        raise ValueError("parent source provenance differs from current source")
    promotion_source = parent_manifest.get("source", {})
    if (
        promotion_source.get("source_artifact")
        != "artifacts/battle-effect-sprite-animations-v1"
        or promotion_source.get("source_artifact_manifest_sha256") != source_hash
        or promotion_source.get("tracked_checkpoint_count") != 93
        or promotion_source.get("supplemental_state_count") != 5
    ):
        raise ValueError("parent promotion source provenance differs")


def _static_contract(rom: bytes) -> dict[str, Any]:
    slices = {}
    for name, (start, end, expected) in CODE_SLICES.items():
        payload = rom[start - 0x08000000 : end - 0x08000000]
        if len(payload) != end - start or _digest(payload) != expected:
            raise ValueError(f"{name} code slice mismatch")
        slices[name] = {
            "start": _addr(start),
            "end_exclusive": _addr(end),
            "size": len(payload),
            "sha256": expected,
        }
    return {
        "code_slices": slices,
        "task_pool": {
            "base": _addr(TASK_BASE),
            "record_size": TASK_SIZE,
            "slot_count": TASK_COUNT,
            "size": POOL_SIZE,
        },
        "task_group_identity": {
            "definition_pointer_field": "+0x1C",
            "animation_pointer_field": "+0x20",
            "identity": "unique (definition_pointer, animation_pointer) pair",
            "dynamic_tile_source_field": "+0x24",
            "dynamic_tile_source_is_group_identity": False,
        },
        "runtime_offsets": {
            "address": _addr(OFFSET_TABLE),
            "entry_count": 4,
            "entry_stride": 8,
            "selection": "(task.flags & 0x00006000) >> 13 when bit 0x1000 is set",
        },
        "submission": {
            "shadow_oam": _addr(SHADOW_OAM),
            "hardware_oam": _addr(HARDWARE_OAM),
            "pending_flag": _addr(PENDING),
            "frame_counter": _addr(FRAME_COUNTER),
            "pending_wait": f"{_addr(WAIT_START)}..{_addr(WAIT_END)}",
        },
    }


def _tasks(pool: bytes, groups: dict[tuple[int, int], dict[str, Any]]) -> list[dict[str, Any]]:
    if len(pool) != POOL_SIZE:
        raise ValueError("task pool size mismatch")
    rows = []
    for slot in range(TASK_COUNT):
        record = pool[slot * TASK_SIZE : (slot + 1) * TASK_SIZE]
        flags = struct.unpack_from("<I", record)[0]
        anchor_x, anchor_y, delta_x, delta_y, scale_x, scale_y = struct.unpack_from(
            "<hhhhhh", record, 4
        )
        animation_id, keyframe_index, hold_timer = struct.unpack_from("<HHH", record, 0x14)
        definition, animation, dynamic = struct.unpack_from("<III", record, 0x1C)
        group = groups.get((definition, animation))
        selected_frame = selected_hold = None
        if group is not None and animation_id < len(group["animations"]):
            timeline = group["animations"][animation_id]
            if keyframe_index < len(timeline["keyframes"]):
                keyframe = timeline["keyframes"][keyframe_index]
                selected_frame = keyframe["frame_id"]
                selected_hold = keyframe["hold_frames"]
        rows.append({
            "slot": slot,
            "address": _addr(TASK_BASE + slot * TASK_SIZE),
            "raw_sha256": _digest(record),
            "active_flag": bool(flags & 1),
            "flags": _addr(flags),
            "anchor": {"x": anchor_x, "y": anchor_y},
            "follow_delta": {"x": delta_x, "y": delta_y},
            "scale_q8_8": {"x": scale_x, "y": scale_y},
            "tile_base": struct.unpack_from("<H", record, 0x10)[0],
            "palette_bank": record[0x12],
            "angle": record[0x13],
            "animation_state": {
                "animation_id": animation_id,
                "keyframe_index": keyframe_index,
                "hold_timer": hold_timer,
                "selected_frame_id": selected_frame,
                "selected_hold_frames": selected_hold,
            },
            "resource_pointers": {
                "definition_pointer_table": _addr(definition),
                "animation_pointer_table": _addr(animation),
            },
            "dynamic_tile_source": _addr(dynamic),
            "group_id": group["group_id"] if group is not None else None,
            "callback": _addr(struct.unpack_from("<I", record, 0x28)[0]),
            "context": _addr(struct.unpack_from("<I", record, 0x2C)[0]),
            "context_index": struct.unpack_from("<I", record, 0x30)[0],
            "_flags": flags,
            "_sort_y": struct.unpack_from("<h", record, 0x1A if flags & 0x02000000 else 6)[0],
        })
    return rows


def _precedes(current: dict[str, Any], previous: dict[str, Any]) -> bool:
    for mask in (0xC0, 0x300):
        a, b = current["_flags"] & mask, previous["_flags"] & mask
        if a != b:
            return a < b
    a, b = bool(current["_flags"] & 0x40000), bool(previous["_flags"] & 0x40000)
    if a != b:
        return a and not b
    return a and current["_sort_y"] > previous["_sort_y"]


def _dispatcher(state: Any, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = []
    for task in tasks:
        if not task["_flags"] & 1:
            continue
        index = len(ordered)
        ordered.append(task)
        while index and _precedes(task, ordered[index - 1]):
            ordered[index] = ordered[index - 1]
            index -= 1
        ordered[index] = task
    reconstructed = [task["slot"] for task in ordered]
    count = state.read_memory(ACTIVE_COUNT, 1)[0]
    if count > TASK_COUNT:
        raise ValueError("active count exceeds task pool")
    raw = state.read_memory(ACTIVE_POINTERS, count * 4)
    pointers = struct.unpack(f"<{count}I", raw) if count else ()
    actual = []
    for pointer in pointers:
        delta = pointer - TASK_BASE
        if delta < 0 or delta % TASK_SIZE or delta // TASK_SIZE >= TASK_COUNT:
            raise ValueError("active pointer outside task pool")
        actual.append(delta // TASK_SIZE)
    return {
        "active_count": count,
        "pointer_list_sha256": _digest(raw),
        "active_task_slots": actual,
        "reconstructed_active_task_slots": reconstructed,
        "exact_reconstruction": actual == reconstructed,
    }


def _offsets(state: Any) -> tuple[dict[str, Any], list[tuple[int, int]]]:
    raw = state.read_memory(OFFSET_TABLE, 32)
    words = struct.unpack("<8i", raw)
    pairs = [(words[index], words[index + 1]) for index in range(0, 8, 2)]
    return ({
        "address": _addr(OFFSET_TABLE), "size": 32, "sha256": _digest(raw),
        "entries": [{"x_q8_8": x, "y_q8_8": y} for x, y in pairs],
    }, pairs)


def _phase(state: Any) -> tuple[dict[str, Any], bytes, bytes]:
    shadow = state.read_memory(SHADOW_OAM, OAM_SIZE)
    hardware = state.read_memory(HARDWARE_OAM, OAM_SIZE)
    differing = [index for index in range(128) if shadow[index*8:index*8+8] != hardware[index*8:index*8+8]]
    pc = (state.registers[15] - (4 if state.cpsr & 0x20 else 8)) & 0xFFFFFFFF
    pending = state.read_memory(PENDING, 1)[0]
    in_wait = WAIT_START <= pc <= WAIT_END
    return ({
        "shadow_sha256": _digest(shadow),
        "hardware_sha256": _digest(hardware),
        "full_buffer_matches_hardware": not differing,
        "differing_object_indices": differing,
        "current_pc": _addr(pc),
        "pending_flag": pending,
        "frame_counter": state.read_memory(FRAME_COUNTER, 1)[0],
        "in_pending_wait_loop": in_wait,
        "difference_inside_code_proven_pending_window": bool(differing) and pending in (1, 2) and in_wait,
    }, shadow, hardware)


def _component(group: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    frame = next(row for row in group["frames"] if row["frame_id"] == candidate["frame_id"])
    return next(row for row in frame["components"] if row["component_index"] == candidate["component_index"])


def _prediction(task: dict[str, Any], component: dict[str, Any], match: dict[str, Any], offsets: list[tuple[int, int]]) -> dict[str, Any]:
    flags = task["_flags"]
    dynamic = bool(flags & DYNAMIC_COPY)
    offset_index = None
    offset_x = offset_y = 0
    if flags & 0x1000:
        offset_index = (flags & 0x6000) >> 13
        offset_x, offset_y = offsets[offset_index]
    x = (task["anchor"]["x"] + task["follow_delta"]["x"] + component["x"] - (offset_x >> 8)) & 0x1FF
    y = (task["anchor"]["y"] + task["follow_delta"]["y"] + component["y"] - (offset_y >> 8)) & 0xFF
    shape, size = SHAPES[(component["width"], component["height"])]
    flip_x = bool(component["horizontal_flip"] ^ bool(flags & 0x8000))
    flip_y = bool(component["vertical_flip"] ^ bool(flags & 0x10000))
    tile = (task["tile_base"] if dynamic else task["tile_base"] + component["tile_index"]) & 0x3FF
    priority = (flags >> 6) & 3
    attr0 = y | (flags & 0xC00) | (shape << 14)
    attr1 = x | (int(flip_x) << 12) | (int(flip_y) << 13) | (size << 14)
    attr2 = tile | (priority << 10) | (task["palette_bank"] << 12)
    checks = {
        "unique_parent_frame_component": match["frame_component_resolution"] == "unique_best_frame_component",
        "selected_frame": task["animation_state"]["selected_frame_id"] == match["best_candidates"][0]["frame_id"],
        "non_affine": not match["affine"],
        "default_task_scale": task["scale_q8_8"] == {"x": 256, "y": 256},
        "default_component_scale": component["scale_x"] == 256 and component["scale_y"] == 256,
        "zero_angles": task["angle"] == 0 and component["angle_offset"] == 0,
        "dynamic_copy_component_zero": not dynamic or component["component_index"] == 0,
        "attr0": _h16(attr0) == match["attr0"],
        "attr1": _h16(attr1) == match["attr1"],
        "attr2": _h16(attr2) == match["attr2"],
    }
    return {
        "runtime_offset_index": offset_index,
        "runtime_offset_x_q8_8": offset_x,
        "runtime_offset_y_q8_8": offset_y,
        "runtime_offset_x": offset_x >> 8,
        "runtime_offset_y": offset_y >> 8,
        "dynamic_obj_copy": dynamic,
        "predicted_x_raw": x, "predicted_y_raw": y,
        "predicted_tile_index": tile, "predicted_priority": priority,
        "predicted_palette_bank": task["palette_bank"],
        "predicted_attr0": _h16(attr0), "predicted_attr1": _h16(attr1), "predicted_attr2": _h16(attr2),
        "checks": checks, "matches_parent_oam": all(checks.values()),
    }


def _oam(match: dict[str, Any]) -> dict[str, Any]:
    keys = ("oam_index", "attr0", "attr1", "attr2", "affine", "width", "height", "tile_index", "priority", "palette_bank", "group_resolution", "frame_component_resolution")
    return {key: match[key] for key in keys}


def _correlate(parent_matches: list[dict[str, Any]], active: list[dict[str, Any]], groups_by_id: dict[int, dict[str, Any]], dispatcher: dict[str, Any], offsets: list[tuple[int, int]], shadow: bytes, hardware: bytes, allow: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted, observations = [], []
    for match in parent_matches:
        rows = []
        group_ids = match.get("best_group_ids", [])
        if len(group_ids) == 1 and match.get("best_candidates"):
            group = groups_by_id[group_ids[0]]
            for task in active:
                if task["group_id"] != group_ids[0]:
                    continue
                for candidate in match["best_candidates"]:
                    if candidate["group_id"] != group_ids[0]:
                        continue
                    component = _component(group, candidate)
                    rows.append((task, candidate, component, _prediction(task, component, match, offsets)))
        exact = [row for row in rows if row[3]["matches_parent_oam"]]
        if allow and len(exact) == 1:
            task, candidate, component, prediction = exact[0]
            index = match["oam_index"]
            ordinals = [n for n, slot in enumerate(dispatcher["active_task_slots"]) if slot == task["slot"]]
            if len(ordinals) != 1:
                raise ValueError("binding lacks unique dispatch membership")
            accepted.append({
                "resolution": "frame_consistent_renderer_identity",
                "parent_match_sha256": _canonical(match),
                "task": _public(task),
                "source": {"group_id": candidate["group_id"], "frame_id": candidate["frame_id"], "component_index": candidate["component_index"], "component_tile_index": component["tile_index"]},
                "oam": _oam(match), "renderer_prediction": prediction,
                "dispatch_ordinal": ordinals[0],
                "shadow_entry_hex": shadow[index*8:index*8+8].hex(),
                "hardware_entry_hex": hardware[index*8:index*8+8].hex(),
                "shadow_matches_hardware": shadow[index*8:index*8+8] == hardware[index*8:index*8+8],
            })
        else:
            observations.append({
                "resolution": "supplemental_phase_observation_not_promoted" if not allow else "no_unique_frame_consistent_renderer_identity",
                "parent_match_sha256": _canonical(match), "oam": _oam(match),
                "candidate_count": len(rows), "exact_candidate_count": len(exact),
                "task_slots": sorted({row[0]["slot"] for row in rows}),
            })
    accepted.sort(key=lambda row: row["oam"]["oam_index"])
    return accepted, observations


def _expected_state(root: Path, parent: dict[str, Any], groups: dict[tuple[int, int], dict[str, Any]], allow: bool) -> dict[str, Any]:
    path = root / parent["path"]
    container = path.read_bytes()
    if _digest(container) != parent["sha256"]:
        raise ValueError("checkpoint hash differs from parent")
    state = load_gba_state(path)
    pool = state.read_memory(TASK_BASE, POOL_SIZE)
    tasks = _tasks(pool, groups)
    dispatcher = _dispatcher(state, tasks)
    if not dispatcher["exact_reconstruction"]:
        raise ValueError("dispatcher reconstruction differs")
    offset_record, offsets = _offsets(state)
    phase, shadow, hardware = _phase(state)
    active = [task for task in tasks if task["active_flag"] and task["group_id"] is not None]
    accepted, observations = _correlate(parent.get("matches", []), active, {g["group_id"]: g for g in groups.values()}, dispatcher, offsets, shadow, hardware, allow)
    return {
        "path": parent["path"], "sha256": parent["sha256"],
        "parent_state_sha256": _canonical(parent), "parent_match_count": len(parent.get("matches", [])),
        "task_pool": {"address": _addr(TASK_BASE), "size": len(pool), "sha256": _digest(pool)},
        "dispatcher": dispatcher, "runtime_offset_table": offset_record, "submission_phase": phase,
        "active_effect_task_slots": [task["slot"] for task in active],
        "active_effect_tasks": [_public(task) for task in active],
        "accepted_binding_count": len(accepted), "accepted_bindings": accepted,
        "unresolved_or_phase_observations": observations,
    }


def verify_bindings(root: Path | str, bindings: Path | str) -> dict[str, Any]:
    root = Path(root).resolve()
    errors = []
    actual: dict[str, Any] = {}
    try:
        actual = _object(Path(bindings))
        if actual.get("schema") != SCHEMA:
            raise ValueError("task binding schema mismatch")
        rom = (root / "rom/base.gba").read_bytes()
        if _digest(rom) != ROM_SHA256:
            raise ValueError("base ROM hash mismatch")
        parent_raw = (root / PARENT_PAYLOAD).read_bytes()
        parent_manifest_raw = (root / PARENT_MANIFEST).read_bytes()
        source_raw = (root / SOURCE_MANIFEST).read_bytes()
        parent = json.loads(parent_raw)
        parent_manifest = json.loads(parent_manifest_raw)
        source = json.loads(source_raw)
        _validate_provenance(
            parent,
            parent_manifest,
            source,
            _digest(parent_raw),
            _digest(source_raw),
        )
        groups = _groups(source)
        expected_tracked = [_expected_state(root, row, groups, True) for row in parent["tracked_checkpoints"]]
        expected_supplemental = [_expected_state(root, row, groups, False) for row in parent["supplemental_states"]]
        expected_tracked.sort(key=lambda row: row["path"])
        expected_supplemental.sort(key=lambda row: row["path"])
        if actual.get("tracked_checkpoints") != expected_tracked:
            errors.append("tracked task/OAM reconstruction differs")
        if actual.get("supplemental_states") != expected_supplemental:
            errors.append("supplemental task/OAM reconstruction differs")
        all_states = expected_tracked + expected_supplemental
        tracked_tasks = [task for state in expected_tracked for task in state["active_effect_tasks"]]
        supplemental_tasks = [task for state in expected_supplemental for task in state["active_effect_tasks"]]
        accepted = [binding for state in all_states for binding in state["accepted_bindings"]]
        tracked_groups = sorted({task["group_id"] for task in tracked_tasks})
        supplemental_groups = sorted({task["group_id"] for task in supplemental_tasks})
        expected_summary = {
            "tracked_checkpoint_count": 93, "supplemental_state_count": 5, "parse_error_count": 0,
            "tracked_parent_match_count": sum(row["parent_match_count"] for row in expected_tracked),
            "supplemental_parent_match_count": sum(row["parent_match_count"] for row in expected_supplemental),
            "tracked_recognized_effect_task_count": len(tracked_tasks),
            "supplemental_recognized_effect_task_count": len(supplemental_tasks),
            "recognized_effect_task_count": len(tracked_tasks) + len(supplemental_tasks),
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
            "all_persisted_observed_group_ids": sorted(set(tracked_groups) | set(supplemental_groups)),
        }
        if actual.get("summary") != expected_summary:
            errors.append("summary differs from independent reconstruction")
        if actual.get("parse_errors") != []:
            errors.append("parse errors are not empty")
        expected_identity = {
            "path": "artifacts/battle-effect-runtime-oam-bindings-v1",
            "schema": parent["schema"], "payload_sha256": _digest(parent_raw),
            "manifest_sha256": _digest(parent_manifest_raw),
        }
        if actual.get("parent_artifact") != expected_identity:
            errors.append("parent artifact identity differs")
        expected_source = {
            "path": SOURCE_MANIFEST.as_posix(),
            "schema": source["schema"],
            "manifest_sha256": _digest(source_raw),
            "group_count": len(groups),
        }
        if actual.get("source_artifact") != expected_source:
            errors.append("source artifact identity differs")
        expected_rom = {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": _digest(rom),
        }
        if actual.get("rom") != expected_rom:
            errors.append("ROM identity differs")
        if actual.get("static_contract") != _static_contract(rom):
            errors.append("static contract differs")
        expected_binding_contract = {
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
        }
        if actual.get("binding_contract") != expected_binding_contract:
            errors.append("binding contract differs")
        expected_scope = {
            "all_parent_states_scanned": True,
            "parent_oam_content_matches_preserved": True,
            "task_group_identity_uses_pointer_pair": True,
            "tracked_unique_non_affine_parent_matches_bound": (
                expected_summary["accepted_binding_count"]
                == expected_summary["tracked_parent_match_count"]
            ),
            "all_submission_differences_inside_code_proven_pending_window": (
                expected_summary["unexplained_submission_difference_count"] == 0
            ),
            "affine_task_binding_complete": False,
            "multi_component_dynamic_copy_binding_complete": False,
            "task_to_oam_writer_or_allocation_index_traced": False,
            "all_effect_groups_runtime_observed": (
                len(expected_summary["all_persisted_observed_group_ids"]) == 18
            ),
            "all_group_frames_runtime_observed": False,
            "cross_frame_timing_complete": False,
            "physical_gba_verified": False,
        }
        if actual.get("scope") != expected_scope:
            errors.append("scope claims differ from evidence")
    except (OSError, ValueError, KeyError, StopIteration, json.JSONDecodeError, struct.error) as error:
        errors.append(str(error))
    summary = actual.get("summary", {}) if not errors else {}
    return {
        "verified": not errors,
        "errors": errors,
        "tracked_checkpoints": summary.get("tracked_checkpoint_count", 0),
        "supplemental_states": summary.get("supplemental_state_count", 0),
        "recognized_effect_tasks": summary.get("recognized_effect_task_count", 0),
        "accepted_bindings": summary.get("accepted_binding_count", 0),
        "observed_group_ids": summary.get("all_persisted_observed_group_ids", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--bindings", type=Path, required=True)
    args = parser.parse_args()
    report = verify_bindings(args.root, args.bindings)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
