#!/usr/bin/env python3
"""Promote the group-15 allocator-reset side A/B into a compact artifact."""

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
    from tools.build_controlled_battle_effect_allocator_reset_probe import build_probe
    from tools.inspect_mgba_savestate import load_gba_state
    from tools.verify_battle_effect_controlled_runtime import (
        read_safe_tar as read_parent_tar,
        verify_artifact as verify_parent_artifact,
    )
except ModuleNotFoundError:
    from build_controlled_battle_effect_allocator_reset_probe import build_probe
    from inspect_mgba_savestate import load_gba_state
    from verify_battle_effect_controlled_runtime import (
        read_safe_tar as read_parent_tar,
        verify_artifact as verify_parent_artifact,
    )


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "battle-effect-group15-allocator-side-runtime-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
CANONICAL_ARTIFACT = "artifacts/battle-effect-group15-allocator-side-runtime-v1"
CASE_ROWS = (
    ("group-15-sequence-17-reset-side-0", 0),
    ("group-15-sequence-17-reset-side-1", 1),
)
CASE_IDS = tuple(row[0] for row in CASE_ROWS)
PHASE_NAMES = ("binder-return", "renderer-post", "submit-post", "ack-post")
CAPTURE_OUTPUT_NAMES = (
    "capture-active-count.bin", "capture-active-pointers.bin",
    "capture-hardware-oam.bin", "capture-io.bin", "capture-phase.json",
    "capture-pram.bin", "capture-runtime-offsets.bin", "capture-shadow-oam.bin",
    "capture-submission.bin", "capture-task-pool.bin", "capture-vram.bin",
    "capture.png", "capture.ss9",
)
EXPECTED_SOURCE_MEMBERS = {
    "source/batch-audit.json",
    *(f"source/{case}/{name}" for case in CASE_IDS for name in (
        "profile.json", "guard-summary.json", "guard-summary.json.done.json",
        "output/audit.json",
    )),
    *(f"source/{case}/output/{phase}/{name}" for case in CASE_IDS
      for phase in PHASE_NAMES for name in CAPTURE_OUTPUT_NAMES),
}
BASE_ROM = "rom/base.gba"
INPUT_STATE = "artifacts/runtime-checkpoints/scenario-50-battle-15-escort-12hp-player-turn.ss9"
SEQUENCE_CATALOG = "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
ANIMATION_CATALOG = "artifacts/battle-effect-sprite-animations-v1/manifest.json"
RESOURCE_CATALOG = "artifacts/battle-effect-resource-pairs-v1/manifest.json"
PARENT_CONTROLLED_ARTIFACT = "artifacts/battle-effect-controlled-runtime-v1/manifest.json"
PARENT_CONTROLLED_ROOT = "artifacts/battle-effect-controlled-runtime-v1"
GROUP15_GRAPHICS = "artifacts/battle-effect-resource-pairs-v1/group-15-graphics-4bpp.bin"
GROUP15_PALETTE = "artifacts/battle-effect-resource-pairs-v1/group-15-palette-bgr555.bin"
TOOLCHAIN_PROFILE = "artifacts/rom-expansion-profile-v1/profile.json"
CAPTURE_SCRIPT = "tools/mgba_controlled_battle_effect_capture.lua"
EXPECTED_BINARY_SHA256 = "c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8"
EXPECTED_TOOLCHAIN_SOURCE_COMMIT = "d8bad14b4540f9114246c0281d74985cf81adc68"
REPOSITORY_FILES = (
    "tools/build_controlled_battle_effect_allocator_reset_probe.py",
    "tools/run_battle_effect_allocator_reset_batch.py",
    "tools/export_battle_effect_group15_allocator_side_runtime.py",
    "tools/verify_battle_effect_group15_allocator_side_runtime.py",
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
    "tools/build_save_state_runtime_probe.py",
    "tools/thumb_branch.py",
    "tools/verify_battle_effect_controlled_runtime.py",
    "tests/test_build_controlled_battle_effect_allocator_reset_probe.py",
    "tests/test_run_battle_effect_allocator_reset_batch.py",
    "tests/test_export_battle_effect_group15_allocator_side_runtime.py",
    "tests/test_verify_battle_effect_group15_allocator_side_runtime.py",
)
TASK_BASE = 0x03003BB8
TASK_SIZE = 0x3C
TASK_COUNT = 128
ACTIVE_COUNT = 0x03005BB8
ACTIVE_POINTERS = 0x030059B8
SHADOW_OAM = 0x0300027C
HARDWARE_OAM = 0x07000000
OBJ_VRAM = 0x06010000
OBJ_PRAM = 0x05000200
SELECTOR_RESULT = 0x0202C64F
SIDE_OPCODE = 0x0809E852


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
        raise ValueError(f"{label} must be an object")
    return value


