#!/usr/bin/env python3
"""Promote a controlled battle-effect batch into one compact verified artifact."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
from typing import Any

try:
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "battle-effect-controlled-runtime-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
CANONICAL_ARTIFACT = "artifacts/battle-effect-controlled-runtime-v1"
PHASE_NAMES = ("binder-return", "renderer-post", "submit-post", "ack-post")
PHASE_ADDRESSES = (
    "0x0809E85A",
    "0x08063328",
    "0x08061126",
    "0x080612AA",
)
EXPECTED_PENDING = (0, 0, 1, 0)
EXPECTED_FRAMES = (0, 0, 0, 1)
CASE_ROWS = (
    ("group-03-sequence-03", 3, 3),
    ("group-04-sequence-04", 4, 4),
    ("group-06-sequence-08", 6, 8),
    ("group-07-sequence-09", 7, 9),
    ("group-08-sequence-10", 8, 10),
    ("group-09-sequence-11", 9, 11),
    ("group-10-sequence-12", 10, 12),
    ("group-12-sequence-14", 12, 14),
    ("group-13-sequence-15", 13, 15),
    ("group-15-sequence-17", 15, 17),
    ("group-16-sequence-19", 16, 19),
    ("group-17-sequence-20", 17, 20),
    ("group-18-sequence-07", 18, 7),
)
EXPECTED_CASE_IDS = tuple(row[0] for row in CASE_ROWS)
POSITIVE_GROUP_IDS = (4, 6, 7, 8, 9, 10, 12, 13, 16, 17)
NEGATIVE_GROUP_IDS = (3, 15, 18)
REPOSITORY_FILES = (
    "tools/export_battle_effect_controlled_runtime.py",
    "tools/verify_battle_effect_controlled_runtime.py",
    "tools/build_controlled_battle_effect_sequence_probe.py",
    "tools/build_save_state_runtime_probe.py",
    "tools/thumb_branch.py",
    "tools/run_battle_effect_controlled_sequence_batch.py",
    "tools/run_macos_mgba_controlled_battle_effect_capture.py",
    "tools/run_macos_mgba_battle_effect_phase_capture.py",
    "tools/run_macos_mgba_input_sequence.py",
    "tools/run_macos_mgba_replay.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_controlled_battle_effect_capture.lua",
    "tools/macos_mgba_runtime_residue.py",
    "tools/run_guarded.py",
    "tools/mgba_runtime_safety.py",
    "tools/project_resource_guard.py",
    "tools/inspect_mgba_savestate.py",
    "tools/verify_battle_effect_sequence_bindings.py",
    "tools/verify_battle_effect_sprite_animations.py",
    "tools/verify_battle_effect_resource_pairs.py",
    "tests/test_export_battle_effect_controlled_runtime.py",
    "tests/test_verify_battle_effect_controlled_runtime.py",
    "tests/test_build_controlled_battle_effect_sequence_probe.py",
    "tests/test_run_battle_effect_controlled_sequence_batch.py",
    "tests/test_mgba_controlled_battle_effect_capture_script.py",
    "tests/test_run_macos_mgba_controlled_battle_effect_capture.py",
    "sequel/content/battle-effect-controlled-runtime/unobserved-groups-v1.json",
)
SPEC = "sequel/content/battle-effect-controlled-runtime/unobserved-groups-v1.json"
SEQUENCE_CATALOG = "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
ANIMATION_CATALOG = "artifacts/battle-effect-sprite-animations-v1/manifest.json"
RESOURCE_CATALOG = "artifacts/battle-effect-resource-pairs-v1/manifest.json"
TOOLCHAIN_PROFILE = "artifacts/rom-expansion-profile-v1/profile.json"
CAPTURE_SCRIPT = "tools/mgba_controlled_battle_effect_capture.lua"
BASE_ROM = "rom/base.gba"
TASK_BASE = 0x03003BB8
TASK_SIZE = 0x3C
TASK_COUNT = 128
SCRATCH = 0x0203FF40
PENDING = 0x0300067C
ACTIVE_COUNT = 0x03005BB8
ACTIVE_POINTERS = 0x030059B8
OFFSET_TABLE = 0x03000054
SHADOW_OAM = 0x0300027C
HARDWARE_OAM = 0x07000000
DYNAMIC_COPY = 0x00400000
CAPTURE_OUTPUT_NAMES = (
    "capture-active-count.bin",
    "capture-active-pointers.bin",
    "capture-hardware-oam.bin",
    "capture-io.bin",
    "capture-phase.json",
    "capture-pram.bin",
    "capture-runtime-offsets.bin",
    "capture-shadow-oam.bin",
    "capture-submission.bin",
    "capture-task-pool.bin",
    "capture-vram.bin",
    "capture.png",
    "capture.ss9",
)
SHAPES = {
    (8, 8): (0, 0), (16, 16): (0, 1), (32, 32): (0, 2), (64, 64): (0, 3),
    (16, 8): (1, 0), (32, 8): (1, 1), (32, 16): (1, 2), (64, 32): (1, 3),
    (8, 16): (2, 0), (8, 32): (2, 1), (16, 32): (2, 2), (32, 64): (2, 3),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def is_allowed_artifact_output(path: Path) -> bool:
    """Accept the tracked destination or a managed experiment candidate only."""
    try:
        relative = path.resolve().relative_to(ROOT)
    except ValueError:
        return False
    return relative.as_posix() == CANONICAL_ARTIFACT or (
        len(relative.parts) == 6
        and relative.parts[:3] == ("build", "experiments", "active")
        and relative.parts[-1] == "final"
    )


def collect_state_members(source_root: Path) -> dict[str, Path]:
    source_root = Path(source_root)
    members: dict[str, Path] = {}
    for case_id in EXPECTED_CASE_IDS:
        for phase in PHASE_NAMES:
            source = source_root / case_id / "output" / phase / "capture.ss9"
            if not source.is_file() or source.stat().st_size == 0:
                raise ValueError(f"missing controlled savestate: {source}")
            members[f"raw/{case_id}/{phase}.ss9"] = source
    return dict(sorted(members.items()))


def collect_batch_members(source_root: Path) -> dict[str, Path]:
    """Collect the complete retained batch, including every audit-declared output."""

    source_root = Path(source_root)
    batch = source_root / "batch-audit.json"
    if not batch.is_file():
        raise ValueError(f"missing controlled batch audit: {batch}")
    members = {"source/batch-audit.json": batch}
    expected_outputs = {
        f"{phase}/{name}"
        for phase in PHASE_NAMES
        for name in CAPTURE_OUTPUT_NAMES
    }
    for case_id in EXPECTED_CASE_IDS:
        case_root = source_root / case_id
        for relative in (
            "profile.json",
            "guard-summary.json",
            "guard-summary.json.done.json",
            "output/audit.json",
        ):
            path = case_root / relative
            if not path.is_file():
                raise ValueError(f"missing retained batch member: {path}")
            members[f"source/{case_id}/{relative}"] = path
        audit = _object(case_root / "output/audit.json", f"{case_id} runtime audit")
        files = audit.get("files")
        if not isinstance(files, dict) or set(files) != expected_outputs:
            raise ValueError(f"{case_id} runtime audit output inventory mismatch")
        for relative in sorted(files):
            path = case_root / "output" / relative
            if not path.is_file():
                raise ValueError(f"missing audit-declared output: {path}")
            members[f"source/{case_id}/output/{relative}"] = path
    return dict(sorted(members.items()))


def write_deterministic_tar(sources: dict[str, Path], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(sources):
            raw = sources[name].read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mode = 0o644
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, io.BytesIO(raw))


def classify_target_presence(presence: list[bool]) -> str:
    if presence == [False, True, True, True]:
        return "verified_target_transaction"
    if presence == [False, False, False, False]:
        return "target_absent_negative"
    return "invalid_inconclusive"


def validate_state_boundary(state: Any, address: str, *, pending: int) -> None:
    """Validate serialized breakpoint state without inventing a frame-counter field."""

    if (
        not state.cpsr & 0x20
        or state.registers[15] - 2 != int(address, 16)
        or state.read_memory(SCRATCH, 4) != (1).to_bytes(4, "little")
        or state.read_memory(PENDING, 1)[0] != pending
    ):
        raise ValueError("savestate breakpoint, scratch, or pending boundary mismatch")


def _target_slots(state: Any, definition: int, animation: int) -> list[int]:
    slots = []
    for slot in range(TASK_COUNT):
        record = state.read_memory(TASK_BASE + slot * TASK_SIZE, TASK_SIZE)
        flags = struct.unpack_from("<I", record, 0)[0]
        if flags & 1 and struct.unpack_from("<II", record, 0x1C) == (definition, animation):
            slots.append(slot)
    return slots


def _active_slots(state: Any) -> list[int]:
    count = state.read_memory(ACTIVE_COUNT, 1)[0]
    if count > TASK_COUNT:
        raise ValueError("active task count exceeds pool")
    raw = state.read_memory(ACTIVE_POINTERS, count * 4)
    slots = []
    for (pointer,) in struct.iter_unpack("<I", raw):
        delta = pointer - TASK_BASE
        if delta < 0 or delta % TASK_SIZE or delta // TASK_SIZE >= TASK_COUNT:
            raise ValueError("active dispatcher pointer is outside the task pool")
        slots.append(delta // TASK_SIZE)
    if len(slots) != len(set(slots)):
        raise ValueError("active dispatcher contains duplicate tasks")
    return slots


def _task_record(state: Any, slot: int) -> dict[str, Any]:
    raw = state.read_memory(TASK_BASE + slot * TASK_SIZE, TASK_SIZE)
    flags = struct.unpack_from("<I", raw)[0]
    anchor_x, anchor_y, delta_x, delta_y, scale_x, scale_y = struct.unpack_from(
        "<hhhhhh", raw, 4
    )
    animation_id, keyframe_index, hold_timer = struct.unpack_from("<HHH", raw, 0x14)
    return {
        "flags": flags,
        "anchor_x": anchor_x,
        "anchor_y": anchor_y,
        "delta_x": delta_x,
        "delta_y": delta_y,
        "scale_x": scale_x,
        "scale_y": scale_y,
        "tile_base": struct.unpack_from("<H", raw, 0x10)[0],
        "palette_bank": raw[0x12],
        "angle": raw[0x13],
        "animation_id": animation_id,
        "keyframe_index": keyframe_index,
        "hold_timer": hold_timer,
    }


def _runtime_offsets(state: Any) -> list[tuple[int, int]]:
    words = struct.unpack("<8i", state.read_memory(OFFSET_TABLE, 32))
    return list(zip(words[::2], words[1::2], strict=True))


def _component_attributes(
    task: dict[str, Any], component: dict[str, Any], offsets: list[tuple[int, int]]
) -> tuple[int, int, int] | None:
    flags = task["flags"]
    if (
        flags & DYNAMIC_COPY
        or task["scale_x"] != 256
        or task["scale_y"] != 256
        or task["angle"] != 0
        or component.get("scale_x") != 256
        or component.get("scale_y") != 256
        or component.get("angle_offset") != 0
        or component.get("affine_mode") != 0
    ):
        return None
    size_key = (component["width"], component["height"])
    if size_key not in SHAPES:
        return None
    offset_x = offset_y = 0
    if flags & 0x1000:
        offset_x, offset_y = offsets[(flags & 0x6000) >> 13]
    local_x = component["x"]
    local_y = component["y"]
    if flags & 0x8000:
        local_x = -component["x"] - component["width"]
    if flags & 0x10000:
        local_y = -component["y"] - component["height"]
    signed_x = task["anchor_x"] + task["delta_x"] + local_x - (offset_x >> 8)
    signed_y = task["anchor_y"] + task["delta_y"] + local_y - (offset_y >> 8)
    if (
        signed_x >= 240
        or signed_x + component["width"] <= 0
        or signed_y >= 160
        or signed_y + component["height"] <= 0
    ):
        return None
    shape, size = SHAPES[size_key]
    flip_x = bool(component["horizontal_flip"] ^ bool(flags & 0x8000))
    flip_y = bool(component["vertical_flip"] ^ bool(flags & 0x10000))
    attr0 = (signed_y & 0xFF) | (flags & 0xC00) | (shape << 14)
    attr1 = (
        (signed_x & 0x1FF)
        | (int(flip_x) << 12)
        | (int(flip_y) << 13)
        | (size << 14)
    )
    attr2 = (
        ((task["tile_base"] + component["tile_index"]) & 0x3FF)
        | (((flags >> 6) & 3) << 10)
        | (task["palette_bank"] << 12)
    )
    return attr0, attr1, attr2


def derive_task_oam_bindings(
    binder: Any,
    renderer: Any,
    ack: Any,
    slot: int,
    group: dict[str, Any],
) -> dict[str, Any]:
    """Bind one target task's visible source components to submitted OAM entries."""

    task = _task_record(renderer, slot)
    active = _active_slots(renderer)
    ordinals = [index for index, active_slot in enumerate(active) if active_slot == slot]
    if len(ordinals) != 1:
        raise ValueError("target dispatcher ordinal is not unique")
    offsets = _runtime_offsets(renderer)
    binder_shadow = binder.read_memory(SHADOW_OAM, 0x400)
    renderer_shadow = renderer.read_memory(SHADOW_OAM, 0x400)
    ack_hardware = ack.read_memory(HARDWARE_OAM, 0x400)
    candidates = []
    for frame in group.get("frames", []):
        bindings = []
        clipped = []
        valid = True
        used_indices: set[int] = set()
        for component in frame.get("components", []):
            attributes = _component_attributes(task, component, offsets)
            if attributes is None:
                clipped.append(component["component_index"])
                continue
            matches = [
                index
                for index in range(128)
                if struct.unpack_from("<HHH", renderer_shadow, index * 8) == attributes
                and binder_shadow[index * 8:index * 8 + 8]
                != renderer_shadow[index * 8:index * 8 + 8]
                and ack_hardware[index * 8:index * 8 + 8]
                == renderer_shadow[index * 8:index * 8 + 8]
            ]
            if len(matches) != 1 or matches[0] in used_indices:
                valid = False
                break
            index = matches[0]
            used_indices.add(index)
            attr0, attr1, attr2 = attributes
            bindings.append(
                {
                    "frame_id": frame["frame_id"],
                    "component_index": component["component_index"],
                    "oam_index": index,
                    "attr0": f"0x{attr0:04X}",
                    "attr1": f"0x{attr1:04X}",
                    "attr2": f"0x{attr2:04X}",
                    "dispatch_ordinal": ordinals[0],
                    "renderer_shadow_entry_hex": renderer_shadow[index * 8:index * 8 + 8].hex(),
                    "ack_hardware_entry_hex": ack_hardware[index * 8:index * 8 + 8].hex(),
                }
            )
        if valid and bindings:
            candidates.append((frame["frame_id"], bindings, clipped))
    if len(candidates) != 1:
        raise ValueError("target frame/component OAM binding is not unique")
    output_frame, bindings, clipped = candidates[0]
    animation_id = task["animation_id"]
    keyframe_index = task["keyframe_index"]
    try:
        selected_frame = group["animations"][animation_id]["keyframes"][keyframe_index]["frame_id"]
    except (IndexError, KeyError, TypeError) as error:
        raise ValueError("target task animation state is invalid") from error
    return {
        "dispatch_ordinal": ordinals[0],
        "output_frame_id": output_frame,
        "post_renderer_selected_frame_id": selected_frame,
        "frame_relation": (
            "post_renderer_selected_frame"
            if selected_frame == output_frame
            else "post_renderer_task_advanced_after_output"
        ),
        "clipped_component_indices": clipped,
        "bindings": bindings,
    }


