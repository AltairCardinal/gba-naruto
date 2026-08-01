#!/usr/bin/env python3
"""Promote group 3/18 direct selector+spawn captures into a compact artifact."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import struct
import subprocess
import sys
import tarfile
import tempfile
from typing import Any

try:
    from tools.build_controlled_battle_effect_direct_spawn_probe import (
        CASES_BY_ID,
        SCRATCH,
        build_probe,
    )
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    from build_controlled_battle_effect_direct_spawn_probe import (
        CASES_BY_ID,
        SCRATCH,
        build_probe,
    )
    from inspect_mgba_savestate import load_gba_state


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "battle-effect-direct-spawn-runtime-v1"
CANONICAL_ARTIFACT = "artifacts/battle-effect-direct-spawn-runtime-v1"
ARCHIVE_ROOT = "build/experiments/archive/battle-effect-direct-spawn/2026-08"
PHASES = ("renderer-post", "submit-post", "ack-post")
PHASE_ADDRESSES = (0x08063328, 0x08061126, 0x080612AA)
PHASE_PENDING = (0, 1, 0)
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
EXPECTED_BINARY_SHA256 = "c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8"
BASE_ROM = "rom/base.gba"
INPUT_STATE = "artifacts/runtime-checkpoints/scenario-50-battle-15-escort-12hp-player-turn.ss9"
SEQUENCE_CATALOG = "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
ANIMATION_CATALOG = "artifacts/battle-effect-sprite-animations-v1/manifest.json"
RESOURCE_CATALOG = "artifacts/battle-effect-resource-pairs-v1/manifest.json"
PARENT_CONTROLLED_MANIFEST = "artifacts/battle-effect-controlled-runtime-v1/manifest.json"
PARENT_GROUP15_MANIFEST = "artifacts/battle-effect-group15-allocator-side-runtime-v1/manifest.json"
TOOLCHAIN_PROFILE = "artifacts/rom-expansion-profile-v1/profile.json"
CAPTURE_SCRIPT = "tools/mgba_battle_effect_phase_capture.lua"
RESOURCE_FILES = {
    3: (
        "artifacts/battle-effect-resource-pairs-v1/group-03-graphics-4bpp.bin",
        "artifacts/battle-effect-resource-pairs-v1/group-03-palette-bgr555.bin",
    ),
    18: (
        "artifacts/battle-effect-resource-pairs-v1/group-18-graphics-4bpp.bin",
        "artifacts/battle-effect-resource-pairs-v1/group-18-palette-bgr555.bin",
    ),
}
REPOSITORY_FILES = (
    "tools/build_controlled_battle_effect_direct_spawn_probe.py",
    "tools/run_battle_effect_direct_spawn_batch.py",
    "tools/export_battle_effect_direct_spawn_runtime.py",
    "tools/verify_battle_effect_direct_spawn_runtime.py",
    "tools/verify_battle_effect_controlled_runtime.py",
    "tools/verify_battle_effect_group15_allocator_side_runtime.py",
    "tools/run_macos_mgba_battle_effect_phase_capture.py",
    "tools/run_macos_mgba_input_sequence.py",
    "tools/run_macos_mgba_replay.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_battle_effect_phase_capture.lua",
    "tools/macos_mgba_runtime_residue.py",
    "tools/run_guarded.py",
    "tools/mgba_runtime_safety.py",
    "tools/project_resource_guard.py",
    "tools/inspect_mgba_savestate.py",
    "tools/build_save_state_runtime_probe.py",
    "tools/thumb_branch.py",
    "tests/test_build_controlled_battle_effect_direct_spawn_probe.py",
    "tests/test_run_battle_effect_direct_spawn_batch.py",
    "tests/test_export_battle_effect_direct_spawn_runtime.py",
    "tests/test_verify_battle_effect_direct_spawn_runtime.py",
)


@dataclass(frozen=True)
class SourceCase:
    case_id: str
    group_id: int
    sequence_id: int
    side: int | None
    run_id: str


CASE_ROWS = (
    SourceCase("group-03-sequence-03-side-0-direct-spawn", 3, 3, 0, "20260802-03"),
    SourceCase("group-03-sequence-03-side-1-direct-spawn", 3, 3, 1, "20260802-04"),
    SourceCase("group-18-sequence-07-direct-spawn", 18, 7, None, "20260802-01"),
    SourceCase("group-18-sequence-18-direct-spawn", 18, 18, None, "20260802-02"),
)
NEGATIVE_RUN_ID = "20260801-02"
NEGATIVE_CASE_ID = "group-03-sequence-03-direct-spawn"


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _json_file(path: Path, label: str) -> dict[str, Any]:
    return _json_bytes(path.read_bytes(), label)


def read_run_archive(path: Path, *, run_id: str) -> dict[str, bytes]:
    """Read a lifecycle archive without extracting paths to the filesystem."""

    prefix = f"{run_id}/"
    payloads: dict[str, bytes] = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            pure = PurePosixPath(member.name)
            if pure.is_absolute() or ".." in pure.parts:
                raise ValueError("unsafe or foreign run archive member")
            if member.isdir():
                if member.name != run_id and not member.name.startswith(prefix):
                    raise ValueError("foreign run archive directory")
                continue
            if not member.name.startswith(prefix):
                raise ValueError("foreign run archive member")
            if not member.isfile() or member.linkname:
                raise ValueError("run archive contains a non-regular member")
            relative = member.name[len(prefix):]
            if not relative or relative in payloads:
                raise ValueError("empty or duplicate run archive member")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError("run archive member cannot be read")
            payloads[relative] = extracted.read()
    return payloads


def expected_source_members() -> set[str]:
    members: set[str] = set()
    for case in CASE_ROWS:
        base = f"source/{case.case_id}"
        members.add(f"{base}/batch-audit.json")
        for name in (
            "profile.json",
            "guard-summary.json",
            "guard-summary.json.done.json",
            "output/audit.json",
        ):
            members.add(f"{base}/{name}")
        for phase in PHASES:
            members.add(f"{base}/output/{phase}/capture-phase.json")
            members.add(f"{base}/output/{phase}/capture.ss9")
    negative = "source/narrow-window-negative"
    for name in (
        "profile.json",
        "guard-summary.json",
        "guard-summary.json.done.json",
        "output/audit.json",
        "output/timeout.ss9",
        "run-inventory.json",
        "run-metadata.json",
    ):
        members.add(f"{negative}/{name}")
    return members


def collect_source_payloads(archive_root: Path) -> dict[str, bytes]:
    output: dict[str, bytes] = {}
    for case in CASE_ROWS:
        payloads = read_run_archive(
            archive_root / f"{case.run_id}.tar.gz", run_id=case.run_id
        )
        run_base = f"output/{case.case_id}"
        mapping = {
            f"source/{case.case_id}/batch-audit.json": "output/batch-audit.json",
            f"source/{case.case_id}/profile.json": f"{run_base}/profile.json",
            f"source/{case.case_id}/guard-summary.json": f"{run_base}/guard-summary.json",
            f"source/{case.case_id}/guard-summary.json.done.json": f"{run_base}/guard-summary.json.done.json",
            f"source/{case.case_id}/output/audit.json": f"{run_base}/output/audit.json",
        }
        for phase in PHASES:
            for name in ("capture-phase.json", "capture.ss9"):
                mapping[
                    f"source/{case.case_id}/output/{phase}/{name}"
                ] = f"{run_base}/output/{phase}/{name}"
        for target, source in mapping.items():
            if source not in payloads:
                raise ValueError(f"missing {case.run_id} member: {source}")
            output[target] = payloads[source]

    negative_payloads = read_run_archive(
        archive_root / f"{NEGATIVE_RUN_ID}.tar.gz", run_id=NEGATIVE_RUN_ID
    )
    negative_base = f"output/{NEGATIVE_CASE_ID}"
    for target_name, source_name in (
        ("profile.json", f"{negative_base}/profile.json"),
        ("guard-summary.json", f"{negative_base}/guard-summary.json"),
        ("guard-summary.json.done.json", f"{negative_base}/guard-summary.json.done.json"),
        ("output/audit.json", f"{negative_base}/output/audit.json"),
        ("output/timeout.ss9", f"{negative_base}/output/timeout.ss9"),
        ("run-inventory.json", ".inventory.json"),
        ("run-metadata.json", ".experiment.json"),
    ):
        if source_name not in negative_payloads:
            raise ValueError(f"missing narrow-window member: {source_name}")
        output[f"source/narrow-window-negative/{target_name}"] = negative_payloads[source_name]
    if set(output) != expected_source_members():
        raise ValueError("promoted source member denominator mismatch")
    return dict(sorted(output.items()))


def _canonical_tar(payloads: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, raw in sorted(payloads.items()):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mode = 0o644
            info.uid = info.gid = info.mtime = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(raw))
    return stream.getvalue()


def _state(raw: bytes, temporary: Path, name: str) -> Any:
    path = temporary / name
    path.write_bytes(raw)
    return load_gba_state(path)


def _target_tasks(state: Any, definition: int, animation: int) -> list[dict[str, Any]]:
    rows = []
    for slot in range(TASK_COUNT):
        raw = state.read_memory(TASK_BASE + slot * TASK_SIZE, TASK_SIZE)
        flags = struct.unpack_from("<I", raw)[0]
        if flags & 1 and struct.unpack_from("<II", raw, 0x1C) == (definition, animation):
            rows.append(
                {
                    "slot": slot,
                    "flags": f"0x{flags:08X}",
                    "anchor_x": struct.unpack_from("<h", raw, 4)[0],
                    "anchor_y": struct.unpack_from("<h", raw, 6)[0],
                    "tile_base": struct.unpack_from("<H", raw, 0x10)[0],
                    "palette_bank": raw[0x12],
                    "definition_pointer": f"0x{definition:08X}",
                    "animation_pointer": f"0x{animation:08X}",
                }
            )
    return rows


def _active_slots(state: Any) -> list[int]:
    count = state.read_memory(ACTIVE_COUNT, 1)[0]
    pointers = struct.unpack(
        f"<{count}I", state.read_memory(ACTIVE_POINTERS, count * 4)
    )
    slots = []
    for pointer in pointers:
        delta = pointer - TASK_BASE
        if delta < 0 or delta % TASK_SIZE or delta // TASK_SIZE >= TASK_COUNT:
            raise ValueError("active task pointer lies outside the task pool")
        slots.append(delta // TASK_SIZE)
    return slots


def _source_record(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    return {"path": relative, "sha256": _sha256(path), "size": path.stat().st_size}


def _summarize_case(
    payloads: dict[str, bytes],
    case: SourceCase,
    animation_group: dict[str, Any],
    resource_entry: dict[str, Any],
    temporary: Path,
) -> dict[str, Any]:
    prefix = f"source/{case.case_id}"
    profile = _json_bytes(payloads[f"{prefix}/profile.json"], f"{case.case_id} profile")
    audit = _json_bytes(payloads[f"{prefix}/output/audit.json"], f"{case.case_id} audit")
    guard = _json_bytes(payloads[f"{prefix}/guard-summary.json"], f"{case.case_id} guard")
    done = _json_bytes(payloads[f"{prefix}/guard-summary.json.done.json"], f"{case.case_id} done")
    batch = _json_bytes(payloads[f"{prefix}/batch-audit.json"], f"{case.case_id} batch")
    direct_case = CASES_BY_ID[case.case_id]
    expected_rom = build_probe((ROOT / BASE_ROM).read_bytes(), case_id=case.case_id)
    rom_sha = _sha256_bytes(expected_rom)
    if (
        profile.get("group_id") != case.group_id
        or profile.get("sequence_id") != case.sequence_id
        or profile.get("spawn", {}).get("side") != case.side
        or profile.get("source_rom_sha256") != rom_sha
        or audit.get("rom_sha256") != rom_sha
        or audit.get("outcome") != "three-phase-captured"
        or audit.get("binary_sha256") != EXPECTED_BINARY_SHA256
        or guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or done.get("status") != "three-phase-captured"
        or len(batch.get("cases", [])) != 1
    ):
        raise ValueError(f"{case.case_id} source provenance mismatch")
    definition = int(animation_group["definition_pointer_table"], 16)
    animation = int(animation_group["animation_pointer_table"], 16)
    graphics_path, palette_path = RESOURCE_FILES[case.group_id]
    graphics = (ROOT / graphics_path).read_bytes()
    palette = (ROOT / palette_path).read_bytes()
    states = []
    phase_rows = []
    palette_observations = []
    previous_cycle = -1
    for index, phase in enumerate(PHASES):
        state = _state(
            payloads[f"{prefix}/output/{phase}/capture.ss9"],
            temporary,
            f"{case.case_id}-{phase}.ss9",
        )
        meta = _json_bytes(
            payloads[f"{prefix}/output/{phase}/capture-phase.json"],
            f"{case.case_id} {phase}",
        )
        saved_address = state.registers[15] - 2
        cycle = int(meta["cycle"])
        if (
            saved_address != PHASE_ADDRESSES[index]
            or int(meta["address"], 16) != PHASE_ADDRESSES[index]
            or state.read_memory(PENDING, 1)[0] != PHASE_PENDING[index]
            or cycle <= previous_cycle
        ):
            raise ValueError(f"{case.case_id} phase boundary mismatch")
        previous_cycle = cycle
        targets = _target_tasks(state, definition, animation)
        if len(targets) != 1 or targets[0]["slot"] not in _active_slots(state):
            raise ValueError(f"{case.case_id} target task mismatch")
        task = targets[0]
        if state.read_memory(OBJ_VRAM + task["tile_base"] * 32, len(graphics)) != graphics:
            raise ValueError(f"{case.case_id} graphics mismatch")
        runtime_palette = state.read_memory(
            OBJ_PRAM + task["palette_bank"] * 32, len(palette)
        )
        palette_mismatches = [
            offset
            for offset, pair in enumerate(zip(runtime_palette, palette, strict=True))
            if pair[0] != pair[1]
        ]
        if case.group_id == 3:
            if palette_mismatches != [30, 31] or runtime_palette[:30] != palette[:30]:
                raise ValueError(f"{case.case_id} palette prefix mismatch")
        elif palette_mismatches:
            raise ValueError(f"{case.case_id} palette mismatch")
        palette_observations.append(
            {
                "matched_prefix_bytes": 30 if case.group_id == 3 else 32,
                "mismatch_offsets": palette_mismatches,
                "runtime_tail_hex": runtime_palette[30:].hex(),
                "source_tail_hex": palette[30:].hex(),
            }
        )
        selector = state.read_memory(SCRATCH + 4, 1)[0]
        if state.read_memory(SCRATCH, 4) != b"\x01\x00\x00\x00" or selector == 0xFF:
            raise ValueError(f"{case.case_id} selector scratch mismatch")
        states.append(state)
        phase_rows.append(
            {
                "name": phase,
                "address": f"0x{saved_address:08X}",
                "cycle": str(cycle),
                "pending": PHASE_PENDING[index],
                "selector_result": selector,
                "target_task": task,
                "savestate_sha256": _sha256_bytes(
                    payloads[f"{prefix}/output/{phase}/capture.ss9"]
                ),
            }
        )
    renderer_shadow = states[0].read_memory(SHADOW_OAM, 0x400)
    renderer_hardware = states[0].read_memory(HARDWARE_OAM, 0x400)
    submit_hardware = states[1].read_memory(HARDWARE_OAM, 0x400)
    ack_hardware = states[2].read_memory(HARDWARE_OAM, 0x400)
    if renderer_shadow == renderer_hardware or submit_hardware != renderer_hardware or ack_hardware != renderer_shadow:
        raise ValueError(f"{case.case_id} OAM transaction mismatch")
    return {
        "case_id": case.case_id,
        "group_id": case.group_id,
        "sequence_id": case.sequence_id,
        "side": case.side,
        "allocator_reset": profile["allocator_reset"],
        "spawn": profile["spawn"],
        "rom_sha256": rom_sha,
        "profile_sha256": _sha256_bytes(payloads[f"{prefix}/profile.json"]),
        "audit_sha256": _sha256_bytes(payloads[f"{prefix}/output/audit.json"]),
        "guard_summary_sha256": _sha256_bytes(payloads[f"{prefix}/guard-summary.json"]),
        "peak_tree_rss_mib_sample": guard.get("peak_tree_rss_mib"),
        "rss_sample_valid_for_statistics": bool((guard.get("peak_tree_rss_mib") or 0) >= 10),
        "phases": phase_rows,
        "oam_transaction": {
            "renderer_shadow_differs_from_old_hardware": True,
            "submit_hardware_unchanged": True,
            "ack_hardware_equals_renderer_shadow": True,
        },
        "resource": {
            "graphics_sha256": resource_entry["graphics"]["decompressed_sha256"],
            "graphics_size": len(graphics),
            "palette_sha256": resource_entry["palette"]["decompressed_sha256"],
            "palette_size": len(palette),
            "runtime_palette_observations": palette_observations,
        },
        "probe_contract": {
            "allocator_tile_start": direct_case.allocator_tile_start,
            "allocator_tile_end": direct_case.allocator_tile_end,
            "allocator_palette_start": direct_case.allocator_palette_start,
            "allocator_palette_end": direct_case.allocator_palette_end,
            "spawn_x": direct_case.spawn_x,
            "spawn_y": direct_case.spawn_y,
        },
    }


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


def export_artifact(archive_root: Path, artifact: Path) -> dict[str, Any]:
    archive_root = archive_root.resolve(strict=True)
    artifact = artifact.resolve()
    if artifact.exists() or not is_allowed_output(artifact):
        raise ValueError("artifact output must be absent and managed")
    payloads = collect_source_payloads(archive_root)
    animations = _json_file(ROOT / ANIMATION_CATALOG, "animation catalog")
    resources = _json_file(ROOT / RESOURCE_CATALOG, "resource catalog")
    animation_groups = {row["group_id"]: row for row in animations["groups"]}
    resource_entries = {row["group_id"]: row for row in resources["entries"]}
    with tempfile.TemporaryDirectory() as temporary_name:
        temporary = Path(temporary_name)
        cases = [
            _summarize_case(
                payloads,
                case,
                animation_groups[case.group_id],
                resource_entries[case.group_id],
                temporary,
            )
            for case in CASE_ROWS
        ]
        negative_state = _state(
            payloads["source/narrow-window-negative/output/timeout.ss9"],
            temporary,
            "narrow-window-negative.ss9",
        )
    negative_profile = _json_bytes(
        payloads["source/narrow-window-negative/profile.json"], "negative profile"
    )
    negative_guard = _json_bytes(
        payloads["source/narrow-window-negative/guard-summary.json"], "negative guard"
    )
    narrow_selector = negative_state.read_memory(SCRATCH + 4, 1)[0]
    if (
        narrow_selector != 0xFF
        or negative_state.read_memory(SCRATCH, 4) != b"\x01\x00\x00\x00"
        or negative_profile.get("allocator_reset", {}).get("tile_start") != "0x0300"
        or negative_profile.get("allocator_reset", {}).get("tile_end") != "0x037F"
        or negative_guard.get("reason") != "completed"
        or negative_guard.get("degraded") is not False
    ):
        raise ValueError("narrow-window negative contract mismatch")

    artifact.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{artifact.name}-", dir=artifact.parent))
    try:
        raw_tar = staging / "raw-batch.tar"
        raw_tar.write_bytes(_canonical_tar(payloads))
        source_paths = {
            "base_rom": BASE_ROM,
            "input_state": INPUT_STATE,
            "sequence_catalog": SEQUENCE_CATALOG,
            "animation_catalog": ANIMATION_CATALOG,
            "resource_catalog": RESOURCE_CATALOG,
            "parent_controlled_manifest": PARENT_CONTROLLED_MANIFEST,
            "parent_group15_manifest": PARENT_GROUP15_MANIFEST,
            "toolchain_profile": TOOLCHAIN_PROFILE,
            "capture_script": CAPTURE_SCRIPT,
            "group3_graphics": RESOURCE_FILES[3][0],
            "group3_palette": RESOURCE_FILES[3][1],
            "group18_graphics": RESOURCE_FILES[18][0],
            "group18_palette": RESOURCE_FILES[18][1],
        }
        evidence = {
            "schema": SCHEMA,
            "boundary": (
                "Controlled direct selector+spawn evidence for groups 3 and 18. "
                "It proves valid selector handles, stable resource/task identity and one "
                "renderer→submit→ack transaction per case. It is not natural gameplay, "
                "full animation, final pixel A/B, mirror-branch, audio or real-hardware evidence."
            ),
            "sources": {name: _source_record(path) for name, path in source_paths.items()},
            "archive": {
                "path": "raw-batch.tar",
                "sha256": _sha256(raw_tar),
                "size": raw_tar.stat().st_size,
                "member_count": len(payloads),
                "members": {
                    name: {"sha256": _sha256_bytes(raw), "size": len(raw)}
                    for name, raw in payloads.items()
                },
            },
            "cases": cases,
            "group3_allocator_ab": {
                "narrow_window": {"tile_start": 0x300, "tile_end": 0x37F},
                "narrow_selector_result": narrow_selector,
                "wide_window": {"tile_start": 0x100, "tile_end": 0x39F},
                "wide_selector_results": [cases[0]["phases"][0]["selector_result"], cases[1]["phases"][0]["selector_result"]],
                "resource_tile_count": resource_entries[3]["graphics"]["tile_count"],
                "causal_boundary": (
                    "The failed selector is upstream of spawn coordinates; the narrow 128-tile "
                    "window cannot contain the 304-tile group 3 payload. The wide window is a "
                    "controlled capacity reconstruction, not a proven direct natural caller reset."
                ),
            },
            "group3_side_observation": {
                "sides": [0, 1],
                "requested_x": 104,
                "target_anchors": [
                    [cases[0]["phases"][0]["target_task"]["anchor_x"], cases[0]["phases"][0]["target_task"]["anchor_y"]],
                    [cases[1]["phases"][0]["target_task"]["anchor_x"], cases[1]["phases"][0]["target_task"]["anchor_y"]],
                ],
                "target_flags": [
                    cases[0]["phases"][0]["target_task"]["flags"],
                    cases[1]["phases"][0]["target_task"]["flags"],
                ],
                "mirror_branch_proven": False,
                "reason": (
                    "The accepted checkpoint has owner byte+2 values 1/0 for side 0/1, "
                    "so both calls take the mirrored-x branch and both anchors are 136,80."
                ),
            },
            "coverage": {
                "direct_case_count": 4,
                "direct_case_success_count": 4,
                "new_controlled_group_ids": [3, 18],
                "controlled_or_observed_group_ids": list(range(1, 19)),
                "controlled_or_observed": {"numerator": 18, "denominator": 18},
                "production_natural_pixel_ab": {"numerator": 4, "denominator": 18},
                "observed_frame_phase": {"numerator": 5, "denominator": 18},
                "natural_entry_complete": False,
                "full_animation_complete": False,
                "real_hardware_complete": False,
            },
            "memory_sampling": {
                "valid_case_ids": [row["case_id"] for row in cases if row["rss_sample_valid_for_statistics"]],
                "undersampled_case_ids": [row["case_id"] for row in cases if not row["rss_sample_valid_for_statistics"]],
                "interpretation": "Guard enforcement remained active; sub-10 MiB peak samples are timing misses and are excluded from statistics.",
            },
        }
        (staging / "evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest = {
            "schema": "git-artifact-promotion-v1",
            "artifact_schema": SCHEMA,
            "artifact_status": "accepted",
            "files": {
                name: _sha256(staging / name) for name in ("evidence.json", "raw-batch.tar")
            },
            "repository_files": {
                name: _sha256(ROOT / name) for name in REPOSITORY_FILES
            },
            "verifier": {
                "command": [
                    "python3",
                    "tools/verify_battle_effect_direct_spawn_runtime.py",
                    "artifacts/battle-effect-direct-spawn-runtime-v1",
                ],
                "exit_code": 0,
            },
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging.rename(artifact)
    except Exception:
        for child in sorted(staging.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        if staging.exists():
            staging.rmdir()
        raise
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, default=ROOT / ARCHIVE_ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / CANONICAL_ARTIFACT)
    args = parser.parse_args()
    evidence = export_artifact(args.archive_root, args.output)
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools/verify_battle_effect_direct_spawn_runtime.py"), str(args.output)],
        cwd=ROOT,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise ValueError("independent verifier rejected exported artifact")
    print(json.dumps({"artifact": str(args.output), "cases": len(evidence["cases"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
