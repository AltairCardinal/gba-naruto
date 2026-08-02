#!/usr/bin/env python3
"""Promote a probe-free natural delayed-effect final-pixel A/B artifact."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tarfile
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_natural_delayed_battle_effect_pixel_ab import (
    BUILD_SCHEMA,
    _validate_profile,
    build_pair,
)
from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint
from tools.verify_battle_effect_direct_spawn_runtime import _active_slots, _target_tasks
from tools.verify_battle_effect_frame_phase import (
    expected_phase_inputs,
    verify_artifact as verify_phase_artifact,
)


EVIDENCE_SCHEMA = "natural-delayed-battle-effect-pixel-ab-runtime-v1"
VARIANTS = ("baseline", "candidate")
PHASES = ("renderer-post", "submit-post", "ack-post")
PHASE_ADDRESSES = (0x08063328, 0x08061126, 0x080612AA)
PHASE_PENDING = (0, 1, 0)
DEFINITION = 0x083425D8
ANIMATION = 0x083426CC
TASK_SLOT = 126
TILE_BASE = 288
PALETTE_BANK = 5
GRAPHICS_ADDRESS = 0x06012400
PALETTE_ADDRESS = 0x050002A0
PENDING = 0x0300067C
SHADOW_OAM = 0x0300027C
HARDWARE_OAM = 0x07000000
SUBMISSION_COUNTS = (1, 1, 2)
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "IWRAM": (0x03000000, 0x8000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "VRAM": (0x06000000, 0x18000),
    "OAM": (0x07000000, 0x400),
}
IMPLEMENTATION_PATHS = (
    "tools/build_natural_delayed_battle_effect_pixel_ab.py",
    "tools/run_natural_delayed_battle_effect_pixel_ab.py",
    "tools/export_natural_delayed_battle_effect_pixel_ab.py",
    "tools/verify_natural_delayed_battle_effect_pixel_ab.py",
    "tools/verify_battle_effect_frame_phase.py",
    "tools/verify_battle_effect_natural_checkpoint.py",
    "tools/verify_battlefield_object_producers.py",
    "tools/verify_battle_effect_direct_spawn_runtime.py",
    "tools/run_macos_mgba_battle_effect_phase_capture.py",
    "tools/mgba_battle_effect_phase_capture.lua",
    "tools/run_guarded.py",
    "tools/mgba_runtime_safety.py",
    "tools/inspect_mgba_savestate.py",
    "tools/thumb_branch.py",
    "tools/render_mode0_checkpoint.py",
    "tools/import_battle_effect_resource_relocations.py",
    "tools/import_battle_effect_resources.py",
    "tools/image_resource_regions.py",
    "tools/patch_safety.py",
    "tools/rom_layout.py",
    "tests/test_build_natural_delayed_battle_effect_pixel_ab.py",
    "tests/test_run_natural_delayed_battle_effect_pixel_ab.py",
    "tests/test_export_natural_delayed_battle_effect_pixel_ab.py",
    "tests/test_verify_natural_delayed_battle_effect_pixel_ab.py",
    "tests/test_verify_battle_effect_natural_checkpoint.py",
    "tests/test_verify_battlefield_object_producers.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"natural delayed pixel JSON must be an object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def runtime_contract(
    profile: dict[str, Any], phase_manifest: dict[str, Any]
) -> dict[str, Any]:
    group_id = profile.get("group_id")
    sequence_id = profile.get("sequence_id")
    if (
        not isinstance(group_id, int)
        or isinstance(group_id, bool)
        or not isinstance(sequence_id, int)
        or isinstance(sequence_id, bool)
        or phase_manifest.get("artifact_status") != "accepted"
        or phase_manifest.get("group_id") != group_id
    ):
        raise ValueError("natural delayed pixel runtime identity mismatch")
    phases = phase_manifest.get("phase_sequence")
    task_slots = {
        row.get("task_slot") for row in phases if isinstance(row, dict)
    } if isinstance(phases, list) else set()
    if len(phases or []) != 3 or len(task_slots) != 1:
        raise ValueError("natural delayed pixel runtime task identity mismatch")
    animations = _json(ROOT / "artifacts/battle-effect-sprite-animations-v1/manifest.json")
    matches = [
        row
        for row in animations.get("groups", [])
        if isinstance(row, dict) and row.get("group_id") == group_id
    ]
    if len(matches) != 1:
        raise ValueError("natural delayed pixel animation identity mismatch")
    runtime = profile.get("runtime_oam")
    if not isinstance(runtime, dict):
        raise ValueError("natural delayed pixel runtime OAM is missing")
    try:
        graphics_address = int(runtime["obj_vram_address"], 16)
        palette_bank = int(runtime["palette_bank"])
        oam_index = int(runtime["oam_index"])
        tile_base = int(runtime["obj_tile_base"])
        renderer_change = runtime.get("renderer_shadow_change", True)
        graphics_offset = int(profile["graphics_byte_offset"])
        definition = int(matches[0]["definition_pointer_table"], 16)
        animation = int(matches[0]["animation_pointer_table"], 16)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("natural delayed pixel runtime OAM is invalid") from error
    if (
        not isinstance(renderer_change, bool)
        or not 0x06010000 <= graphics_address < 0x06018000
        or not 0 <= palette_bank <= 15
        or not 0 <= oam_index < 128
    ):
        raise ValueError("natural delayed pixel runtime OAM is invalid")
    phase_artifact = ROOT / str(profile.get("source_natural_phase_artifact", ""))
    submission_counts = []
    for phase, expected_pending in zip(PHASES, PHASE_PENDING, strict=True):
        raw = (
            phase_artifact / f"raw/{phase}/capture-submission.bin"
        ).read_bytes()
        if len(raw) != 2 or raw[0] != expected_pending:
            raise ValueError("natural delayed pixel parent submission state mismatch")
        submission_counts.append(raw[1])
    return {
        "group_id": group_id,
        "sequence_id": sequence_id,
        "definition": definition,
        "animation": animation,
        "task_slot": next(iter(task_slots)),
        "tile_base": tile_base,
        "palette_bank": palette_bank,
        "graphics_address": graphics_address,
        "palette_address": 0x05000200 + palette_bank * 32,
        "oam_index": oam_index,
        "oam_attributes": runtime.get("attributes"),
        "vram_difference_offset": graphics_address - 0x06000000 + graphics_offset,
        "renderer_shadow_change": renderer_change,
        "submission_counts": submission_counts,
    }


def input_contract(
    profile: dict[str, Any], phase_manifest: dict[str, Any]
) -> dict[str, Any]:
    try:
        mode, events = expected_phase_inputs(profile)
    except ValueError as error:
        raise ValueError(f"natural delayed pixel input contract mismatch: {error}") from error
    if (
        phase_manifest.get("input_mode") != mode
        or phase_manifest.get("inputs") != events
    ):
        raise ValueError("natural delayed pixel parent input contract mismatch")
    capture_frame = profile.get("capture_frame")
    timeout_frames = profile.get("timeout_frames")
    if mode == "explicit-input-sequence" and (
        not isinstance(capture_frame, int)
        or isinstance(capture_frame, bool)
        or not isinstance(timeout_frames, int)
        or isinstance(timeout_frames, bool)
        or timeout_frames <= capture_frame
    ):
        raise ValueError("natural delayed pixel explicit input timing mismatch")
    return {
        "mode": mode,
        "events": events,
        "raw_inputs": profile.get("inputs", []),
        "capture_frame": capture_frame,
        "timeout_frames": timeout_frames,
    }


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("natural delayed pixel byte lengths differ")
    return [index for index, pair in enumerate(zip(left, right, strict=True)) if pair[0] != pair[1]]


def _pixel_changes(left: bytes, right: bytes) -> list[dict[str, Any]]:
    changes = []
    for index in range(240 * 160):
        offset = index * 3
        before = list(left[offset:offset + 3])
        after = list(right[offset:offset + 3])
        if before != after:
            changes.append({
                "x": index % 240,
                "y": index // 240,
                "before_rgb": before,
                "after_rgb": after,
            })
    return changes


def _save_rgb(path: Path, pixels: bytes) -> None:
    Image.frombytes("RGB", (240, 160), pixels).save(path, optimize=False)


def _raw_paths(source: Path, group_id: int) -> list[Path]:
    selected = [source / "batch-audit.json", source / "build/build-manifest.json"]
    for variant in VARIANTS:
        selected.extend([
            source / f"build/{variant}/group-{group_id:02d}-graphics-4bpp.bin",
            source / f"build/{variant}/spec.json",
            source / f"runs/{variant}/profile.json",
            source / f"runs/{variant}/guard-summary.json",
            source / f"runs/{variant}/guard-summary.json.done.json",
        ])
        selected.extend(sorted(
            path for path in (source / f"runs/{variant}/output").rglob("*")
            if path.is_file()
        ))
    if any(not path.is_file() or path.is_symlink() for path in selected):
        raise ValueError("natural delayed pixel raw source is incomplete or unsafe")
    return sorted(set(selected), key=lambda path: path.relative_to(source).as_posix())


def _write_tar(source: Path, paths: list[Path], output: Path) -> list[dict[str, Any]]:
    inventory = []
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as archive:
        for path in paths:
            name = path.relative_to(source).as_posix()
            data = path.read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
            inventory.append({"path": name, "size": len(data), "sha256": _sha256(data)})
    return inventory


def _phase_transaction(
    source: Path,
    variant: str,
    graphics: bytes,
    palette: bytes,
    runtime: dict[str, Any],
) -> tuple[dict[str, Any], Any]:
    run = source / f"runs/{variant}"
    audit = _json(run / "output/audit.json")
    states = []
    metas = []
    cycles = []
    frames = []
    hashes = []
    previous_cycle = -1
    for index, phase in enumerate(PHASES):
        phase_root = run / f"output/{phase}"
        for path in phase_root.iterdir():
            if path.is_file() and audit.get("files", {}).get(f"{phase}/{path.name}") != _sha256_file(path):
                raise ValueError(f"natural delayed pixel {variant} phase hash mismatch: {phase}/{path.name}")
        state_path = phase_root / "capture.ss9"
        state = load_gba_state(state_path)
        meta = _json(phase_root / "capture-phase.json")
        address = state.registers[15] - 2
        cycle = int(meta.get("cycle", -1))
        targets = _target_tasks(
            state, runtime["definition"], runtime["animation"]
        )
        if (
            address != PHASE_ADDRESSES[index]
            or meta.get("name") != phase
            or meta.get("address") != f"0x{address:08X}"
            or meta.get("pending") != PHASE_PENDING[index]
            or state.read_memory(PENDING, 1)[0] != PHASE_PENDING[index]
            or cycle <= previous_cycle
            or len(targets) != 1
            or targets[0]["slot"] != runtime["task_slot"]
            or targets[0]["slot"] not in _active_slots(state)
            or targets[0]["tile_base"] != runtime["tile_base"]
            or targets[0]["palette_bank"] != runtime["palette_bank"]
            or meta.get("task_slot") != runtime["task_slot"]
            or state.read_memory(runtime["graphics_address"], len(graphics)) != graphics
            or state.read_memory(runtime["palette_address"], len(palette)) != palette
        ):
            raise ValueError(f"natural delayed pixel {variant} phase mismatch: {phase}")
        dumps = {
            "capture-task-pool.bin": (0x03003BB8, 128 * 0x3C),
            "capture-active-count.bin": (0x03005BB8, 1),
            "capture-active-pointers.bin": (0x030059B8, 512),
            "capture-shadow-oam.bin": (SHADOW_OAM, 0x400),
            "capture-hardware-oam.bin": (HARDWARE_OAM, 0x400),
            "capture-pram.bin": (0x05000000, 0x400),
            "capture-vram.bin": (0x06000000, 0x18000),
        }
        for name, (start, size) in dumps.items():
            if (phase_root / name).read_bytes() != state.read_memory(start, size):
                raise ValueError(f"natural delayed pixel {variant} dump mismatch: {phase}/{name}")
        if (phase_root / "capture-submission.bin").read_bytes() != bytes([
            PHASE_PENDING[index], runtime["submission_counts"][index]
        ]):
            raise ValueError(f"natural delayed pixel {variant} submission mismatch: {phase}")
        previous_cycle = cycle
        states.append(state)
        metas.append(meta)
        cycles.append(str(cycle))
        frames.append(meta.get("frame"))
        hashes.append(_sha256_file(state_path))
    if audit.get("phases") != metas or audit.get("renderer_hit_count", 0) < 1 or audit.get("submission_watch_hit_count", 0) < 3 or audit.get("ack_hit_count") != 1:
        raise ValueError(f"natural delayed pixel {variant} phase audit mismatch")
    renderer_shadow = states[0].read_memory(SHADOW_OAM, 0x400)
    renderer_hardware = states[0].read_memory(HARDWARE_OAM, 0x400)
    renderer_differs = renderer_shadow != renderer_hardware
    if (
        renderer_differs != runtime["renderer_shadow_change"]
        or states[1].read_memory(HARDWARE_OAM, 0x400) != renderer_hardware
        or states[2].read_memory(HARDWARE_OAM, 0x400) != renderer_shadow
    ):
        raise ValueError(f"natural delayed pixel {variant} OAM transaction mismatch")
    return ({
        "addresses": [f"0x{value:08X}" for value in PHASE_ADDRESSES],
        "pending": list(PHASE_PENDING),
        "frames": frames,
        "cycles": cycles,
        "savestate_sha256": hashes,
        "renderer_shadow_differs_from_old_hardware": renderer_differs,
        "submit_hardware_unchanged": True,
        "ack_hardware_equals_renderer_shadow": True,
    }, states[2])


def export_evidence(root: Path, profile_path: Path, source: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    profile_path = Path(profile_path).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("natural delayed pixel artifact output must be empty")
    profile, contract = _validate_profile(root, profile_path)
    parent = verify_phase_artifact(root / profile["source_natural_phase_artifact"])
    if not parent.get("verified"):
        raise ValueError("natural delayed pixel source phase is not verified")
    phase_manifest = _json(root / profile["source_natural_phase_manifest"])
    runtime = runtime_contract(profile, phase_manifest)
    inputs = input_contract(profile, phase_manifest)
    expected_coverage = profile.get(
        "expected_production_natural_pixel_coverage",
        "6/18" if profile["group_id"] == 3 else None,
    )
    if not isinstance(expected_coverage, str):
        raise ValueError("natural delayed pixel production coverage is missing")
    batch = _json(source / "batch-audit.json")
    build = _json(source / "build/build-manifest.json")
    if (
        batch.get("schema") != "natural-delayed-battle-effect-pixel-ab-batch-v1"
        or batch.get("natural_gameplay_route") is not True
        or batch.get("input_mode") != inputs["mode"]
        or batch.get("inputs", []) != inputs["raw_inputs"]
        or batch.get("capture_frame") != inputs["capture_frame"]
        or batch.get("timeout_frames") != inputs["timeout_frames"]
        or build.get("schema") != BUILD_SCHEMA
        or build.get("profile_sha256") != _sha256_file(profile_path)
        or build.get("natural_gameplay_route") is not True
        or build.get("probe_free") is not True
        or build.get("same_patch_topology") is not True
        or build.get("same_encoded_size") is not True
        or build.get("group_id") != profile["group_id"]
        or build.get("sequence_id") != profile["sequence_id"]
        or build.get("input_mode") != inputs["mode"]
        or build.get("inputs", []) != inputs["raw_inputs"]
        or build.get("capture_frame") != inputs["capture_frame"]
        or build.get("timeout_frames") != inputs["timeout_frames"]
        or build.get("source_pointer_offsets") != profile["source_pointer_offsets"]
        or build.get("target_pointer_offsets") != profile["target_pointer_offsets"]
        or batch.get("build_manifest_sha256") != _sha256_file(source / "build/build-manifest.json")
    ):
        raise ValueError("natural delayed pixel build/batch contract mismatch")
    with __import__("tempfile").TemporaryDirectory() as temporary:
        rebuilt = build_pair(root, profile_path, Path(temporary) / "build")
        if {
            key: rebuilt[key]
            for key in ("schema", "profile_sha256", "input_mode", "inputs", "capture_frame", "timeout_frames", "source_pointer_offsets", "target_pointer_offsets", "same_patch_topology", "same_encoded_size", "probe_free", "variants")
        } != {
            key: build[key]
            for key in ("schema", "profile_sha256", "input_mode", "inputs", "capture_frame", "timeout_frames", "source_pointer_offsets", "target_pointer_offsets", "same_patch_topology", "same_encoded_size", "probe_free", "variants")
        }:
            raise ValueError("natural delayed pixel build is not reproducible")

    palette = contract["palette_path"].read_bytes()
    graphics = {
        variant: (
            source
            / f"build/{variant}/group-{profile['group_id']:02d}-graphics-4bpp.bin"
        ).read_bytes()
        for variant in VARIANTS
    }
    if _diff(graphics["baseline"], graphics["candidate"]) != [profile["graphics_byte_offset"]]:
        raise ValueError("natural delayed pixel authored graphics mismatch")
    audits = {}
    guards = {}
    states = {}
    transactions = {}
    batch_rows = {row["variant"]: row for row in batch["runs"]}
    for variant in VARIANTS:
        run = source / f"runs/{variant}"
        run_profile = _json(run / "profile.json")
        audit = _json(run / "output/audit.json")
        guard = _json(run / "guard-summary.json")
        try:
            run_input_mode, run_inputs = expected_phase_inputs(run_profile)
        except ValueError as error:
            raise ValueError(
                f"natural delayed pixel {variant} input profile mismatch: {error}"
            ) from error
        if (
            run_profile.get("execution_mode") != "natural-delayed-object-pixel-ab"
            or run_profile.get("natural_gameplay_route") is not True
            or run_input_mode != inputs["mode"]
            or run_inputs != inputs["events"]
            or run_profile.get("variant") != variant
            or run_profile.get("source_rom_sha256") != build["variants"][variant]["rom_sha256"]
            or audit.get("outcome") != "three-phase-captured"
            or audit.get("input_mode") != inputs["mode"]
            or audit.get("inputs") != inputs["events"]
            or audit.get("automatic_inputs") != []
            or audit.get("recovery_inputs") != []
            or audit.get("rom_sha256") != build["variants"][variant]["rom_sha256"]
            or guard.get("reason") != "completed"
            or guard.get("exit_code") != 0
            or guard.get("degraded") is not False
            or audit.get("runtime_residue", {}).get("pgid_clean") is not True
            or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
        ):
            raise ValueError(f"natural delayed pixel {variant} runtime provenance mismatch")
        transactions[variant], states[variant] = _phase_transaction(
            source, variant, graphics[variant], palette, runtime
        )
        audits[variant] = audit
        guards[variant] = guard

    memory = {
        name: _diff(
            states["baseline"].read_memory(address, size),
            states["candidate"].read_memory(address, size),
        )
        for name, (address, size) in DOMAINS.items()
    }
    if memory != {
        **{name: [] for name in DOMAINS},
        "VRAM": [runtime["vram_difference_offset"]],
    }:
        raise ValueError("natural delayed pixel runtime memory isolation mismatch")
    expected_oam = b"".join(int(value, 16).to_bytes(2, "little") for value in profile["runtime_oam"]["attributes"])
    oam_address = HARDWARE_OAM + runtime["oam_index"] * 8
    if any(
        state.read_memory(oam_address, 6) != expected_oam
        for state in states.values()
    ):
        raise ValueError("natural delayed pixel runtime OAM mismatch")
    rendered = {
        variant: render_checkpoint(source / f"runs/{variant}/output/ack-post/capture.ss9")[0]
        for variant in VARIANTS
    }
    pixels = _pixel_changes(rendered["baseline"], rendered["candidate"])
    expected_pixel = {
        "x": profile["screen_xy"][0],
        "y": profile["screen_xy"][1],
        "before_rgb": profile["before_rgb"],
        "after_rgb": profile["after_rgb"],
    }
    if pixels != [expected_pixel]:
        raise ValueError("natural delayed pixel final compositor mismatch")

    output.mkdir(parents=True, exist_ok=True)
    _save_rgb(output / "baseline.png", rendered["baseline"])
    _save_rgb(output / "candidate.png", rendered["candidate"])
    raw_inventory = _write_tar(
        source, _raw_paths(source, profile["group_id"]), output / "raw.tar"
    )
    runs = []
    for variant in VARIANTS:
        rss = guards[variant].get("peak_tree_rss_mib")
        runs.append({
            "variant": variant,
            "rom_sha256": build["variants"][variant]["rom_sha256"],
            "profile_sha256": _sha256_file(source / f"runs/{variant}/profile.json"),
            "audit_sha256": _sha256_file(source / f"runs/{variant}/output/audit.json"),
            "guard_summary_sha256": _sha256_file(source / f"runs/{variant}/guard-summary.json"),
            "ack_state_sha256": _sha256_file(source / f"runs/{variant}/output/ack-post/capture.ss9"),
            "peak_tree_rss_mib": rss,
            "pgid_clean": batch_rows[variant]["pgid_clean"],
            "phase_transaction": transactions[variant],
        })
    input_evidence = {
        "mode": inputs["mode"],
        "inputs": inputs["events"],
        "path": profile["input_state"],
        "sha256": profile["input_state_sha256"],
        "evidence": profile["input_evidence"],
        "evidence_sha256": profile["input_evidence_sha256"],
    }
    if inputs["mode"] == "explicit-input-sequence":
        input_evidence.update({
            "capture_frame": inputs["capture_frame"],
            "timeout_frames": inputs["timeout_frames"],
        })
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "verified": True,
        "profile": profile_path.relative_to(root).as_posix(),
        "profile_sha256": _sha256_file(profile_path),
        "group_id": profile["group_id"],
        "sequence_id": profile["sequence_id"],
        "input": input_evidence,
        "scope": {
            "execution_mode": "natural-delayed-object",
            "production_resource_relocation": True,
            "natural_gameplay_route": True,
            "production_natural_pixel_ab": expected_coverage,
            "single_group_single_frame_single_pixel": True,
            "all_18_effect_groups_runtime_verified": False,
            "physical_gba_verified": False,
        },
        "edit": build["edit"],
        "build": {
            "manifest_sha256": _sha256_file(source / "build/build-manifest.json"),
            "same_patch_topology": True,
            "same_encoded_size": True,
            "probe_free": True,
            "encoded_graphics_size": profile["expected_encoded_size"],
            "allocation_offset": profile["graphics_allocation_offset"],
            "source_pointer_offsets": profile["source_pointer_offsets"],
            "pointer_offsets": profile["target_pointer_offsets"],
        },
        "runs": runs,
        "runtime": {
            "graphics_difference_offsets": [profile["graphics_byte_offset"]],
            "memory_differences": memory,
            "memory_absolute_difference": (
                f"0x{0x06000000 + runtime['vram_difference_offset']:08X}"
            ),
            "pixel_changes": pixels,
            "pixel_render_source": "offline-mode0-from-ack-savestate",
            "oam_index": runtime["oam_index"],
            "oam_attributes": profile["runtime_oam"]["attributes"],
            "palette_equal": True,
            "full_source_palette_equal": True,
        },
        "parent_natural_phase_verifier": parent,
        "raw_inventory": raw_inventory,
        "boundary": profile["boundary"],
    }
    _write_json(output / "evidence.json", evidence)
    artifact_path = (
        f"artifacts/battle-effect-group{profile['group_id']:02d}-natural-pixel-ab-v1"
    )
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": EVIDENCE_SCHEMA,
        "artifact_status": "accepted",
        "files": {
            name: _sha256_file(output / name)
            for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar")
        },
        "repository_files": {path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS},
        "profile": evidence["profile"],
        "profile_sha256": evidence["profile_sha256"],
        "verifier": {
            "command": [
                "python3", "tools/verify_natural_delayed_battle_effect_pixel_ab.py",
                "--root", ".", "--artifact", artifact_path,
            ],
            "exit_code": 0,
        },
        "boundary": profile["boundary"],
    }
    _write_json(output / "manifest.json", manifest)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_evidence(args.root, args.profile, args.source, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
