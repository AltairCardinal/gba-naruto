#!/usr/bin/env python3
"""Promote a complete three-phase battle-effect capture into a tracked artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "battle-effect-frame-phase-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PHASES = ("renderer-post", "submit-post", "ack-post")
CAPTURE_SUFFIXES = (
    "-task-pool.bin",
    "-active-count.bin",
    "-active-pointers.bin",
    "-runtime-offsets.bin",
    "-shadow-oam.bin",
    "-hardware-oam.bin",
    "-submission.bin",
    "-vram.bin",
    "-pram.bin",
    "-io.bin",
    ".ss9",
    ".png",
    "-phase.json",
)
REPOSITORY_FILES = (
    "tools/export_battle_effect_frame_phase.py",
    "tools/verify_battle_effect_frame_phase.py",
    "tools/mgba_battle_effect_phase_capture.lua",
    "tools/run_macos_mgba_battle_effect_phase_capture.py",
    "tests/test_export_battle_effect_frame_phase.py",
    "tests/test_verify_battle_effect_frame_phase.py",
    "tests/test_mgba_battle_effect_phase_capture_script.py",
    "tests/test_run_macos_mgba_battle_effect_phase_capture.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def collect_phase_files(source_dir: Path) -> dict[str, Path]:
    """Return the exact required files for all three capture phases."""

    source_dir = Path(source_dir)
    files: dict[str, Path] = {}
    for phase in PHASES:
        for suffix in CAPTURE_SUFFIXES:
            relative = f"{phase}/capture{suffix}"
            path = source_dir / relative
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"missing or empty phase capture file: {path}")
            files[relative] = path
    return files


def _repository_hashes(profile: Path, toolchain_profile: Path) -> dict[str, str]:
    paths = list(REPOSITORY_FILES)
    try:
        paths.append(profile.resolve(strict=True).relative_to(ROOT).as_posix())
        paths.append(toolchain_profile.resolve(strict=True).relative_to(ROOT).as_posix())
    except ValueError as error:
        raise ValueError("capture profile must be inside the repository") from error
    result: dict[str, str] = {}
    for relative in paths:
        path = ROOT / relative
        if not path.is_file():
            raise ValueError(f"repository evidence file is missing: {relative}")
        result[relative] = _sha256(path)
    return dict(sorted(result.items()))


def export_artifact(
    source_dir: Path,
    guard_summary_path: Path,
    profile_path: Path,
    artifact_path: Path,
) -> dict[str, Any]:
    source_dir = source_dir.resolve(strict=True)
    guard_summary_path = guard_summary_path.resolve(strict=True)
    profile_path = profile_path.resolve(strict=True)
    artifact_path = artifact_path.resolve()
    if artifact_path.exists() and (not artifact_path.is_dir() or any(artifact_path.iterdir())):
        raise ValueError("artifact directory must be absent or empty")

    phase_files = collect_phase_files(source_dir)
    audit_path = source_dir / "audit.json"
    audit = _object(audit_path, "runtime audit")
    guard = _object(guard_summary_path, "guard summary")
    profile = _object(profile_path, "capture profile")
    if audit.get("schema") != "mgba-battle-effect-phase-capture-v1":
        raise ValueError("runtime audit schema mismatch")
    if audit.get("outcome") != "three-phase-captured":
        raise ValueError("runtime audit is not a complete three-phase capture")
    if audit.get("group_id") != profile.get("group_id"):
        raise ValueError("runtime audit group differs from profile")
    if audit.get("profile_sha256") != _sha256(profile_path):
        raise ValueError("runtime audit profile hash mismatch")
    if audit.get("guard_summary_sha256") != _sha256(guard_summary_path):
        raise ValueError("runtime audit guard hash mismatch")
    if guard.get("reason") != "completed" or guard.get("exit_code") != 0:
        raise ValueError("guard did not complete successfully")
    source_hashes = audit.get("files")
    if not isinstance(source_hashes, dict):
        raise ValueError("runtime audit file hash table is missing")
    for relative, path in phase_files.items():
        if source_hashes.get(relative) != _sha256(path):
            raise ValueError(f"runtime audit file hash mismatch: {relative}")

    phases = audit.get("phases")
    if not isinstance(phases, list) or [row.get("name") for row in phases] != list(PHASES):
        raise ValueError("runtime audit phase order mismatch")
    raw_toolchain = audit.get("toolchain")
    if not isinstance(raw_toolchain, dict):
        raise ValueError("runtime audit toolchain is missing")
    raw_toolchain_path = raw_toolchain.get("path")
    if not isinstance(raw_toolchain_path, str):
        raise ValueError("runtime audit toolchain path is missing")
    toolchain_profile_path = Path(raw_toolchain_path).resolve(strict=True)
    try:
        toolchain_relative = toolchain_profile_path.relative_to(ROOT).as_posix()
    except ValueError as error:
        raise ValueError("runtime toolchain profile must be inside the repository") from error
    if raw_toolchain.get("sha256") != _sha256(toolchain_profile_path):
        raise ValueError("runtime toolchain profile hash mismatch")
    toolchain = dict(raw_toolchain)
    toolchain["path"] = toolchain_relative

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{artifact_path.name}-", dir=artifact_path.parent
    ) as temporary:
        staging = Path(temporary)
        for relative, source in phase_files.items():
            destination = staging / "raw" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        shutil.copy2(audit_path, staging / "runtime-audit.json")
        shutil.copy2(guard_summary_path, staging / "guard-summary.json")

        copied_files = {
            path.relative_to(staging).as_posix(): _sha256(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        }
        manifest: dict[str, Any] = {
            "schema": PROMOTION_SCHEMA,
            "artifact_schema": SCHEMA,
            "artifact_status": "accepted",
            "description": (
                "One zero-input renderer transaction containing an active group-11 "
                "task, captured after rendering, submission, and acknowledgement."
            ),
            "group_id": audit["group_id"],
            "run_id": audit["run_id"],
            "input_mode": audit["input_mode"],
            "inputs": audit["inputs"],
            "phase_sequence": phases,
            "rom_sha256": audit["rom_sha256"],
            "input_state": {
                "path": profile["input_state"],
                "sha256": profile["input_state_sha256"],
            },
            "profile": {
                "path": profile_path.relative_to(ROOT).as_posix(),
                "sha256": _sha256(profile_path),
            },
            "animations": {
                "path": Path(audit["animations"]).resolve().relative_to(ROOT).as_posix(),
                "sha256": audit["animations_sha256"],
            },
            "toolchain": toolchain,
            "breakpoint_pc_semantics": {
                "mode": "Thumb",
                "saved_r15_to_breakpoint": "saved_r15 - 2",
                "mgba_source": "src/arm/debugger/debugger.c:_checkBreakpoints",
                "mgba_source_commit": toolchain["source_commit"],
            },
            "phase_script_sha256": audit["phase_script_sha256"],
            "dump_semantics": {
                "savestate_exact": [
                    "task-pool.bin",
                    "active-count.bin",
                    "active-pointers.bin",
                    "runtime-offsets.bin",
                    "shadow-oam.bin",
                    "hardware-oam.bin",
                    "submission.bin",
                    "vram.bin",
                    "pram.bin",
                ],
                "live_byte_read_only": ["io.bin"],
                "live_byte_read_boundary": (
                    "mGBA byte-wise MMIO reads are hash-locked live observations but "
                    "are not required to equal the emulator's serialized I/O image."
                ),
            },
            "files": dict(sorted(copied_files.items())),
            "repository_files": _repository_hashes(
                profile_path, toolchain_profile_path
            ),
            "boundary": profile["boundary"],
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if artifact_path.exists():
            artifact_path.rmdir()
        staging.rename(artifact_path)
    verifier_command = [
        sys.executable,
        str(ROOT / "tools/verify_battle_effect_frame_phase.py"),
        "--artifact",
        str(artifact_path),
    ]
    completed = subprocess.run(
        verifier_command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    try:
        verification = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("independent verifier did not return JSON") from error
    if completed.returncode or not isinstance(verification, dict) or not verification.get("verified"):
        raise ValueError(
            "independent verifier rejected promoted artifact: "
            + (completed.stderr or completed.stdout).strip()
        )
    manifest["verifier"] = {
        "command": [
            "python3",
            "tools/verify_battle_effect_frame_phase.py",
            "--artifact",
            "artifacts/battle-effect-frame-phase-v1",
        ],
        "exit_code": completed.returncode,
        "result": verification,
    }
    (artifact_path / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--guard-summary", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest = export_artifact(
        args.source_dir, args.guard_summary, args.profile, args.artifact
    )
    print(json.dumps({"artifact": str(args.artifact), "group_id": manifest["group_id"], "phase_count": len(PHASES)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
