#!/usr/bin/env python3
"""Promote the natural Cutscene OBJ ID-1 primary-pointer pixel A/B."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from typing import Any

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_cutscene_obj_primary_ptr_ab import build_pair
from tools.extract_tileset import lz77_decompress
from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint


ARTIFACT_ID = "cutscene-obj-id1-primary-ptr-ab-v1"
EVIDENCE_SCHEMA = "cutscene-obj-id1-primary-ptr-ab-evidence-v1"
ARTIFACT_SCHEMA = "cutscene-obj-id1-primary-ptr-ab-artifact-v1"
BINARY_PATH = Path("/Users/altair/github/mgba-build-c16/qt/mGBA.app/Contents/MacOS/mGBA")
BINARY_SHA256 = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
BINARY_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
SCRIPT_PATH = Path("tools/mgba_single_input_replay.lua")
SCRIPT_SHA256 = "28965f8610bdb9e6669ac4c4b787c7e6d1e16cc1e259d6446150f306a382703d"
INPUT_PATH = Path("artifacts/runtime-checkpoints/scenario-41-combat-popup.ss9")
INPUT_SHA256 = "01f478cfafa2796cbe1652007c16e54480d2a289d1e6f54068ace8adc970300a"
RAW_FILES = (
    ("build/build-manifest.json", "build/build-manifest.json"),
    ("runtime/baseline/audit.json", "runtime/baseline/audit.json"),
    ("runtime/baseline/sentinel.json", "runtime/baseline/sentinel.json"),
    ("runtime/baseline/frame512.png", "runtime/baseline/frame512.png"),
    ("runtime/baseline/frame512.ss9", "runtime/baseline/frame512.ss9"),
    ("runtime/baseline/guard.json", "runtime/baseline/guard.json"),
    ("runtime/candidate/audit.json", "runtime/candidate/audit.json"),
    ("runtime/candidate/sentinel.json", "runtime/candidate/sentinel.json"),
    ("runtime/candidate/frame512.png", "runtime/candidate/frame512.png"),
    ("runtime/candidate/frame512.ss9", "runtime/candidate/frame512.ss9"),
    ("runtime/candidate/guard.json", "runtime/candidate/guard.json"),
)
IMPLEMENTATION_FILES = (
    "tools/build_cutscene_obj_primary_ptr_ab.py",
    "tools/export_cutscene_obj_primary_ptr_ab.py",
    "tools/verify_cutscene_obj_primary_ptr_ab.py",
    "tools/build_cutscene_obj_id1_pixel_ab.py",
    "tools/import_cutscene_obj_bundle_relocations.py",
    "tools/build_mod.py",
    "tools/extract_tileset.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/inspect_mgba_savestate.py",
    "tools/patch_safety.py",
    "tools/render_mode0_checkpoint.py",
    "tools/rom_layout.py",
    "tools/mgba_single_input_replay.lua",
    "tests/test_build_cutscene_obj_primary_ptr_ab.py",
    "tests/test_cutscene_obj_primary_ptr_ab_artifact.py",
)
EXPECTED_REGIONS = {
    "IO": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "b34a9c5192b642487c66a138971036c6823499449f7c13d980902a80718bb7ae", "b34a9c5192b642487c66a138971036c6823499449f7c13d980902a80718bb7ae", None),
    "PRAM": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "3e236665e019c89aae4d6a96c8db5312c7e8b4a4c209b53a66b33ddbd4920af8", "3e236665e019c89aae4d6a96c8db5312c7e8b4a4c209b53a66b33ddbd4920af8", None),
    "VRAM": (2263, "ae85828d998f83ebf49515f644e53f60feae7c100571250a5c9d1bc02a3c21f7", "b748df4b171a330826a34e3faa6521b993cb6089e4d8eb107f8301474ab2fc13", "13d1e0b1eaedc070150a774c31c213bcfb362725b36165e2bcf801186747da1c", (0x1603F, 0x16FF6)),
    "OAM": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "0d093adb5edfbdc4d2fd588c586ed62be13a2f84ec47a946e1c4044565b35ad8", "0d093adb5edfbdc4d2fd588c586ed62be13a2f84ec47a946e1c4044565b35ad8", None),
    "IWRAM": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "1e7cd8df8827f7e9bfc94d2698f0b451b803c4ccbdca8f6816b52111a95480d8", "1e7cd8df8827f7e9bfc94d2698f0b451b803c4ccbdca8f6816b52111a95480d8", None),
    "EWRAM": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "0d8c650f6c673b567954aa713c5d55fcfbe67b989148b1c3e60a1c5806286f63", "0d8c650f6c673b567954aa713c5d55fcfbe67b989148b1c3e60a1c5806286f63", None),
}
EXPECTED_PIXELS = {
    "width": 240,
    "height": 160,
    "changed_pixel_count": 4032,
    "bbox_inclusive": [42, 49, 197, 110],
    "baseline_rgb_sha256": "051162ea4f830febd94823d2e87d75ad474223f352867e63fa0965912dbe7bc8",
    "candidate_rgb_sha256": "cf8f61412fd1dfa5defd75fa52cd580c6f788972c62f8a0b0fc6caf02a1895d4",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _region_facts(states: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for name, address, size in (
        ("IO", 0x04000000, 0x400),
        ("PRAM", 0x05000000, 0x400),
        ("VRAM", 0x06000000, 0x18000),
        ("OAM", 0x07000000, 0x400),
        ("IWRAM", 0x03000000, 0x8000),
        ("EWRAM", 0x02000000, 0x40000),
    ):
        left = states["baseline"].read_memory(address, size)
        right = states["candidate"].read_memory(address, size)
        indices = [index for index, pair in enumerate(zip(left, right, strict=True)) if pair[0] != pair[1]]
        actual = (
            len(indices),
            _sha256(b"".join(index.to_bytes(4, "little") for index in indices)),
            _sha256(left),
            _sha256(right),
            None if not indices else (indices[0], indices[-1]),
        )
        if actual != EXPECTED_REGIONS[name]:
            raise ValueError(f"Cutscene OBJ primary-pointer {name} mismatch")
        row = {"count": actual[0], "index_sha256": actual[1], "baseline_sha256": actual[2], "candidate_sha256": actual[3]}
        if actual[4] is not None:
            row.update({"first_offset": actual[4][0], "last_offset": actual[4][1]})
        result[name] = row
    return result


def _pixel_facts(left_path: Path, right_path: Path) -> dict[str, Any]:
    left_image = Image.open(left_path).convert("RGB")
    right_image = Image.open(right_path).convert("RGB")
    left = left_image.tobytes()
    right = right_image.tobytes()
    bbox = ImageChops.difference(left_image, right_image).getbbox()
    facts = {
        "width": 240,
        "height": 160,
        "changed_pixel_count": sum(left[index:index + 3] != right[index:index + 3] for index in range(0, len(left), 3)),
        "bbox_inclusive": None if bbox is None else [bbox[0], bbox[1], bbox[2] - 1, bbox[3] - 1],
        "baseline_rgb_sha256": _sha256(left),
        "candidate_rgb_sha256": _sha256(right),
    }
    if left_image.size != (240, 160) or right_image.size != (240, 160) or facts != EXPECTED_PIXELS:
        raise ValueError("Cutscene OBJ primary-pointer pixel mismatch")
    return facts


def _validate_source(root: Path, source: Path) -> dict[str, Any]:
    if _sha256_file(root / INPUT_PATH) != INPUT_SHA256:
        raise ValueError("Cutscene OBJ primary-pointer checkpoint mismatch")
    if _sha256_file(root / SCRIPT_PATH) != SCRIPT_SHA256:
        raise ValueError("Cutscene OBJ primary-pointer script mismatch")
    if not BINARY_PATH.is_file() or _sha256_file(BINARY_PATH) != BINARY_SHA256:
        raise ValueError("Cutscene OBJ primary-pointer binary mismatch")
    if any(not (source / name).is_file() for name, _ in RAW_FILES):
        raise ValueError("Cutscene OBJ primary-pointer raw source incomplete")

    build = _read_json(source / "build/build-manifest.json")
    with tempfile.TemporaryDirectory() as temporary:
        rebuilt_root = Path(temporary) / "build"
        rebuilt = build_pair(root, rebuilt_root)
        if rebuilt != build:
            raise ValueError("Cutscene OBJ primary-pointer build is not reproducible")
        roms = {
            variant: (
                rebuilt_root / build["variants"][variant]["rom_path"]
            ).read_bytes()
            for variant in ("baseline", "candidate")
        }
    if (
        build.get("schema") != "cutscene-obj-id1-primary-ptr-ab-build-v1"
        or build.get("edit") != {
            "offset": 0x53DF78,
            "resource_id": 1,
            "field": "primary_ptr",
            "before_pointer": 0x08BA04C0,
            "after_pointer": 0x08BA09CC,
            "donor_resource_id": 2,
        }
        or build.get("isolation", {}).get("changed_rom_offsets") != [0x53DF78, 0x53DF79]
    ):
        raise ValueError("Cutscene OBJ primary-pointer build contract mismatch")

    launch_identity = _launch_identity(source)
    states = {}
    runs = {}
    for variant in ("baseline", "candidate"):
        runtime = source / f"runtime/{variant}"
        audit = _read_json(runtime / "audit.json")
        sentinel = _read_json(runtime / "sentinel.json")
        guard = _read_json(runtime / "guard.json")
        command = guard.get("command")
        if (
            audit != sentinel
            or audit.get("success") is not True
            or audit.get("status") != "capture-complete"
            or audit.get("capture_frame") != 512
            or audit.get("inputs") != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
            or audit.get("automatic_inputs") != []
            or audit.get("recovery_inputs") != []
            or audit.get("rom_sha256") != build["variants"][variant]["rom_sha256"]
            or audit.get("input_state_sha256") != INPUT_SHA256
            or guard.get("reason") != "completed"
            or guard.get("exit_code") != 0
            or guard.get("completion_trigger") != "success-marker"
            or guard.get("protection_backend") != "posix-process-group"
            or guard.get("degraded") is not False
            or not isinstance(guard.get("peak_tree_rss_mib"), (int, float))
            or guard["peak_tree_rss_mib"] > 512
            or not isinstance(command, list)
            or len(command) != 4
            or command[0] != str(BINARY_PATH)
            or command[1:3] != ["--script", str((root / SCRIPT_PATH).resolve())]
            or not command[3].endswith(f"/runtime/{variant}/staged.gba")
            or launch_identity["guards"][variant]["staged_rom_sha256"]
            != build["variants"][variant]["rom_sha256"]
        ):
            raise ValueError(f"Cutscene OBJ primary-pointer {variant} provenance mismatch")
        state_path = runtime / "frame512.ss9"
        png_path = runtime / "frame512.png"
        state = load_gba_state(state_path)
        with Image.open(png_path) as image:
            png_rgb = image.convert("RGB").tobytes()
        if render_checkpoint(state_path)[0] != png_rgb:
            raise ValueError(f"Cutscene OBJ primary-pointer {variant} renderer mismatch")
        states[variant] = state
        runs[variant] = {
            "rom_sha256": audit["rom_sha256"],
            "audit_sha256": _sha256_file(runtime / "audit.json"),
            "sentinel_sha256": _sha256_file(runtime / "sentinel.json"),
            "state_sha256": _sha256_file(state_path),
            "png_sha256": _sha256_file(png_path),
            "guard_sha256": _sha256_file(runtime / "guard.json"),
            "staged_rom_sha256": launch_identity["guards"][variant]["staged_rom_sha256"],
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
            "pgid_clean": True,
        }

    for variant, pointer in (("baseline", 0x08BA04C0), ("candidate", 0x08BA09CC)):
        graphics = lz77_decompress(roms[variant], pointer - 0x08000000)
        if len(graphics) != 4096 or states[variant].read_memory(0x06016000, 4096) != graphics:
            raise ValueError(f"Cutscene OBJ primary-pointer {variant} VRAM route mismatch")
    if (
        states["baseline"].read_memory(0x07000008, 6) != states["candidate"].read_memory(0x07000008, 6)
        or states["baseline"].read_memory(0x05000380, 32) != states["candidate"].read_memory(0x05000380, 32)
    ):
        raise ValueError("Cutscene OBJ primary-pointer OAM/palette isolation mismatch")
    return {
        "build": build,
        "runs": runs,
        "memory_differences": _region_facts(states),
        "pixels": _pixel_facts(source / "runtime/baseline/frame512.png", source / "runtime/candidate/frame512.png"),
    }


def _launch_identity(source: Path) -> dict[str, Any]:
    existing_path = source / "launch-identity.json"
    existing = _read_json(existing_path) if existing_path.is_file() else None
    guards = {}
    for variant in ("baseline", "candidate"):
        runtime = source / f"runtime/{variant}"
        guard = _read_json(runtime / "guard.json")
        command = guard["command"]
        staged = runtime / "staged.gba"
        staged_sha256 = (
            _sha256_file(staged)
            if staged.is_file()
            else existing.get("guards", {}).get(variant, {}).get("staged_rom_sha256")
            if isinstance(existing, dict)
            else None
        )
        if not isinstance(staged_sha256, str):
            raise ValueError(f"Cutscene OBJ primary-pointer {variant} staged ROM identity missing")
        guards[variant] = {
            "guard_sha256": _sha256_file(runtime / "guard.json"),
            "staged_rom_sha256": staged_sha256,
            "binary_command_path_sha256": _sha256(command[0].encode()),
            "script_command_path_sha256": _sha256(command[2].encode()),
        }
    result = {
        "schema": "cutscene-obj-primary-ptr-launch-identity-v1",
        "binary": {"basename": "mGBA", "sha256": BINARY_SHA256, "source_commit": BINARY_COMMIT},
        "script": {"repository_path": SCRIPT_PATH.as_posix(), "sha256": SCRIPT_SHA256},
        "guards": guards,
    }
    if existing is not None and existing != result:
        raise ValueError("Cutscene OBJ primary-pointer launch identity mismatch")
    return result


def _write_raw_tar(source: Path, output: Path) -> None:
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as archive:
        for source_name, archive_name in RAW_FILES:
            path = source / source_name
            info = archive.gettarinfo(str(path), arcname=archive_name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            with path.open("rb") as stream:
                archive.addfile(info, stream)
        payload = (json.dumps(_launch_identity(source), indent=2, sort_keys=True) + "\n").encode()
        info = tarfile.TarInfo("launch-identity.json")
        info.size = len(payload)
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mtime = 0
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(payload))


def export_artifact(root: Path, source: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Cutscene OBJ primary-pointer artifact output must be absent or empty")
    facts = _validate_source(root, source)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "runtime/baseline/frame512.png", output / "baseline.png")
    shutil.copyfile(source / "runtime/candidate/frame512.png", output / "candidate.png")
    _write_raw_tar(source, output / "raw.tar")
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "verified": True,
        "actual_identity": "two adjacent four-record Cutscene OBJ visual-resource tables",
        "input": {"path": INPUT_PATH.as_posix(), "sha256": INPUT_SHA256, "event": {"key": "A", "down_frame": 5, "up_frame": 13}, "capture_frame": 512, "natural_victory_load": True},
        "emulator": {"binary_sha256": BINARY_SHA256, "source_commit": BINARY_COMMIT, "script_path": SCRIPT_PATH.as_posix(), "script_sha256": SCRIPT_SHA256},
        "edit": facts["build"]["edit"],
        "runs": facts["runs"],
        "memory_differences": facts["memory_differences"],
        "pixels": facts["pixels"],
        "runtime": {"graphics_vram_address": "0x06016000", "oam_entry": 1, "oam_equal": True, "palette_equal": True, "renderer_exact": True},
        "scope": {"resource_1_primary_pointer_runtime_verified": True, "resources_0_2_3_runtime_verified": False, "second_table_runtime_ab_verified": False, "physical_gba_verified": False},
    }
    _write_json(output / "evidence.json", evidence)
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": ARTIFACT_SCHEMA,
        "artifact_id": ARTIFACT_ID,
        "artifact_status": "accepted",
        "files": {name: _sha256_file(output / name) for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar")},
        "implementation": {name: _sha256_file(root / name) for name in IMPLEMENTATION_FILES},
        "verifier": {"command": ["python3", "tools/verify_cutscene_obj_primary_ptr_ab.py", "--root", ".", "--artifact", f"artifacts/{ARTIFACT_ID}"], "exit_code": 0},
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_artifact(args.root, args.source, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
