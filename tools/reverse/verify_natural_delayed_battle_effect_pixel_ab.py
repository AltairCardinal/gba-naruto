#!/usr/bin/env python3
"""Independently verify natural delayed-effect production pixel A/B evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import sys
import tarfile
import tempfile
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint
from tools.verify_battle_effect_direct_spawn_runtime import _active_slots, _target_tasks
from tools.verify_battle_effect_frame_phase import (
    expected_phase_inputs,
    verify_artifact as verify_phase_artifact,
)
from tools.verify_menu_portrait_writeback_audit import _encode_lz77


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PROFILE_SCHEMA = "natural-delayed-battle-effect-pixel-ab-profile-v1"
BUILD_SCHEMA = "natural-delayed-battle-effect-pixel-ab-build-v1"
EVIDENCE_SCHEMA = "natural-delayed-battle-effect-pixel-ab-runtime-v1"
VARIANTS = ("baseline", "candidate")
PHASES = ("renderer-post", "submit-post", "ack-post")
PHASE_ADDRESSES = (0x08063328, 0x08061126, 0x080612AA)
PHASE_PENDING = (0, 1, 0)
SHADOW_OAM = 0x0300027C
HARDWARE_OAM = 0x07000000
PENDING = 0x0300067C
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "IWRAM": (0x03000000, 0x8000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "VRAM": (0x06000000, 0x18000),
    "OAM": (0x07000000, 0x400),
}
ROUTE_CONTRACTS = {
    (3, 3): {
        "profile": "sequel/content/battle-effect-natural-pixel-ab/group-03-tool67-expiry.json",
        "profile_id": "group-03-tool67-expiry-pixel",
        "input_mode": "zero-input-active-state",
        "phase_artifact": "artifacts/battle-effect-frame-phase-group3-natural-v1",
        "delayed_object": {
            "slot": 3, "state": 1, "ninja_tool_id": 67,
            "encoded_action": "0xC3", "remaining_turns": 0,
            "expiry_action": "0xE4", "resource_group_id": 3,
        },
        "source_pointer_offsets": [0x59912C, 0x599134],
        "target_pointer_offsets": [0x599134],
        "coverage": "6/18",
    },
    (18, 7): {
        "profile": "sequel/content/battle-effect-natural-pixel-ab/group-18-tool67-zero-event-expiry.json",
        "profile_id": "group-18-tool67-zero-event-expiry-pixel",
        "input_mode": "explicit-input-sequence",
        "phase_artifact": "artifacts/battle-effect-frame-phase-group18-natural-sequence-v1",
        "delayed_object": {
            "slot": 3, "state": 1, "x": 13, "y": 6,
            "ninja_tool_id": 67, "encoded_action": "0xC3",
            "remaining_turns": 2, "resource_group_id": 18,
        },
        "source_pointer_offsets": [0x5991AC],
        "target_pointer_offsets": [0x5991AC],
        "coverage": "9/18",
    },
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _safe_file(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"natural delayed pixel {label} is not a repository path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"natural delayed pixel {label} is unsafe")
    path = (root / relative).resolve(strict=True)
    if root not in path.parents or not path.is_file():
        raise ValueError(f"natural delayed pixel {label} escapes repository")
    return path


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


def _png_rgb(path: Path) -> bytes:
    with Image.open(path) as image:
        image.load()
        if image.size != (240, 160):
            raise ValueError("natural delayed pixel PNG geometry mismatch")
        return image.convert("RGB").tobytes()


def _tar_payloads(path: Path) -> dict[str, bytes]:
    payloads = {}
    with tarfile.open(path, "r:") as archive:
        members = archive.getmembers()
        if not 80 <= len(members) <= 110:
            raise ValueError("natural delayed pixel raw member count mismatch")
        for member in members:
            pure = PurePosixPath(member.name)
            if (
                not member.isfile()
                or pure.is_absolute()
                or ".." in pure.parts
                or member.name in payloads
                or member.size > 2 * 1024 * 1024
            ):
                raise ValueError("natural delayed pixel raw member is unsafe")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("natural delayed pixel raw member is unreadable")
            payloads[member.name] = stream.read()
    return payloads


def _materialize(payloads: dict[str, bytes], root: Path) -> None:
    for name, data in payloads.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _verify_profile(
    root: Path, manifest: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    profile_relative = manifest.get("profile")
    path = _safe_file(root, profile_relative, "profile")
    profile = _json(path)
    group_id = profile.get("group_id")
    sequence_id = profile.get("sequence_id")
    route = (group_id, sequence_id)
    contract = ROUTE_CONTRACTS.get(route)
    if (
        contract is None
        or profile_relative != contract["profile"]
        or manifest.get("profile_sha256") != _sha256_file(path)
        or profile.get("schema") != PROFILE_SCHEMA
        or profile.get("profile_id") != contract["profile_id"]
        or profile.get("execution_mode") != "natural-delayed-object"
        or profile.get("natural_gameplay_route") is not True
        or profile.get("production_resource_relocation") is not True
        or profile.get("input_mode") != contract["input_mode"]
        or profile.get("source_natural_phase_artifact") != contract["phase_artifact"]
        or profile.get("delayed_object") != contract["delayed_object"]
        or profile.get("source_pointer_offsets") != contract["source_pointer_offsets"]
        or profile.get("target_pointer_offsets") != contract["target_pointer_offsets"]
        or profile.get(
            "expected_production_natural_pixel_coverage", contract["coverage"]
        ) != contract["coverage"]
    ):
        raise ValueError("natural delayed pixel profile contract mismatch")
    for key in (
        "input_state", "input_evidence", "source_graphics", "source_palette",
        "source_natural_phase_manifest",
    ):
        file = _safe_file(root, profile.get(key), key)
        if _sha256_file(file) != profile.get(f"{key}_sha256"):
            raise ValueError(f"natural delayed pixel {key} hash mismatch")
    catalogs = profile.get("catalogs")
    if not isinstance(catalogs, dict):
        raise ValueError("natural delayed pixel catalog contract mismatch")
    for key in ("resource_pairs", "animations", "sequence_bindings"):
        file = _safe_file(root, catalogs.get(key), key)
        if _sha256_file(file) != catalogs.get(f"{key}_sha256"):
            raise ValueError(f"natural delayed pixel {key} hash mismatch")
    try:
        input_mode, input_events = expected_phase_inputs(profile)
    except ValueError as error:
        raise ValueError(f"natural delayed pixel input sequence mismatch: {error}") from error
    phase_artifact = root / profile["source_natural_phase_artifact"]
    parent = verify_phase_artifact(phase_artifact)
    if not parent.get("verified") or parent.get("group_id") != group_id:
        raise ValueError("natural delayed pixel parent phase is not verified")
    phase_manifest = _json(root / profile["source_natural_phase_manifest"])
    if (
        phase_manifest.get("artifact_status") != "accepted"
        or phase_manifest.get("group_id") != group_id
        or phase_manifest.get("input_mode") != input_mode
        or phase_manifest.get("inputs") != input_events
        or phase_manifest.get("input_state")
        != {"path": profile["input_state"], "sha256": profile["input_state_sha256"]}
    ):
        raise ValueError("natural delayed pixel parent phase contract mismatch")
    phases = phase_manifest.get("phase_sequence")
    task_slots = {
        row.get("task_slot") for row in phases if isinstance(row, dict)
    } if isinstance(phases, list) else set()
    animations = _json(root / catalogs["animations"])
    animation_rows = [
        row for row in animations.get("groups", [])
        if isinstance(row, dict) and row.get("group_id") == group_id
    ]
    runtime_oam = profile.get("runtime_oam")
    if (
        len(phases or []) != 3
        or len(task_slots) != 1
        or len(animation_rows) != 1
        or not isinstance(runtime_oam, dict)
        or runtime_oam.get("phase") != "ack-post"
    ):
        raise ValueError("natural delayed pixel runtime identity mismatch")
    try:
        attributes = [int(value, 16) for value in runtime_oam["attributes"]]
        runtime = {
            "definition": int(animation_rows[0]["definition_pointer_table"], 16),
            "animation": int(animation_rows[0]["animation_pointer_table"], 16),
            "task_slot": next(iter(task_slots)),
            "tile_base": int(runtime_oam["obj_tile_base"]),
            "palette_bank": int(runtime_oam["palette_bank"]),
            "graphics_address": int(runtime_oam["obj_vram_address"], 16),
            "oam_index": int(runtime_oam["oam_index"]),
            "oam_attributes": attributes,
            "renderer_shadow_change": runtime_oam.get(
                "renderer_shadow_change", True
            ),
        }
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("natural delayed pixel runtime OAM mismatch") from error
    runtime["palette_address"] = 0x05000200 + runtime["palette_bank"] * 32
    runtime["vram_difference_offset"] = (
        runtime["graphics_address"] - 0x06000000 + profile["graphics_byte_offset"]
    )
    if (
        len(attributes) != 3
        or not isinstance(runtime["renderer_shadow_change"], bool)
        or not 0 <= runtime["oam_index"] < 128
        or attributes[2] & 0x3FF != runtime["tile_base"]
        or attributes[2] >> 12 != runtime["palette_bank"]
        or not 0x06010000 <= runtime["graphics_address"] < 0x06018000
    ):
        raise ValueError("natural delayed pixel runtime OAM mismatch")
    state = load_gba_state(phase_artifact / "raw/ack-post/capture.ss9")
    graphics = (root / profile["source_graphics"]).read_bytes()
    palette = (root / profile["source_palette"]).read_bytes()
    oam = state.read_memory(HARDWARE_OAM + runtime["oam_index"] * 8, 6)
    if (
        oam != struct.pack("<HHH", *attributes)
        or state.read_memory(runtime["graphics_address"], len(graphics)) != graphics
        or state.read_memory(runtime["palette_address"], len(palette)) != palette
    ):
        raise ValueError("natural delayed pixel parent resource mismatch")
    runtime["submission_counts"] = [
        (phase_artifact / f"raw/{phase}/capture-submission.bin").read_bytes()[1]
        for phase in PHASES
    ]
    inputs = {
        "mode": input_mode,
        "events": input_events,
        "raw": profile.get("inputs", []),
        "capture_frame": profile.get("capture_frame"),
        "timeout_frames": profile.get("timeout_frames"),
    }
    return profile, runtime, inputs


def _verify_build(
    root: Path,
    raw: Path,
    profile: dict[str, Any],
    inputs: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, bytes]]:
    build = _json(raw / "build/build-manifest.json")
    batch = _json(raw / "batch-audit.json")
    group_id = profile["group_id"]
    if (
        build.get("schema") != BUILD_SCHEMA
        or build.get("profile") != ROUTE_CONTRACTS[(group_id, profile["sequence_id"])]["profile"]
        or build.get("profile_sha256")
        != _sha256_file(root / ROUTE_CONTRACTS[(group_id, profile["sequence_id"])]["profile"])
        or build.get("group_id") != group_id
        or build.get("sequence_id") != profile["sequence_id"]
        or build.get("natural_gameplay_route") is not True
        or build.get("input_mode") != inputs["mode"]
        or build.get("inputs", []) != inputs["raw"]
        or build.get("capture_frame") != inputs["capture_frame"]
        or build.get("timeout_frames") != inputs["timeout_frames"]
        or build.get("probe_free") is not True
        or build.get("same_patch_topology") is not True
        or build.get("same_encoded_size") is not True
        or build.get("source_pointer_offsets") != profile["source_pointer_offsets"]
        or build.get("target_pointer_offsets") != profile["target_pointer_offsets"]
        or batch.get("schema") != "natural-delayed-battle-effect-pixel-ab-batch-v1"
        or batch.get("natural_gameplay_route") is not True
        or batch.get("input_mode") != inputs["mode"]
        or batch.get("inputs", []) != inputs["raw"]
        or batch.get("capture_frame") != inputs["capture_frame"]
        or batch.get("timeout_frames") != inputs["timeout_frames"]
        or batch.get("build_manifest_sha256") != _sha256_file(raw / "build/build-manifest.json")
    ):
        raise ValueError("natural delayed pixel build contract mismatch")
    source = (root / profile["source_graphics"]).read_bytes()
    if source[profile["graphics_byte_offset"]] != profile["before_byte"]:
        raise ValueError("natural delayed pixel authored source byte mismatch")
    candidate = bytearray(source)
    candidate[profile["graphics_byte_offset"]] = profile["after_byte"]
    graphics = {"baseline": source, "candidate": bytes(candidate)}
    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("natural delayed pixel base ROM mismatch")
    for variant in VARIANTS:
        row = build.get("variants", {}).get(variant, {})
        payload = (
            raw / f"build/{variant}/group-{group_id:02d}-graphics-4bpp.bin"
        ).read_bytes()
        if payload != graphics[variant]:
            raise ValueError(f"natural delayed pixel {variant} graphics mismatch")
        encoded = _encode_lz77(payload)
        output = bytearray(base)
        output.extend(b"\xFF" * (0x1000000 - len(output)))
        allocation = profile["graphics_allocation_offset"]
        pointer = 0x08000000 + allocation
        output[allocation:allocation + len(encoded)] = encoded
        for offset in profile["target_pointer_offsets"]:
            output[offset:offset + 4] = pointer.to_bytes(4, "little")
        ledger = row.get("patch_ledger")
        if (
            row.get("rom_sha256") != _sha256(output)
            or row.get("rom_size") != 0x1000000
            or row.get("graphics_sha256") != _sha256(payload)
            or row.get("encoded_graphics_size") != profile["expected_encoded_size"]
            or row.get("graphics_allocation_offset") != allocation
            or row.get("redirect_pointer_offsets") != profile["target_pointer_offsets"]
            or not isinstance(ledger, list)
            or len(ledger) != 2
            or ledger[0].get("kind") != "allocation"
            or ledger[0].get("offset") != allocation
            or ledger[0].get("size") != profile["expected_encoded_size"]
            or ledger[0].get("after_sha256") != _sha256(encoded)
            or ledger[1].get("kind") != "redirect"
            or ledger[1].get("offset") != profile["pair_pointer_offset"]
            or ledger[1].get("after_hex") != pointer.to_bytes(4, "little").hex()
            or ledger[1].get("target_pointer_offsets") != profile["target_pointer_offsets"]
        ):
            raise ValueError(f"natural delayed pixel {variant} reconstruction mismatch")
    if _diff(graphics["baseline"], graphics["candidate"]) != [
        profile["graphics_byte_offset"]
    ]:
        raise ValueError("natural delayed pixel authored graphics isolation mismatch")
    return build, graphics


def _verify_phase(
    raw: Path,
    variant: str,
    graphics: bytes,
    palette: bytes,
    runtime: dict[str, Any],
    inputs: dict[str, Any],
) -> tuple[dict[str, Any], Any]:
    run = raw / f"runs/{variant}"
    audit = _json(run / "output/audit.json")
    guard = _json(run / "guard-summary.json")
    run_profile = _json(run / "profile.json")
    try:
        run_input_mode, run_input_events = expected_phase_inputs(run_profile)
    except ValueError as error:
        raise ValueError(
            f"natural delayed pixel {variant} input profile mismatch: {error}"
        ) from error
    if (
        run_profile.get("execution_mode") != "natural-delayed-object-pixel-ab"
        or run_profile.get("natural_gameplay_route") is not True
        or run_input_mode != inputs["mode"]
        or run_input_events != inputs["events"]
        or run_profile.get("variant") != variant
        or audit.get("outcome") != "three-phase-captured"
        or audit.get("input_mode") != inputs["mode"]
        or audit.get("inputs") != inputs["events"]
        or audit.get("automatic_inputs") != []
        or audit.get("recovery_inputs") != []
        or guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or audit.get("runtime_residue", {}).get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
    ):
        raise ValueError(f"natural delayed pixel {variant} run contract mismatch")
    states = []
    metas = []
    frames = []
    cycles = []
    hashes = []
    previous_cycle = -1
    for index, phase in enumerate(PHASES):
        phase_root = run / f"output/{phase}"
        state_path = phase_root / "capture.ss9"
        state = load_gba_state(state_path)
        meta = _json(phase_root / "capture-phase.json")
        cycle = int(meta.get("cycle", -1))
        targets = _target_tasks(
            state, runtime["definition"], runtime["animation"]
        )
        if (
            state.registers[15] - 2 != PHASE_ADDRESSES[index]
            or meta.get("name") != phase
            or meta.get("address") != f"0x{PHASE_ADDRESSES[index]:08X}"
            or meta.get("pending") != PHASE_PENDING[index]
            or state.read_memory(PENDING, 1)[0] != PHASE_PENDING[index]
            or cycle <= previous_cycle
            or len(targets) != 1
            or targets[0]["slot"] != runtime["task_slot"]
            or targets[0]["slot"] not in _active_slots(state)
            or targets[0]["tile_base"] != runtime["tile_base"]
            or targets[0]["palette_bank"] != runtime["palette_bank"]
            or state.read_memory(runtime["graphics_address"], len(graphics)) != graphics
            or state.read_memory(runtime["palette_address"], len(palette)) != palette
            or (phase_root / "capture-submission.bin").read_bytes()
            != bytes([PHASE_PENDING[index], runtime["submission_counts"][index]])
        ):
            raise ValueError(f"natural delayed pixel {variant} phase mismatch: {phase}")
        for name, (start, size) in {
            "capture-task-pool.bin": (0x03003BB8, 128 * 0x3C),
            "capture-active-count.bin": (0x03005BB8, 1),
            "capture-active-pointers.bin": (0x030059B8, 512),
            "capture-shadow-oam.bin": (SHADOW_OAM, 0x400),
            "capture-hardware-oam.bin": (HARDWARE_OAM, 0x400),
            "capture-pram.bin": (0x05000000, 0x400),
            "capture-vram.bin": (0x06000000, 0x18000),
        }.items():
            if (phase_root / name).read_bytes() != state.read_memory(start, size):
                raise ValueError(f"natural delayed pixel {variant} phase dump mismatch")
        for path in phase_root.iterdir():
            if path.is_file() and audit.get("files", {}).get(f"{phase}/{path.name}") != _sha256_file(path):
                raise ValueError(f"natural delayed pixel {variant} phase hash mismatch")
        previous_cycle = cycle
        states.append(state)
        metas.append(meta)
        frames.append(meta.get("frame"))
        cycles.append(str(cycle))
        hashes.append(_sha256_file(state_path))
    if audit.get("phases") != metas or audit.get("ack_hit_count") != 1:
        raise ValueError(f"natural delayed pixel {variant} phase audit mismatch")
    shadow = states[0].read_memory(SHADOW_OAM, 0x400)
    old_hardware = states[0].read_memory(HARDWARE_OAM, 0x400)
    renderer_changed = shadow != old_hardware
    if (
        renderer_changed is not runtime["renderer_shadow_change"]
        or states[1].read_memory(HARDWARE_OAM, 0x400) != old_hardware
        or states[2].read_memory(HARDWARE_OAM, 0x400) != shadow
        or states[2].read_memory(
            HARDWARE_OAM + runtime["oam_index"] * 8, 6
        ) != struct.pack("<HHH", *runtime["oam_attributes"])
    ):
        raise ValueError(f"natural delayed pixel {variant} OAM transaction mismatch")
    return ({
        "addresses": [f"0x{value:08X}" for value in PHASE_ADDRESSES],
        "pending": list(PHASE_PENDING),
        "frames": frames,
        "cycles": cycles,
        "savestate_sha256": hashes,
        "renderer_shadow_differs_from_old_hardware": renderer_changed,
        "submit_hardware_unchanged": True,
        "ack_hardware_equals_renderer_shadow": True,
    }, states[2])


def _verify(root: Path, artifact: Path) -> int:
    root = root.resolve(strict=True)
    artifact = artifact.resolve(strict=True)
    manifest = _json(artifact / "manifest.json")
    expected_files = {"baseline.png", "candidate.png", "evidence.json", "manifest.json", "raw.tar"}
    actual_files = {path.name for path in artifact.iterdir() if path.is_file()}
    if actual_files != expected_files or any(path.is_symlink() for path in artifact.iterdir()):
        raise ValueError("natural delayed pixel artifact file set mismatch")
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != EVIDENCE_SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("files") != {
            name: _sha256_file(artifact / name)
            for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar")
        }
    ):
        raise ValueError("natural delayed pixel promotion manifest mismatch")
    for path, expected in manifest.get("repository_files", {}).items():
        if _sha256_file(_safe_file(root, path, "repository file")) != expected:
            raise ValueError(f"natural delayed pixel implementation drift: {path}")
    profile, runtime, inputs = _verify_profile(root, manifest)
    group_id = profile["group_id"]
    sequence_id = profile["sequence_id"]
    profile_relative = ROUTE_CONTRACTS[(group_id, sequence_id)]["profile"]
    evidence = _json(artifact / "evidence.json")
    payloads = _tar_payloads(artifact / "raw.tar")
    inventory = evidence.get("raw_inventory")
    if not isinstance(inventory, list) or payloads.keys() != {row.get("path") for row in inventory if isinstance(row, dict)}:
        raise ValueError("natural delayed pixel raw inventory mismatch")
    if inventory != [
        {"path": name, "size": len(data), "sha256": _sha256(data)}
        for name, data in payloads.items()
    ]:
        raise ValueError("natural delayed pixel raw inventory ledger mismatch")
    with tempfile.TemporaryDirectory() as temporary:
        raw = Path(temporary) / "raw"
        _materialize(payloads, raw)
        build_manifest_sha256 = _sha256_file(raw / "build/build-manifest.json")
        build, graphics = _verify_build(root, raw, profile, inputs)
        palette = (root / profile["source_palette"]).read_bytes()
        states = {}
        transactions = {}
        for variant in VARIANTS:
            transactions[variant], states[variant] = _verify_phase(
                raw, variant, graphics[variant], palette, runtime, inputs
            )
            if _json(raw / f"runs/{variant}/output/audit.json").get("rom_sha256") != build["variants"][variant]["rom_sha256"]:
                raise ValueError(f"natural delayed pixel {variant} ROM provenance mismatch")
        memory = {
            name: _diff(states["baseline"].read_memory(address, size), states["candidate"].read_memory(address, size))
            for name, (address, size) in DOMAINS.items()
        }
        if memory != {
            **{name: [] for name in DOMAINS},
            "VRAM": [runtime["vram_difference_offset"]],
        }:
            raise ValueError("natural delayed pixel runtime memory isolation mismatch")
        rendered = {
            variant: render_checkpoint(raw / f"runs/{variant}/output/ack-post/capture.ss9")[0]
            for variant in VARIANTS
        }
        if any(rendered[variant] != _png_rgb(artifact / f"{variant}.png") for variant in VARIANTS):
            raise ValueError("natural delayed pixel promoted PNG mismatch")
        pixels = _pixel_changes(rendered["baseline"], rendered["candidate"])
    expected_pixel = [{
        "x": profile["screen_xy"][0],
        "y": profile["screen_xy"][1],
        "before_rgb": profile["before_rgb"],
        "after_rgb": profile["after_rgb"],
    }]
    expected_input = {
        "mode": inputs["mode"], "inputs": inputs["events"],
        "path": profile["input_state"], "sha256": profile["input_state_sha256"],
        "evidence": profile["input_evidence"],
        "evidence_sha256": profile["input_evidence_sha256"],
    }
    if inputs["mode"] == "explicit-input-sequence":
        expected_input.update({
            "capture_frame": inputs["capture_frame"],
            "timeout_frames": inputs["timeout_frames"],
        })
    expected_scope = {
        "execution_mode": "natural-delayed-object",
        "production_resource_relocation": True,
        "natural_gameplay_route": True,
        "production_natural_pixel_ab": profile.get(
            "expected_production_natural_pixel_coverage",
            ROUTE_CONTRACTS[(group_id, sequence_id)]["coverage"],
        ),
        "single_group_single_frame_single_pixel": True,
        "all_18_effect_groups_runtime_verified": False,
        "physical_gba_verified": False,
    }
    runs = {row.get("variant"): row for row in evidence.get("runs", []) if isinstance(row, dict)}
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("verified") is not True
        or evidence.get("profile") != profile_relative
        or evidence.get("profile_sha256") != _sha256_file(root / profile_relative)
        or evidence.get("group_id") != group_id
        or evidence.get("sequence_id") != sequence_id
        or evidence.get("input") != expected_input
        or evidence.get("scope") != expected_scope
        or evidence.get("edit") != build["edit"]
        or evidence.get("build") != {
            "manifest_sha256": build_manifest_sha256,
            "same_patch_topology": True, "same_encoded_size": True,
            "probe_free": True,
            "encoded_graphics_size": profile["expected_encoded_size"],
            "allocation_offset": profile["graphics_allocation_offset"],
            "source_pointer_offsets": profile["source_pointer_offsets"],
            "pointer_offsets": profile["target_pointer_offsets"],
        }
        or set(runs) != set(VARIANTS)
        or any(runs[variant].get("phase_transaction") != transactions[variant] for variant in VARIANTS)
        or evidence.get("runtime") != {
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
        }
        or pixels != expected_pixel
        or evidence.get("parent_natural_phase_verifier", {}).get("verified") is not True
        or evidence.get("boundary") != profile["boundary"]
    ):
        raise ValueError("natural delayed pixel signed semantic evidence mismatch")
    return group_id


def verify_evidence(root: Path, artifact: Path) -> dict[str, Any]:
    try:
        group_id = _verify(Path(root), Path(artifact))
    except (OSError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError, tarfile.TarError) as error:
        return {"errors": [str(error)], "verified": False}
    return {
        "errors": [],
        "group_id": group_id,
        "natural_gameplay_route": True,
        "verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    result = verify_evidence(args.root, args.artifact)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
