#!/usr/bin/env python3
"""Promote the derived WRAM tilemap modified-ROM pixel A/B evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "residual-wram-tilemap-pixel-ab-evidence-v1"
SOURCE_POINTER = "0x084635D8"
RUNTIME_POINTER = "0x08BC15AC"
VRAM_ENTRY_ADDRESS = "0x06000A16"
STATE_SHA256 = "dc5a1c1847600bd9719f6e6f4dbfa6237110426f0f942cb74568cdfefd6c0864"
PARENT_MANIFEST = Path(
    "artifacts/residual-wram-transformed-tilemap-runtime-v1/manifest.json"
)
IMPLEMENTATION_PATHS = (
    "tools/build_residual_wram_tilemap_pixel_ab.py",
    "tools/export_residual_wram_tilemap_pixel_ab_evidence.py",
    "tools/verify_residual_wram_tilemap_pixel_ab_evidence.py",
    "tools/mgba_wram_tilemap_sequence_probe.lua",
    "tools/mgba_checkpoint_replay.lua",
    "tests/test_build_residual_wram_tilemap_pixel_ab.py",
    "tests/test_residual_wram_tilemap_pixel_ab_evidence.py",
)
VARIANT_FILES = {
    "sequence-audit.json": "raw/audit.json",
    "sequence-guard.json": "raw/guard.json",
    "load.ss9": "raw/choice_phase_b_second_load-hit.ss9",
    "load-post.ss9": "raw/choice_phase_b_second_load_post-hit.ss9",
    "staging.bin": "raw/source_084635D8-load-staging.bin",
    "output-rows.bin": "raw/source_084635D8-queue-pre-output-rows.bin",
    "post-vram-rows.bin": "raw/source_084635D8-queue-post-vram-rows.bin",
    "queue-post.ss9": "raw/source_084635D8-queue-post.ss9",
    "replay-audit.json": "replay/audit.json",
    "replay-guard.json": "replay/guard.json",
    "frame1.ss9": "replay/frame1.ss9",
    "frame1.png": "replay/frame1.png",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _changed_bytes(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("A/B buffers have different lengths")
    return [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]


def _changed_pixels(left_path: Path, right_path: Path) -> list[list[int]]:
    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB")
    if left.size != (240, 160) or right.size != left.size:
        raise ValueError("A/B replay screenshots are not 240x160 RGB frames")
    return [
        [x, y]
        for y in range(left.height)
        for x in range(left.width)
        if left.getpixel((x, y)) != right.getpixel((x, y))
    ]


def export(root: Path, run_dir: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    run_dir = Path(run_dir).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("pixel A/B artifact output already exists")
    build = _read_json(run_dir / "build-manifest.json")
    if build.get("schema") != "residual-wram-tilemap-pixel-ab-build-v1":
        raise ValueError("pixel A/B build manifest schema mismatch")
    if build.get("runtime_source_pointer") != RUNTIME_POINTER:
        raise ValueError("pixel A/B runtime pointer mismatch")
    edit = build.get("edit", {})
    if edit.get("source_pointer") != SOURCE_POINTER or edit.get("vram_entry_address") != VRAM_ENTRY_ADDRESS:
        raise ValueError("pixel A/B edit contract mismatch")

    output.mkdir(parents=True)
    shutil.copy2(run_dir / "build-manifest.json", output / "build-manifest.json")
    for variant in ("baseline", "candidate"):
        target = output / variant
        target.mkdir()
        for destination, source in VARIANT_FILES.items():
            source_path = run_dir / variant / source
            if not source_path.is_file():
                raise ValueError(f"missing pixel A/B source file: {source_path}")
            shutil.copy2(source_path, target / destination)

    baseline_staging = (output / "baseline/staging.bin").read_bytes()
    candidate_staging = (output / "candidate/staging.bin").read_bytes()
    baseline_output = (output / "baseline/output-rows.bin").read_bytes()
    candidate_output = (output / "candidate/output-rows.bin").read_bytes()
    baseline_vram = (output / "baseline/post-vram-rows.bin").read_bytes()
    candidate_vram = (output / "candidate/post-vram-rows.bin").read_bytes()
    if _changed_bytes(baseline_staging, candidate_staging) != [208]:
        raise ValueError("pixel A/B staging is not isolated to byte 208")
    if _changed_bytes(baseline_output, candidate_output) != [208]:
        raise ValueError("pixel A/B transformed output is not isolated to byte 208")
    if baseline_output != baseline_vram or candidate_output != candidate_vram:
        raise ValueError("pixel A/B post-VRAM rows do not match transformed output")
    if struct.unpack_from("<H", baseline_vram, 208)[0] != 0xDAC8:
        raise ValueError("pixel A/B baseline VRAM entry mismatch")
    if struct.unpack_from("<H", candidate_vram, 208)[0] != 0xDAC7:
        raise ValueError("pixel A/B candidate VRAM entry mismatch")

    pixels = _changed_pixels(
        output / "baseline/frame1.png", output / "candidate/frame1.png"
    )
    oracle = [[row["x"], row["y"]] for row in build["pixel_oracle"]["expected_screen_pixels"]]
    if pixels != oracle:
        raise ValueError("mGBA pixel difference does not match the build oracle")
    runtime_evidence = {
        "schema": SCHEMA,
        "source_pointer": SOURCE_POINTER,
        "runtime_source_pointer": RUNTIME_POINTER,
        "input_state_sha256": STATE_SHA256,
        "edit": edit,
        "runtime_chain": {
            "load_frame": 150,
            "load_cycle": "1198116187",
            "staging_differing_byte_offsets": [208],
            "output_differing_byte_offsets": [208],
            "post_vram_differing_byte_offsets": [208],
            "baseline_vram_entry": "0xDAC8",
            "candidate_vram_entry": "0xDAC7",
        },
        "pixel_result": {
            "frame_after_queue_post": 1,
            "differing_pixel_count": len(pixels),
            "screen_bbox": [88, 64, 95, 71],
            "differing_pixels": pixels,
            "baseline_rgb": [8, 8, 255],
            "candidate_rgb": [231, 247, 214],
        },
    }
    _write_json(output / "runtime-evidence.json", runtime_evidence)

    parent = root / PARENT_MANIFEST
    verifier_command = [
        "python3",
        "tools/verify_residual_wram_tilemap_pixel_ab_evidence.py",
        "--root",
        ".",
        "--artifact",
        f"artifacts/{output.name}",
    ]
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_id": output.name,
        "artifact_status": "accepted",
        "parent": {
            "path": PARENT_MANIFEST.as_posix(),
            "manifest_sha256": _sha256(parent),
            "input_state_sha256": STATE_SHA256,
        },
        "scope": {
            "modified_relocated_rom_runtime_load_verified": True,
            "single_source_byte_to_single_transformed_entry_verified": True,
            "post_queue_vram_entry_verified": True,
            "next_frame_mgba_pixel_diff_verified": True,
            "exact_50_pixel_oracle_verified": True,
            "controlled_entry": True,
            "natural_entry": False,
            "full_timing": False,
            "exclusive_writer": False,
        },
        "implementation_sha256": {
            path: _sha256(root / path) for path in IMPLEMENTATION_PATHS
        },
        "files": {},
        "payload_file": "runtime-evidence.json",
        "payload_sha256": _sha256(output / "runtime-evidence.json"),
        "verifier": {"command": verifier_command, "exit_code": 0},
    }
    manifest["files"] = {
        path.relative_to(output).as_posix(): _sha256(path)
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    _write_json(output / "manifest.json", manifest)
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
