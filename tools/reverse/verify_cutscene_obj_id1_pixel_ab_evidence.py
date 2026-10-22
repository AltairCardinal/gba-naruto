#!/usr/bin/env python3
"""Independently verify the natural Cutscene OBJ ID 1 pixel A/B artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.build_cutscene_obj_id1_pixel_ab import build_pair
from tools.export_cutscene_obj_id1_pixel_ab_evidence import (
    DOMAINS,
    EXPECTED_DIFFERENCES,
    EXPECTED_SCOPE,
    IMPLEMENTATION_PATHS,
    RAW_FILES,
    SCHEMA,
)
from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
INPUT_PATH = Path("artifacts/runtime-checkpoints/scenario-41-combat-popup.ss9")
INPUT_SHA256 = "01f478cfafa2796cbe1652007c16e54480d2a289d1e6f54068ace8adc970300a"
CATALOG_PATH = Path("artifacts/cutscene-obj-v1/manifest.json")
CATALOG_SHA256 = "b8e1341172decef9f07080879cd8369bc5308274d84383d5c706de72a0b781e7"
BASELINE_GRAPHICS_SHA256 = "1494d4db49423aaf026f3a1d45df4a63c70db9a0c6c7bae72621f7f7688bae0d"
CANDIDATE_GRAPHICS_SHA256 = "a3d3b365ada377ca525d5b5d1aa2a6e1ab367dfad8928dcadace54a257b2bf05"
BASELINE_ROM_SHA256 = "4da5caf8e6aedf78182b13e75829931398dfb61aee7b7f5f45cd6ec324a33c16"
CANDIDATE_ROM_SHA256 = "223b91b49f8f07eaf0fa4bf65a7281a2402f1d568d6d53f304ac0acea9cc7e4c"
EXPECTED_PIXELS = [
    {
        "x": 60,
        "y": 52,
        "before_rgb": [255, 255, 255],
        "after_rgb": [181, 181, 181],
    }
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("Cutscene OBJ verifier byte lengths differ")
    return [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]


def _rgb(path: Path) -> bytes:
    with Image.open(path) as image:
        image.load()
        if image.size != (240, 160):
            raise ValueError("Cutscene OBJ verifier screenshot geometry mismatch")
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


def _runtime_provenance(raw: Path, variant: str, build: dict[str, Any]) -> None:
    audit = _json(raw / variant / "audit.json")
    guard = _json(raw / variant / "guard.json")
    if (
        audit != _json(raw / variant / "sentinel.json")
        or audit.get("success") is not True
        or audit.get("status") != "capture-complete"
        or audit.get("evidence_mode") != "single-input"
        or audit.get("capture_frame") != 512
        or audit.get("inputs")
        != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
        or audit.get("automatic_inputs") != []
        or audit.get("recovery_inputs") != []
        or audit.get("input_state_sha256") != INPUT_SHA256
        or audit.get("rom_sha256") != build["variants"][variant]["rom_sha256"]
        or audit.get("staged_rom_sha256") != audit.get("rom_sha256")
        or audit.get("output_state_sha256")
        != _sha256_file(raw / variant / "frame512.ss9")
        or audit.get("output_png_sha256")
        != _sha256_file(raw / variant / "frame512.png")
        or audit.get("guard_summary_sha256")
        != _sha256_file(raw / variant / "guard.json")
        or audit.get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
        or guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("protection_backend") != "posix-process-group"
        or guard.get("child_pid") != audit.get("child_pgid")
        or guard.get("peak_tree_rss_mib") != audit.get("peak_tree_rss_mib")
    ):
        raise ValueError(f"Cutscene OBJ independent {variant} runtime provenance mismatch")


def _verify(root: Path, artifact: Path) -> None:
    root = root.resolve()
    artifact = artifact.resolve()
    raw = artifact / "raw"
    expected_files = {
        Path("manifest.json"),
        Path("runtime-evidence.json"),
        *(Path("raw") / name for name in RAW_FILES),
    }
    actual_files = {
        path.relative_to(artifact) for path in artifact.rglob("*") if path.is_file()
    }
    if any(path.is_symlink() for path in artifact.rglob("*")):
        raise ValueError("Cutscene OBJ artifact must not contain symlinks")
    if actual_files != expected_files:
        raise ValueError("Cutscene OBJ artifact file set mismatch")

    manifest = _json(artifact / "manifest.json")
    evidence = _json(artifact / "runtime-evidence.json")
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_id") != "cutscene-obj-id1-pixel-ab-v1"
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("base_rom_sha256") != ROM_SHA256
        or manifest.get("parent")
        != {"path": INPUT_PATH.as_posix(), "sha256": INPUT_SHA256}
        or manifest.get("source_catalog") != CATALOG_PATH.as_posix()
        or manifest.get("source_catalog_sha256") != CATALOG_SHA256
        or manifest.get("payload_file") != "runtime-evidence.json"
        or manifest.get("payload_sha256")
        != _sha256_file(artifact / "runtime-evidence.json")
        or manifest.get("scope") != EXPECTED_SCOPE
        or manifest.get("verifier", {}).get("exit_code") != 0
        or manifest.get("verifier", {}).get("result")
        != {"errors": [], "verified": True}
    ):
        raise ValueError("Cutscene OBJ manifest contract mismatch")
    expected_hashes = {
        path.relative_to(artifact).as_posix(): _sha256_file(path)
        for path in sorted(artifact.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    if manifest.get("files") != expected_hashes:
        raise ValueError("Cutscene OBJ artifact file hash mismatch")
    if manifest.get("raw_files") != {
        name: _sha256_file(raw / name) for name in RAW_FILES
    }:
        raise ValueError("Cutscene OBJ raw file hash mismatch")
    if manifest.get("implementation_sha256") != {
        path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
    }:
        raise ValueError("Cutscene OBJ implementation hash mismatch")
    if _sha256_file(root / INPUT_PATH) != INPUT_SHA256:
        raise ValueError("Cutscene OBJ input checkpoint hash mismatch")
    if _sha256_file(root / CATALOG_PATH) != CATALOG_SHA256:
        raise ValueError("Cutscene OBJ catalog hash mismatch")

    build = _json(raw / "build-manifest.json")
    if (
        build.get("base_rom_sha256") != ROM_SHA256
        or build.get("variants", {}).get("baseline", {}).get("rom_sha256")
        != BASELINE_ROM_SHA256
        or build.get("variants", {}).get("candidate", {}).get("rom_sha256")
        != CANDIDATE_ROM_SHA256
        or build.get("variants", {}).get("baseline", {}).get("encoded_graphics_size")
        != 1187
        or build.get("variants", {}).get("candidate", {}).get("encoded_graphics_size")
        != 1187
        or build.get("variants", {}).get("baseline", {}).get("graphics_allocation_offset")
        != 0xBA04C0
        or build.get("isolation", {}).get("decoded_graphics_offsets") != [82]
        or build.get("isolation", {}).get("same_patch_topology") is not True
        or build.get("isolation", {}).get("same_allocation_offsets") is not True
        or build.get("isolation", {}).get("same_redirect_pointers") is not True
    ):
        raise ValueError("Cutscene OBJ independent build contract mismatch")
    with tempfile.TemporaryDirectory() as temporary:
        if build_pair(root, Path(temporary) / "build") != build:
            raise ValueError("Cutscene OBJ independent build is not reproducible")

    graphics = {
        variant: (raw / variant / "resource_1.4bpp.bin").read_bytes()
        for variant in ("baseline", "candidate")
    }
    if (
        _sha256(graphics["baseline"]) != BASELINE_GRAPHICS_SHA256
        or _sha256(graphics["candidate"]) != CANDIDATE_GRAPHICS_SHA256
        or _diff(graphics["baseline"], graphics["candidate"]) != [82]
        or graphics["baseline"][82] != 0x11
        or graphics["candidate"][82] != 0x12
    ):
        raise ValueError("Cutscene OBJ independent graphics contract mismatch")

    for variant in ("baseline", "candidate"):
        _runtime_provenance(raw, variant, build)
    states = {
        variant: load_gba_state(raw / variant / "frame512.ss9")
        for variant in ("baseline", "candidate")
    }
    differences = {
        name: _diff(
            states["baseline"].read_memory(address, size),
            states["candidate"].read_memory(address, size),
        )
        for name, (address, size) in DOMAINS.items()
    }
    if differences != EXPECTED_DIFFERENCES:
        raise ValueError("Cutscene OBJ independent memory isolation mismatch")
    for variant in ("baseline", "candidate"):
        state = states[variant]
        rendered, _ = render_checkpoint(raw / variant / "frame512.ss9")
        if (
            state.read_memory(0x06016000, 4096) != graphics[variant]
            or state.read_memory(0x07000008, 6).hex() != "300028c000c3"
            or state.read_memory(0x05000382, 2).hex() != "ff7f"
            or state.read_memory(0x05000384, 2).hex() != "d65a"
            or rendered != _rgb(raw / variant / "frame512.png")
        ):
            raise ValueError(f"Cutscene OBJ independent {variant} route mismatch")
    pixels = _pixel_changes(
        _rgb(raw / "baseline/frame512.png"),
        _rgb(raw / "candidate/frame512.png"),
    )
    if pixels != EXPECTED_PIXELS:
        raise ValueError("Cutscene OBJ independent final pixel mismatch")
    if (
        evidence.get("schema") != SCHEMA
        or evidence.get("verified") is not True
        or evidence.get("edit") != build.get("edit")
        or evidence.get("runtime", {}).get("memory_differences") != differences
        or evidence.get("runtime", {}).get("pixels", {}).get("changes") != pixels
        or evidence.get("runtime", {}).get("renderer_exact") is not True
        or evidence.get("scope") != EXPECTED_SCOPE
    ):
        raise ValueError("Cutscene OBJ signed semantic evidence mismatch")


def verify_evidence(root: Path, artifact: Path) -> dict[str, Any]:
    try:
        _verify(Path(root), Path(artifact))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return {"errors": [str(error)], "verified": False}
    return {"errors": [], "verified": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    result = verify_evidence(args.root, args.artifact)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