def collect_source_members(source: Path) -> dict[str, Path]:
    members = {"source/batch-audit.json": source / "batch-audit.json"}
    for case_id in CASE_IDS:
        case = source / case_id
        audit = _object(case / "output/audit.json", f"{case_id} audit")
        files = audit.get("files")
        expected = {
            f"{phase}/{name}" for phase in PHASE_NAMES for name in CAPTURE_OUTPUT_NAMES
        }
        if not isinstance(files, dict) or set(files) != expected:
            raise ValueError(f"{case_id} audit file inventory mismatch")
        for name in ("profile.json", "guard-summary.json", "guard-summary.json.done.json"):
            members[f"source/{case_id}/{name}"] = case / name
        members[f"source/{case_id}/output/audit.json"] = case / "output/audit.json"
        for relative in sorted(files):
            members[f"source/{case_id}/output/{relative}"] = case / "output" / relative
    if set(members) != EXPECTED_SOURCE_MEMBERS or any(not path.is_file() for path in members.values()):
        raise ValueError("source batch member inventory mismatch")
    return dict(sorted(members.items()))


def write_deterministic_tar(members: dict[str, Path], output: Path) -> None:
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name, path in sorted(members.items()):
            payload = path.read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o644
            info.uid = info.gid = info.mtime = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(payload))


def _target_tasks(state: Any, definition: int, animation: int) -> list[dict[str, Any]]:
    rows = []
    for slot in range(TASK_COUNT):
        raw = state.read_memory(TASK_BASE + slot * TASK_SIZE, TASK_SIZE)
        flags = struct.unpack_from("<I", raw)[0]
        if flags & 1 and struct.unpack_from("<II", raw, 0x1C) == (definition, animation):
            rows.append({
                "slot": slot,
                "flags": f"0x{flags:08X}",
                "anchor_x": struct.unpack_from("<h", raw, 4)[0],
                "anchor_y": struct.unpack_from("<h", raw, 6)[0],
                "tile_base": struct.unpack_from("<H", raw, 0x10)[0],
                "palette_bank": raw[0x12],
                "animation_id": raw[0x14],
                "keyframe_index": raw[0x16],
            })
    return rows


