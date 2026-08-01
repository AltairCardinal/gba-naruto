#!/usr/bin/env python3
"""Run the remaining direct battle-effect selector/spawn cases under the heavy guard."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence

try:
    from tools.build_controlled_battle_effect_direct_spawn_probe import (
        CASES,
        DirectSpawnCase,
        build_probe,
    )
except ModuleNotFoundError:
    from build_controlled_battle_effect_direct_spawn_probe import (
        CASES,
        DirectSpawnCase,
        build_probe,
    )


ROOT = Path(__file__).resolve().parents[1]
BASE_ROM = ROOT / "rom/base.gba"
INPUT_STATE = ROOT / "artifacts/runtime-checkpoints/scenario-50-battle-15-escort-12hp-player-turn.ss9"
INPUT_STATE_SHA256 = "7d6796a767d574f5f7a91935c3c1e65ce44edbc51aa5a6b587784d4730bbe94f"
SEQUENCE_CATALOG = ROOT / "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
SINGLE_RUNNER = ROOT / "tools/run_macos_mgba_battle_effect_phase_capture.py"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def prepare_case(output_root: Path, *, case: DirectSpawnCase) -> dict[str, Any]:
    case_root = Path(output_root) / case.case_id
    case_root.mkdir(parents=True, exist_ok=False)
    rom_path = case_root / "probe.gba"
    profile_path = case_root / "profile.json"
    rom_path.write_bytes(build_probe(BASE_ROM.read_bytes(), case_id=case.case_id))
    rom_sha256 = sha256_file(rom_path)
    profile = {
        "schema": "battle-effect-phase-capture-profile-v1",
        "profile_id": f"controlled-{case.case_id}",
        "group_id": case.group_id,
        "sequence_id": case.sequence_id,
        "side": case.side,
        "execution_mode": "controlled-direct-spawn",
        "input_mode": "zero-input-active-state",
        "input_state": INPUT_STATE.relative_to(ROOT).as_posix(),
        "input_state_sha256": INPUT_STATE_SHA256,
        "source_runtime_evidence": SEQUENCE_CATALOG.relative_to(ROOT).as_posix(),
        "source_runtime_evidence_sha256": sha256_file(SEQUENCE_CATALOG),
        "source_rom_sha256": rom_sha256,
        "timeout_frames": 60,
        "allocator_reset": {
            "function": "0x0807FDCC",
            "tile_start": f"0x{case.allocator_tile_start:04X}",
            "tile_end": f"0x{case.allocator_tile_end:04X}",
            "palette_start": case.allocator_palette_start,
            "palette_end": case.allocator_palette_end,
        },
        "spawn": {
            "selector": "0x0807FE2C",
            "function": f"0x{case.spawn_function:08X}",
            "side": case.side,
            "x": case.spawn_x,
            "y": case.spawn_y,
        },
        "boundary": (
            "Controlled direct-entry reconstruction. It applies the resource window, "
            "selects the statically proven sequence and calls that entry family's object "
            "spawn helper. It is not natural gameplay or pixel-A/B evidence."
        ),
    }
    _write_json(profile_path, profile)
    return {
        "case_id": case.case_id,
        "group_id": case.group_id,
        "sequence_id": case.sequence_id,
        "side": case.side,
        "case_root": case_root,
        "rom": rom_path,
        "rom_sha256": rom_sha256,
        "profile": profile_path,
        "profile_sha256": sha256_file(profile_path),
        "guard_summary": case_root / "guard-summary.json",
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
        "--guard-summary", str(case["guard_summary"]),
        "--wall-timeout-s", str(wall_timeout_s),
        "--idle-timeout-s", str(idle_timeout_s),
    ]


def select_cases(case_ids: Sequence[str] | None) -> list[DirectSpawnCase]:
    if not case_ids:
        return list(CASES)
    by_id = {case.case_id: case for case in CASES}
    try:
        return [by_id[case_id] for case_id in case_ids]
    except KeyError as error:
        raise ValueError(f"unknown direct-spawn case: {error.args[0]}") from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument("--toolchain-profile", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--case-id",
        action="append",
        choices=tuple(case.case_id for case in CASES),
        help="Run only this case; repeat to select multiple cases (default: all).",
    )
    parser.add_argument("--wall-timeout-s", type=float, default=60)
    parser.add_argument("--idle-timeout-s", type=float, default=25)
    args = parser.parse_args(argv)
    if args.wall_timeout_s <= 0 or args.idle_timeout_s <= 0:
        raise ValueError("timeouts must be positive")
    binary = args.binary.resolve(strict=True)
    toolchain = args.toolchain_profile.resolve(strict=True)
    if sha256_file(binary) != args.expected_binary_sha256:
        raise ValueError("mGBA binary hash mismatch")
    if sha256_file(INPUT_STATE) != INPUT_STATE_SHA256:
        raise ValueError("input state hash mismatch")
    output_root = args.output_root.resolve()
    if output_root.exists():
        if not output_root.is_dir() or any(output_root.iterdir()):
            raise ValueError("batch output root must be absent or empty")
    else:
        output_root.mkdir(parents=True)

    results = []
    for direct_case in select_cases(args.case_id):
        case = prepare_case(output_root, case=direct_case)
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
                f"direct-spawn case {case['case_id']} failed: "
                + (completed.stderr or completed.stdout).strip()
            )
        audit_path = case["case_root"] / "output/audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if audit.get("outcome") != "three-phase-captured":
            raise ValueError(f"direct-spawn case {case['case_id']} audit mismatch")
        results.append({
            "case_id": case["case_id"],
            "group_id": case["group_id"],
            "sequence_id": case["sequence_id"],
            "side": case["side"],
            "rom_sha256": case["rom_sha256"],
            "profile_sha256": case["profile_sha256"],
            "audit_sha256": sha256_file(audit_path),
            "guard_summary_sha256": sha256_file(case["guard_summary"]),
        })
    _write_json(output_root / "batch-audit.json", {
        "schema": "battle-effect-direct-spawn-batch-audit-v1",
        "input_state": INPUT_STATE.relative_to(ROOT).as_posix(),
        "input_state_sha256": INPUT_STATE_SHA256,
        "binary_sha256": args.expected_binary_sha256,
        "toolchain_profile": toolchain.relative_to(ROOT).as_posix(),
        "toolchain_profile_sha256": sha256_file(toolchain),
        "cases": results,
    })
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
