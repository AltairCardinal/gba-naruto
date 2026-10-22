#!/usr/bin/env python3
"""Promote the descriptor-2 tile-assets palette-pointer runtime A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
from typing import Any, Sequence

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint
SCHEMA = "tile-asset-descriptor-pixel-ab-evidence-v1"
MANIFEST_SCHEMA = "tile-asset-descriptor-pixel-ab-artifact-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
BINARY_SHA256 = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
BINARY_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
CHECKPOINT = "artifacts/runtime-checkpoints/scene-visual-controller-mode0-preselector.ss9"
CHECKPOINT_SHA256 = "6df712f69dd9cc702a77ba8ee25964d348f39cc0440a6362c7407c5321cd88cd"
PARENT_CHECKPOINT = "artifacts/residual-wram-tilemap-runtime-v2/scene-panel-setup.ss9"
PARENT_CHECKPOINT_SHA256 = "6fed9fe8db43646a5a5a53901a5f0edf1c743ba5e682fd842d3fd19b12776000"
EXPECTED_RAW_FILES = (
    "build/build-manifest.json",
    "route/controller-audit.json",
    "route/controller-guard.json",
    "route/initializer-audit.json",
    "route/initializer-guard.json",
    "runs/baseline/audit.json",
    "runs/baseline/final.png",
    "runs/baseline/final.ss9",
    "runs/baseline/guard-summary.json",
    "runs/candidate/audit.json",
    "runs/candidate/final.png",
    "runs/candidate/final.ss9",
    "runs/candidate/guard-summary.json",
)
IMPLEMENTATION_FILES = (
    "sequel/content/tile-assets/bank.json",
    "sequel/content/tile-assets/descriptor-02-palette-pointer-pixel-ab.json",
    "artifacts/tile-assets-bg-v2/manifest.json",
    "tools/build_tile_asset_descriptor_pixel_ab.py",
    "tools/export_tile_asset_descriptor_pixel_ab.py",
    "tools/verify_tile_asset_descriptor_pixel_ab.py",
    "tools/mgba_tile_asset_initializer_trace.lua",
    "tools/mgba_checkpoint_replay.lua",
    "tools/inspect_mgba_savestate.py",
    "tools/render_mode0_checkpoint.py",
    "tests/test_render_mode0_checkpoint.py",
    "tests/test_build_tile_asset_descriptor_pixel_ab.py",
    "tests/test_mgba_tile_asset_initializer_trace_script.py",
    "tests/test_tile_asset_descriptor_pixel_ab_artifact.py",
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _region_differences(left: bytes, right: bytes) -> list[int]:
    return [index for index, pair in enumerate(zip(left, right, strict=True)) if pair[0] != pair[1]]


def _pixel_facts(baseline_path: Path, candidate_path: Path) -> dict[str, Any]:
    baseline = Image.open(baseline_path).convert("RGB")
    candidate = Image.open(candidate_path).convert("RGB")
    if baseline.size != (240, 160) or candidate.size != baseline.size:
        raise ValueError("tile descriptor runtime PNG dimensions mismatch")
    left = baseline.tobytes()
    right = candidate.tobytes()
    changed = sum(
        1
        for offset in range(0, len(left), 3)
        if left[offset : offset + 3] != right[offset : offset + 3]
    )
    bbox = ImageChops.difference(baseline, candidate).getbbox()
    if bbox is None:
        raise ValueError("tile descriptor runtime produced no pixel difference")
    return {
        "width": 240,
        "height": 160,
        "baseline_rgb_sha256": sha256_bytes(left),
        "candidate_rgb_sha256": sha256_bytes(right),
        "changed_pixel_count": changed,
        "bbox_inclusive": [bbox[0], bbox[1], bbox[2] - 1, bbox[3] - 1],
    }


def _validate_guard(guard: dict[str, Any], variant: str | None = None) -> None:
    if (
        guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("protection_backend") != "posix-process-group"
        or guard.get("degraded") is not False
        or not isinstance(guard.get("peak_tree_rss_mib"), (int, float))
        or guard["peak_tree_rss_mib"] > 768
    ):
        raise ValueError(f"tile descriptor {variant or 'route'} guard mismatch")


def _validate_source(root: Path, source: Path) -> dict[str, Any]:
    actual = tuple(
        sorted(path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_file())
    )
    if actual != EXPECTED_RAW_FILES:
        raise ValueError("tile descriptor raw source file set mismatch")
    build = read_object(source / "build/build-manifest.json", "build manifest")
    if (
        build.get("schema") != "tile-asset-descriptor-pixel-ab-build-v1"
        or build.get("descriptor_id") != 2
        or build.get("consumer_id") != 3
        or build.get("input_state") != CHECKPOINT
        or build.get("input_state_sha256") != CHECKPOINT_SHA256
        or build.get("input_mode") != "zero-input-active-state"
        or build.get("inputs") != []
        or build.get("capture_frame") != 100
    ):
        raise ValueError("tile descriptor build contract mismatch")

    controller = read_object(source / "route/controller-audit.json", "controller route audit")
    initializer = read_object(source / "route/initializer-audit.json", "initializer route audit")
    controller_events = {row.get("name"): row for row in controller.get("events", [])}
    initializer_events = {row.get("name"): row for row in initializer.get("events", [])}
    if (
        controller.get("input_state_sha256") != PARENT_CHECKPOINT_SHA256
        or controller.get("inputs") != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
        or controller.get("recovery_inputs") != []
        or controller_events.get("scene-panel-result", {}).get("r8") != "0x000000FF"
        or controller_events.get("controller-entry", {}).get("r0") != "0x00000000"
        or initializer.get("input_state_sha256") != CHECKPOINT_SHA256
        or initializer.get("input_mode") != "zero-input-active-state"
        or initializer.get("inputs") != []
        or initializer.get("outcome") != "all-boundaries-hit"
        or initializer.get("required_hit_count") != 5
        or initializer_events.get("presentation-call", {}).get("r0") != "0x00000003"
        or initializer_events.get("initializer-entry", {}).get("lr") != "0x0808C1DD"
        or initializer_events.get("descriptor-selected", {}).get("descriptor_id") != 2
        or initializer_events.get("descriptor-selected", {}).get("r8") != "0x085A3294"
    ):
        raise ValueError("tile descriptor natural route mismatch")
    _validate_guard(read_object(source / "route/controller-guard.json", "controller guard"))
    _validate_guard(read_object(source / "route/initializer-guard.json", "initializer guard"))

    runs: dict[str, Any] = {}
    states = {}
    for variant in ("baseline", "candidate"):
        row = build["variants"][variant]
        audit = read_object(source / f"runs/{variant}/audit.json", f"{variant} audit")
        guard = read_object(source / f"runs/{variant}/guard-summary.json", f"{variant} guard")
        if (
            audit.get("capture_frame") != 100
            or audit.get("inputs") != []
            or audit.get("status") != "capture-complete"
            or audit.get("rom_sha256") != row.get("rom_sha256")
            or audit.get("input_state_sha256") != CHECKPOINT_SHA256
        ):
            raise ValueError(f"tile descriptor {variant} replay mismatch")
        _validate_guard(guard, variant)
        states[variant] = load_gba_state(source / f"runs/{variant}/final.ss9")
        rendered = render_checkpoint(source / f"runs/{variant}/final.ss9")[0]
        with Image.open(source / f"runs/{variant}/final.png") as screenshot:
            screenshot_rgb = screenshot.convert("RGB").tobytes()
        if screenshot.size != (240, 160) or screenshot_rgb != rendered:
            raise ValueError(f"tile descriptor {variant} savestate screenshot mismatch")
        runs[variant] = {
            "rom_sha256": row["rom_sha256"],
            "audit_sha256": sha256_file(source / f"runs/{variant}/audit.json"),
            "guard_sha256": sha256_file(source / f"runs/{variant}/guard-summary.json"),
            "state_sha256": sha256_file(source / f"runs/{variant}/final.ss9"),
            "png_sha256": sha256_file(source / f"runs/{variant}/final.png"),
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
            "pgid_clean": True,
        }

    regions = (
        ("IO", 0x04000000, 0x400),
        ("PRAM", 0x05000000, 0x400),
        ("VRAM", 0x06000000, 0x18000),
        ("OAM", 0x07000000, 0x400),
        ("IWRAM", 0x03000000, 0x8000),
        ("EWRAM", 0x02000000, 0x40000),
    )
    differences = {}
    for name, address, size in regions:
        differences[name] = _region_differences(
            states["baseline"].read_memory(address, size),
            states["candidate"].read_memory(address, size),
        )
    expected_pram = list(range(0x1E2, 0x200))
    if differences != {"IO": [], "PRAM": expected_pram, "VRAM": [], "OAM": [], "IWRAM": [], "EWRAM": []}:
        raise ValueError("tile descriptor runtime memory attribution mismatch")

    rom = (root / "rom/base.gba").read_bytes()
    before_palette = rom[0x34B228 : 0x34B248]
    after_palette = rom[0x349E74 : 0x349E94]
    baseline_pram = states["baseline"].read_memory(0x050001E0, 32)
    candidate_pram = states["candidate"].read_memory(0x050001E0, 32)
    if baseline_pram != before_palette or candidate_pram != after_palette:
        raise ValueError("tile descriptor runtime palette source mismatch")

    pixels = _pixel_facts(
        source / "runs/baseline/final.png", source / "runs/candidate/final.png"
    )
    if pixels["changed_pixel_count"] != 38400 or pixels["bbox_inclusive"] != [0, 0, 239, 159]:
        raise ValueError("tile descriptor runtime pixel difference mismatch")
    return {
        "build": build,
        "controller": controller,
        "initializer": initializer,
        "runs": runs,
        "memory_differences": differences,
        "baseline_palette_hex": before_palette.hex(),
        "candidate_palette_hex": after_palette.hex(),
        "pixels": pixels,
    }


def _write_raw_tar(source: Path, output: Path) -> None:
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name in EXPECTED_RAW_FILES:
            path = source / name
            info = archive.gettarinfo(str(path), arcname=name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            with path.open("rb") as stream:
                archive.addfile(info, stream)


def export_artifact(root: Path, source: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("tile descriptor artifact output must be absent or empty")
    facts = _validate_source(root, source)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "runs/baseline/final.png", output / "baseline.png")
    shutil.copyfile(source / "runs/candidate/final.png", output / "candidate.png")
    _write_raw_tar(source, output / "raw.tar")
    evidence = {
        "schema": SCHEMA,
        "verified": True,
        "descriptor_id": 2,
        "consumer_id": 3,
        "natural_route": {
            "parent_checkpoint": PARENT_CHECKPOINT,
            "parent_checkpoint_sha256": PARENT_CHECKPOINT_SHA256,
            "input": {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8},
            "checkpoint": CHECKPOINT,
            "checkpoint_sha256": CHECKPOINT_SHA256,
            "controller_mode": 0,
            "selector": "0x0808C18C",
            "presentation_id": 3,
            "initializer": "0x080983B8",
            "descriptor_address": "0x085A3294",
            "zero_input_frames_to_initializer": 73,
        },
        "build": {
            "manifest_sha256": sha256_file(source / "build/build-manifest.json"),
            "edit": facts["build"]["edit"],
        },
        "emulator": {"source_commit": BINARY_COMMIT, "binary_sha256": BINARY_SHA256},
        "runs": facts["runs"],
        "memory": {
            "differences": facts["memory_differences"],
            "palette_destination": "0x050001E0",
            "palette_size": 32,
            "baseline_palette_hex": facts["baseline_palette_hex"],
            "candidate_palette_hex": facts["candidate_palette_hex"],
        },
        "pixels": facts["pixels"],
        "run_budget": {"planned": 2, "actual": 2, "blind_retries": 0},
        "scope": {
            "natural_base_rom_route": True,
            "modified_rom_pixel_ab": True,
            "descriptor_2_layer_a_palette_pointer_runtime_verified": True,
            "other_descriptor_fields_runtime_verified": False,
            "physical_gba_verified": False,
        },
    }
    write_json(output / "evidence.json", evidence)
    implementation = {name: sha256_file(root / name) for name in IMPLEMENTATION_FILES}
    files = {
        name: sha256_file(output / name)
        for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar")
    }
    manifest = {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": MANIFEST_SCHEMA,
        "artifact_status": "accepted",
        "files": files,
        "implementation": implementation,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_tile_asset_descriptor_pixel_ab.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/tile-asset-descriptor2-pixel-ab-v1",
            ],
            "exit_code": 0,
            "expected": {"verified": True},
        },
        "scope": evidence["scope"],
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = export_artifact(args.root, args.source, args.output)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
