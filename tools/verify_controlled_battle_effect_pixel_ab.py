#!/usr/bin/env python3
"""Independently verify an allowlisted controlled final-pixel A/B artifact."""

from __future__ import annotations

import argparse
import hashlib
import io
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
from tools.verify_battle_effect_direct_spawn_runtime import (
    CASE_ROWS,
    build_expected_probe,
    verify_artifact as verify_direct_artifact,
)
from tools.verify_menu_portrait_writeback_audit import _encode_lz77


EVIDENCE_SCHEMA = "controlled-battle-effect-pixel-ab-runtime-v1"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
VARIANTS = ("baseline", "candidate")
PHASES = ("renderer-post", "submit-post", "ack-post")
PHASE_ADDRESSES = (0x08063328, 0x08061126, 0x080612AA)
PHASE_PENDING = (0, 1, 0)
EXPECTED_RAW_MEMBER_COUNT = 102
MAX_RAW_TAR_BYTES = 4 * 1024 * 1024
MAX_RAW_TOTAL_BYTES = 2 * 1024 * 1024
PENDING = 0x0300067C
SCRATCH = 0x0203FF40
SHADOW_OAM = 0x0300027C
HARDWARE_OAM = 0x07000000
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "IWRAM": (0x03000000, 0x8000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "VRAM": (0x06000000, 0x18000),
    "OAM": (0x07000000, 0x400),
}
IMPLEMENTATION_PATHS = (
    "tools/build_controlled_battle_effect_pixel_ab.py",
    "tools/run_controlled_battle_effect_pixel_ab.py",
    "tools/export_controlled_battle_effect_pixel_ab.py",
    "tools/verify_controlled_battle_effect_pixel_ab.py",
    "tools/build_controlled_battle_effect_direct_spawn_probe.py",
    "tools/verify_battle_effect_direct_spawn_runtime.py",
    "tools/verify_menu_portrait_writeback_audit.py",
    "tools/run_macos_mgba_battle_effect_phase_capture.py",
    "tools/mgba_battle_effect_phase_capture.lua",
    "tools/run_guarded.py",
    "tools/mgba_runtime_safety.py",
    "tools/inspect_mgba_savestate.py",
    "tools/render_mode0_checkpoint.py",
    "tools/import_battle_effect_resource_relocations.py",
    "tools/gba_image_export.py",
    "tests/test_build_controlled_battle_effect_pixel_ab.py",
    "tests/test_run_controlled_battle_effect_pixel_ab.py",
    "tests/test_export_controlled_battle_effect_pixel_ab.py",
    "tests/test_verify_controlled_battle_effect_pixel_ab.py",
)

