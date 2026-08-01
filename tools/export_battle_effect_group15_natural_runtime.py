#!/usr/bin/env python3
"""Promote the natural battle-8 action-64 group-15 run into one compact artifact."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Mapping

try:
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "battle-effect-group15-natural-runtime-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
VERIFIER_EVIDENCE = {
    "command": [
        "python3",
        "tools/verify_battle_effect_group15_natural_runtime.py",
        "--artifact",
        "artifacts/battle-effect-group15-natural-runtime-v1",
    ],
    "exit_code": 0,
}
PHASES = ("renderer-post", "submit-post", "ack-post")
PHASE_SUFFIXES = (
    "-task-pool.bin",
    "-active-count.bin",
    "-active-pointers.bin",
    "-runtime-offsets.bin",
    "-shadow-oam.bin",
    "-hardware-oam.bin",
    "-submission.bin",
    "-vram.bin",
    "-pram.bin",
    "-io.bin",
    ".ss9",
    ".png",
    "-phase.json",
)
BRANCH_CHAIN_NAMES = (
    "runtime-copy-b",
    "presentation-entry",
    "classification-cmp",
    "dynamic-selector",
    "dynamic-binder-call",
    "binder-entry",
)
EXPECTED_INPUT = {"key": "A", "down_frame": 60, "up_frame": 68, "hold_frames": 8}
BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROUTE_ROM_SHA256 = "6325192e28774efdb30014b87fe7a3e17f2c1bd1f7c34b2484815c156c081b4e"
INPUT_STATE_SHA256 = "c775d4b5ea952f95bdac11993979ad62e11a9418456afc99a54d484b202ce1e1"
TOOLCHAIN_SHA256 = "e21d375914dda3c20b05ccec45c39406db310609e69ee19d04dfa342f4b70287"
ANIMATIONS_SHA256 = "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848"
BRANCH_SCRIPT_SHA256 = "782cfd0c2125ef4753b2504271ed67c9438fe119d7a384dd961d07d7ccbb4f83"
PHASE_SCRIPT_SHA256 = "013b5eda11c067401873e39c068269462ed132cbd968c337c062ef45a00422e5"
BINARY_SHA256 = "c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8"
TOOLCHAIN_SOURCE_COMMIT = "d8bad14b4540f9114246c0281d74985cf81adc68"
ACTION_ID = 64
SEQUENCE_ID = 17
GROUP_ID = 15
TASK_SLOT = 124
TASK_BASE = 0x03003BB8
TASK_SIZE = 0x3C
TASK_ADDRESS = TASK_BASE + TASK_SLOT * TASK_SIZE
DEFINITION_POINTER = 0x0834711C
ANIMATION_POINTER = 0x08347168
PHASE_ADDRESSES = ("0x08063328", "0x08061126", "0x080612AA")
PHASE_PENDING = (0, 1, 0)
REPOSITORY_FILES = (
    "tools/export_battle_effect_group15_natural_runtime.py",
    "tools/verify_battle_effect_group15_natural_runtime.py",
    "tools/mgba_group15_natural_branch_trace.lua",
    "tools/run_macos_mgba_group15_natural_branch_trace.py",
    "tools/mgba_battle_effect_phase_capture.lua",
    "tools/run_macos_mgba_battle_effect_phase_capture.py",
    "tools/run_macos_mgba_input_sequence.py",
    "tools/run_macos_mgba_replay.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/macos_mgba_runtime_residue.py",
    "tools/run_guarded.py",
    "tools/mgba_runtime_safety.py",
    "tools/project_resource_guard.py",
    "tools/build_chapter_battle_route_probe.py",
    "tools/build_chapter_script_probe.py",
    "tools/build_save_state_runtime_probe.py",
    "tools/inspect_mgba_savestate.py",
    "tools/thumb_branch.py",
    "tests/test_export_battle_effect_group15_natural_runtime.py",
    "tests/test_verify_battle_effect_group15_natural_runtime.py",
    "tests/test_mgba_group15_natural_branch_trace_script.py",
    "tests/test_run_macos_mgba_group15_natural_branch_trace.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def expected_archive_members() -> set[str]:
    members = {
        "source/input-state.ss9",
        "source/branch-audit.json",
        "source/branch-guard.json",
        "source/branch-final.ss9",
        "source/branch-final.png",
        "source/branch-done.json",
        "source/phase-profile.json",
        "source/phase-audit.json",
        "source/phase-guard.json",
    }
    members.update(
        f"source/phase/{phase}/capture{suffix}"
        for phase in PHASES
        for suffix in PHASE_SUFFIXES
    )
    return members


def _parse_hex(row: Mapping[str, object], name: str) -> int:
    value = row.get(name)
    if not isinstance(value, str):
        raise ValueError(f"branch event {name} is missing")
    try:
        return int(value, 16)
    except ValueError as error:
        raise ValueError(f"branch event {name} is invalid") from error


def select_branch_chain(events: object) -> list[dict[str, Any]]:
    if not isinstance(events, list) or any(not isinstance(row, dict) for row in events):
        raise ValueError("branch event list is invalid")
    if any(row.get("name") == "special-sequence-6" for row in events):
        raise ValueError("natural branch entered fixed special sequence 6")
    selected: list[dict[str, Any]] = []
    for name in BRANCH_CHAIN_NAMES:
        matches = [row for row in events if row.get("name") == name]
        if len(matches) != 1:
            raise ValueError(f"natural branch must contain one {name} event")
        selected.append(dict(matches[0]))
    try:
        cycles = [int(row["cycle"]) for row in selected]
        frames = [int(row["frame"]) for row in selected]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("natural branch frame/cycle is invalid") from error
    if cycles != sorted(cycles) or len(cycles) != len(set(cycles)):
        raise ValueError("natural branch cycles are not strictly increasing")
    if frames[0] >= frames[1] or len(set(frames[1:])) != 1:
        raise ValueError("natural branch frame sequence mismatch")
    runtime = 0x02026CB8
    if (
        _parse_hex(selected[0], "r4") != runtime
        or _parse_hex(selected[1], "r0") != runtime
        or _parse_hex(selected[2], "r0") != 0
        or _parse_hex(selected[3], "r4") != runtime
    ):
        raise ValueError("natural branch runtime/classification context mismatch")
    for row in selected[4:]:
        if (
            _parse_hex(row, "r0") != 1
            or _parse_hex(row, "r1") != SEQUENCE_ID
            or _parse_hex(row, "r2") != 0x770
        ):
            raise ValueError("natural binder is not side 1 sequence 17")
    return selected


def _validate_guard(guard: dict[str, Any], label: str) -> None:
    if (
        guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or guard.get("completion_trigger") != "success-marker"
    ):
        raise ValueError(f"{label} guard did not complete cleanly")


def _phase_member_paths(source: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for phase in PHASES:
        for suffix in PHASE_SUFFIXES:
            relative = f"{phase}/capture{suffix}"
            path = source / relative
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"missing phase member: {path}")
            paths[f"source/phase/{relative}"] = path
    return paths


def _write_tar(path: Path, members: Mapping[str, Path]) -> None:
    with tarfile.open(path, "w", format=tarfile.PAX_FORMAT) as archive:
        for name, source in sorted(members.items()):
            raw = source.read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(raw))


def _repository_hashes() -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in REPOSITORY_FILES:
        path = ROOT / relative
        if not path.is_file():
            raise ValueError(f"repository dependency is missing: {relative}")
        result[relative] = _sha256(path)
    return result


def export_artifact(
    *,
    input_state: Path,
    branch_audit_path: Path,
    branch_guard_path: Path,
    branch_state_path: Path,
    branch_png_path: Path,
    branch_done_path: Path,
    phase_profile_path: Path,
    phase_source: Path,
    phase_guard_path: Path,
    artifact: Path,
) -> dict[str, Any]:
    paths = {
        "source/input-state.ss9": input_state.resolve(strict=True),
        "source/branch-audit.json": branch_audit_path.resolve(strict=True),
        "source/branch-guard.json": branch_guard_path.resolve(strict=True),
        "source/branch-final.ss9": branch_state_path.resolve(strict=True),
        "source/branch-final.png": branch_png_path.resolve(strict=True),
        "source/branch-done.json": branch_done_path.resolve(strict=True),
        "source/phase-profile.json": phase_profile_path.resolve(strict=True),
        "source/phase-audit.json": (phase_source / "audit.json").resolve(strict=True),
        "source/phase-guard.json": phase_guard_path.resolve(strict=True),
    }
    paths.update(_phase_member_paths(phase_source.resolve(strict=True)))
    if set(paths) != expected_archive_members():
        raise ValueError("natural runtime archive member denominator mismatch")
    if _sha256(paths["source/input-state.ss9"]) != INPUT_STATE_SHA256:
        raise ValueError("natural runtime input state hash mismatch")

    branch = _object(paths["source/branch-audit.json"], "branch audit")
    branch_guard = _object(paths["source/branch-guard.json"], "branch guard")
    branch_done = _object(paths["source/branch-done.json"], "branch completion marker")
    profile = _object(paths["source/phase-profile.json"], "phase profile")
    phase = _object(paths["source/phase-audit.json"], "phase audit")
    phase_guard = _object(paths["source/phase-guard.json"], "phase guard")
    _validate_guard(branch_guard, "branch")
    _validate_guard(phase_guard, "phase")
    if (
        branch.get("schema") != "natural-battle-effect-branch-trace-experiment-v1"
        or branch.get("frame") != 1800
        or branch.get("capture_frame") != 1800
        or branch.get("inputs") != [EXPECTED_INPUT]
        or branch.get("automatic_inputs") != []
        or branch.get("recovery_inputs") != []
        or branch.get("rom_sha256") != ROUTE_ROM_SHA256
        or branch.get("staged_rom_sha256") != ROUTE_ROM_SHA256
        or branch.get("input_state_sha256") != INPUT_STATE_SHA256
        or branch.get("script_sha256") != BRANCH_SCRIPT_SHA256
        or branch.get("binary_sha256") != BINARY_SHA256
        or branch.get("guard_summary_sha256") != _sha256(paths["source/branch-guard.json"])
        or branch.get("output_state_sha256") != _sha256(paths["source/branch-final.ss9"])
        or branch.get("output_png_sha256") != _sha256(paths["source/branch-final.png"])
        or branch.get("completion_marker_sha256") != _sha256(paths["source/branch-done.json"])
    ):
        raise ValueError("natural branch input contract mismatch")
    chain = select_branch_chain(branch.get("events"))
    if branch.get("selected_chain") != chain:
        raise ValueError("natural branch selected chain mismatch")
    if branch_done != {"run_id": branch.get("run_id"), "status": "trace-complete"}:
        raise ValueError("natural branch completion marker mismatch")
    branch_toolchain = branch.get("toolchain")
    if (
        not isinstance(branch_toolchain, dict)
        or branch_toolchain.get("kind") != "current-desktop-runtime-profile"
        or branch_toolchain.get("sha256") != TOOLCHAIN_SHA256
        or branch_toolchain.get("source_commit") != TOOLCHAIN_SOURCE_COMMIT
        or branch_toolchain.get("patch_sha256") is not None
    ):
        raise ValueError("natural branch toolchain mismatch")
    branch_command = branch.get("guard_command")
    if (
        not isinstance(branch_command, list)
        or len(branch_command) != 4
        or branch_guard.get("command") != branch_command
        or branch_command[1] != "--script"
        or Path(branch_command[2]).resolve() != (ROOT / "tools/mgba_group15_natural_branch_trace.lua").resolve()
        or branch_command[3] != branch.get("staged_rom")
    ):
        raise ValueError("natural branch guard command mismatch")
    branch_residue = branch.get("runtime_residue")
    if (
        not isinstance(branch_residue, dict)
        or branch.get("pgid_clean") is not True
        or branch_residue.get("pgid_clean") is not True
        or branch_residue.get("mgba_listener_clean") is not True
        or branch.get("peak_tree_rss_mib") != branch_guard.get("peak_tree_rss_mib")
    ):
        raise ValueError("natural branch runtime residue mismatch")
    for name in ("source/branch-final.ss9", "source/branch-final.png"):
        with paths[name].open("rb") as stream:
            if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                raise ValueError(f"natural branch mGBA container mismatch: {name}")
    expected_phase_input = [EXPECTED_INPUT]
    if (
        phase.get("schema") != "mgba-battle-effect-phase-capture-v1"
        or phase.get("outcome") != "three-phase-captured"
        or phase.get("group_id") != GROUP_ID
        or phase.get("input_mode") != "explicit-single-input"
        or phase.get("inputs") != expected_phase_input
        or phase.get("automatic_inputs") != []
        or phase.get("recovery_inputs") != []
        or phase.get("rom_sha256") != ROUTE_ROM_SHA256
        or phase.get("input_state_sha256") != INPUT_STATE_SHA256
        or phase.get("profile_sha256") != _sha256(paths["source/phase-profile.json"])
        or phase.get("guard_summary_sha256") != _sha256(paths["source/phase-guard.json"])
        or phase.get("animations_sha256") != ANIMATIONS_SHA256
        or phase.get("phase_script_sha256") != PHASE_SCRIPT_SHA256
        or phase.get("definition_pointer") != f"0x{DEFINITION_POINTER:08X}"
        or phase.get("animation_pointer") != f"0x{ANIMATION_POINTER:08X}"
    ):
        raise ValueError("natural phase audit identity mismatch")
    toolchain = phase.get("toolchain")
    if (
        not isinstance(toolchain, dict)
        or toolchain.get("kind") != "current-desktop-runtime-profile"
        or toolchain.get("sha256") != TOOLCHAIN_SHA256
        or toolchain.get("patch_sha256") is not None
    ):
        raise ValueError("natural phase toolchain mismatch")
    recorded_phases = phase.get("phases")
    if not isinstance(recorded_phases, list) or len(recorded_phases) != 3:
        raise ValueError("natural phase sequence is missing")
    action_address = _parse_hex(chain[-1], "r4") + _parse_hex(chain[-1], "r2")
    phase_rows: list[dict[str, Any]] = []
    source_hashes = phase.get("files")
    if not isinstance(source_hashes, dict):
        raise ValueError("natural phase file hash table is missing")
    for index, phase_name in enumerate(PHASES):
        row = recorded_phases[index]
        if (
            row.get("name") != phase_name
            or row.get("address") != PHASE_ADDRESSES[index]
            or row.get("pending") != PHASE_PENDING[index]
            or row.get("task_slot") != TASK_SLOT
            or row.get("task_address") != f"0x{TASK_ADDRESS:08X}"
        ):
            raise ValueError(f"natural phase row mismatch: {phase_name}")
        for suffix in PHASE_SUFFIXES:
            relative = f"{phase_name}/capture{suffix}"
            source = paths[f"source/phase/{relative}"]
            if source_hashes.get(relative) != _sha256(source):
                raise ValueError(f"natural phase source hash mismatch: {relative}")
        state_path = paths[f"source/phase/{phase_name}/capture.ss9"]
        state = load_gba_state(state_path)
        if state.read_memory(action_address, 1) != bytes([ACTION_ID]):
            raise ValueError(f"natural action byte mismatch: {phase_name}")
        task_pool = paths[f"source/phase/{phase_name}/capture-task-pool.bin"].read_bytes()
        task = task_pool[TASK_SLOT * TASK_SIZE:(TASK_SLOT + 1) * TASK_SIZE]
        if (
            len(task) != TASK_SIZE
            or struct.unpack_from("<I", task, 0x1C)[0] != DEFINITION_POINTER
            or struct.unpack_from("<I", task, 0x20)[0] != ANIMATION_POINTER
        ):
            raise ValueError(f"natural group-15 task identity mismatch: {phase_name}")
        count = paths[f"source/phase/{phase_name}/capture-active-count.bin"].read_bytes()[0]
        pointers_raw = paths[f"source/phase/{phase_name}/capture-active-pointers.bin"].read_bytes()
        pointers = struct.unpack(f"<{count}I", pointers_raw[: count * 4])
        if pointers.count(TASK_ADDRESS) != 1:
            raise ValueError(f"natural group-15 task is not unique: {phase_name}")
        shadow = paths[f"source/phase/{phase_name}/capture-shadow-oam.bin"].read_bytes()
        hardware = paths[f"source/phase/{phase_name}/capture-hardware-oam.bin"].read_bytes()
        phase_rows.append(
            {
                **row,
                "action_address": f"0x{action_address:08X}",
                "action_id": ACTION_ID,
                "dispatcher_ordinal": pointers.index(TASK_ADDRESS),
                "active_task_count": count,
                "global_shadow_matches_hardware": shadow == hardware,
            }
        )
    if [row["global_shadow_matches_hardware"] for row in phase_rows] != [False, False, True]:
        raise ValueError("natural global OAM submission sequence mismatch")

    member_hashes = {name: _sha256(path) for name, path in sorted(paths.items())}
    evidence: dict[str, Any] = {
        "schema": SCHEMA,
        "verified": True,
        "execution": {
            "route": "primary scenario 39 diagnostic battle-id substitution",
            "battle_id": 8,
            "character_id": 20,
            "action_id": ACTION_ID,
            "sequence_id": SEQUENCE_ID,
            "group_id": GROUP_ID,
            "input": EXPECTED_INPUT,
            "automatic_inputs": [],
            "recovery_inputs": [],
        },
        "rom": {
            "base_sha256": BASE_ROM_SHA256,
            "route_sha256": ROUTE_ROM_SHA256,
            "difference_count": 1,
            "difference_file_offset": "0x00031071",
            "before": 40,
            "after": 8,
        },
        "branch": {
            "run_id": branch.get("run_id"),
            "raw_event_count": len(branch["events"]),
            "selected_chain": chain,
            "action_address": f"0x{action_address:08X}",
            "guard_peak_tree_rss_mib": branch_guard.get("peak_tree_rss_mib"),
            "runtime_residue": branch_residue,
        },
        "phase": {
            "run_id": phase.get("run_id"),
            "rows": phase_rows,
            "definition_pointer": f"0x{DEFINITION_POINTER:08X}",
            "animation_pointer": f"0x{ANIMATION_POINTER:08X}",
            "task_slot": TASK_SLOT,
            "guard_peak_tree_rss_mib": phase_guard.get("peak_tree_rss_mib"),
            "runtime_residue": phase.get("runtime_residue"),
            "exclusive_task_oam_attribution": False,
        },
        "archive": {"member_count": len(paths), "members": member_hashes},
        "boundary": (
            "The route changes only scenario 39's battle ID to reach original battle 8. "
            "One A confirms end turn; the original AI selects action 64 and naturally "
            "binds side 1 sequence 17/group 15. This proves the branch and one global "
            "renderer/submit/ack transaction containing the stable group-15 task; it does "
            "not prove exclusive task-to-OAM attribution, original-story reachability, action 65, final "
            "pixel A/B, all animation frames, audio, or physical-GBA equivalence."
        ),
    }
    artifact = artifact.resolve()
    if artifact.exists() and (not artifact.is_dir() or any(artifact.iterdir())):
        raise ValueError("artifact directory must be absent or empty")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{artifact.name}-", dir=artifact.parent) as temporary:
        staging = Path(temporary)
        evidence_path = staging / "evidence.json"
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        archive_path = staging / "raw-runtime.tar"
        _write_tar(archive_path, paths)
        manifest = {
            "schema": PROMOTION_SCHEMA,
            "artifact_schema": SCHEMA,
            "artifact_status": "accepted",
            "description": "Natural battle-8 action 64 to side-1 sequence 17/group-15 runtime transaction.",
            "files": {
                "evidence.json": _sha256(evidence_path),
                "raw-runtime.tar": _sha256(archive_path),
            },
            "repository_files": _repository_hashes(),
            "verifier": VERIFIER_EVIDENCE,
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if artifact.exists():
            artifact.rmdir()
        staging.rename(artifact)
    command = [
        sys.executable,
        str(ROOT / "tools/verify_battle_effect_group15_natural_runtime.py"),
        "--artifact",
        str(artifact),
    ]
    completed = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    try:
        verification = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("independent verifier did not return JSON") from error
    if completed.returncode or verification.get("verified") is not True:
        raise ValueError(
            "independent verifier rejected natural runtime artifact: "
            + (completed.stderr or completed.stdout).strip()
        )
    return evidence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-state", type=Path, required=True)
    parser.add_argument("--branch-audit", type=Path, required=True)
    parser.add_argument("--branch-guard", type=Path, required=True)
    parser.add_argument("--branch-state", type=Path, required=True)
    parser.add_argument("--branch-png", type=Path, required=True)
    parser.add_argument("--branch-done", type=Path, required=True)
    parser.add_argument("--phase-profile", type=Path, required=True)
    parser.add_argument("--phase-source", type=Path, required=True)
    parser.add_argument("--phase-guard", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    evidence = export_artifact(
        input_state=args.input_state,
        branch_audit_path=args.branch_audit,
        branch_guard_path=args.branch_guard,
        branch_state_path=args.branch_state,
        branch_png_path=args.branch_png,
        branch_done_path=args.branch_done,
        phase_profile_path=args.phase_profile,
        phase_source=args.phase_source,
        phase_guard_path=args.phase_guard,
        artifact=args.artifact,
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
