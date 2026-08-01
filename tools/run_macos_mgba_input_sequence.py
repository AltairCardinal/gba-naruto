#!/usr/bin/env python3
"""Replay an explicit ordered input sequence through the guarded mGBA build."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

try:
    from tools.macos_mgba_runtime_residue import (
        RuntimeResidueError,
        probe_runtime_residue,
    )
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
        validate_output_paths,
        validate_owned_pgid_clean,
    )
    from tools.run_macos_mgba_single_input import (
        PNG_SIGNATURE,
        _absolute,
        _load_json,
        _require_absent,
        _require_fresh_regular,
        _validate_payload_fields,
    )
    from tools.macos_mgba_toolchain_profile import (
        CURRENT_MGBA_SOURCE_COMMIT,
        CURRENT_TOOLCHAIN_PROFILE_SHA256,
        validate_current_toolchain_profile,
    )
except ModuleNotFoundError:
    from macos_mgba_runtime_residue import RuntimeResidueError, probe_runtime_residue
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
        validate_output_paths,
        validate_owned_pgid_clean,
    )
    from run_macos_mgba_single_input import (
        PNG_SIGNATURE,
        _absolute,
        _load_json,
        _require_absent,
        _require_fresh_regular,
        _validate_payload_fields,
    )
    from macos_mgba_toolchain_profile import (
        CURRENT_MGBA_SOURCE_COMMIT,
        CURRENT_TOOLCHAIN_PROFILE_SHA256,
        validate_current_toolchain_profile,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_SEQUENCE_SCRIPT = ROOT / "tools/mgba_input_sequence_replay.lua"
EXPECTED_INPUT_SEQUENCE_SCRIPT_SHA256 = (
    "28b7e0662d0377d75e063d05a1544846c257046947ef30e47560c1bcd9ffb196"
)
VALID_KEYS = ("Down", "A", "B", "L", "R", "Up", "Right", "Left", "Start")


def parse_input_events(
    raw_events: Sequence[str], capture_frame: int
) -> list[dict[str, object]]:
    if not isinstance(capture_frame, int) or isinstance(capture_frame, bool):
        raise ReplayError("input sequence capture frame must be an integer")
    if not raw_events:
        raise ReplayError("input sequence must contain at least one event")
    events: list[dict[str, object]] = []
    previous_up = 0
    for raw in raw_events:
        if not isinstance(raw, str):
            raise ReplayError("input event must be KEY:DOWN:UP text")
        fields = raw.split(":")
        if len(fields) != 3 or fields[0] not in VALID_KEYS:
            raise ReplayError("input event must be KEY:DOWN:UP with a supported key")
        try:
            down_frame, up_frame = (int(value, 10) for value in fields[1:])
        except ValueError as error:
            raise ReplayError("input event frames must be decimal integers") from error
        if str(down_frame) != fields[1] or str(up_frame) != fields[2]:
            raise ReplayError("input event frames must use canonical decimal integers")
        if not 0 < down_frame < up_frame < capture_frame:
            raise ReplayError("input event must satisfy 0 < down < up < capture")
        if down_frame < previous_up:
            raise ReplayError("input event intervals must not overlap")
        events.append(
            {
                "key": fields[0],
                "down_frame": down_frame,
                "up_frame": up_frame,
                "hold_frames": up_frame - down_frame,
            }
        )
        previous_up = up_frame
    return events


def encode_schedule(events: Sequence[Mapping[str, object]]) -> str:
    return ",".join(
        f"{event['key']}:{event['down_frame']}:{event['up_frame']}"
        for event in events
    )


def validate_input_sequence_payload(
    payload: Mapping[str, object], *, events: list[dict[str, object]], capture_frame: int
) -> None:
    expected = {
        "evidence_mode": "input-sequence",
        "zero_input_verified": False,
        "inputs": events,
        "automatic_inputs": [],
        "recovery_inputs": [],
        "frame": capture_frame,
        "capture_frame": capture_frame,
    }
    _validate_payload_fields(payload, expected)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    toolchain = parser.add_mutually_exclusive_group(required=True)
    toolchain.add_argument("--toolchain-profile", type=Path)
    toolchain.add_argument("--build-manifest", type=Path)
    parser.add_argument("--expected-build-manifest-sha256")
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--expected-rom-sha256", required=True)
    parser.add_argument("--expected-state-sha256", required=True)
    parser.add_argument("--input-event", action="append", required=True)
    parser.add_argument("--capture-frame", type=int, required=True)
    parser.add_argument("--staged-rom", type=Path, required=True)
    parser.add_argument("--output-state", type=Path, required=True)
    parser.add_argument("--output-png", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--sentinel", type=Path, required=True)
    parser.add_argument("--guard-summary", type=Path, required=True)
    parser.add_argument("--wall-timeout-s", type=float, default=180)
    parser.add_argument("--idle-timeout-s", type=float, default=45)
    return parser


def validate_args(args: argparse.Namespace) -> argparse.Namespace:
    args.events = parse_input_events(args.input_event, args.capture_frame)
    if args.wall_timeout_s <= 0 or args.idle_timeout_s <= 0:
        raise ReplayError("wall and idle timeouts must be positive")
    args.binary = canonical_input(args.binary, "mGBA binary")
    if args.toolchain_profile is not None:
        args.toolchain_profile = canonical_input(
            args.toolchain_profile, "mGBA runtime profile"
        )
        toolchain_artifact = args.toolchain_profile
    else:
        args.build_manifest = canonical_input(
            args.build_manifest, "legacy build manifest"
        )
        toolchain_artifact = args.build_manifest
    inputs = {
        "binary": args.binary,
        "toolchain_artifact": toolchain_artifact,
        "rom": canonical_input(args.rom, "ROM"),
        "state": canonical_input(args.state, "input state"),
        "input_sequence_script": canonical_input(
            DEFAULT_INPUT_SEQUENCE_SCRIPT, "input-sequence replay script"
        ),
    }
    source_save = inputs["rom"].with_suffix(".sav")
    _require_absent(source_save, "source ROM save sidecar")
    if inputs["input_sequence_script"] != DEFAULT_INPUT_SEQUENCE_SCRIPT.resolve(
        strict=True
    ):
        raise ReplayError("input-sequence runner requires the repository fixed Lua script")
    validate_expected_hash(
        inputs["input_sequence_script"],
        EXPECTED_INPUT_SEQUENCE_SCRIPT_SHA256,
        "input-sequence replay script",
    )
    staged_save = args.staged_rom.with_suffix(".sav")
    outputs = validate_output_paths(
        [
            args.staged_rom,
            args.output_state,
            args.output_png,
            args.audit,
            args.sentinel,
            args.guard_summary,
            Path(f"{args.guard_summary}.done.json"),
        ],
        derived=[staged_save],
    )
    canonical_staged_save = _absolute(staged_save).resolve(strict=False)
    for output in [*outputs, canonical_staged_save]:
        if output == source_save:
            raise ReplayError(f"output overlaps reserved source ROM save: {output}")
        for label, input_path in inputs.items():
            if (
                output == input_path
                or output in input_path.parents
                or input_path in output.parents
            ):
                raise ReplayError(
                    f"unsafe input/output overlap: {label}={input_path}, output={output}"
                )
    if outputs[0].parent == inputs["rom"].parent:
        raise ReplayError("staged ROM must not share the source ROM directory")
    for name, value in inputs.items():
        setattr(args, name, value)
    (
        args.staged_rom,
        args.output_state,
        args.output_png,
        args.audit,
        args.sentinel,
        args.guard_summary,
        args.done_marker,
    ) = outputs
    args.staged_save = canonical_staged_save
    args.source_save = source_save
    if not os.access(args.binary, os.X_OK):
        raise ReplayError(f"mGBA binary is not executable: {args.binary}")
    validate_expected_hash(args.binary, args.expected_binary_sha256, "mGBA binary")
    if args.toolchain_profile is not None:
        if args.expected_build_manifest_sha256 is not None:
            raise ReplayError("current mGBA mode must not supply a legacy manifest hash")
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
    validate_expected_hash(args.state, args.expected_state_sha256, "state")
    return args


def _expected_payload(args: argparse.Namespace, run_id: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "frame": args.capture_frame,
        "capture_frame": args.capture_frame,
        "inputs": args.events,
        "automatic_inputs": [],
        "recovery_inputs": [],
        "evidence_mode": "input-sequence",
        "zero_input_verified": False,
        "success": True,
        "status": "capture-complete",
        "input_state": str(args.state),
        "output_state": str(args.output_state),
        "output_png": str(args.output_png),
        "audit": str(args.audit),
        "sentinel": str(args.sentinel),
        "rom_sha256": args.expected_rom_sha256,
        "input_state_sha256": args.expected_state_sha256,
    }


def _environment(args: argparse.Namespace, run_id: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "MGBA_REPLAY_INPUT_STATE": str(args.state),
            "MGBA_REPLAY_OUTPUT_STATE": str(args.output_state),
            "MGBA_REPLAY_OUTPUT_PNG": str(args.output_png),
            "MGBA_REPLAY_AUDIT": str(args.audit),
            "MGBA_REPLAY_SENTINEL": str(args.sentinel),
            "MGBA_REPLAY_DONE_MARKER": str(args.done_marker),
            "MGBA_REPLAY_CAPTURE_FRAME": str(args.capture_frame),
            "MGBA_REPLAY_RUN_ID": run_id,
            "MGBA_REPLAY_ROM_SHA256": args.expected_rom_sha256,
            "MGBA_REPLAY_INPUT_STATE_SHA256": args.expected_state_sha256,
            "MGBA_INPUT_SEQUENCE_SCHEDULE": encode_schedule(args.events),
        }
    )
    return environment


def _validate_output_bundle(
    args: argparse.Namespace, expected: Mapping[str, object]
) -> dict[str, object]:
    for path, label in (
        (args.output_state, "state"),
        (args.output_png, "PNG"),
        (args.audit, "audit"),
        (args.sentinel, "sentinel"),
    ):
        _require_fresh_regular(path, label)
    for path, label in ((args.output_state, "state"), (args.output_png, "PNG")):
        with path.open("rb") as stream:
            if stream.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                raise ReplayError(f"fresh {label} does not have an mGBA PNG signature")
    audit = _load_json(args.audit, "audit")
    sentinel = _load_json(args.sentinel, "sentinel")
    _validate_payload_fields(audit, expected)
    _validate_payload_fields(sentinel, expected)
    validate_input_sequence_payload(
        audit, events=args.events, capture_frame=args.capture_frame
    )
    validate_input_sequence_payload(
        sentinel, events=args.events, capture_frame=args.capture_frame
    )
    if audit != sentinel:
        raise ReplayError("audit and sentinel payloads differ")
    return {
        "audit": audit,
        "state_sha256": sha256_file(args.output_state),
        "png_sha256": sha256_file(args.output_png),
    }


def _revalidate_critical_inputs(args: argparse.Namespace) -> None:
    _require_absent(args.source_save, "source ROM save sidecar")
    for path, expected, label in (
        (
            args.toolchain_artifact,
            args.toolchain_artifact_sha256,
            "mGBA toolchain provenance",
        ),
        (args.binary, args.expected_binary_sha256, "mGBA binary"),
        (args.rom, args.expected_rom_sha256, "ROM"),
        (args.state, args.expected_state_sha256, "state"),
        (args.staged_rom, args.expected_rom_sha256, "staged ROM"),
        (
            args.input_sequence_script,
            EXPECTED_INPUT_SEQUENCE_SCRIPT_SHA256,
            "input-sequence replay script",
        ),
    ):
        validate_expected_hash(path, expected, label)


def _finalize(
    args: argparse.Namespace,
    bundle: Mapping[str, object],
    summary: Mapping[str, object],
    residue: Mapping[str, object],
) -> dict[str, object]:
    finalized = dict(bundle["audit"])
    finalized.update(
        {
            "binary_sha256": args.expected_binary_sha256,
            "toolchain": {
                "kind": args.toolchain_kind,
                "path": str(args.toolchain_artifact),
                "sha256": args.toolchain_artifact_sha256,
                "source_commit": args.toolchain_source_commit,
                "patch_sha256": args.toolchain_patch_sha256,
            },
            "replay_script": str(args.input_sequence_script),
            "replay_script_sha256": EXPECTED_INPUT_SEQUENCE_SCRIPT_SHA256,
            "output_state_sha256": bundle["state_sha256"],
            "output_png_sha256": bundle["png_sha256"],
            "guard_summary_sha256": sha256_file(args.guard_summary),
            "peak_tree_rss_mib": summary["peak_tree_rss_mib"],
            "child_pgid": summary["child_pid"],
            "pgid_clean": True,
            "runtime_residue": dict(residue),
            "staged_rom": str(args.staged_rom),
            "staged_rom_sha256": sha256_file(args.staged_rom),
        }
    )
    if args.build_manifest is not None:
        finalized.update(
            {
                "patch_sha256": EXPECTED_PATCH_SHA256,
                "build_manifest": str(args.build_manifest),
                "build_manifest_sha256": args.expected_build_manifest_sha256,
            }
        )
    encoded = json.dumps(finalized, indent=2, sort_keys=True) + "\n"
    args.audit.write_text(encoded, encoding="utf-8")
    args.sentinel.write_text(encoded, encoding="utf-8")
    return finalized


def main(argv: Sequence[str] | None = None) -> int:
    args = validate_args(build_parser().parse_args(argv))
    for path in (
        args.staged_rom,
        args.output_state,
        args.output_png,
        args.audit,
        args.sentinel,
        args.guard_summary,
        args.done_marker,
        args.staged_save,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        prepare_fresh_output(path, path.name)
    shutil.copy2(args.rom, args.staged_rom)
    validate_expected_hash(args.staged_rom, args.expected_rom_sha256, "staged ROM")
    run_id = secrets.token_hex(16)
    child = emulator_command(args.binary, [], args.input_sequence_script, args.staged_rom)
    wrapped = guarded_command(
        args.guard_summary,
        args.done_marker,
        child,
        args.wall_timeout_s,
        args.idle_timeout_s,
    )
    completed = subprocess.run(
        wrapped,
        cwd=ROOT,
        env=_environment(args, run_id),
        check=False,
    )
    summary = _load_json(args.guard_summary, "guard summary")
    validate_guard_summary(summary, child, completed.returncode)
    validate_completion_marker(
        args.done_marker,
        {
            "run_id": run_id,
            "capture_frame": args.capture_frame,
            "status": "capture-complete",
        },
    )
    child_pgid = summary["child_pid"]
    validate_owned_pgid_clean(child_pgid, read_ps_snapshot())
    residue = probe_runtime_residue(child_pgid)
    bundle = _validate_output_bundle(args, _expected_payload(args, run_id))
    _revalidate_critical_inputs(args)
    finalized = _finalize(args, bundle, summary, residue)
    print(json.dumps(finalized, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, RuntimeResidueError) as error:
        print(f"run_macos_mgba_input_sequence: {error}", file=sys.stderr)
        raise SystemExit(2)
