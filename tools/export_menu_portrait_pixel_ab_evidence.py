#!/usr/bin/env python3
"""Promote the natural menu-portrait single-pixel A/B runtime evidence."""

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

from tools.build_menu_portrait_pixel_ab import (
    AFTER_INDEX,
    BEFORE_INDEX,
    CANVAS_XY,
    PAIR_POINTER_OFFSET,
    RESOURCE_ID,
    SCHEMA as BUILD_SCHEMA,
    STREAM_BYTE_OFFSET,
    build_pair,
)
from tools.import_menu_portraits import portrait_canvas_to_stream
from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint


SCHEMA = "menu-portrait-pixel-ab-runtime-v1"
RAW_FILES = (
    "build-manifest.json",
    "baseline/audit.json",
    "baseline/frame80.png",
    "baseline/frame80.ss9",
    "baseline/guard.json",
    "baseline/portrait.png",
    "baseline/sentinel.json",
    "baseline/spec.json",
    "candidate/audit.json",
    "candidate/frame80.png",
    "candidate/frame80.ss9",
    "candidate/guard.json",
    "candidate/portrait.png",
    "candidate/sentinel.json",
    "candidate/spec.json",
)
DOMAINS = {
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "VRAM": (0x06000000, 0x18000),
    "OAM": (0x07000000, 0x400),
    "IWRAM": (0x03000000, 0x8000),
    "EWRAM": (0x02000000, 0x40000),
}
EXPECTED_DIFFERENCES = {
    "EWRAM": [0x3CC0],
    "IWRAM": [0x7F9C],
    "IO": [],
    "PRAM": [],
    "VRAM": [0x11440],
    "OAM": [],
}
EXPECTED_SCOPE = {
    "natural_show_portrait_load": True,
    "production_relocation_route": True,
    "row_1_variant_0_single_pixel": True,
    "all_311_portraits_runtime_verified": False,
    "all_portrait_transitions_runtime_verified": False,
    "physical_gba_verified": False,
}
IMPLEMENTATION_PATHS = (
    "tools/build_menu_portrait_pixel_ab.py",
    "tools/export_menu_portrait_pixel_ab_evidence.py",
    "tools/verify_menu_portrait_pixel_ab_evidence.py",
    "tools/verify_menu_portrait_writeback_audit.py",
    "tools/build_mod.py",
    "tools/image_resource_regions.py",
    "tools/patch_safety.py",
    "tools/rom_layout.py",
    "tools/import_menu_portrait_relocations.py",
    "tools/import_menu_portraits.py",
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
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("menu portrait evidence byte domains differ in size")
    return [
        index
        for index, pair in enumerate(zip(left, right))
        if pair[0] != pair[1]
    ]


def _rgb(path: Path) -> tuple[bytes, int, int]:
    with Image.open(path) as image:
        image.load()
        rgb = image.convert("RGB")
        return rgb.tobytes(), rgb.width, rgb.height


def _pixels(baseline: Path, candidate: Path) -> dict[str, Any]:
    left, width, height = _rgb(baseline)
    right, right_width, right_height = _rgb(candidate)
    if (width, height) != (240, 160) or (right_width, right_height) != (240, 160):
        raise ValueError("menu portrait runtime PNG dimensions mismatch")
    changes = []
    for index in range(width * height):
        offset = index * 3
        before = list(left[offset : offset + 3])
        after = list(right[offset : offset + 3])
        if before != after:
            changes.append(
                {
                    "x": index % width,
                    "y": index // width,
                    "before_rgb": before,
                    "after_rgb": after,
                }
            )
    if changes != [
        {
            "x": 56,
            "y": 48,
            "before_rgb": [239, 189, 165],
            "after_rgb": [222, 222, 82],
        }
    ]:
        raise ValueError("menu portrait final pixel isolation mismatch")
    return {
        "count": len(changes),
        "bbox": [56, 48, 56, 48],
        "changes": changes,
        "baseline_rgb_sha256": _sha256(left),
        "candidate_rgb_sha256": _sha256(right),
    }


def _authored_stream(path: Path) -> tuple[bytes, bytes]:
    with Image.open(path) as image:
        image.load()
        if image.mode != "P" or image.size != (80, 80):
            raise ValueError("menu portrait authored PNG contract mismatch")
        pixels = image.tobytes()
        palette = image.getpalette()
        if palette is None or len(palette) < 64 * 3:
            raise ValueError("menu portrait authored palette is missing")
    return portrait_canvas_to_stream(pixels), bytes(palette[: 64 * 3])


def _validate_audit(raw_root: Path, variant: str, build: dict[str, Any]) -> dict[str, Any]:
    audit = _json(raw_root / variant / "audit.json")
    sentinel = _json(raw_root / variant / "sentinel.json")
    guard = _json(raw_root / variant / "guard.json")
    row = build["variants"][variant]
    if audit != sentinel:
        raise ValueError(f"{variant} audit/sentinel mismatch")
    if (
        audit.get("success") is not True
        or audit.get("status") != "capture-complete"
        or audit.get("evidence_mode") != "single-input"
        or audit.get("zero_input_verified") is not False
        or audit.get("capture_frame") != 80
        or audit.get("inputs")
        != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
        or audit.get("automatic_inputs") != []
        or audit.get("recovery_inputs") != []
        or audit.get("rom_sha256") != row["rom_sha256"]
        or audit.get("input_state_sha256") != build["input_state_sha256"]
        or audit.get("output_state_sha256")
        != _sha256_file(raw_root / variant / "frame80.ss9")
        or audit.get("output_png_sha256")
        != _sha256_file(raw_root / variant / "frame80.png")
        or audit.get("guard_summary_sha256")
        != _sha256_file(raw_root / variant / "guard.json")
        or audit.get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
    ):
        raise ValueError(f"{variant} runtime audit contract mismatch")
    if (
        guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("child_pid") != audit.get("child_pgid")
        or guard.get("peak_tree_rss_mib") != audit.get("peak_tree_rss_mib")
        or not isinstance(guard.get("command"), list)
        or len(guard["command"]) != 4
        or guard["command"][1:3]
        != ["--script", audit.get("replay_script")]
    ):
        raise ValueError(f"{variant} guard contract mismatch")
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
    actual_raw = {
        path.relative_to(raw_root)
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    if actual_raw != expected_raw:
        raise ValueError("menu portrait raw evidence file set mismatch")
    if output.exists():
        extras = {path.name for path in output.iterdir()} - {"raw"}
        if extras:
            raise ValueError("menu portrait evidence output must be empty except raw")
    output.mkdir(parents=True, exist_ok=True)
    promoted_raw = output / "raw"
    if raw_root != promoted_raw:
        if promoted_raw.exists():
            raise ValueError("menu portrait promoted raw directory already exists")
        shutil.copytree(raw_root, promoted_raw)

    build = _json(raw_root / "build-manifest.json")
    if build.get("schema") != BUILD_SCHEMA:
        raise ValueError("menu portrait build manifest schema mismatch")
    with tempfile.TemporaryDirectory() as temporary:
        rebuilt_root = Path(temporary) / "build"
        rebuilt = build_pair(root, rebuilt_root)
        if rebuilt != build:
            raise ValueError("menu portrait build manifest is not reproducible")

    streams = {}
    for variant in ("baseline", "candidate"):
        stream, _ = _authored_stream(raw_root / variant / "portrait.png")
        streams[variant] = stream
        if _sha256(stream) != build["variants"][variant]["graphics_sha256"]:
            raise ValueError(f"{variant} authored graphics hash mismatch")
    if (
        _diff(streams["baseline"], streams["candidate"])
        != [STREAM_BYTE_OFFSET]
        or streams["baseline"][STREAM_BYTE_OFFSET] != BEFORE_INDEX
        or streams["candidate"][STREAM_BYTE_OFFSET] != AFTER_INDEX
    ):
        raise ValueError("menu portrait authored stream isolation mismatch")

    input_state = load_gba_state(root / build["input_state"])
    if input_state.read_u32(0x030011F0) != 0x08031F42:
        raise ValueError("menu portrait pre-load script cursor mismatch")
    rom = (root / "rom/base.gba").read_bytes()
    if rom.find(bytes.fromhex("02000100"), 0x31F42, 0x32000) != 0x31F6E:
        raise ValueError("menu portrait natural ShowPortrait command mismatch")
    if input_state.read_memory(0x06010000, 6400) in streams.values():
        raise ValueError("menu portrait input state already contains target graphics")

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
        raise ValueError("menu portrait runtime memory isolation mismatch")
    for variant in ("baseline", "candidate"):
        state = states[variant]
        if (
            state.read_memory(0x06010000, 6400) != streams[variant]
            or _sha256(state.read_memory(0x05000200, 128))
            != build["variants"][variant]["palette_sha256"]
            or render_checkpoint(raw_root / variant / "frame80.ss9")[0]
            != _rgb(raw_root / variant / "frame80.png")[0]
        ):
            raise ValueError(f"{variant} portrait runtime route mismatch")
    if states["baseline"].read_memory(0x07000008, 48) != states[
        "candidate"
    ].read_memory(0x07000008, 48):
        raise ValueError("menu portrait OAM component set changed")

    pixels = _pixels(
        raw_root / "baseline/frame80.png",
        raw_root / "candidate/frame80.png",
    )
    runs = {
        variant: _validate_audit(raw_root, variant, build)
        for variant in ("baseline", "candidate")
    }
    evidence = {
        "schema": SCHEMA,
        "verified": True,
        "input": {
            "path": build["input_state"],
            "sha256": build["input_state_sha256"],
            "script_cursor": "0x08031F42",
            "next_show_portrait_command": {
                "address": "0x08031F6E",
                "bytes": "02000100",
                "slot": 0,
                "portrait_id": 1,
                "variant": 0,
            },
            "event": {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8},
            "capture_frame": 80,
            "target_absent_before_input": True,
        },
        "edit": build["edit"],
        "runtime": {
            "memory_differences": memory_differences,
            "ewram_decompression_work_address": "0x02002880",
            "vram_graphics_address": "0x06010000",
            "pram_palette_address": "0x05000200",
            "changed_ewram_address": "0x02003CC0",
            "changed_vram_address": "0x06011440",
            "baseline_ewram_byte": states["baseline"].read_memory(0x02003CC0, 1)[0],
            "candidate_ewram_byte": states["candidate"].read_memory(0x02003CC0, 1)[0],
            "baseline_vram_byte": states["baseline"].read_memory(0x06011440, 1)[0],
            "candidate_vram_byte": states["candidate"].read_memory(0x06011440, 1)[0],
            "palette_sha256": _sha256(states["baseline"].read_memory(0x05000200, 128)),
            "oam_entries_1_through_6_hex": states["baseline"].read_memory(0x07000008, 48).hex(),
            "pixels": pixels,
            "renderer_exact": True,
        },
        "runs": runs,
        "scope": EXPECTED_SCOPE,
    }
    evidence_path = output / "runtime-evidence.json"
    _write_json(evidence_path, evidence)
    raw_hashes = {
        name: _sha256_file(raw_root / name)
        for name in RAW_FILES
    }
    implementation = {
        path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
    }
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_id": "menu-portrait-pixel-ab-v1",
        "artifact_status": "accepted",
        "base_rom_sha256": build["base_rom_sha256"],
        "parent": {
            "path": build["input_state"],
            "sha256": build["input_state_sha256"],
        },
        "source_catalog": build["source_catalog"],
        "source_catalog_sha256": build["source_catalog_sha256"],
        "payload_file": "runtime-evidence.json",
        "payload_sha256": _sha256_file(evidence_path),
        "files": {},
        "raw_files": raw_hashes,
        "implementation_sha256": implementation,
        "scope": EXPECTED_SCOPE,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_menu_portrait_pixel_ab_evidence.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/menu-portrait-pixel-ab-v1",
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
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = export_evidence(args.root, args.raw_root, args.output)
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
