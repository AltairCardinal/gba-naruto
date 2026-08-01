#!/usr/bin/env python3
"""Capture one battle-effect task at renderer, OAM-copy, and acknowledgement posts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from typing import Any, Mapping, Sequence

try:
    from tools.macos_mgba_runtime_residue import RuntimeResidueError, probe_runtime_residue
    from tools.run_macos_mgba_input_sequence import encode_schedule, parse_input_events
    from tools.run_macos_mgba_replay import (
        EXPECTED_PATCH_SHA256,
        ReplayError,
        canonical_input,
        emulator_command,
        guarded_command,
        prepare_fresh_output,
        read_ps_snapshot,
        sha256_file,
        validate_build_manifest,
        validate_completion_marker,
        validate_expected_hash,
        validate_guard_summary,
        validate_owned_pgid_clean,
    )
    from tools.run_macos_mgba_single_input import PNG_SIGNATURE, _absolute, _load_json, _require_fresh_regular
except ModuleNotFoundError:
    from macos_mgba_runtime_residue import RuntimeResidueError, probe_runtime_residue
    from run_macos_mgba_input_sequence import encode_schedule, parse_input_events
    from run_macos_mgba_replay import (
        EXPECTED_PATCH_SHA256,
        ReplayError,
        canonical_input,
        emulator_command,
        guarded_command,
        prepare_fresh_output,
        read_ps_snapshot,
        sha256_file,
        validate_build_manifest,
        validate_completion_marker,
        validate_expected_hash,
        validate_guard_summary,
        validate_owned_pgid_clean,
    )
    from run_macos_mgba_single_input import PNG_SIGNATURE, _absolute, _load_json, _require_fresh_regular


ROOT = Path(__file__).resolve().parents[1]
PHASE_SCRIPT = ROOT / "tools/mgba_battle_effect_phase_capture.lua"
PHASE_SCRIPT_SHA256 = "013b5eda11c067401873e39c068269462ed132cbd968c337c062ef45a00422e5"
ANIMATIONS = ROOT / "artifacts/battle-effect-sprite-animations-v1/manifest.json"
ANIMATIONS_SHA256 = "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848"
CURRENT_TOOLCHAIN_PROFILE_SHA256 = "e21d375914dda3c20b05ccec45c39406db310609e69ee19d04dfa342f4b70287"
CURRENT_MGBA_SOURCE_COMMIT = "d8bad14b4540f9114246c0281d74985cf81adc68"
PHASE_TAIL_FRAMES = 60
PHASES = (
    ("renderer-post", "0x08063328"),
    ("submit-post", "0x08061126"),
    ("ack-post", "0x080612AA"),
)
CAPTURE_FILE_SIZES = {
    "task-pool.bin": 0x3C * 128,
    "active-count.bin": 1,
    "active-pointers.bin": 0x200,
    "runtime-offsets.bin": 0x20,
    "shadow-oam.bin": 0x400,
    "hardware-oam.bin": 0x400,
    "submission.bin": 2,
    "vram.bin": 0x18000,
    "pram.bin": 0x400,
    "io.bin": 0x400,
}


def _object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReplayError(f"invalid {label}: {path}") from error
    if not isinstance(value, dict):
        raise ReplayError(f"{label} must be a JSON object")
    return value


def load_capture_profile(profile_path: Path, animations_path: Path) -> dict[str, Any]:
    profile_path = profile_path.resolve(strict=True)
    animations_path = animations_path.resolve(strict=True)
    profile = _object(profile_path, "battle-effect phase profile")
    animations = _object(animations_path, "battle-effect animation catalog")
    schema = profile.get("schema")
    if schema not in {
        "battle-effect-pixel-ab-profile-v1",
        "battle-effect-phase-capture-profile-v1",
    }:
        raise ReplayError("battle-effect phase profile schema mismatch")
    if animations.get("schema") != "battle-effect-sprite-animations-v1":
        raise ReplayError("battle-effect animation catalog schema mismatch")
    groups = animations.get("groups")
    if not isinstance(groups, list) or animations.get("group_count") != len(groups):
        raise ReplayError("battle-effect animation group denominator mismatch")
    group_id = profile.get("group_id")
    if not isinstance(group_id, int) or isinstance(group_id, bool):
        raise ReplayError("battle-effect profile group_id must be an integer")
    matches = [row for row in groups if row.get("group_id") == group_id]
    if len(matches) != 1:
        raise ReplayError("battle-effect profile group is absent or ambiguous")
    if schema == "battle-effect-pixel-ab-profile-v1":
        input_mode = "explicit-single-input"
        runtime = profile.get("runtime_input")
        if not isinstance(runtime, dict):
            raise ReplayError("battle-effect profile runtime_input is missing")
        key = runtime.get("key")
        down = runtime.get("down_frame")
        up = runtime.get("up_frame")
        capture = runtime.get("capture_frame")
        if any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in (down, up, capture)
        ):
            raise ReplayError("battle-effect profile input frames must be integers")
        events = parse_input_events([f"{key}:{down}:{up}"], capture)
        timeout = capture + PHASE_TAIL_FRAMES
    else:
        input_mode = profile.get("input_mode")
        timeout = profile.get("timeout_frames")
        if input_mode != "zero-input-active-state":
            raise ReplayError("battle-effect phase profile input mode mismatch")
        if (
            not isinstance(timeout, int)
            or isinstance(timeout, bool)
            or not 1 <= timeout <= 600
        ):
            raise ReplayError("battle-effect phase profile timeout is invalid")
        capture = 0
        events = []
    raw_state = profile.get("input_state")
    if not isinstance(raw_state, str) or not raw_state:
        raise ReplayError("battle-effect profile input_state is missing")
    state = Path(raw_state)
    if not state.is_absolute():
        state = ROOT / state
    state = state.resolve(strict=True)
    expected_state_hash = profile.get("input_state_sha256")
    if not isinstance(expected_state_hash, str):
        raise ReplayError("battle-effect profile input state hash is missing")
    validate_expected_hash(state, expected_state_hash, "battle-effect input state")
    group = matches[0]
    try:
        definition = int(group["definition_pointer_table"], 16)
        animation = int(group["animation_pointer_table"], 16)
    except (KeyError, TypeError, ValueError) as error:
        raise ReplayError("battle-effect group identity pointers are invalid") from error
    return {
        "profile": profile,
        "profile_path": profile_path,
        "profile_sha256": sha256_file(profile_path),
        "profile_id": profile.get("profile_id"),
        "group_id": group_id,
        "definition_pointer": definition,
        "animation_pointer": animation,
        "input_state": state,
        "input_state_sha256": expected_state_hash,
        "input_mode": input_mode,
        "events": events,
        "input_schedule": encode_schedule(events),
        "capture_frames": capture,
        "timeout_frames": timeout,
        "animations_path": animations_path,
        "animations_sha256": sha256_file(animations_path),
    }


def validate_current_toolchain_profile(
    profile_path: Path, binary: Path, expected_binary_sha256: str
) -> dict[str, Any]:
    """Validate the current desktop mGBA against its accepted runtime evidence."""
    profile = _object(profile_path, "mGBA runtime profile")
    if profile.get("schema") != "rom-expansion-profile-v1":
        raise ReplayError("mGBA runtime profile schema mismatch")
    if profile.get("identity") != "agb_standard_16mib_sequel_rom_profile":
        raise ReplayError("mGBA runtime profile identity mismatch")
    hardware = profile.get("hardware_evidence")
    if not isinstance(hardware, dict):
        raise ReplayError("mGBA runtime profile hardware evidence is missing")
    if hardware.get("mgba_source_commit") != CURRENT_MGBA_SOURCE_COMMIT:
        raise ReplayError("mGBA runtime profile source commit mismatch")
    if hardware.get("mgba_binary_sha256") != expected_binary_sha256:
        raise ReplayError("mGBA runtime profile binary hash mismatch")
    validate_expected_hash(binary, expected_binary_sha256, "mGBA binary")
    runtime = profile.get("runtime_probe")
    if not isinstance(runtime, dict):
        raise ReplayError("mGBA runtime profile probe evidence is missing")
    expected_runtime = {
        "guard_reason": "completed",
        "guard_completion_trigger": "success-marker",
        "guard_exit_code": 0,
        "guard_degraded": False,
        "new_mgba_crash_report": False,
        "owned_process_residue": False,
    }
    for field, expected in expected_runtime.items():
        if runtime.get(field) != expected:
            raise ReplayError(f"mGBA runtime profile {field} mismatch")
    return profile


def validate_phase_payload(payload: Mapping[str, object], expected: Mapping[str, object]) -> None:
    if payload.get("schema") != "mgba-battle-effect-phase-capture-v1":
        raise ReplayError("battle-effect phase payload schema mismatch")
    if payload.get("outcome") != "three-phase-captured":
        raise ReplayError("battle-effect three-phase transaction is incomplete")
    if payload.get("group_id") != expected["group_id"]:
        raise ReplayError("battle-effect phase group mismatch")
    for field in ("definition_pointer", "animation_pointer"):
        if payload.get(field) != f"0x{int(expected[field]):08X}":
            raise ReplayError(f"battle-effect phase {field} mismatch")
    if payload.get("automatic_inputs") != [] or payload.get("recovery_inputs") != []:
        raise ReplayError("battle-effect phase capture contains implicit inputs")
    if payload.get("input_mode") != expected["input_mode"]:
        raise ReplayError("battle-effect phase input mode mismatch")
    if expected["input_mode"] == "zero-input-active-state":
        expected_events = []
    else:
        expected_events = parse_input_events(
            [expected["input_schedule"]], int(expected["capture_frames"])
        )
    if payload.get("inputs") != expected_events:
        raise ReplayError("battle-effect phase input schedule mismatch")
    phases = payload.get("phases")
    if not isinstance(phases, list) or len(phases) != 3:
        raise ReplayError("battle-effect phase transaction must contain exactly three phases")
    cycles: list[int] = []
    for index, ((name, address), phase) in enumerate(zip(PHASES, phases, strict=True)):
        if not isinstance(phase, dict) or phase.get("name") != name:
            raise ReplayError("battle-effect phases are absent or out of order")
        phase_address = phase.get("address")
        if phase_address != address:
            raise ReplayError("battle-effect phase address mismatch")
        try:
            cycles.append(int(str(phase["cycle"]), 10))
        except (KeyError, TypeError, ValueError) as error:
            raise ReplayError("battle-effect phase cycle is invalid") from error
    if cycles != sorted(cycles) or len(set(cycles)) != 3:
        raise ReplayError("battle-effect phase cycles are not strictly ordered")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    toolchain = parser.add_mutually_exclusive_group(required=True)
    toolchain.add_argument("--toolchain-profile", type=Path)
    toolchain.add_argument("--build-manifest", type=Path)
    parser.add_argument("--expected-build-manifest-sha256")
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--expected-rom-sha256", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--expected-profile-sha256", required=True)
    parser.add_argument("--staged-rom", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--guard-summary", type=Path, required=True)
    parser.add_argument("--wall-timeout-s", type=float, default=180)
    parser.add_argument("--idle-timeout-s", type=float, default=45)
    return parser


def _canonical_output(path: Path) -> Path:
    return _absolute(path).resolve(strict=False)


def validate_args(args: argparse.Namespace) -> argparse.Namespace:
    if args.wall_timeout_s <= 0 or args.idle_timeout_s <= 0:
        raise ReplayError("wall and idle timeouts must be positive")
    args.binary = canonical_input(args.binary, "mGBA binary")
    args.rom = canonical_input(args.rom, "ROM")
    args.profile = canonical_input(args.profile, "battle-effect profile")
    args.phase_script = canonical_input(PHASE_SCRIPT, "battle-effect phase script")
    args.animations = canonical_input(ANIMATIONS, "battle-effect animation catalog")
    validate_expected_hash(args.phase_script, PHASE_SCRIPT_SHA256, "battle-effect phase script")
    validate_expected_hash(args.animations, ANIMATIONS_SHA256, "battle-effect animation catalog")
    validate_expected_hash(args.profile, args.expected_profile_sha256, "battle-effect profile")
    validate_expected_hash(args.binary, args.expected_binary_sha256, "mGBA binary")
    if args.toolchain_profile is not None:
        if args.expected_build_manifest_sha256 is not None:
            raise ReplayError("current mGBA mode must not supply a legacy manifest hash")
        args.toolchain_profile = canonical_input(
            args.toolchain_profile, "mGBA runtime profile"
        )
        validate_expected_hash(
            args.toolchain_profile,
            CURRENT_TOOLCHAIN_PROFILE_SHA256,
            "mGBA runtime profile",
        )
        payload = validate_current_toolchain_profile(
            args.toolchain_profile, args.binary, args.expected_binary_sha256
        )
        args.toolchain_artifact = args.toolchain_profile
        args.toolchain_artifact_sha256 = CURRENT_TOOLCHAIN_PROFILE_SHA256
        args.toolchain_kind = "current-desktop-runtime-profile"
        args.toolchain_source_commit = CURRENT_MGBA_SOURCE_COMMIT
        args.toolchain_patch_sha256 = None
    else:
        if args.expected_build_manifest_sha256 is None:
            raise ReplayError("legacy mGBA mode requires its expected manifest hash")
        args.build_manifest = canonical_input(args.build_manifest, "legacy build manifest")
        validate_expected_hash(
            args.build_manifest,
            args.expected_build_manifest_sha256,
            "legacy build manifest",
        )
        payload = validate_build_manifest(
            args.build_manifest, args.binary, args.expected_binary_sha256
        )
        args.toolchain_artifact = args.build_manifest
        args.toolchain_artifact_sha256 = args.expected_build_manifest_sha256
        args.toolchain_kind = "legacy-checkpoint-compatible-build-manifest"
        args.toolchain_source_commit = payload["source_commit"]
        args.toolchain_patch_sha256 = EXPECTED_PATCH_SHA256
    args.toolchain_payload = payload
    validate_expected_hash(args.rom, args.expected_rom_sha256, "ROM")
    args.capture = load_capture_profile(args.profile, args.animations)
    if len(_object(args.animations, "battle-effect animation catalog").get("groups", [])) != 18:
        raise ReplayError("production battle-effect group denominator must be 18")
    args.staged_rom = _canonical_output(args.staged_rom)
    args.output_dir = _canonical_output(args.output_dir)
    args.guard_summary = _canonical_output(args.guard_summary)
    args.done_marker = _canonical_output(Path(f"{args.guard_summary}.done.json"))
    args.staged_save = args.staged_rom.with_suffix(".sav")
    source_save = args.rom.with_suffix(".sav")
    if source_save.exists():
        raise ReplayError("source ROM save sidecar must be absent")
    inputs = {
        args.binary,
        args.toolchain_artifact,
        args.rom,
        args.profile,
        args.phase_script,
        args.animations,
        args.capture["input_state"],
    }
    outputs = {args.staged_rom, args.staged_save, args.output_dir, args.guard_summary, args.done_marker}
    for output in outputs:
        for input_path in inputs:
            if output == input_path or output in input_path.parents or input_path in output.parents:
                raise ReplayError(f"unsafe input/output overlap: {input_path} / {output}")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ReplayError("battle-effect phase output directory must be absent or empty")
    if not os.access(args.binary, os.X_OK):
        raise ReplayError(f"mGBA binary is not executable: {args.binary}")
    return args


def _environment(args: argparse.Namespace, run_id: str) -> dict[str, str]:
    capture = args.capture
    environment = os.environ.copy()
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "MGBA_EFFECT_PHASE_INPUT_STATE": str(capture["input_state"]),
            "MGBA_EFFECT_PHASE_INPUT_STATE_SHA256": capture["input_state_sha256"],
            "MGBA_EFFECT_PHASE_OUTPUT_DIR": str(args.output_dir),
            "MGBA_EFFECT_PHASE_DONE_MARKER": str(args.done_marker),
            "MGBA_EFFECT_PHASE_RUN_ID": run_id,
            "MGBA_EFFECT_PHASE_ROM_SHA256": args.expected_rom_sha256,
            "MGBA_EFFECT_PHASE_INPUT_SCHEDULE": capture["input_schedule"],
            "MGBA_EFFECT_PHASE_INPUT_MODE": capture["input_mode"],
            "MGBA_EFFECT_PHASE_GROUP_ID": str(capture["group_id"]),
            "MGBA_EFFECT_PHASE_DEFINITION_POINTER": f"0x{capture['definition_pointer']:08X}",
            "MGBA_EFFECT_PHASE_ANIMATION_POINTER": f"0x{capture['animation_pointer']:08X}",
            "MGBA_EFFECT_PHASE_CAPTURE_FRAMES": str(capture["capture_frames"]),
            "MGBA_EFFECT_PHASE_TIMEOUT_FRAMES": str(capture["timeout_frames"]),
        }
    )
    return environment


def _phase_bundle(output_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
    audit_path = output_dir / "audit.json"
    _require_fresh_regular(audit_path, "battle-effect phase audit")
    audit = _load_json(audit_path, "battle-effect phase audit")
    hashes: dict[str, str] = {}
    for phase_name, _ in PHASES:
        prefix = output_dir / phase_name / "capture"
        for suffix, size in CAPTURE_FILE_SIZES.items():
            path = Path(f"{prefix}-{suffix}")
            _require_fresh_regular(path, f"{phase_name} {suffix}")
            if path.stat().st_size != size:
                raise ReplayError(f"{phase_name} {suffix} size mismatch")
            hashes[str(path.relative_to(output_dir))] = sha256_file(path)
        for suffix in (".ss9", ".png"):
            path = Path(f"{prefix}{suffix}")
            _require_fresh_regular(path, f"{phase_name} {suffix}")
            with path.open("rb") as stream:
                if stream.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                    raise ReplayError(f"{phase_name} {suffix} is not an mGBA PNG container")
            hashes[str(path.relative_to(output_dir))] = sha256_file(path)
        phase_json = Path(f"{prefix}-phase.json")
        _require_fresh_regular(phase_json, f"{phase_name} phase metadata")
        hashes[str(phase_json.relative_to(output_dir))] = sha256_file(phase_json)
    return audit, hashes


def main(argv: Sequence[str] | None = None) -> int:
    args = validate_args(build_parser().parse_args(argv))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for phase_name, _ in PHASES:
        (args.output_dir / phase_name).mkdir()
    for path in (args.staged_rom, args.staged_save, args.guard_summary, args.done_marker):
        path.parent.mkdir(parents=True, exist_ok=True)
        prepare_fresh_output(path, path.name)
    shutil.copy2(args.rom, args.staged_rom)
    validate_expected_hash(args.staged_rom, args.expected_rom_sha256, "staged ROM")
    run_id = secrets.token_hex(16)
    child = emulator_command(args.binary, [], args.phase_script, args.staged_rom)
    wrapped = guarded_command(
        args.guard_summary,
        args.done_marker,
        child,
        args.wall_timeout_s,
        args.idle_timeout_s,
    )
    completed = subprocess.run(wrapped, cwd=ROOT, env=_environment(args, run_id), check=False)
    summary = _load_json(args.guard_summary, "guard summary")
    validate_guard_summary(summary, child, completed.returncode)
    validate_completion_marker(
        args.done_marker,
        {"run_id": run_id, "status": "three-phase-captured", "phase_count": 3},
    )
    validate_owned_pgid_clean(summary["child_pid"], read_ps_snapshot())
    residue = probe_runtime_residue(summary["child_pid"])
    audit, files = _phase_bundle(args.output_dir)
    validate_phase_payload(audit, args.capture)
    for path, expected, label in (
        (args.binary, args.expected_binary_sha256, "mGBA binary"),
        (args.toolchain_artifact, args.toolchain_artifact_sha256, "mGBA provenance"),
        (args.rom, args.expected_rom_sha256, "ROM"),
        (args.staged_rom, args.expected_rom_sha256, "staged ROM"),
        (args.profile, args.expected_profile_sha256, "battle-effect profile"),
        (args.phase_script, PHASE_SCRIPT_SHA256, "battle-effect phase script"),
        (args.animations, ANIMATIONS_SHA256, "battle-effect animation catalog"),
        (args.capture["input_state"], args.capture["input_state_sha256"], "input state"),
    ):
        validate_expected_hash(path, expected, label)
    finalized = dict(audit)
    finalized.update(
        {
            "profile": str(args.profile),
            "profile_sha256": args.expected_profile_sha256,
            "animations": str(args.animations),
            "animations_sha256": ANIMATIONS_SHA256,
            "binary_sha256": args.expected_binary_sha256,
            "toolchain": {
                "kind": args.toolchain_kind,
                "path": str(args.toolchain_artifact),
                "sha256": args.toolchain_artifact_sha256,
                "source_commit": args.toolchain_source_commit,
                "patch_sha256": args.toolchain_patch_sha256,
            },
            "phase_script": str(args.phase_script),
            "phase_script_sha256": PHASE_SCRIPT_SHA256,
            "guard_summary_sha256": sha256_file(args.guard_summary),
            "peak_tree_rss_mib": summary["peak_tree_rss_mib"],
            "child_pgid": summary["child_pid"],
            "pgid_clean": True,
            "runtime_residue": residue,
            "staged_rom": str(args.staged_rom),
            "staged_rom_sha256": sha256_file(args.staged_rom),
            "files": files,
        }
    )
    (args.output_dir / "audit.json").write_text(
        json.dumps(finalized, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(finalized, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, RuntimeResidueError) as error:
        print(f"run_macos_mgba_battle_effect_phase_capture: {error}", file=sys.stderr)
        raise SystemExit(2)
