#!/usr/bin/env python3
"""Run one zero-input mGBA checkpoint replay behind the project resource guard."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
GUARD_SCRIPT = ROOT / "tools" / "run_guarded.py"
HEAVY_LOCK = ROOT / "build" / "resource-guard" / "heavy.lock"
DEFAULT_REPLAY_SCRIPT = ROOT / "tools" / "mgba_checkpoint_replay.lua"
EXPECTED_REPLAY_SCRIPT_SHA256 = "1481f10cd8f72c7635326e8d3233c2466b76c7a4b812cefe1220fe43c29f9659"
SOURCE_COMMIT = "26b7884bc25a5933960f3cdcd98bac1ae14d42e2"
BACKPORT_COMMIT = "7cacae126207de5499857439b9c7919bf8e882c2"
EXPECTED_PATCH_SHA256 = "e76c8fc4f5451bdffe28b7f3595cd441bbb90fb1aa88a926cfbe4f1254d3d2a6"
EXPECTED_LABEL = "mGBA 0.10.5 + Qt script backport"
MIN_AVAILABLE_MIB = 4096
MAX_TREE_RSS_MIB = 1536
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class ReplayError(RuntimeError):
    """Replay provenance, containment, or fresh-output validation failed closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _reject_symlink_components(path: Path, label: str) -> None:
    candidate = _absolute(path)
    if candidate.is_symlink():
        raise ReplayError(f"{label} path is a symlink: {candidate}")


def canonical_input(path: Path, label: str) -> Path:
    _reject_symlink_components(path, label)
    absolute = _absolute(path)
    try:
        mode = absolute.lstat().st_mode
    except FileNotFoundError as error:
        raise ReplayError(f"{label} is missing: {absolute}") from error
    if not stat.S_ISREG(mode):
        raise ReplayError(f"{label} is not a regular file: {absolute}")
    return absolute.resolve(strict=True)


def validate_output_paths(
    paths: Sequence[Path], *, derived: Sequence[Path] = ()
) -> list[Path]:
    canonical: list[Path] = []
    for path in [*paths, *derived]:
        _reject_symlink_components(path, "output")
        absolute = _absolute(path)
        if absolute.is_symlink():
            raise ReplayError(f"output path is a symlink: {absolute}")
        canonical.append(absolute.resolve(strict=False))
    if len(set(canonical)) != len(canonical):
        raise ReplayError("output paths overlap after canonicalization")
    for index, left in enumerate(canonical):
        for right in canonical[index + 1 :]:
            if left in right.parents or right in left.parents:
                raise ReplayError(f"output path overlap is unsafe: {left} / {right}")
    return canonical[: len(paths)]


