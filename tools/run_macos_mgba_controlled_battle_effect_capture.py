#!/usr/bin/env python3
"""Capture controlled effect spawn plus the following OAM transaction."""

from __future__ import annotations

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
    from tools.run_macos_mgba_battle_effect_phase_capture import (
        ANIMATIONS_SHA256,
        CAPTURE_FILE_SIZES,
        ReplayError,
        _load_json,
        _require_fresh_regular,
        build_parser,
        canonical_input,
        emulator_command,
        guarded_command,
        prepare_fresh_output,
        read_ps_snapshot,
        sha256_file,
        validate_args,
        validate_completion_marker,
        validate_expected_hash,
        validate_guard_summary,
        validate_owned_pgid_clean,
        PNG_SIGNATURE,
        ROOT,
    )
except ModuleNotFoundError:
    from macos_mgba_runtime_residue import RuntimeResidueError, probe_runtime_residue
    from run_macos_mgba_battle_effect_phase_capture import (
        ANIMATIONS_SHA256,
        CAPTURE_FILE_SIZES,
        ReplayError,
        _load_json,
        _require_fresh_regular,
        build_parser,
        canonical_input,
        emulator_command,
        guarded_command,
        prepare_fresh_output,
        read_ps_snapshot,
        sha256_file,
        validate_args,
        validate_completion_marker,
        validate_expected_hash,
        validate_guard_summary,
        validate_owned_pgid_clean,
        PNG_SIGNATURE,
        ROOT,
    )


CONTROLLED_SCRIPT = ROOT / "tools/mgba_controlled_battle_effect_capture.lua"
CONTROLLED_SCRIPT_SHA256 = "81e9639dedfd3517fcc00032a222b87a870ec6db6396aef9bc41e246aab7ec41"
CONTROLLED_PHASES = (
    ("binder-return", "0x0809E85A"),
    ("renderer-post", "0x08063328"),
    ("submit-post", "0x08061126"),
    ("ack-post", "0x080612AA"),
)


def validate_controlled_payload(
    payload: Mapping[str, object], expected: Mapping[str, object]
) -> None:
    if payload.get("schema") != "mgba-controlled-battle-effect-capture-v1":
        raise ReplayError("controlled battle-effect payload schema mismatch")
    if payload.get("outcome") != "binder-plus-three-phase-captured":
        raise ReplayError("controlled battle-effect transaction is incomplete")
    for field in ("group_id", "sequence_id"):
        if payload.get(field) != expected[field]:
            raise ReplayError(f"controlled battle-effect {field} mismatch")
    for field in ("definition_pointer", "animation_pointer"):
        if payload.get(field) != f"0x{int(expected[field]):08X}":
            raise ReplayError(f"controlled battle-effect {field} mismatch")
    for field in ("inputs", "automatic_inputs", "recovery_inputs"):
        if payload.get(field) != []:
            raise ReplayError(f"controlled battle-effect {field} is not empty")
    if payload.get("scratch_before") != 0 or payload.get("scratch_after") != 1:
        raise ReplayError("controlled one-shot scratch transition mismatch")
    phases = payload.get("phases")
    if not isinstance(phases, list) or len(phases) != len(CONTROLLED_PHASES):
        raise ReplayError("controlled battle-effect phase count mismatch")
    cycles: list[int] = []
    for (name, address), phase in zip(CONTROLLED_PHASES, phases, strict=True):
        if (
            not isinstance(phase, dict)
            or phase.get("name") != name
            or phase.get("address") != address
        ):
            raise ReplayError("controlled battle-effect phase order mismatch")
        try:
            cycles.append(int(str(phase["cycle"]), 10))
        except (KeyError, TypeError, ValueError) as error:
            raise ReplayError("controlled battle-effect cycle is invalid") from error
    if cycles != sorted(cycles) or len(set(cycles)) != len(cycles):
        raise ReplayError("controlled battle-effect cycles are not strictly ordered")


