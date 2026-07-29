#!/usr/bin/env python3
"""Independently verify natural character OAM-to-task bindings."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

try:
    from tools.inspect_mgba_savestate import load_gba_state
    from tools.verify_character_runtime_oam_bindings import (
        verify_bindings as verify_parent_bindings,
    )
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state
    from verify_character_runtime_oam_bindings import (
        verify_bindings as verify_parent_bindings,
    )


SCHEMA = "character-runtime-oam-task-bindings-v1"
ROM_RELATIVE = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PARENT_DIRECTORY = Path("artifacts/character-runtime-oam-bindings-v1")
PARENT_RELATIVE = PARENT_DIRECTORY / "bindings.json"
PARENT_PROMOTION_RELATIVE = PARENT_DIRECTORY / "manifest.json"
SOURCE_MANIFEST_RELATIVE = Path(
    "artifacts/character-battle-visuals-v1/manifest.json"
)
TASK_POOL_BASE = 0x03003BB8
TASK_RECORD_SIZE = 0x3C
TASK_SLOT_COUNT = 128
TASK_POOL_SIZE = TASK_RECORD_SIZE * TASK_SLOT_COUNT
ACTIVE_TASK_COUNT_ADDRESS = 0x03005BB8
ACTIVE_TASK_POINTER_LIST_ADDRESS = 0x030059B8
SHADOW_OAM_BASE = 0x0300027C
HARDWARE_OAM_BASE = 0x07000000
OAM_RECORD_SIZE = 8
OAM_RECORD_COUNT = 128
OAM_BUFFER_SIZE = OAM_RECORD_SIZE * OAM_RECORD_COUNT
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
    "renderer_driver": (
        0x08062924,
        0x08063338,
        "5e29f07126eb06c69170c5c15a2ab28fe0e1ad86ffdd85f6dfbd4601defbee36",
    ),
    "dispatcher": (
        0x080627B0,
        0x0806291A,
        "2a9a970b7cd4227b53d46ee2274e38c0fe0927919d4fd6611923aad81355857a",
    ),
    "allocator": (
        0x080625A4,
        0x080626B0,
        "e238cd1ee159265fb8b718766f336f8d5462596954f93c7805d1bf33dd6b3c54",
    ),
    "renderer": (
        0x08062982,
        0x08063278,
        "ffc3fc22d05d94a21ebb1f6de147a891fc791d4ad35505d5a5712dd0791ddb87",
    ),
    "owner_callback": (
        0x0807AC40,
        0x0807ADB2,
        "6c14764539f4a6071dfae9d1a0943a467ff931094f94aed74fbad587788db626",
    ),
    "owner_selector": (
        0x0807AE04,
        0x0807B278,
        "d8d926ab79fa74ba96a25552b7b6da57cb7ba3fc6fdac1c9d77df2aacd748ac1",
    ),
    "owner_constructor": (
        0x0807B444,
        0x0807B632,
        "8b61749aa457f90a2ea5fee4f1982f3da9269668a4f1bec3f131090c66af0d00",
    ),
    "owner_variant_constructor": (
        0x0807B6E0,
        0x0807B758,
        "b34cfd678fe4b8abfaf5de8871a905cd566968da9f923b92ce13be58152cb44d",
    ),
}


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object_digest(value: Any) -> str:
    return _digest(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _slice_metadata(rom: bytes) -> dict[str, dict[str, Any]]:
    result = {}
    for name, (start, end, expected_hash) in CODE_SLICES.items():
        payload = rom[start - 0x08000000 : end - 0x08000000]
        if len(payload) != end - start or _digest(payload) != expected_hash:
            raise ValueError(f"{name} ROM code slice mismatch")
        result[name] = {
            "start": f"0x{start:08X}",
            "end_exclusive": f"0x{end:08X}",
            "size": len(payload),
            "sha256": expected_hash,
        }
    return result


def _static_contract(rom: bytes) -> dict[str, Any]:
    slices = _slice_metadata(rom)
    return {
        "task_pool": {
            "base": "0x03003BB8",
            "record_size": 60,
            "slot_count": 128,
            "last_slot": "0x0300597C",
        },
        "task_fields": {
            "origin_x_s16": "0x04",
            "origin_y_s16": "0x06",
            "tile_base_u16": "0x10",
            "palette_bank_u8": "0x12",
            "animation_id_u16": "0x14",
            "keyframe_index_u16": "0x16",
            "hold_timer_u16": "0x18",
            "frame_pointer_table_u32": "0x1C",
            "animation_pointer_table_u32": "0x20",
            "graphics_u32": "0x24",
            "callback_u32": "0x28",
            "context_u32": "0x2C",
            "context_index_u32": "0x30",
        },
        "dispatcher": {
            **slices["dispatcher"],
            "active_count": f"0x{ACTIVE_TASK_COUNT_ADDRESS:08X}",
            "pointer_list": f"0x{ACTIVE_TASK_POINTER_LIST_ADDRESS:08X}",
            "shadow_oam_base": f"0x{SHADOW_OAM_BASE:08X}",
            "shadow_oam_end": f"0x{SHADOW_OAM_BASE + OAM_BUFFER_SIZE:08X}",
            "pool_scan": (
                "scan all 128 records at 0x03003BB8 + index*0x3C, "
                "then dispatch the active pointer list"
            ),
            "sort_order": (
                "stable insertion order by flags 0xC0, flags 0x300, "
                "flag 0x40000, then descending task sort-y when 0x40000"
            ),
            "renderer_driver": {
                **slices["renderer_driver"],
                "active_list_builder_call": "0x08062968",
                "shadow_oam_pointer_init": "0x0806296C",
                "active_pointer_loop": "0x08062982..0x0806330C",
                "disabled_tail_fill": "0x08063310..0x08063328",
            },
        },
        "renderer": {
            **slices["renderer"],
            "task_selection": (
                "animation_id selects task+0x20 pointer; keyframe_index selects "
                "the current <frame_id,hold> item; frame_id selects task+0x1C"
            ),
            "coordinate_path": (
                "task +0x04/+0x06 plus component-local geometry reaches "
                "OAM attr1/attr0"
            ),
            "dynamic_obj_copy_path": (
                "flag 0x00400000 copies task+0x24 plus component source tile "
                "offset into sequential OBJ tiles beginning at task+0x10"
            ),
            "attr2_path": (
                "dynamic-copy OAM uses task tile base plus component output "
                "offset, task palette bank, and task priority bits"
            ),
        },
        "allocator": {
            **slices["allocator"],
            "pool_proof": (
                "reverse scan from global slot 127 at 0x0300597C by "
                "index*0x3C proves 128 slots from 0x03003BB8"
            ),
        },
        "presentation_owner_family": {
            "callback": slices["owner_callback"],
            "selector": slices["owner_selector"],
            "constructor": slices["owner_constructor"],
            "variant_constructor": slices["owner_variant_constructor"],
            "owner_table": "0x02026BE0 + 0xC4 + slot*4",
            "owner_coordinates": {
                "x_q8_8": "owner+0x20",
                "y_q8_8": "owner+0x24",
                "callback_task_context": "task+0x2C",
                "callback_offset_index": "task+0x30",
                "signed_offset_table": "0x0853E000",
            },
            "same_family_as_bound_field_tasks_proven": False,
            "boundary": (
                "the owner callback/constructor is code-proven as a separate "
                "presentation task family; the bound natural field tasks do "
                "not acquire owner identity from co-residence alone"
            ),
        },
    }


def _validated_sources(
    root: Path,
) -> tuple[
    bytes,
    dict[str, Any],
    str,
    str,
    dict[str, Any],
    str,
    dict[tuple[int, int, int], dict[str, Any]],
    dict[int, dict[str, Any]],
]:
    rom = (root / ROM_RELATIVE).read_bytes()
    if _digest(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")

    parent_path = root / PARENT_RELATIVE
    report = verify_parent_bindings(root, parent_path)
    if not report["verified"]:
        raise ValueError("parent OAM bindings are not independently verified")
    parent = _object(parent_path)
    if parent.get("schema") != "character-runtime-oam-bindings-v1":
        raise ValueError("parent OAM schema mismatch")
    parent_hash = _file_digest(parent_path)
    promotion_path = root / PARENT_PROMOTION_RELATIVE
    promotion = _object(promotion_path)
    if (
        promotion.get("schema") != "git-artifact-promotion-v1"
        or promotion.get("artifact_status") != "accepted"
        or promotion.get("artifact_schema")
        != "character-runtime-oam-bindings-v1"
        or promotion.get("files", {}).get("bindings.json") != parent_hash
    ):
        raise ValueError("parent OAM promotion mismatch")

    source_path = root / SOURCE_MANIFEST_RELATIVE
    source_raw = source_path.read_bytes()
    source = json.loads(source_raw)
    if (
        not isinstance(source, dict)
        or source.get("schema") != "character-battle-visuals-v1"
    ):
        raise ValueError("character source manifest mismatch")
    resources = {}
    resources_by_id = {}
    for resource in source["resources"]:
        descriptor = resource["descriptor"]
        triple = tuple(
            int(descriptor[field], 16)
            for field in (
                "frame_pointer_table",
                "animation_pointer_table",
                "graphics",
            )
        )
        if triple in resources:
            raise ValueError("duplicate resource pointer triple")
        resources[triple] = resource
        resources_by_id[resource["resource_id"]] = resource
    if len(resources) != source["summary"]["resource_count"]:
        raise ValueError("source resource count mismatch")
    if len(resources_by_id) != len(resources):
        raise ValueError("duplicate resource ID")
    source_hash = _digest(source_raw)
    if parent["source_artifact"]["manifest_sha256"] != source_hash:
        raise ValueError("parent/source character visual manifest hash mismatch")
    return (
        rom,
        parent,
        parent_hash,
        _file_digest(promotion_path),
        source,
        source_hash,
        resources,
        resources_by_id,
    )


def _tasks(
    pool: bytes,
    resources: dict[tuple[int, int, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(pool) != TASK_POOL_SIZE:
        raise ValueError("task pool size mismatch")
    result = []
    for slot in range(TASK_SLOT_COUNT):
        raw = pool[slot * TASK_RECORD_SIZE : (slot + 1) * TASK_RECORD_SIZE]
        flags = struct.unpack_from("<I", raw, 0)[0]
        x, y = struct.unpack_from("<hh", raw, 4)
        tile_base = struct.unpack_from("<H", raw, 0x10)[0]
        palette_bank = raw[0x12]
        animation_id, keyframe_index, hold_timer = struct.unpack_from(
            "<HHH", raw, 0x14
        )
        pointer_triple = struct.unpack_from("<III", raw, 0x1C)
        resource = resources.get(pointer_triple)
        frame_id = None
        hold_frames = None
        if resource is not None and animation_id < len(resource["animations"]):
            animation = resource["animations"][animation_id]
            if keyframe_index < len(animation["keyframes"]):
                keyframe = animation["keyframes"][keyframe_index]
                frame_id = keyframe["frame_id"]
                hold_frames = keyframe["hold_frames"]
        result.append(
            {
                "slot": slot,
                "address": f"0x{TASK_POOL_BASE + slot * TASK_RECORD_SIZE:08X}",
                "raw_sha256": _digest(raw),
                "flags": f"0x{flags:08X}",
                "origin": {"x": x, "y": y},
                "tile_base": tile_base,
                "palette_bank": palette_bank,
                "animation_state": {
                    "animation_id": animation_id,
                    "keyframe_index": keyframe_index,
                    "hold_timer": hold_timer,
                    "selected_frame_id": frame_id,
                    "selected_hold_frames": hold_frames,
                },
                "resource_pointers": {
                    "frame_pointer_table": f"0x{pointer_triple[0]:08X}",
                    "animation_pointer_table": f"0x{pointer_triple[1]:08X}",
                    "graphics": f"0x{pointer_triple[2]:08X}",
                },
                "resource_id": (
                    resource["resource_id"] if resource is not None else None
                ),
                "callback": f"0x{struct.unpack_from('<I', raw, 0x28)[0]:08X}",
                "context": f"0x{struct.unpack_from('<I', raw, 0x2C)[0]:08X}",
                "context_index": struct.unpack_from("<I", raw, 0x30)[0],
                "_flags": flags,
                "_sort_y": struct.unpack_from(
                    "<h",
                    raw,
                    0x1A if flags & 0x02000000 else 0x06,
                )[0],
            }
        )
    return result


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in task.items() if not key.startswith("_")}


def _comes_before(
    candidate: dict[str, Any],
    incumbent: dict[str, Any],
) -> bool:
    candidate_flags = candidate["_flags"]
    incumbent_flags = incumbent["_flags"]
    candidate_primary = candidate_flags & 0xC0
    incumbent_primary = incumbent_flags & 0xC0
    if candidate_primary != incumbent_primary:
        return candidate_primary < incumbent_primary
    candidate_secondary = candidate_flags & 0x300
    incumbent_secondary = incumbent_flags & 0x300
    if candidate_secondary != incumbent_secondary:
        return candidate_secondary < incumbent_secondary
    candidate_depth = bool(candidate_flags & 0x00040000)
    incumbent_depth = bool(incumbent_flags & 0x00040000)
    if candidate_depth != incumbent_depth:
        return candidate_depth
    if candidate_depth:
        return candidate["_sort_y"] > incumbent["_sort_y"]
    return False


def _expected_dispatch_slots(tasks: list[dict[str, Any]]) -> list[int]:
    active = [task for task in tasks if task["_flags"] & 1]
    for index in range(1, len(active)):
        candidate = active[index]
        cursor = index
        while cursor > 0 and _comes_before(candidate, active[cursor - 1]):
            active[cursor] = active[cursor - 1]
            cursor -= 1
        active[cursor] = candidate
    return [task["slot"] for task in active]


def _dispatch_snapshot(
    state: Any,
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    count = state.read_memory(ACTIVE_TASK_COUNT_ADDRESS, 1)[0]
    if count > TASK_SLOT_COUNT:
        raise ValueError("active task count is out of range")
    raw = state.read_memory(ACTIVE_TASK_POINTER_LIST_ADDRESS, count * 4)
    pointers = struct.unpack(f"<{count}I", raw) if count else ()
    observed_slots = []
    for pointer in pointers:
        difference = pointer - TASK_POOL_BASE
        if (
            difference < 0
            or difference % TASK_RECORD_SIZE
            or difference >= TASK_POOL_SIZE
        ):
            raise ValueError("active task pointer is invalid")
        observed_slots.append(difference // TASK_RECORD_SIZE)
    expected_slots = _expected_dispatch_slots(tasks)
    return {
        "active_count_address": f"0x{ACTIVE_TASK_COUNT_ADDRESS:08X}",
        "pointer_list_address": f"0x{ACTIVE_TASK_POINTER_LIST_ADDRESS:08X}",
        "active_count": count,
        "pointer_list_size": len(raw),
        "pointer_list_sha256": _digest(raw),
        "active_task_slots": observed_slots,
        "reconstructed_active_task_slots": expected_slots,
        "exact_reconstruction": observed_slots == expected_slots,
    }


def _oam_snapshot(state: Any) -> tuple[dict[str, Any], bytes, bytes]:
    shadow_bytes = state.read_memory(SHADOW_OAM_BASE, OAM_BUFFER_SIZE)
    hardware_bytes = state.read_memory(HARDWARE_OAM_BASE, OAM_BUFFER_SIZE)
    differences = []
    for index in range(OAM_RECORD_COUNT):
        begin = index * OAM_RECORD_SIZE
        end = begin + OAM_RECORD_SIZE
        if shadow_bytes[begin:end] != hardware_bytes[begin:end]:
            differences.append(index)
    return (
        {
            "shadow_address": f"0x{SHADOW_OAM_BASE:08X}",
            "hardware_address": f"0x{HARDWARE_OAM_BASE:08X}",
            "size": OAM_BUFFER_SIZE,
            "shadow_sha256": _digest(shadow_bytes),
            "hardware_sha256": _digest(hardware_bytes),
            "full_buffer_matches_hardware": not differences,
            "differing_object_indices": differences,
        },
        shadow_bytes,
        hardware_bytes,
    )


def _add_dispatch_oam_evidence(
    bindings: list[dict[str, Any]],
    dispatch: dict[str, Any],
    shadow: bytes,
    hardware: bytes,
) -> None:
    ordered_slots = dispatch["active_task_slots"]
    for binding in bindings:
        matching_ordinals = [
            ordinal
            for ordinal, slot in enumerate(ordered_slots)
            if slot == binding["task"]["slot"]
        ]
        if len(matching_ordinals) != 1:
            raise ValueError("bound task dispatch membership is not unique")
        oam_index = binding["oam_index"]
        if oam_index < 0 or oam_index >= OAM_RECORD_COUNT:
            raise ValueError("bound OAM index is invalid")
        offset = oam_index * OAM_RECORD_SIZE
        shadow_record = shadow[offset : offset + OAM_RECORD_SIZE]
        hardware_record = hardware[offset : offset + OAM_RECORD_SIZE]
        attr0, attr1, attr2 = struct.unpack_from("<HHH", shadow_record)
        prediction = binding["renderer_prediction"]
        matches_prediction = all(
            (
                prediction["predicted_attr0"] == f"0x{attr0:04X}",
                prediction["predicted_attr1"] == f"0x{attr1:04X}",
                prediction["predicted_attr2"] == f"0x{attr2:04X}",
            )
        )
        binding["dispatch_and_oam_observation"] = {
            "dispatch_ordinal": matching_ordinals[0],
            "task_pointer": binding["task"]["address"],
            "unique_dispatch_membership": True,
            "shadow_oam_index": oam_index,
            "shadow_oam_address": f"0x{SHADOW_OAM_BASE + offset:08X}",
            "shadow_entry_hex": shadow_record.hex(),
            "shadow_entry_sha256": _digest(shadow_record),
            "hardware_oam_address": f"0x{HARDWARE_OAM_BASE + offset:08X}",
            "hardware_entry_hex": hardware_record.hex(),
            "hardware_entry_sha256": _digest(hardware_record),
            "renderer_prediction_matches_shadow": matches_prediction,
            "shadow_matches_hardware": shadow_record == hardware_record,
        }


def _source_view(
    source: dict[str, Any],
    component: dict[str, Any],
) -> dict[str, Any]:
    result = {
        key: source[key]
        for key in (
            "resource_id",
            "frame_id",
            "component_index",
            "source_tile_offset",
            "component_x",
            "component_y",
            "component_horizontal_flip",
            "component_vertical_flip",
            "character_ids",
            "visual_slots",
            "semantics",
        )
    }
    result["component_width"] = component["width"]
    result["component_height"] = component["height"]
    return result


def _oam_view(match: dict[str, Any]) -> dict[str, Any]:
    return {
        key: match[key]
        for key in (
            "attr0",
            "attr1",
            "attr2",
            "screen_x_raw",
            "screen_y_raw",
            "width",
            "height",
            "tile_index",
            "palette_bank",
            "priority",
            "horizontal_flip",
            "vertical_flip",
            "affine",
        )
    }


def _prediction(
    task: dict[str, Any],
    source: dict[str, Any],
    component: dict[str, Any],
    match: dict[str, Any],
) -> dict[str, Any]:
    x = (task["origin"]["x"] + source["component_x"]) & 0x1FF
    y = (task["origin"]["y"] + source["component_y"]) & 0xFF
    dynamic = bool(task["_flags"] & DYNAMIC_OBJ_COPY_FLAG)
    if dynamic:
        if source["component_index"] != 0:
            raise ValueError("unverified multi-component dynamic output offset")
        tile = task["tile_base"] & 0x3FF
    else:
        tile = (
            task["tile_base"] + source["source_tile_offset"]
        ) & 0x3FF
    priority = (task["_flags"] >> 6) & 3
    dimensions = (component["width"], component["height"])
    if dimensions not in SHAPE_SIZE_BY_DIMENSIONS:
        raise ValueError("invalid GBA OBJ component dimensions")
    shape, size = SHAPE_SIZE_BY_DIMENSIONS[dimensions]
    horizontal_flip = bool(
        component["horizontal_flip"] ^ bool(task["_flags"] & 0x00008000)
    )
    vertical_flip = bool(
        component["vertical_flip"] ^ bool(task["_flags"] & 0x00010000)
    )
    attr0 = y | (shape << 14)
    attr1 = (
        x
        | (int(horizontal_flip) << 12)
        | (int(vertical_flip) << 13)
        | (size << 14)
    )
    attr2 = tile | (priority << 10) | (task["palette_bank"] << 12)
    checks = {
        "frame": (
            task["animation_state"]["selected_frame_id"] == source["frame_id"]
        ),
        "screen_x_raw": x == match["screen_x_raw"],
        "screen_y_raw": y == match["screen_y_raw"],
        "width": component["width"] == match["width"],
        "height": component["height"] == match["height"],
        "horizontal_flip": horizontal_flip == match["horizontal_flip"],
        "vertical_flip": vertical_flip == match["vertical_flip"],
        "tile_index": tile == match["tile_index"],
        "palette_bank": task["palette_bank"] == match["palette_bank"],
        "priority": priority == match["priority"],
        "non_affine": not match["affine"],
        "attr0": f"0x{attr0:04X}" == match["attr0"],
        "attr1": f"0x{attr1:04X}" == match["attr1"],
        "attr2": f"0x{attr2:04X}" == match["attr2"],
    }
    return {
        "dynamic_obj_copy": dynamic,
        "predicted_screen_x_raw": x,
        "predicted_screen_y_raw": y,
        "predicted_tile_index": tile,
        "predicted_palette_bank": task["palette_bank"],
        "predicted_priority": priority,
        "predicted_horizontal_flip": horizontal_flip,
        "predicted_vertical_flip": vertical_flip,
        "predicted_attr0": f"0x{attr0:04X}",
        "predicted_attr1": f"0x{attr1:04X}",
        "predicted_attr2": f"0x{attr2:04X}",
        "checks": checks,
        "matches_oam": all(checks.values()),
    }


def _classify(
    match: dict[str, Any],
    tasks: list[dict[str, Any]],
    resources_by_id: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    candidates = []
    for source in match["best_sources"]:
        origin = source["non_affine_task_origin_candidate"]
        if origin is None:
            continue
        for task in tasks:
            if (
                task["resource_id"] == source["resource_id"]
                and task["origin"] == origin
            ):
                candidates.append((task, source))
    if not candidates:
        return None, None
    consistent = [
        pair
        for pair in candidates
        if pair[0]["animation_state"]["selected_frame_id"]
        == pair[1]["frame_id"]
    ]
    common = {
        "oam_index": match["oam_index"],
        "parent_match_sha256": _object_digest(match),
        "oam": _oam_view(match),
    }
    if len(consistent) == 1:
        task, source = consistent[0]
        component = resources_by_id[source["resource_id"]]["frames"][
            source["frame_id"]
        ]["components"][source["component_index"]]
        prediction = _prediction(task, source, component, match)
        if not prediction["matches_oam"]:
            raise ValueError("renderer prediction mismatch")
        return (
            {
                **common,
                "resolution": "frame_consistent_renderer_identity",
                "task": _public_task(task),
                "source": _source_view(source, component),
                "renderer_prediction": prediction,
            },
            None,
        )
    return (
        None,
        {
            **common,
            "resolution": (
                "frame_state_mismatch"
                if not consistent
                else "multiple_frame_consistent_candidates"
            ),
            "candidate_count": len(candidates),
            "frame_consistent_candidate_count": len(consistent),
            "candidates": [
                {
                    "task": _public_task(task),
                    "source": _source_view(
                        source,
                        resources_by_id[source["resource_id"]]["frames"][
                            source["frame_id"]
                        ]["components"][source["component_index"]],
                    ),
                }
                for task, source in candidates
            ],
        },
    )


def _reconstruct(root: Path) -> dict[str, Any]:
    (
        rom,
        parent,
        parent_hash,
        promotion_hash,
        source,
        source_hash,
        resources,
        resources_by_id,
    ) = _validated_sources(root)
    checkpoints = []
    bound_slots = set()
    bound_resources = set()
    correlation_count = 0
    binding_count = 0
    checkpoints_with_correlations = 0
    checkpoints_with_bindings = 0
    active_pointer_total = 0
    exact_dispatch_total = 0
    full_oam_match_total = 0
    unique_dispatch_total = 0
    bound_oam_match_total = 0
    for parent_checkpoint in parent["checkpoints"]:
        state = load_gba_state(root / parent_checkpoint["path"])
        pool = state.read_memory(TASK_POOL_BASE, TASK_POOL_SIZE)
        tasks = _tasks(pool, resources)
        dispatch = _dispatch_snapshot(state, tasks)
        oam_state, shadow_oam, hardware_oam = _oam_snapshot(state)
        active_pointer_total += dispatch["active_count"]
        exact_dispatch_total += int(dispatch["exact_reconstruction"])
        full_oam_match_total += int(oam_state["full_buffer_matches_hardware"])
        bindings = []
        correlations = []
        for match in parent_checkpoint["matches"]:
            binding, correlation = _classify(
                match,
                tasks,
                resources_by_id,
            )
            if binding is not None:
                bindings.append(binding)
                binding_count += 1
                correlation_count += 1
                bound_slots.add(binding["task"]["slot"])
                bound_resources.add(binding["source"]["resource_id"])
            elif correlation is not None:
                correlations.append(correlation)
                correlation_count += 1
        bindings.sort(key=lambda row: row["oam_index"])
        correlations.sort(key=lambda row: row["oam_index"])
        _add_dispatch_oam_evidence(
            bindings,
            dispatch,
            shadow_oam,
            hardware_oam,
        )
        unique_dispatch_total += sum(
            row["dispatch_and_oam_observation"]["unique_dispatch_membership"]
            for row in bindings
        )
        bound_oam_match_total += sum(
            row["dispatch_and_oam_observation"][
                "renderer_prediction_matches_shadow"
            ]
            and row["dispatch_and_oam_observation"]["shadow_matches_hardware"]
            for row in bindings
        )
        if bindings or correlations:
            checkpoints_with_correlations += 1
        if bindings:
            checkpoints_with_bindings += 1
        checkpoints.append(
            {
                "path": parent_checkpoint["path"],
                "sha256": parent_checkpoint["sha256"],
                "task_pool": {
                    "address": "0x03003BB8",
                    "size": len(pool),
                    "sha256": _digest(pool),
                    "recognized_resource_task_count": sum(
                        task["resource_id"] is not None for task in tasks
                    ),
                },
                "dispatcher_state": dispatch,
                "shadow_oam_state": oam_state,
                "bindings": bindings,
                "correlations": correlations,
            }
        )
    summary = {
        "checkpoint_count": len(parent["checkpoints"]),
        "checkpoint_parse_error_count": 0,
        "task_pool_slot_count": 128,
        "resource_and_origin_correlation_count": correlation_count,
        "frame_consistent_renderer_identity_count": binding_count,
        "frame_inconsistent_correlation_count": correlation_count - binding_count,
        "checkpoints_with_correlations": checkpoints_with_correlations,
        "checkpoints_with_bindings": checkpoints_with_bindings,
        "bound_task_slot_count": len(bound_slots),
        "bound_resource_count": len(bound_resources),
        "active_task_pointer_count": active_pointer_total,
        "checkpoints_with_exact_dispatch_reconstruction": exact_dispatch_total,
        "checkpoints_with_shadow_hardware_full_match": full_oam_match_total,
        "bound_tasks_with_unique_dispatch_membership": unique_dispatch_total,
        "bound_shadow_hardware_slot_match_count": bound_oam_match_total,
    }
    return {
        "schema": SCHEMA,
        "rom": {
            "path": ROM_RELATIVE.as_posix(),
            "size": len(rom),
            "sha256": ROM_SHA256,
        },
        "source_oam_bindings": {
            "path": PARENT_RELATIVE.as_posix(),
            "schema": "character-runtime-oam-bindings-v1",
            "sha256": parent_hash,
            "promotion_manifest_path": PARENT_PROMOTION_RELATIVE.as_posix(),
            "promotion_manifest_sha256": promotion_hash,
        },
        "source_character_visuals": {
            "path": SOURCE_MANIFEST_RELATIVE.as_posix(),
            "schema": "character-battle-visuals-v1",
            "sha256": source_hash,
            "resource_count": source["summary"]["resource_count"],
        },
        "static_contract": _static_contract(rom),
        "checkpoints": checkpoints,
        "parse_errors": [],
        "summary": summary,
        "scope": {
            "all_tracked_checkpoints_scanned": True,
            "task_pool_layout_code_proven": True,
            "task_resource_fields_code_proven": True,
            "task_animation_state_code_proven": True,
            "task_origin_to_oam_renderer_code_proven": True,
            "frame_state_consistent_renderer_identity_observed": True,
            "active_task_pointer_list_reconstructed_all_checkpoints": (
                exact_dispatch_total == len(checkpoints)
            ),
            "bound_task_unique_dispatch_membership_observed": (
                unique_dispatch_total == binding_count
            ),
            "bound_predicted_oam_observed_in_shadow_and_hardware": (
                bound_oam_match_total == binding_count
            ),
            "shadow_oam_full_buffer_equal_to_hardware_all_checkpoints": (
                full_oam_match_total == len(checkpoints)
            ),
            "shadow_to_hardware_copy_schedule_traced": False,
            "task_to_oam_writer_or_allocation_index_traced": False,
            "component_zero_dynamic_copy_subset_complete": True,
            "multi_component_dynamic_copy_binding_complete": False,
            "all_character_oam_task_bindings_complete": False,
            "presentation_owner_family_linked_to_bound_field_tasks": False,
            "unit_ownership_proven": False,
            "camera_and_viewport_complete": False,
            "blend_window_priority_complete": False,
            "screen_space_composition_complete": False,
        },
    }


def verify_bindings(
    root: Path | str,
    bindings_path: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    bindings_path = Path(bindings_path)
    errors = []
    actual: dict[str, Any] = {}
    try:
        actual = _object(bindings_path)
        expected = _reconstruct(root)
        if actual != expected:
            errors.append(
                "bindings do not match independently reconstructed evidence"
            )
    except (OSError, ValueError, KeyError, IndexError, struct.error) as error:
        errors.append(str(error))
    summary = actual.get("summary", {}) if isinstance(actual, dict) else {}
    return {
        "schema": "character-runtime-oam-task-bindings-verification-v1",
        "verified": not errors,
        "errors": errors,
        "checkpoint_count": (
            summary.get("checkpoint_count", 0) if not errors else 0
        ),
        "binding_count": (
            summary.get("frame_consistent_renderer_identity_count", 0)
            if not errors
            else 0
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--bindings", type=Path, required=True)
    args = parser.parse_args()
    report = verify_bindings(args.root, args.bindings)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