def prepare_fresh_output(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if stat.S_ISREG(mode):
        path.unlink()
        return
    raise ReplayError(f"stale {label} is not a regular file: {path}")


def require_fresh_regular_file(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise ReplayError(f"fresh {label} is missing: {path}") from error
    if not stat.S_ISREG(mode):
        raise ReplayError(f"fresh {label} is not a regular file: {path}")
    if path.stat().st_size <= 0:
        raise ReplayError(f"fresh {label} is empty: {path}")


def validate_expected_hash(path: Path, expected: str, label: str) -> str:
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise ReplayError(f"expected {label} SHA-256 must be 64 lowercase hexadecimal characters")
    actual = sha256_file(path)
    if actual != expected:
        raise ReplayError(f"{label} SHA-256 mismatch: expected {expected}, got {actual}")
    return actual


def revalidate_critical_inputs(args: argparse.Namespace) -> None:
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
        args.replay_script,
        args.expected_replay_script_sha256,
        "replay script",
    )
    for script, expected_sha in zip(args.pre_script, args.expected_pre_script_sha256):
        validate_expected_hash(script, expected_sha, "pre-script")


def _load_json(path: Path, label: str) -> dict[str, object]:
    require_fresh_regular_file(path, label)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReplayError(f"fresh {label} is invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ReplayError(f"fresh {label} must be a JSON object")
    return payload


def validate_build_manifest(
    path: Path, binary: Path, expected_binary_sha256: str | None = None
) -> dict[str, object]:
    payload = _load_json(path, "build manifest")
    binary_sha256 = sha256_file(binary)
    if expected_binary_sha256 is not None and binary_sha256 != expected_binary_sha256:
        raise ReplayError(
            "mGBA binary SHA-256 mismatch: "
            f"expected {expected_binary_sha256}, got {binary_sha256}"
        )
    expected = {
        "label": EXPECTED_LABEL,
        "version": "0.10.5",
        "source_commit": SOURCE_COMMIT,
        "backport_commit": BACKPORT_COMMIT,
        "patch_sha256": EXPECTED_PATCH_SHA256,
        "architecture": "x86_64",
        "binary_sha256": binary_sha256,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ReplayError(f"build manifest {key} mismatch: expected {value}, got {payload.get(key)}")
    return payload


def emulator_command(
    binary: Path, pre_scripts: Sequence[Path], replay_script: Path, staged_rom: Path
) -> list[str]:
    command = [str(binary)]
    for script in [*pre_scripts, replay_script]:
        command.extend(("--script", str(script)))
    command.append(str(staged_rom))
    return command


def guarded_command(
    summary: Path,
    success_marker: Path,
    child_command: Sequence[str],
    wall_timeout_s: float,
    idle_timeout_s: float,
) -> list[str]:
    return [
        sys.executable,
        str(GUARD_SCRIPT),
        "--summary",
        str(summary),
        "--success-marker",
        str(success_marker),
        "--lock-file",
        str(HEAVY_LOCK),
        "--cwd",
        str(ROOT),
        "--min-available-mib",
        str(MIN_AVAILABLE_MIB),
        "--max-tree-rss-mib",
        str(MAX_TREE_RSS_MIB),
        "--wall-timeout-s",
        str(wall_timeout_s),
        "--idle-timeout-s",
        str(idle_timeout_s),
        "--",
        *map(str, child_command),
    ]


def validate_guard_summary(
    summary: Mapping[str, object], expected_command: Sequence[str], wrapper_returncode: int
) -> None:
    summary_exit = summary.get("exit_code")
    if wrapper_returncode != summary_exit:
        raise ReplayError(
            f"guard wrapper/result mismatch: wrapper={wrapper_returncode}, summary={summary_exit}"
        )
    if summary.get("reason") != "completed" or summary_exit != 0:
        raise ReplayError(f"guarded replay failed: {summary.get('reason')}/{summary_exit}")
    if summary.get("completion_trigger") != "success-marker":
        raise ReplayError("guard summary is missing success-marker completion trigger")
    if not isinstance(summary.get("child_pid"), int) or summary["child_pid"] <= 0:
        raise ReplayError("guard summary is missing a valid owned child PID/PGID")
    if summary.get("protection_backend") != "posix-process-group":
        raise ReplayError("guard did not use POSIX process-group protection")
    if summary.get("degraded") is not False:
        raise ReplayError("guard protection is degraded")
    peak = summary.get("peak_tree_rss_mib")
    if not isinstance(peak, (int, float)) or peak < 0 or peak > MAX_TREE_RSS_MIB:
        raise ReplayError(f"guard peak RSS is invalid or above {MAX_TREE_RSS_MIB} MiB")
    if summary.get("command") != list(map(str, expected_command)):
        raise ReplayError("guard summary command does not match requested replay")


def validate_completion_marker(
    path: Path, expected: Mapping[str, object]
) -> dict[str, object]:
    payload = _load_json(path, "completion marker")
    if payload != dict(expected):
        raise ReplayError(
            f"completion marker mismatch: expected {dict(expected)}, got {payload}"
        )
    return payload


def read_ps_snapshot() -> str:
    completed = subprocess.run(
        ["ps", "-axo", "pid=,pgid="],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=5,
    )
    if completed.returncode:
        raise ReplayError(f"final PGID query failed: {completed.stderr.strip()}")
    return completed.stdout


def validate_owned_pgid_clean(process_group_id: int, ps_output: str) -> None:
    for line in ps_output.splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 2:
            raise ReplayError(f"final ps output is malformed: {line!r}")
        try:
            pid, pgid = (int(value) for value in fields)
        except ValueError as error:
            raise ReplayError(f"final ps output is malformed: {line!r}") from error
        if pid <= 0 or pgid <= 0:
            raise ReplayError(f"final ps output is malformed: {line!r}")
        if pgid == process_group_id:
            raise ReplayError(f"owned PGID {process_group_id} still has PID {pid}")


def validate_replay_payload(payload: Mapping[str, object], expected: Mapping[str, object]) -> None:
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ReplayError(f"replay payload {key} mismatch: expected {value}, got {payload.get(key)}")


def validate_output_bundle(
    state: Path,
    png: Path,
    audit: Path,
    sentinel: Path,
    expected: Mapping[str, object],
) -> dict[str, object]:
    for path, label in ((state, "state"), (png, "PNG"), (audit, "audit"), (sentinel, "sentinel")):
        require_fresh_regular_file(path, label)
    for path, label in ((state, "state"), (png, "PNG")):
        with path.open("rb") as stream:
            if stream.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                raise ReplayError(f"fresh {label} does not have an mGBA PNG signature")
    audit_payload = _load_json(audit, "audit")
    sentinel_payload = _load_json(sentinel, "sentinel")
    validate_replay_payload(audit_payload, expected)
    validate_replay_payload(sentinel_payload, expected)
    return {
        "state_sha256": sha256_file(state),
        "png_sha256": sha256_file(png),
        "audit": audit_payload,
        "sentinel": sentinel_payload,
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
    parser.add_argument("--staged-rom", type=Path, required=True)
    parser.add_argument("--output-state", type=Path, required=True)
    parser.add_argument("--output-png", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--sentinel", type=Path, required=True)
    parser.add_argument("--guard-summary", type=Path, required=True)
    parser.add_argument("--capture-frame", type=int, default=80)
    parser.add_argument(
        "--evidence-mode",
        choices=("zero-input", "script-order-diagnostic"),
        default="zero-input",
    )
    parser.add_argument("--pre-script", type=Path, action="append", default=[])
    parser.add_argument("--replay-script", type=Path, default=DEFAULT_REPLAY_SCRIPT)
    parser.add_argument("--wall-timeout-s", type=float, default=120)
    parser.add_argument("--idle-timeout-s", type=float, default=30)
    return parser


def validate_args(args: argparse.Namespace) -> argparse.Namespace:
    if args.capture_frame <= 0:
        raise ReplayError("capture frame must be positive")
    if args.wall_timeout_s <= 0 or args.idle_timeout_s <= 0:
        raise ReplayError("wall and idle timeouts must be positive")
    inputs = {
        "binary": canonical_input(args.binary, "mGBA binary"),
        "build_manifest": canonical_input(args.build_manifest, "build manifest"),
        "rom": canonical_input(args.rom, "ROM"),
        "state": canonical_input(args.state, "input state"),
        "replay_script": canonical_input(args.replay_script, "replay script"),
    }
    pre_scripts = [canonical_input(path, f"pre-script {index + 1}") for index, path in enumerate(args.pre_script)]
    default_replay = DEFAULT_REPLAY_SCRIPT.resolve(strict=True)
    if args.evidence_mode == "zero-input":
        if inputs["replay_script"] != default_replay:
            raise ReplayError(
                f"zero-input mode requires the repository replay script: {default_replay}"
            )
        args.expected_replay_script_sha256 = EXPECTED_REPLAY_SCRIPT_SHA256
    else:
        args.expected_replay_script_sha256 = sha256_file(inputs["replay_script"])
    validate_expected_hash(
        inputs["replay_script"],
        args.expected_replay_script_sha256,
        "replay script",
    )
    if args.evidence_mode == "zero-input" and pre_scripts:
        raise ReplayError("zero-input mode forbids pre-scripts")
    declared_outputs = [
        args.staged_rom,
        args.output_state,
        args.output_png,
        args.audit,
        args.sentinel,
        args.guard_summary,
        Path(f"{args.guard_summary}.done.json"),
    ]
    staged_save = args.staged_rom.with_suffix(".sav")
    outputs = validate_output_paths(
        declared_outputs,
        derived=[staged_save],
    )
    canonical_staged_save = _absolute(staged_save).resolve(strict=False)
    for output in [*outputs, canonical_staged_save]:
        for label, input_path in inputs.items():
            if output == input_path or output in input_path.parents or input_path in output.parents:
                raise ReplayError(f"unsafe input/output overlap: {label}={input_path}, output={output}")
        for script in pre_scripts:
            if output == script or output in script.parents or script in output.parents:
                raise ReplayError(f"unsafe pre-script/output overlap: {script}, output={output}")
    if outputs[0].parent == inputs["rom"].parent:
        raise ReplayError("staged ROM must not share the source ROM directory")
    for key, value in inputs.items():
        setattr(args, key, value)
    args.pre_script = pre_scripts
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
    args.expected_pre_script_sha256 = [sha256_file(path) for path in args.pre_script]
    validate_expected_hash(args.rom, args.expected_rom_sha256, "ROM")
    validate_expected_hash(args.state, args.expected_state_sha256, "state")
    return args


def _expected_payload(args: argparse.Namespace, run_id: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "frame": args.capture_frame,
        "capture_frame": args.capture_frame,
        "inputs": [],
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


def _replay_environment(args: argparse.Namespace, run_id: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
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
        }
    )
    return env


def _finalize_payloads(
    args: argparse.Namespace,
    bundle: Mapping[str, object],
    summary: Mapping[str, object],
) -> dict[str, object]:
    additions = {
        "evidence_mode": args.evidence_mode,
        "zero_input_verified": args.evidence_mode == "zero-input",
        "binary_sha256": args.expected_binary_sha256,
        "patch_sha256": EXPECTED_PATCH_SHA256,
        "build_manifest": str(args.build_manifest),
        "build_manifest_sha256": args.expected_build_manifest_sha256,
        "replay_script": str(args.replay_script),
        "replay_script_sha256": args.expected_replay_script_sha256,
        "pre_scripts": [
            {"path": str(path), "sha256": sha256}
            for path, sha256 in zip(args.pre_script, args.expected_pre_script_sha256)
        ],
        "output_state_sha256": bundle["state_sha256"],
        "output_png_sha256": bundle["png_sha256"],
        "guard_summary_sha256": sha256_file(args.guard_summary),
        "peak_tree_rss_mib": summary["peak_tree_rss_mib"],
        "child_pgid": summary["child_pid"],
        "pgid_clean": True,
        "staged_rom": str(args.staged_rom),
        "staged_rom_sha256": sha256_file(args.staged_rom),
    }
    finalized = dict(bundle["audit"])
    finalized.update(additions)
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
    if sha256_file(args.staged_rom) != args.expected_rom_sha256:
        raise ReplayError("staged ROM SHA-256 changed during copy")

    run_id = secrets.token_hex(16)
    child = emulator_command(args.binary, args.pre_script, args.replay_script, args.staged_rom)
    wrapped = guarded_command(
        args.guard_summary,
        args.done_marker,
        child,
        args.wall_timeout_s,
        args.idle_timeout_s,
    )
    completed = subprocess.run(wrapped, cwd=ROOT, env=_replay_environment(args, run_id), check=False)
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
    validate_owned_pgid_clean(summary["child_pid"], read_ps_snapshot())
    expected = _expected_payload(args, run_id)
    bundle = validate_output_bundle(
        args.output_state, args.output_png, args.audit, args.sentinel, expected
    )
    revalidate_critical_inputs(args)
    finalized = _finalize_payloads(args, bundle, summary)
    print(json.dumps(finalized, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReplayError as error:
        print(f"run_macos_mgba_replay: {error}", file=sys.stderr)
        raise SystemExit(2)
