#!/usr/bin/env python3
"""Independently verify the natural battle-8 action-64 group-15 artifact."""

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
    "-task-pool.bin", "-active-count.bin", "-active-pointers.bin",
    "-runtime-offsets.bin", "-shadow-oam.bin", "-hardware-oam.bin",
    "-submission.bin", "-vram.bin", "-pram.bin", "-io.bin",
    ".ss9", ".png", "-phase.json",
)
EXPECTED_ARCHIVE_MEMBERS = {
    "source/input-state.ss9",
    "source/branch-audit.json",
    "source/branch-guard.json",
    "source/branch-final.ss9",
    "source/branch-final.png",
    "source/branch-done.json",
    "source/phase-profile.json",
    "source/phase-audit.json",
    "source/phase-guard.json",
    *(
        f"source/phase/{phase}/capture{suffix}"
        for phase in PHASES
        for suffix in PHASE_SUFFIXES
    ),
}
EXPECTED_REPOSITORY_FILES = (
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
CHAIN = (
    ("runtime-copy-b", "0x0807A222"),
    ("presentation-entry", "0x0807F064"),
    ("classification-cmp", "0x0807F09E"),
    ("dynamic-selector", "0x0807F0FC"),
    ("dynamic-binder-call", "0x0807F10C"),
    ("binder-entry", "0x0807C5E8"),
)
BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROUTE_ROM_SHA256 = "6325192e28774efdb30014b87fe7a3e17f2c1bd1f7c34b2484815c156c081b4e"
INPUT_STATE_SHA256 = "c775d4b5ea952f95bdac11993979ad62e11a9418456afc99a54d484b202ce1e1"
TOOLCHAIN_SHA256 = "e21d375914dda3c20b05ccec45c39406db310609e69ee19d04dfa342f4b70287"
ANIMATIONS_SHA256 = "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848"
BRANCH_SCRIPT_SHA256 = "782cfd0c2125ef4753b2504271ed67c9438fe119d7a384dd961d07d7ccbb4f83"
PHASE_SCRIPT_SHA256 = "013b5eda11c067401873e39c068269462ed132cbd968c337c062ef45a00422e5"
BINARY_SHA256 = "c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8"
TOOLCHAIN_SOURCE_COMMIT = "d8bad14b4540f9114246c0281d74985cf81adc68"
PHASE_ADDRESSES = ("0x08063328", "0x08061126", "0x080612AA")
PHASE_PENDING = (0, 1, 0)
ACTION_ID = 64
SEQUENCE_ID = 17
GROUP_ID = 15
TASK_SLOT = 124
TASK_BASE = 0x03003BB8
TASK_SIZE = 0x3C
TASK_ADDRESS = TASK_BASE + TASK_SLOT * TASK_SIZE
DEFINITION_POINTER = 0x0834711C
ANIMATION_POINTER = 0x08347168
ROUTE_OFFSET = 0x31071
MAX_JSON_MEMBER_BYTES = 1024 * 1024
MAX_CONTAINER_MEMBER_BYTES = 512 * 1024
MAX_ARCHIVE_PAYLOAD_BYTES = 8 * 1024 * 1024
FIXED_PHASE_MEMBER_SIZES = {
    "-task-pool.bin": 0x3C * 128,
    "-active-count.bin": 1,
    "-active-pointers.bin": 0x200,
    "-runtime-offsets.bin": 0x20,
    "-shadow-oam.bin": 0x400,
    "-hardware-oam.bin": 0x400,
    "-submission.bin": 2,
    "-vram.bin": 0x18000,
    "-pram.bin": 0x400,
    "-io.bin": 0x400,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_path(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def read_safe_tar(path: Path) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    total_size = 0
    with tarfile.open(path, "r|") as archive:
        for member in archive:
            pure = PurePosixPath(member.name)
            if (
                member.name != pure.as_posix()
                or pure.is_absolute()
                or ".." in pure.parts
                or not member.isfile()
                or member.issym()
                or member.islnk()
                or member.name in payloads
            ):
                raise ValueError(f"unsafe archive member: {member.name}")
            if member.name not in EXPECTED_ARCHIVE_MEMBERS:
                raise ValueError(f"unexpected archive member: {member.name}")
            if len(payloads) >= len(EXPECTED_ARCHIVE_MEMBERS):
                raise ValueError("archive member count limit exceeded")
            limit = MAX_JSON_MEMBER_BYTES
            exact_size = None
            if member.name.endswith((".ss9", ".png")):
                limit = MAX_CONTAINER_MEMBER_BYTES
            for suffix, size in FIXED_PHASE_MEMBER_SIZES.items():
                if member.name.endswith(suffix):
                    exact_size = size
                    limit = size
                    break
            if member.size < 0 or member.size > limit:
                raise ValueError(f"archive member size limit exceeded: {member.name}")
            if exact_size is not None and member.size != exact_size:
                raise ValueError(f"archive member exact size mismatch: {member.name}")
            total_size += member.size
            if total_size > MAX_ARCHIVE_PAYLOAD_BYTES:
                raise ValueError("archive total size limit exceeded")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"archive member is unreadable: {member.name}")
            payloads[member.name] = stream.read()
    if set(payloads) != EXPECTED_ARCHIVE_MEMBERS:
        raise ValueError("archive member denominator mismatch")
    return payloads


def _hex(row: dict[str, Any], field: str) -> int:
    try:
        return int(row[field], 16)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"branch {field} is invalid") from error


def _branch_chain(events: Any) -> list[dict[str, Any]]:
    if not isinstance(events, list) or any(not isinstance(row, dict) for row in events):
        raise ValueError("branch events are invalid")
    if any(row.get("name") == "special-sequence-6" for row in events):
        raise ValueError("branch incorrectly entered special sequence 6")
    selected: list[dict[str, Any]] = []
    for name, address in CHAIN:
        matches = [row for row in events if row.get("name") == name]
        if len(matches) != 1 or matches[0].get("address") != address:
            raise ValueError(f"branch chain mismatch: {name}")
        selected.append(matches[0])
    cycles = [int(row["cycle"]) for row in selected]
    frames = [int(row["frame"]) for row in selected]
    if cycles != sorted(set(cycles)) or frames[0] >= frames[1] or len(set(frames[1:])) != 1:
        raise ValueError("branch ordering mismatch")
    runtime = 0x02026CB8
    if (
        _hex(selected[0], "r4") != runtime
        or _hex(selected[1], "r0") != runtime
        or _hex(selected[2], "r0") != 0
        or _hex(selected[3], "r4") != runtime
    ):
        raise ValueError("branch runtime/classification mismatch")
    for row in selected[4:]:
        if _hex(row, "r0") != 1 or _hex(row, "r1") != 17 or _hex(row, "r2") != 0x770:
            raise ValueError("branch binder is not side 1 sequence 17")
    return selected


def _guard(payload: dict[str, Any], label: str) -> None:
    if (
        payload.get("reason") != "completed"
        or payload.get("exit_code") != 0
        or payload.get("degraded") is not False
        or payload.get("completion_trigger") != "success-marker"
    ):
        raise ValueError(f"{label} guard mismatch")


def _verify_repository(manifest: dict[str, Any]) -> None:
    hashes = manifest.get("repository_files")
    if not isinstance(hashes, dict) or set(hashes) != set(EXPECTED_REPOSITORY_FILES):
        raise ValueError("repository dependency denominator mismatch")
    for relative in EXPECTED_REPOSITORY_FILES:
        path = ROOT / relative
        if not path.is_file() or _sha256(path) != hashes[relative]:
            raise ValueError(f"repository dependency hash mismatch: {relative}")
    if hashes["tools/mgba_group15_natural_branch_trace.lua"] != BRANCH_SCRIPT_SHA256:
        raise ValueError("branch observer script identity mismatch")
    if hashes["tools/mgba_battle_effect_phase_capture.lua"] != PHASE_SCRIPT_SHA256:
        raise ValueError("phase capture script identity mismatch")


def _verify_route() -> None:
    base_path = ROOT / "rom/base.gba"
    if _sha256(base_path) != BASE_ROM_SHA256:
        raise ValueError("base ROM hash mismatch")
    base = base_path.read_bytes()
    if base[0x31070:0x31074] != b"\x1A\x28\x02\x00":
        raise ValueError("primary scenario 39 command mismatch")
    route = bytearray(base)
    route[ROUTE_OFFSET] = 8
    differences = [i for i, (a, b) in enumerate(zip(base, route, strict=True)) if a != b]
    if differences != [ROUTE_OFFSET] or _sha256_bytes(route) != ROUTE_ROM_SHA256:
        raise ValueError("battle-8 route reconstruction mismatch")


def _verify_payloads(payloads: dict[str, bytes], evidence: dict[str, Any]) -> dict[str, Any]:
    archive = evidence.get("archive")
    if (
        not isinstance(archive, dict)
        or archive.get("member_count") != 48
        or not isinstance(archive.get("members"), dict)
        or set(archive["members"]) != EXPECTED_ARCHIVE_MEMBERS
    ):
        raise ValueError("evidence archive denominator mismatch")
    for name, raw in payloads.items():
        if archive["members"].get(name) != _sha256_bytes(raw):
            raise ValueError(f"evidence archive hash mismatch: {name}")
    if _sha256_bytes(payloads["source/input-state.ss9"]) != INPUT_STATE_SHA256:
        raise ValueError("input state hash mismatch")
    branch = _json_bytes(payloads["source/branch-audit.json"], "branch audit")
    branch_guard = _json_bytes(payloads["source/branch-guard.json"], "branch guard")
    branch_done = _json_bytes(payloads["source/branch-done.json"], "branch completion marker")
    profile = _json_bytes(payloads["source/phase-profile.json"], "phase profile")
    phase = _json_bytes(payloads["source/phase-audit.json"], "phase audit")
    phase_guard = _json_bytes(payloads["source/phase-guard.json"], "phase guard")
    _guard(branch_guard, "branch")
    _guard(phase_guard, "phase")
    if (
        branch.get("schema") != "natural-battle-effect-branch-trace-experiment-v1"
        or branch.get("frame") != 1800
        or branch.get("capture_frame") != 1800
        or branch.get("inputs")
        != [{"key": "A", "down_frame": 60, "up_frame": 68, "hold_frames": 8}]
        or branch.get("automatic_inputs") != []
        or branch.get("recovery_inputs") != []
        or branch.get("rom_sha256") != ROUTE_ROM_SHA256
        or branch.get("staged_rom_sha256") != ROUTE_ROM_SHA256
        or branch.get("input_state_sha256") != INPUT_STATE_SHA256
        or branch.get("script_sha256") != BRANCH_SCRIPT_SHA256
        or branch.get("binary_sha256") != BINARY_SHA256
        or branch.get("guard_summary_sha256")
        != _sha256_bytes(payloads["source/branch-guard.json"])
        or branch.get("output_state_sha256")
        != _sha256_bytes(payloads["source/branch-final.ss9"])
        or branch.get("output_png_sha256")
        != _sha256_bytes(payloads["source/branch-final.png"])
        or branch.get("completion_marker_sha256")
        != _sha256_bytes(payloads["source/branch-done.json"])
    ):
        raise ValueError("branch input contract mismatch")
    selected = _branch_chain(branch.get("events"))
    if branch.get("selected_chain") != selected:
        raise ValueError("branch selected chain mismatch")
    if branch_done != {"run_id": branch.get("run_id"), "status": "trace-complete"}:
        raise ValueError("branch completion marker mismatch")
    for name in ("source/branch-final.ss9", "source/branch-final.png"):
        if payloads[name][:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"branch mGBA container mismatch: {name}")
    branch_toolchain = branch.get("toolchain")
    if (
        not isinstance(branch_toolchain, dict)
        or branch_toolchain.get("kind") != "current-desktop-runtime-profile"
        or branch_toolchain.get("sha256") != TOOLCHAIN_SHA256
        or branch_toolchain.get("source_commit") != TOOLCHAIN_SOURCE_COMMIT
        or branch_toolchain.get("patch_sha256") is not None
    ):
        raise ValueError("branch toolchain mismatch")
    branch_command = branch.get("guard_command")
    if (
        not isinstance(branch_command, list)
        or len(branch_command) != 4
        or branch_guard.get("command") != branch_command
        or branch_command[1] != "--script"
        or Path(branch_command[2]).resolve()
        != (ROOT / "tools/mgba_group15_natural_branch_trace.lua").resolve()
        or branch_command[3] != branch.get("staged_rom")
    ):
        raise ValueError("branch guard command mismatch")
    branch_residue = branch.get("runtime_residue")
    if (
        not isinstance(branch_residue, dict)
        or branch.get("pgid_clean") is not True
        or branch_residue.get("pgid_clean") is not True
        or branch_residue.get("mgba_listener_clean") is not True
        or branch.get("peak_tree_rss_mib") != branch_guard.get("peak_tree_rss_mib")
    ):
        raise ValueError("branch runtime residue mismatch")
    action_address = _hex(selected[-1], "r4") + _hex(selected[-1], "r2")
    if evidence.get("branch", {}).get("selected_chain") != selected:
        raise ValueError("evidence branch chain differs from raw trace")
    execution = evidence.get("execution")
    if (
        not isinstance(execution, dict)
        or execution.get("battle_id") != 8
        or execution.get("character_id") != 20
        or execution.get("action_id") != ACTION_ID
        or execution.get("sequence_id") != SEQUENCE_ID
        or execution.get("group_id") != GROUP_ID
        or execution.get("input")
        != {"key": "A", "down_frame": 60, "up_frame": 68, "hold_frames": 8}
        or execution.get("automatic_inputs") != []
        or execution.get("recovery_inputs") != []
    ):
        raise ValueError("action identity or input scope mismatch")
    rom = evidence.get("rom")
    if (
        not isinstance(rom, dict)
        or rom.get("base_sha256") != BASE_ROM_SHA256
        or rom.get("route_sha256") != ROUTE_ROM_SHA256
        or rom.get("difference_count") != 1
        or rom.get("difference_file_offset") != "0x00031071"
        or rom.get("before") != 40
        or rom.get("after") != 8
    ):
        raise ValueError("route evidence mismatch")
    if (
        profile.get("profile_id") != "natural-battle8-action64-group15-ai-preconfirm"
        or profile.get("group_id") != GROUP_ID
        or profile.get("sequence_id") != SEQUENCE_ID
        or profile.get("input_state_sha256") != INPUT_STATE_SHA256
        or profile.get("runtime_input")
        != {"key": "A", "down_frame": 60, "up_frame": 68, "capture_frame": 1800}
    ):
        raise ValueError("phase profile mismatch")
    if (
        phase.get("schema") != "mgba-battle-effect-phase-capture-v1"
        or phase.get("outcome") != "three-phase-captured"
        or phase.get("group_id") != GROUP_ID
        or phase.get("input_mode") != "explicit-single-input"
        or phase.get("inputs")
        != [{"key": "A", "down_frame": 60, "up_frame": 68, "hold_frames": 8}]
        or phase.get("automatic_inputs") != []
        or phase.get("recovery_inputs") != []
        or phase.get("rom_sha256") != ROUTE_ROM_SHA256
        or phase.get("input_state_sha256") != INPUT_STATE_SHA256
        or phase.get("profile_sha256") != _sha256_bytes(payloads["source/phase-profile.json"])
        or phase.get("guard_summary_sha256") != _sha256_bytes(payloads["source/phase-guard.json"])
        or phase.get("animations_sha256") != ANIMATIONS_SHA256
        or phase.get("phase_script_sha256") != PHASE_SCRIPT_SHA256
        or phase.get("definition_pointer") != f"0x{DEFINITION_POINTER:08X}"
        or phase.get("animation_pointer") != f"0x{ANIMATION_POINTER:08X}"
    ):
        raise ValueError("phase runtime identity mismatch")
    toolchain = phase.get("toolchain")
    if (
        not isinstance(toolchain, dict)
        or toolchain.get("kind") != "current-desktop-runtime-profile"
        or toolchain.get("sha256") != TOOLCHAIN_SHA256
        or toolchain.get("patch_sha256") is not None
    ):
        raise ValueError("phase toolchain mismatch")
    files = phase.get("files")
    rows = phase.get("phases")
    if not isinstance(files, dict) or not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("phase file/row denominator mismatch")
    pending: list[int] = []
    matches: list[bool] = []
    evidence_rows = evidence.get("phase", {}).get("rows")
    if not isinstance(evidence_rows, list) or len(evidence_rows) != 3:
        raise ValueError("evidence phase rows are missing")
    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary)
        for index, phase_name in enumerate(PHASES):
            row = rows[index]
            if (
                row.get("name") != phase_name
                or row.get("address") != PHASE_ADDRESSES[index]
                or row.get("pending") != PHASE_PENDING[index]
                or row.get("task_slot") != TASK_SLOT
                or row.get("task_address") != f"0x{TASK_ADDRESS:08X}"
            ):
                raise ValueError(f"phase row mismatch: {phase_name}")
            for suffix in PHASE_SUFFIXES:
                relative = f"{phase_name}/capture{suffix}"
                raw = payloads[f"source/phase/{relative}"]
                if files.get(relative) != _sha256_bytes(raw):
                    raise ValueError(f"phase member hash mismatch: {relative}")
            state_path = temporary_root / f"{phase_name}.ss9"
            state_path.write_bytes(payloads[f"source/phase/{phase_name}/capture.ss9"])
            state = load_gba_state(state_path)
            if state.read_memory(action_address, 1) != bytes([ACTION_ID]):
                raise ValueError(f"phase action byte mismatch: {phase_name}")
            task_pool = payloads[f"source/phase/{phase_name}/capture-task-pool.bin"]
            task = task_pool[TASK_SLOT * TASK_SIZE:(TASK_SLOT + 1) * TASK_SIZE]
            if (
                len(task) != TASK_SIZE
                or struct.unpack_from("<I", task, 0x1C)[0] != DEFINITION_POINTER
                or struct.unpack_from("<I", task, 0x20)[0] != ANIMATION_POINTER
            ):
                raise ValueError(f"phase task identity mismatch: {phase_name}")
            count = payloads[f"source/phase/{phase_name}/capture-active-count.bin"][0]
            pointer_raw = payloads[f"source/phase/{phase_name}/capture-active-pointers.bin"]
            pointers = struct.unpack(f"<{count}I", pointer_raw[: count * 4])
            if pointers.count(TASK_ADDRESS) != 1:
                raise ValueError(f"phase task dispatcher mismatch: {phase_name}")
            shadow = payloads[f"source/phase/{phase_name}/capture-shadow-oam.bin"]
            hardware = payloads[f"source/phase/{phase_name}/capture-hardware-oam.bin"]
            match = shadow == hardware
            if evidence_rows[index] != {
                **row,
                "action_address": f"0x{action_address:08X}",
                "action_id": ACTION_ID,
                "dispatcher_ordinal": pointers.index(TASK_ADDRESS),
                "active_task_count": count,
                "global_shadow_matches_hardware": match,
            }:
                raise ValueError(f"evidence phase row differs from raw: {phase_name}")
            pending.append(row["pending"])
            matches.append(match)
    if pending != [0, 1, 0] or matches != [False, False, True]:
        raise ValueError("global phase submission transaction mismatch")
    if evidence.get("phase", {}).get("exclusive_task_oam_attribution") is not False:
        raise ValueError("exclusive task OAM attribution boundary mismatch")
    residue = phase.get("runtime_residue")
    if (
        not isinstance(residue, dict)
        or residue.get("pgid_clean") is not True
        or residue.get("mgba_listener_clean") is not True
        or phase.get("pgid_clean") is not True
        or phase.get("peak_tree_rss_mib") != phase_guard.get("peak_tree_rss_mib")
        or branch.get("peak_tree_rss_mib") != branch_guard.get("peak_tree_rss_mib")
    ):
        raise ValueError("runtime resource/residue evidence mismatch")
    return {
        "action_id": ACTION_ID,
        "sequence_id": SEQUENCE_ID,
        "group_id": GROUP_ID,
        "phase_pending": pending,
    }


