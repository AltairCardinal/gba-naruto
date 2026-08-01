#!/usr/bin/env python3
"""Promote the natural world-map page 0 single-pixel A/B evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.build_world_map_page0_pixel_ab import (
    AFTER_INDEX,
    BEFORE_INDEX,
    GRAPHICS_BYTE_OFFSET,
    INPUT_STATE,
    INPUT_STATE_SHA256,
    SCHEMA as BUILD_SCHEMA,
    TABLE_POINTER_OFFSET,
    build_pair,
)
from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint


SCHEMA = "world-map-page0-pixel-ab-runtime-v1"
ARTIFACT_ID = "world-map-page0-pixel-ab-v1"
RAW_FILES = (
    "build-manifest.json",
    "baseline/audit.json",
    "baseline/background.8bpp.bin",
    "baseline/frame80.png",
    "baseline/frame80.ss9",
    "baseline/guard.json",
    "baseline/sentinel.json",
    "baseline/spec.json",
    "candidate/audit.json",
    "candidate/background.8bpp.bin",
    "candidate/frame80.png",
    "candidate/frame80.ss9",
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
    "VRAM": [0x7CE4],
    "OAM": [],
}
EXPECTED_SCOPE = {
    "natural_page0_load": True,
    "production_relocation_route": True,
    "page0_graphics_single_pixel": True,
    "page1_and_page2_runtime_verified": False,
    "labels_cursor_transition_verified": False,
    "physical_gba_verified": False,
}
IMPLEMENTATION_PATHS = (
    "tools/build_world_map_page0_pixel_ab.py",
    "tools/export_world_map_page0_pixel_ab_evidence.py",
    "tools/verify_world_map_page0_pixel_ab_evidence.py",
    "tools/import_world_map_background_relocations.py",
    "tools/verify_menu_portrait_writeback_audit.py",
    "tools/extract_tileset.py",
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
        raise ValueError("world-map evidence byte lengths differ")
    return [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]


def _rgb(path: Path) -> tuple[bytes, tuple[int, int]]:
    with Image.open(path) as image:
        image.load()
        rgb = image.convert("RGB")
        return rgb.tobytes(), rgb.size


def _pixels(baseline: Path, candidate: Path) -> dict[str, Any]:
    before, size = _rgb(baseline)
    after, after_size = _rgb(candidate)
    if size != (240, 160) or after_size != size:
        raise ValueError("world-map evidence screenshot geometry mismatch")
    changes = []
    for pixel in range(size[0] * size[1]):
        offset = pixel * 3
        if before[offset : offset + 3] != after[offset : offset + 3]:
            changes.append(
                {
                    "x": pixel % size[0],
                    "y": pixel // size[0],
                    "before_rgb": list(before[offset : offset + 3]),
                    "after_rgb": list(after[offset : offset + 3]),
                }
            )
    expected = [
        {
            "x": 116,
            "y": 76,
            "before_rgb": [189, 165, 107],
            "after_rgb": [66, 33, 0],
        }
    ]
    if changes != expected:
        raise ValueError("world-map evidence final pixel isolation mismatch")
    return {
        "count": 1,
        "bbox": [116, 76, 116, 76],
        "baseline_rgb_sha256": _sha256(before),
        "candidate_rgb_sha256": _sha256(after),
        "changes": changes,
    }


def _validate_audit(
    raw: Path,
    variant: str,
    build: dict[str, Any],
) -> dict[str, Any]:
    audit = _json(raw / variant / "audit.json")
    sentinel = _json(raw / variant / "sentinel.json")
    guard_path = raw / variant / "guard.json"
    guard = _json(guard_path)
    state_path = raw / variant / "frame80.ss9"
    png_path = raw / variant / "frame80.png"
    row = build["variants"][variant]
    if (
        audit != sentinel
        or audit.get("success") is not True
        or audit.get("status") != "capture-complete"
        or audit.get("evidence_mode") != "single-input"
        or audit.get("rom_sha256") != row["rom_sha256"]
        or audit.get("input_state_sha256") != INPUT_STATE_SHA256
        or audit.get("inputs")
        != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
        or audit.get("capture_frame") != 80
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
        raise ValueError(
            f"world-map {variant} audit/sentinel or runtime provenance mismatch"
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


def export_evidence(root: Path, raw_root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    raw_root = Path(raw_root).resolve()
    output = Path(output).resolve()
    expected_raw = {Path(name) for name in RAW_FILES}
    actual_raw = {path.relative_to(raw_root) for path in raw_root.rglob("*") if path.is_file()}
    if actual_raw != expected_raw:
        raise ValueError("world-map raw evidence file set mismatch")
    if output.exists():
        extras = {path.name for path in output.iterdir()} - {"raw"}
        if extras:
            raise ValueError("world-map evidence output must be empty except raw")
    output.mkdir(parents=True, exist_ok=True)
    promoted_raw = output / "raw"
    if raw_root != promoted_raw:
        if promoted_raw.exists():
            raise ValueError("world-map promoted raw directory already exists")
        shutil.copytree(raw_root, promoted_raw)

    build = _json(raw_root / "build-manifest.json")
    if (
        build.get("schema") != BUILD_SCHEMA
        or build.get("input_state") != INPUT_STATE.as_posix()
        or build.get("input_state_sha256") != INPUT_STATE_SHA256
        or build.get("edit", {}).get("graphics_byte_offset") != GRAPHICS_BYTE_OFFSET
        or build.get("edit", {}).get("before_index") != BEFORE_INDEX
        or build.get("edit", {}).get("after_index") != AFTER_INDEX
        or build.get("edit", {}).get("table_pointer_offset") != TABLE_POINTER_OFFSET
    ):
        raise ValueError("world-map build manifest contract mismatch")
    with tempfile.TemporaryDirectory() as temporary:
        if build_pair(root, Path(temporary) / "build") != build:
            raise ValueError("world-map build manifest is not reproducible")

    graphics = {
        variant: (raw_root / variant / "background.8bpp.bin").read_bytes()
        for variant in ("baseline", "candidate")
    }
    if (
        _diff(graphics["baseline"], graphics["candidate"])
        != [GRAPHICS_BYTE_OFFSET]
        or graphics["baseline"][GRAPHICS_BYTE_OFFSET] != BEFORE_INDEX
        or graphics["candidate"][GRAPHICS_BYTE_OFFSET] != AFTER_INDEX
    ):
        raise ValueError("world-map authored graphics isolation mismatch")

    states = {
        variant: load_gba_state(raw_root / variant / "frame80.ss9")
        for variant in ("baseline", "candidate")
    }
    memory_differences = {
        name: _diff(
            states["baseline"].read_memory(address, size),
            states["candidate"].read_memory(address, size),
        )
        for name, (address, size) in DOMAINS.items()
    }
    if memory_differences != EXPECTED_DIFFERENCES:
        raise ValueError("world-map runtime memory isolation mismatch")

    palette = (root / "artifacts/world-map-backgrounds-v1/page-00/palette.bgr555.bin").read_bytes()
    tilemap = (root / "artifacts/world-map-backgrounds-v1/shared/tilemap-30x20.bin").read_bytes()
    overwrite_offsets: dict[str, list[int]] = {}
    for variant in ("baseline", "candidate"):
        state = states[variant]
        runtime_graphics = state.read_memory(0x06004000, 32768)
        overwrite_offsets[variant] = _diff(graphics[variant], runtime_graphics)
        screenblock = state.read_memory(0x06000000, 0x800)
        if (
            runtime_graphics[GRAPHICS_BYTE_OFFSET] != graphics[variant][GRAPHICS_BYTE_OFFSET]
            or state.read_memory(0x05000000, 320) != palette
            or any(
                screenblock[row * 64 : row * 64 + 60]
                != tilemap[row * 60 : row * 60 + 60]
                for row in range(20)
            )
            or int.from_bytes(state.read_memory(0x04000008, 2), "little") != 0x0086
            or render_checkpoint(raw_root / variant / "frame80.ss9")[0]
            != _rgb(raw_root / variant / "frame80.png")[0]
        ):
            raise ValueError(f"world-map {variant} natural page0 route mismatch")
    common_overwrites = overwrite_offsets["baseline"]
    if (
        common_overwrites != overwrite_offsets["candidate"]
        or common_overwrites
        or GRAPHICS_BYTE_OFFSET in common_overwrites
        or any(
            states["baseline"].read_memory(0x06004000 + offset, 1)
            != states["candidate"].read_memory(0x06004000 + offset, 1)
            for offset in common_overwrites
        )
    ):
        raise ValueError("world-map common runtime overwrite contract mismatch")

    input_state = load_gba_state(root / INPUT_STATE)
    if (
        _sha256_file(root / INPUT_STATE) != INPUT_STATE_SHA256
        or input_state.read_memory(0x06004000, 32768) in graphics.values()
        or input_state.read_memory(0x05000000, 320) == palette
    ):
        raise ValueError("world-map natural pre-load boundary mismatch")

    pixels = _pixels(
        raw_root / "baseline/frame80.png",
        raw_root / "candidate/frame80.png",
    )
    runs = {
        variant: _validate_audit(raw_root, variant, build)
        for variant in ("baseline", "candidate")
    }
    packed_overwrites = b"".join(struct.pack("<I", offset) for offset in common_overwrites)
    evidence = {
        "schema": SCHEMA,
        "verified": True,
        "input": {
            "path": INPUT_STATE.as_posix(),
            "sha256": INPUT_STATE_SHA256,
            "script_cursor": "0x08031FE7",
            "event": {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8},
            "capture_frame": 80,
            "page0_absent_before_input": True,
        },
        "edit": build["edit"],
        "runtime": {
            "memory_differences": memory_differences,
            "changed_vram_address": "0x06007CE4",
            "baseline_vram_byte": BEFORE_INDEX,
            "candidate_vram_byte": AFTER_INDEX,
            "graphics_vram_address": "0x06004000",
            "palette_pram_address": "0x05000000",
            "tilemap_vram_address": "0x06000000",
            "common_overwrite_count": len(common_overwrites),
            "common_overwrite_offsets_sha256": _sha256(packed_overwrites),
            "renderer_exact": True,
            "pixels": pixels,
        },
        "runs": runs,
        "scope": EXPECTED_SCOPE,
    }
    evidence_path = output / "runtime-evidence.json"
    _write_json(evidence_path, evidence)
    raw_hashes = {name: _sha256_file(raw_root / name) for name in RAW_FILES}
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
        "raw_files": raw_hashes,
        "implementation_sha256": {
            path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
        },
        "scope": EXPECTED_SCOPE,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_world_map_page0_pixel_ab_evidence.py",
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
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_evidence(args.root, args.raw_root, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
