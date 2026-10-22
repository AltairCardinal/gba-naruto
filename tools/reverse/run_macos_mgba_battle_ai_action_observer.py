#!/usr/bin/env python3
"""Observe natural enemy-AI selections until the first non-skipped action."""

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
    from tools.macos_mgba_toolchain_profile import (
        CURRENT_MGBA_SOURCE_COMMIT,
        CURRENT_TOOLCHAIN_PROFILE_SHA256,
        validate_current_toolchain_profile,
    )
    from tools.run_macos_mgba_replay import (
        ReplayError,
        canonical_input,
        emulator_command,
        guarded_command,
        prepare_fresh_output,
        read_ps_snapshot,
        sha256_file,
        validate_completion_marker,
        validate_expected_hash,
        validate_guard_summary,
        validate_owned_pgid_clean,
    )
    from tools.run_macos_mgba_single_input import (
        PNG_SIGNATURE,
        _absolute,
        _load_json,
        _require_fresh_regular,
    )
    from tools.run_macos_mgba_input_sequence import encode_schedule, parse_input_events
except ModuleNotFoundError:
    from macos_mgba_runtime_residue import RuntimeResidueError, probe_runtime_residue
    from macos_mgba_toolchain_profile import (
        CURRENT_MGBA_SOURCE_COMMIT,
        CURRENT_TOOLCHAIN_PROFILE_SHA256,
        validate_current_toolchain_profile,
    )
    from run_macos_mgba_replay import (
        ReplayError,
        canonical_input,
        emulator_command,
        guarded_command,
        prepare_fresh_output,
        read_ps_snapshot,
        sha256_file,
        validate_completion_marker,
        validate_expected_hash,
        validate_guard_summary,
        validate_owned_pgid_clean,
    )
    from run_macos_mgba_single_input import (
        PNG_SIGNATURE,
        _absolute,
        _load_json,
        _require_fresh_regular,
    )
    from run_macos_mgba_input_sequence import encode_schedule, parse_input_events


ROOT = Path(__file__).resolve().parents[1]
OBSERVER_SCRIPT = ROOT / "tools/mgba_battle_ai_action_observer.lua"
OBSERVER_SCRIPT_SHA256 = "79a6204f1d24bf62e7c8d801f1dfcfdd0f72fb9f6337f8accd201507bd9b3425"
CAPTURE_FRAME_LIMIT = 1800
DEFAULT_INPUT_EVENTS = ["A:60:68"]
RUNTIME_POINTER = 0x02026CB8
ACTION_ADDRESS = RUNTIME_POINTER + 0x770


def _hex(row: Mapping[str, object], field: str) -> int:
    value = row.get(field)
    if not isinstance(value, str):
        raise ReplayError(f"observer selection {field} is invalid")
    try:
        return int(value, 16)
    except ValueError as error:
        raise ReplayError(f"observer selection {field} is invalid") from error


