#!/usr/bin/env python3
"""Build and capture the two natural motion/effect parameter A/B variants."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_motion_effect_parameter_pixel_ab import build_pair, sha256_file
from tools.run_battle_effect_direct_spawn_batch import build_case_command


VARIANTS = ("baseline", "candidate")


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def repository_relative_file(path: Path, label: str) -> str:
    resolved = Path(path).resolve(strict=True)
    try:
        relative = resolved.relative_to(ROOT)
    except ValueError as error:
        raise ValueError(f"motion parameter {label} must be inside repository") from error
    if not resolved.is_file():
        raise ValueError(f"motion parameter {label} must be a file")
    return relative.as_posix()


def prepare_variant(
    output_root: Path,
    build_root: Path,
    build: dict[str, Any],
    variant: str,
) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown motion parameter variant: {variant}")
    if (
        build.get("schema") != "motion-effect-parameter-pixel-ab-build-v1"
        or build.get("group_id") != 3
        or build.get("sequence_id") != 3
    ):
        raise ValueError("motion parameter runtime requires the natural group-3 build")
    row = build.get("variants", {}).get(variant)
    if not isinstance(row, dict):
        raise ValueError(f"motion parameter build variant is missing: {variant}")
    rom = (Path(build_root) / row.get("rom_path", "")).resolve(strict=True)
    rom_sha = sha256_file(rom)
    if rom_sha != row.get("rom_sha256"):
        raise ValueError(f"motion parameter ROM hash mismatch: {variant}")
    if build.get("input_mode") != "zero-input-active-state" or build.get("inputs") != []:
        raise ValueError("motion parameter runtime input contract mismatch")

    case_root = Path(output_root) / variant
    case_root.mkdir(parents=True, exist_ok=False)
    profile_path = case_root / "profile.json"
    profile = {
        "schema": "battle-effect-phase-capture-profile-v1",
        "profile_id": f"group-03-motion-parameter-{variant}",
        "variant": variant,
        "group_id": 3,
        "sequence_id": 3,
        "execution_mode": "natural-motion-parameter-pixel-ab",
        "natural_gameplay_route": True,
        "input_mode": "zero-input-active-state",
        "inputs": [],
        "input_state": build["input_state"],
        "input_state_sha256": build["input_state_sha256"],
        "source_runtime_evidence": build["input_evidence"],
        "source_runtime_evidence_sha256": build["input_evidence_sha256"],
        "source_phase_artifact": build["source_phase_artifact"],
        "source_phase_manifest_sha256": build["source_phase_manifest_sha256"],
        "source_build_manifest": "build/build-manifest.json",
        "source_build_manifest_sha256": sha256_file(Path(build_root) / "build-manifest.json"),
        "source_rom_sha256": rom_sha,
        "parameter_contract": build["edit"],
        "timeout_frames": build["timeout_frames"],
        "boundary": build["boundary"],
    }
    write_json(profile_path, profile)
    return {
        "variant": variant,
        "case_root": case_root,
        "rom": rom,
        "rom_sha256": rom_sha,
        "profile": profile_path,
        "profile_sha256": sha256_file(profile_path),
        "guard_summary": case_root / "guard-summary.json",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument("--toolchain-profile", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--wall-timeout-s", type=float, default=120)
    parser.add_argument("--idle-timeout-s", type=float, default=35)
    args = parser.parse_args(argv)
    if args.wall_timeout_s <= 0 or args.idle_timeout_s <= 0:
        raise ValueError("motion parameter timeouts must be positive")
    binary = args.binary.resolve(strict=True)
    toolchain = args.toolchain_profile.resolve(strict=True)
    if sha256_file(binary) != args.expected_binary_sha256:
        raise ValueError("motion parameter mGBA binary hash mismatch")
    output_root = args.output_root.resolve()
    if output_root.exists():
        if not output_root.is_dir() or any(output_root.iterdir()):
            raise ValueError("motion parameter output root must be absent or empty")
    else:
        output_root.mkdir(parents=True)

    build_root = output_root / "build"
    build = build_pair(ROOT, args.profile, build_root)
    results = []
    for variant in VARIANTS:
        case = prepare_variant(output_root / "runs", build_root, build, variant)
        completed = subprocess.run(
            build_case_command(
                binary=binary,
                binary_sha256=args.expected_binary_sha256,
                toolchain_profile=toolchain,
                case=case,
                wall_timeout_s=args.wall_timeout_s,
                idle_timeout_s=args.idle_timeout_s,
            ),
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode:
            raise ValueError(
                f"motion parameter {variant} run failed: "
                + (completed.stderr or completed.stdout).strip()
            )
        audit_path = case["case_root"] / "output/audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if (
            audit.get("outcome") != "three-phase-captured"
            or audit.get("group_id") != 3
            or audit.get("input_mode") != "zero-input-active-state"
            or audit.get("inputs") != []
            or audit.get("automatic_inputs") != []
            or audit.get("recovery_inputs") != []
            or audit.get("pgid_clean") is not True
        ):
            raise ValueError(f"motion parameter {variant} audit mismatch")
        results.append(
            {
                "variant": variant,
                "rom_sha256": case["rom_sha256"],
                "profile_sha256": case["profile_sha256"],
                "audit_sha256": sha256_file(audit_path),
                "guard_summary_sha256": sha256_file(case["guard_summary"]),
                "peak_tree_rss_mib": audit.get("peak_tree_rss_mib"),
                "pgid_clean": True,
            }
        )
    batch = {
        "schema": "motion-effect-parameter-pixel-ab-batch-v1",
        "build_manifest": "build/build-manifest.json",
        "build_manifest_sha256": sha256_file(build_root / "build-manifest.json"),
        "binary_sha256": args.expected_binary_sha256,
        "toolchain_profile": repository_relative_file(toolchain, "toolchain profile"),
        "toolchain_profile_sha256": sha256_file(toolchain),
        "natural_gameplay_route": True,
        "input_mode": "zero-input-active-state",
        "inputs": [],
        "run_budget": {"planned": 2, "actual": 2, "blind_retries": 0},
        "runs": results,
    }
    write_json(output_root / "batch-audit.json", batch)
    print(json.dumps(batch, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
