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
from tools.verify_battle_effect_frame_phase import verify_artifact as verify_phase_artifact
from tools.verify_menu_portrait_writeback_audit import _encode_lz77


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PROFILE = "sequel/content/battle-effect-natural-pixel-ab/group-03-tool67-expiry.json"
PROFILE_SCHEMA = "natural-delayed-battle-effect-pixel-ab-profile-v1"
BUILD_SCHEMA = "natural-delayed-battle-effect-pixel-ab-build-v1"
EVIDENCE_SCHEMA = "natural-delayed-battle-effect-pixel-ab-runtime-v1"
ARTIFACT_ID = "battle-effect-group03-natural-pixel-ab-v1"
VARIANTS = ("baseline", "candidate")
PHASES = ("renderer-post", "submit-post", "ack-post")
PHASE_ADDRESSES = (0x08063328, 0x08061126, 0x080612AA)
PHASE_PENDING = (0, 1, 0)
SUBMISSION_COUNTS = (1, 1, 2)
DEFINITION = 0x083425D8
ANIMATION = 0x083426CC
TASK_SLOT = 126
TILE_BASE = 288
PALETTE_BANK = 5
GRAPHICS_ADDRESS = 0x06012400
PALETTE_ADDRESS = 0x050002A0
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
EXPECTED_SCOPE = {
    "execution_mode": "natural-delayed-object",
    "production_resource_relocation": True,
    "natural_gameplay_route": True,
    "production_natural_pixel_ab": "6/18",
    "single_group_single_frame_single_pixel": True,
    "all_18_effect_groups_runtime_verified": False,
    "physical_gba_verified": False,
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


def _verify_profile(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("profile") != PROFILE:
        raise ValueError("natural delayed pixel profile path mismatch")
    path = _safe_file(root, PROFILE, "profile")
    profile = _json(path)
    if (
        manifest.get("profile_sha256") != _sha256_file(path)
        or profile.get("schema") != PROFILE_SCHEMA
        or profile.get("profile_id") != "group-03-tool67-expiry-pixel"
        or profile.get("group_id") != 3
        or profile.get("sequence_id") != 3
        or profile.get("execution_mode") != "natural-delayed-object"
        or profile.get("natural_gameplay_route") is not True
        or profile.get("production_resource_relocation") is not True
        or profile.get("input_mode") != "zero-input-active-state"
        or profile.get("source_natural_phase_artifact")
        != "artifacts/battle-effect-frame-phase-group3-natural-v1"
        or profile.get("delayed_object") != {
            "slot": 3, "state": 1, "ninja_tool_id": 67,
            "encoded_action": "0xC3", "remaining_turns": 0,
            "expiry_action": "0xE4", "resource_group_id": 3,
        }
        or profile.get("source_pointer_offsets") != [0x59912C, 0x599134]
        or profile.get("target_pointer_offsets") != [0x599134]
        or profile.get("graphics_allocation_offset") != 0xB40000
        or profile.get("expected_encoded_size") != 5294
        or profile.get("graphics_byte_offset") != 207
        or profile.get("before_byte") != 3
        or profile.get("after_byte") != 14
        or profile.get("screen_xy") != [70, 91]
        or profile.get("runtime_oam") != {
            "phase": "ack-post", "oam_index": 0,
            "attributes": ["0x0050", "0x8030", "0x5920"],
            "obj_tile_base": 288, "palette_bank": 5,
            "obj_vram_address": "0x06012400",
        }
    ):
        raise ValueError("natural delayed pixel profile contract mismatch")
    for key in ("input_state", "input_evidence", "source_graphics", "source_palette", "source_natural_phase_manifest"):
        file = _safe_file(root, profile.get(key), key)
        if _sha256_file(file) != profile.get(f"{key}_sha256"):
            raise ValueError(f"natural delayed pixel {key} hash mismatch")
    for key in ("resource_pairs", "animations", "sequence_bindings"):
        file = _safe_file(root, profile.get("catalogs", {}).get(key), key)
        if _sha256_file(file) != profile["catalogs"].get(f"{key}_sha256"):
            raise ValueError(f"natural delayed pixel {key} hash mismatch")
    parent = verify_phase_artifact(root / profile["source_natural_phase_artifact"])
    if not parent.get("verified") or parent.get("group_id") != 3:
        raise ValueError("natural delayed pixel parent phase is not verified")
    return profile


def _verify_build(root: Path, raw: Path, profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bytes]]:
    build = _json(raw / "build/build-manifest.json")
    batch = _json(raw / "batch-audit.json")
    if (
        build.get("schema") != BUILD_SCHEMA
        or build.get("profile") != PROFILE
        or build.get("profile_sha256") != _sha256_file(root / PROFILE)
        or build.get("group_id") != 3
        or build.get("sequence_id") != 3
        or build.get("natural_gameplay_route") is not True
        or build.get("input_mode") != "zero-input-active-state"
        or build.get("probe_free") is not True
        or build.get("same_patch_topology") is not True
        or build.get("same_encoded_size") is not True
        or build.get("source_pointer_offsets") != [0x59912C, 0x599134]
        or build.get("target_pointer_offsets") != [0x599134]
        or batch.get("schema") != "natural-delayed-battle-effect-pixel-ab-batch-v1"
        or batch.get("natural_gameplay_route") is not True
        or batch.get("input_mode") != "zero-input-active-state"
        or batch.get("build_manifest_sha256") != _sha256_file(raw / "build/build-manifest.json")
    ):
        raise ValueError("natural delayed pixel build contract mismatch")
    source = (root / profile["source_graphics"]).read_bytes()
    candidate = bytearray(source)
    candidate[207] = 14
    graphics = {"baseline": source, "candidate": bytes(candidate)}
    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("natural delayed pixel base ROM mismatch")
    for variant in VARIANTS:
        row = build.get("variants", {}).get(variant, {})
        payload = (raw / f"build/{variant}/group-03-graphics-4bpp.bin").read_bytes()
        if payload != graphics[variant]:
            raise ValueError(f"natural delayed pixel {variant} graphics mismatch")
        encoded = _encode_lz77(payload)
        output = bytearray(base)
        output.extend(b"\xFF" * (0x1000000 - len(output)))
        output[0xB40000:0xB40000 + len(encoded)] = encoded
        output[0x599134:0x599138] = (0x08B40000).to_bytes(4, "little")
        ledger = row.get("patch_ledger")
        if (
            row.get("rom_sha256") != _sha256(output)
            or row.get("rom_size") != 0x1000000
            or row.get("graphics_sha256") != _sha256(payload)
            or row.get("encoded_graphics_size") != 5294
            or row.get("graphics_allocation_offset") != 0xB40000
            or row.get("redirect_pointer_offsets") != [0x599134]
            or not isinstance(ledger, list)
            or len(ledger) != 2
            or ledger[0].get("kind") != "allocation"
            or ledger[0].get("offset") != 0xB40000
            or ledger[0].get("size") != 5294
            or ledger[0].get("after_sha256") != _sha256(encoded)
            or ledger[1].get("kind") != "redirect"
            or ledger[1].get("offset") != 0x599134
            or ledger[1].get("after_hex") != "0000b408"
            or ledger[1].get("target_pointer_offsets") != [0x599134]
        ):
            raise ValueError(f"natural delayed pixel {variant} reconstruction mismatch")
    if _diff(graphics["baseline"], graphics["candidate"]) != [207]:
        raise ValueError("natural delayed pixel authored graphics isolation mismatch")
    return build, graphics


def _verify_phase(raw: Path, variant: str, graphics: bytes, palette: bytes) -> tuple[dict[str, Any], Any]:
    run = raw / f"runs/{variant}"
    audit = _json(run / "output/audit.json")
    guard = _json(run / "guard-summary.json")
    run_profile = _json(run / "profile.json")
    if (
        run_profile.get("execution_mode") != "natural-delayed-object-pixel-ab"
        or run_profile.get("natural_gameplay_route") is not True
        or run_profile.get("input_mode") != "zero-input-active-state"
        or run_profile.get("inputs") != []
        or run_profile.get("variant") != variant
        or audit.get("outcome") != "three-phase-captured"
        or audit.get("inputs") != []
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
        targets = _target_tasks(state, DEFINITION, ANIMATION)
        if (
            state.registers[15] - 2 != PHASE_ADDRESSES[index]
            or meta.get("name") != phase
            or meta.get("address") != f"0x{PHASE_ADDRESSES[index]:08X}"
            or meta.get("pending") != PHASE_PENDING[index]
            or state.read_memory(PENDING, 1)[0] != PHASE_PENDING[index]
            or cycle <= previous_cycle
            or len(targets) != 1
            or targets[0]["slot"] != TASK_SLOT
            or targets[0]["slot"] not in _active_slots(state)
            or targets[0]["tile_base"] != TILE_BASE
            or targets[0]["palette_bank"] != PALETTE_BANK
            or state.read_memory(GRAPHICS_ADDRESS, len(graphics)) != graphics
            or state.read_memory(PALETTE_ADDRESS, len(palette)) != palette
            or (phase_root / "capture-submission.bin").read_bytes()
            != bytes([PHASE_PENDING[index], SUBMISSION_COUNTS[index]])
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
    if shadow == old_hardware or states[1].read_memory(HARDWARE_OAM, 0x400) != old_hardware or states[2].read_memory(HARDWARE_OAM, 0x400) != shadow:
        raise ValueError(f"natural delayed pixel {variant} OAM transaction mismatch")
    return ({
        "addresses": [f"0x{value:08X}" for value in PHASE_ADDRESSES],
        "pending": list(PHASE_PENDING),
        "frames": frames,
        "cycles": cycles,
        "savestate_sha256": hashes,
        "renderer_shadow_differs_from_old_hardware": True,
        "submit_hardware_unchanged": True,
        "ack_hardware_equals_renderer_shadow": True,
    }, states[2])


def _verify(root: Path, artifact: Path) -> None:
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
    profile = _verify_profile(root, manifest)
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
        build, graphics = _verify_build(root, raw, profile)
        palette = (root / profile["source_palette"]).read_bytes()
        states = {}
        transactions = {}
        for variant in VARIANTS:
            transactions[variant], states[variant] = _verify_phase(raw, variant, graphics[variant], palette)
            if _json(raw / f"runs/{variant}/output/audit.json").get("rom_sha256") != build["variants"][variant]["rom_sha256"]:
                raise ValueError(f"natural delayed pixel {variant} ROM provenance mismatch")
        memory = {
            name: _diff(states["baseline"].read_memory(address, size), states["candidate"].read_memory(address, size))
            for name, (address, size) in DOMAINS.items()
        }
        if memory != {**{name: [] for name in DOMAINS}, "VRAM": [0x124CF]}:
            raise ValueError("natural delayed pixel runtime memory isolation mismatch")
        rendered = {
            variant: render_checkpoint(raw / f"runs/{variant}/output/ack-post/capture.ss9")[0]
            for variant in VARIANTS
        }
        if any(rendered[variant] != _png_rgb(artifact / f"{variant}.png") for variant in VARIANTS):
            raise ValueError("natural delayed pixel promoted PNG mismatch")
        pixels = _pixel_changes(rendered["baseline"], rendered["candidate"])
    expected_pixel = [{
        "x": 70, "y": 91,
        "before_rgb": [247, 115, 0],
        "after_rgb": [115, 107, 99],
    }]
    expected_input = {
        "mode": "zero-input-active-state", "inputs": [],
        "path": profile["input_state"], "sha256": profile["input_state_sha256"],
        "evidence": profile["input_evidence"],
        "evidence_sha256": profile["input_evidence_sha256"],
    }
    runs = {row.get("variant"): row for row in evidence.get("runs", []) if isinstance(row, dict)}
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("verified") is not True
        or evidence.get("profile") != PROFILE
        or evidence.get("profile_sha256") != _sha256_file(root / PROFILE)
        or evidence.get("group_id") != 3
        or evidence.get("sequence_id") != 3
        or evidence.get("input") != expected_input
        or evidence.get("scope") != EXPECTED_SCOPE
        or evidence.get("edit") != build["edit"]
        or evidence.get("build") != {
            "manifest_sha256": build_manifest_sha256,
            "same_patch_topology": True, "same_encoded_size": True,
            "probe_free": True, "encoded_graphics_size": 5294,
            "allocation_offset": 0xB40000,
            "source_pointer_offsets": [0x59912C, 0x599134],
            "pointer_offsets": [0x599134],
        }
        or set(runs) != set(VARIANTS)
        or any(runs[variant].get("phase_transaction") != transactions[variant] for variant in VARIANTS)
        or evidence.get("runtime") != {
            "graphics_difference_offsets": [207],
            "memory_differences": memory,
            "memory_absolute_difference": "0x060124CF",
            "pixel_changes": pixels,
            "pixel_render_source": "offline-mode0-from-ack-savestate",
            "oam_index": 0,
            "oam_attributes": ["0x0050", "0x8030", "0x5920"],
            "palette_equal": True,
            "full_source_palette_equal": True,
        }
        or pixels != expected_pixel
        or evidence.get("parent_natural_phase_verifier", {}).get("verified") is not True
        or evidence.get("boundary") != profile["boundary"]
    ):
        raise ValueError("natural delayed pixel signed semantic evidence mismatch")


def verify_evidence(root: Path, artifact: Path) -> dict[str, Any]:
    try:
        _verify(Path(root), Path(artifact))
    except (OSError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError, tarfile.TarError) as error:
        return {"errors": [str(error)], "verified": False}
    return {"errors": [], "group_id": 3, "natural_gameplay_route": True, "verified": True}


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