def validate_observer_payload(
    payload: Mapping[str, object],
    *,
    run_id: str,
    rom_sha256: str,
    input_state_sha256: str,
    script_sha256: str,
    skipped_action_ids: Sequence[int],
    expected_inputs: Sequence[Mapping[str, object]],
) -> dict[str, Any]:
    expected = {
        "schema": "battle-ai-action-observer-v4",
        "run_id": run_id,
        "capture_frame_limit": CAPTURE_FRAME_LIMIT,
        "inputs": list(expected_inputs),
        "automatic_inputs": [],
        "recovery_inputs": [],
        "rom_sha256": rom_sha256,
        "input_state_sha256": input_state_sha256,
        "script_sha256": script_sha256,
        "skipped_action_ids": list(skipped_action_ids),
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            if field in {"automatic_inputs", "recovery_inputs"}:
                raise ReplayError("observer contains implicit inputs")
            raise ReplayError(f"observer {field} mismatch")
    frame = payload.get("frame")
    if not isinstance(frame, int) or isinstance(frame, bool) or not 1 <= frame <= CAPTURE_FRAME_LIMIT:
        raise ReplayError("observer frame is invalid")
    events = payload.get("events")
    if not isinstance(events, list):
        raise ReplayError("observer events are invalid")

    def validate_event(event: object) -> dict[str, Any]:
        if not isinstance(event, dict):
            raise ReplayError("observer event is invalid")
        selection = event
        if selection.get("address") != "0x0807A22C":
            raise ReplayError("observer runtime-copy address mismatch")
        if _hex(selection, "runtime_pointer") != RUNTIME_POINTER:
            raise ReplayError("observer runtime pointer mismatch")
        if _hex(selection, "action_address") != ACTION_ADDRESS:
            raise ReplayError("observer action address mismatch")
        if _hex(selection, "r5") != 0x0202680C:
            raise ReplayError("observer battle-control pointer mismatch")
        action_id = selection.get("action_id")
        if (
            not isinstance(action_id, int)
            or isinstance(action_id, bool)
            or not 0 <= action_id <= 255
        ):
            raise ReplayError("observer action ID is invalid")
        candidate_pointer = _hex(selection, "candidate_pointer")
        if _hex(selection, "source_action_address") != candidate_pointer + 0x0C:
            raise ReplayError("observer source action address mismatch")
        source_action_id = selection.get("source_action_id")
        if source_action_id != action_id:
            raise ReplayError("observer source action ID mismatch")
        try:
            cycle = int(selection["cycle"])
        except (KeyError, TypeError, ValueError) as error:
            raise ReplayError("observer cycle is invalid") from error
        if cycle <= 0:
            raise ReplayError("observer cycle is invalid")
        return dict(selection)

    validated_events = [validate_event(event) for event in events]
    selection = payload.get("selection")
    if not isinstance(selection, dict):
        raise ReplayError("no AI action selection before the frame limit")
    validated_selection = validate_event(selection)
    if not validated_events or validated_events[-1] != validated_selection:
        raise ReplayError("observer selection is not the final event")
    skipped = set(skipped_action_ids)
    if any(event["action_id"] not in skipped for event in validated_events[:-1]):
        raise ReplayError("observer contains an unskipped action before the selection")
    if validated_selection["action_id"] in skipped:
        raise ReplayError("observer selection action was configured to be skipped")
    return validated_selection


def parse_observer_input_events(
    raw_events: Sequence[str] | None,
) -> list[dict[str, object]]:
    return parse_input_events(raw_events or DEFAULT_INPUT_EVENTS, CAPTURE_FRAME_LIMIT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--toolchain-profile", type=Path, required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--expected-rom-sha256", required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--expected-state-sha256", required=True)
    parser.add_argument("--staged-rom", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--guard-summary", type=Path, required=True)
    parser.add_argument("--skip-action-id", action="append", type=int, default=[])
    parser.add_argument("--input-event", action="append")
    parser.add_argument("--wall-timeout-s", type=float, default=180)
    parser.add_argument("--idle-timeout-s", type=float, default=45)
    return parser


def _output(path: Path) -> Path:
    return _absolute(path).resolve(strict=False)


def validate_args(args: argparse.Namespace) -> argparse.Namespace:
    if args.wall_timeout_s <= 0 or args.idle_timeout_s <= 0:
        raise ReplayError("wall and idle timeouts must be positive")
    if any(action_id < 0 or action_id > 255 for action_id in args.skip_action_id):
        raise ReplayError("skip action IDs must be in 0..255")
    if len(set(args.skip_action_id)) != len(args.skip_action_id):
        raise ReplayError("skip action IDs must be unique")
    args.skip_action_id = sorted(args.skip_action_id)
    args.events = parse_observer_input_events(args.input_event)
    args.binary = canonical_input(args.binary, "mGBA binary")
    args.toolchain_profile = canonical_input(args.toolchain_profile, "mGBA runtime profile")
    args.rom = canonical_input(args.rom, "route ROM")
    args.state = canonical_input(args.state, "input state")
    args.observer_script = canonical_input(OBSERVER_SCRIPT, "AI action observer script")
    for path, expected, label in (
        (args.binary, args.expected_binary_sha256, "mGBA binary"),
        (args.toolchain_profile, CURRENT_TOOLCHAIN_PROFILE_SHA256, "mGBA runtime profile"),
        (args.rom, args.expected_rom_sha256, "route ROM"),
        (args.state, args.expected_state_sha256, "input state"),
        (args.observer_script, OBSERVER_SCRIPT_SHA256, "AI action observer script"),
    ):
        validate_expected_hash(path, expected, label)
    validate_current_toolchain_profile(
        args.toolchain_profile, args.binary, args.expected_binary_sha256
    )
    if not os.access(args.binary, os.X_OK):
        raise ReplayError(f"mGBA binary is not executable: {args.binary}")
    if args.rom.with_suffix(".sav").exists():
        raise ReplayError("source route ROM save sidecar must be absent")
    args.staged_rom = _output(args.staged_rom)
    args.output_dir = _output(args.output_dir)
    args.guard_summary = _output(args.guard_summary)
    args.done_marker = _output(Path(f"{args.guard_summary}.done.json"))
    args.staged_save = args.staged_rom.with_suffix(".sav")
    args.output_state = args.output_dir / "selection.ss9"
    args.output_png = args.output_dir / "selection.png"
    args.audit = args.output_dir / "audit.json"
    inputs = {args.binary, args.toolchain_profile, args.rom, args.state, args.observer_script}
    outputs = {args.staged_rom, args.staged_save, args.output_dir, args.guard_summary, args.done_marker}
    for output in outputs:
        for input_path in inputs:
            if output == input_path or output in input_path.parents or input_path in output.parents:
                raise ReplayError(f"unsafe input/output overlap: {input_path} / {output}")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ReplayError("observer output directory must be absent or empty")
    return args


def _environment(args: argparse.Namespace, run_id: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "AI_OBSERVER_INPUT_STATE": str(args.state),
            "AI_OBSERVER_OUTPUT_STATE": str(args.output_state),
            "AI_OBSERVER_OUTPUT_PNG": str(args.output_png),
            "AI_OBSERVER_AUDIT": str(args.audit),
            "AI_OBSERVER_DONE": str(args.done_marker),
            "AI_OBSERVER_RUN_ID": run_id,
            "AI_OBSERVER_ROM_SHA256": args.expected_rom_sha256,
            "AI_OBSERVER_INPUT_STATE_SHA256": args.expected_state_sha256,
            "AI_OBSERVER_SCRIPT_SHA256": OBSERVER_SCRIPT_SHA256,
            "AI_OBSERVER_SKIP_ACTION_IDS": ",".join(
                str(action_id) for action_id in args.skip_action_id
            ),
            "AI_OBSERVER_INPUT_SCHEDULE": encode_schedule(args.events),
        }
    )
    return environment


def main(argv: Sequence[str] | None = None) -> int:
    args = validate_args(build_parser().parse_args(argv))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path in (args.staged_rom, args.staged_save, args.guard_summary, args.done_marker):
        path.parent.mkdir(parents=True, exist_ok=True)
        prepare_fresh_output(path, path.name)
    shutil.copy2(args.rom, args.staged_rom)
    validate_expected_hash(args.staged_rom, args.expected_rom_sha256, "staged route ROM")
    run_id = secrets.token_hex(16)
    child = emulator_command(args.binary, [], args.observer_script, args.staged_rom)
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
        args.done_marker, {"run_id": run_id, "status": "observer-complete"}
    )
    validate_owned_pgid_clean(summary["child_pid"], read_ps_snapshot())
    residue = probe_runtime_residue(summary["child_pid"])
    for path, label in (
        (args.output_state, "observer state"),
        (args.output_png, "observer PNG"),
        (args.audit, "observer audit"),
    ):
        _require_fresh_regular(path, label)
    for path in (args.output_state, args.output_png):
        with path.open("rb") as stream:
            if stream.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                raise ReplayError(f"observer output is not an mGBA PNG container: {path}")
    raw = _load_json(args.audit, "observer audit")
    selection = validate_observer_payload(
        raw,
        run_id=run_id,
        rom_sha256=args.expected_rom_sha256,
        input_state_sha256=args.expected_state_sha256,
        script_sha256=OBSERVER_SCRIPT_SHA256,
        skipped_action_ids=args.skip_action_id,
        expected_inputs=args.events,
    )
    finalized = dict(raw)
    finalized.update(
        {
            "selection": selection,
            "binary_sha256": args.expected_binary_sha256,
            "toolchain": {
                "kind": "current-desktop-runtime-profile",
                "path": str(args.toolchain_profile),
                "sha256": CURRENT_TOOLCHAIN_PROFILE_SHA256,
                "source_commit": CURRENT_MGBA_SOURCE_COMMIT,
                "patch_sha256": None,
            },
            "staged_rom": str(args.staged_rom),
            "staged_rom_sha256": sha256_file(args.staged_rom),
            "guard_summary_sha256": sha256_file(args.guard_summary),
            "guard_command": child,
            "peak_tree_rss_mib": summary["peak_tree_rss_mib"],
            "child_pgid": summary["child_pid"],
            "pgid_clean": True,
            "runtime_residue": residue,
            "output_state_sha256": sha256_file(args.output_state),
            "output_png_sha256": sha256_file(args.output_png),
            "completion_marker_sha256": sha256_file(args.done_marker),
        }
    )
    args.audit.write_text(
        json.dumps(finalized, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(finalized, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, RuntimeResidueError) as error:
        print(f"run_macos_mgba_battle_ai_action_observer: {error}", file=sys.stderr)
        raise SystemExit(2)
