#!/usr/bin/env python3
"""Run one zero-input replay with the current desktop mGBA runtime profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
from typing import Mapping, Sequence

try:
    from tools.macos_mgba_runtime_residue import (
        RuntimeResidueError,
        probe_runtime_residue,
    )
    from tools.macos_mgba_toolchain_profile import (
        CURRENT_MGBA_SOURCE_COMMIT,
        CURRENT_TOOLCHAIN_PROFILE_SHA256,
        validate_current_toolchain_profile,
    )
    from tools.run_macos_mgba_replay import (
        DEFAULT_REPLAY_SCRIPT,
        EXPECTED_REPLAY_SCRIPT_SHA256,
        ReplayError,
        _expected_payload,
        _load_json,
        _replay_environment,
        canonical_input,
        emulator_command,
        guarded_command,
        prepare_fresh_output,
        read_ps_snapshot,
        sha256_file,
        validate_completion_marker,
        validate_expected_hash,
        validate_guard_summary,
        validate_output_bundle,
        validate_output_paths,
        validate_owned_pgid_clean,
    )
    from tools.run_macos_mgba_single_input import _absolute, _require_absent
except ModuleNotFoundError:
    from macos_mgba_runtime_residue import (
        RuntimeResidueError,
        probe_runtime_residue,
    )
    from macos_mgba_toolchain_profile import (
        CURRENT_MGBA_SOURCE_COMMIT,
        CURRENT_TOOLCHAIN_PROFILE_SHA256,
        validate_current_toolchain_profile,
    )
    from run_macos_mgba_replay import (
        DEFAULT_REPLAY_SCRIPT,
        EXPECTED_REPLAY_SCRIPT_SHA256,
        ReplayError,
        _expected_payload,
        _load_json,
        _replay_environment,
        canonical_input,
        emulator_command,
        guarded_command,
        prepare_fresh_output,
        read_ps_snapshot,
        sha256_file,
        validate_completion_marker,
        validate_expected_hash,
        validate_guard_summary,
        validate_output_bundle,
        validate_output_paths,
        validate_owned_pgid_clean,
    )
    from run_macos_mgba_single_input import _absolute, _require_absent


ROOT = Path(__file__).resolve().parents[1]


def _replace_file(source: Path, target: Path) -> None:
    os.replace(source, target)


def _stage_bytes(target: Path, raw: bytes) -> Path:
    temporary = target.with_name(f".{target.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _atomic_replace_bytes(target: Path, raw: bytes) -> None:
    temporary = _stage_bytes(target, raw)
    try:
        _replace_file(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--toolchain-profile", type=Path, required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--expected-rom-sha256", required=True)
    parser.add_argument("--expected-state-sha256", required=True)
    parser.add_argument("--capture-frame", type=int, default=80)
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
    if (
        not isinstance(args.capture_frame, int)
        or isinstance(args.capture_frame, bool)
        or args.capture_frame <= 0
    ):
        raise ReplayError("capture frame must be a positive integer")
    if args.wall_timeout_s <= 0 or args.idle_timeout_s <= 0:
        raise ReplayError("wall and idle timeouts must be positive")

    inputs = {
        "binary": canonical_input(args.binary, "mGBA binary"),
        "toolchain_profile": canonical_input(
            args.toolchain_profile, "mGBA runtime profile"
        ),
        "rom": canonical_input(args.rom, "ROM"),
        "state": canonical_input(args.state, "input state"),
        "replay_script": canonical_input(
            DEFAULT_REPLAY_SCRIPT, "zero-input replay script"
        ),
    }
    source_save = inputs["rom"].with_suffix(".sav")
    _require_absent(source_save, "source ROM save sidecar")
    validate_expected_hash(
        inputs["replay_script"],
        EXPECTED_REPLAY_SCRIPT_SHA256,
        "zero-input replay script",
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
            Path(f"{args.audit}.finalized.json"),
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
        args.finalization_marker,
    ) = outputs
    args.staged_save = canonical_staged_save
    args.source_save = source_save

    if not os.access(args.binary, os.X_OK):
        raise ReplayError(f"mGBA binary is not executable: {args.binary}")
    validate_expected_hash(args.binary, args.expected_binary_sha256, "mGBA binary")
    validate_expected_hash(
        args.toolchain_profile,
        CURRENT_TOOLCHAIN_PROFILE_SHA256,
        "mGBA runtime profile",
    )
    validate_current_toolchain_profile(
        args.toolchain_profile, args.binary, args.expected_binary_sha256
    )
    validate_expected_hash(args.rom, args.expected_rom_sha256, "ROM")
    validate_expected_hash(args.state, args.expected_state_sha256, "state")
    return args


def _revalidate_critical_inputs(args: argparse.Namespace) -> None:
    _require_absent(args.source_save, "source ROM save sidecar")
    _require_absent(args.staged_save, "staged ROM save sidecar")
    for path, expected, label in (
        (
            args.toolchain_profile,
            CURRENT_TOOLCHAIN_PROFILE_SHA256,
            "mGBA runtime profile",
        ),
        (args.binary, args.expected_binary_sha256, "mGBA binary"),
        (args.rom, args.expected_rom_sha256, "ROM"),
        (args.state, args.expected_state_sha256, "state"),
        (args.staged_rom, args.expected_rom_sha256, "staged ROM"),
        (
            args.replay_script,
            EXPECTED_REPLAY_SCRIPT_SHA256,
            "zero-input replay script",
        ),
    ):
        validate_expected_hash(path, expected, label)


def _consume_staged_save(path: Path) -> dict[str, object]:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return {
            "created": False,
            "path": str(path),
            "removed": False,
            "sha256": None,
            "size": 0,
        }
    if not stat.S_ISREG(mode):
        raise ReplayError(f"staged ROM save sidecar is not a regular file: {path}")
    result = {
        "created": True,
        "path": str(path),
        "removed": True,
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
    }
    path.unlink()
    _require_absent(path, "staged ROM save sidecar")
    return result


def _finalize(
    args: argparse.Namespace,
    bundle: Mapping[str, object],
    summary: Mapping[str, object],
    residue: Mapping[str, object],
    staged_save_sidecar: Mapping[str, object],
) -> dict[str, object]:
    if bundle["audit"] != bundle["sentinel"]:
        raise ReplayError("raw audit and sentinel payloads differ")
    raw_audit = args.audit.read_bytes()
    raw_sentinel = args.sentinel.read_bytes()
    finalized = dict(bundle["audit"])
    finalized.update(
        {
            "evidence_mode": "zero-input",
            "zero_input_verified": True,
            "binary_sha256": args.expected_binary_sha256,
            "toolchain": {
                "kind": "current-desktop-runtime-profile",
                "path": str(args.toolchain_profile),
                "sha256": CURRENT_TOOLCHAIN_PROFILE_SHA256,
                "source_commit": CURRENT_MGBA_SOURCE_COMMIT,
                "patch_sha256": None,
            },
            "replay_script": str(args.replay_script),
            "replay_script_sha256": EXPECTED_REPLAY_SCRIPT_SHA256,
            "output_state_sha256": bundle["state_sha256"],
            "output_png_sha256": bundle["png_sha256"],
            "guard_summary_sha256": sha256_file(args.guard_summary),
            "peak_tree_rss_mib": summary["peak_tree_rss_mib"],
            "child_pgid": summary["child_pid"],
            "pgid_clean": True,
            "runtime_residue": dict(residue),
            "staged_save_sidecar": dict(staged_save_sidecar),
            "finalization_marker": str(args.finalization_marker),
            "staged_rom": str(args.staged_rom),
            "staged_rom_sha256": sha256_file(args.staged_rom),
        }
    )
    encoded = (json.dumps(finalized, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    encoded_sha256 = hashlib.sha256(encoded).hexdigest()
    marker = (
        json.dumps(
            {
                "schema": "mgba-replay-finalization-v1",
                "status": "finalized",
                "run_id": finalized["run_id"],
                "audit": str(args.audit),
                "audit_sha256": encoded_sha256,
                "sentinel": str(args.sentinel),
                "sentinel_sha256": encoded_sha256,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    staged: list[Path] = []
    try:
        staged.append(_stage_bytes(args.audit, encoded))
        staged.append(_stage_bytes(args.sentinel, encoded))
        staged.append(_stage_bytes(args.finalization_marker, marker))
        _replace_file(staged[0], args.audit)
        _replace_file(staged[1], args.sentinel)
        _replace_file(staged[2], args.finalization_marker)
    except Exception as error:
        args.finalization_marker.unlink(missing_ok=True)
        try:
            _atomic_replace_bytes(args.audit, raw_audit)
            _atomic_replace_bytes(args.sentinel, raw_sentinel)
        except Exception as rollback_error:
            raise ReplayError(
                f"replay finalize failed and rollback failed: {rollback_error}"
            ) from error
        raise ReplayError(f"replay finalize failed: {error}") from error
    finally:
        for temporary in staged:
            temporary.unlink(missing_ok=True)
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
        args.finalization_marker,
        args.staged_save,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        prepare_fresh_output(path, path.name)
    shutil.copy2(args.rom, args.staged_rom)
    validate_expected_hash(args.staged_rom, args.expected_rom_sha256, "staged ROM")

    run_id = secrets.token_hex(16)
    child = emulator_command(args.binary, [], args.replay_script, args.staged_rom)
    wrapped = guarded_command(
        args.guard_summary,
        args.done_marker,
        child,
        args.wall_timeout_s,
        args.idle_timeout_s,
    )
    completed = subprocess.run(
        wrapped, cwd=ROOT, env=_replay_environment(args, run_id), check=False
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
    bundle = validate_output_bundle(
        args.output_state,
        args.output_png,
        args.audit,
        args.sentinel,
        _expected_payload(args, run_id),
    )
    staged_save_sidecar = _consume_staged_save(args.staged_save)
    _revalidate_critical_inputs(args)
    finalized = _finalize(args, bundle, summary, residue, staged_save_sidecar)
    print(json.dumps(finalized, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, RuntimeResidueError) as error:
        print(f"run_macos_mgba_replay_current: {error}", file=sys.stderr)
        raise SystemExit(2)
