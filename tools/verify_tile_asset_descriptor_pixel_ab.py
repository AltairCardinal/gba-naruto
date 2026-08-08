#!/usr/bin/env python3
"""Independently verify the descriptor-2 tile-assets runtime pixel A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
from typing import Any, Sequence

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint
BASE_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CHECKPOINT = "artifacts/runtime-checkpoints/scene-visual-controller-mode0-preselector.ss9"
CHECKPOINT_SHA256 = "6df712f69dd9cc702a77ba8ee25964d348f39cc0440a6362c7407c5321cd88cd"
PARENT_SHA256 = "6fed9fe8db43646a5a5a53901a5f0edf1c743ba5e682fd842d3fd19b12776000"
BINARY_SHA256 = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
PATCH_OFFSET = 0x5A32A8
BEFORE_POINTER = 0x0834B228
AFTER_POINTER = 0x08349E74
RAW_FILES = {
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
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def _extract_raw(archive_path: Path, output: Path) -> None:
    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()
        if {member.name for member in members} != RAW_FILES:
            raise ValueError("tile descriptor raw archive file set mismatch")
        for member in members:
            target = Path(member.name)
            if (
                not member.isfile()
                or target.is_absolute()
                or ".." in target.parts
                or member.uid != 0
                or member.gid != 0
                or member.mtime != 0
                or member.mode != 0o644
            ):
                raise ValueError("tile descriptor raw archive member mismatch")
        archive.extractall(output, filter="data")


def _guard_ok(value: dict[str, Any]) -> bool:
    return (
        value.get("reason") == "completed"
        and value.get("exit_code") == 0
        and value.get("completion_trigger") == "success-marker"
        and value.get("protection_backend") == "posix-process-group"
        and value.get("degraded") is False
        and isinstance(value.get("peak_tree_rss_mib"), (int, float))
        and value["peak_tree_rss_mib"] <= 768
    )


def _pixel_facts(left_path: Path, right_path: Path) -> dict[str, Any]:
    left_image = Image.open(left_path).convert("RGB")
    right_image = Image.open(right_path).convert("RGB")
    if left_image.size != (240, 160) or right_image.size != left_image.size:
        raise ValueError("tile descriptor PNG dimensions mismatch")
    left = left_image.tobytes()
    right = right_image.tobytes()
    changed = sum(
        left[offset : offset + 3] != right[offset : offset + 3]
        for offset in range(0, len(left), 3)
    )
    bbox = ImageChops.difference(left_image, right_image).getbbox()
    return {
        "width": 240,
        "height": 160,
        "baseline_rgb_sha256": sha256_bytes(left),
        "candidate_rgb_sha256": sha256_bytes(right),
        "changed_pixel_count": changed,
        "bbox_inclusive": None if bbox is None else [bbox[0], bbox[1], bbox[2] - 1, bbox[3] - 1],
    }


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    artifact = Path(artifact).resolve(strict=True)
    actual_files = {path.name for path in artifact.iterdir() if path.is_file()}
    if actual_files != {"baseline.png", "candidate.png", "evidence.json", "raw.tar", "manifest.json"}:
        raise ValueError("tile descriptor artifact file set mismatch")
    manifest = read_object(artifact / "manifest.json", "artifact manifest")
    evidence = read_object(artifact / "evidence.json", "runtime evidence")
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != "tile-asset-descriptor-pixel-ab-artifact-v1"
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("verifier", {}).get("exit_code") != 0
    ):
        raise ValueError("tile descriptor manifest contract mismatch")
    for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar"):
        if manifest.get("files", {}).get(name) != sha256_file(artifact / name):
            raise ValueError(f"tile descriptor artifact hash mismatch: {name}")
    for name, expected in manifest.get("implementation", {}).items():
        path = root / name
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"tile descriptor implementation hash mismatch: {name}")
    if (
        evidence.get("schema") != "tile-asset-descriptor-pixel-ab-evidence-v1"
        or evidence.get("verified") is not True
        or evidence.get("descriptor_id") != 2
        or evidence.get("consumer_id") != 3
        or evidence.get("emulator")
        != {"source_commit": "c16c3ff55585e71bee83c95539c2ecde15d728c8", "binary_sha256": BINARY_SHA256}
    ):
        raise ValueError("tile descriptor evidence contract mismatch")

    checkpoint = root / CHECKPOINT
    if sha256_file(checkpoint) != CHECKPOINT_SHA256:
        raise ValueError("tile descriptor checkpoint hash mismatch")
    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or sha256_bytes(base) != BASE_SHA256:
        raise ValueError("tile descriptor base ROM mismatch")
    before = struct.pack("<I", BEFORE_POINTER)
    after = struct.pack("<I", AFTER_POINTER)
    if base[PATCH_OFFSET : PATCH_OFFSET + 4] != before:
        raise ValueError("tile descriptor base pointer mismatch")
    candidate = bytearray(base)
    candidate[PATCH_OFFSET : PATCH_OFFSET + 4] = after
    candidate = bytes(candidate)
    changed_offsets = [
        index
        for index, pair in enumerate(zip(base, candidate, strict=True))
        if pair[0] != pair[1]
    ]
    if changed_offsets != [PATCH_OFFSET, PATCH_OFFSET + 1]:
        raise ValueError("tile descriptor reconstructed patch mismatch")

    with tempfile.TemporaryDirectory() as directory:
        raw = Path(directory) / "raw"
        raw.mkdir()
        _extract_raw(artifact / "raw.tar", raw)
        build = read_object(raw / "build/build-manifest.json", "raw build manifest")
        if (
            evidence.get("build", {}).get("manifest_sha256")
            != sha256_file(raw / "build/build-manifest.json")
            or build.get("schema") != "tile-asset-descriptor-pixel-ab-build-v1"
            or build.get("source_rom_sha256") != BASE_SHA256
            or build.get("input_state") != CHECKPOINT
            or build.get("input_state_sha256") != CHECKPOINT_SHA256
            or build.get("edit", {}).get("changed_rom_offsets") != changed_offsets
            or build.get("edit", {}).get("before_bytes") != before.hex()
            or build.get("edit", {}).get("after_bytes") != after.hex()
            or build.get("variants", {}).get("baseline", {}).get("rom_sha256") != BASE_SHA256
            or build.get("variants", {}).get("candidate", {}).get("rom_sha256") != sha256_bytes(candidate)
        ):
            raise ValueError("tile descriptor raw build mismatch")

        controller = read_object(raw / "route/controller-audit.json", "controller audit")
        initializer = read_object(raw / "route/initializer-audit.json", "initializer audit")
        controller_events = {row.get("name"): row for row in controller.get("events", [])}
        initializer_events = {row.get("name"): row for row in initializer.get("events", [])}
        if (
            controller.get("input_state_sha256") != PARENT_SHA256
            or controller.get("inputs") != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
            or controller_events.get("scene-panel-result", {}).get("r8") != "0x000000FF"
            or controller_events.get("controller-entry", {}).get("r0") != "0x00000000"
            or initializer.get("input_state_sha256") != CHECKPOINT_SHA256
            or initializer.get("outcome") != "all-boundaries-hit"
            or initializer.get("required_hit_count") != 5
            or initializer_events.get("presentation-call", {}).get("r0") != "0x00000003"
            or initializer_events.get("descriptor-selected", {}).get("descriptor_id") != 2
            or initializer_events.get("descriptor-selected", {}).get("r8") != "0x085A3294"
            or not _guard_ok(read_object(raw / "route/controller-guard.json", "controller guard"))
            or not _guard_ok(read_object(raw / "route/initializer-guard.json", "initializer guard"))
        ):
            raise ValueError("tile descriptor natural route mismatch")

        states = {}
        for variant, rom_sha in (("baseline", BASE_SHA256), ("candidate", sha256_bytes(candidate))):
            audit_path = raw / f"runs/{variant}/audit.json"
            guard_path = raw / f"runs/{variant}/guard-summary.json"
            audit = read_object(audit_path, f"{variant} audit")
            guard = read_object(guard_path, f"{variant} guard")
            run = evidence.get("runs", {}).get(variant, {})
            if (
                audit.get("capture_frame") != 100
                or audit.get("inputs") != []
                or audit.get("rom_sha256") != rom_sha
                or audit.get("input_state_sha256") != CHECKPOINT_SHA256
                or not _guard_ok(guard)
                or run.get("rom_sha256") != rom_sha
                or run.get("audit_sha256") != sha256_file(audit_path)
                or run.get("guard_sha256") != sha256_file(guard_path)
                or run.get("state_sha256") != sha256_file(raw / f"runs/{variant}/final.ss9")
                or run.get("png_sha256") != sha256_file(raw / f"runs/{variant}/final.png")
                or run.get("pgid_clean") is not True
            ):
                raise ValueError(f"tile descriptor {variant} runtime mismatch")
            states[variant] = load_gba_state(raw / f"runs/{variant}/final.ss9")
            rendered = render_checkpoint(raw / f"runs/{variant}/final.ss9")[0]
            with Image.open(raw / f"runs/{variant}/final.png") as screenshot:
                screenshot_rgb = screenshot.convert("RGB").tobytes()
            if screenshot.size != (240, 160) or screenshot_rgb != rendered:
                raise ValueError(f"tile descriptor {variant} savestate screenshot mismatch")
            if (artifact / f"{variant}.png").read_bytes() != (raw / f"runs/{variant}/final.png").read_bytes():
                raise ValueError(f"tile descriptor {variant} promoted PNG mismatch")

        expected_differences = {
            "IO": [],
            "PRAM": list(range(0x1E2, 0x200)),
            "VRAM": [],
            "OAM": [],
            "IWRAM": [],
            "EWRAM": [],
        }
        regions = (
            ("IO", 0x04000000, 0x400),
            ("PRAM", 0x05000000, 0x400),
            ("VRAM", 0x06000000, 0x18000),
            ("OAM", 0x07000000, 0x400),
            ("IWRAM", 0x03000000, 0x8000),
            ("EWRAM", 0x02000000, 0x40000),
        )
        actual_differences = {}
        for name, address, size in regions:
            left = states["baseline"].read_memory(address, size)
            right = states["candidate"].read_memory(address, size)
            actual_differences[name] = [
                index for index, pair in enumerate(zip(left, right, strict=True)) if pair[0] != pair[1]
            ]
        if actual_differences != expected_differences or evidence.get("memory", {}).get("differences") != actual_differences:
            raise ValueError("tile descriptor memory difference mismatch")
        baseline_palette = base[0x34B228 : 0x34B248]
        candidate_palette = base[0x349E74 : 0x349E94]
        if (
            states["baseline"].read_memory(0x050001E0, 32) != baseline_palette
            or states["candidate"].read_memory(0x050001E0, 32) != candidate_palette
            or evidence.get("memory", {}).get("baseline_palette_hex") != baseline_palette.hex()
            or evidence.get("memory", {}).get("candidate_palette_hex") != candidate_palette.hex()
        ):
            raise ValueError("tile descriptor palette source mismatch")

        pixels = _pixel_facts(raw / "runs/baseline/final.png", raw / "runs/candidate/final.png")
        if (
            pixels["changed_pixel_count"] != 38400
            or pixels["bbox_inclusive"] != [0, 0, 239, 159]
            or evidence.get("pixels") != pixels
        ):
            raise ValueError("tile descriptor pixel difference mismatch")

    expected_scope = {
        "natural_base_rom_route": True,
        "modified_rom_pixel_ab": True,
        "descriptor_2_layer_a_palette_pointer_runtime_verified": True,
        "other_descriptor_fields_runtime_verified": False,
        "physical_gba_verified": False,
    }
    if evidence.get("scope") != expected_scope or manifest.get("scope") != expected_scope:
        raise ValueError("tile descriptor scope mismatch")
    if evidence.get("run_budget") != {"planned": 2, "actual": 2, "blind_retries": 0}:
        raise ValueError("tile descriptor run budget mismatch")
    return {"verified": True, "descriptor_id": 2, "changed_pixel_count": 38400}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args(argv)
    result = verify_artifact(args.root, args.artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
