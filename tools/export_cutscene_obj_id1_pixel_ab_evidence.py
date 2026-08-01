#!/usr/bin/env python3
"""Promote the natural Cutscene OBJ ID 1 victory single-pixel A/B evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.build_cutscene_obj_id1_pixel_ab import (
    AFTER_BYTE,
    AFTER_INDEX,
    BEFORE_BYTE,
    BEFORE_INDEX,
    GRAPHICS_BYTE_OFFSET,
    INPUT_STATE,
    INPUT_STATE_SHA256,
    SCHEMA as BUILD_SCHEMA,
    SOURCE_GRAPHICS,
    build_pair,
)
from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint


SCHEMA = "cutscene-obj-id1-pixel-ab-runtime-v1"
ARTIFACT_ID = "cutscene-obj-id1-pixel-ab-v1"
VARIANTS = ("baseline", "candidate")
RAW_FILES = (
    "build-manifest.json",
    "baseline/audit.json",
    "baseline/frame512.png",
    "baseline/frame512.ss9",
    "baseline/guard.json",
    "baseline/resource_1.4bpp.bin",
    "baseline/sentinel.json",
    "baseline/spec.json",
    "candidate/audit.json",
    "candidate/frame512.png",
    "candidate/frame512.ss9",
    "candidate/guard.json",
    "candidate/resource_1.4bpp.bin",
    "candidate/sentinel.json",
    "candidate/spec.json",
)
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "IWRAM": (0x03000000, 0x8000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "VRAM": (0x06000000, 0x18000),
    "OAM": (0x07000000, 0x400),
}
EXPECTED_DIFFERENCES = {
    "EWRAM": [],
    "IWRAM": [],
    "IO": [],
    "PRAM": [],
    "VRAM": [0x16052],
    "OAM": [],
}
EXPECTED_SCOPE = {
    "natural_victory_load": True,
    "production_relocation_route": True,
    "resource_1_frame_0_graphics_single_pixel": True,
    "resources_0_2_3_runtime_verified": False,
    "all_animations_runtime_verified": False,
    "physical_gba_verified": False,
}
IMPLEMENTATION_PATHS = (
    "tools/build_cutscene_obj_id1_pixel_ab.py",
    "tools/export_cutscene_obj_id1_pixel_ab_evidence.py",
    "tools/verify_cutscene_obj_id1_pixel_ab_evidence.py",
    "tools/import_cutscene_obj_bundle_relocations.py",
    "tools/gba_image_export.py",
    "tools/build_mod.py",
    "tools/image_resource_regions.py",
    "tools/patch_safety.py",
    "tools/rom_layout.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tools/inspect_mgba_savestate.py",
    "tools/render_mode0_checkpoint.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("Cutscene OBJ evidence byte lengths differ")
    return [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]


def _rgb(path: Path) -> bytes:
    with Image.open(path) as image:
        image.load()
        if image.size != (240, 160):
            raise ValueError("Cutscene OBJ screenshot geometry mismatch")
        return image.convert("RGB").tobytes()


def _pixel_changes(left: bytes, right: bytes) -> list[dict[str, Any]]:
    changes = []
    for index in range(240 * 160):
        offset = index * 3
        before = list(left[offset : offset + 3])
        after = list(right[offset : offset + 3])
        if before != after:
            changes.append(
                {
                    "x": index % 240,
                    "y": index // 240,
                    "before_rgb": before,
                    "after_rgb": after,
                }
            )
    return changes


def _validate_audit(raw: Path, variant: str, build: dict[str, Any]) -> dict[str, Any]:
    audit = _json(raw / variant / "audit.json")
    sentinel = _json(raw / variant / "sentinel.json")
    guard_path = raw / variant / "guard.json"
    guard = _json(guard_path)
    state_path = raw / variant / "frame512.ss9"
    png_path = raw / variant / "frame512.png"
    expected_input = [
        {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
    ]
    if (
        audit != sentinel
        or audit.get("success") is not True
        or audit.get("status") != "capture-complete"
        or audit.get("evidence_mode") != "single-input"
        or audit.get("rom_sha256") != build["variants"][variant]["rom_sha256"]
        or audit.get("input_state_sha256") != INPUT_STATE_SHA256
        or audit.get("inputs") != expected_input
        or audit.get("capture_frame") != 512
        or audit.get("automatic_inputs") != []
        or audit.get("recovery_inputs") != []
        or audit.get("output_state_sha256") != _sha256_file(state_path)
        or audit.get("output_png_sha256") != _sha256_file(png_path)
        or audit.get("guard_summary_sha256") != _sha256_file(guard_path)
        or audit.get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
        or guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("child_pid") != audit.get("child_pgid")
        or guard.get("peak_tree_rss_mib") != audit.get("peak_tree_rss_mib")
    ):
        raise ValueError(f"Cutscene OBJ {variant} runtime provenance mismatch")
    return {
        "run_id": audit["run_id"],
        "rom_sha256": audit["rom_sha256"],
        "state_sha256": audit["output_state_sha256"],
        "png_sha256": audit["output_png_sha256"],
        "binary_sha256": audit["binary_sha256"],
        "build_manifest_sha256": audit["build_manifest_sha256"],
        "replay_script_sha256": audit["replay_script_sha256"],
        "guard_sha256": audit["guard_summary_sha256"],
        "child_pgid": audit["child_pgid"],
        "peak_tree_rss_mib": audit["peak_tree_rss_mib"],
        "pgid_clean": True,
    }


def collect_experiment_raw(experiment: Path, raw: Path) -> None:
    """Copy the bounded build/runtime evidence into the canonical raw layout."""
    experiment = Path(experiment).resolve()
    raw = Path(raw).resolve()
    if raw.exists():
        raise ValueError("Cutscene OBJ canonical raw output already exists")
    mapping = {"build-manifest.json": experiment / "build/build-manifest.json"}
    for variant in VARIANTS:
        runtime = experiment / "runtime" / f"{variant}-fixed"
        build = experiment / "build" / variant
        mapping.update(
            {
                f"{variant}/audit.json": runtime / "audit.json",
                f"{variant}/frame512.png": runtime / "frame512.png",
                f"{variant}/frame512.ss9": runtime / "frame512.ss9",
                f"{variant}/guard.json": runtime / "guard.json",
                f"{variant}/resource_1.4bpp.bin": build / "resource_1.4bpp.bin",
                f"{variant}/sentinel.json": runtime / "sentinel.json",
                f"{variant}/spec.json": build / "spec.json",
            }
        )
    if set(mapping) != set(RAW_FILES) or any(not path.is_file() for path in mapping.values()):
        raise ValueError("Cutscene OBJ experiment evidence is incomplete")
    for name, source in mapping.items():
        destination = raw / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def export_evidence(root: Path, raw_root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    raw_root = Path(raw_root).resolve()
    output = Path(output).resolve()
    actual_raw = {
        path.relative_to(raw_root) for path in raw_root.rglob("*") if path.is_file()
    }
    if actual_raw != {Path(name) for name in RAW_FILES}:
        raise ValueError("Cutscene OBJ raw evidence file set mismatch")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Cutscene OBJ evidence output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    promoted_raw = output / "raw"
    if raw_root != promoted_raw:
        shutil.copytree(raw_root, promoted_raw)

    build = _json(raw_root / "build-manifest.json")
    edit = build.get("edit", {})
    if (
        build.get("schema") != BUILD_SCHEMA
        or build.get("input_state") != INPUT_STATE.as_posix()
        or build.get("input_state_sha256") != INPUT_STATE_SHA256
        or edit.get("resource_id") != 1
        or edit.get("frame_id") != 0
        or edit.get("graphics_byte_offset") != GRAPHICS_BYTE_OFFSET
        or edit.get("before_byte") != BEFORE_BYTE
        or edit.get("after_byte") != AFTER_BYTE
        or edit.get("before_index") != BEFORE_INDEX
        or edit.get("after_index") != AFTER_INDEX
        or build.get("isolation", {}).get("same_patch_topology") is not True
        or build.get("isolation", {}).get("same_allocation_offsets") is not True
        or build.get("isolation", {}).get("same_redirect_pointers") is not True
    ):
        raise ValueError("Cutscene OBJ build manifest contract mismatch")
    with tempfile.TemporaryDirectory() as temporary:
        if build_pair(root, Path(temporary) / "build") != build:
            raise ValueError("Cutscene OBJ build manifest is not reproducible")

    graphics = {
        variant: (raw_root / variant / "resource_1.4bpp.bin").read_bytes()
        for variant in VARIANTS
    }
    if (
        _diff(graphics["baseline"], graphics["candidate"])
        != [GRAPHICS_BYTE_OFFSET]
        or graphics["baseline"][GRAPHICS_BYTE_OFFSET] != BEFORE_BYTE
        or graphics["candidate"][GRAPHICS_BYTE_OFFSET] != AFTER_BYTE
        or graphics["baseline"] != (root / SOURCE_GRAPHICS).read_bytes()
    ):
        raise ValueError("Cutscene OBJ authored graphics isolation mismatch")

    runs = {
        variant: _validate_audit(raw_root, variant, build) for variant in VARIANTS
    }
    states = {
        variant: load_gba_state(raw_root / variant / "frame512.ss9")
        for variant in VARIANTS
    }
    memory_differences = {
        name: _diff(
            states["baseline"].read_memory(address, size),
            states["candidate"].read_memory(address, size),
        )
        for name, (address, size) in DOMAINS.items()
    }
    if memory_differences != EXPECTED_DIFFERENCES:
        raise ValueError("Cutscene OBJ runtime memory isolation mismatch")
    for variant in VARIANTS:
        state = states[variant]
        rendered, _ = render_checkpoint(raw_root / variant / "frame512.ss9")
        if (
            state.read_memory(0x06016000, 4096) != graphics[variant]
            or rendered != _rgb(raw_root / variant / "frame512.png")
            or state.read_memory(0x07000008, 6).hex() != "300028c000c3"
            or int.from_bytes(state.read_memory(0x05000382, 2), "little") != 0x7FFF
            or int.from_bytes(state.read_memory(0x05000384, 2), "little") != 0x5AD6
        ):
            raise ValueError(f"Cutscene OBJ {variant} natural victory route mismatch")
    input_state = load_gba_state(root / INPUT_STATE)
    if (
        _sha256_file(root / INPUT_STATE) != INPUT_STATE_SHA256
        or input_state.read_memory(0x06016000, 4096) in graphics.values()
    ):
        raise ValueError("Cutscene OBJ natural pre-load boundary mismatch")

    baseline_rgb = _rgb(raw_root / "baseline/frame512.png")
    candidate_rgb = _rgb(raw_root / "candidate/frame512.png")
    changes = _pixel_changes(baseline_rgb, candidate_rgb)
    expected_changes = [
        {
            "x": 60,
            "y": 52,
            "before_rgb": [255, 255, 255],
            "after_rgb": [181, 181, 181],
        }
    ]
    if changes != expected_changes:
        raise ValueError("Cutscene OBJ final pixel isolation mismatch")
    evidence = {
        "schema": SCHEMA,
        "verified": True,
        "input": {
            "path": INPUT_STATE.as_posix(),
            "sha256": INPUT_STATE_SHA256,
            "event": {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8},
            "capture_frame": 512,
            "resource_absent_before_input": True,
        },
        "edit": edit,
        "runtime": {
            "memory_differences": memory_differences,
            "graphics_vram_address": "0x06016000",
            "changed_vram_address": "0x06016052",
            "baseline_vram_byte": BEFORE_BYTE,
            "candidate_vram_byte": AFTER_BYTE,
            "oam_entry": 1,
            "oam_xy": [40, 48],
            "oam_tile": 0x300,
            "palette_bank": 12,
            "renderer_exact": True,
            "pixels": {
                "count": 1,
                "bbox": [60, 52, 60, 52],
                "baseline_rgb_sha256": _sha256(baseline_rgb),
                "candidate_rgb_sha256": _sha256(candidate_rgb),
                "changes": changes,
            },
        },
        "runs": runs,
        "scope": EXPECTED_SCOPE,
    }
    evidence_path = output / "runtime-evidence.json"
    _write_json(evidence_path, evidence)
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_id": ARTIFACT_ID,
        "artifact_status": "accepted",
        "base_rom_sha256": build["base_rom_sha256"],
        "parent": {"path": INPUT_STATE.as_posix(), "sha256": INPUT_STATE_SHA256},
        "source_catalog": build["source_catalog"],
        "source_catalog_sha256": build["source_catalog_sha256"],
        "payload_file": "runtime-evidence.json",
        "payload_sha256": _sha256_file(evidence_path),
        "files": {},
        "raw_files": {name: _sha256_file(raw_root / name) for name in RAW_FILES},
        "implementation_sha256": {
            path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
        },
        "scope": EXPECTED_SCOPE,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_cutscene_obj_id1_pixel_ab_evidence.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
            ],
            "exit_code": 0,
            "result": {"errors": [], "verified": True},
        },
    }
    manifest["files"] = {
        path.relative_to(output).as_posix(): _sha256_file(path)
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    _write_json(output / "manifest.json", manifest)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--experiment-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.raw_root is None) == (args.experiment_root is None):
        parser.error("provide exactly one of --raw-root or --experiment-root")
    if args.experiment_root is not None:
        with tempfile.TemporaryDirectory() as temporary:
            raw = Path(temporary) / "raw"
            collect_experiment_raw(args.experiment_root, raw)
            result = export_evidence(args.root, raw, args.output)
    else:
        result = export_evidence(args.root, args.raw_root, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
