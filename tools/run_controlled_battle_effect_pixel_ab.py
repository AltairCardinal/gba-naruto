#!/usr/bin/env python3
"""Build and run both controlled battle-effect pixel variants."""

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

from tools.build_controlled_battle_effect_direct_spawn_probe import CASES_BY_ID
from tools.build_controlled_battle_effect_pixel_ab import build_pair
from tools.run_battle_effect_direct_spawn_batch import (
    build_case_command as build_direct_case_command,
    sha256_file,
)
from tools.run_battle_effect_controlled_sequence_batch import (
    build_case_command as build_sequence_case_command,
)


VARIANTS = ("baseline", "candidate")
DIRECT_EVIDENCE = ROOT / "artifacts/battle-effect-direct-spawn-runtime-v1/evidence.json"
CONTROLLED_EVIDENCE = ROOT / "artifacts/battle-effect-controlled-runtime-v1/evidence.json"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _repository_relative_file(path: Path, label: str) -> str:
    resolved = Path(path).resolve(strict=True)
    try:
        relative = resolved.relative_to(ROOT)
    except ValueError as error:
        raise ValueError(f"controlled pixel {label} must be inside repository") from error
    if not resolved.is_file():
        raise ValueError(f"controlled pixel {label} must be a file")
    return relative.as_posix()


