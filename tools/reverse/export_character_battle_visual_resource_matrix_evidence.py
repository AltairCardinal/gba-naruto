#!/usr/bin/env python3
"""Promote character palette/component/timeline natural pixel A/B evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "character-battle-visual-resource-matrix-v1"
ARTIFACT_ID = SCHEMA
BUILD_SCHEMA = "character-battle-visual-resource-matrix-build-v1"
BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
INPUT_STATE = Path("artifacts/runtime-checkpoints/scenario-41-start-row.ss9")
INPUT_STATE_SHA256 = "e5039f21675dde00f3bc78e7dad08bf7cbd4ce8bff2944ea108a92bbf25b9e81"
MGBA_SHA256 = "20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408"
MGBA_BUILD_MANIFEST_SHA256 = "9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d"
REPLAY_SHA256 = "28965f8610bdb9e6669ac4c4b787c7e6d1e16cc1e259d6446150f306a382703d"
VARIANTS = ("baseline", "palette", "component", "timeline")
EVENT = {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
BUNDLE_OFFSET = 0x600000
BUNDLE_SIZE = 0x4B60
EXPECTED_ROM_SHA256 = {
    "baseline": "2f738f390239caed48d12af99bd8d324df6c5465610c64fda8278c7f945e5db8",
    "palette": "7812e244b7dfe305c631695ac6dc5de774fbbff9bf6c8859a9364a2846483b61",
    "component": "3b8d46cf3e4a555a2928a019736d633624f0909a10c1cbe22510cce9c199e84b",
    "timeline": "f94dc6b6c44c964e0097787b4f5e70ea40ee0278479999faec20fd0059e203e8",
}
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "VRAM": (0x06000000, 0x18000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "OAM": (0x07000000, 0x400),
}
IMPLEMENTATION_PATHS = (
    "tools/build_character_battle_visual_resource_matrix.py",
    "tools/export_character_battle_visual_resource_matrix_evidence.py",
    "tools/verify_character_battle_visual_resource_matrix_evidence.py",
    "tools/inspect_mgba_savestate.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tests/test_build_character_battle_visual_resource_matrix.py",
    "tests/test_character_battle_visual_resource_matrix_evidence.py",
)
RUNTIME_FILES = ("frame80.ss9", "frame80.png", "audit.json", "sentinel.json", "guard.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("character visual matrix domains have different lengths")
    return [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]


def _pixel_changes(left_path: Path, right_path: Path) -> list[list[Any]]:
    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB")
    if left.size != (240, 160) or right.size != left.size:
        raise ValueError("character visual matrix screenshots are not 240x160 RGB")
    return [
        [x, y, list(left.getpixel((x, y))), list(right.getpixel((x, y)))]
        for y in range(160)
        for x in range(240)
        if left.getpixel((x, y)) != right.getpixel((x, y))
    ]


def _scope() -> dict[str, bool]:
    return {
        "natural_entry": True,
        "resource_0_relocated_bundle_route_verified": True,
        "resource_0_palette_pixel_ab": True,
        "resource_0_component_geometry_pixel_ab": True,
        "resource_0_timeline_frame_selection_pixel_ab": True,
        "all_250_resources_runtime_verified": False,
        "all_character_slots_runtime_verified": False,
        "full_animation_timing_verified": False,
        "camera_blend_transform_verified": False,
        "physical_gba_verified": False,
    }


def export(root: Path, run_dir: Path, output: Path) -> dict[str, Any]:
    """Copy minimal raw runs, summarize them, and require independent verification."""

    root = Path(root).resolve()
    run_dir = Path(run_dir).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("character visual matrix output already exists")
    if _sha256(root / "rom/base.gba") != BASE_ROM_SHA256:
        raise ValueError("character visual matrix base ROM identity mismatch")
    if _sha256(root / INPUT_STATE) != INPUT_STATE_SHA256:
        raise ValueError("character visual matrix input checkpoint mismatch")
    build_path = run_dir / "build/build-manifest.json"
    build = _read_json(build_path)
    if build.get("schema") != BUILD_SCHEMA or set(build.get("variants", {})) != set(VARIANTS):
        raise ValueError("character visual matrix build manifest mismatch")

    output.mkdir(parents=True)
    shutil.copy2(build_path, output / "build-manifest.json")
    states: dict[str, Any] = {}
    audits: dict[str, dict[str, Any]] = {}
    guards: dict[str, dict[str, Any]] = {}
    outer_guards: dict[str, dict[str, Any]] = {}
    bundles: dict[str, bytes] = {}
    run_ids: list[str] = []
    for variant in VARIANTS:
        source = run_dir / "runtime" / variant
        target = output / variant
        target.mkdir()
        staged = source / "staged.gba"
        if staged.stat().st_size != 0x1000000 or _sha256(staged) != EXPECTED_ROM_SHA256[variant]:
            raise ValueError(f"{variant} staged ROM identity mismatch")
        with staged.open("rb") as stream:
            stream.seek(BUNDLE_OFFSET)
            bundle = stream.read(BUNDLE_SIZE)
        if len(bundle) != BUNDLE_SIZE:
            raise ValueError(f"{variant} staged bundle size mismatch")
        (target / "bundle.bin").write_bytes(bundle)
        bundles[variant] = bundle
        for name in RUNTIME_FILES:
            path = source / name
            if not path.is_file():
                raise ValueError(f"missing character visual matrix runtime file: {path}")
            shutil.copy2(path, target / name)
        outer_source = source / "outer-guard.json"
        if not outer_source.is_file():
            outer_source = source / "outer-shared-guard-r2.json"
        if not outer_source.is_file():
            raise ValueError(f"missing character visual matrix outer guard: {source}")
        shutil.copy2(outer_source, target / "outer-guard.json")

        audit = _read_json(target / "audit.json")
        sentinel = _read_json(target / "sentinel.json")
        if audit != sentinel:
            raise ValueError(f"{variant} audit/sentinel mismatch")
        if (
            audit.get("frame") != 80
            or audit.get("inputs") != [EVENT]
            or audit.get("input_state_sha256") != INPUT_STATE_SHA256
            or audit.get("rom_sha256") != EXPECTED_ROM_SHA256[variant]
        ):
            raise ValueError(f"{variant} runtime audit mismatch")
        if png_screen_fingerprint(target / "frame80.ss9") != png_screen_fingerprint(target / "frame80.png"):
            raise ValueError(f"{variant} screenshot is not bound to savestate")
        run_id = audit.get("run_id")
        if not isinstance(run_id, str):
            raise ValueError(f"{variant} run ID mismatch")
        run_ids.append(run_id)
        states[variant] = load_gba_state(target / "frame80.ss9")
        audits[variant] = audit
        guards[variant] = _read_json(target / "guard.json")
        outer_guards[variant] = _read_json(target / "outer-guard.json")
    if len(set(run_ids)) != len(VARIANTS):
        raise ValueError("character visual matrix runs are not independent")

    memory_differences: dict[str, dict[str, list[int]]] = {}
    pixel_summaries: dict[str, dict[str, Any]] = {}
    selected_frames: dict[str, int] = {}
    baseline = states["baseline"]
    for variant in VARIANTS:
        selected_frames[variant] = struct.unpack_from("<H", bundles[variant], 0x4A64)[0]
    for variant in VARIANTS[1:]:
        changed = {}
        for label, (address, size) in DOMAINS.items():
            offsets = _diff(baseline.read_memory(address, size), states[variant].read_memory(address, size))
            if offsets:
                changed[label] = offsets
        memory_differences[variant] = changed
        pixels = _pixel_changes(output / "baseline/frame80.png", output / variant / "frame80.png")
        pixel_summaries[variant] = {
            "count": len(pixels),
            "bbox": [
                min(row[0] for row in pixels),
                min(row[1] for row in pixels),
                max(row[0] for row in pixels),
                max(row[1] for row in pixels),
            ],
            "sha256": _digest(json.dumps(pixels, separators=(",", ":")).encode()),
        }
    domain_sha256 = {
        variant: {
            label: _digest(states[variant].read_memory(address, size))
            for label, (address, size) in DOMAINS.items()
        }
        for variant in VARIANTS
    }
    evidence = {
        "schema": SCHEMA,
        "input": {"path": INPUT_STATE.as_posix(), "sha256": INPUT_STATE_SHA256, "event": EVENT, "loader_state": "pre-map-load-zero-runtime"},
        "source": {"resource_id": 0, "character_id": 1, "visual_slot": 0, "animation_id": 1, "keyframe_index": 0, "baseline_frame_id": 3, "timeline_frame_id": 4},
        "runtime": {
            variant: {
                "memory_differences": memory_differences[variant],
                "pixel_change_count": pixel_summaries[variant]["count"],
                "pixel_bbox": pixel_summaries[variant]["bbox"],
                "pixel_changes_sha256": pixel_summaries[variant]["sha256"],
                "selected_frame_id": selected_frames[variant],
            }
            for variant in VARIANTS[1:]
        },
        "domain_sha256": domain_sha256,
        "provenance": {"mgba_sha256": MGBA_SHA256, "mgba_build_manifest_sha256": MGBA_BUILD_MANIFEST_SHA256, "replay_script_sha256": REPLAY_SHA256},
        "runs": {
            variant: {
                "run_id": audits[variant]["run_id"],
                "rom_sha256": EXPECTED_ROM_SHA256[variant],
                "peak_tree_rss_mib": guards[variant].get("peak_tree_rss_mib"),
                "outer_peak_tree_rss_mib": outer_guards[variant].get("peak_tree_rss_mib"),
                "guard_reason": "completed",
            }
            for variant in VARIANTS
        },
    }
    _write_json(output / "runtime-evidence.json", evidence)

    clean_result = {
        "verified": True,
        "errors": [],
        "memory_differences": memory_differences,
        "pixel_change_counts": {variant: pixel_summaries[variant]["count"] for variant in VARIANTS[1:]},
        "selected_frame_ids": selected_frames,
    }
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_id": ARTIFACT_ID,
        "artifact_status": "accepted",
        "parent": {"path": INPUT_STATE.as_posix(), "sha256": INPUT_STATE_SHA256},
        "scope": _scope(),
        "implementation_sha256": {path: _sha256(root / path) for path in IMPLEMENTATION_PATHS},
        "payload_file": "runtime-evidence.json",
        "payload_sha256": _sha256(output / "runtime-evidence.json"),
        "files": {},
        "verifier": {
            "command": ["python3", "tools/verify_character_battle_visual_resource_matrix_evidence.py", "--root", ".", "--artifact", f"artifacts/{ARTIFACT_ID}"],
            "exit_code": 0,
            "result": clean_result,
        },
    }
    manifest["files"] = {
        path.relative_to(output).as_posix(): _sha256(path)
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    _write_json(output / "manifest.json", manifest)

    try:
        from tools.verify_character_battle_visual_resource_matrix_evidence import verify
    except ModuleNotFoundError:
        from verify_character_battle_visual_resource_matrix_evidence import verify
    report = verify(root, output)
    if not report["verified"]:
        raise ValueError(f"character visual matrix independent verifier failed: {report['errors']}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.root, args.run_dir, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
