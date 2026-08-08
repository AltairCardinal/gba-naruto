#!/usr/bin/env python3
"""Validate and promote the controlled map-sprites definition-pointer pixel A/B."""

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


EVIDENCE_SCHEMA = "map-sprites-definition-pixel-ab-evidence-v1"
MANIFEST_SCHEMA = "map-sprites-definition-pixel-ab-artifact-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
BINARY_SHA256 = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
BINARY_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
BINARY_PATH = Path("/Users/altair/github/mgba-build-c16/qt/mGBA.app/Contents/MacOS/mGBA")
CHECKPOINT = "artifacts/runtime-checkpoints/scenario-41-combat-dialogue.ss9"
CHECKPOINT_SHA256 = "3741a385a4473919243e9f3220f9cbdf79d590b8002107f71e22f67e6b74ab1c"
EXPECTED_RAW_FILES = (
    "build/build-manifest.json",
    "runs/baseline/guard-summary.json",
    "runs/baseline/output/audit.json",
    "runs/baseline/output/final.png",
    "runs/baseline/output/final.ss9",
    "runs/candidate/guard-summary.json",
    "runs/candidate/output/audit.json",
    "runs/candidate/output/final.png",
    "runs/candidate/output/final.ss9",
)
IMPLEMENTATION_FILES = (
    "sequel/content/map-sprites/bank.json",
    "sequel/content/map-sprites/definition-id01-pixel-ab.json",
    "artifacts/sprite-definition-assets-v2/manifest.json",
    "tools/build_map_sprites_definition_pixel_ab.py",
    "tools/export_map_sprites_definition_pixel_ab.py",
    "tools/verify_map_sprites_definition_pixel_ab.py",
    "tools/mgba_map_sprites_trace.lua",
    "tools/inspect_mgba_savestate.py",
    "tools/render_mode0_checkpoint.py",
    "tests/test_build_map_sprites_definition_pixel_ab.py",
    "tests/test_mgba_map_sprites_trace_script.py",
    "tests/test_map_sprites_definition_pixel_ab_artifact.py",
    "tests/test_render_mode0_checkpoint.py",
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
        raise ValueError(f"{label} must be a JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate_guard(root: Path, guard: dict[str, Any], variant: str) -> None:
    command = guard.get("command")
    expected_script = str((root / "tools/mgba_map_sprites_trace.lua").resolve(strict=True))
    if (
        guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("protection_backend") != "posix-process-group"
        or guard.get("degraded") is not False
        or not isinstance(guard.get("peak_tree_rss_mib"), (int, float))
        or guard["peak_tree_rss_mib"] > 768
        or not isinstance(command, list)
        or len(command) != 4
        or command[0] != str(BINARY_PATH)
        or command[1] != "--script"
        or command[2] != expected_script
        or Path(command[3]).name != f"{variant}.gba"
    ):
        raise ValueError(f"map-sprites {variant} guard mismatch")


def _reconstruct_variants(root: Path, build: dict[str, Any]) -> dict[str, bytes]:
    base = (root / "rom/base.gba").read_bytes()
    patch_offset = 0x53F148
    before = bytes.fromhex("d8f51208")
    after = bytes.fromhex("ccf71208")
    if (
        len(base) != 0x600000
        or sha256_bytes(base) != build.get("source_rom_sha256")
        or base[patch_offset : patch_offset + 4] != before
    ):
        raise ValueError("map-sprites ROM reconstruction mismatch")
    candidate_buffer = bytearray(base)
    candidate_buffer[patch_offset : patch_offset + 4] = after
    candidate = bytes(candidate_buffer)
    changed_offsets = [
        index
        for index, pair in enumerate(zip(base, candidate, strict=True))
        if pair[0] != pair[1]
    ]
    edit = build.get("edit")
    variants = build.get("variants")
    expected_edit = {
        "rom_offset": patch_offset,
        "rom_address": "0x0853F148",
        "field": "definition_ptr",
        "before_pointer": "0x0812F5D8",
        "after_pointer": "0x0812F7CC",
        "before_bytes": before.hex(),
        "after_bytes": after.hex(),
        "changed_rom_offsets": changed_offsets,
    }
    reconstructed = {"baseline": base, "candidate": candidate}
    if edit != expected_edit or not isinstance(variants, dict) or set(variants) != set(reconstructed):
        raise ValueError("map-sprites ROM reconstruction mismatch")
    for variant, payload in reconstructed.items():
        expected = {
            "rom_path": f"{variant}/{variant}.gba",
            "rom_sha256": sha256_bytes(payload),
            "rom_size": len(payload),
        }
        if variants.get(variant) != expected:
            raise ValueError("map-sprites ROM reconstruction mismatch")
    return reconstructed


def _pixel_facts(baseline_path: Path, candidate_path: Path) -> dict[str, Any]:
    with Image.open(baseline_path) as image:
        baseline = image.convert("RGB")
    with Image.open(candidate_path) as image:
        candidate = image.convert("RGB")
    if baseline.size != (240, 160) or candidate.size != baseline.size:
        raise ValueError("map-sprites runtime PNG dimensions mismatch")
    left = baseline.tobytes()
    right = candidate.tobytes()
    changed = sum(
        left[offset : offset + 3] != right[offset : offset + 3]
        for offset in range(0, len(left), 3)
    )
    bbox = ImageChops.difference(baseline, candidate).getbbox()
    if bbox is None:
        raise ValueError("map-sprites runtime produced no pixel difference")
    return {
        "width": 240,
        "height": 160,
        "baseline_rgb_sha256": sha256_bytes(left),
        "candidate_rgb_sha256": sha256_bytes(right),
        "changed_pixel_count": changed,
        "bbox_inclusive": [bbox[0], bbox[1], bbox[2] - 1, bbox[3] - 1],
    }


def _event_map(audit: dict[str, Any], variant: str) -> dict[str, dict[str, Any]]:
    events = audit.get("events")
    if not isinstance(events, list):
        raise ValueError(f"map-sprites {variant} events missing")
    result = {event.get("name"): event for event in events if isinstance(event, dict)}
    if set(result) != {"controlled-bootstrap", "frame-select", "oam-compose"}:
        raise ValueError(f"map-sprites {variant} event set mismatch")
    return result


def _validate_source(root: Path, source: Path) -> dict[str, Any]:
    for name in EXPECTED_RAW_FILES:
        if not (source / name).is_file():
            raise ValueError(f"map-sprites raw source missing {name}")
    build = read_object(source / "build/build-manifest.json", "map-sprites build manifest")
    source_contract = {
        "profile": "sequel/content/map-sprites/definition-id01-pixel-ab.json",
        "source_rom": "rom/base.gba",
        "source_bank": "sequel/content/map-sprites/bank.json",
        "source_asset_manifest": "artifacts/sprite-definition-assets-v2/manifest.json",
        "input_state": CHECKPOINT,
    }
    if any(build.get(key) != value for key, value in source_contract.items()) or any(
        build.get(digest_key) != sha256_file(root / build[path_key])
        for path_key, digest_key in (
            ("profile", "profile_sha256"),
            ("source_rom", "source_rom_sha256"),
            ("source_bank", "source_bank_sha256"),
            ("source_asset_manifest", "source_asset_manifest_sha256"),
            ("input_state", "input_state_sha256"),
        )
    ):
        raise ValueError("map-sprites source contract mismatch")
    if (
        build.get("schema") != "map-sprites-definition-pixel-ab-build-v1"
        or build.get("entry_id") != 1
        or build.get("donor_entry_id") != 37
        or build.get("natural_gameplay_route") is not False
        or build.get("controlled_task_materialization") is not True
        or build.get("task_slot") != 123
        or build.get("input_state") != CHECKPOINT
        or build.get("input_state_sha256") != CHECKPOINT_SHA256
        or build.get("inputs") != []
        or build.get("capture_post_boundary_frames") != 2
        or build.get("edit", {}).get("changed_rom_offsets") != [0x53F148, 0x53F149]
    ):
        raise ValueError("map-sprites build contract mismatch")
    reconstructed_variants = _reconstruct_variants(root, build)
    script_digest = sha256_file(root / "tools/mgba_map_sprites_trace.lua")
    if not BINARY_PATH.is_file() or sha256_file(BINARY_PATH) != BINARY_SHA256:
        raise ValueError("map-sprites runtime tool hash mismatch")

    expected_definitions = {"baseline": "0x0812F5D8", "candidate": "0x0812F7CC"}
    expected_components = {"baseline": "0x0812F5C0", "candidate": "0x0812F7A0"}
    expected_r4 = {"baseline": "0x00B00040", "candidate": "0x00D00040"}
    states: dict[str, Any] = {}
    runs: dict[str, Any] = {}
    event_summaries: dict[str, Any] = {}
    for variant in ("baseline", "candidate"):
        audit_path = source / f"runs/{variant}/output/audit.json"
        guard_path = source / f"runs/{variant}/guard-summary.json"
        state_path = source / f"runs/{variant}/output/final.ss9"
        png_path = source / f"runs/{variant}/output/final.png"
        audit = read_object(audit_path, f"map-sprites {variant} audit")
        guard = read_object(guard_path, f"map-sprites {variant} guard")
        _validate_guard(root, guard, variant)
        events = _event_map(audit, variant)
        definition = expected_definitions[variant]
        if (
            audit.get("script_sha256") != script_digest
            or audit.get("binary_sha256") != BINARY_SHA256
        ):
            raise ValueError("map-sprites runtime tool hash mismatch")
        if (
            audit.get("outcome") != "all-downstream-boundaries-hit"
            or audit.get("frame") != 2
            or audit.get("input_state_sha256") != CHECKPOINT_SHA256
            or audit.get("rom_sha256")
            != build.get("variants", {}).get(variant, {}).get("rom_sha256")
            or audit.get("rom_sha256") != sha256_bytes(reconstructed_variants[variant])
            or audit.get("controlled_task_materialization") is not True
            or audit.get("bootstrap_task_slot") != 123
            or audit.get("target_task") != "0x0300588C"
            or audit.get("target_id") != 1
            or audit.get("required_hit_count") != 3
            or audit.get("hit_count") != 3
            or audit.get("inputs") != []
            or audit.get("recovery_inputs") != []
            or events["controlled-bootstrap"].get("definition") != definition
            or events["controlled-bootstrap"].get("task_definition") != definition
            or events["controlled-bootstrap"].get("task_animation") != "0x0812F5E4"
            or events["controlled-bootstrap"].get("task_flags") != "0x01000049"
            or events["frame-select"].get("r7") != "0x0300588C"
            or events["frame-select"].get("task_definition") != definition
            or events["oam-compose"].get("r7") != "0x0300588C"
            or events["oam-compose"].get("r8") != expected_components[variant]
            or events["oam-compose"].get("r4") != expected_r4[variant]
        ):
            raise ValueError(f"map-sprites {variant} runtime chain mismatch")
        state = load_gba_state(state_path)
        rendered = render_checkpoint(state_path)[0]
        with Image.open(png_path) as screenshot:
            screenshot_rgb = screenshot.convert("RGB").tobytes()
            screenshot_size = screenshot.size
        if screenshot_size != (240, 160) or screenshot_rgb != rendered:
            raise ValueError(f"map-sprites {variant} savestate screenshot mismatch")
        states[variant] = state
        runs[variant] = {
            "rom_sha256": audit["rom_sha256"],
            "audit_sha256": sha256_file(audit_path),
            "guard_sha256": sha256_file(guard_path),
            "state_sha256": sha256_file(state_path),
            "png_sha256": sha256_file(png_path),
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
            "pgid_clean": True,
        }
        event_summaries[variant] = {
            name: {
                key: events[name][key]
                for key in ("address", "frame", "task", "definition", "animation", "task_flags", "r4", "r7", "r8")
            }
            for name in ("controlled-bootstrap", "frame-select", "oam-compose")
        }

    regions = (
        ("IO", 0x04000000, 0x400),
        ("PRAM", 0x05000000, 0x400),
        ("VRAM", 0x06000000, 0x18000),
        ("OAM", 0x07000000, 0x400),
        ("IWRAM", 0x03000000, 0x8000),
        ("EWRAM", 0x02000000, 0x40000),
    )
    differences: dict[str, list[int]] = {}
    for name, address, size in regions:
        left = states["baseline"].read_memory(address, size)
        right = states["candidate"].read_memory(address, size)
        differences[name] = [
            index for index, pair in enumerate(zip(left, right, strict=True)) if pair[0] != pair[1]
        ]
    expected_differences = {
        "IO": [],
        "PRAM": [],
        "VRAM": [],
        "OAM": [10, 16, 17, 18, 19, 20, 21, 26, 27, 28, 29, 32, 33, 34, 35],
        "IWRAM": [646, 652, 653, 654, 655, 656, 657, 662, 663, 664, 665, 668, 669, 670, 671, 22696, 22697],
        "EWRAM": [],
    }
    if differences != expected_differences:
        raise ValueError("map-sprites runtime memory attribution mismatch")
    pixels = _pixel_facts(
        source / "runs/baseline/output/final.png",
        source / "runs/candidate/output/final.png",
    )
    if pixels["changed_pixel_count"] != 213 or pixels["bbox_inclusive"] != [178, 64, 215, 71]:
        raise ValueError("map-sprites pixel difference mismatch")
    return {
        "build": build,
        "runs": runs,
        "events": event_summaries,
        "memory_differences": differences,
        "pixels": pixels,
    }


def _build_evidence(facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": EVIDENCE_SCHEMA,
        "verified": True,
        "entry_id": 1,
        "donor_entry_id": 37,
        "checkpoint": {"path": CHECKPOINT, "sha256": CHECKPOINT_SHA256},
        "route": {
            "natural_loader_reentry": False,
            "controlled_task_materialization": True,
            "task_slot": 123,
            "task_address": "0x0300588C",
            "inputs": [],
            "post_boundary_frames": 2,
            "boundary": facts["build"]["boundary"],
        },
        "build": {
            "manifest_sha256": None,
            "edit": facts["build"]["edit"],
        },
        "emulator": {"source_commit": BINARY_COMMIT, "binary_sha256": BINARY_SHA256},
        "runs": facts["runs"],
        "events": facts["events"],
        "memory": {"differences": facts["memory_differences"]},
        "pixels": facts["pixels"],
        "proved": "Entry 1 definition_ptr is materialized from ROM into task 123; the changed pointer reaches frame selection and OAM composition and changes 213 final pixels.",
        "not_proved": "No natural input route recreated the generic task during this run; pixel compatibility with donor entry 37's native tile base is outside this single-field experiment.",
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
        raise ValueError("map-sprites artifact output must be absent or empty")
    facts = _validate_source(root, source)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "runs/baseline/output/final.png", output / "baseline.png")
    shutil.copyfile(source / "runs/candidate/output/final.png", output / "candidate.png")
    _write_raw_tar(source, output / "raw.tar")
    evidence = _build_evidence(facts)
    evidence["build"]["manifest_sha256"] = sha256_file(source / "build/build-manifest.json")
    write_json(output / "evidence.json", evidence)
    files = {
        name: sha256_file(output / name)
        for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar")
    }
    implementation = {name: sha256_file(root / name) for name in IMPLEMENTATION_FILES}
    manifest = {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": MANIFEST_SCHEMA,
        "artifact_id": "map-sprites-definition-id1-pixel-ab-v1",
        "artifact_status": "accepted",
        "files": files,
        "implementation": implementation,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_map_sprites_definition_pixel_ab.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/map-sprites-definition-id1-pixel-ab-v1",
            ],
            "exit_code": 0,
        },
        "scope": {
            "proved": evidence["proved"],
            "not_proved": evidence["not_proved"],
        },
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(export_artifact(ROOT, args.source, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
