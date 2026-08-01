#!/usr/bin/env python3
"""Run the fixed battle-8 action-64 natural branch trace under the heavy guard."""

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


ROOT = Path(__file__).resolve().parents[1]
TRACE_SCRIPT = ROOT / "tools/mgba_group15_natural_branch_trace.lua"
# Updated only when the fixed repository observer changes intentionally.
TRACE_SCRIPT_SHA256 = "782cfd0c2125ef4753b2504271ed67c9438fe119d7a384dd961d07d7ccbb4f83"
ROUTE_ROM_SHA256 = "6325192e28774efdb30014b87fe7a3e17f2c1bd1f7c34b2484815c156c081b4e"
INPUT_STATE_SHA256 = "c775d4b5ea952f95bdac11993979ad62e11a9418456afc99a54d484b202ce1e1"
CAPTURE_FRAME = 1800
EXPECTED_INPUTS = [
    {"key": "A", "down_frame": 60, "up_frame": 68, "hold_frames": 8}
]
CHAIN = (
    ("runtime-copy-b", "0x0807A222"),
    ("presentation-entry", "0x0807F064"),
    ("classification-cmp", "0x0807F09E"),
    ("dynamic-selector", "0x0807F0FC"),
    ("dynamic-binder-call", "0x0807F10C"),
    ("binder-entry", "0x0807C5E8"),
)


def _hex(row: Mapping[str, object], field: str) -> int:
    try:
        value = row[field]
        if not isinstance(value, str):
            raise TypeError
        return int(value, 16)
    except (KeyError, TypeError, ValueError) as error:
        raise ReplayError(f"branch {field} is invalid") from error


def validate_branch_chain(events: object) -> list[dict[str, Any]]:
    if not isinstance(events, list) or any(not isinstance(row, dict) for row in events):
        raise ReplayError("branch events are invalid")
    if any(row.get("name") == "special-sequence-6" for row in events):
        raise ReplayError("branch entered fixed special sequence 6")
    selected: list[dict[str, Any]] = []
    for name, address in CHAIN:
        rows = [row for row in events if row.get("name") == name]
        if len(rows) != 1 or rows[0].get("address") != address:
            raise ReplayError(f"branch chain mismatch: {name}")
        selected.append(dict(rows[0]))
    try:
        cycles = [int(row["cycle"]) for row in selected]
        frames = [int(row["frame"]) for row in selected]
    except (KeyError, TypeError, ValueError) as error:
        raise ReplayError("branch frame/cycle is invalid") from error
    if cycles != sorted(cycles) or len(cycles) != len(set(cycles)):
        raise ReplayError("branch cycles are not strictly increasing")
    if frames[0] >= frames[1] or len(set(frames[1:])) != 1:
        raise ReplayError("branch frame sequence mismatch")
    runtime = 0x02026CB8
    if (
        _hex(selected[0], "r4") != runtime
        or _hex(selected[1], "r0") != runtime
        or _hex(selected[2], "r0") != 0
        or _hex(selected[3], "r4") != runtime
    ):
        raise ReplayError("branch runtime/classification context mismatch")
    for row in selected[4:]:
        if _hex(row, "r0") != 1 or _hex(row, "r1") != 17 or _hex(row, "r2") != 0x770:
            raise ReplayError("branch binder is not side 1 sequence 17")
    return selected