def _source_record(path: str, **extra: Any) -> dict[str, Any]:
    record = {"path": path, "sha256": _sha256(ROOT / path)}
    record.update(extra)
    return record


def _validate_raw_file_hashes(audit: dict[str, Any], output: Path) -> None:
    hashes = audit.get("files")
    if not isinstance(hashes, dict):
        raise ValueError("runtime audit file hash table is missing")
    for relative, expected in hashes.items():
        path = output / relative
        if not path.is_file() or _sha256(path) != expected:
            raise ValueError(f"runtime audit file hash mismatch: {relative}")


def _build_case(
    source_root: Path,
    batch_row: dict[str, Any],
    expected: tuple[str, int, int],
    groups: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    case_id, group_id, sequence_id = expected
    if (
        batch_row.get("case_id") != case_id
        or batch_row.get("group_id") != group_id
        or batch_row.get("sequence_id") != sequence_id
    ):
        raise ValueError(f"batch case identity mismatch: {case_id}")
    case_root = source_root / case_id
    audit_path = case_root / "output/audit.json"
    profile_path = case_root / "profile.json"
    guard_path = case_root / "guard-summary.json"
    done_path = case_root / "guard-summary.json.done.json"
    audit = _object(audit_path, f"{case_id} runtime audit")
    profile = _object(profile_path, f"{case_id} profile")
    guard = _object(guard_path, f"{case_id} guard summary")
    done = _object(done_path, f"{case_id} completion marker")
    for path, expected_hash, label in (
        (audit_path, batch_row.get("audit_sha256"), "audit"),
        (profile_path, batch_row.get("profile_sha256"), "profile"),
        (guard_path, audit.get("guard_summary_sha256"), "guard"),
    ):
        if _sha256(path) != expected_hash:
            raise ValueError(f"{case_id} {label} hash mismatch")
    if audit.get("profile_sha256") != batch_row.get("profile_sha256"):
        raise ValueError(f"{case_id} audit/profile hash mismatch")
    if (
        audit.get("schema") != "mgba-controlled-battle-effect-capture-v1"
        or audit.get("outcome") != "binder-plus-three-phase-captured"
        or audit.get("group_id") != group_id
        or audit.get("sequence_id") != sequence_id
        or audit.get("scratch_before") != 0
        or audit.get("scratch_after") != 1
    ):
        raise ValueError(f"{case_id} runtime contract mismatch")
    if (
        profile.get("group_id") != group_id
        or profile.get("sequence_id") != sequence_id
        or profile.get("source_rom_sha256") != batch_row.get("rom_sha256")
        or audit.get("rom_sha256") != audit.get("staged_rom_sha256")
    ):
        raise ValueError(f"{case_id} profile or ROM identity mismatch")
    if audit.get("rom_sha256") != batch_row.get("rom_sha256"):
        raise ValueError(f"{case_id} batch ROM hash mismatch")
    if (
        guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("protection_backend") != "posix-process-group"
    ):
        raise ValueError(f"{case_id} guard did not complete cleanly")
    residue = audit.get("runtime_residue")
    if (
        audit.get("pgid_clean") is not True
        or not isinstance(residue, dict)
        or residue.get("pgid_clean") is not True
        or residue.get("mgba_listener_clean") is not True
        or residue.get("pgid_matching_rows") != []
        or residue.get("mgba_listener_rows") != []
    ):
        raise ValueError(f"{case_id} runtime residue is not clean")
    _validate_raw_file_hashes(audit, case_root / "output")

    group = groups[group_id]
    definition = int(group["definition_pointer_table"], 16)
    animation = int(group["animation_pointer_table"], 16)
    if (
        audit.get("definition_pointer") != f"0x{definition:08X}"
        or audit.get("animation_pointer") != f"0x{animation:08X}"
    ):
        raise ValueError(f"{case_id} animation identity mismatch")
    phases = audit.get("phases")
    if not isinstance(phases, list) or len(phases) != 4:
        raise ValueError(f"{case_id} phase denominator mismatch")
    phase_records = []
    presence = []
    cycles = []
    states = []
    for phase, name, address, pending, frame in zip(
        phases, PHASE_NAMES, PHASE_ADDRESSES, EXPECTED_PENDING, EXPECTED_FRAMES,
        strict=True,
    ):
        state_path = case_root / "output" / name / "capture.ss9"
        state = load_gba_state(state_path)
        states.append(state)
        try:
            validate_state_boundary(state, address, pending=pending)
        except ValueError as error:
            raise ValueError(f"{case_id} {name} savestate boundary mismatch") from error
        if (
            phase.get("name") != name
            or phase.get("address") != address
            or phase.get("pending") != pending
            or phase.get("frame") != frame
        ):
            raise ValueError(f"{case_id} {name} savestate boundary mismatch")
        targets = _target_slots(state, definition, animation)
        if len(targets) > 1:
            raise ValueError(f"{case_id} {name} has duplicate target tasks")
        target_present = len(targets) == 1
        task_slot = targets[0] if target_present else None
        if phase.get("target_present") is not target_present or phase.get("task_slot") != task_slot:
            raise ValueError(f"{case_id} {name} target metadata mismatch")
        try:
            cycle = int(str(phase.get("cycle")), 10)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{case_id} {name} cycle is invalid") from error
        cycles.append(cycle)
        presence.append(target_present)
        phase_records.append(
            {
                "name": name,
                "address": address,
                "cycle": str(cycle),
                "frame": frame,
                "pending": pending,
                "target_present": target_present,
                "task_slot": task_slot,
                "task_address": phase.get("task_address"),
                "task_flags": phase.get("task_flags"),
                "savestate_member": f"source/{case_id}/output/{name}/capture.ss9",
                "savestate_sha256": _sha256(state_path),
                "savestate_size": state_path.stat().st_size,
            }
        )
    if not all(left < right for left, right in zip(cycles, cycles[1:])):
        raise ValueError(f"{case_id} phase cycles are not strictly increasing")
    verdict = classify_target_presence(presence)
    expected_verdict = (
        "verified_target_transaction"
        if group_id in POSITIVE_GROUP_IDS
        else "target_absent_negative"
    )
    if verdict != expected_verdict:
        raise ValueError(f"{case_id} target transaction verdict mismatch")
    if verdict == "verified_target_transaction":
        slots = [phase["task_slot"] for phase in phase_records[1:]]
        if len(set(slots)) != 1 or slots[0] != 108:
            raise ValueError(f"{case_id} target task is not stable")
        task_oam = derive_task_oam_bindings(states[0], states[1], states[3], slots[0], group)
    else:
        task_oam = None

    if done != {
        "run_id": audit.get("run_id"),
        "status": audit.get("outcome"),
        "phase_count": 4,
    }:
        raise ValueError(f"{case_id} completion marker mismatch")

    rss_value = guard.get("peak_tree_rss_mib")
    rss_valid = isinstance(rss_value, (int, float)) and not isinstance(rss_value, bool) and rss_value >= 1
    return {
        "case_id": case_id,
        "group_id": group_id,
        "sequence_id": sequence_id,
        "verdict": verdict,
        "outcome": audit["outcome"],
        "probe_rom_sha256": audit["rom_sha256"],
        "profile_sha256": _sha256(profile_path),
        "runtime_audit_sha256": _sha256(audit_path),
        "guard_summary_sha256": _sha256(guard_path),
        "source_members": {
            "profile": f"source/{case_id}/profile.json",
            "runtime_audit": f"source/{case_id}/output/audit.json",
            "guard_summary": f"source/{case_id}/guard-summary.json",
            "completion_marker": f"source/{case_id}/guard-summary.json.done.json",
        },
        "definition_pointer": f"0x{definition:08X}",
        "animation_pointer": f"0x{animation:08X}",
        "scratch_before": 0,
        "scratch_after": 1,
        "guard": {
            "reason": guard["reason"],
            "exit_code": guard["exit_code"],
            "degraded": guard["degraded"],
            "completion_trigger": guard["completion_trigger"],
            "protection_backend": guard["protection_backend"],
            "pgid_clean": True,
            "listener_clean": True,
            "peak_tree_rss_mib_sample": rss_value,
            "rss_sample_valid": rss_valid,
        },
        "task_oam": task_oam,
        "oam_bindings": [] if task_oam is None else task_oam["bindings"],
        "phases": phase_records,
    }


def export_artifact(source_root: Path, artifact_path: Path) -> dict[str, Any]:
    source_root = source_root.resolve(strict=True)
    artifact_path = artifact_path.resolve()
    if artifact_path.exists():
        raise ValueError("artifact directory must not already exist")
    if not is_allowed_artifact_output(artifact_path):
        raise ValueError(
            "artifact path must be canonical or an active experiment final directory"
        )
    batch_path = source_root / "batch-audit.json"
    batch = _object(batch_path, "controlled batch audit")
    if (
        batch.get("schema") != "battle-effect-controlled-sequence-batch-audit-v1"
        or batch.get("case_count") != 13
        or batch.get("group_ids") != [row[1] for row in CASE_ROWS]
        or batch.get("spec") != SPEC
        or batch.get("sequence_catalog") != SEQUENCE_CATALOG
        or batch.get("toolchain_profile") != TOOLCHAIN_PROFILE
    ):
        raise ValueError("controlled batch audit denominator or provenance mismatch")
    for relative, expected, label in (
        (SPEC, batch.get("spec_sha256"), "spec"),
        (SEQUENCE_CATALOG, batch.get("sequence_catalog_sha256"), "sequence catalog"),
        (TOOLCHAIN_PROFILE, batch.get("toolchain_profile_sha256"), "toolchain profile"),
    ):
        if _sha256(ROOT / relative) != expected:
            raise ValueError(f"controlled batch {label} hash mismatch")
    input_state = ROOT / str(batch.get("input_state", ""))
    if not input_state.is_file() or _sha256(input_state) != batch.get("input_state_sha256"):
        raise ValueError("controlled batch input state mismatch")
    base_rom = ROOT / BASE_ROM
    base_sha256 = _sha256(base_rom)
    base_sha1 = hashlib.sha1(base_rom.read_bytes()).hexdigest()

    animation_catalog = _object(ROOT / ANIMATION_CATALOG, "animation catalog")
    groups = {
        row["group_id"]: row
        for row in animation_catalog.get("groups", [])
        if isinstance(row, dict) and isinstance(row.get("group_id"), int)
    }
    if set(groups) != set(range(1, 19)):
        raise ValueError("animation catalog denominator mismatch")
    batch_cases = batch.get("cases")
    if not isinstance(batch_cases, list) or len(batch_cases) != len(CASE_ROWS):
        raise ValueError("controlled batch case list mismatch")
    cases = [
        _build_case(source_root, row, expected, groups)
        for row, expected in zip(batch_cases, CASE_ROWS, strict=True)
    ]

    batch_members = collect_batch_members(source_root)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{artifact_path.name}-", dir=artifact_path.parent))
    try:
        archive_path = staging / "raw-batch.tar"
        write_deterministic_tar(batch_members, archive_path)
        member_ledger = {
            name: {"sha256": _sha256(path), "size": path.stat().st_size}
            for name, path in batch_members.items()
        }
        anomalies = [
            row["case_id"]
            for row in cases
            if row["guard"]["rss_sample_valid"] is False
        ]
        if anomalies != [
            "group-04-sequence-04",
            "group-06-sequence-08",
            "group-07-sequence-09",
            "group-17-sequence-20",
        ]:
            raise ValueError("unexpected RSS sampling anomaly set")
        toolchain = _object(ROOT / TOOLCHAIN_PROFILE, "toolchain profile")
        hardware = toolchain.get("hardware_evidence", {})
        if not isinstance(hardware, dict) or hardware.get("mgba_binary_sha256") != batch.get("binary_sha256"):
            raise ValueError("batch mGBA binary differs from toolchain profile")
        capture_hashes = {row.get("phase_script_sha256") for row in (
            _object(source_root / case_id / "output/audit.json", "runtime audit")
            for case_id in EXPECTED_CASE_IDS
        )}
        if capture_hashes != {_sha256(ROOT / CAPTURE_SCRIPT)}:
            raise ValueError("controlled capture script hash mismatch across cases")
        evidence = {
            "schema": SCHEMA,
            "boundary": (
                "Supplemental zero-input controlled sequence injection. It proves the binder "
                "boundary for 13 selected cases, exact resource/task identity for 10 cases, "
                "and 25 visible task-component to submitted-OAM bindings across those 10 cases; "
                "it does not prove natural entry, renderer write-instruction ownership, "
                "all frames, blend/audio behavior, or physical GBA output."
            ),
            "source_batch_audit_sha256": _sha256(batch_path),
            "sources": {
                "spec": _source_record(SPEC),
                "base_rom": _source_record(BASE_ROM, sha1=base_sha1),
                "input_state": _source_record(batch["input_state"]),
                "sequence_catalog": _source_record(SEQUENCE_CATALOG),
                "animation_catalog": _source_record(ANIMATION_CATALOG),
                "resource_catalog": _source_record(RESOURCE_CATALOG),
                "toolchain_profile": _source_record(
                    TOOLCHAIN_PROFILE,
                    binary_sha256=batch["binary_sha256"],
                    source_commit=hardware.get("mgba_source_commit"),
                ),
                "capture_script": _source_record(CAPTURE_SCRIPT),
            },
            "archive": {
                "path": "raw-batch.tar",
                "sha256": _sha256(archive_path),
                "size": archive_path.stat().st_size,
                "member_count": len(batch_members),
                "members": member_ledger,
            },
            "coverage": {
                "positive_group_ids": list(POSITIVE_GROUP_IDS),
                "negative_group_ids": list(NEGATIVE_GROUP_IDS),
                "controlled_case_count": 13,
                "controlled_transaction_count": 10,
                "controlled_negative_count": 3,
                "existing_observed_group_ids": [1, 2, 5, 11, 14],
                "controlled_or_observed_group_ids": [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17],
                "production_natural_pixel_ab": {"numerator": 4, "denominator": 18},
                "observed_frame_phase": {"numerator": 5, "denominator": 18},
                "tracked_parent_checkpoint_count": 93,
                "uncovered_sequence_group_edges": [{"group_id": 18, "sequence_id": 18}],
                "all_entry_paths_complete": False,
            },
            "rss_sampling": {
                "valid_for_batch_statistics": False,
                "anomaly_case_ids": anomalies,
                "boundary": (
                    "Four sub-second runs were under-sampled at roughly 0.17 MiB. Per-case "
                    "samples are preserved but no batch peak, average, or upper bound is claimed."
                ),
            },
            "cases": cases,
        }
        evidence_path = staging / "evidence.json"
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        repository_hashes = {
            relative: _sha256(ROOT / relative) for relative in REPOSITORY_FILES
        }
        manifest = {
            "schema": PROMOTION_SCHEMA,
            "artifact_schema": SCHEMA,
            "artifact_status": "accepted",
            "artifact_path": CANONICAL_ARTIFACT,
            "description": "Controlled runtime evidence for 13 previously unobserved battle-effect groups, with 10 verified transactions and 3 negative results.",
            "files": {
                "evidence.json": _sha256(evidence_path),
                "raw-batch.tar": _sha256(archive_path),
            },
            "repository_files": dict(sorted(repository_hashes.items())),
            "verifier": {
                "command": [
                    "python3",
                    "tools/verify_battle_effect_controlled_runtime.py",
                    CANONICAL_ARTIFACT,
                ],
                "exit_code": 0,
                "result": "verified",
            },
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        verifier = subprocess.run(
            [sys.executable, str(ROOT / "tools/verify_battle_effect_controlled_runtime.py"), str(staging)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if verifier.returncode:
            raise ValueError("independent controlled artifact verifier failed: " + (verifier.stdout or verifier.stderr).strip())
        os.replace(staging, artifact_path)
        return evidence
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, default=ROOT / CANONICAL_ARTIFACT)
    args = parser.parse_args()
    try:
        evidence = export_artifact(args.source, args.artifact)
    except ValueError as error:
        print(f"export_battle_effect_controlled_runtime: {error}", file=sys.stderr)
        return 2
    print(json.dumps(evidence["coverage"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
