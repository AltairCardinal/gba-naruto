#!/usr/bin/env python3
"""Run one fixed Down, A, or B mGBA input segment behind the resource guard."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import stat
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
        BACKPORT_COMMIT,
        EXPECTED_LABEL,
        EXPECTED_PATCH_SHA256,
        MAX_TREE_RSS_MIB,
        MIN_AVAILABLE_MIB,
        SOURCE_COMMIT,
        ReplayError,
        canonical_input,
        emulator_command,
        guarded_command,
        prepare_fresh_output,
        read_ps_snapshot,
        sha256_file,
        validate_build_manifest,
        validate_expected_hash,
        validate_guard_summary,
        validate_output_paths,
        validate_owned_pgid_clean,
    )
except ModuleNotFoundError:
    from macos_mgba_runtime_residue import RuntimeResidueError, probe_runtime_residue
    from run_macos_mgba_replay import (
        BACKPORT_COMMIT,
        EXPECTED_LABEL,
        EXPECTED_PATCH_SHA256,
        MAX_TREE_RSS_MIB,
        MIN_AVAILABLE_MIB,
        SOURCE_COMMIT,
        ReplayError,
        canonical_input,
        emulator_command,
        guarded_command,
        prepare_fresh_output,
        read_ps_snapshot,
        sha256_file,
        validate_build_manifest,
        validate_expected_hash,
        validate_guard_summary,
        validate_output_paths,
        validate_owned_pgid_clean,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SINGLE_INPUT_SCRIPT = ROOT / "tools" / "mgba_single_input_replay.lua"
EXPECTED_SINGLE_INPUT_SCRIPT_SHA256 = (
    "51b299c978698363c236376636ab7d9c78ffcbe57f2b94254a7b1d2249ea4487"
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class _SingleKeyAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest, None) is not None:
            parser.error("--key must be specified exactly once")
        setattr(namespace, self.dest, values)


def validate_single_input(
    key: str, down_frame: int, up_frame: int, capture_frame: int
) -> None:
    if key not in ("Down", "A", "B"):
        raise ReplayError("single input key must be exactly Down, A, or B")
    frames = (down_frame, up_frame, capture_frame)
    if any(not isinstance(frame, int) or isinstance(frame, bool) for frame in frames):
        raise ReplayError("single input frames must be integers")
    if not 0 < down_frame < up_frame < capture_frame:
        raise ReplayError("single input frames must satisfy 0 < down < up < capture")


def _event(key: str, down_frame: int, up_frame: int) -> dict[str, object]:
    return {
        "key": key,
        "down_frame": down_frame,
        "up_frame": up_frame,
        "hold_frames": up_frame - down_frame,
    }


def validate_single_input_payload(
    payload: Mapping[str, object],
    *,
    key: str,
    down_frame: int,
    up_frame: int,
    capture_frame: int,
) -> None:
    validate_single_input(key, down_frame, up_frame, capture_frame)
    expected = {
        "evidence_mode": "single-input",
        "zero_input_verified": False,
        "inputs": [_event(key, down_frame, up_frame)],
        "automatic_inputs": [],
        "recovery_inputs": [],
        "frame": capture_frame,
        "capture_frame": capture_frame,
    }
    for name, value in expected.items():
        if payload.get(name) != value:
            raise ReplayError(
                f"single-input payload {name} mismatch: expected {value}, got {payload.get(name)}"
            )


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _require_fresh_regular(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise ReplayError(f"fresh {label} is missing: {path}") from error
    if not stat.S_ISREG(mode):
        raise ReplayError(f"fresh {label} is not a regular file: {path}")
    if path.stat().st_size <= 0:
        raise ReplayError(f"fresh {label} is empty: {path}")


def _require_absent(path: Path, label: str) -> None:
    try:
        path.lstat()
    except FileNotFoundError:
        return
    raise ReplayError(f"{label} must be absent: {path}")


def _load_json(path: Path, label: str) -> dict[str, object]:
    _require_fresh_regular(path, label)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReplayError(f"fresh {label} is invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ReplayError(f"fresh {label} must be a JSON object")
    return payload


def _validate_payload_fields(
    payload: Mapping[str, object], expected: Mapping[str, object]
) -> None:
    for name, value in expected.items():
        if payload.get(name) != value:
            raise ReplayError(
                f"single-input payload {name} mismatch: expected {value}, got {payload.get(name)}"
            )


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
    validate_single_input_payload(
        audit,
        key=args.key,
        down_frame=args.down_frame,
        up_frame=args.up_frame,
        capture_frame=args.capture_frame,
    )
    validate_single_input_payload(
        sentinel,
        key=args.key,
        down_frame=args.down_frame,
        up_frame=args.up_frame,
        capture_frame=args.capture_frame,
    )
    if audit != sentinel:
        raise ReplayError("audit and sentinel payloads differ")
    return {
        "audit": audit,
        "state_sha256": sha256_file(args.output_state),
        "png_sha256": sha256_file(args.output_png),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--expected-build-manifest-sha256", required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--expected-rom-sha256", required=True)
    parser.add_argument("--expected-state-sha256", required=True)
    parser.add_argument("--key", action=_SingleKeyAction, required=True)
    parser.add_argument("--down-frame", type=int, required=True)
    parser.add_argument("--up-frame", type=int, required=True)
    parser.add_argument("--capture-frame", type=int, required=True)
    parser.add_argument("--staged-rom", type=Path, required=True)
    parser.add_argument("--output-state", type=Path, required=True)
    parser.add_argument("--output-png", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--sentinel", type=Path, required=True)
    parser.add_argument("--guard-summary", type=Path, required=True)
    parser.add_argument("--wall-timeout-s", type=float, default=120)
    parser.add_argument("--idle-timeout-s", type=float, default=30)
    return parser


def validate_args(args: argparse.Namespace) -> argparse.Namespace:
    validate_single_input(args.key, args.down_frame, args.up_frame, args.capture_frame)
    if args.wall_timeout_s <= 0 or args.idle_timeout_s <= 0:
        raise ReplayError("wall and idle timeouts must be positive")
    inputs = {
        "binary": canonical_input(args.binary, "mGBA binary"),
        "build_manifest": canonical_input(args.build_manifest, "build manifest"),
        "rom": canonical_input(args.rom, "ROM"),
        "state": canonical_input(args.state, "input state"),
        "single_input_script": canonical_input(
            DEFAULT_SINGLE_INPUT_SCRIPT, "single-input replay script"
        ),
    }
    source_save = inputs["rom"].with_suffix(".sav")
    _require_absent(source_save, "source ROM save sidecar")
    if inputs["single_input_script"] != DEFAULT_SINGLE_INPUT_SCRIPT.resolve(strict=True):
        raise ReplayError("single-input runner requires the repository fixed Lua script")
    validate_expected_hash(
        inputs["single_input_script"],
        EXPECTED_SINGLE_INPUT_SCRIPT_SHA256,
        "single-input replay script",
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
    ) = outputs
    args.staged_save = canonical_staged_save
    args.source_save = source_save
    if not os.access(args.binary, os.X_OK):
        raise ReplayError(f"mGBA binary is not executable: {args.binary}")
    validate_expected_hash(
        args.build_manifest,
        args.expected_build_manifest_sha256,
        "build manifest",
    )
    validate_expected_hash(args.binary, args.expected_binary_sha256, "mGBA binary")
    args.build_manifest_payload = validate_build_manifest(
        args.build_manifest, args.binary, args.expected_binary_sha256
    )
    validate_expected_hash(args.rom, args.expected_rom_sha256, "ROM")
    validate_expected_hash(args.state, args.expected_state_sha256, "state")
    return args


def _revalidate_critical_inputs(args: argparse.Namespace) -> None:
    _require_absent(args.source_save, "source ROM save sidecar")
    validate_expected_hash(
        args.build_manifest,
        args.expected_build_manifest_sha256,
        "build manifest",
    )
    validate_expected_hash(args.binary, args.expected_binary_sha256, "mGBA binary")
    validate_expected_hash(args.rom, args.expected_rom_sha256, "ROM")
    validate_expected_hash(args.state, args.expected_state_sha256, "state")
    validate_expected_hash(args.staged_rom, args.expected_rom_sha256, "staged ROM")
    validate_expected_hash(
        args.single_input_script,
        EXPECTED_SINGLE_INPUT_SCRIPT_SHA256,
        "single-input replay script",
    )


def _expected_payload(args: argparse.Namespace, run_id: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "frame": args.capture_frame,
        "capture_frame": args.capture_frame,
        "inputs": [_event(args.key, args.down_frame, args.up_frame)],
        "automatic_inputs": [],
        "recovery_inputs": [],
        "evidence_mode": "single-input",
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
            "MGBA_REPLAY_CAPTURE_FRAME": str(args.capture_frame),
            "MGBA_REPLAY_RUN_ID": run_id,
            "MGBA_REPLAY_ROM_SHA256": args.expected_rom_sha256,
            "MGBA_REPLAY_INPUT_STATE_SHA256": args.expected_state_sha256,
            "MGBA_SINGLE_INPUT_KEY": args.key,
            "MGBA_SINGLE_INPUT_DOWN_FRAME": str(args.down_frame),
            "MGBA_SINGLE_INPUT_UP_FRAME": str(args.up_frame),
        }
    )
    return environment


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
            "patch_sha256": EXPECTED_PATCH_SHA256,
            "build_manifest": str(args.build_manifest),
            "build_manifest_sha256": args.expected_build_manifest_sha256,
            "replay_script": str(args.single_input_script),
            "replay_script_sha256": EXPECTED_SINGLE_INPUT_SCRIPT_SHA256,
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
        args.staged_save,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        prepare_fresh_output(path, path.name)
    shutil.copy2(args.rom, args.staged_rom)
    validate_expected_hash(args.staged_rom, args.expected_rom_sha256, "staged ROM")

    run_id = secrets.token_hex(16)
    child = emulator_command(
        args.binary, [], args.single_input_script, args.staged_rom
    )
    wrapped = guarded_command(
        args.guard_summary, child, args.wall_timeout_s, args.idle_timeout_s
    )
    completed = subprocess.run(
        wrapped, cwd=ROOT, env=_environment(args, run_id), check=False
    )
    summary = _load_json(args.guard_summary, "guard summary")
    validate_guard_summary(summary, child, completed.returncode)
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
        print(f"run_macos_mgba_single_input: {error}", file=sys.stderr)
        raise SystemExit(2)