def validate_trace_payload(
    payload: Mapping[str, object],
    *,
    run_id: str,
    rom_sha256: str,
    input_state_sha256: str,
    script_sha256: str,
) -> list[dict[str, Any]]:
    expected = {
        "schema": "natural-battle-effect-branch-trace-experiment-v1",
        "run_id": run_id,
        "frame": CAPTURE_FRAME,
        "capture_frame": CAPTURE_FRAME,
        "inputs": EXPECTED_INPUTS,
        "automatic_inputs": [],
        "recovery_inputs": [],
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            if field in {"automatic_inputs", "recovery_inputs"}:
                raise ReplayError("branch trace contains implicit inputs")
            raise ReplayError(f"branch trace {field} mismatch")
    identities = {
        "rom_sha256": (rom_sha256, "ROM identity"),
        "input_state_sha256": (input_state_sha256, "input-state identity"),
        "script_sha256": (script_sha256, "script identity"),
    }
    for field, (value, label) in identities.items():
        if payload.get(field) != value:
            raise ReplayError(f"branch trace {label} mismatch")
    return validate_branch_chain(payload.get("events"))


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
    parser.add_argument("--wall-timeout-s", type=float, default=180)
    parser.add_argument("--idle-timeout-s", type=float, default=45)
    return parser


def _output(path: Path) -> Path:
    return _absolute(path).resolve(strict=False)


def validate_args(args: argparse.Namespace) -> argparse.Namespace:
    if args.wall_timeout_s <= 0 or args.idle_timeout_s <= 0:
        raise ReplayError("wall and idle timeouts must be positive")
    args.binary = canonical_input(args.binary, "mGBA binary")
    args.toolchain_profile = canonical_input(args.toolchain_profile, "mGBA runtime profile")
    args.rom = canonical_input(args.rom, "route ROM")
    args.state = canonical_input(args.state, "input state")
    args.trace_script = canonical_input(TRACE_SCRIPT, "group-15 branch trace script")
    if args.expected_rom_sha256 != ROUTE_ROM_SHA256:
        raise ReplayError("group-15 runner requires the fixed battle-8 route ROM")
    if args.expected_state_sha256 != INPUT_STATE_SHA256:
        raise ReplayError("group-15 runner requires the fixed pre-confirm state")
    validate_expected_hash(args.binary, args.expected_binary_sha256, "mGBA binary")
    validate_expected_hash(
        args.toolchain_profile,
        CURRENT_TOOLCHAIN_PROFILE_SHA256,
        "mGBA runtime profile",
    )
    validate_current_toolchain_profile(
        args.toolchain_profile, args.binary, args.expected_binary_sha256
    )
    validate_expected_hash(args.rom, ROUTE_ROM_SHA256, "route ROM")
    validate_expected_hash(args.state, INPUT_STATE_SHA256, "input state")
    validate_expected_hash(args.trace_script, TRACE_SCRIPT_SHA256, "branch trace script")
    args.staged_rom = _output(args.staged_rom)
    args.output_dir = _output(args.output_dir)
    args.guard_summary = _output(args.guard_summary)
    args.done_marker = _output(Path(f"{args.guard_summary}.done.json"))
    args.staged_save = args.staged_rom.with_suffix(".sav")
    args.output_state = args.output_dir / "final.ss9"
    args.output_png = args.output_dir / "final.png"
    args.audit = args.output_dir / "audit.json"
    inputs = {args.binary, args.toolchain_profile, args.rom, args.state, args.trace_script}
    outputs = {
        args.staged_rom,
        args.staged_save,
        args.output_dir,
        args.guard_summary,
        args.done_marker,
    }
    for output in outputs:
        for input_path in inputs:
            if output == input_path or output in input_path.parents or input_path in output.parents:
                raise ReplayError(f"unsafe input/output overlap: {input_path} / {output}")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ReplayError("branch trace output directory must be absent or empty")
    if args.rom.with_suffix(".sav").exists():
        raise ReplayError("source route ROM save sidecar must be absent")
    if not os.access(args.binary, os.X_OK):
        raise ReplayError(f"mGBA binary is not executable: {args.binary}")
    return args


def _environment(args: argparse.Namespace, run_id: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "NATURAL_TRACE_INPUT_STATE": str(args.state),
            "NATURAL_TRACE_OUTPUT_STATE": str(args.output_state),
            "NATURAL_TRACE_OUTPUT_PNG": str(args.output_png),
            "NATURAL_TRACE_AUDIT": str(args.audit),
            "NATURAL_TRACE_DONE": str(args.done_marker),
            "NATURAL_TRACE_RUN_ID": run_id,
            "NATURAL_TRACE_ROM_SHA256": ROUTE_ROM_SHA256,
            "NATURAL_TRACE_INPUT_STATE_SHA256": INPUT_STATE_SHA256,
            "NATURAL_TRACE_SCRIPT_SHA256": TRACE_SCRIPT_SHA256,
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
    validate_expected_hash(args.staged_rom, ROUTE_ROM_SHA256, "staged route ROM")
    run_id = secrets.token_hex(16)
    child = emulator_command(args.binary, [], args.trace_script, args.staged_rom)
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
        args.done_marker, {"run_id": run_id, "status": "trace-complete"}
    )
    validate_owned_pgid_clean(summary["child_pid"], read_ps_snapshot())
    residue = probe_runtime_residue(summary["child_pid"])
    for path, label in (
        (args.output_state, "branch final state"),
        (args.output_png, "branch final PNG"),
        (args.audit, "branch audit"),
    ):
        _require_fresh_regular(path, label)
    for path, label in ((args.output_state, "state"), (args.output_png, "PNG")):
        with path.open("rb") as stream:
            if stream.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                raise ReplayError(f"branch final {label} is not an mGBA PNG container")
    raw = _load_json(args.audit, "branch audit")
    chain = validate_trace_payload(
        raw,
        run_id=run_id,
        rom_sha256=ROUTE_ROM_SHA256,
        input_state_sha256=INPUT_STATE_SHA256,
        script_sha256=TRACE_SCRIPT_SHA256,
    )
    for path, expected, label in (
        (args.binary, args.expected_binary_sha256, "mGBA binary"),
        (args.toolchain_profile, CURRENT_TOOLCHAIN_PROFILE_SHA256, "mGBA runtime profile"),
        (args.rom, ROUTE_ROM_SHA256, "route ROM"),
        (args.staged_rom, ROUTE_ROM_SHA256, "staged route ROM"),
        (args.state, INPUT_STATE_SHA256, "input state"),
        (args.trace_script, TRACE_SCRIPT_SHA256, "branch trace script"),
    ):
        validate_expected_hash(path, expected, label)
    finalized = dict(raw)
    finalized.update(
        {
            "selected_chain": chain,
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
        print(f"run_macos_mgba_group15_natural_branch_trace: {error}", file=sys.stderr)
        raise SystemExit(2)