def prepare_variant(
    output_root: Path,
    *,
    build_root: Path,
    build: dict[str, Any],
    variant: str,
) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown controlled pixel variant: {variant}")
    if build.get("schema") != "controlled-battle-effect-pixel-ab-build-v1":
        raise ValueError("controlled pixel build manifest schema mismatch")
    case_id = build.get("case_id")
    case = CASES_BY_ID.get(case_id)
    execution_mode = build.get("execution_mode")
    if execution_mode == "controlled-direct-spawn":
        if case is None:
            raise ValueError("controlled pixel direct-spawn case mismatch")
        group_id, sequence_id = case.group_id, case.sequence_id
        runner_kind = "direct-spawn"
        runtime_evidence = DIRECT_EVIDENCE
    elif execution_mode == "controlled-sequence-injection":
        group_id = build.get("group_id")
        sequence_id = build.get("sequence_id")
        if case_id != "group-06-sequence-08" or (group_id, sequence_id) != (6, 8):
            raise ValueError("controlled pixel sequence case mismatch")
        runner_kind = "controlled-sequence"
        runtime_evidence = CONTROLLED_EVIDENCE
    else:
        raise ValueError("controlled pixel execution mode mismatch")
    variant_build = build.get("variants", {}).get(variant)
    if not isinstance(variant_build, dict):
        raise ValueError(f"controlled pixel build variant is missing: {variant}")
    rom = (Path(build_root) / variant_build["rom_path"]).resolve(strict=True)
    rom_sha256 = sha256_file(rom)
    if rom_sha256 != variant_build.get("rom_sha256"):
        raise ValueError(f"controlled pixel ROM hash mismatch: {variant}")

    case_root = Path(output_root) / variant
    case_root.mkdir(parents=True, exist_ok=False)
    profile_path = case_root / "profile.json"
    profile = {
        "schema": "battle-effect-phase-capture-profile-v1",
        "profile_id": f"controlled-{case_id}-pixel-{variant}",
        "case_id": case_id,
        "variant": variant,
        "group_id": group_id,
        "sequence_id": sequence_id,
        "execution_mode": (
            "controlled-direct-spawn-pixel-ab"
            if runner_kind == "direct-spawn"
            else "controlled-sequence-injection"
        ),
        "natural_gameplay_route": False,
        "input_mode": "zero-input-active-state",
        "input_state": build["input_state"],
        "input_state_sha256": build["input_state_sha256"],
        "source_runtime_evidence": runtime_evidence.relative_to(ROOT).as_posix(),
        "source_runtime_evidence_sha256": sha256_file(runtime_evidence),
        "source_build_manifest": "build/build-manifest.json",
        "source_build_manifest_sha256": sha256_file(Path(build_root) / "build-manifest.json"),
        "source_rom_sha256": rom_sha256,
        "timeout_frames": 60,
        "pixel_contract": build["edit"],
        "boundary": (
            "Production-relocated resource under a controlled entry. This is zero-input "
            "controlled final-pixel evidence, not natural gameplay."
        ),
    }
    if runner_kind == "direct-spawn":
        profile["side"] = case.side
        profile["allocator_reset"] = {
            "function": "0x0807FDCC",
            "tile_start": f"0x{case.allocator_tile_start:04X}",
            "tile_end": f"0x{case.allocator_tile_end:04X}",
            "palette_start": case.allocator_palette_start,
            "palette_end": case.allocator_palette_end,
        }
        profile["spawn"] = {
            "selector": "0x0807FE2C",
            "function": f"0x{case.spawn_function:08X}",
            "side": case.side,
            "x": case.spawn_x,
            "y": case.spawn_y,
        }
    _write_json(profile_path, profile)
    return {
        "variant": variant,
        "case_id": case_id,
        "group_id": group_id,
        "sequence_id": sequence_id,
        "runner_kind": runner_kind,
        "case_root": case_root,
        "rom": rom,
        "rom_sha256": rom_sha256,
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
    parser.add_argument("--wall-timeout-s", type=float, default=90)
    parser.add_argument("--idle-timeout-s", type=float, default=30)
    args = parser.parse_args(argv)
    if args.wall_timeout_s <= 0 or args.idle_timeout_s <= 0:
        raise ValueError("controlled pixel timeouts must be positive")
    binary = args.binary.resolve(strict=True)
    toolchain = args.toolchain_profile.resolve(strict=True)
    toolchain_relative = _repository_relative_file(toolchain, "toolchain profile")
    if sha256_file(binary) != args.expected_binary_sha256:
        raise ValueError("controlled pixel mGBA binary hash mismatch")
    output_root = args.output_root.resolve()
    if output_root.exists():
        if not output_root.is_dir() or any(output_root.iterdir()):
            raise ValueError("controlled pixel output root must be absent or empty")
    else:
        output_root.mkdir(parents=True)

    build_root = output_root / "build"
    build = build_pair(ROOT, args.profile, build_root)
    runs_root = output_root / "runs"
    results = []
    for variant in VARIANTS:
        case = prepare_variant(
            runs_root, build_root=build_root, build=build, variant=variant
        )
        command_builder = (
            build_direct_case_command
            if case["runner_kind"] == "direct-spawn"
            else build_sequence_case_command
        )
        completed = subprocess.run(
            command_builder(
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
                f"controlled pixel {variant} run failed: "
                + (completed.stderr or completed.stdout).strip()
            )
        audit_path = case["case_root"] / "output/audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        expected_outcome = (
            "three-phase-captured"
            if case["runner_kind"] == "direct-spawn"
            else "binder-plus-three-phase-captured"
        )
        if audit.get("outcome") != expected_outcome:
            raise ValueError(f"controlled pixel {variant} phase capture mismatch")
        results.append(
            {
                "variant": variant,
                "rom_sha256": case["rom_sha256"],
                "profile_sha256": case["profile_sha256"],
                "audit_sha256": sha256_file(audit_path),
                "guard_summary_sha256": sha256_file(case["guard_summary"]),
                "peak_tree_rss_mib": audit.get("peak_tree_rss_mib"),
                "pgid_clean": audit.get("pgid_clean"),
            }
        )
    batch = {
        "schema": "controlled-battle-effect-pixel-ab-batch-v1",
        "build_manifest": "build/build-manifest.json",
        "build_manifest_sha256": sha256_file(build_root / "build-manifest.json"),
        "binary_sha256": args.expected_binary_sha256,
        "toolchain_profile": toolchain_relative,
        "toolchain_profile_sha256": sha256_file(toolchain),
        "natural_gameplay_route": False,
        "runs": results,
    }
    _write_json(output_root / "batch-audit.json", batch)
    print(json.dumps(batch, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
