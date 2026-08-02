#!/usr/bin/env python3
"""Independently verify aggregate coverage for observed battle-effect frame phases."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from tools.verify_battle_effect_frame_phase import verify_artifact
    from tools.verify_battle_effect_group5_pixel_ab_evidence import verify_evidence as verify_group5_pixel
    from tools.verify_battle_effect_pixel_ab_evidence import verify_evidence as verify_generic_pixel
    from tools.verify_battle_effect_runtime_oam_task_bindings import verify_bindings
    from tools.verify_natural_delayed_battle_effect_pixel_ab import verify_evidence as verify_natural_pixel
except ModuleNotFoundError:
    from verify_battle_effect_frame_phase import verify_artifact
    from verify_battle_effect_group5_pixel_ab_evidence import verify_evidence as verify_group5_pixel
    from verify_battle_effect_pixel_ab_evidence import verify_evidence as verify_generic_pixel
    from verify_battle_effect_runtime_oam_task_bindings import verify_bindings
    from verify_natural_delayed_battle_effect_pixel_ab import verify_evidence as verify_natural_pixel


EXPECTED = {
    1: Path("artifacts/battle-effect-frame-phase-group1-v1"),
    2: Path("artifacts/battle-effect-frame-phase-group2-v1"),
    3: Path("artifacts/battle-effect-frame-phase-group3-natural-v1"),
    4: Path("artifacts/battle-effect-frame-phase-group4-natural-v1"),
    5: Path("artifacts/battle-effect-frame-phase-group5-v1"),
    11: Path("artifacts/battle-effect-frame-phase-v1"),
    14: Path("artifacts/battle-effect-frame-phase-group14-v1"),
    16: Path("artifacts/battle-effect-frame-phase-group16-natural-v1"),
    17: Path("artifacts/battle-effect-frame-phase-group17-natural-v1"),
    18: Path("artifacts/battle-effect-frame-phase-group18-natural-sequence-v1"),
}
PERSISTED_OBSERVED_GROUP_IDS = [1, 2, 5, 11, 14]
NATURAL_DELAYED_EXTENSION_GROUP_IDS = [3, 18]
NATURAL_CONFIRMATION_EXTENSION_GROUP_IDS = [4]
NATURAL_NINJA_TOOL_HANDLER_EXTENSION_GROUP_IDS = [16, 17]
PIXEL_AB = {
    1: (Path("artifacts/battle-effect-group1-pixel-ab-v1"), "generic"),
    2: (Path("artifacts/battle-effect-group2-pixel-ab-v1"), "generic"),
    3: (Path("artifacts/battle-effect-group03-natural-pixel-ab-v1"), "natural"),
    4: (Path("artifacts/battle-effect-group4-pixel-ab-v1"), "generic"),
    5: (Path("artifacts/battle-effect-group5-pixel-ab-v1"), "group5"),
    11: (Path("artifacts/battle-effect-group11-pixel-ab-v1"), "generic"),
    13: (Path("artifacts/battle-effect-group13-pixel-ab-v1"), "generic"),
    14: (Path("artifacts/battle-effect-group14-pixel-ab-v1"), "generic"),
    15: (Path("artifacts/battle-effect-group15-pixel-ab-v1"), "generic"),
    16: (Path("artifacts/battle-effect-group16-pixel-ab-v1"), "generic"),
    17: (Path("artifacts/battle-effect-group17-pixel-ab-v1"), "generic"),
    18: (Path("artifacts/battle-effect-group18-natural-pixel-ab-v1"), "natural"),
}
OBSERVED_ARTIFACT = Path("artifacts/battle-effect-runtime-oam-task-bindings-v1")
OBSERVED_PAYLOAD = OBSERVED_ARTIFACT / "bindings.json"
REQUIRED_REPOSITORY_FILES = {
    "tools/export_battle_effect_observed_frame_phases.py",
    "tools/verify_battle_effect_observed_frame_phases.py",
    "tests/test_export_battle_effect_observed_frame_phases.py",
    "tests/test_verify_battle_effect_observed_frame_phases.py",
    "tools/verify_battle_effect_frame_phase.py",
    "tests/test_verify_battle_effect_frame_phase.py",
    "tools/verify_battle_effect_runtime_oam_task_bindings.py",
    "tools/verify_natural_delayed_battle_effect_pixel_ab.py",
    "tests/test_verify_natural_delayed_battle_effect_pixel_ab.py",
    "tools/verify_battle_effect_pixel_ab_evidence.py",
    "tests/test_verify_battle_effect_pixel_ab_evidence.py",
    "tools/verify_battle_effect_group5_pixel_ab_evidence.py",
    "tests/test_verify_battle_effect_group5_pixel_ab_evidence.py",
    "tests/test_verify_battle_effect_runtime_oam_task_bindings.py",
    "tools/inspect_mgba_savestate.py",
    "tests/test_inspect_mgba_savestate.py",
}


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


def verify_coverage(root: Path, artifact: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    artifact = Path(artifact).resolve(strict=True)
    errors: list[str] = []
    try:
        coverage = _object(artifact / "coverage.json")
        manifest = _object(artifact / "manifest.json")
        if manifest.get("schema") != "git-artifact-promotion-v1":
            errors.append("promotion manifest schema mismatch")
        if manifest.get("artifact_schema") != "battle-effect-observed-frame-phases-v1":
            errors.append("coverage artifact schema mismatch")
        if manifest.get("artifact_status") != "accepted":
            errors.append("coverage artifact is not accepted")
        if manifest.get("files") != {"coverage.json": _sha256(artifact / "coverage.json")}:
            errors.append("coverage file hash mismatch")
        repository_files = manifest.get("producer", {}).get("repository_files", {})
        if not isinstance(repository_files, dict):
            errors.append("coverage repository hashes are missing")
            repository_files = {}
        if set(repository_files) != REQUIRED_REPOSITORY_FILES:
            errors.append("coverage repository hash lock is incomplete")
        for relative, expected_hash in repository_files.items():
            path = root / relative
            if not path.is_file() or _sha256(path) != expected_hash:
                errors.append(f"coverage repository hash mismatch: {relative}")

        animations_source = coverage.get("sources", {}).get("animations", {})
        animations_path = root / str(animations_source.get("path", ""))
        animations = _object(animations_path)
        if (
            animations.get("group_count") != 18
            or len(animations.get("groups", [])) != 18
            or _sha256(animations_path) != animations_source.get("sha256")
        ):
            errors.append("all-group animation denominator mismatch")
        observed_source = coverage.get("sources", {}).get("observed_task_bindings", {})
        expected_observed_source = {
            "path": OBSERVED_ARTIFACT.as_posix(),
            "manifest_sha256": _sha256(root / OBSERVED_ARTIFACT / "manifest.json"),
            "payload_path": OBSERVED_PAYLOAD.as_posix(),
            "payload_sha256": _sha256(root / OBSERVED_PAYLOAD),
        }
        if observed_source != expected_observed_source:
            errors.append("observed group source manifest mismatch")
        observed_manifest = _object(root / OBSERVED_ARTIFACT / "manifest.json")
        if (
            observed_manifest.get("schema") != "git-artifact-promotion-v1"
            or observed_manifest.get("artifact_status") != "accepted"
            or observed_manifest.get("artifact_schema")
            != "battle-effect-runtime-oam-task-bindings-v1"
            or observed_manifest.get("files", {}).get("bindings.json")
            != expected_observed_source["payload_sha256"]
        ):
            errors.append("observed group source promotion mismatch")
        observed_path = root / OBSERVED_PAYLOAD
        observed = _object(observed_path)
        observed_ids = observed.get("summary", {}).get("all_persisted_observed_group_ids")
        binding_verification = verify_bindings(root, observed_path)
        if (
            observed_ids != PERSISTED_OBSERVED_GROUP_IDS
            or not binding_verification.get("verified")
            or binding_verification.get("observed_group_ids")
            != PERSISTED_OBSERVED_GROUP_IDS
        ):
            errors.append("observed group source mismatch")
        batch_source = coverage.get("sources", {}).get("batch_spec", {})
        batch_path = root / str(batch_source.get("path", ""))
        batch = _object(batch_path)
        if (
            [row.get("group_id") for row in batch.get("cases", [])] != [1, 2, 5, 14]
            or batch.get("already_promoted_group_ids") != [11]
            or _sha256(batch_path) != batch_source.get("sha256")
        ):
            errors.append("phase batch denominator mismatch")

        phase_rows = coverage.get("phase_artifacts")
        if not isinstance(phase_rows, list) or len(phase_rows) != len(EXPECTED):
            errors.append("phase artifact rows are incomplete")
            phase_rows = []
        for row in phase_rows:
            group_id = row.get("group_id")
            relative = EXPECTED.get(group_id)
            if relative is None or row.get("path") != relative.as_posix():
                errors.append(f"unexpected phase artifact row: {group_id}")
                continue
            manifest_path = root / relative / "manifest.json"
            if _sha256(manifest_path) != row.get("manifest_sha256"):
                errors.append(f"phase manifest hash mismatch: {group_id}")
            result = verify_artifact(root / relative)
            if result.get("errors") or result.get("group_id") != group_id:
                errors.append(f"phase artifact verification failed: {group_id}")
        pixel_rows = coverage.get("production_pixel_ab_artifacts")
        if not isinstance(pixel_rows, list) or len(pixel_rows) != len(PIXEL_AB):
            errors.append("production pixel A/B rows are incomplete")
            pixel_rows = []
        for row in pixel_rows:
            group_id = row.get("group_id")
            entry = PIXEL_AB.get(group_id)
            relative = entry[0] if entry is not None else None
            if relative is None or row.get("path") != relative.as_posix():
                errors.append(f"unexpected pixel A/B artifact row: {group_id}")
                continue
            if _sha256(root / relative / "manifest.json") != row.get("manifest_sha256"):
                errors.append(f"pixel A/B manifest hash mismatch: {group_id}")
            verification_kind = entry[1]
            if verification_kind == "natural":
                pixel_result = verify_natural_pixel(root, root / relative)
            elif verification_kind == "group5":
                pixel_result = verify_group5_pixel(root, root / relative)
            else:
                pixel_result = verify_generic_pixel(root, root / relative)
            if not pixel_result.get("verified"):
                errors.append(f"pixel A/B verification failed: {group_id}")
        expected_scope = {
            "all_observed_groups_have_one_verified_phase_transaction": True,
            "natural_delayed_group3_phase_transaction_included": True,
            "natural_delayed_group18_phase_transaction_included": True,
            "natural_confirmation_group4_phase_transaction_included": True,
            "natural_ninja_tool_handler_group16_phase_transaction_included": True,
            "natural_ninja_tool_handler_group17_phase_transaction_included": True,
            "group2_affine_transaction_included": True,
            "all_18_groups_phase_verified": False,
            "production_pixel_ab_all_18_groups": False,
            "target_task_exclusive_oam_causality": False,
            "physical_gba_verified": False,
        }
        if coverage.get("scope") != expected_scope:
            errors.append("coverage scope mismatch")
        if (
            coverage.get("all_group_denominator") != 18
            or coverage.get("observed_group_denominator") != 5
            or coverage.get("observed_group_ids") != PERSISTED_OBSERVED_GROUP_IDS
            or coverage.get("natural_delayed_extension_group_ids")
            != NATURAL_DELAYED_EXTENSION_GROUP_IDS
            or coverage.get("natural_confirmation_extension_group_ids")
            != NATURAL_CONFIRMATION_EXTENSION_GROUP_IDS
            or coverage.get("natural_ninja_tool_handler_extension_group_ids")
            != NATURAL_NINJA_TOOL_HANDLER_EXTENSION_GROUP_IDS
            or coverage.get("phase_verified_group_count") != len(EXPECTED)
            or coverage.get("phase_verified_group_ids") != sorted(EXPECTED)
            or coverage.get("production_pixel_ab_group_count") != len(PIXEL_AB)
            or coverage.get("production_pixel_ab_group_ids") != sorted(PIXEL_AB)
        ):
            errors.append("coverage summary denominator mismatch")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "verified": not errors,
        "errors": errors,
        "phase_verified_groups": len(EXPECTED) if not errors else 0,
        "all_groups": 18,
        "production_pixel_ab_groups": len(PIXEL_AB) if not errors else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    result = verify_coverage(args.root, args.artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
