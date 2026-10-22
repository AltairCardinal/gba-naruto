#!/usr/bin/env python3
"""Run one guarded three-phase capture for every unobserved effect group."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence

try:
    from tools.build_controlled_battle_effect_sequence_probe import (
        SCRATCH,
        build_probe,
    )
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    from build_controlled_battle_effect_sequence_probe import SCRATCH, build_probe
    from inspect_mgba_savestate import load_gba_state


ROOT = Path(__file__).resolve().parents[1]
BASE_ROM = ROOT / "rom/base.gba"
SEQUENCE_CATALOG = ROOT / "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
SINGLE_RUNNER = ROOT / "tools/run_macos_mgba_controlled_battle_effect_capture.py"
EXPECTED_GROUPS = (3, 4, 6, 7, 8, 9, 10, 12, 13, 15, 16, 17, 18)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _repository_file(raw: Any, label: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{label} path is missing")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} must be repository-relative")
    try:
        result = (ROOT / relative).resolve(strict=True)
        result.relative_to(ROOT)
    except (OSError, ValueError) as error:
        raise ValueError(f"{label} escapes or is missing") from error
    if not result.is_file():
        raise ValueError(f"{label} is not a regular file")
    return result


def load_spec(path: Path) -> dict[str, Any]:
    path = Path(path).resolve(strict=True)
    payload = _object(path, "controlled sequence batch spec")
    if payload.get("schema") != "battle-effect-controlled-sequence-batch-v1":
        raise ValueError("controlled sequence batch schema mismatch")
    rows = payload.get("cases")
    if not isinstance(rows, list):
        raise ValueError("controlled sequence cases are missing")
    try:
        group_ids = tuple(row["group_id"] for row in rows)
        sequence_ids = tuple(row["sequence_id"] for row in rows)
    except (KeyError, TypeError) as error:
        raise ValueError("controlled sequence case is malformed") from error
    if group_ids != EXPECTED_GROUPS or any(
        not isinstance(value, int) or isinstance(value, bool)
        for value in (*group_ids, *sequence_ids)
    ):
        raise ValueError("cases do not match the exact unobserved group denominator")

    catalog = _object(SEQUENCE_CATALOG, "sequence binding catalog")
    if catalog.get("schema") != "battle-effect-sequence-bindings-v1":
        raise ValueError("sequence binding catalog schema mismatch")
    by_sequence = {
        row.get("sequence_id"): row
        for row in catalog.get("sequences", [])
        if isinstance(row, dict)
    }
    for group_id, sequence_id in zip(group_ids, sequence_ids, strict=True):
        sequence = by_sequence.get(sequence_id, {})
        if sequence.get("nonzero_resource_group_ids") != [group_id]:
            raise ValueError(
                f"sequence {sequence_id} does not bind group {group_id} exclusively"
            )

    input_state = _repository_file(payload.get("input_state"), "input state")
    if sha256_file(input_state) != payload.get("input_state_sha256"):
        raise ValueError("input state hash mismatch")
    if payload.get("scratch_address") != f"0x{SCRATCH:08X}":
        raise ValueError("controlled sequence scratch address mismatch")
    try:
        scratch_before = bytes.fromhex(payload.get("scratch_expected_hex", ""))
    except ValueError as error:
        raise ValueError("scratch expected value is invalid hex") from error
    if len(scratch_before) != 4:
        raise ValueError("scratch expected value must be four bytes")
    state = load_gba_state(input_state)
    if state.read_memory(SCRATCH, 4) != scratch_before:
        raise ValueError("input state does not satisfy scratch precondition")

    result = dict(payload)
    result.update(
        {
            "path": path,
            "sha256": sha256_file(path),
            "input_state_path": input_state,
            "scratch_before": scratch_before,
            "sequence_catalog_sha256": sha256_file(SEQUENCE_CATALOG),
        }
    )
    return result


def prepare_case(
    spec: dict[str, Any], row: dict[str, int], output_root: Path
) -> dict[str, Any]:
    group_id = row["group_id"]
    sequence_id = row["sequence_id"]
    case_id = f"group-{group_id:02d}-sequence-{sequence_id:02d}"
    case_root = Path(output_root) / case_id
    case_root.mkdir(parents=True, exist_ok=False)
    rom_path = case_root / "probe.gba"
    profile_path = case_root / "profile.json"
    rom = build_probe(BASE_ROM.read_bytes(), sequence_id=sequence_id)
    rom_path.write_bytes(rom)
    rom_sha256 = hashlib.sha256(rom).hexdigest()
    profile = {
        "schema": "battle-effect-phase-capture-profile-v1",
        "profile_id": f"controlled-{case_id}",
        "group_id": group_id,
        "sequence_id": sequence_id,
        "execution_mode": "controlled-sequence-injection",
        "input_mode": "zero-input-active-state",
        "input_state": spec["input_state_path"].relative_to(ROOT).as_posix(),
        "input_state_sha256": spec["input_state_sha256"],
        "source_runtime_evidence": SEQUENCE_CATALOG.relative_to(ROOT).as_posix(),
        "source_runtime_evidence_sha256": spec["sequence_catalog_sha256"],
        "source_rom_sha256": rom_sha256,
        "timeout_frames": 60,
        "boundary": spec["boundary"],
    }
    profile_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "case_id": case_id,
        "group_id": group_id,
        "sequence_id": sequence_id,
        "case_root": case_root,
        "rom": rom_path,
        "rom_sha256": rom_sha256,
        "profile": profile_path,
        "profile_sha256": sha256_file(profile_path),
    }


def build_case_command(
    *,
    binary: Path,
    binary_sha256: str,
    toolchain_profile: Path,
    case: dict[str, Any],
    wall_timeout_s: float,
    idle_timeout_s: float,
) -> list[str]:
    return [
        sys.executable,
        str(SINGLE_RUNNER),
        "--binary", str(binary),
        "--toolchain-profile", str(toolchain_profile),
        "--expected-binary-sha256", binary_sha256,
        "--rom", str(case["rom"]),
        "--expected-rom-sha256", case["rom_sha256"],
        "--profile", str(case["profile"]),
        "--expected-profile-sha256", case["profile_sha256"],
        "--staged-rom", str(case["case_root"] / "staged.gba"),
        "--output-dir", str(case["case_root"] / "output"),
        "--guard-summary", str(case["case_root"] / "guard-summary.json"),
        "--wall-timeout-s", str(wall_timeout_s),
        "--idle-timeout-s", str(idle_timeout_s),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument("--toolchain-profile", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--wall-timeout-s", type=float, default=60)
    parser.add_argument("--idle-timeout-s", type=float, default=25)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.wall_timeout_s <= 0 or args.idle_timeout_s <= 0:
        raise ValueError("timeouts must be positive")
    spec = load_spec(args.spec)
    binary = args.binary.resolve(strict=True)
    if sha256_file(binary) != args.expected_binary_sha256:
        raise ValueError("mGBA binary hash mismatch")
    toolchain = args.toolchain_profile.resolve(strict=True)
    output_root = args.output_root.resolve()
    if output_root.exists():
        if not output_root.is_dir() or any(output_root.iterdir()):
            raise ValueError("batch output root must be absent or empty")
    else:
        output_root.mkdir(parents=True)

    results: list[dict[str, Any]] = []
    for row in spec["cases"]:
        case = prepare_case(spec, row, output_root)
        command = build_case_command(
            binary=binary,
            binary_sha256=args.expected_binary_sha256,
            toolchain_profile=toolchain,
            case=case,
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
                f"controlled case {case['case_id']} failed: "
                + (completed.stderr or completed.stdout).strip()
            )
        audit_path = case["case_root"] / "output/audit.json"
        audit = _object(audit_path, "case runtime audit")
        if (
            audit.get("outcome") != "binder-plus-three-phase-captured"
            or audit.get("group_id") != case["group_id"]
        ):
            raise ValueError(f"controlled case {case['case_id']} audit mismatch")
        results.append(
            {
                key: case[key]
                for key in (
                    "case_id", "group_id", "sequence_id", "rom_sha256",
                    "profile_sha256",
                )
            }
            | {
                "profile": case["profile"].relative_to(output_root).as_posix(),
                "audit": audit_path.relative_to(output_root).as_posix(),
                "audit_sha256": sha256_file(audit_path),
                "guard_summary": (
                    case["case_root"] / "guard-summary.json"
                ).relative_to(output_root).as_posix(),
                "peak_tree_rss_mib": audit.get("peak_tree_rss_mib"),
            }
        )
    batch_audit = {
        "schema": "battle-effect-controlled-sequence-batch-audit-v1",
        "spec": spec["path"].relative_to(ROOT).as_posix(),
        "spec_sha256": spec["sha256"],
        "input_state": spec["input_state"],
        "input_state_sha256": spec["input_state_sha256"],
        "scratch_address": spec["scratch_address"],
        "scratch_expected_hex": spec["scratch_expected_hex"],
        "sequence_catalog": SEQUENCE_CATALOG.relative_to(ROOT).as_posix(),
        "sequence_catalog_sha256": spec["sequence_catalog_sha256"],
        "binary_sha256": args.expected_binary_sha256,
        "toolchain_profile": toolchain.relative_to(ROOT).as_posix(),
        "toolchain_profile_sha256": sha256_file(toolchain),
        "case_count": len(results),
        "group_ids": [row["group_id"] for row in results],
        "cases": results,
        "boundary": spec["boundary"],
    }
    (output_root / "batch-audit.json").write_text(
        json.dumps(batch_audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(batch_audit, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"run_battle_effect_controlled_sequence_batch: {error}", file=sys.stderr)
        raise SystemExit(2)