def _active_slots(state: Any) -> list[int]:
    count = struct.unpack("<I", state.read_memory(ACTIVE_COUNT, 4))[0]
    if count > TASK_COUNT:
        raise ValueError("active task count overflow")
    pointers = struct.unpack(f"<{count}I", state.read_memory(ACTIVE_POINTERS, count * 4))
    slots = []
    for pointer in pointers:
        delta = pointer - TASK_BASE
        if delta < 0 or delta % TASK_SIZE or delta // TASK_SIZE >= TASK_COUNT:
            raise ValueError("active task pointer mismatch")
        slots.append(delta // TASK_SIZE)
    return slots


def _source_record(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    return {"path": relative, "sha256": _sha256(path), "size": path.stat().st_size}


def _parent_no_reset_selector_results() -> list[int]:
    parent_root = ROOT / PARENT_CONTROLLED_ROOT
    result = verify_parent_artifact(parent_root)
    if not result.get("verified"):
        raise ValueError(f"parent controlled artifact failed verification: {result.get('errors')}")
    parent_evidence = _object(parent_root / "evidence.json", "parent evidence")
    case = next(
        row for row in parent_evidence["cases"]
        if row.get("case_id") == "group-15-sequence-17"
    )
    if case.get("probe_rom_sha256") != "de882cbee61c407ed1601c1accc9f652fa02de389afe0a56369650ab25f38ed6":
        raise ValueError("parent no-reset probe hash mismatch")
    payloads = read_parent_tar(parent_root / "raw-batch.tar")
    profile = _payload_json(
        payloads["source/group-15-sequence-17/profile.json"],
        "parent group-15 profile",
    )
    if (
        profile.get("group_id") != 15
        or profile.get("sequence_id") != 17
        or profile.get("input_state_sha256") != _sha256(ROOT / INPUT_STATE)
        or profile.get("source_rom_sha256") != case.get("probe_rom_sha256")
    ):
        raise ValueError("parent no-reset profile mismatch")
    results = []
    with tempfile.TemporaryDirectory() as temporary:
        for phase in PHASE_NAMES:
            state_path = Path(temporary) / f"parent-{phase}.ss9"
            state_path.write_bytes(
                payloads[
                    f"source/group-15-sequence-17/output/{phase}/capture.ss9"
                ]
            )
            results.append(load_gba_state(state_path).read_memory(SELECTOR_RESULT, 1)[0])
    if results != [0xFF, 0xFF, 0xFF, 0xFF]:
        raise ValueError("parent no-reset selector result mismatch")
    return results


def _payload_json(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid archived {label}") from error
    if not isinstance(value, dict):
        raise ValueError(f"archived {label} must be an object")
    return value


def is_allowed_output(path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(ROOT)
    except ValueError:
        return False
    return relative.as_posix() == CANONICAL_ARTIFACT or (
        len(relative.parts) == 6
        and relative.parts[:3] == ("build", "experiments", "active")
        and relative.parts[-1] == "final"
    )


def export_artifact(source: Path, artifact: Path) -> dict[str, Any]:
    source = source.resolve(strict=True)
    artifact = artifact.resolve()
    if artifact.exists() or not is_allowed_output(artifact):
        raise ValueError("artifact output must be absent and managed")
    batch = _object(source / "batch-audit.json", "batch audit")
    if (
        batch.get("schema") != "battle-effect-allocator-reset-batch-audit-v1"
        or batch.get("group_id") != 15
        or batch.get("sequence_id") != 17
        or batch.get("sides") != [0, 1]
        or batch.get("input_state_sha256") != _sha256(ROOT / INPUT_STATE)
        or batch.get("binary_sha256") != EXPECTED_BINARY_SHA256
        or batch.get("toolchain_profile") != TOOLCHAIN_PROFILE
        or batch.get("toolchain_profile_sha256") != _sha256(ROOT / TOOLCHAIN_PROFILE)
    ):
        raise ValueError("batch audit contract mismatch")
    animation_catalog = _object(ROOT / ANIMATION_CATALOG, "animation catalog")
    group = next(row for row in animation_catalog["groups"] if row.get("group_id") == 15)
    definition = int(group["definition_pointer_table"], 16)
    animation = int(group["animation_pointer_table"], 16)
    resource_catalog = _object(ROOT / RESOURCE_CATALOG, "resource catalog")
    resource = next(row for row in resource_catalog["entries"] if row.get("group_id") == 15)
    if (
        resource["graphics"].get("output_bin") != Path(GROUP15_GRAPHICS).name
        or resource["graphics"].get("decompressed_sha256") != _sha256(ROOT / GROUP15_GRAPHICS)
        or resource["palette"].get("output_bin") != Path(GROUP15_PALETTE).name
        or resource["palette"].get("decompressed_sha256") != _sha256(ROOT / GROUP15_PALETTE)
    ):
        raise ValueError("group 15 resource catalog identity mismatch")
    graphics = (ROOT / GROUP15_GRAPHICS).read_bytes()
    palette = (ROOT / GROUP15_PALETTE).read_bytes()
    base = (ROOT / BASE_ROM).read_bytes()
    roms = {side: build_probe(base, sequence_id=17, side=side) for side in (0, 1)}
    differences = [index for index, pair in enumerate(zip(roms[0], roms[1], strict=True)) if pair[0] != pair[1]]
    if differences != [SIDE_OPCODE - 0x08000000]:
        raise ValueError("side A/B is not a one-byte ROM difference")

    cases = []
    for (case_id, side), batch_row in zip(CASE_ROWS, batch["cases"], strict=True):
        case_root = source / case_id
        profile = _object(case_root / "profile.json", f"{case_id} profile")
        audit = _object(case_root / "output/audit.json", f"{case_id} audit")
        guard = _object(case_root / "guard-summary.json", f"{case_id} guard")
        done = _object(
            case_root / "guard-summary.json.done.json", f"{case_id} completion marker"
        )
        toolchain = audit.get("toolchain")
        toolchain_valid = (
            isinstance(toolchain, dict)
            and toolchain.get("kind") == "current-desktop-runtime-profile"
            and toolchain.get("patch_sha256") is None
            and isinstance(toolchain.get("path"), str)
            and Path(toolchain["path"]).as_posix().endswith("/" + TOOLCHAIN_PROFILE)
            and toolchain.get("sha256") == _sha256(ROOT / TOOLCHAIN_PROFILE)
            and toolchain.get("source_commit") == EXPECTED_TOOLCHAIN_SOURCE_COMMIT
        )
        if (
            batch_row.get("case_id") != case_id
            or batch_row.get("side") != side
            or profile.get("side") != side
            or profile.get("allocator_reset") != {
                "function": "0x0807FDCC", "tile_start": "0x0300",
                "tile_end": "0x037F", "palette_start": 12, "palette_end": 14,
            }
            or profile.get("source_rom_sha256") != hashlib.sha256(roms[side]).hexdigest()
            or audit.get("rom_sha256") != hashlib.sha256(roms[side]).hexdigest()
            or audit.get("binary_sha256") != EXPECTED_BINARY_SHA256
            or audit.get("phase_script_sha256") != _sha256(ROOT / CAPTURE_SCRIPT)
            or not toolchain_valid
            or done.get("status") != audit.get("outcome")
            or done.get("phase_count") != 4
            or done.get("run_id") != audit.get("run_id")
            or guard.get("reason") != "completed"
            or guard.get("exit_code") != 0
            or guard.get("degraded") is not False
        ):
            raise ValueError(f"{case_id} provenance mismatch")
        states = [load_gba_state(case_root / "output" / phase / "capture.ss9") for phase in PHASE_NAMES]
        selector_results = [state.read_memory(SELECTOR_RESULT, 1)[0] for state in states]
        targets = [_target_tasks(state, definition, animation) for state in states]
        active = [_active_slots(state) for state in states]
        if selector_results != [0, 0, 0, 0]:
            raise ValueError(f"{case_id} selector handle mismatch")
        if side == 0 and targets != [[], [], [], []]:
            raise ValueError("side 0 unexpectedly produced target task")
        if side == 1:
            if targets[0] or any(len(rows) != 1 or rows[0]["slot"] != 108 for rows in targets[1:]):
                raise ValueError("side 1 target task phase mismatch")
            task = targets[1][0]
            if task["anchor_x"] != -98 or task["anchor_y"] != 62:
                raise ValueError("side 1 target anchor changed")
            address = OBJ_VRAM + task["tile_base"] * 32
            palette_address = OBJ_PRAM + task["palette_bank"] * 32
            if any(state.read_memory(address, len(graphics)) != graphics for state in states[1:]):
                raise ValueError("side 1 graphics bytes mismatch")
            if any(state.read_memory(palette_address, len(palette)) != palette for state in states[1:]):
                raise ValueError("side 1 palette bytes mismatch")
        shadow_changed = states[1].read_memory(SHADOW_OAM, 0x400) != states[0].read_memory(SHADOW_OAM, 0x400)
        submitted = states[3].read_memory(HARDWARE_OAM, 0x400) == states[1].read_memory(SHADOW_OAM, 0x400)
        cases.append({
            "case_id": case_id,
            "side": side,
            "rom_sha256": hashlib.sha256(roms[side]).hexdigest(),
            "profile_sha256": _sha256(case_root / "profile.json"),
            "audit_sha256": _sha256(case_root / "output/audit.json"),
            "guard_summary_sha256": _sha256(case_root / "guard-summary.json"),
            "selector_results": selector_results,
            "target_tasks": targets,
            "active_slots": active,
            "oam_transaction": {"shadow_changed": shadow_changed, "ack_equals_renderer_shadow": submitted},
            "peak_tree_rss_mib_sample": guard.get("peak_tree_rss_mib"),
        })

    members = collect_source_members(source)
    parent_selector_results = _parent_no_reset_selector_results()
    artifact.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{artifact.name}-", dir=artifact.parent))
    try:
        archive = staging / "raw-batch.tar"
        write_deterministic_tar(members, archive)
        evidence = {
            "schema": SCHEMA,
            "boundary": (
                "Controlled allocator reset and binder-side A/B. It proves a valid selector "
                "handle for both sides and a stable group-15 resource/task only for side 1. "
                "The target anchor is offscreen, so no visible target OAM or natural entry is claimed."
            ),
            "sources": {name: _source_record(path) for name, path in {
                "base_rom": BASE_ROM, "input_state": INPUT_STATE,
                "sequence_catalog": SEQUENCE_CATALOG, "animation_catalog": ANIMATION_CATALOG,
                "resource_catalog": RESOURCE_CATALOG,
                "parent_controlled_artifact": PARENT_CONTROLLED_ARTIFACT,
                "group15_graphics": GROUP15_GRAPHICS,
                "group15_palette": GROUP15_PALETTE,
                "toolchain_profile": TOOLCHAIN_PROFILE,
                "capture_script": CAPTURE_SCRIPT,
            }.items()},
            "archive": {
                "path": "raw-batch.tar", "sha256": _sha256(archive),
                "size": archive.stat().st_size, "member_count": len(members),
                "members": {name: {"sha256": _sha256(path), "size": path.stat().st_size} for name, path in members.items()},
            },
            "side_ab": {
                "rom_byte_difference_count": 1,
                "difference_address": f"0x{SIDE_OPCODE:08X}",
                "side_0_byte": roms[0][differences[0]],
                "side_1_byte": roms[1][differences[0]],
            },
            "allocator_reset_ab": {
                "boundary": "same accepted checkpoint, sequence 17 and side 0",
                "no_reset_parent_artifact": PARENT_CONTROLLED_ROOT,
                "no_reset_probe_rom_sha256": "de882cbee61c407ed1601c1accc9f652fa02de389afe0a56369650ab25f38ed6",
                "no_reset_selector_results": parent_selector_results,
                "reset_selector_results": cases[0]["selector_results"],
            },
            "coverage": {
                "selector_valid_sides": [0, 1], "target_task_sides": [1],
                "target_task_slot": 108, "visible_target_oam_binding_count": 0,
                "natural_entry_complete": False,
            },
            "rss_sampling": {
                "valid_for_batch_statistics": False,
                "reason": "side 1 completed too quickly for a valid peak sample",
            },
            "cases": cases,
        }
        evidence_path = staging / "evidence.json"
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest = {
            "schema": PROMOTION_SCHEMA, "artifact_schema": SCHEMA,
            "artifact_status": "accepted", "artifact_path": CANONICAL_ARTIFACT,
            "description": "Group 15 controlled allocator-reset and binder-side task evidence.",
            "files": {"evidence.json": _sha256(evidence_path), "raw-batch.tar": _sha256(archive)},
            "repository_files": {name: _sha256(ROOT / name) for name in REPOSITORY_FILES},
            "verifier": {"command": ["python3", "tools/verify_battle_effect_group15_allocator_side_runtime.py", CANONICAL_ARTIFACT], "exit_code": 0, "result": "verified"},
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        verified = subprocess.run([sys.executable, str(ROOT / "tools/verify_battle_effect_group15_allocator_side_runtime.py"), str(staging)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if verified.returncode:
            raise ValueError("independent verifier failed: " + (verified.stdout or verified.stderr).strip())
        os.replace(staging, artifact)
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
        print(f"export_group15_allocator_side: {error}", file=sys.stderr)
        return 2
    print(json.dumps(evidence["coverage"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