CASE_CONTRACTS = {
    "group-03-sequence-03-side-0-direct-spawn": {
        "artifact": "artifacts/battle-effect-group03-controlled-pixel-ab-v1",
        "profile": "sequel/content/battle-effect-controlled-pixel-ab/group-03-sequence-03-side-0-direct-spawn.json",
        "group_id": 3,
        "sequence_id": 3,
        "definition": 0x083425D8,
        "animation": 0x083426CC,
        "case_row": 0,
        "graphics_filename": "group-03-graphics-4bpp.bin",
        "task_slot": 109,
        "tile_base": 256,
        "palette_bank": 4,
        "palette_prefix": 30,
        "palette_mismatches": [30, 31],
        "submission_counts": [1, 1, 2],
        "encoded_size": 5294,
        "allocation_offset": 0xB40000,
        "source_pointer_offsets": [0x59912C, 0x599134],
        "target_pointer_offsets": [0x599134],
        "source_graphics_pointer": 0x08340AF8,
        "build_pointer_lists_required": True,
        "graphics_offset": 207,
        "before_byte": 3,
        "after_byte": 14,
        "oam_index": 22,
        "oam_attributes": ["0x0028", "0x9078", "0x4900"],
        "vram_difference": 0x120CF,
        "absolute_difference": "0x060120CF",
        "pixel": {
            "x": 129,
            "y": 51,
            "before_rgb": [247, 115, 0],
            "after_rgb": [115, 107, 99],
        },
    },
    "group-18-sequence-07-direct-spawn": {
        "artifact": "artifacts/battle-effect-group18-controlled-pixel-ab-v1",
        "profile": "sequel/content/battle-effect-controlled-pixel-ab/group-18-sequence-07-direct-spawn.json",
        "group_id": 18,
        "sequence_id": 7,
        "definition": 0x0834819C,
        "animation": 0x083481DC,
        "case_row": 2,
        "graphics_filename": "group-18-graphics-4bpp.bin",
        "task_slot": 109,
        "tile_base": 768,
        "palette_bank": 12,
        "palette_prefix": 32,
        "palette_mismatches": [],
        "submission_counts": [0, 0, 1],
        "encoded_size": 2002,
        "allocation_offset": 0xB40000,
        "source_pointer_offsets": [0x5991AC],
        "target_pointer_offsets": [0x5991AC],
        "source_graphics_pointer": 0x083478F4,
        "build_pointer_lists_required": False,
        "graphics_offset": 202,
        "before_byte": 68,
        "after_byte": 65,
        "oam_index": 17,
        "oam_attributes": ["0x0021", "0x8068", "0xCB00"],
        "vram_difference": 0x160CA,
        "absolute_difference": "0x060160CA",
        "pixel": {
            "x": 124,
            "y": 43,
            "before_rgb": [181, 181, 181],
            "after_rgb": [231, 231, 231],
        },
    },
}


def _expected_verifier(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": [
            "python3",
            "tools/verify_controlled_battle_effect_pixel_ab.py",
            "--root",
            ".",
            "--artifact",
            contract["artifact"],
        ],
        "exit_code": 0,
    }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"controlled pixel expected JSON object: {path}")
    return value


def _json_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"controlled pixel invalid JSON: {label}") from error
    if not isinstance(value, dict):
        raise ValueError(f"controlled pixel JSON is not an object: {label}")
    return value


