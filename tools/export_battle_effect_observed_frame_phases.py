#!/usr/bin/env python3
"""Aggregate verified frame-phase artifacts for every currently observed effect group."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "battle-effect-observed-frame-phases-v1"
PHASE_ARTIFACTS = {
    1: Path("artifacts/battle-effect-frame-phase-group1-v1"),
    2: Path("artifacts/battle-effect-frame-phase-group2-v1"),
    3: Path("artifacts/battle-effect-frame-phase-group3-natural-v1"),
    5: Path("artifacts/battle-effect-frame-phase-group5-v1"),
    11: Path("artifacts/battle-effect-frame-phase-v1"),
    14: Path("artifacts/battle-effect-frame-phase-group14-v1"),
}
PERSISTED_OBSERVED_GROUP_IDS = [1, 2, 5, 11, 14]
NATURAL_DELAYED_EXTENSION_GROUP_IDS = [3]
PIXEL_AB_ARTIFACTS = {
    1: (Path("artifacts/battle-effect-group1-pixel-ab-v1"), "battle-effect-pixel-ab-runtime-v1"),
    3: (Path("artifacts/battle-effect-group03-natural-pixel-ab-v1"), "natural-delayed-battle-effect-pixel-ab-runtime-v1"),
    5: (Path("artifacts/battle-effect-group5-pixel-ab-v1"), "battle-effect-group5-pixel-ab-runtime-v1"),
    11: (Path("artifacts/battle-effect-group11-pixel-ab-v1"), "battle-effect-pixel-ab-runtime-v1"),
    14: (Path("artifacts/battle-effect-group14-pixel-ab-v1"), "battle-effect-pixel-ab-runtime-v1"),
    15: (Path("artifacts/battle-effect-group15-pixel-ab-v1"), "battle-effect-pixel-ab-runtime-v1"),
}
BATCH_SPEC = Path(
    "sequel/content/battle-effect-phase-capture/observed-groups-batch-v1.json"
)
OBSERVED_SOURCE = Path(
    "artifacts/battle-effect-runtime-oam-task-bindings-v1/bindings.json"
)
OBSERVED_ARTIFACT = Path("artifacts/battle-effect-runtime-oam-task-bindings-v1")
ANIMATIONS = Path("artifacts/battle-effect-sprite-animations-v1/manifest.json")
REPOSITORY_FILES = (
    "tools/export_battle_effect_observed_frame_phases.py",
    "tools/verify_battle_effect_observed_frame_phases.py",
    "tests/test_export_battle_effect_observed_frame_phases.py",
    "tests/test_verify_battle_effect_observed_frame_phases.py",
    "tools/verify_battle_effect_frame_phase.py",
    "tests/test_verify_battle_effect_frame_phase.py",
    "tools/verify_battle_effect_runtime_oam_task_bindings.py",
    "tools/verify_natural_delayed_battle_effect_pixel_ab.py",
    "tests/test_verify_battle_effect_runtime_oam_task_bindings.py",
    "tools/inspect_mgba_savestate.py",
    "tests/test_inspect_mgba_savestate.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _accepted_artifact(root: Path, relative: Path, artifact_schema: str) -> dict[str, Any]:
    manifest_path = root / relative / "manifest.json"
    manifest = _object(manifest_path)
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("artifact_schema") != artifact_schema
    ):
        raise ValueError(f"artifact is not accepted with {artifact_schema}: {relative}")
    return {
        "path": relative.as_posix(),
        "manifest_sha256": _sha256(manifest_path),
    }


def build_coverage(root: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    animations = _object(root / ANIMATIONS)
    all_groups = animations.get("group_count")
    if all_groups != 18 or len(animations.get("groups", [])) != 18:
        raise ValueError("battle-effect all-group denominator mismatch")
    observed_promotion = _accepted_artifact(
        root, OBSERVED_ARTIFACT, "battle-effect-runtime-oam-task-bindings-v1"
    )
    observed_manifest = _object(root / OBSERVED_ARTIFACT / "manifest.json")
    observed_hash = _sha256(root / OBSERVED_SOURCE)
    if observed_manifest.get("files", {}).get("bindings.json") != observed_hash:
        raise ValueError("observed task bindings are not hash-locked by the promotion")
    observed = _object(root / OBSERVED_SOURCE)
    observed_ids = observed.get("summary", {}).get("all_persisted_observed_group_ids")
    if observed_ids != PERSISTED_OBSERVED_GROUP_IDS:
        raise ValueError("persisted observed group source mismatch")
    batch = _object(root / BATCH_SPEC)
    batch_ids = [row.get("group_id") for row in batch.get("cases", [])]
    if batch_ids != [1, 2, 5, 14] or batch.get("already_promoted_group_ids") != [11]:
        raise ValueError("phase batch spec does not cover the observed group set")

    phase_rows = []
    for group_id, relative in PHASE_ARTIFACTS.items():
        row = _accepted_artifact(root, relative, "battle-effect-frame-phase-v1")
        manifest = _object(root / relative / "manifest.json")
        if manifest.get("group_id") != group_id:
            raise ValueError(f"phase artifact group mismatch: {relative}")
        phase_rows.append(
            {
                "group_id": group_id,
                **row,
                "run_id": manifest.get("run_id"),
                "input_mode": manifest.get("input_mode"),
            }
        )
    pixel_rows = [
        {"group_id": group_id, **_accepted_artifact(root, relative, schema)}
        for group_id, (relative, schema) in PIXEL_AB_ARTIFACTS.items()
    ]
    return {
        "schema": SCHEMA,
        "all_group_denominator": all_groups,
        "observed_group_denominator": len(observed_ids),
        "observed_group_ids": observed_ids,
        "natural_delayed_extension_group_ids": NATURAL_DELAYED_EXTENSION_GROUP_IDS,
        "phase_verified_group_count": len(phase_rows),
        "phase_verified_group_ids": [row["group_id"] for row in phase_rows],
        "phase_artifacts": phase_rows,
        "production_pixel_ab_group_count": len(pixel_rows),
        "production_pixel_ab_group_ids": [row["group_id"] for row in pixel_rows],
        "production_pixel_ab_artifacts": pixel_rows,
        "sources": {
            "animations": {"path": ANIMATIONS.as_posix(), "sha256": _sha256(root / ANIMATIONS)},
            "observed_task_bindings": {
                **observed_promotion,
                "payload_path": OBSERVED_SOURCE.as_posix(),
                "payload_sha256": observed_hash,
            },
            "batch_spec": {"path": BATCH_SPEC.as_posix(), "sha256": _sha256(root / BATCH_SPEC)},
        },
        "scope": {
            "all_observed_groups_have_one_verified_phase_transaction": True,
            "natural_delayed_group3_phase_transaction_included": True,
            "group2_affine_transaction_included": True,
            "all_18_groups_phase_verified": False,
            "production_pixel_ab_all_18_groups": False,
            "target_task_exclusive_oam_causality": False,
            "physical_gba_verified": False,
        },
        "boundary": (
            "Six of 18 groups have one verified global renderer/submit/ack transaction; "
            "group 3 is a natural delayed-object extension beyond the five-group persisted corpus. "
            "Groups 1, 3, 5, 11, 14 and 15 have production modified-ROM pixel A/B evidence; "
            "group 3 uses the same natural delayed-object entry as its phase artifact."
        ),
    }


def export_coverage(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("coverage artifact output must be absent or empty")
    coverage = build_coverage(root)
    output.mkdir(parents=True, exist_ok=True)
    coverage_path = output / "coverage.json"
    coverage_path.write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {"coverage.json": _sha256(coverage_path)},
        "producer": {
            "command": [
                "python3",
                "tools/export_battle_effect_observed_frame_phases.py",
                "--root",
                ".",
                "--output",
                output.relative_to(root).as_posix(),
            ],
            "repository_files": {
                relative: _sha256(root / relative) for relative in REPOSITORY_FILES
            },
        },
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    command = [
        sys.executable,
        str(root / "tools/verify_battle_effect_observed_frame_phases.py"),
        "--root",
        str(root),
        "--artifact",
        str(output),
    ]
    completed = subprocess.run(
        command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("coverage verifier did not return JSON") from error
    if completed.returncode or not result.get("verified"):
        raise ValueError((completed.stderr or completed.stdout).strip())
    manifest["verifier"] = {
        "command": [
            "python3",
            "tools/verify_battle_effect_observed_frame_phases.py",
            "--root",
            ".",
            "--artifact",
            output.relative_to(root).as_posix(),
        ],
        "exit_code": 0,
        "result": result,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return coverage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    coverage = export_coverage(args.root, args.output)
    print(json.dumps({"phase_verified_groups": coverage["phase_verified_group_count"], "all_groups": coverage["all_group_denominator"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
