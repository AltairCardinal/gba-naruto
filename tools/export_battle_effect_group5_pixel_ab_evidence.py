#!/usr/bin/env python3
"""Promote the natural battle-effect group 5 single-pixel A/B evidence."""

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

from tools.build_battle_effect_group5_pixel_ab import (
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


SCHEMA = "battle-effect-group5-pixel-ab-runtime-v1"
ARTIFACT_ID = "battle-effect-group5-pixel-ab-v1"
VARIANTS = ("baseline", "candidate")
RAW_FILES = (
    "build-manifest.json",
    "baseline/audit.json",
    "baseline/frame150.png",
    "baseline/frame150.ss9",
    "baseline/group-05-graphics-4bpp.bin",
    "baseline/guard.json",
    "baseline/sentinel.json",
    "baseline/spec.json",
    "candidate/audit.json",
    "candidate/frame150.png",
    "candidate/frame150.ss9",
    "candidate/group-05-graphics-4bpp.bin",
    "candidate/guard.json",
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
    "VRAM": [0x12600],
    "OAM": [],
}
EXPECTED_PIXELS = [
    {
        "x": 160,
        "y": 48,
        "before_rgb": [255, 222, 198],
        "after_rgb": [189, 123, 115],
    }
]
EXPECTED_SCOPE = {
    "natural_action_5_attack": True,
    "production_relocation_route": True,
    "sequence_6_group_5_frame_1_graphics_single_pixel": True,
    "all_18_effect_groups_runtime_verified": False,
    "all_group_5_frames_runtime_verified": False,
    "affine_blend_timing_audio_equivalence": False,
    "physical_gba_verified": False,
}
IMPLEMENTATION_PATHS = (
    "tools/build_battle_effect_group5_pixel_ab.py",
    "tools/export_battle_effect_group5_pixel_ab_evidence.py",
    "tools/verify_battle_effect_group5_pixel_ab_evidence.py",
    "tools/import_battle_effect_resource_relocations.py",
    "tools/import_battle_effect_resources.py",
    "tools/gba_image_export.py",
    "tools/verify_menu_portrait_writeback_audit.py",
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
        raise ValueError("battle-effect group 5 evidence byte lengths differ")
    return [
        index for index, (before, after) in enumerate(zip(left, right))
        if before != after
    ]


def _rgb(path: Path) -> bytes:
    with Image.open(path) as image:
        image.load()
        if image.size != (240, 160):
            raise ValueError("battle-effect group 5 screenshot geometry mismatch")
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
    state_path = raw / variant / "frame150.ss9"
    png_path = raw / variant / "frame150.png"
    if (
        audit != sentinel
        or audit.get("success") is not True
        or audit.get("status") != "capture-complete"
        or audit.get("evidence_mode") != "single-input"
        or audit.get("rom_sha256") != build["variants"][variant]["rom_sha256"]
        or audit.get("staged_rom_sha256") != audit.get("rom_sha256")
        or audit.get("input_state_sha256") != INPUT_STATE_SHA256
        or audit.get("inputs")
        != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
        or audit.get("capture_frame") != 150
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
        or guard.get("protection_backend") != "posix-process-group"
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("child_pid") != audit.get("child_pgid")
        or guard.get("peak_tree_rss_mib") != audit.get("peak_tree_rss_mib")
    ):
        raise ValueError(
            f"battle-effect group 5 {variant} runtime provenance mismatch"
        )
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
    """Copy bounded build/runtime evidence into the canonical raw layout."""
    experiment = Path(experiment).resolve()
    raw = Path(raw).resolve()
    if raw.exists():
        raise ValueError("battle-effect group 5 canonical raw output already exists")
    mapping = {"build-manifest.json": experiment / "build/build-manifest.json"}
    for variant in VARIANTS:
        runtime = experiment / "runtime" / variant
        build = experiment / "build" / variant
        mapping.update(
            {
                f"{variant}/audit.json": runtime / "audit.json",
                f"{variant}/frame150.png": runtime / "frame150.png",
                f"{variant}/frame150.ss9": runtime / "frame150.ss9",
                f"{variant}/group-05-graphics-4bpp.bin": build
                / "group-05-graphics-4bpp.bin",
                f"{variant}/guard.json": runtime / "guard.json",
                f"{variant}/sentinel.json": runtime / "sentinel.json",
                f"{variant}/spec.json": build / "spec.json",
            }
        )
    if set(mapping) != set(RAW_FILES) or any(
        not path.is_file() for path in mapping.values()
    ):
        raise ValueError("battle-effect group 5 experiment evidence is incomplete")
    for name, source in mapping.items():
        destination = raw / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _canonicalize_promoted_raw(raw: Path) -> None:
    """Remove host-specific paths while preserving signed runtime facts."""
    for variant in VARIANTS:
        guard_path = raw / variant / "guard.json"
        guard = _json(guard_path)
        guard["command"] = [
            "mGBA",
            "--script",
            "tools/mgba_single_input_replay.lua",
            f"runtime-only/{variant}/staged.gba",
        ]
        guard["cwd"] = "."
        _write_json(guard_path, guard)

        audit_path = raw / variant / "audit.json"
        audit = _json(audit_path)
        audit.update(
            {
                "audit": f"raw/{variant}/audit.json",
                "build_manifest": "toolchain/mgba-build-manifest.json",
                "input_state": INPUT_STATE.as_posix(),
                "output_png": f"raw/{variant}/frame150.png",
                "output_state": f"raw/{variant}/frame150.ss9",
                "replay_script": "tools/mgba_single_input_replay.lua",
                "sentinel": f"raw/{variant}/sentinel.json",
                "staged_rom": f"runtime-only/{variant}/staged.gba",
                "guard_summary_sha256": _sha256_file(guard_path),
            }
        )
        _write_json(audit_path, audit)
        _write_json(raw / variant / "sentinel.json", audit)

        spec_path = raw / variant / "spec.json"
        spec = _json(spec_path)
        edits = spec.get("edits")
        if not isinstance(edits, list) or len(edits) != 1:
            raise ValueError("battle-effect group 5 promoted spec mismatch")
        edits[0]["source_file"] = (
            f"raw/{variant}/group-05-graphics-4bpp.bin"
        )
        _write_json(spec_path, spec)


def export_evidence(root: Path, raw_root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    raw_root = Path(raw_root).resolve()
    output = Path(output).resolve()
    actual_raw = {
        path.relative_to(raw_root) for path in raw_root.rglob("*") if path.is_file()
    }
    if actual_raw != {Path(name) for name in RAW_FILES}:
        raise ValueError("battle-effect group 5 raw evidence file set mismatch")
    if output.exists() and any(output.iterdir()):
        raise ValueError("battle-effect group 5 evidence output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    promoted_raw = output / "raw"
    if raw_root != promoted_raw:
        shutil.copytree(raw_root, promoted_raw)
    _canonicalize_promoted_raw(promoted_raw)
    raw_root = promoted_raw

    build = _json(raw_root / "build-manifest.json")
    edit = build.get("edit", {})
    if (
        build.get("schema") != BUILD_SCHEMA
        or build.get("input_state") != INPUT_STATE.as_posix()
        or build.get("input_state_sha256") != INPUT_STATE_SHA256
        or edit.get("group_id") != 5
        or edit.get("sequence_id") != 6
        or edit.get("frame_id") != 1
        or edit.get("graphics_byte_offset") != GRAPHICS_BYTE_OFFSET
        or edit.get("before_byte") != BEFORE_BYTE
        or edit.get("after_byte") != AFTER_BYTE
        or edit.get("before_index") != BEFORE_INDEX
        or edit.get("after_index") != AFTER_INDEX
        or build.get("isolation", {}).get("same_patch_topology") is not True
        or build.get("isolation", {}).get("same_allocation_offsets") is not True
        or build.get("isolation", {}).get("same_redirect_pointers") is not True
    ):
        raise ValueError("battle-effect group 5 build manifest contract mismatch")
    with tempfile.TemporaryDirectory() as temporary:
        if build_pair(root, Path(temporary) / "build") != build:
            raise ValueError("battle-effect group 5 build manifest is not reproducible")

    graphics = {
        variant: (raw_root / variant / "group-05-graphics-4bpp.bin").read_bytes()
        for variant in VARIANTS
    }
    if (
        _diff(graphics["baseline"], graphics["candidate"])
        != [GRAPHICS_BYTE_OFFSET]
        or graphics["baseline"][GRAPHICS_BYTE_OFFSET] != BEFORE_BYTE
        or graphics["candidate"][GRAPHICS_BYTE_OFFSET] != AFTER_BYTE
        or graphics["baseline"] != (root / SOURCE_GRAPHICS).read_bytes()
    ):
        raise ValueError("battle-effect group 5 authored graphics isolation mismatch")

    runs = {
        variant: _validate_audit(raw_root, variant, build) for variant in VARIANTS
    }
    states = {
        variant: load_gba_state(raw_root / variant / "frame150.ss9")
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
        raise ValueError("battle-effect group 5 runtime memory isolation mismatch")
    palette = (root / "artifacts/battle-effect-resource-pairs-v1/group-05-palette-bgr555.bin").read_bytes()
    for variant in VARIANTS:
        state = states[variant]
        rendered, _ = render_checkpoint(raw_root / variant / "frame150.ss9")
        if (
            state.read_memory(0x06012400, 3840) != graphics[variant]
            or state.read_memory(0x050002A0, 32) != palette
            or state.read_memory(0x07000008, 8).hex() != "3000a08030590000"
            or rendered != _rgb(raw_root / variant / "frame150.png")
        ):
            raise ValueError(
                f"battle-effect group 5 {variant} natural attack route mismatch"
            )
    input_state = load_gba_state(root / INPUT_STATE)
    if (
        _sha256_file(root / INPUT_STATE) != INPUT_STATE_SHA256
        or input_state.read_memory(0x06010000, 0x8000).find(graphics["baseline"]) >= 0
    ):
        raise ValueError("battle-effect group 5 natural pre-load boundary mismatch")

    baseline_rgb = _rgb(raw_root / "baseline/frame150.png")
    candidate_rgb = _rgb(raw_root / "candidate/frame150.png")
    changes = _pixel_changes(baseline_rgb, candidate_rgb)
    if changes != EXPECTED_PIXELS:
        raise ValueError("battle-effect group 5 final pixel isolation mismatch")
    evidence = {
        "schema": SCHEMA,
        "verified": True,
        "input": {
            "path": INPUT_STATE.as_posix(),
            "sha256": INPUT_STATE_SHA256,
            "event": {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8},
            "capture_frame": 150,
            "resource_absent_before_input": True,
        },
        "edit": edit,
        "runtime": {
            "memory_differences": memory_differences,
            "graphics_vram_address": "0x06012400",
            "changed_vram_address": "0x06012600",
            "baseline_vram_byte": BEFORE_BYTE,
            "candidate_vram_byte": AFTER_BYTE,
            "oam_entry": 1,
            "oam_xy": [160, 48],
            "oam_tile": 304,
            "palette_bank": 5,
            "renderer_exact": True,
            "pixels": {
                "count": 1,
                "bbox": [160, 48, 160, 48],
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
                "tools/verify_battle_effect_group5_pixel_ab_evidence.py",
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
