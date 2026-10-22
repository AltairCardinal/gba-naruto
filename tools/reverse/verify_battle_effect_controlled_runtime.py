#!/usr/bin/env python3
"""Independently verify the controlled battle-effect runtime batch artifact."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import struct
import tarfile
import tempfile
from typing import Any

try:
    from tools.build_controlled_battle_effect_sequence_probe import SCRATCH, build_probe
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    from build_controlled_battle_effect_sequence_probe import SCRATCH, build_probe
    from inspect_mgba_savestate import load_gba_state


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "battle-effect-controlled-runtime-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PHASES = (
    ("binder-return", "0x0809E85A", 0, 0),
    ("renderer-post", "0x08063328", 0, 0),
    ("submit-post", "0x08061126", 1, 0),
    ("ack-post", "0x080612AA", 0, 1),
)
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
POSITIVE_GROUP_IDS = (4, 6, 7, 8, 9, 10, 12, 13, 16, 17)
NEGATIVE_GROUP_IDS = (3, 15, 18)
OBSERVED_GROUP_IDS = (1, 2, 5, 11, 14)
CONTROLLED_OR_OBSERVED = (1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17)
PHASE_NAMES = tuple(row[0] for row in PHASES)
EXPECTED_MEMBER_NAMES = tuple(
    sorted(
        ["source/batch-audit.json"]
        + [
            f"source/{case_id}/{relative}"
            for case_id, _, _ in CASE_ROWS
            for relative in (
                "profile.json",
                "guard-summary.json",
                "guard-summary.json.done.json",
                "output/audit.json",
            )
        ]
        + [
            f"source/{case_id}/output/{phase}/{name}"
            for case_id, _, _ in CASE_ROWS
            for phase in PHASE_NAMES
            for name in (
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
        ]
    )
)
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
BASE_ROM = "rom/base.gba"
TASK_BASE = 0x03003BB8
TASK_SIZE = 0x3C
TASK_COUNT = 128
ACTIVE_COUNT = 0x03005BB8
ACTIVE_POINTERS = 0x030059B8
SHADOW_OAM = 0x0300027C
HARDWARE_OAM = 0x07000000
PENDING = 0x0300067C
OBJ_VRAM = 0x06010000
OBJ_PRAM = 0x05000200
DYNAMIC_COPY = 0x00400000
OFFSET_TABLE = 0x03000054
TRUSTED_SOURCE_SHA256 = {
    "spec": "359c1ec0f6c4750433a92d1c9a327a22dfc483fdbb7df79e4faf88b446c3e408",
    "base_rom": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
    "input_state": "7d6796a767d574f5f7a91935c3c1e65ce44edbc51aa5a6b587784d4730bbe94f",
    "sequence_catalog": "ec8f41571bb132577ecb7bc57f946a85f219b4c05f3697c89b75be73385b0c73",
    "animation_catalog": "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848",
    "resource_catalog": "716ac580326077127797c634d1f19bbc0aadcfd4db9c577730728b112f002963",
    "toolchain_profile": "e21d375914dda3c20b05ccec45c39406db310609e69ee19d04dfa342f4b70287",
    "capture_script": "81e9639dedfd3517fcc00032a222b87a870ec6db6396aef9bc41e246aab7ec41",
}
SHAPES = {
    (8, 8): (0, 0), (16, 16): (0, 1), (32, 32): (0, 2), (64, 64): (0, 3),
    (16, 8): (1, 0), (32, 8): (1, 1), (32, 16): (1, 2), (64, 32): (1, 3),
    (8, 16): (2, 0), (8, 32): (2, 1), (16, 32): (2, 2), (32, 64): (2, 3),
}


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _json_payload(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid archived {label}") from error
    if not isinstance(value, dict):
        raise ValueError(f"archived {label} must be an object")
    return value


def validate_trusted_source_hashes(actual: dict[str, str]) -> None:
    if actual != TRUSTED_SOURCE_SHA256:
        raise ValueError("trusted source hash mismatch")


def _repository_file(raw: Any, expected: str, label: str) -> Path:
    if raw != expected:
        raise ValueError(f"{label} path mismatch")
    relative = Path(expected)
    path = (ROOT / relative).resolve(strict=True)
    path.relative_to(ROOT)
    if not path.is_file():
        raise ValueError(f"{label} is not a regular file")
    return path


def _canonical_tar(payloads: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(payloads):
            raw = payloads[name]
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mode = 0o644
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, io.BytesIO(raw))
    return output.getvalue()


def read_safe_tar(path: Path) -> dict[str, bytes]:
    """Read a deterministic regular-only tar, rejecting traversal and aliases."""

    payloads: dict[str, bytes] = {}
    with tarfile.open(path, "r:") as archive:
        for member in archive.getmembers():
            name = member.name
            pure = PurePosixPath(name)
            if (
                not name
                or pure.is_absolute()
                or ".." in pure.parts
                or "" in pure.parts
                or name in payloads
            ):
                raise ValueError("unsafe or duplicate tar member path")
            if not member.isfile() or member.linkname or member.pax_headers:
                raise ValueError("tar members must be regular files without extensions")
            if (
                member.mode != 0o644
                or member.mtime != 0
                or member.uid != 0
                or member.gid != 0
                or member.uname
                or member.gname
            ):
                raise ValueError("tar member metadata is not deterministic")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError("tar member cannot be read")
            raw = extracted.read()
            if len(raw) != member.size:
                raise ValueError("tar member size mismatch")
            payloads[name] = raw
    if path.read_bytes() != _canonical_tar(payloads):
        raise ValueError("tar byte stream is not canonical USTAR")
    return payloads


def validate_coverage_contract(coverage: dict[str, Any]) -> None:
    expected = {
        "positive_group_ids": list(POSITIVE_GROUP_IDS),
        "negative_group_ids": list(NEGATIVE_GROUP_IDS),
        "controlled_case_count": 13,
        "controlled_transaction_count": 10,
        "controlled_negative_count": 3,
        "existing_observed_group_ids": list(OBSERVED_GROUP_IDS),
        "controlled_or_observed_group_ids": list(CONTROLLED_OR_OBSERVED),
        "production_natural_pixel_ab": {"numerator": 4, "denominator": 18},
        "observed_frame_phase": {"numerator": 5, "denominator": 18},
        "tracked_parent_checkpoint_count": 93,
        "uncovered_sequence_group_edges": [{"group_id": 18, "sequence_id": 18}],
        "all_entry_paths_complete": False,
    }
    if coverage != expected:
        raise ValueError("controlled coverage contract or natural metric boundary mismatch")


def _active_slots(state: Any) -> list[int]:
    count = state.read_memory(ACTIVE_COUNT, 1)[0]
    if count > TASK_COUNT:
        raise ValueError("active task count exceeds pool")
    raw = state.read_memory(ACTIVE_POINTERS, count * 4)
    slots: list[int] = []
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
        "slot": slot,
        "flags": flags,
        "sort_y": struct.unpack_from("<h", raw, 0x1A if flags & 0x02000000 else 6)[0],
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


def _precedes(current: dict[str, Any], previous: dict[str, Any]) -> bool:
    for mask in (0xC0, 0x300):
        left, right = current["flags"] & mask, previous["flags"] & mask
        if left != right:
            return left < right
    left = bool(current["flags"] & 0x40000)
    right = bool(previous["flags"] & 0x40000)
    if left != right:
        return left and not right
    return left and current["sort_y"] > previous["sort_y"]


def _reconstructed_active_slots(state: Any) -> list[int]:
    ordered: list[dict[str, Any]] = []
    for slot in range(TASK_COUNT):
        task = _task_record(state, slot)
        if not task["flags"] & 1:
            continue
        index = len(ordered)
        ordered.append(task)
        while index and _precedes(task, ordered[index - 1]):
            ordered[index] = ordered[index - 1]
            index -= 1
        ordered[index] = task
    return [task["slot"] for task in ordered]


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
    return (
        (signed_y & 0xFF) | (flags & 0xC00) | (shape << 14),
        (signed_x & 0x1FF) | (int(flip_x) << 12) | (int(flip_y) << 13) | (size << 14),
        ((task["tile_base"] + component["tile_index"]) & 0x3FF)
        | (((flags >> 6) & 3) << 10)
        | (task["palette_bank"] << 12),
    )


def _derive_task_oam_bindings(
    binder: Any, renderer: Any, ack: Any, slot: int, group: dict[str, Any]
) -> dict[str, Any]:
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
        used: set[int] = set()
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
            if len(matches) != 1 or matches[0] in used:
                valid = False
                break
            index = matches[0]
            used.add(index)
            attr0, attr1, attr2 = attributes
            bindings.append({
                "frame_id": frame["frame_id"],
                "component_index": component["component_index"],
                "oam_index": index,
                "attr0": f"0x{attr0:04X}",
                "attr1": f"0x{attr1:04X}",
                "attr2": f"0x{attr2:04X}",
                "dispatch_ordinal": ordinals[0],
                "renderer_shadow_entry_hex": renderer_shadow[index * 8:index * 8 + 8].hex(),
                "ack_hardware_entry_hex": ack_hardware[index * 8:index * 8 + 8].hex(),
            })
        if valid and bindings:
            candidates.append((frame["frame_id"], bindings, clipped))
    if len(candidates) != 1:
        raise ValueError("target frame/component OAM binding is not unique")
    output_frame, bindings, clipped = candidates[0]
    try:
        selected_frame = group["animations"][task["animation_id"]]["keyframes"][task["keyframe_index"]]["frame_id"]
    except (IndexError, KeyError, TypeError) as error:
        raise ValueError("target task animation state is invalid") from error
    return {
        "dispatch_ordinal": ordinals[0],
        "output_frame_id": output_frame,
        "post_renderer_selected_frame_id": selected_frame,
        "frame_relation": (
            "post_renderer_selected_frame"
            if output_frame == selected_frame
            else "post_renderer_task_advanced_after_output"
        ),
        "clipped_component_indices": clipped,
        "bindings": bindings,
    }


def _target_tasks(state: Any, definition: int, animation: int) -> list[dict[str, int]]:
    result = []
    for slot in range(TASK_COUNT):
        address = TASK_BASE + slot * TASK_SIZE
        record = state.read_memory(address, TASK_SIZE)
        flags = struct.unpack_from("<I", record, 0)[0]
        pair = struct.unpack_from("<II", record, 0x1C)
        if flags & 1 and pair == (definition, animation):
            result.append(
                {
                    "slot": slot,
                    "address": address,
                    "flags": flags,
                    "tile_base": struct.unpack_from("<H", record, 0x10)[0],
                    "palette_bank": record[0x12],
                }
            )
    return result


def _verify_archived_batch(
    payloads: dict[str, bytes], evidence: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    batch_raw = payloads["source/batch-audit.json"]
    if _sha256_bytes(batch_raw) != evidence.get("source_batch_audit_sha256"):
        raise ValueError("source batch audit hash mismatch")
    batch = _json_payload(batch_raw, "batch audit")
    if (
        batch.get("schema") != "battle-effect-controlled-sequence-batch-audit-v1"
        or batch.get("case_count") != 13
        or batch.get("group_ids") != [row[1] for row in CASE_ROWS]
        or batch.get("spec") != SPEC
        or batch.get("spec_sha256") != TRUSTED_SOURCE_SHA256["spec"]
        or batch.get("sequence_catalog") != SEQUENCE_CATALOG
        or batch.get("sequence_catalog_sha256") != TRUSTED_SOURCE_SHA256["sequence_catalog"]
        or batch.get("toolchain_profile") != TOOLCHAIN_PROFILE
        or batch.get("toolchain_profile_sha256") != TRUSTED_SOURCE_SHA256["toolchain_profile"]
        or batch.get("input_state_sha256") != TRUSTED_SOURCE_SHA256["input_state"]
    ):
        raise ValueError("archived batch denominator or provenance mismatch")
    rows = batch.get("cases")
    if not isinstance(rows, list) or len(rows) != len(CASE_ROWS):
        raise ValueError("archived batch case list mismatch")
    results: dict[str, dict[str, Any]] = {}
    for row, (case_id, group_id, sequence_id) in zip(rows, CASE_ROWS, strict=True):
        if (
            row.get("case_id") != case_id
            or row.get("group_id") != group_id
            or row.get("sequence_id") != sequence_id
            or row.get("profile") != f"{case_id}/profile.json"
            or row.get("audit") != f"{case_id}/output/audit.json"
            or row.get("guard_summary") != f"{case_id}/guard-summary.json"
        ):
            raise ValueError(f"{case_id} archived batch row mismatch")
        profile_member = f"source/{case_id}/profile.json"
        audit_member = f"source/{case_id}/output/audit.json"
        guard_member = f"source/{case_id}/guard-summary.json"
        done_member = f"source/{case_id}/guard-summary.json.done.json"
        profile_raw = payloads[profile_member]
        audit_raw = payloads[audit_member]
        guard_raw = payloads[guard_member]
        if _sha256_bytes(profile_raw) != row.get("profile_sha256"):
            raise ValueError(f"{case_id} profile hash mismatch")
        if _sha256_bytes(audit_raw) != row.get("audit_sha256"):
            raise ValueError(f"{case_id} runtime audit hash mismatch")
        profile = _json_payload(profile_raw, f"{case_id} profile")
        audit = _json_payload(audit_raw, f"{case_id} runtime audit")
        guard = _json_payload(guard_raw, f"{case_id} guard summary")
        done = _json_payload(payloads[done_member], f"{case_id} completion marker")
        if audit.get("guard_summary_sha256") != _sha256_bytes(guard_raw):
            raise ValueError(f"{case_id} guard hash mismatch")
        if (
            audit.get("profile_sha256") != row.get("profile_sha256")
            or audit.get("group_id") != group_id
            or audit.get("sequence_id") != sequence_id
            or audit.get("rom_sha256") != row.get("rom_sha256")
            or audit.get("staged_rom_sha256") != row.get("rom_sha256")
            or audit.get("input_state_sha256") != TRUSTED_SOURCE_SHA256["input_state"]
            or audit.get("phase_script_sha256") != TRUSTED_SOURCE_SHA256["capture_script"]
            or audit.get("outcome") != "binder-plus-three-phase-captured"
            or audit.get("scratch_before") != 0
            or audit.get("scratch_after") != 1
        ):
            raise ValueError(f"{case_id} archived runtime audit mismatch")
        if (
            profile.get("group_id") != group_id
            or profile.get("sequence_id") != sequence_id
            or profile.get("source_rom_sha256") != row.get("rom_sha256")
            or profile.get("input_state_sha256") != TRUSTED_SOURCE_SHA256["input_state"]
            or profile.get("source_runtime_evidence_sha256")
            != TRUSTED_SOURCE_SHA256["sequence_catalog"]
        ):
            raise ValueError(f"{case_id} archived profile mismatch")
        if (
            guard.get("reason") != "completed"
            or guard.get("exit_code") != 0
            or guard.get("degraded") is not False
            or guard.get("completion_trigger") != "success-marker"
            or guard.get("protection_backend") != "posix-process-group"
            or done != {
                "run_id": audit.get("run_id"),
                "status": audit.get("outcome"),
                "phase_count": 4,
            }
        ):
            raise ValueError(f"{case_id} archived guard or completion marker mismatch")
        rss = guard.get("peak_tree_rss_mib")
        if (
            not isinstance(rss, (int, float))
            or isinstance(rss, bool)
            or rss < 0
            or audit.get("peak_tree_rss_mib") != rss
            or row.get("peak_tree_rss_mib") != rss
        ):
            raise ValueError(f"{case_id} archived RSS mismatch")
        files = audit.get("files")
        expected_files = {
            f"{phase}/{name}"
            for phase in PHASE_NAMES
            for name in (
                "capture-active-count.bin", "capture-active-pointers.bin",
                "capture-hardware-oam.bin", "capture-io.bin", "capture-phase.json",
                "capture-pram.bin", "capture-runtime-offsets.bin", "capture-shadow-oam.bin",
                "capture-submission.bin", "capture-task-pool.bin", "capture-vram.bin",
                "capture.png", "capture.ss9",
            )
        }
        if not isinstance(files, dict) or set(files) != expected_files:
            raise ValueError(f"{case_id} archived output inventory mismatch")
        for relative, expected_hash in files.items():
            member = f"source/{case_id}/output/{relative}"
            if _sha256_bytes(payloads[member]) != expected_hash:
                raise ValueError(f"{case_id} archived output hash mismatch: {relative}")
        results[case_id] = {
            "profile_sha256": _sha256_bytes(profile_raw),
            "runtime_audit_sha256": _sha256_bytes(audit_raw),
            "guard_summary_sha256": _sha256_bytes(guard_raw),
            "rss": rss,
            "rss_valid": rss >= 1,
        }
    return results


def _catalogs(evidence: dict[str, Any]) -> tuple[
    bytes,
    dict[int, dict[str, Any]],
    dict[int, dict[str, Any]],
    dict[int, tuple[bytes, bytes]],
]:
    sources = evidence.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("source provenance is missing")
    expected_sources = {
        "spec": SPEC,
        "base_rom": BASE_ROM,
        "input_state": None,
        "sequence_catalog": SEQUENCE_CATALOG,
        "animation_catalog": ANIMATION_CATALOG,
        "resource_catalog": RESOURCE_CATALOG,
        "toolchain_profile": TOOLCHAIN_PROFILE,
        "capture_script": "tools/mgba_controlled_battle_effect_capture.lua",
    }
    loaded: dict[str, Path] = {}
    actual_hashes: dict[str, str] = {}
    for key, expected in expected_sources.items():
        info = sources.get(key)
        if not isinstance(info, dict):
            raise ValueError(f"{key} source provenance is missing")
        expected_path = expected
        if key == "input_state":
            spec = _object(ROOT / SPEC)
            expected_path = spec.get("input_state")
        path = _repository_file(info.get("path"), str(expected_path), key)
        if _sha256(path) != info.get("sha256"):
            raise ValueError(f"{key} source hash mismatch")
        actual_hashes[key] = info["sha256"]
        loaded[key] = path
    validate_trusted_source_hashes(actual_hashes)

    base = loaded["base_rom"].read_bytes()
    if hashlib.sha1(base).hexdigest() != sources["base_rom"].get("sha1"):
        raise ValueError("base ROM SHA-1 mismatch")
    spec = _object(loaded["spec"])
    if spec.get("schema") != "battle-effect-controlled-sequence-batch-v1":
        raise ValueError("controlled batch spec schema mismatch")
    expected_spec_rows = [
        {"group_id": group_id, "sequence_id": sequence_id}
        for _, group_id, sequence_id in CASE_ROWS
    ]
    if spec.get("cases") != expected_spec_rows:
        raise ValueError("controlled batch spec denominator mismatch")
    if spec.get("scratch_address") != f"0x{SCRATCH:08X}" or spec.get("scratch_expected_hex") != "00000000":
        raise ValueError("controlled scratch contract mismatch")
    input_state = load_gba_state(loaded["input_state"])
    if input_state.read_memory(SCRATCH, 4) != bytes(4):
        raise ValueError("input checkpoint scratch precondition mismatch")

    sequence_catalog = _object(loaded["sequence_catalog"])
    if sequence_catalog.get("schema") != "battle-effect-sequence-bindings-v1":
        raise ValueError("sequence catalog schema mismatch")
    sequences = {
        row.get("sequence_id"): row
        for row in sequence_catalog.get("sequences", [])
        if isinstance(row, dict)
    }
    for _, group_id, sequence_id in CASE_ROWS:
        if sequences.get(sequence_id, {}).get("nonzero_resource_group_ids") != [group_id]:
            raise ValueError("controlled sequence-to-group mapping mismatch")
    if sequences.get(18, {}).get("nonzero_resource_group_ids") != [18]:
        raise ValueError("uncovered group 18 sequence 18 edge is not present in catalog")

    animation_catalog = _object(loaded["animation_catalog"])
    if animation_catalog.get("schema") != "battle-effect-sprite-animations-v1":
        raise ValueError("animation catalog schema mismatch")
    groups: dict[int, dict[str, Any]] = {}
    for row in animation_catalog.get("groups", []):
        if isinstance(row, dict) and isinstance(row.get("group_id"), int):
            groups[row["group_id"]] = row
    if set(groups) != set(range(1, 19)):
        raise ValueError("animation group denominator mismatch")

    resource_catalog = _object(loaded["resource_catalog"])
    if resource_catalog.get("schema") != "battle-effect-resource-pairs-v1":
        raise ValueError("resource catalog schema mismatch")
    resources: dict[int, tuple[bytes, bytes]] = {}
    for row in resource_catalog.get("entries", []):
        if not isinstance(row, dict):
            continue
        group_id = row.get("group_id")
        graphics_info = row.get("graphics", {})
        palette_info = row.get("palette", {})
        graphics_path = loaded["resource_catalog"].parent / graphics_info.get("output_bin", "")
        palette_path = loaded["resource_catalog"].parent / palette_info.get("output_bin", "")
        graphics = graphics_path.read_bytes()
        palette = palette_path.read_bytes()
        if (
            _sha256_bytes(graphics) != graphics_info.get("decompressed_sha256")
            or _sha256_bytes(palette) != palette_info.get("decompressed_sha256")
            or len(graphics) != graphics_info.get("decompressed_size")
            or len(palette) != 32
        ):
            raise ValueError("resource pair payload mismatch")
        resources[group_id] = (graphics, palette)
    if set(resources) != set(range(1, 19)):
        raise ValueError("resource pair denominator mismatch")

    toolchain = _object(loaded["toolchain_profile"])
    hardware = toolchain.get("hardware_evidence", {})
    if (
        toolchain.get("schema") != "rom-expansion-profile-v1"
        or toolchain.get("identity") != "agb_standard_16mib_sequel_rom_profile"
        or not isinstance(hardware, dict)
        or hardware.get("mgba_binary_sha256") != sources["toolchain_profile"].get("binary_sha256")
    ):
        raise ValueError("toolchain profile identity mismatch")
    return base, sequences, groups, resources


def verify_artifact(artifact: Path | str) -> dict[str, Any]:
    artifact = Path(artifact).resolve()
    errors: list[str] = []
    positives: list[int] = []
    negatives: list[int] = []
    task_oam_binding_count = 0
    task_oam_bound_groups: list[int] = []
    try:
        manifest = _object(artifact / "manifest.json")
        evidence = _object(artifact / "evidence.json")
        archive_path = artifact / "raw-batch.tar"
        if manifest.get("schema") != PROMOTION_SCHEMA:
            raise ValueError("promotion manifest schema mismatch")
        if manifest.get("artifact_schema") != SCHEMA or evidence.get("schema") != SCHEMA:
            raise ValueError("controlled artifact schema mismatch")
        if manifest.get("artifact_status") != "accepted":
            raise ValueError("controlled artifact is not accepted")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != {"evidence.json", "raw-batch.tar"}:
            raise ValueError("artifact file inventory mismatch")
        actual_files = {
            path.relative_to(artifact).as_posix()
            for path in artifact.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        if actual_files != {"manifest.json", *files} or any(
            path.is_symlink() for path in artifact.rglob("*")
        ):
            raise ValueError("artifact directory inventory mismatch")
        for relative, expected_hash in files.items():
            path = artifact / relative
            if not path.is_file() or _sha256(path) != expected_hash:
                raise ValueError(f"artifact hash mismatch: {relative}")
        repository_hashes = manifest.get("repository_files")
        if not isinstance(repository_hashes, dict) or set(repository_hashes) != set(REPOSITORY_FILES):
            raise ValueError("repository evidence inventory mismatch")
        for relative in REPOSITORY_FILES:
            if _sha256(ROOT / relative) != repository_hashes[relative]:
                raise ValueError(f"repository evidence hash mismatch: {relative}")
        verifier = manifest.get("verifier")
        canonical_artifact = manifest.get("artifact_path")
        if (
            canonical_artifact != "artifacts/battle-effect-controlled-runtime-v1"
            or not isinstance(verifier, dict)
            or verifier.get("exit_code") != 0
            or verifier.get("result") != "verified"
            or verifier.get("command") != [
                "python3",
                "tools/verify_battle_effect_controlled_runtime.py",
                canonical_artifact,
            ]
        ):
            raise ValueError("verifier promotion record mismatch")

        validate_coverage_contract(evidence.get("coverage", {}))
        rss = evidence.get("rss_sampling")
        if (
            not isinstance(rss, dict)
            or rss.get("valid_for_batch_statistics") is not False
            or rss.get("anomaly_case_ids")
            != [
                "group-04-sequence-04",
                "group-06-sequence-08",
                "group-07-sequence-09",
                "group-17-sequence-20",
            ]
        ):
            raise ValueError("RSS under-sampling boundary mismatch")

        payloads = read_safe_tar(archive_path)
        if tuple(sorted(payloads)) != EXPECTED_MEMBER_NAMES:
            raise ValueError("raw savestate archive member denominator mismatch")
        archive = evidence.get("archive")
        if (
            not isinstance(archive, dict)
            or archive.get("path") != "raw-batch.tar"
            or archive.get("sha256") != _sha256(archive_path)
            or archive.get("size") != archive_path.stat().st_size
            or archive.get("member_count") != 729
        ):
            raise ValueError("raw savestate archive ledger mismatch")
        member_ledger = archive.get("members")
        if not isinstance(member_ledger, dict) or set(member_ledger) != set(EXPECTED_MEMBER_NAMES):
            raise ValueError("raw savestate member ledger mismatch")
        for name, raw in payloads.items():
            if member_ledger[name] != {"sha256": _sha256_bytes(raw), "size": len(raw)}:
                raise ValueError(f"raw savestate member hash mismatch: {name}")

        archived_cases = _verify_archived_batch(payloads, evidence)
        base, _, groups, resources = _catalogs(evidence)
        cases = evidence.get("cases")
        if not isinstance(cases, list) or len(cases) != len(CASE_ROWS):
            raise ValueError("controlled evidence case denominator mismatch")
        if [row.get("case_id") for row in cases] != [row[0] for row in CASE_ROWS]:
            raise ValueError("controlled evidence case order mismatch")

        with tempfile.TemporaryDirectory(prefix="verify-controlled-effects-") as temporary:
            temporary_path = Path(temporary)
            for case, (case_id, group_id, sequence_id) in zip(cases, CASE_ROWS, strict=True):
                if case.get("group_id") != group_id or case.get("sequence_id") != sequence_id:
                    raise ValueError(f"{case_id} identity mismatch")
                archived = archived_cases[case_id]
                expected_source_members = {
                    "profile": f"source/{case_id}/profile.json",
                    "runtime_audit": f"source/{case_id}/output/audit.json",
                    "guard_summary": f"source/{case_id}/guard-summary.json",
                    "completion_marker": f"source/{case_id}/guard-summary.json.done.json",
                }
                if case.get("source_members") != expected_source_members:
                    raise ValueError(f"{case_id} source member ledger mismatch")
                for field in ("profile_sha256", "runtime_audit_sha256", "guard_summary_sha256"):
                    if case.get(field) != archived[field]:
                        raise ValueError(f"{case_id} archived source hash mismatch: {field}")
                expected_verdict = (
                    "verified_target_transaction"
                    if group_id in POSITIVE_GROUP_IDS
                    else "target_absent_negative"
                )
                if case.get("verdict") != expected_verdict:
                    raise ValueError(f"{case_id} verdict mismatch")
                probe = build_probe(base, sequence_id=sequence_id)
                if _sha256_bytes(probe) != case.get("probe_rom_sha256"):
                    raise ValueError(f"{case_id} probe ROM hash mismatch")
                group = groups[group_id]
                definition = int(group["definition_pointer_table"], 16)
                animation = int(group["animation_pointer_table"], 16)
                if (
                    case.get("definition_pointer") != f"0x{definition:08X}"
                    or case.get("animation_pointer") != f"0x{animation:08X}"
                    or case.get("outcome") != "binder-plus-three-phase-captured"
                    or case.get("scratch_before") != 0
                    or case.get("scratch_after") != 1
                ):
                    raise ValueError(f"{case_id} controlled runtime contract mismatch")
                guard = case.get("guard")
                if not isinstance(guard, dict) or {
                    key: guard.get(key)
                    for key in (
                        "reason", "exit_code", "degraded", "completion_trigger",
                        "protection_backend", "pgid_clean", "listener_clean",
                    )
                } != {
                    "reason": "completed",
                    "exit_code": 0,
                    "degraded": False,
                    "completion_trigger": "success-marker",
                    "protection_backend": "posix-process-group",
                    "pgid_clean": True,
                    "listener_clean": True,
                }:
                    raise ValueError(f"{case_id} guard or residue boundary mismatch")
                if (
                    guard.get("peak_tree_rss_mib_sample") != archived["rss"]
                    or guard.get("rss_sample_valid") is not archived["rss_valid"]
                ):
                    raise ValueError(f"{case_id} RSS evidence mismatch")

                phases = case.get("phases")
                if not isinstance(phases, list) or len(phases) != 4:
                    raise ValueError(f"{case_id} phase denominator mismatch")
                states = []
                cycles = []
                target_rows = []
                active_lists = []
                for phase, (name, address, pending, frame) in zip(phases, PHASES, strict=True):
                    member = f"source/{case_id}/output/{name}/capture.ss9"
                    if phase.get("name") != name or phase.get("address") != address:
                        raise ValueError(f"{case_id} {name} phase identity mismatch")
                    if phase.get("savestate_member") != member:
                        raise ValueError(f"{case_id} {name} member path mismatch")
                    raw = payloads[member]
                    if (
                        phase.get("savestate_sha256") != _sha256_bytes(raw)
                        or phase.get("savestate_size") != len(raw)
                    ):
                        raise ValueError(f"{case_id} {name} savestate ledger mismatch")
                    state_path = temporary_path / f"{case_id}-{name}.ss9"
                    state_path.write_bytes(raw)
                    state = load_gba_state(state_path)
                    states.append(state)
                    if not state.cpsr & 0x20 or state.registers[15] - 2 != int(address, 16):
                        raise ValueError(f"{case_id} {name} breakpoint PC mismatch")
                    if state.read_memory(SCRATCH, 4) != (1).to_bytes(4, "little"):
                        raise ValueError(f"{case_id} {name} scratch latch mismatch")
                    state_pending = state.read_memory(PENDING, 1)[0]
                    if phase.get("pending") != pending or state_pending != pending:
                        raise ValueError(f"{case_id} {name} pending mismatch")
                    if phase.get("frame") != frame:
                        raise ValueError(f"{case_id} {name} frame mismatch")
                    try:
                        cycles.append(int(str(phase.get("cycle")), 10))
                    except (TypeError, ValueError) as error:
                        raise ValueError(f"{case_id} {name} cycle is invalid") from error
                    targets = _target_tasks(state, definition, animation)
                    target_rows.append(targets)
                    active = _active_slots(state)
                    if active != _reconstructed_active_slots(state):
                        raise ValueError(f"{case_id} {name} dispatcher order mismatch")
                    active_lists.append(active)
                    present = len(targets) == 1
                    expected_slot = targets[0]["slot"] if present else None
                    if (
                        phase.get("target_present") is not present
                        or phase.get("task_slot") != expected_slot
                    ):
                        raise ValueError(f"{case_id} {name} target metadata mismatch")
                    expected_address = (
                        f"0x{targets[0]['address']:08X}" if present else None
                    )
                    expected_flags = (
                        f"0x{targets[0]['flags']:08X}" if present else None
                    )
                    if (
                        phase.get("task_address") != expected_address
                        or phase.get("task_flags") != expected_flags
                    ):
                        raise ValueError(f"{case_id} {name} task metadata mismatch")
                    if present and active.count(expected_slot) != 1:
                        raise ValueError(f"{case_id} {name} target dispatcher membership mismatch")
                if not all(left < right for left, right in zip(cycles, cycles[1:])):
                    raise ValueError(f"{case_id} phase cycles are not strictly increasing")

                renderer = states[1]
                submit = states[2]
                ack = states[3]
                renderer_shadow = renderer.read_memory(SHADOW_OAM, 0x400)
                renderer_hardware = renderer.read_memory(HARDWARE_OAM, 0x400)
                if renderer_shadow == renderer_hardware:
                    raise ValueError(f"{case_id} renderer phase has no pending OAM transaction")
                if (
                    submit.read_memory(SHADOW_OAM, 0x400) != renderer_shadow
                    or submit.read_memory(HARDWARE_OAM, 0x400) != renderer_hardware
                    or ack.read_memory(SHADOW_OAM, 0x400) != renderer_shadow
                    or ack.read_memory(HARDWARE_OAM, 0x400) != renderer_shadow
                ):
                    raise ValueError(f"{case_id} OAM submission/ack transaction mismatch")

                graphics, palette = resources[group_id]
                if expected_verdict == "verified_target_transaction":
                    if target_rows[0] or any(len(rows) != 1 for rows in target_rows[1:]):
                        raise ValueError(f"{case_id} positive target phase pattern mismatch")
                    slots = [rows[0]["slot"] for rows in target_rows[1:]]
                    if len(set(slots)) != 1 or slots[0] != 108:
                        raise ValueError(f"{case_id} positive target task is not stable")
                    if len(active_lists[1]) != len(active_lists[0]) + 1:
                        raise ValueError(f"{case_id} target task allocation count mismatch")
                    task = target_rows[1][0]
                    if task["flags"] & DYNAMIC_COPY or not 0 <= task["palette_bank"] < 16:
                        raise ValueError(f"{case_id} target task resource mode mismatch")
                    graphics_address = OBJ_VRAM + task["tile_base"] * 32
                    palette_address = OBJ_PRAM + task["palette_bank"] * 32
                    for state in states:
                        if (
                            state.read_memory(graphics_address, len(graphics)) != graphics
                            or state.read_memory(palette_address, len(palette)) != palette
                        ):
                            raise ValueError(f"{case_id} target resource bytes mismatch")
                    derived_task_oam = _derive_task_oam_bindings(
                        states[0], states[1], states[3], slots[0], group
                    )
                    recorded_task_oam = case.get("task_oam")
                    if not isinstance(recorded_task_oam, dict):
                        raise ValueError(f"{case_id} OAM binding metadata missing")
                    if recorded_task_oam.get("dispatch_ordinal") != derived_task_oam["dispatch_ordinal"]:
                        raise ValueError(f"{case_id} dispatcher ordinal mismatch")
                    if recorded_task_oam != derived_task_oam or case.get("oam_bindings") != derived_task_oam["bindings"]:
                        raise ValueError(f"{case_id} OAM binding mismatch")
                    task_oam_binding_count += len(derived_task_oam["bindings"])
                    task_oam_bound_groups.append(group_id)
                    positives.append(group_id)
                else:
                    if case.get("task_oam") is not None or case.get("oam_bindings") != []:
                        raise ValueError(f"{case_id} negative result contains OAM binding claims")
                    if any(target_rows):
                        raise ValueError(f"{case_id} negative result contains a target task")
                    for state in states:
                        obj_vram = state.read_memory(OBJ_VRAM, 0x8000)
                        obj_pram = state.read_memory(OBJ_PRAM, 0x200)
                        if graphics in obj_vram or any(
                            obj_pram[index:index + 32] == palette
                            for index in range(0, 0x200, 32)
                        ):
                            raise ValueError(f"{case_id} negative result contains a full target resource")
                    negatives.append(group_id)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, tarfile.TarError) as error:
        errors.append(str(error))

    verified = not errors
    return {
        "verified": verified,
        "errors": errors,
        "case_count": 13 if verified else 0,
        "positive_group_ids": positives if verified else [],
        "negative_group_ids": negatives if verified else [],
        "task_oam_binding_count": task_oam_binding_count if verified else 0,
        "task_oam_bound_group_ids": task_oam_bound_groups if verified else [],
        "natural_pixel_ab_unchanged": verified,
        "observed_frame_phase_unchanged": verified,
        "all_entry_paths_complete": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    result = verify_artifact(args.artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