def _environment(args, run_id: str) -> dict[str, str]:
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
            "MGBA_EFFECT_PHASE_GROUP_ID": str(capture["group_id"]),
            "MGBA_EFFECT_SEQUENCE_ID": str(capture["sequence_id"]),
            "MGBA_EFFECT_PHASE_DEFINITION_POINTER": f"0x{capture['definition_pointer']:08X}",
            "MGBA_EFFECT_PHASE_ANIMATION_POINTER": f"0x{capture['animation_pointer']:08X}",
            "MGBA_EFFECT_PHASE_TIMEOUT_FRAMES": str(capture["timeout_frames"]),
        }
    )
    return environment


def _bundle(output_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
    audit_path = output_dir / "audit.json"
    _require_fresh_regular(audit_path, "controlled battle-effect audit")
    audit = _load_json(audit_path, "controlled battle-effect audit")
    hashes: dict[str, str] = {}
    for phase_name, _ in CONTROLLED_PHASES:
        prefix = output_dir / phase_name / "capture"
        for suffix, size in CAPTURE_FILE_SIZES.items():
            path = Path(f"{prefix}-{suffix}")
            _require_fresh_regular(path, f"{phase_name} {suffix}")
            if path.stat().st_size != size:
                raise ReplayError(f"{phase_name} {suffix} size mismatch")
            hashes[path.relative_to(output_dir).as_posix()] = sha256_file(path)
        for suffix in (".ss9", ".png"):
            path = Path(f"{prefix}{suffix}")
            _require_fresh_regular(path, f"{phase_name} {suffix}")
            if not path.read_bytes().startswith(PNG_SIGNATURE):
                raise ReplayError(f"{phase_name} {suffix} is not an mGBA PNG container")
            hashes[path.relative_to(output_dir).as_posix()] = sha256_file(path)
        metadata = Path(f"{prefix}-phase.json")
        _require_fresh_regular(metadata, f"{phase_name} metadata")
        hashes[metadata.relative_to(output_dir).as_posix()] = sha256_file(metadata)
    return audit, dict(sorted(hashes.items()))


def main(argv: Sequence[str] | None = None) -> int:
    args = validate_args(build_parser().parse_args(argv))
    profile = _load_json(args.profile, "controlled battle-effect profile")
    if profile.get("execution_mode") != "controlled-sequence-injection":
        raise ReplayError("controlled execution mode mismatch")
    sequence_id = profile.get("sequence_id")
    if not isinstance(sequence_id, int) or isinstance(sequence_id, bool):
        raise ReplayError("controlled sequence ID is invalid")
    args.capture["sequence_id"] = sequence_id
    args.phase_script = canonical_input(CONTROLLED_SCRIPT, "controlled capture script")
    validate_expected_hash(
        args.phase_script, CONTROLLED_SCRIPT_SHA256, "controlled capture script"
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for phase_name, _ in CONTROLLED_PHASES:
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
    completed = subprocess.run(
        wrapped, cwd=ROOT, env=_environment(args, run_id), check=False
    )
    summary = _load_json(args.guard_summary, "guard summary")
    validate_guard_summary(summary, child, completed.returncode)
    validate_completion_marker(
        args.done_marker,
        {
            "run_id": run_id,
            "status": "binder-plus-three-phase-captured",
            "phase_count": 4,
        },
    )
    validate_owned_pgid_clean(summary["child_pid"], read_ps_snapshot())
    residue = probe_runtime_residue(summary["child_pid"])
    audit, files = _bundle(args.output_dir)
    validate_controlled_payload(audit, args.capture)
    for path, expected, label in (
        (args.binary, args.expected_binary_sha256, "mGBA binary"),
        (args.toolchain_artifact, args.toolchain_artifact_sha256, "mGBA provenance"),
        (args.rom, args.expected_rom_sha256, "ROM"),
        (args.staged_rom, args.expected_rom_sha256, "staged ROM"),
        (args.profile, args.expected_profile_sha256, "controlled profile"),
        (args.phase_script, CONTROLLED_SCRIPT_SHA256, "controlled capture script"),
        (args.animations, ANIMATIONS_SHA256, "animation catalog"),
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
            "phase_script_sha256": CONTROLLED_SCRIPT_SHA256,
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
        print(f"run_macos_mgba_controlled_battle_effect_capture: {error}", file=sys.stderr)
        raise SystemExit(2)
