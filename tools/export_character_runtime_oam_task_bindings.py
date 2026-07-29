#!/usr/bin/env python3
"""Bind natural character OAM to frame-consistent live sprite tasks."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import struct
from typing import Any
import uuid

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
PARENT_SCHEMA = "character-runtime-oam-bindings-v1"
SOURCE_DIRECTORY = Path("artifacts/character-battle-visuals-v1")
SOURCE_MANIFEST_RELATIVE = SOURCE_DIRECTORY / "manifest.json"
SOURCE_SCHEMA = "character-battle-visuals-v1"

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
    "irq_dispatcher_source": {
        "start": 0x08000104,
        "end": 0x0800024C,
        "sha256": "a984224bb360571a504eff7daeb9203de192e1c72658acad2cd195f1d33a1d03",
    },
    "frame_wait": {
        "start": 0x080610E8,
        "end": 0x0806114A,
        "sha256": "931ab756083f41deb5f80be9d2346ce681c9bbdedc27d3f0387cc3e58b6734fb",
    },
    "transfer_helper": {
        "start": 0x08061150,
        "end": 0x080611E0,
        "sha256": "d740dcdafe6ec186fd361552fd81be786dcad858762ec70785a481fd9af06ef1",
    },
    "phase_ack": {
        "start": 0x08061290,
        "end": 0x080612AC,
        "sha256": "01600103bfd3c15d871fd0e539640a983381ab278632261a5c5a8661603fd565",
    },
    "vblank_callback": {
        "start": 0x080612BC,
        "end": 0x080614EC,
        "sha256": "682fb5e1ca18c9155ce5f7541d152cb925c4046d9371b79a85cac4b12bc37d42",
    },
    "irq_oam_bootstrap": {
        "start": 0x08061624,
        "end": 0x08061710,
        "sha256": "e3ba1dadf23b428fd2a39b6d9aef48b7ba9521d825ca196b37d7a93403192dff",
    },
    "renderer_driver": {
        "start": 0x08062924,
        "end": 0x08063338,
        "sha256": "5e29f07126eb06c69170c5c15a2ab28fe0e1ad86ffdd85f6dfbd4601defbee36",
    },
    "dispatcher": {
        "start": 0x080627B0,
        "end": 0x0806291A,
        "sha256": "2a9a970b7cd4227b53d46ee2274e38c0fe0927919d4fd6611923aad81355857a",
    },
    "allocator": {
        "start": 0x080625A4,
        "end": 0x080626B0,
        "sha256": "e238cd1ee159265fb8b718766f336f8d5462596954f93c7805d1bf33dd6b3c54",
    },
    "renderer": {
        "start": 0x08062982,
        "end": 0x08063278,
        "sha256": "ffc3fc22d05d94a21ebb1f6de147a891fc791d4ad35505d5a5712dd0791ddb87",
    },
    "owner_callback": {
        "start": 0x0807AC40,
        "end": 0x0807ADB2,
        "sha256": "6c14764539f4a6071dfae9d1a0943a467ff931094f94aed74fbad587788db626",
    },
    "owner_selector": {
        "start": 0x0807AE04,
        "end": 0x0807B278,
        "sha256": "d8d926ab79fa74ba96a25552b7b6da57cb7ba3fc6fdac1c9d77df2aacd748ac1",
    },
    "owner_constructor": {
        "start": 0x0807B444,
        "end": 0x0807B632,
        "sha256": "8b61749aa457f90a2ea5fee4f1982f3da9269668a4f1bec3f131090c66af0d00",
    },
    "owner_variant_constructor": {
        "start": 0x0807B6E0,
        "end": 0x0807B758,
        "sha256": "b34cfd678fe4b8abfaf5de8871a905cd566968da9f923b92ce13be58152cb44d",
    },
}


def _digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_digest(value: Any) -> str:
    return _digest_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _gba_slice(rom: bytes, start: int, end: int) -> bytes:
    offset = start - 0x08000000
    size = end - start
    if offset < 0 or size <= 0 or offset + size > len(rom):
        raise ValueError("ROM code slice is out of range")
    return rom[offset : offset + size]


def _static_contract(rom: bytes) -> dict[str, Any]:
    slices = {}
    for name, expected in CODE_SLICES.items():
        payload = _gba_slice(rom, expected["start"], expected["end"])
        actual = _digest_bytes(payload)
        if actual != expected["sha256"]:
            raise ValueError(f"{name} code slice SHA-256 mismatch")
        slices[name] = {
            "start": f"0x{expected['start']:08X}",
            "end_exclusive": f"0x{expected['end']:08X}",
            "size": len(payload),
            "sha256": actual,
        }

    callback_offset = 0x0853D5B4 - 0x08000000
    if struct.unpack_from("<I", rom, callback_offset)[0] != 0x080612BD:
        raise ValueError("VBlank callback table entry mismatch")

    return {
        "code_slices": slices,
        "task_pool": {
            "base": f"0x{TASK_POOL_BASE:08X}",
            "record_size": TASK_RECORD_SIZE,
            "slot_count": TASK_SLOT_COUNT,
            "last_slot": (
                f"0x{TASK_POOL_BASE + (TASK_SLOT_COUNT - 1) * TASK_RECORD_SIZE:08X}"
            ),
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
        "oam_submission": {
            "irq_registration": {
                "callback_table_rom": "0x0853D5B4",
                "callback_table_ram": "0x03000014",
                "vblank_entry_index": 0,
                "vblank_callback": "0x080612BD",
                "irq_dispatcher_source": "0x08000104",
                "irq_dispatcher_ram": "0x0300007C",
                "irq_vector": "0x03007FFC",
            },
            "bootstrap_copies": [
                {
                    "kind": "dma3",
                    "callsite": "0x0806162A",
                    "source": "0x08000104",
                    "destination": "0x0300007C",
                    "control": "0x84000080",
                    "size": 512,
                },
                {
                    "kind": "dma3",
                    "callsite": "0x0806163C",
                    "source": "0x0853D5B4",
                    "destination": "0x03000014",
                    "control": "0x8400000E",
                    "size": 56,
                },
            ],
            "pending_protocol": {
                "pending_flag": f"0x{SUBMISSION_PENDING_ADDRESS:08X}",
                "frame_counter": (
                    f"0x{SUBMISSION_FRAME_COUNTER_ADDRESS:08X}"
                ),
                "producer_writes": [
                    "0x0806111A value 2",
                    "0x08061124 value 1",
                ],
                "wait_loop": "0x08061126..0x0806112C",
                "acknowledgement": "0x080612A8 writes 0",
            },
            "vblank_copy_routes": [
                {
                    "kind": "cpu_fast_set",
                    "callsite": "0x08061346",
                    "source": "0x0300027C",
                    "destination": "0x07000000",
                    "control": "0x04000100",
                    "size": OAM_BUFFER_SIZE,
                },
                {
                    "kind": "dma3",
                    "callsite": "0x08061386",
                    "source": "0x0300027C",
                    "destination": "0x07000000",
                    "control": "0x84000100",
                    "size": OAM_BUFFER_SIZE,
                },
            ],
            "vblank_order": [
                "renderer call 0x08061320",
                "shadow-to-hardware copy 0x0806133E/0x08061386",
                "pending acknowledgement 0x080612A8",
            ],
            "initialization": {
                "shadow_clear": "0x080616A4..0x080616B0",
                "initial_hardware_copy": "0x080616B2..0x080616BE",
            },
        },
    }


def _validated_parent(root: Path) -> tuple[dict[str, Any], str, str]:
    path = root / PARENT_RELATIVE
    report = verify_parent_bindings(root, path)
    if not report["verified"]:
        raise ValueError(
            "parent OAM bindings failed independent verification: "
            + "; ".join(report["errors"])
        )
    parent = _read_object(path)
    if parent.get("schema") != PARENT_SCHEMA:
        raise ValueError("parent OAM schema mismatch")
    parent_hash = _digest_path(path)
    promotion_path = root / PARENT_PROMOTION_RELATIVE
    promotion = _read_object(promotion_path)
    if (
        promotion.get("schema") != "git-artifact-promotion-v1"
        or promotion.get("artifact_status") != "accepted"
        or promotion.get("artifact_schema") != PARENT_SCHEMA
        or promotion.get("files", {}).get("bindings.json") != parent_hash
    ):
        raise ValueError("parent OAM promotion identity mismatch")
    return parent, parent_hash, _digest_path(promotion_path)


def _source_resources(
    root: Path,
) -> tuple[
    dict[str, Any],
    str,
    dict[tuple[int, int, int], dict[str, Any]],
    dict[int, dict[str, Any]],
]:
    path = root / SOURCE_MANIFEST_RELATIVE
    raw = path.read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or manifest.get("schema") != SOURCE_SCHEMA:
        raise ValueError("character visual source manifest mismatch")
    resources = {}
    resources_by_id = {}
    for resource in manifest.get("resources", []):
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
            raise ValueError("duplicate character resource pointer triple")
        resources[triple] = resource
        resources_by_id[resource["resource_id"]] = resource
    if len(resources) != manifest.get("summary", {}).get("resource_count"):
        raise ValueError("character resource count mismatch")
    if len(resources_by_id) != len(resources):
        raise ValueError("duplicate character resource ID")
    return manifest, _digest_bytes(raw), resources, resources_by_id


def _parse_tasks(
    pool: bytes,
    resources: dict[tuple[int, int, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(pool) != TASK_POOL_SIZE:
        raise ValueError("task pool byte length mismatch")
    result = []
    for slot in range(TASK_SLOT_COUNT):
        record = pool[slot * TASK_RECORD_SIZE : (slot + 1) * TASK_RECORD_SIZE]
        flags = struct.unpack_from("<I", record, 0)[0]
        origin_x, origin_y = struct.unpack_from("<hh", record, 0x04)
        tile_base = struct.unpack_from("<H", record, 0x10)[0]
        palette_bank = record[0x12]
        animation_id, keyframe_index, hold_timer = struct.unpack_from(
            "<HHH", record, 0x14
        )
        pointer_triple = struct.unpack_from("<III", record, 0x1C)
        resource = resources.get(pointer_triple)
        current_frame_id = None
        current_hold = None
        if resource is not None and animation_id < len(resource["animations"]):
            animation = resource["animations"][animation_id]
            if keyframe_index < len(animation["keyframes"]):
                keyframe = animation["keyframes"][keyframe_index]
                current_frame_id = keyframe["frame_id"]
                current_hold = keyframe["hold_frames"]
        result.append(
            {
                "slot": slot,
                "address": (
                    f"0x{TASK_POOL_BASE + slot * TASK_RECORD_SIZE:08X}"
                ),
                "raw_sha256": _digest_bytes(record),
                "flags": f"0x{flags:08X}",
                "origin": {"x": origin_x, "y": origin_y},
                "tile_base": tile_base,
                "palette_bank": palette_bank,
                "animation_state": {
                    "animation_id": animation_id,
                    "keyframe_index": keyframe_index,
                    "hold_timer": hold_timer,
                    "selected_frame_id": current_frame_id,
                    "selected_hold_frames": current_hold,
                },
                "resource_pointers": {
                    "frame_pointer_table": f"0x{pointer_triple[0]:08X}",
                    "animation_pointer_table": f"0x{pointer_triple[1]:08X}",
                    "graphics": f"0x{pointer_triple[2]:08X}",
                },
                "resource_id": (
                    resource["resource_id"] if resource is not None else None
                ),
                "callback": f"0x{struct.unpack_from('<I', record, 0x28)[0]:08X}",
                "context": f"0x{struct.unpack_from('<I', record, 0x2C)[0]:08X}",
                "context_index": struct.unpack_from("<I", record, 0x30)[0],
                "_flags_int": flags,
                "_sort_y": struct.unpack_from(
                    "<h",
                    record,
                    0x1A if flags & 0x02000000 else 0x06,
                )[0],
            }
        )
    return result


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in task.items() if not key.startswith("_")}


def _dispatcher_precedes(
    current: dict[str, Any],
    previous: dict[str, Any],
) -> bool:
    current_flags = current["_flags_int"]
    previous_flags = previous["_flags_int"]
    for mask in (0xC0, 0x300):
        current_key = current_flags & mask
        previous_key = previous_flags & mask
        if current_key != previous_key:
            return current_key < previous_key
    current_depth_sort = bool(current_flags & 0x00040000)
    previous_depth_sort = bool(previous_flags & 0x00040000)
    if current_depth_sort != previous_depth_sort:
        return current_depth_sort and not previous_depth_sort
    if current_depth_sort:
        return current["_sort_y"] > previous["_sort_y"]
    return False


def _reconstruct_active_task_slots(
    tasks: list[dict[str, Any]],
) -> list[int]:
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


def _dispatcher_state(
    state: Any,
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    active_count = state.read_memory(ACTIVE_TASK_COUNT_ADDRESS, 1)[0]
    if active_count > TASK_SLOT_COUNT:
        raise ValueError("active task count exceeds global task pool")
    pointer_bytes = state.read_memory(
        ACTIVE_TASK_POINTER_LIST_ADDRESS,
        active_count * 4,
    )
    pointers = struct.unpack(f"<{active_count}I", pointer_bytes) if active_count else ()
    active_slots = []
    for pointer in pointers:
        delta = pointer - TASK_POOL_BASE
        if (
            delta < 0
            or delta % TASK_RECORD_SIZE
            or delta // TASK_RECORD_SIZE >= TASK_SLOT_COUNT
        ):
            raise ValueError("active task pointer is outside the global pool")
        active_slots.append(delta // TASK_RECORD_SIZE)
    reconstructed = _reconstruct_active_task_slots(tasks)
    return {
        "active_count_address": f"0x{ACTIVE_TASK_COUNT_ADDRESS:08X}",
        "pointer_list_address": f"0x{ACTIVE_TASK_POINTER_LIST_ADDRESS:08X}",
        "active_count": active_count,
        "pointer_list_size": len(pointer_bytes),
        "pointer_list_sha256": _digest_bytes(pointer_bytes),
        "active_task_slots": active_slots,
        "reconstructed_active_task_slots": reconstructed,
        "exact_reconstruction": active_slots == reconstructed,
    }


def _shadow_oam_state(state: Any) -> tuple[dict[str, Any], bytes, bytes]:
    shadow = state.read_memory(SHADOW_OAM_BASE, OAM_BUFFER_SIZE)
    hardware = state.read_memory(HARDWARE_OAM_BASE, OAM_BUFFER_SIZE)
    differing = [
        index
        for index in range(OAM_RECORD_COUNT)
        if shadow[
            index * OAM_RECORD_SIZE : (index + 1) * OAM_RECORD_SIZE
        ]
        != hardware[
            index * OAM_RECORD_SIZE : (index + 1) * OAM_RECORD_SIZE
        ]
    ]
    return (
        {
            "shadow_address": f"0x{SHADOW_OAM_BASE:08X}",
            "hardware_address": f"0x{HARDWARE_OAM_BASE:08X}",
            "size": OAM_BUFFER_SIZE,
            "shadow_sha256": _digest_bytes(shadow),
            "hardware_sha256": _digest_bytes(hardware),
            "full_buffer_matches_hardware": not differing,
            "differing_object_indices": differing,
        },
        shadow,
        hardware,
    )


def _submission_phase(
    state: Any,
    shadow_oam_state: dict[str, Any],
) -> dict[str, Any]:
    thumb = bool(state.cpsr & 0x20)
    current_pc = (
        state.registers[15] - (4 if thumb else 8)
    ) & 0xFFFFFFFF
    pending = state.read_memory(SUBMISSION_PENDING_ADDRESS, 1)[0]
    frame_counter = state.read_memory(
        SUBMISSION_FRAME_COUNTER_ADDRESS, 1
    )[0]
    in_wait = SUBMISSION_WAIT_START <= current_pc <= SUBMISSION_WAIT_END
    difference = not shadow_oam_state["full_buffer_matches_hardware"]
    return {
        "current_pc": f"0x{current_pc:08X}",
        "pending_flag_address": f"0x{SUBMISSION_PENDING_ADDRESS:08X}",
        "pending_flag": pending,
        "frame_counter_address": (
            f"0x{SUBMISSION_FRAME_COUNTER_ADDRESS:08X}"
        ),
        "frame_counter": frame_counter,
        "in_pending_wait_loop": in_wait,
        "shadow_hardware_difference_observed": difference,
        "difference_inside_code_proven_pending_window": (
            difference and pending in (1, 2) and in_wait
        ),
    }


def _attach_dispatch_and_oam_observations(
    bindings: list[dict[str, Any]],
    dispatcher: dict[str, Any],
    shadow: bytes,
    hardware: bytes,
) -> None:
    slots = dispatcher["active_task_slots"]
    for binding in bindings:
        task_slot = binding["task"]["slot"]
        ordinals = [
            ordinal for ordinal, slot in enumerate(slots) if slot == task_slot
        ]
        if len(ordinals) != 1:
            raise ValueError("bound task lacks unique active dispatch membership")
        oam_index = binding["oam_index"]
        if not 0 <= oam_index < OAM_RECORD_COUNT:
            raise ValueError("bound OAM index is outside the hardware table")
        start = oam_index * OAM_RECORD_SIZE
        shadow_entry = shadow[start : start + OAM_RECORD_SIZE]
        hardware_entry = hardware[start : start + OAM_RECORD_SIZE]
        attr0, attr1, attr2 = struct.unpack_from("<HHH", shadow_entry)
        prediction = binding["renderer_prediction"]
        prediction_matches_shadow = (
            prediction["predicted_attr0"] == f"0x{attr0:04X}"
            and prediction["predicted_attr1"] == f"0x{attr1:04X}"
            and prediction["predicted_attr2"] == f"0x{attr2:04X}"
        )
        binding["dispatch_and_oam_observation"] = {
            "dispatch_ordinal": ordinals[0],
            "task_pointer": binding["task"]["address"],
            "unique_dispatch_membership": True,
            "shadow_oam_index": oam_index,
            "shadow_oam_address": (
                f"0x{SHADOW_OAM_BASE + start:08X}"
            ),
            "shadow_entry_hex": shadow_entry.hex(),
            "shadow_entry_sha256": _digest_bytes(shadow_entry),
            "hardware_oam_address": (
                f"0x{HARDWARE_OAM_BASE + start:08X}"
            ),
            "hardware_entry_hex": hardware_entry.hex(),
            "hardware_entry_sha256": _digest_bytes(hardware_entry),
            "renderer_prediction_matches_shadow": prediction_matches_shadow,
            "shadow_matches_hardware": shadow_entry == hardware_entry,
        }


def _renderer_prediction(
    task: dict[str, Any],
    source: dict[str, Any],
    component: dict[str, Any],
    match: dict[str, Any],
) -> dict[str, Any]:
    predicted_x_raw = (
        task["origin"]["x"] + source["component_x"]
    ) & 0x1FF
    predicted_y_raw = (
        task["origin"]["y"] + source["component_y"]
    ) & 0xFF
    dynamic_copy = bool(task["_flags_int"] & DYNAMIC_OBJ_COPY_FLAG)
    if dynamic_copy:
        if source["component_index"] != 0:
            raise ValueError(
                "dynamic-copy binding requires preceding component output sizes"
            )
        predicted_tile = task["tile_base"] & 0x3FF
    else:
        predicted_tile = (
            task["tile_base"] + source["source_tile_offset"]
        ) & 0x3FF
    predicted_priority = (task["_flags_int"] >> 6) & 0x03
    dimensions = (component["width"], component["height"])
    if dimensions not in SHAPE_SIZE_BY_DIMENSIONS:
        raise ValueError("component dimensions cannot be encoded as GBA OBJ")
    shape, size = SHAPE_SIZE_BY_DIMENSIONS[dimensions]
    predicted_horizontal_flip = bool(
        component["horizontal_flip"] ^ bool(task["_flags_int"] & 0x00008000)
    )
    predicted_vertical_flip = bool(
        component["vertical_flip"] ^ bool(task["_flags_int"] & 0x00010000)
    )
    predicted_attr0 = predicted_y_raw | (shape << 14)
    predicted_attr1 = (
        predicted_x_raw
        | (int(predicted_horizontal_flip) << 12)
        | (int(predicted_vertical_flip) << 13)
        | (size << 14)
    )
    predicted_attr2 = (
        predicted_tile
        | (predicted_priority << 10)
        | (task["palette_bank"] << 12)
    )
    checks = {
        "frame": (
            task["animation_state"]["selected_frame_id"] == source["frame_id"]
        ),
        "screen_x_raw": predicted_x_raw == match["screen_x_raw"],
        "screen_y_raw": predicted_y_raw == match["screen_y_raw"],
        "width": component["width"] == match["width"],
        "height": component["height"] == match["height"],
        "horizontal_flip": (
            predicted_horizontal_flip == match["horizontal_flip"]
        ),
        "vertical_flip": predicted_vertical_flip == match["vertical_flip"],
        "tile_index": predicted_tile == match["tile_index"],
        "palette_bank": task["palette_bank"] == match["palette_bank"],
        "priority": predicted_priority == match["priority"],
        "non_affine": not match["affine"],
        "attr0": f"0x{predicted_attr0:04X}" == match["attr0"],
        "attr1": f"0x{predicted_attr1:04X}" == match["attr1"],
        "attr2": f"0x{predicted_attr2:04X}" == match["attr2"],
    }
    return {
        "dynamic_obj_copy": dynamic_copy,
        "predicted_screen_x_raw": predicted_x_raw,
        "predicted_screen_y_raw": predicted_y_raw,
        "predicted_tile_index": predicted_tile,
        "predicted_palette_bank": task["palette_bank"],
        "predicted_priority": predicted_priority,
        "predicted_horizontal_flip": predicted_horizontal_flip,
        "predicted_vertical_flip": predicted_vertical_flip,
        "predicted_attr0": f"0x{predicted_attr0:04X}",
        "predicted_attr1": f"0x{predicted_attr1:04X}",
        "predicted_attr2": f"0x{predicted_attr2:04X}",
        "checks": checks,
        "matches_oam": all(checks.values()),
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


def _correlate_match(
    match: dict[str, Any],
    tasks: list[dict[str, Any]],
    resources_by_id: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    candidates = []
    for source in match["best_sources"]:
        origin = source.get("non_affine_task_origin_candidate")
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
        (task, source)
        for task, source in candidates
        if task["animation_state"]["selected_frame_id"] == source["frame_id"]
    ]
    common = {
        "oam_index": match["oam_index"],
        "parent_match_sha256": _canonical_digest(match),
        "oam": _oam_view(match),
    }
    if len(consistent) == 1:
        task, source = consistent[0]
        component = resources_by_id[source["resource_id"]]["frames"][
            source["frame_id"]
        ]["components"][source["component_index"]]
        prediction = _renderer_prediction(task, source, component, match)
        if not prediction["matches_oam"]:
            raise ValueError("frame-consistent task does not reproduce OAM")
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

    reason = (
        "frame_state_mismatch"
        if not consistent
        else "multiple_frame_consistent_candidates"
    )
    return (
        None,
        {
            **common,
            "resolution": reason,
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


def build_bindings(root: Path | str) -> dict[str, Any]:
    root = Path(root).resolve()
    rom_path = root / ROM_RELATIVE
    rom = rom_path.read_bytes()
    if _digest_bytes(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")

    parent, parent_hash, parent_promotion_hash = _validated_parent(root)
    source, source_hash, resources, resources_by_id = _source_resources(root)
    if parent["source_artifact"]["manifest_sha256"] != source_hash:
        raise ValueError("parent/source character visual manifest hash mismatch")
    static_contract = _static_contract(rom)
    checkpoints = []
    parse_errors = []
    correlation_count = 0
    binding_count = 0
    checkpoints_with_correlations = 0
    checkpoints_with_bindings = 0
    bound_slots = set()
    bound_resources = set()
    active_task_pointer_count = 0
    exact_dispatch_reconstruction_count = 0
    shadow_hardware_full_match_count = 0
    unique_dispatch_membership_count = 0
    bound_shadow_hardware_slot_match_count = 0
    pending_submission_count = 0
    pending_wait_count = 0
    differing_in_pending_wait_count = 0
    differing_outside_pending_wait_count = 0

    for parent_checkpoint in parent["checkpoints"]:
        path = root / parent_checkpoint["path"]
        try:
            state = load_gba_state(path)
            pool = state.read_memory(TASK_POOL_BASE, TASK_POOL_SIZE)
            tasks = _parse_tasks(pool, resources)
            dispatcher_state = _dispatcher_state(state, tasks)
            (
                shadow_oam_state,
                shadow_oam,
                hardware_oam,
            ) = _shadow_oam_state(state)
            submission_phase = _submission_phase(
                state,
                shadow_oam_state,
            )
            active_task_pointer_count += dispatcher_state["active_count"]
            exact_dispatch_reconstruction_count += int(
                dispatcher_state["exact_reconstruction"]
            )
            shadow_hardware_full_match_count += int(
                shadow_oam_state["full_buffer_matches_hardware"]
            )
            pending_submission_count += int(
                submission_phase["pending_flag"] in (1, 2)
            )
            pending_wait_count += int(
                submission_phase["in_pending_wait_loop"]
            )
            differing_in_pending_wait_count += int(
                submission_phase[
                    "difference_inside_code_proven_pending_window"
                ]
            )
            differing_outside_pending_wait_count += int(
                submission_phase["shadow_hardware_difference_observed"]
                and not submission_phase[
                    "difference_inside_code_proven_pending_window"
                ]
            )
            bindings = []
            correlations = []
            for match in parent_checkpoint["matches"]:
                binding, correlation = _correlate_match(
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
            _attach_dispatch_and_oam_observations(
                bindings,
                dispatcher_state,
                shadow_oam,
                hardware_oam,
            )
            unique_dispatch_membership_count += sum(
                row["dispatch_and_oam_observation"][
                    "unique_dispatch_membership"
                ]
                for row in bindings
            )
            bound_shadow_hardware_slot_match_count += sum(
                row["dispatch_and_oam_observation"][
                    "renderer_prediction_matches_shadow"
                ]
                and row["dispatch_and_oam_observation"][
                    "shadow_matches_hardware"
                ]
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
                        "address": f"0x{TASK_POOL_BASE:08X}",
                        "size": len(pool),
                        "sha256": _digest_bytes(pool),
                        "recognized_resource_task_count": sum(
                            task["resource_id"] is not None for task in tasks
                        ),
                    },
                    "dispatcher_state": dispatcher_state,
                    "shadow_oam_state": shadow_oam_state,
                    "submission_phase": submission_phase,
                    "bindings": bindings,
                    "correlations": correlations,
                }
            )
        except Exception as error:
            parse_errors.append(
                {"path": parent_checkpoint["path"], "error": str(error)}
            )

    summary = {
        "checkpoint_count": len(parent["checkpoints"]),
        "checkpoint_parse_error_count": len(parse_errors),
        "task_pool_slot_count": TASK_SLOT_COUNT,
        "resource_and_origin_correlation_count": correlation_count,
        "frame_consistent_renderer_identity_count": binding_count,
        "frame_inconsistent_correlation_count": correlation_count - binding_count,
        "checkpoints_with_correlations": checkpoints_with_correlations,
        "checkpoints_with_bindings": checkpoints_with_bindings,
        "bound_task_slot_count": len(bound_slots),
        "bound_resource_count": len(bound_resources),
        "active_task_pointer_count": active_task_pointer_count,
        "checkpoints_with_exact_dispatch_reconstruction": (
            exact_dispatch_reconstruction_count
        ),
        "checkpoints_with_shadow_hardware_full_match": (
            shadow_hardware_full_match_count
        ),
        "bound_tasks_with_unique_dispatch_membership": (
            unique_dispatch_membership_count
        ),
        "bound_shadow_hardware_slot_match_count": (
            bound_shadow_hardware_slot_match_count
        ),
        "checkpoints_with_pending_submission_flag": (
            pending_submission_count
        ),
        "checkpoints_in_pending_wait_loop": pending_wait_count,
        "differing_checkpoints_in_pending_wait_loop": (
            differing_in_pending_wait_count
        ),
        "differing_checkpoints_outside_pending_wait_loop": (
            differing_outside_pending_wait_count
        ),
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
            "schema": PARENT_SCHEMA,
            "sha256": parent_hash,
            "promotion_manifest_path": PARENT_PROMOTION_RELATIVE.as_posix(),
            "promotion_manifest_sha256": parent_promotion_hash,
        },
        "source_character_visuals": {
            "path": SOURCE_MANIFEST_RELATIVE.as_posix(),
            "schema": SOURCE_SCHEMA,
            "sha256": source_hash,
            "resource_count": source["summary"]["resource_count"],
        },
        "static_contract": static_contract,
        "checkpoints": checkpoints,
        "parse_errors": parse_errors,
        "summary": summary,
        "scope": {
            "all_tracked_checkpoints_scanned": (
                len(checkpoints) == len(parent["checkpoints"])
                and not parse_errors
            ),
            "task_pool_layout_code_proven": True,
            "task_resource_fields_code_proven": True,
            "task_animation_state_code_proven": True,
            "task_origin_to_oam_renderer_code_proven": True,
            "frame_state_consistent_renderer_identity_observed": True,
            "active_task_pointer_list_reconstructed_all_checkpoints": (
                exact_dispatch_reconstruction_count == len(checkpoints)
            ),
            "bound_task_unique_dispatch_membership_observed": (
                unique_dispatch_membership_count == binding_count
            ),
            "bound_predicted_oam_observed_in_shadow_and_hardware": (
                bound_shadow_hardware_slot_match_count == binding_count
            ),
            "shadow_oam_full_buffer_equal_to_hardware_all_checkpoints": (
                shadow_hardware_full_match_count == len(checkpoints)
            ),
            "shadow_to_hardware_copy_schedule_traced": False,
            "shadow_to_hardware_copy_routes_code_verified": True,
            "vblank_submission_phase_protocol_code_verified": True,
            "shadow_hardware_differences_observed_only_in_pending_wait_window": (
                differing_outside_pending_wait_count == 0
            ),
            "exact_previous_frame_hardware_identity_proven": False,
            "all_hardware_oam_writers_exhaustively_proven": False,
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


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def export_bindings(root: Path | str, output: Path | str) -> dict[str, Any]:
    result = build_bindings(root)
    _write_json_atomic(Path(output), result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = export_bindings(args.root, args.output)
    except (OSError, ValueError, KeyError, IndexError, struct.error) as error:
        print(f"character-runtime-oam-task-bindings: {error}")
        return 1
    print(
        json.dumps(
            {"schema": result["schema"], "summary": result["summary"]},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
