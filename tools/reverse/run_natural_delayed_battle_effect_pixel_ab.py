#!/usr/bin/env python3
"""Build and capture both probe-free natural delayed-effect pixel variants."""

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

from tools.build_natural_delayed_battle_effect_pixel_ab import build_pair
from tools.run_battle_effect_direct_spawn_batch import build_case_command, sha256_file
from tools.verify_battle_effect_frame_phase import expected_phase_inputs


VARIANTS = ("baseline", "candidate")


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _repository_relative_file(path: Path, label: str) -> str:
    resolved = Path(path).resolve(strict=True)
    try:
        relative = resolved.relative_to(ROOT)
    except ValueError as error:
        raise ValueError(f"natural delayed pixel {label} must be inside repository") from error
    if not resolved.is_file():
        raise ValueError(f"natural delayed pixel {label} must be a file")
    return relative.as_posix()


def prepare_variant(
    output_root: Path,
    *,
    build_root: Path,
    build: dict[str, Any],
    variant: str,
) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown natural delayed pixel variant: {variant}")
    if build.get("schema") != "natural-delayed-battle-effect-pixel-ab-build-v1":
        raise ValueError("natural delayed pixel build schema mismatch")
    row = build.get("variants", {}).get(variant)
    if not isinstance(row, dict):
        raise ValueError(f"natural delayed pixel build variant is missing: {variant}")
    rom = (Path(build_root) / row["rom_path"]).resolve(strict=True)
    rom_sha = sha256_file(rom)
    if rom_sha != row.get("rom_sha256"):
        raise ValueError(f"natural delayed pixel ROM hash mismatch: {variant}")
    case_root = Path(output_root) / variant
    case_root.mkdir(parents=True, exist_ok=False)
    profile_path = case_root / "profile.json"
    group_id = build.get("group_id")
    sequence_id = build.get("sequence_id")
    runtime_oam = build.get("runtime_oam", {})
    input_mode = build.get("input_mode")
    inputs = build.get("inputs")
    if (
        not isinstance(group_id, int)
        or isinstance(group_id, bool)
        or not isinstance(sequence_id, int)
        or isinstance(sequence_id, bool)
        or not isinstance(runtime_oam, dict)
        or not isinstance(runtime_oam.get("renderer_shadow_change", True), bool)
        or input_mode not in {"zero-input-active-state", "explicit-input-sequence"}
        or not isinstance(inputs, list)
    ):
        raise ValueError("natural delayed pixel build identity mismatch")
    profile = {
        "schema": "battle-effect-phase-capture-profile-v1",
        "profile_id": f"group-{group_id:02d}-natural-pixel-{variant}",
        "variant": variant,
        "group_id": group_id,
        "sequence_id": sequence_id,
        "execution_mode": "natural-delayed-object-pixel-ab",
        "natural_gameplay_route": True,
        "input_mode": input_mode,
        "inputs": inputs,
        "input_state": build["input_state"],
        "input_state_sha256": build["input_state_sha256"],
        "source_runtime_evidence": build["input_evidence"],
        "source_runtime_evidence_sha256": build["input_evidence_sha256"],
        "source_natural_phase_artifact": build["source_natural_phase_artifact"],
        "source_natural_phase_manifest_sha256": build["source_natural_phase_manifest_sha256"],
        "source_build_manifest": "build/build-manifest.json",
        "source_build_manifest_sha256": sha256_file(Path(build_root) / "build-manifest.json"),
        "source_rom_sha256": rom_sha,
        "oam_transaction": {
            "renderer_shadow_change": runtime_oam.get(
                "renderer_shadow_change", True
            )
        },
        "timeout_frames": build.get("timeout_frames") or 600,
        "pixel_contract": build["edit"],
        "boundary": build["boundary"],
    }
    if input_mode == "explicit-input-sequence":
        profile["capture_frame"] = build.get("capture_frame")
    expected_phase_inputs(profile)
    _write_json(profile_path, profile)
    return {
        "variant": variant,
        "group_id": group_id,
        "sequence_id": sequence_id,
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
        raise ValueError("natural delayed pixel timeouts must be positive")
    binary = args.binary.resolve(strict=True)
    toolchain = args.toolchain_profile.resolve(strict=True)
    toolchain_relative = _repository_relative_file(toolchain, "toolchain profile")
    if sha256_file(binary) != args.expected_binary_sha256:
        raise ValueError("natural delayed pixel mGBA binary hash mismatch")
    output_root = args.output_root.resolve()
    if output_root.exists():
        if not output_root.is_dir() or any(output_root.iterdir()):
            raise ValueError("natural delayed pixel output root must be empty")
    else:
        output_root.mkdir(parents=True)
    build_root = output_root / "build"
    build = build_pair(ROOT, args.profile, build_root)
    results = []
    for variant in VARIANTS:
        case = prepare_variant(
            output_root / "runs", build_root=build_root, build=build, variant=variant
        )
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
                f"natural delayed pixel {variant} run failed: "
                + (completed.stderr or completed.stdout).strip()
            )
        audit_path = case["case_root"] / "output/audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        run_profile = json.loads(case["profile"].read_text(encoding="utf-8"))
        expected_input_mode, expected_inputs = expected_phase_inputs(run_profile)
        if (
            audit.get("outcome") != "three-phase-captured"
            or audit.get("input_mode") != expected_input_mode
            or audit.get("inputs") != expected_inputs
            or audit.get("automatic_inputs") != []
            or audit.get("recovery_inputs") != []
            or audit.get("pgid_clean") is not True
        ):
            raise ValueError(f"natural delayed pixel {variant} audit mismatch")
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
        "schema": "natural-delayed-battle-effect-pixel-ab-batch-v1",
        "build_manifest": "build/build-manifest.json",
        "build_manifest_sha256": sha256_file(build_root / "build-manifest.json"),
        "binary_sha256": args.expected_binary_sha256,
        "toolchain_profile": toolchain_relative,
        "toolchain_profile_sha256": sha256_file(toolchain),
        "natural_gameplay_route": True,
        "input_mode": build["input_mode"],
        "inputs": build["inputs"],
        "capture_frame": build.get("capture_frame"),
        "timeout_frames": build.get("timeout_frames"),
        "runs": results,
    }
    _write_json(output_root / "batch-audit.json", batch)
    print(json.dumps(batch, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