def verify_artifact(artifact: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "verified": False,
        "errors": [],
        "action_id": None,
        "sequence_id": None,
        "group_id": None,
        "phase_pending": [],
    }
    try:
        artifact = Path(artifact).resolve(strict=True)
        manifest = _json_path(artifact / "manifest.json")
        evidence = _json_path(artifact / "evidence.json")
        if (
            manifest.get("schema") != PROMOTION_SCHEMA
            or manifest.get("artifact_schema") != SCHEMA
            or manifest.get("artifact_status") != "accepted"
            or manifest.get("verifier") != VERIFIER_EVIDENCE
            or evidence.get("schema") != SCHEMA
            or evidence.get("verified") is not True
        ):
            raise ValueError("artifact schema/status mismatch")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != {"evidence.json", "raw-runtime.tar"}:
            raise ValueError("artifact file denominator mismatch")
        for relative, expected in files.items():
            path = artifact / relative
            if not path.is_file() or _sha256(path) != expected:
                raise ValueError(f"artifact file hash mismatch: {relative}")
        _verify_repository(manifest)
        _verify_route()
        payloads = read_safe_tar(artifact / "raw-runtime.tar")
        result.update(_verify_payloads(payloads, evidence))
        result["verified"] = True
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, tarfile.TarError, struct.error) as error:
        result["errors"].append(str(error))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args(argv)
    result = verify_artifact(args.artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