def _safe_file(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"controlled pixel {label} is not a path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"controlled pixel {label} path is unsafe")
    path = (root / relative).resolve(strict=True)
    if root not in path.parents or not path.is_file():
        raise ValueError(f"controlled pixel {label} escapes repository")
    return path


def _strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _canonical_tar(payloads: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, raw in sorted(payloads.items()):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mode = 0o644
            info.uid = info.gid = info.mtime = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(raw))
    return stream.getvalue()


def _tar_payloads(path: Path) -> dict[str, bytes]:
    if path.stat().st_size > MAX_RAW_TAR_BYTES:
        raise ValueError("controlled pixel raw archive exceeds file-size limit")
    payloads = {}
    with tarfile.open(path, "r:") as archive:
        members = archive.getmembers()
        if len(members) != EXPECTED_RAW_MEMBER_COUNT:
            raise ValueError("controlled pixel raw archive member count mismatch")
        total_size = 0
        for member in members:
            pure = PurePosixPath(member.name)
            if (
                not member.isfile()
                or not member.name
                or pure.is_absolute()
                or ".." in pure.parts
                or member.name in payloads
                or member.size > 2 * 1024 * 1024
                or member.linkname
                or member.pax_headers
                or member.mode != 0o644
                or member.mtime != 0
                or member.uid != 0
                or member.gid != 0
                or member.uname
                or member.gname
            ):
                raise ValueError("controlled pixel raw archive member is unsafe")
            total_size += member.size
            if total_size > MAX_RAW_TOTAL_BYTES:
                raise ValueError("controlled pixel raw archive exceeds total-size limit")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("controlled pixel raw archive member is unreadable")
            payloads[member.name] = stream.read()
    if path.read_bytes() != _canonical_tar(payloads):
        raise ValueError("controlled pixel raw archive is not canonical USTAR")
    return payloads


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("controlled pixel byte lengths differ")
    return [
        index
        for index, pair in enumerate(zip(left, right, strict=True))
        if pair[0] != pair[1]
    ]


def _pixel_changes(left: bytes, right: bytes) -> list[dict[str, Any]]:
    rows = []
    for index in range(240 * 160):
        offset = index * 3
        before = list(left[offset:offset + 3])
        after = list(right[offset:offset + 3])
        if before != after:
            rows.append(
                {
                    "x": index % 240,
                    "y": index // 240,
                    "before_rgb": before,
                    "after_rgb": after,
                }
            )
    return rows


def _target_task(state: Any, contract: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for slot in range(128):
        raw = state.read_memory(0x03003BB8 + slot * 0x3C, 0x3C)
        flags = struct.unpack_from("<I", raw)[0]
        if flags & 1 and struct.unpack_from("<II", raw, 0x1C) == (
            contract["definition"],
            contract["animation"],
        ):
            rows.append(
                {
                    "slot": slot,
                    "flags": f"0x{flags:08X}",
                    "anchor_x": struct.unpack_from("<h", raw, 4)[0],
                    "anchor_y": struct.unpack_from("<h", raw, 6)[0],
                    "tile_base": struct.unpack_from("<H", raw, 0x10)[0],
                    "palette_bank": raw[0x12],
                    "definition_pointer": f"0x{contract['definition']:08X}",
                    "animation_pointer": f"0x{contract['animation']:08X}",
                }
            )
    if len(rows) != 1:
        raise ValueError("controlled pixel target task is absent or ambiguous")
    count = state.read_memory(0x03005BB8, 1)[0]
    pointers = struct.unpack(
        f"<{count}I", state.read_memory(0x030059B8, count * 4)
    )
    if 0x03003BB8 + rows[0]["slot"] * 0x3C not in pointers:
        raise ValueError("controlled pixel target task is not active")
    return rows[0]


def _rebuild_rom(base: bytes, graphics: bytes, contract: dict[str, Any]) -> bytes:
    encoded = _encode_lz77(graphics)
    if len(encoded) != contract["encoded_size"]:
        raise ValueError("controlled pixel independent encoded size mismatch")
    relocated = bytearray(base + bytes([0xFF]) * (0x1000000 - len(base)))
    allocation = contract["allocation_offset"]
    relocated[allocation:allocation + len(encoded)] = encoded
    for pointer_offset in contract["target_pointer_offsets"]:
        struct.pack_into("<I", relocated, pointer_offset, 0x08000000 + allocation)
    return build_expected_probe(bytes(relocated), CASE_ROWS[contract["case_row"]])


def _verify_or_raise(root: Path, artifact: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    artifact = Path(artifact).resolve(strict=True)
    manifest = _json(artifact / "manifest.json")
    evidence = _json(artifact / "evidence.json")
    contract = CASE_CONTRACTS.get(evidence.get("case_id"))
    if contract is None:
        raise ValueError("controlled pixel case is not allowlisted")
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != EVIDENCE_SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("verifier") != _expected_verifier(contract)
        or evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("verified") is not True
    ):
        raise ValueError("controlled pixel artifact schema/status mismatch")
    expected_files = {"baseline.png", "candidate.png", "evidence.json", "raw.tar"}
    if set(manifest.get("files", {})) != expected_files:
        raise ValueError("controlled pixel artifact file denominator mismatch")
    for name in expected_files:
        if manifest["files"][name] != _sha256_file(artifact / name):
            raise ValueError(f"controlled pixel artifact hash mismatch: {name}")
    if set(manifest.get("repository_files", {})) != set(IMPLEMENTATION_PATHS):
        raise ValueError("controlled pixel implementation denominator mismatch")
    for path in IMPLEMENTATION_PATHS:
        if manifest["repository_files"][path] != _sha256_file(root / path):
            raise ValueError(f"controlled pixel implementation hash mismatch: {path}")
    if any(value.startswith("/") for value in _strings(evidence)):
        raise ValueError("controlled pixel promoted evidence contains absolute paths")

    profile_path = _safe_file(root, evidence.get("profile"), "profile")
    profile = _json(profile_path)
    if (
        evidence.get("profile_sha256") != _sha256_file(profile_path)
        or manifest.get("profile") != evidence.get("profile")
        or manifest.get("profile_sha256") != evidence.get("profile_sha256")
        or profile.get("schema") != "controlled-battle-effect-pixel-ab-profile-v1"
        or evidence.get("profile") != contract["profile"]
        or profile.get("case_id") != evidence.get("case_id")
        or profile.get("group_id") != contract["group_id"]
        or profile.get("sequence_id") != contract["sequence_id"]
        or profile.get("natural_gameplay_route") is not False
        or profile.get("production_resource_relocation") is not True
        or profile.get("graphics_byte_offset") != contract["graphics_offset"]
        or profile.get("before_byte") != contract["before_byte"]
        or profile.get("after_byte") != contract["after_byte"]
        or profile.get("runtime_oam", {}).get("oam_index") != contract["oam_index"]
        or profile.get("runtime_oam", {}).get("attributes") != contract["oam_attributes"]
        or profile.get("runtime_oam", {}).get("obj_tile_base") != contract["tile_base"]
        or profile.get("runtime_oam", {}).get("palette_bank") != contract["palette_bank"]
        or profile.get("expected_encoded_size") != contract["encoded_size"]
        or profile.get("graphics_allocation_offset") != contract["allocation_offset"]
        or profile.get(
            "source_pointer_offsets", [profile.get("pair_pointer_offset")]
        )
        != contract["source_pointer_offsets"]
        or profile.get(
            "target_pointer_offsets", [profile.get("pair_pointer_offset")]
        )
        != contract["target_pointer_offsets"]
    ):
        raise ValueError("controlled pixel profile contract mismatch")
    expected_scope = {
        "execution_mode": "controlled-direct-spawn",
        "production_resource_relocation": True,
        "controlled_final_pixel_writeback": True,
        "mgba_capture_pixel_ab": False,
        "natural_gameplay_route": False,
        "production_natural_pixel_ab": "5/18",
        "physical_gba_verified": False,
    }
    if evidence.get("scope") != expected_scope:
        raise ValueError("controlled pixel evidence scope mismatch")
    parent = verify_direct_artifact(root / "artifacts/battle-effect-direct-spawn-runtime-v1")
    if not parent.get("verified") or evidence.get("parent_direct_spawn_verifier") != parent:
        raise ValueError("controlled pixel parent verifier mismatch")

    payloads = _tar_payloads(artifact / "raw.tar")
    inventory = evidence.get("raw_inventory")
    expected_inventory = [
        {"path": name, "size": len(data), "sha256": _sha256(data)}
        for name, data in sorted(payloads.items())
    ]
    if inventory != expected_inventory:
        raise ValueError("controlled pixel raw inventory mismatch")
    batch = _json_bytes(payloads["batch-audit.json"], "batch")
    build = _json_bytes(payloads["build/build-manifest.json"], "build")
    if (
        batch.get("schema") != "controlled-battle-effect-pixel-ab-batch-v1"
        or batch.get("natural_gameplay_route") is not False
        or build.get("schema") != "controlled-battle-effect-pixel-ab-build-v1"
        or build.get("profile_sha256") != _sha256_file(profile_path)
        or build.get("same_patch_topology") is not True
        or build.get("same_encoded_size") is not True
        or build.get("same_probe_bytes") is not True
        or build.get("group_id") != contract["group_id"]
        or build.get("sequence_id") != contract["sequence_id"]
        or (
            contract["build_pointer_lists_required"]
            and build.get("source_pointer_offsets")
            != contract["source_pointer_offsets"]
        )
        or (
            contract["build_pointer_lists_required"]
            and build.get("target_pointer_offsets")
            != contract["target_pointer_offsets"]
        )
        or (
            not contract["build_pointer_lists_required"]
            and build.get("source_pointer_offsets")
            not in (None, contract["source_pointer_offsets"])
        )
        or (
            not contract["build_pointer_lists_required"]
            and build.get("target_pointer_offsets")
            not in (None, contract["target_pointer_offsets"])
        )
        or evidence.get("build", {}).get("encoded_graphics_size")
        != contract["encoded_size"]
        or evidence.get("build", {}).get("allocation_offset")
        != contract["allocation_offset"]
        or evidence.get("build", {}).get("source_pointer_offsets")
        != contract["source_pointer_offsets"]
        or evidence.get("build", {}).get("pointer_offsets")
        != contract["target_pointer_offsets"]
        or evidence.get("build", {}).get("manifest_sha256")
        != _sha256(payloads["build/build-manifest.json"])
    ):
        raise ValueError("controlled pixel raw build/batch mismatch")

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("controlled pixel base ROM mismatch")
    if any(
        struct.unpack_from("<I", base, offset)[0]
        != contract["source_graphics_pointer"]
        for offset in contract["source_pointer_offsets"]
    ):
        raise ValueError("controlled pixel source pointer alias mismatch")
    graphics = {
        variant: payloads[f"build/{variant}/{contract['graphics_filename']}"]
        for variant in VARIANTS
    }
    if (
        _diff(graphics["baseline"], graphics["candidate"])
        != [contract["graphics_offset"]]
        or graphics["baseline"][contract["graphics_offset"]] != contract["before_byte"]
        or graphics["candidate"][contract["graphics_offset"]] != contract["after_byte"]
    ):
        raise ValueError("controlled pixel raw graphics mutation mismatch")
    for variant in VARIANTS:
        rebuilt = _rebuild_rom(base, graphics[variant], contract)
        if _sha256(rebuilt) != build["variants"][variant]["rom_sha256"]:
            raise ValueError(f"controlled pixel independently rebuilt ROM mismatch: {variant}")

    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        states = {}
        rendered = {}
        run_rows = {row["variant"]: row for row in evidence.get("runs", [])}
        batch_rows = {row["variant"]: row for row in batch.get("runs", [])}
        palette = _safe_file(root, profile["source_palette"], "source palette").read_bytes()
        for variant in VARIANTS:
            prefix = f"runs/{variant}"
            profile_raw = payloads[f"{prefix}/profile.json"]
            audit_raw = payloads[f"{prefix}/output/audit.json"]
            guard_raw = payloads[f"{prefix}/guard-summary.json"]
            run_profile = _json_bytes(profile_raw, f"{variant} profile")
            audit = _json_bytes(audit_raw, f"{variant} audit")
            guard = _json_bytes(guard_raw, f"{variant} guard")
            done = _json_bytes(
                payloads[f"{prefix}/guard-summary.json.done.json"], f"{variant} done"
            )
            rom_sha = build["variants"][variant]["rom_sha256"]
            profile_sha = _sha256(profile_raw)
            audit_sha = _sha256(audit_raw)
            guard_sha = _sha256(guard_raw)
            phase_payload_names = {
                name.removeprefix(f"{prefix}/output/")
                for name in payloads
                if any(name.startswith(f"{prefix}/output/{phase}/") for phase in PHASES)
            }
            if (
                run_profile.get("execution_mode") != "controlled-direct-spawn-pixel-ab"
                or run_profile.get("variant") != variant
                or run_profile.get("natural_gameplay_route") is not False
                or run_profile.get("input_mode") != "zero-input-active-state"
                or run_profile.get("source_build_manifest") != "build/build-manifest.json"
                or run_profile.get("source_build_manifest_sha256")
                != _sha256(payloads["build/build-manifest.json"])
                or run_profile.get("source_rom_sha256") != rom_sha
                or audit.get("schema") != "mgba-battle-effect-phase-capture-v1"
                or audit.get("outcome") != "three-phase-captured"
                or audit.get("group_id") != contract["group_id"]
                or audit.get("definition_pointer") != f"0x{contract['definition']:08X}"
                or audit.get("animation_pointer") != f"0x{contract['animation']:08X}"
                or audit.get("input_mode") != "zero-input-active-state"
                or audit.get("inputs") != []
                or audit.get("automatic_inputs") != []
                or audit.get("recovery_inputs") != []
                or audit.get("rom_sha256") != rom_sha
                or audit.get("staged_rom_sha256") != rom_sha
                or audit.get("profile_sha256") != profile_sha
                or audit.get("guard_summary_sha256") != guard_sha
                or set(audit.get("files", {})) != phase_payload_names
                or any(
                    audit["files"][name]
                    != _sha256(payloads[f"{prefix}/output/{name}"])
                    for name in phase_payload_names
                )
                or guard.get("reason") != "completed"
                or guard.get("exit_code") != 0
                or guard.get("degraded") is not False
                or guard.get("completion_trigger") != "success-marker"
                or done.get("status") != "three-phase-captured"
                or done.get("phase_count") != 3
                or done.get("run_id") != audit.get("run_id")
                or audit.get("runtime_residue", {}).get("pgid_clean") is not True
                or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
            ):
                raise ValueError(f"controlled pixel raw runtime provenance mismatch: {variant}")

            phase_states = []
            phase_metas = []
            cycles = []
            savestate_hashes = []
            previous_cycle = -1
            target_task = None
            for index, phase in enumerate(PHASES):
                phase_prefix = f"{prefix}/output/{phase}"
                state_raw = payloads[f"{phase_prefix}/capture.ss9"]
                state_path = temp / f"{variant}-{phase}.ss9"
                state_path.write_bytes(state_raw)
                state = load_gba_state(state_path)
                meta = _json_bytes(
                    payloads[f"{phase_prefix}/capture-phase.json"],
                    f"{variant} {phase} phase",
                )
                address = state.registers[15] - 2
                cycle = int(meta.get("cycle", -1))
                current_task = _target_task(state, contract)
                if (
                    address != PHASE_ADDRESSES[index]
                    or meta.get("name") != phase
                    or meta.get("address") != f"0x{address:08X}"
                    or meta.get("pending") != PHASE_PENDING[index]
                    or state.read_memory(PENDING, 1)[0] != PHASE_PENDING[index]
                    or cycle <= previous_cycle
                    or state.read_memory(SCRATCH, 4) != b"\x01\x00\x00\x00"
                    or state.read_memory(SCRATCH + 4, 1)[0] == 0xFF
                    or meta.get("task_slot") != current_task["slot"]
                    or meta.get("task_address")
                    != f"0x{0x03003BB8 + current_task['slot'] * 0x3C:08X}"
                    or meta.get("task_flags") != current_task["flags"]
                    or state.read_memory(
                        0x06010000 + current_task["tile_base"] * 32,
                        len(graphics[variant]),
                    )
                    != graphics[variant]
                    or _diff(
                        state.read_memory(
                            0x05000200 + current_task["palette_bank"] * 32,
                            len(palette),
                        ),
                        palette,
                    )
                    != contract["palette_mismatches"]
                    or state.read_memory(
                        0x05000200 + current_task["palette_bank"] * 32,
                        contract["palette_prefix"],
                    )
                    != palette[:contract["palette_prefix"]]
                ):
                    raise ValueError(f"controlled pixel runtime phase mismatch: {variant}/{phase}")
                dump_contracts = {
                    "capture-task-pool.bin": (0x03003BB8, 128 * 0x3C),
                    "capture-active-count.bin": (0x03005BB8, 1),
                    "capture-active-pointers.bin": (0x030059B8, 512),
                    "capture-shadow-oam.bin": (SHADOW_OAM, 0x400),
                    "capture-hardware-oam.bin": (HARDWARE_OAM, 0x400),
                    "capture-pram.bin": (0x05000000, 0x400),
                    "capture-vram.bin": (0x06000000, 0x18000),
                }
                for name, (dump_address, dump_size) in dump_contracts.items():
                    if payloads[f"{phase_prefix}/{name}"] != state.read_memory(
                        dump_address, dump_size
                    ):
                        raise ValueError(
                            f"controlled pixel runtime phase dump mismatch: {variant}/{phase}/{name}"
                        )
                if payloads[f"{phase_prefix}/capture-submission.bin"] != bytes(
                    [PHASE_PENDING[index], contract["submission_counts"][index]]
                ):
                    raise ValueError(
                        f"controlled pixel runtime submission mismatch: {variant}/{phase}"
                    )
                if target_task is not None and current_task != target_task:
                    raise ValueError(f"controlled pixel target task changed across phases: {variant}")
                target_task = current_task
                previous_cycle = cycle
                phase_states.append(state)
                phase_metas.append(meta)
                cycles.append(str(cycle))
                savestate_hashes.append(_sha256(state_raw))
            if (
                audit.get("phases") != phase_metas
                or audit.get("renderer_hit_count") != 1
                or audit.get("submission_watch_hit_count") != 3
                or audit.get("ack_hit_count") != 1
            ):
                raise ValueError(f"controlled pixel phase audit mismatch: {variant}")
            renderer_shadow = phase_states[0].read_memory(SHADOW_OAM, 0x400)
            renderer_hardware = phase_states[0].read_memory(HARDWARE_OAM, 0x400)
            if (
                renderer_shadow == renderer_hardware
                or phase_states[1].read_memory(HARDWARE_OAM, 0x400) != renderer_hardware
                or phase_states[2].read_memory(HARDWARE_OAM, 0x400) != renderer_shadow
            ):
                raise ValueError(f"controlled pixel OAM transaction mismatch: {variant}")
            phase_transaction = {
                "addresses": [f"0x{address:08X}" for address in PHASE_ADDRESSES],
                "pending": list(PHASE_PENDING),
                "cycles": cycles,
                "savestate_sha256": savestate_hashes,
                "renderer_shadow_differs_from_old_hardware": True,
                "submit_hardware_unchanged": True,
                "ack_hardware_equals_renderer_shadow": True,
            }
            rss = guard.get("peak_tree_rss_mib")
            expected_batch_row = {
                "variant": variant,
                "rom_sha256": rom_sha,
                "profile_sha256": profile_sha,
                "audit_sha256": audit_sha,
                "guard_summary_sha256": guard_sha,
                "peak_tree_rss_mib": audit.get("peak_tree_rss_mib"),
                "pgid_clean": audit.get("pgid_clean"),
            }
            if batch_rows.get(variant) != expected_batch_row:
                raise ValueError(f"controlled pixel batch run mismatch: {variant}")
            expected_row = {
                "variant": variant,
                "rom_sha256": rom_sha,
                "profile_sha256": profile_sha,
                "audit_sha256": audit_sha,
                "guard_summary_sha256": guard_sha,
                "ack_state_sha256": savestate_hashes[-1],
                "peak_tree_rss_mib_sample": rss,
                "rss_sample_valid_for_statistics": isinstance(rss, (int, float)) and rss >= 10,
                "pgid_clean": True,
                "target_task": target_task,
                "phase_transaction": phase_transaction,
            }
            if run_rows.get(variant) != expected_row:
                raise ValueError(f"controlled pixel run record mismatch: {variant}")
            ack_state = phase_states[-1]
            attrs = struct.unpack_from(
                "<HHH",
                ack_state.read_memory(HARDWARE_OAM, 0x400),
                contract["oam_index"] * 8,
            )
            if [f"0x{value:04X}" for value in attrs] != contract["oam_attributes"]:
                raise ValueError(f"controlled pixel runtime OAM mismatch: {variant}")
            states[variant] = ack_state
            rendered[variant] = render_checkpoint(temp / f"{variant}-ack-post.ss9")[0]

    memory = {
        name: _diff(
            states["baseline"].read_memory(address, size),
            states["candidate"].read_memory(address, size),
        )
        for name, (address, size) in DOMAINS.items()
    }
    expected_memory = {
        **{name: [] for name in DOMAINS},
        "VRAM": [contract["vram_difference"]],
    }
    expected_pixel = [contract["pixel"]]
    pixels = _pixel_changes(rendered["baseline"], rendered["candidate"])
    capture_hashes = {
        variant: _sha256(
            payloads[f"runs/{variant}/output/ack-post/capture.png"]
        )
        for variant in VARIANTS
    }
    expected_capture_record = {
        "baseline_sha256": capture_hashes["baseline"],
        "candidate_sha256": capture_hashes["candidate"],
        "byte_equal": True,
        "used_for_pixel_ab": False,
    }
    if (
        memory != expected_memory
        or evidence.get("runtime", {}).get("memory_differences") != memory
        or evidence.get("runtime", {}).get("memory_absolute_difference")
        != contract["absolute_difference"]
        or pixels != expected_pixel
        or evidence.get("runtime", {}).get("pixel_changes") != pixels
        or evidence.get("runtime", {}).get("graphics_difference_offsets")
        != [contract["graphics_offset"]]
        or evidence.get("runtime", {}).get("oam_index") != contract["oam_index"]
        or evidence.get("runtime", {}).get("oam_attributes")
        != contract["oam_attributes"]
        or evidence.get("runtime", {}).get("palette_equal") is not True
        or evidence.get("runtime", {}).get("source_palette_matched_prefix_bytes")
        != contract["palette_prefix"]
        or evidence.get("runtime", {}).get("source_palette_mismatch_offsets")
        != contract["palette_mismatches"]
        or evidence.get("runtime", {}).get("full_source_palette_equal")
        != (not contract["palette_mismatches"])
        or capture_hashes["baseline"] != capture_hashes["candidate"]
        or evidence.get("runtime", {}).get("pixel_render_source")
        != "offline-mode0-from-ack-savestate"
        or evidence.get("runtime", {}).get("mgba_capture_pngs")
        != expected_capture_record
    ):
        raise ValueError("controlled pixel runtime A/B isolation mismatch")
    for variant in VARIANTS:
        with Image.open(artifact / f"{variant}.png") as image:
            if image.size != (240, 160) or image.convert("RGB").tobytes() != rendered[variant]:
                raise ValueError(f"controlled pixel promoted PNG mismatch: {variant}")
    return {
        "verified": True,
        "errors": [],
        "group_id": contract["group_id"],
        "sequence_id": contract["sequence_id"],
        "controlled_final_pixel_writeback": True,
        "mgba_capture_pixel_ab": False,
        "natural_gameplay_route": False,
        "production_natural_pixel_ab": "5/18",
    }


def verify_evidence(root: Path, artifact: Path) -> dict[str, Any]:
    try:
        return _verify_or_raise(root, artifact)
    except Exception as error:
        group_id = 0
        sequence_id = 0
        try:
            candidate = _json(Path(artifact) / "evidence.json")
            contract = CASE_CONTRACTS.get(candidate.get("case_id"))
            if contract is not None:
                group_id = contract["group_id"]
                sequence_id = contract["sequence_id"]
        except Exception:
            pass
        return {
            "verified": False,
            "errors": [str(error)],
            "group_id": group_id,
            "sequence_id": sequence_id,
            "controlled_final_pixel_writeback": False,
            "mgba_capture_pixel_ab": False,
            "natural_gameplay_route": False,
            "production_natural_pixel_ab": "5/18",
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
