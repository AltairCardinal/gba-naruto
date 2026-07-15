#!/usr/bin/env python3
"""Build and prove the pinned macOS Intel mGBA Qt script backport."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
GUARD_SCRIPT = ROOT / "tools" / "run_guarded.py"
HEAVY_LOCK = ROOT / "build" / "resource-guard" / "heavy.lock"
PATCH_PATH = ROOT / "tools" / "patches" / "mgba-0.10.5-qt-script-cli.patch"
SOURCE_TAG = "0.10.5"
SOURCE_COMMIT = "26b7884bc25a5933960f3cdcd98bac1ae14d42e2"
BACKPORT_COMMIT = "7cacae126207de5499857439b9c7919bf8e882c2"
EXPECTED_PATCH_SHA256 = "e76c8fc4f5451bdffe28b7f3595cd441bbb90fb1aa88a926cfbe4f1254d3d2a6"
EXPECTED_PATCH_PATHS = (
    "src/platform/qt/ConfigController.cpp",
    "src/platform/qt/Window.cpp",
)
QT5_PREFIX = "/usr/local/opt/qt@5"
MIN_AVAILABLE_MIB = 4096
MAX_TREE_RSS_MIB = 1536
BUILD_PARALLEL = 2


class BuildError(RuntimeError):
    """A provenance, guard, build, or runtime proof failed closed."""


@dataclass(frozen=True)
class PatchMetadata:
    commit: str
    paths: tuple[str, ...]
    sha256: str


@dataclass(frozen=True)
class VerifiedPatch:
    data: bytes
    metadata: PatchMetadata


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_git_identity(head: str, tag: str, status: str) -> None:
    if head.strip() != SOURCE_COMMIT:
        raise BuildError(f"source commit must be {SOURCE_COMMIT}, got {head.strip()}")
    if tag.strip() != SOURCE_TAG:
        raise BuildError(f"source tag must be {SOURCE_TAG}, got {tag.strip()}")
    if status.strip():
        raise BuildError("source checkout is dirty; refusing to build")


def _capture_git(source: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise BuildError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout


def validate_source_checkout(source: Path) -> None:
    if not source.is_dir():
        raise BuildError(f"source checkout does not exist: {source}")
    validate_git_identity(
        _capture_git(source, "rev-parse", "HEAD"),
        _capture_git(source, "describe", "--tags", "--exact-match", "HEAD"),
        _capture_git(source, "status", "--short"),
    )


def inspect_patch(text: str) -> PatchMetadata:
    patch_sha256 = hashlib.sha256(text.encode()).hexdigest()
    if patch_sha256 != EXPECTED_PATCH_SHA256:
        raise BuildError(
            f"patch SHA-256 must be {EXPECTED_PATCH_SHA256}, got {patch_sha256}"
        )
    first_line = text.splitlines()[0] if text else ""
    match = re.fullmatch(r"From ([0-9a-f]{40}) Mon Sep 17 00:00:00 2001", first_line)
    if not match or match.group(1) != BACKPORT_COMMIT:
        raise BuildError(f"patch must originate from upstream commit {BACKPORT_COMMIT}")
    paths = []
    for old, new in re.findall(r"^diff --git a/(.+) b/(.+)$", text, re.MULTILINE):
        if old != new:
            raise BuildError(f"patch renames a path unexpectedly: {old} -> {new}")
        paths.append(old)
    if tuple(paths) != EXPECTED_PATCH_PATHS:
        raise BuildError(f"patch paths must be exactly {EXPECTED_PATCH_PATHS}, got {tuple(paths)}")
    return PatchMetadata(match.group(1), tuple(paths), patch_sha256)


def load_verified_patch(path: Path) -> VerifiedPatch:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise BuildError(f"patch is not UTF-8: {error}") from error
    return VerifiedPatch(data=data, metadata=inspect_patch(text))


def apply_patch_checked(worktree: Path, patch_data: bytes) -> None:
    check = subprocess.run(
        ["git", "-C", str(worktree), "apply", "--check", "-"],
        input=patch_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check.returncode:
        raise BuildError(
            f"git apply --check failed: {check.stderr.decode(errors='replace').strip()}"
        )
    applied = subprocess.run(
        ["git", "-C", str(worktree), "apply", "-"],
        input=patch_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if applied.returncode:
        raise BuildError(
            "git apply failed after successful check: "
            f"{applied.stderr.decode(errors='replace').strip()}"
        )


def validate_invocation_paths(**paths: Path) -> dict[str, Path]:
    canonical = {name: path.resolve(strict=False) for name, path in paths.items()}
    items = list(canonical.items())
    for index, (left_name, left) in enumerate(items):
        for right_name, right in items[index + 1 :]:
            if left == right or left in right.parents or right in left.parents:
                raise BuildError(
                    f"path overlap is unsafe: {left_name}={left} and {right_name}={right}"
                )
    return canonical


def _prepare_fresh_output(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if stat.S_ISREG(mode) or stat.S_ISLNK(mode):
        path.unlink()
        return
    raise BuildError(f"stale {label} is not a regular file or symlink: {path}")


def guarded_command(summary: Path, cwd: Path, command: Sequence[str]) -> list[str]:
    return [
        sys.executable,
        str(GUARD_SCRIPT),
        "--summary",
        str(summary),
        "--lock-file",
        str(HEAVY_LOCK),
        "--cwd",
        str(cwd),
        "--min-available-mib",
        str(MIN_AVAILABLE_MIB),
        "--max-tree-rss-mib",
        str(MAX_TREE_RSS_MIB),
        "--wall-timeout-s",
        "1800",
        "--idle-timeout-s",
        "180",
        "--",
        *map(str, command),
    ]


def cmake_configure_command(source: Path, build: Path) -> list[str]:
    return [
        "cmake",
        "-S",
        str(source),
        "-B",
        str(build),
        "-G",
        "Ninja",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_PREFIX_PATH={QT5_PREFIX}",
        "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
        "-DENABLE_SCRIPTING=ON",
        "-DBUILD_QT=ON",
        "-DBUILD_SDL=OFF",
    ]


def cmake_build_command(build: Path) -> list[str]:
    return ["cmake", "--build", str(build), "--parallel", str(BUILD_PARALLEL)]


def validate_help(help_text: str) -> None:
    if "--script" not in help_text:
        raise BuildError("patched Qt frontend help is missing --script")


def validate_guard_summary(summary: Mapping[str, object], expected_command: Sequence[str]) -> None:
    if summary.get("reason") != "completed" or summary.get("exit_code") != 0:
        raise BuildError(
            f"guarded command failed: {summary.get('reason')}/{summary.get('exit_code')}"
        )
    if not isinstance(summary.get("child_pid"), int):
        raise BuildError("guard summary is missing an owned child PID")
    if (
        summary.get("protection_backend") != "posix-process-group"
        or summary.get("degraded") is not False
    ):
        raise BuildError("guard did not use non-degraded POSIX process-group ownership")
    peak = summary.get("peak_tree_rss_mib")
    if not isinstance(peak, (int, float)) or peak > MAX_TREE_RSS_MIB:
        raise BuildError(f"guard peak RSS is invalid or above {MAX_TREE_RSS_MIB} MiB")
    if summary.get("command") != list(map(str, expected_command)):
        raise BuildError("guard summary command fingerprint does not match")


def sentinel_lua(marker: Path, run_id: str) -> str:
    marker_literal = json.dumps(str(marker))
    run_literal = json.dumps(run_id)
    return f'''local marker = {marker_literal}
local run_id = {run_literal}
local frame = 0

local function write_marker(payload)
    local out = assert(io.open(marker, "w"))
    out:write(payload)
    out:close()
end

write_marker(string.format('{{"script_loaded":true,"frame":0,"pc":"loaded","run_id":"%s"}}', run_id))
callbacks:add("frame", function()
    frame = frame + 1
    local pc = tostring(emu:readRegister("pc"))
    write_marker(string.format('{{"script_loaded":true,"frame":%d,"pc":"%s","run_id":"%s"}}', frame, pc, run_id))
    os.exit(0)
end)
'''


def validate_sentinel(marker: Path, run_id: str) -> dict[str, object]:
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise BuildError(f"Lua sentinel marker is missing or invalid: {error}") from error
    if (
        payload.get("script_loaded") is not True
        or payload.get("frame", 0) < 1
        or not payload.get("pc")
        or payload.get("run_id") != run_id
    ):
        raise BuildError(f"Lua sentinel is not from the current run: {payload}")
    return payload


def make_manifest(
    *,
    binary: Path,
    patch_metadata: PatchMetadata,
    version_output: str,
    file_output: str,
    summaries: Mapping[str, Mapping[str, object]],
    sentinel_result: Mapping[str, object],
) -> dict[str, object]:
    if f"mGBA {SOURCE_TAG}" not in version_output or SOURCE_COMMIT not in version_output:
        raise BuildError(
            f"binary version does not identify pinned source commit: {version_output.strip()}"
        )
    if "Mach-O" not in file_output or "x86_64" not in file_output:
        raise BuildError(f"binary is not Mach-O x86_64: {file_output.strip()}")
    return {
        "label": "mGBA 0.10.5 + Qt script backport",
        "version": SOURCE_TAG,
        "source_commit": SOURCE_COMMIT,
        "backport_commit": BACKPORT_COMMIT,
        "patch_sha256": patch_metadata.sha256,
        "binary_sha256": sha256_file(binary),
        "architecture": "x86_64",
        "cmake_flags": cmake_configure_command(Path("SOURCE"), Path("BUILD"))[7:],
        "build_parallel": BUILD_PARALLEL,
        "guard": {
            "min_available_mib": MIN_AVAILABLE_MIB,
            "max_tree_rss_mib": MAX_TREE_RSS_MIB,
            "lock_file": str(HEAVY_LOCK),
            "summaries": dict(summaries),
        },
        "version_output": version_output.strip(),
        "file_output": file_output.strip(),
        "sentinel": dict(sentinel_result),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _run_phase(
    name: str,
    command: Sequence[str],
    *,
    cwd: Path,
    evidence_dir: Path,
) -> dict[str, object]:
    summary_path = evidence_dir / f"{name}.json"
    _prepare_fresh_output(summary_path, "guard summary")
    wrapped = guarded_command(summary_path, cwd, command)
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    completed = subprocess.run(wrapped, cwd=ROOT, env=env, check=False)
    if not summary_path.is_file():
        if completed.returncode:
            raise BuildError(
                f"guard wrapper exited {completed.returncode} without a fresh {name} summary"
            )
        raise BuildError(f"guard did not write {name} summary")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if completed.returncode != summary.get("exit_code"):
        raise BuildError(
            "guard wrapper/result mismatch: "
            f"wrapper={completed.returncode}, summary={summary.get('exit_code')}"
        )
    if completed.returncode == 75 and summary.get("reason") == "admission-rejected":
        raise BuildError(f"BLOCKED: available memory is below {MIN_AVAILABLE_MIB} MiB")
    if completed.returncode != 0:
        raise BuildError(f"guard wrapper exited {completed.returncode} for {name}")
    validate_guard_summary(summary, command)
    return summary


def _prepare(source: Path, workspace: Path, patch_data: bytes) -> int:
    validate_source_checkout(source)
    verified_patch = VerifiedPatch(
        data=patch_data,
        metadata=inspect_patch(patch_data.decode("utf-8")),
    )
    if workspace.exists():
        raise BuildError(f"independent workspace already exists: {workspace}")
    workspace.parent.mkdir(parents=True, exist_ok=True)
    cloned = subprocess.run(
        ["git", "clone", "--quiet", "--no-local", str(source), str(workspace)],
        check=False,
    )
    if cloned.returncode:
        raise BuildError("local source clone failed")
    validate_source_checkout(workspace)
    apply_patch_checked(workspace, verified_patch.data)
    return 0


def _capture(output: Path, command: Sequence[str]) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    _prepare_fresh_output(output, "captured output")
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output.write_text(completed.stdout, encoding="utf-8")
    return completed.returncode


def _run_staged_sentinel(binary: Path, script: Path, source_rom: Path, staged_rom: Path) -> int:
    staged_rom.parent.mkdir(parents=True, exist_ok=True)
    for stale in staged_rom.parent.glob(f"{staged_rom.stem}.*"):
        if not stale.is_file() and not stale.is_symlink():
            raise BuildError(f"stale sentinel sidecar is not a file: {stale}")
        stale.unlink()
    shutil.copy2(source_rom, staged_rom)
    completed = subprocess.run(
        [str(binary), "--script", str(script), str(staged_rom)],
        check=False,
    )
    return completed.returncode


def _internal_main(argv: Sequence[str]) -> int | None:
    if not argv or argv[0] not in {"_prepare", "_capture", "_sentinel"}:
        return None
    if argv[0] == "_prepare":
        if len(argv) != 4:
            raise BuildError("_prepare requires SOURCE WORKSPACE PATCH_BASE64")
        try:
            patch_data = base64.b64decode(argv[3], validate=True)
        except ValueError as error:
            raise BuildError(f"_prepare patch payload is not valid base64: {error}") from error
        return _prepare(Path(argv[1]), Path(argv[2]), patch_data)
    if argv[0] == "_sentinel":
        if len(argv) != 5:
            raise BuildError("_sentinel requires BINARY SCRIPT SOURCE_ROM STAGED_ROM")
        return _run_staged_sentinel(*(Path(value) for value in argv[1:]))
    if "--" not in argv:
        raise BuildError("_capture requires OUTPUT -- COMMAND")
    separator = argv.index("--")
    if separator != 2 or len(argv) < 4:
        raise BuildError("_capture requires OUTPUT -- COMMAND")
    return _capture(Path(argv[1]), argv[3:])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-cache", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--patch", type=Path, default=PATCH_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    internal = _internal_main(raw)
    if internal is not None:
        return internal
    args = build_parser().parse_args(raw)
    canonical = validate_invocation_paths(
        source=args.source_cache,
        workspace=args.workspace,
        build=args.build_dir,
        evidence=args.evidence_dir,
        manifest=args.manifest,
        rom=args.rom,
        patch=args.patch,
    )
    args.source_cache = canonical["source"]
    args.workspace = canonical["workspace"]
    args.build_dir = canonical["build"]
    args.evidence_dir = canonical["evidence"]
    args.manifest = canonical["manifest"]
    args.rom = canonical["rom"]
    args.patch = canonical["patch"]
    validate_source_checkout(args.source_cache)
    verified_patch = load_verified_patch(args.patch)
    if not args.rom.is_file():
        raise BuildError(f"base ROM does not exist: {args.rom}")
    if args.build_dir.exists():
        raise BuildError(f"build directory already exists: {args.build_dir}")
    if args.workspace.exists():
        raise BuildError(f"independent workspace already exists: {args.workspace}")
    _prepare_fresh_output(args.manifest, "manifest")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)

    summaries: dict[str, dict[str, object]] = {}
    prepare = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_prepare",
        str(args.source_cache),
        str(args.workspace),
        base64.b64encode(verified_patch.data).decode("ascii"),
    ]
    summaries["prepare"] = _run_phase("prepare", prepare, cwd=ROOT, evidence_dir=args.evidence_dir)
    configure = cmake_configure_command(args.workspace, args.build_dir)
    summaries["configure"] = _run_phase(
        "configure", configure, cwd=ROOT, evidence_dir=args.evidence_dir
    )
    build = cmake_build_command(args.build_dir)
    summaries["build"] = _run_phase("build", build, cwd=ROOT, evidence_dir=args.evidence_dir)

    binary = args.build_dir / "qt" / "mGBA.app" / "Contents" / "MacOS" / "mGBA"
    if not binary.is_file():
        raise BuildError(f"built Qt binary is missing: {binary}")
    help_output = args.evidence_dir / "help.txt"
    _prepare_fresh_output(help_output, "help output")
    help_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_capture",
        str(help_output),
        "--",
        str(binary),
        "--help",
    ]
    summaries["help"] = _run_phase("help", help_command, cwd=ROOT, evidence_dir=args.evidence_dir)
    validate_help(help_output.read_text(encoding="utf-8"))
    version_output = args.evidence_dir / "version.txt"
    _prepare_fresh_output(version_output, "version output")
    version_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_capture",
        str(version_output),
        "--",
        str(binary),
        "--version",
    ]
    summaries["version"] = _run_phase(
        "version", version_command, cwd=ROOT, evidence_dir=args.evidence_dir
    )

    sentinel_path = args.evidence_dir / "sentinel.lua"
    marker_path = args.evidence_dir / "sentinel-result.json"
    _prepare_fresh_output(sentinel_path, "sentinel script")
    _prepare_fresh_output(marker_path, "sentinel marker")
    run_id = secrets.token_hex(16)
    sentinel_path.write_text(sentinel_lua(marker_path, run_id), encoding="utf-8")
    staged_rom = args.evidence_dir / "sentinel-base.gba"
    sentinel_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_sentinel",
        str(binary),
        str(sentinel_path),
        str(args.rom),
        str(staged_rom),
    ]
    sentinel_summary = _run_phase(
        "sentinel", sentinel_command, cwd=ROOT, evidence_dir=args.evidence_dir
    )
    sentinel_result = validate_sentinel(marker_path, run_id)
    sentinel_summary["sentinel_run_id"] = run_id
    summaries["sentinel"] = sentinel_summary

    validate_source_checkout(args.source_cache)

    file_output = subprocess.run(
        ["file", str(binary)], text=True, stdout=subprocess.PIPE, check=True
    ).stdout
    manifest = make_manifest(
        binary=binary,
        patch_metadata=verified_patch.metadata,
        version_output=version_output.read_text(encoding="utf-8"),
        file_output=file_output,
        summaries=summaries,
        sentinel_result=sentinel_result,
    )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as error:
        print(f"build_macos_mgba: {error}", file=sys.stderr)
        raise SystemExit(2)
