#!/usr/bin/env python3
"""Run preflighted battle-effect phase cases through the guarded single-case runner."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
SINGLE_RUNNER = ROOT / "tools/run_macos_mgba_battle_effect_phase_capture.py"
SCHEMA = "battle-effect-phase-batch-v1"


def sha256_file(path: Path) -> str:
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


def repository_relative_path(raw: str, label: str) -> Path:
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} path must be repository-relative")
    try:
        resolved = (ROOT / relative).resolve(strict=True)
        resolved.relative_to(ROOT)
    except (OSError, ValueError) as error:
        raise ValueError(f"{label} path must stay inside the repository") from error
    return resolved


def load_batch_spec(path: Path) -> dict[str, Any]:
    path = Path(path).resolve(strict=True)
    spec = _object(path, "battle-effect phase batch spec")
    if spec.get("schema") != SCHEMA:
        raise ValueError("battle-effect phase batch schema mismatch")
    cases = spec.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("battle-effect phase batch cases are missing")
    group_ids: list[int] = []
    case_ids: list[str] = []
    for row in cases:
        if not isinstance(row, dict):
            raise ValueError("battle-effect phase batch case must be an object")
        group_id = row.get("group_id")
        case_id = row.get("case_id")
        profile_raw = row.get("profile")
        profile_hash = row.get("profile_sha256")
        rom_hash = row.get("rom_sha256")
        if (
            not isinstance(group_id, int)
            or isinstance(group_id, bool)
            or not 1 <= group_id <= 18
            or not isinstance(case_id, str)
            or not case_id
            or not isinstance(profile_raw, str)
            or not isinstance(profile_hash, str)
            or len(profile_hash) != 64
            or not isinstance(rom_hash, str)
            or len(rom_hash) != 64
        ):
            raise ValueError("battle-effect phase batch case identity is invalid")
        profile_path = repository_relative_path(
            profile_raw, "battle-effect phase profile"
        )
        if not profile_path.is_file() or sha256_file(profile_path) != profile_hash:
            raise ValueError(f"battle-effect phase profile hash mismatch: {profile_raw}")
        profile = _object(profile_path, "battle-effect phase profile")
        if (
            profile.get("schema") != "battle-effect-phase-capture-profile-v1"
            or profile.get("group_id") != group_id
            or profile.get("source_rom_sha256") != rom_hash
        ):
            raise ValueError(f"battle-effect phase profile contract mismatch: {profile_raw}")
        if "default_rom" not in row and "rom_rebuild" not in row:
            raise ValueError(f"battle-effect phase case has no ROM source: {case_id}")
        group_ids.append(group_id)
        case_ids.append(case_id)
    if len(group_ids) != len(set(group_ids)) or len(case_ids) != len(set(case_ids)):
        raise ValueError("battle-effect phase batch groups and case ids must be unique")
    if spec.get("observed_group_denominator") != len(group_ids) + len(
        spec.get("already_promoted_group_ids", [])
    ):
        raise ValueError("battle-effect observed group denominator mismatch")
    return spec


def parse_rom_overrides(values: Sequence[str]) -> dict[int, Path]:
    result: dict[int, Path] = {}
    for value in values:
        group_text, separator, path_text = value.partition("=")
        if not separator or not group_text.isdigit() or not path_text:
            raise ValueError("ROM override must use GROUP=PATH")
        group_id = int(group_text)
        if group_id in result:
            raise ValueError(f"duplicate ROM override for group {group_id}")
        result[group_id] = Path(path_text)
    return result


def build_case_command(
    *,
    python: str,
    binary: Path,
    toolchain_profile: Path,
    binary_sha256: str,
    rom: Path,
    rom_sha256: str,
    profile: Path,
    profile_sha256: str,
    case_root: Path,
    wall_timeout_s: float,
    idle_timeout_s: float,
) -> list[str]:
    return [
        python,
        str(SINGLE_RUNNER),
        "--binary",
        str(binary),
        "--toolchain-profile",
        str(toolchain_profile),
        "--expected-binary-sha256",
        binary_sha256,
        "--rom",
        str(rom),
        "--expected-rom-sha256",
        rom_sha256,
        "--profile",
        str(profile),
        "--expected-profile-sha256",
        profile_sha256,
        "--staged-rom",
        str(case_root / "staged.gba"),
        "--output-dir",
        str(case_root / "output"),
        "--guard-summary",
        str(case_root / "guard-summary.json"),
        "--wall-timeout-s",
        str(wall_timeout_s),
        "--idle-timeout-s",
        str(idle_timeout_s),
    ]


def _resolve_rom(row: dict[str, Any], overrides: dict[int, Path]) -> Path:
    group_id = row["group_id"]
    if group_id in overrides:
        path = overrides[group_id]
    elif isinstance(row.get("default_rom"), str):
        path = ROOT / row["default_rom"]
    else:
        raise ValueError(
            f"group {group_id} requires --rom {group_id}=PATH; rebuild hint: "
            + " ".join(row.get("rom_rebuild", []))
        )
    path = path.resolve(strict=True)
    if sha256_file(path) != row["rom_sha256"]:
        raise ValueError(f"group {group_id} ROM hash mismatch: {path}")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--toolchain-profile", type=Path, required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument("--rom", action="append", default=[], metavar="GROUP=PATH")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--wall-timeout-s", type=float, default=40.0)
    parser.add_argument("--idle-timeout-s", type=float, default=20.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.wall_timeout_s <= 0 or args.idle_timeout_s <= 0:
        raise ValueError("wall and idle timeouts must be positive")
    spec_path = args.spec.resolve(strict=True)
    spec = load_batch_spec(spec_path)
    binary = args.binary.resolve(strict=True)
    toolchain = args.toolchain_profile.resolve(strict=True)
    if sha256_file(binary) != args.expected_binary_sha256:
        raise ValueError("mGBA binary hash mismatch")
    overrides = parse_rom_overrides(args.rom)
    expected_groups = {row["group_id"] for row in spec["cases"]}
    if not set(overrides) <= expected_groups:
        raise ValueError("ROM override names a group outside the batch")
    resolved: list[tuple[dict[str, Any], Path, Path]] = []
    output_root = args.output_root.resolve()
    if output_root.exists() and (not output_root.is_dir() or any(output_root.iterdir())):
        raise ValueError("batch output root must be absent or empty")
    for row in spec["cases"]:
        rom = _resolve_rom(row, overrides)
        profile = repository_relative_path(
            row["profile"], "battle-effect phase profile"
        )
        resolved.append((row, rom, profile))

    output_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for row, rom, profile in resolved:
        case_root = output_root / row["case_id"]
        command = build_case_command(
            python=sys.executable,
            binary=binary,
            toolchain_profile=toolchain,
            binary_sha256=args.expected_binary_sha256,
            rom=rom,
            rom_sha256=row["rom_sha256"],
            profile=profile,
            profile_sha256=row["profile_sha256"],
            case_root=case_root,
            wall_timeout_s=args.wall_timeout_s,
            idle_timeout_s=args.idle_timeout_s,
        )
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode:
            raise ValueError(
                f"phase case {row['case_id']} failed with {completed.returncode}: "
                + (completed.stderr or completed.stdout).strip()
            )
        audit_path = case_root / "output/audit.json"
        guard_path = case_root / "guard-summary.json"
        audit = _object(audit_path, "phase case audit")
        if audit.get("group_id") != row["group_id"] or audit.get("outcome") != "three-phase-captured":
            raise ValueError(f"phase case {row['case_id']} audit mismatch")
        results.append(
            {
                "case_id": row["case_id"],
                "group_id": row["group_id"],
                "profile": row["profile"],
                "profile_sha256": row["profile_sha256"],
                "rom_sha256": row["rom_sha256"],
                "audit": audit_path.relative_to(output_root).as_posix(),
                "audit_sha256": sha256_file(audit_path),
                "guard_summary": guard_path.relative_to(output_root).as_posix(),
                "guard_summary_sha256": sha256_file(guard_path),
                "peak_tree_rss_mib": audit.get("peak_tree_rss_mib"),
            }
        )
    batch_audit = {
        "schema": "battle-effect-phase-batch-audit-v1",
        "spec": spec_path.relative_to(ROOT).as_posix(),
        "spec_sha256": sha256_file(spec_path),
        "binary_sha256": args.expected_binary_sha256,
        "toolchain_profile": toolchain.relative_to(ROOT).as_posix(),
        "toolchain_profile_sha256": sha256_file(toolchain),
        "case_count": len(results),
        "group_ids": [row["group_id"] for row in results],
        "cases": results,
        "boundary": spec["boundary"],
    }
    audit_path = output_root / "batch-audit.json"
    audit_path.write_text(
        json.dumps(batch_audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(batch_audit, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"run_battle_effect_phase_batch: {error}", file=sys.stderr)
        raise SystemExit(2)
