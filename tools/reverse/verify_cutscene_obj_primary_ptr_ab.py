#!/usr/bin/env python3
"""Independently verify the natural Cutscene OBJ primary-pointer A/B artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from typing import Any

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_cutscene_obj_primary_ptr_ab import build_pair
from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint


ARTIFACT_ID = "cutscene-obj-id1-primary-ptr-ab-v1"
BINARY_SHA256 = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
SCRIPT_PATH = Path("tools/mgba_single_input_replay.lua")
SCRIPT_SHA256 = "28965f8610bdb9e6669ac4c4b787c7e6d1e16cc1e259d6446150f306a382703d"
INPUT_PATH = Path("artifacts/runtime-checkpoints/scenario-41-combat-popup.ss9")
INPUT_SHA256 = "01f478cfafa2796cbe1652007c16e54480d2a289d1e6f54068ace8adc970300a"
RAW_FILES = {
    "build/build-manifest.json",
    "runtime/baseline/audit.json",
    "runtime/baseline/sentinel.json",
    "runtime/baseline/frame512.png",
    "runtime/baseline/frame512.ss9",
    "runtime/baseline/guard.json",
    "runtime/candidate/audit.json",
    "runtime/candidate/sentinel.json",
    "runtime/candidate/frame512.png",
    "runtime/candidate/frame512.ss9",
    "runtime/candidate/guard.json",
    "launch-identity.json",
}
IMPLEMENTATION_FILES = {
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
}
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


def _extract_raw(archive_path: Path, output: Path) -> None:
    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()
        if {member.name for member in members} != RAW_FILES:
            raise ValueError("Cutscene OBJ primary-pointer raw file set mismatch")
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
                raise ValueError("Cutscene OBJ primary-pointer raw member mismatch")
        archive.extractall(output, filter="data")


def _lz77(rom: bytes, pointer: int) -> bytes:
    cursor = pointer - 0x08000000
    if not 0 <= cursor < len(rom) or rom[cursor] != 0x10:
        raise ValueError("Cutscene OBJ primary-pointer LZ77 source mismatch")
    size = int.from_bytes(rom[cursor + 1:cursor + 4], "little")
    cursor += 4
    output = bytearray()
    while len(output) < size:
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(output) >= size:
                break
            if flags & (1 << bit):
                pair = (rom[cursor] << 8) | rom[cursor + 1]
                cursor += 2
                length = (pair >> 12) + 3
                distance = (pair & 0xFFF) + 1
                if distance > len(output):
                    raise ValueError("Cutscene OBJ primary-pointer LZ77 backreference mismatch")
                for _ in range(length):
                    output.append(output[-distance])
                    if len(output) >= size:
                        break
            else:
                output.append(rom[cursor])
                cursor += 1
    return bytes(output)


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
        actual = (len(indices), _sha256(b"".join(index.to_bytes(4, "little") for index in indices)), _sha256(left), _sha256(right), None if not indices else (indices[0], indices[-1]))
        if actual != EXPECTED_REGIONS[name]:
            raise ValueError(f"Cutscene OBJ primary-pointer {name} attribution mismatch")
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
        raise ValueError("Cutscene OBJ primary-pointer final pixels mismatch")
    return facts


def _verify(root: Path, artifact: Path, binary: Path | None) -> None:
    root = root.resolve(strict=True)
    artifact = artifact.resolve(strict=True)
    if {path.name for path in artifact.iterdir() if path.is_file()} != {"baseline.png", "candidate.png", "evidence.json", "manifest.json", "raw.tar"}:
        raise ValueError("Cutscene OBJ primary-pointer artifact file set mismatch")
    manifest = _read_json(artifact / "manifest.json")
    evidence = _read_json(artifact / "evidence.json")
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != "cutscene-obj-id1-primary-ptr-ab-artifact-v1"
        or manifest.get("artifact_id") != ARTIFACT_ID
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("verifier") != {"command": ["python3", "tools/verify_cutscene_obj_primary_ptr_ab.py", "--root", ".", "--artifact", f"artifacts/{ARTIFACT_ID}"], "exit_code": 0}
    ):
        raise ValueError("Cutscene OBJ primary-pointer manifest contract mismatch")
    for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar"):
        if manifest.get("files", {}).get(name) != _sha256_file(artifact / name):
            raise ValueError(f"Cutscene OBJ primary-pointer artifact hash mismatch: {name}")
    implementation = manifest.get("implementation")
    if not isinstance(implementation, dict) or set(implementation) != IMPLEMENTATION_FILES:
        raise ValueError("Cutscene OBJ primary-pointer implementation file set mismatch")
    for name, digest in implementation.items():
        if _sha256_file(root / name) != digest:
            raise ValueError(f"Cutscene OBJ primary-pointer implementation hash mismatch: {name}")
    if _sha256_file(root / SCRIPT_PATH) != SCRIPT_SHA256 or _sha256_file(root / INPUT_PATH) != INPUT_SHA256:
        raise ValueError("Cutscene OBJ primary-pointer repository input mismatch")
    if binary is not None and _sha256_file(Path(binary).resolve(strict=True)) != BINARY_SHA256:
        raise ValueError("Cutscene OBJ primary-pointer supplied binary mismatch")

    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        raw = temp / "raw"
        raw.mkdir()
        _extract_raw(artifact / "raw.tar", raw)
        rebuilt = temp / "rebuilt"
        build = build_pair(root, rebuilt)
        if _read_json(raw / "build/build-manifest.json") != build:
            raise ValueError("Cutscene OBJ primary-pointer raw build mismatch")
        launch = _read_json(raw / "launch-identity.json")
        expected_guards = {}
        states = {}
        runs = {}
        for variant in ("baseline", "candidate"):
            audit_path = raw / f"runtime/{variant}/audit.json"
            sentinel_path = raw / f"runtime/{variant}/sentinel.json"
            state_path = raw / f"runtime/{variant}/frame512.ss9"
            png_path = raw / f"runtime/{variant}/frame512.png"
            guard_path = raw / f"runtime/{variant}/guard.json"
            audit = _read_json(audit_path)
            guard = _read_json(guard_path)
            command = guard.get("command")
            if (
                audit != _read_json(sentinel_path)
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
                or not isinstance(command, list)
                or len(command) != 4
                or Path(command[0]).name != "mGBA"
                or command[1] != "--script"
                or Path(command[2]).name != SCRIPT_PATH.name
                or not command[3].endswith(f"/runtime/{variant}/staged.gba")
            ):
                raise ValueError(f"Cutscene OBJ primary-pointer {variant} provenance mismatch")
            expected_guards[variant] = {
                "guard_sha256": _sha256_file(guard_path),
                "staged_rom_sha256": build["variants"][variant]["rom_sha256"],
                "binary_command_path_sha256": _sha256(command[0].encode()),
                "script_command_path_sha256": _sha256(command[2].encode()),
            }
            state = load_gba_state(state_path)
            with Image.open(png_path) as image:
                png_rgb = image.convert("RGB").tobytes()
            if render_checkpoint(state_path)[0] != png_rgb:
                raise ValueError(f"Cutscene OBJ primary-pointer {variant} renderer mismatch")
            states[variant] = state
            runs[variant] = {
                "rom_sha256": audit["rom_sha256"],
                "audit_sha256": _sha256_file(audit_path),
                "sentinel_sha256": _sha256_file(sentinel_path),
                "state_sha256": _sha256_file(state_path),
                "png_sha256": _sha256_file(png_path),
                "guard_sha256": _sha256_file(guard_path),
                "staged_rom_sha256": build["variants"][variant]["rom_sha256"],
                "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
                "pgid_clean": True,
            }
        if launch != {
            "schema": "cutscene-obj-primary-ptr-launch-identity-v1",
            "binary": {"basename": "mGBA", "sha256": BINARY_SHA256, "source_commit": "c16c3ff55585e71bee83c95539c2ecde15d728c8"},
            "script": {"repository_path": SCRIPT_PATH.as_posix(), "sha256": SCRIPT_SHA256},
            "guards": expected_guards,
        }:
            raise ValueError("Cutscene OBJ primary-pointer launch identity mismatch")
        for variant, pointer in (("baseline", 0x08BA04C0), ("candidate", 0x08BA09CC)):
            rom = (rebuilt / build["variants"][variant]["rom_path"]).read_bytes()
            graphics = _lz77(rom, pointer)
            if len(graphics) != 4096 or states[variant].read_memory(0x06016000, 4096) != graphics:
                raise ValueError(f"Cutscene OBJ primary-pointer {variant} VRAM route mismatch")
        regions = _region_facts(states)
        pixels = _pixel_facts(raw / "runtime/baseline/frame512.png", raw / "runtime/candidate/frame512.png")
        expected_evidence = {
            "schema": "cutscene-obj-id1-primary-ptr-ab-evidence-v1",
            "verified": True,
            "actual_identity": "two adjacent four-record Cutscene OBJ visual-resource tables",
            "input": {"path": INPUT_PATH.as_posix(), "sha256": INPUT_SHA256, "event": {"key": "A", "down_frame": 5, "up_frame": 13}, "capture_frame": 512, "natural_victory_load": True},
            "emulator": {"binary_sha256": BINARY_SHA256, "source_commit": "c16c3ff55585e71bee83c95539c2ecde15d728c8", "script_path": SCRIPT_PATH.as_posix(), "script_sha256": SCRIPT_SHA256},
            "edit": build["edit"],
            "runs": runs,
            "memory_differences": regions,
            "pixels": pixels,
            "runtime": {"graphics_vram_address": "0x06016000", "oam_entry": 1, "oam_equal": True, "palette_equal": True, "renderer_exact": True},
            "scope": {"resource_1_primary_pointer_runtime_verified": True, "resources_0_2_3_runtime_verified": False, "second_table_runtime_ab_verified": False, "physical_gba_verified": False},
        }
        if evidence != expected_evidence:
            raise ValueError("Cutscene OBJ primary-pointer signed evidence mismatch")
        if _sha256_file(artifact / "baseline.png") != _sha256_file(raw / "runtime/baseline/frame512.png") or _sha256_file(artifact / "candidate.png") != _sha256_file(raw / "runtime/candidate/frame512.png"):
            raise ValueError("Cutscene OBJ primary-pointer promoted PNG mismatch")


def verify_artifact(root: Path, artifact: Path, binary: Path | None = None) -> dict[str, Any]:
    try:
        _verify(Path(root), Path(artifact), binary)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, tarfile.TarError) as error:
        return {"errors": [str(error)], "verified": False}
    return {"errors": [], "verified": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--binary", type=Path)
    args = parser.parse_args()
    result = verify_artifact(args.root, args.artifact, args.binary)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
