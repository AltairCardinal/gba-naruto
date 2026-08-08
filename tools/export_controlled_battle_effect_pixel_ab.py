#!/usr/bin/env python3
"""Promote an allowlisted controlled battle-effect pixel A/B artifact."""

from __future__ import annotations

import argparse
import hashlib
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

from tools.build_controlled_battle_effect_pixel_ab import _validate_profile
from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint
from tools.verify_battle_effect_direct_spawn_runtime import (
    _active_slots,
    _target_tasks,
    verify_artifact as verify_direct_artifact,
)
from tools.verify_battle_effect_controlled_runtime import (
    verify_artifact as verify_controlled_runtime_artifact,
)


EVIDENCE_SCHEMA = "controlled-battle-effect-pixel-ab-runtime-v1"
VARIANTS = ("baseline", "candidate")
PHASES = ("renderer-post", "submit-post", "ack-post")
PHASE_ADDRESSES = (0x08063328, 0x08061126, 0x080612AA)
PHASE_PENDING = (0, 1, 0)
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
    "tools/build_controlled_battle_effect_sequence_probe.py",
    "tools/verify_battle_effect_direct_spawn_runtime.py",
    "tools/verify_battle_effect_controlled_runtime.py",
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
    "group-06-sequence-08": {
        "artifact": "artifacts/battle-effect-group06-controlled-pixel-ab-v1",
        "group_id": 6,
        "sequence_id": 8,
        "definition": 0x08343700,
        "animation": 0x0834375C,
        "graphics_filename": "group-06-graphics-4bpp.bin",
        "task_slot": 108,
        "tile_base": 800,
        "palette_bank": 13,
        "graphics_address": 0x06016400,
        "palette_address": 0x050003A0,
        "palette_prefix": 32,
        "palette_mismatches": [],
        "submission_counts": [0, 0, 1],
        "encoded_size": 494,
        "allocation_offset": 0xB40000,
        "source_pointer_offsets": [0x59914C],
        "target_pointer_offsets": [0x59914C],
        "source_graphics_pointer": 0x0834311C,
        "build_pointer_lists_required": True,
        "vram_difference": 0x1641E,
        "absolute_difference": "0x0601641E",
        "execution_mode": "controlled-sequence-injection",
        "coverage_before": 12,
        "coverage_after": 13,
    },
    "group-07-sequence-09": {
        "artifact": "artifacts/battle-effect-group07-controlled-pixel-ab-v1",
        "group_id": 7, "sequence_id": 9,
        "definition": 0x08343D28, "animation": 0x08343D84,
        "graphics_filename": "group-07-graphics-4bpp.bin",
        "task_slot": 108, "tile_base": 800, "palette_bank": 13,
        "graphics_address": 0x06016400, "palette_address": 0x050003A0,
        "palette_prefix": 32, "palette_mismatches": [],
        "submission_counts": [0, 0, 1], "encoded_size": 764,
        "allocation_offset": 0xB40000,
        "source_pointer_offsets": [0x599154], "target_pointer_offsets": [0x599154],
        "source_graphics_pointer": 0x08343760, "build_pointer_lists_required": True,
        "vram_difference": 0x16468, "absolute_difference": "0x06016468",
        "execution_mode": "controlled-sequence-injection",
        "coverage_before": 13, "coverage_after": 14,
    },
    "group-08-sequence-10": {
        "artifact": "artifacts/battle-effect-group08-controlled-pixel-ab-v1",
        "group_id": 8, "sequence_id": 10,
        "definition": 0x08344520, "animation": 0x0834457C,
        "graphics_filename": "group-08-graphics-4bpp.bin",
        "task_slot": 108, "tile_base": 800, "palette_bank": 13,
        "graphics_address": 0x06016400, "palette_address": 0x050003A0,
        "palette_prefix": 32, "palette_mismatches": [],
        "submission_counts": [0, 0, 1], "encoded_size": 1304,
        "allocation_offset": 0xB40000,
        "source_pointer_offsets": [0x59915C], "target_pointer_offsets": [0x59915C],
        "source_graphics_pointer": 0x08343D88, "build_pointer_lists_required": True,
        "vram_difference": 0x16637, "absolute_difference": "0x06016637",
        "execution_mode": "controlled-sequence-injection",
        "coverage_before": 14, "coverage_after": 15,
    },
    "group-09-sequence-11": {
        "artifact": "artifacts/battle-effect-group09-controlled-pixel-ab-v1",
        "group_id": 9, "sequence_id": 11,
        "definition": 0x08344DA8, "animation": 0x08344E14,
        "graphics_filename": "group-09-graphics-4bpp.bin",
        "task_slot": 108, "tile_base": 800, "palette_bank": 13,
        "graphics_address": 0x06016400, "palette_address": 0x050003A0,
        "palette_prefix": 32, "palette_mismatches": [],
        "submission_counts": [0, 0, 1], "encoded_size": 554,
        "allocation_offset": 0xB40000,
        "source_pointer_offsets": [0x599164], "target_pointer_offsets": [0x599164],
        "source_graphics_pointer": 0x08344580, "build_pointer_lists_required": True,
        "vram_difference": 0x16417, "absolute_difference": "0x06016417",
        "execution_mode": "controlled-sequence-injection",
        "coverage_before": 15, "coverage_after": 16,
    },
    "group-10-sequence-12": {
        "artifact": "artifacts/battle-effect-group10-controlled-pixel-ab-v1",
        "group_id": 10, "sequence_id": 12,
        "definition": 0x0834525C, "animation": 0x08345298,
        "graphics_filename": "group-10-graphics-4bpp.bin",
        "task_slot": 108, "tile_base": 800, "palette_bank": 13,
        "graphics_address": 0x06016400, "palette_address": 0x050003A0,
        "palette_prefix": 32, "palette_mismatches": [],
        "submission_counts": [0, 0, 1], "encoded_size": 235,
        "allocation_offset": 0xB40000,
        "source_pointer_offsets": [0x59916C], "target_pointer_offsets": [0x59916C],
        "source_graphics_pointer": 0x08344E18, "build_pointer_lists_required": True,
        "vram_difference": 0x1642D, "absolute_difference": "0x0601642D",
        "extra_memory_differences": {"IWRAM": [0x7F9C]},
        "execution_mode": "controlled-sequence-injection",
        "coverage_before": 16, "coverage_after": 17,
    },
    "group-12-sequence-14": {
        "artifact": "artifacts/battle-effect-group12-controlled-pixel-ab-v1",
        "group_id": 12, "sequence_id": 14,
        "definition": 0x08345A90, "animation": 0x08345AC4,
        "graphics_filename": "group-12-graphics-4bpp.bin",
        "task_slot": 108, "tile_base": 800, "palette_bank": 13,
        "graphics_address": 0x06016400, "palette_address": 0x050003A0,
        "palette_prefix": 32, "palette_mismatches": [],
        "submission_counts": [0, 0, 1], "encoded_size": 1106,
        "allocation_offset": 0xB40000,
        "source_pointer_offsets": [0x59917C], "target_pointer_offsets": [0x59917C],
        "source_graphics_pointer": 0x08345568, "build_pointer_lists_required": True,
        "vram_difference": 0x1647B, "absolute_difference": "0x0601647B",
        "execution_mode": "controlled-sequence-injection",
        "coverage_before": 17, "coverage_after": 18,
    },
    "group-03-sequence-03-side-0-direct-spawn": {
        "artifact": "artifacts/battle-effect-group03-controlled-pixel-ab-v1",
        "group_id": 3,
        "sequence_id": 3,
        "definition": 0x083425D8,
        "animation": 0x083426CC,
        "graphics_filename": "group-03-graphics-4bpp.bin",
        "task_slot": 109,
        "tile_base": 256,
        "palette_bank": 4,
        "graphics_address": 0x06012000,
        "palette_address": 0x05000280,
        "palette_prefix": 30,
        "palette_mismatches": [30, 31],
        "submission_counts": [1, 1, 2],
        "encoded_size": 5294,
        "allocation_offset": 0xB40000,
        "source_pointer_offsets": [0x59912C, 0x599134],
        "target_pointer_offsets": [0x599134],
        "source_graphics_pointer": 0x08340AF8,
        "build_pointer_lists_required": True,
        "vram_difference": 0x120CF,
        "absolute_difference": "0x060120CF",
    },
    "group-18-sequence-07-direct-spawn": {
        "artifact": "artifacts/battle-effect-group18-controlled-pixel-ab-v1",
        "group_id": 18,
        "sequence_id": 7,
        "definition": 0x0834819C,
        "animation": 0x083481DC,
        "graphics_filename": "group-18-graphics-4bpp.bin",
        "task_slot": 109,
        "tile_base": 768,
        "palette_bank": 12,
        "graphics_address": 0x06016000,
        "palette_address": 0x05000380,
        "palette_prefix": 32,
        "palette_mismatches": [],
        "submission_counts": [0, 0, 1],
        "encoded_size": 2002,
        "allocation_offset": 0xB40000,
        "source_pointer_offsets": [0x5991AC],
        "target_pointer_offsets": [0x5991AC],
        "source_graphics_pointer": 0x083478F4,
        "build_pointer_lists_required": False,
        "vram_difference": 0x160CA,
        "absolute_difference": "0x060160CA",
    },
}


def _expected_memory_differences(contract: dict[str, Any]) -> dict[str, list[int]]:
    expected = {name: [] for name in DOMAINS}
    expected["VRAM"] = [contract["vram_difference"]]
    for name, offsets in contract.get("extra_memory_differences", {}).items():
        if name not in expected or not isinstance(offsets, list):
            raise ValueError("controlled pixel extra memory contract mismatch")
        expected[name] = offsets
    return expected


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"controlled pixel JSON must be an object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("controlled pixel memory lengths differ")
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


def _save_rgb(path: Path, pixels: bytes) -> None:
    Image.frombytes("RGB", (240, 160), pixels).save(path, optimize=False)


def _raw_paths(source: Path, graphics_filename: str) -> list[Path]:
    selected = [source / "batch-audit.json", source / "build/build-manifest.json"]
    for variant in VARIANTS:
        selected.extend(
            [
                source / f"build/{variant}/{graphics_filename}",
                source / f"build/{variant}/spec.json",
                source / f"runs/{variant}/profile.json",
                source / f"runs/{variant}/guard-summary.json",
                source / f"runs/{variant}/guard-summary.json.done.json",
            ]
        )
        selected.extend(
            sorted(
                path
                for path in (source / f"runs/{variant}/output").rglob("*")
                if path.is_file()
            )
        )
    if any(not path.is_file() or path.is_symlink() for path in selected):
        raise ValueError("controlled pixel raw source is incomplete or unsafe")
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
            import io

            archive.addfile(info, io.BytesIO(data))
            inventory.append({"path": name, "size": len(data), "sha256": _sha256(data)})
    return inventory


def _phase_transaction(
    source: Path,
    variant: str,
    definition: int,
    animation: int,
    graphics: bytes,
    palette: bytes,
    palette_prefix: int,
    palette_mismatches: list[int],
    submission_counts: list[int],
) -> dict[str, Any]:
    run = source / f"runs/{variant}"
    audit = _json(run / "output/audit.json")
    states = []
    cycles = []
    savestate_hashes = []
    metas = []
    previous_cycle = -1
    for index, phase in enumerate(PHASES):
        phase_root = run / f"output/{phase}"
        for path in phase_root.iterdir():
            if path.is_file() and audit.get("files", {}).get(
                f"{phase}/{path.name}"
            ) != _sha256_file(path):
                raise ValueError(
                    f"controlled pixel {variant} phase file hash mismatch: {phase}/{path.name}"
                )
        state_path = phase_root / "capture.ss9"
        state = load_gba_state(state_path)
        meta = _json(phase_root / "capture-phase.json")
        address = state.registers[15] - 2
        cycle = int(meta.get("cycle", -1))
        targets = _target_tasks(state, definition, animation)
        if (
            address != PHASE_ADDRESSES[index]
            or meta.get("name") != phase
            or meta.get("address") != f"0x{address:08X}"
            or meta.get("pending") != PHASE_PENDING[index]
            or state.read_memory(PENDING, 1)[0] != PHASE_PENDING[index]
            or cycle <= previous_cycle
            or state.read_memory(SCRATCH, 4) != b"\x01\x00\x00\x00"
            or state.read_memory(SCRATCH + 4, 1)[0] == 0xFF
            or len(targets) != 1
            or targets[0]["slot"] not in _active_slots(state)
            or meta.get("task_slot") != targets[0]["slot"]
            or meta.get("task_address")
            != f"0x{0x03003BB8 + targets[0]['slot'] * 0x3C:08X}"
            or meta.get("task_flags") != targets[0]["flags"]
            or state.read_memory(0x06010000 + targets[0]["tile_base"] * 32, len(graphics))
            != graphics
            or _diff(
                state.read_memory(
                    0x05000200 + targets[0]["palette_bank"] * 32, len(palette)
                ),
                palette,
            )
            != palette_mismatches
            or state.read_memory(
                0x05000200 + targets[0]["palette_bank"] * 32, palette_prefix
            )
            != palette[:palette_prefix]
        ):
            raise ValueError(f"controlled pixel {variant} phase mismatch: {phase}")
        dump_contracts = {
            "capture-task-pool.bin": (0x03003BB8, 128 * 0x3C),
            "capture-active-count.bin": (0x03005BB8, 1),
            "capture-active-pointers.bin": (0x030059B8, 512),
            "capture-shadow-oam.bin": (SHADOW_OAM, 0x400),
            "capture-hardware-oam.bin": (HARDWARE_OAM, 0x400),
            "capture-pram.bin": (0x05000000, 0x400),
            "capture-vram.bin": (0x06000000, 0x18000),
        }
        for name, (address_start, size) in dump_contracts.items():
            if (phase_root / name).read_bytes() != state.read_memory(address_start, size):
                raise ValueError(
                    f"controlled pixel {variant} phase dump mismatch: {phase}/{name}"
                )
        if (phase_root / "capture-submission.bin").read_bytes() != bytes(
            [PHASE_PENDING[index], submission_counts[index]]
        ):
            raise ValueError(f"controlled pixel {variant} submission mismatch: {phase}")
        previous_cycle = cycle
        states.append(state)
        cycles.append(str(cycle))
        savestate_hashes.append(_sha256_file(state_path))
        metas.append(meta)
    if (
        audit.get("phases", [])[-len(PHASES):] != metas
        or audit.get("renderer_hit_count") != 1
        or audit.get("submission_watch_hit_count") != 3
        or audit.get("ack_hit_count") != 1
    ):
        raise ValueError(f"controlled pixel {variant} phase audit mismatch")
    renderer_shadow = states[0].read_memory(SHADOW_OAM, 0x400)
    renderer_hardware = states[0].read_memory(HARDWARE_OAM, 0x400)
    if (
        renderer_shadow == renderer_hardware
        or states[1].read_memory(HARDWARE_OAM, 0x400) != renderer_hardware
        or states[2].read_memory(HARDWARE_OAM, 0x400) != renderer_shadow
    ):
        raise ValueError(f"controlled pixel {variant} OAM transaction mismatch")
    return {
        "addresses": [f"0x{address:08X}" for address in PHASE_ADDRESSES],
        "pending": list(PHASE_PENDING),
        "cycles": cycles,
        "savestate_sha256": savestate_hashes,
        "renderer_shadow_differs_from_old_hardware": True,
        "submit_hardware_unchanged": True,
        "ack_hardware_equals_renderer_shadow": True,
    }


def export_evidence(root: Path, profile_path: Path, source: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    profile_path = Path(profile_path).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("controlled pixel artifact output must be empty")
    profile, _ = _validate_profile(root, profile_path)
    contract = CASE_CONTRACTS.get(profile["case_id"])
    if contract is None:
        raise ValueError("controlled pixel case is not allowlisted")
    sequence_mode = profile["execution_mode"] == "controlled-sequence-injection"
    parent_result = (
        verify_controlled_runtime_artifact(
            root / "artifacts/battle-effect-controlled-runtime-v1"
        )
        if sequence_mode
        else verify_direct_artifact(
            root / "artifacts/battle-effect-direct-spawn-runtime-v1"
        )
    )
    if not parent_result.get("verified"):
        raise ValueError("controlled pixel parent runtime artifact is not verified")
    batch = _json(source / "batch-audit.json")
    build = _json(source / "build/build-manifest.json")
    if (
        batch.get("schema") != "controlled-battle-effect-pixel-ab-batch-v1"
        or batch.get("natural_gameplay_route") is not False
        or build.get("schema") != "controlled-battle-effect-pixel-ab-build-v1"
        or build.get("profile_sha256") != _sha256_file(profile_path)
        or build.get("natural_gameplay_route") is not False
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
        or any(
            build.get("variants", {}).get(variant, {}).get("encoded_graphics_size")
            != contract["encoded_size"]
            or build.get("variants", {}).get(variant, {}).get(
                "graphics_allocation_offset"
            )
            != contract["allocation_offset"]
            or build.get("variants", {}).get(variant, {}).get(
                "redirect_pointer_offsets"
            )
            != contract["target_pointer_offsets"]
            for variant in VARIANTS
        )
        or batch.get("build_manifest_sha256") != _sha256_file(source / "build/build-manifest.json")
    ):
        raise ValueError("controlled pixel build/batch contract mismatch")

    states = {}
    audits = {}
    guards = {}
    for variant in VARIANTS:
        run = source / f"runs/{variant}"
        run_profile = _json(run / "profile.json")
        audit = _json(run / "output/audit.json")
        guard = _json(run / "guard-summary.json")
        state_path = run / "output/ack-post/capture.ss9"
        state = load_gba_state(state_path)
        if (
            run_profile.get("execution_mode")
            != (
                "controlled-sequence-injection"
                if sequence_mode
                else "controlled-direct-spawn-pixel-ab"
            )
            or run_profile.get("variant") != variant
            or run_profile.get("natural_gameplay_route") is not False
            or run_profile.get("input_mode") != "zero-input-active-state"
            or run_profile.get("source_rom_sha256") != build["variants"][variant]["rom_sha256"]
            or audit.get("outcome")
            != (
                "binder-plus-three-phase-captured"
                if sequence_mode
                else "three-phase-captured"
            )
            or (
                not sequence_mode
                and audit.get("input_mode") != "zero-input-active-state"
            )
            or audit.get("inputs") != []
            or audit.get("automatic_inputs") != []
            or audit.get("recovery_inputs") != []
            or audit.get("rom_sha256") != build["variants"][variant]["rom_sha256"]
            or guard.get("reason") != "completed"
            or guard.get("exit_code") != 0
            or guard.get("degraded") is not False
            or audit.get("runtime_residue", {}).get("pgid_clean") is not True
            or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
            or audit.get("files", {}).get("ack-post/capture.ss9") != _sha256_file(state_path)
        ):
            raise ValueError(f"controlled pixel {variant} runtime provenance mismatch")
        states[variant] = state
        audits[variant] = audit
        guards[variant] = guard

    definition = int(audits["baseline"]["definition_pointer"], 16)
    animation = int(audits["baseline"]["animation_pointer"], 16)
    if definition != contract["definition"] or animation != contract["animation"]:
        raise ValueError("controlled pixel runtime identity mismatch")
    graphics = {}
    target_tasks = {}
    phase_transactions = {}
    palette = (root / profile["source_palette"]).read_bytes()
    for variant in VARIANTS:
        graphics[variant] = (
            source / f"build/{variant}/{contract['graphics_filename']}"
        ).read_bytes()
        targets = _target_tasks(states[variant], definition, animation)
        if len(targets) != 1 or targets[0]["slot"] not in _active_slots(states[variant]):
            raise ValueError(f"controlled pixel {variant} target task mismatch")
        target = targets[0]
        if (
            target["slot"] != contract["task_slot"]
            or target["tile_base"] != contract["tile_base"]
            or target["palette_bank"] != contract["palette_bank"]
            or states[variant].read_memory(
                contract["graphics_address"], len(graphics[variant])
            )
            != graphics[variant]
            or _diff(
                states[variant].read_memory(contract["palette_address"], 32), palette
            )
            != contract["palette_mismatches"]
        ):
            raise ValueError(f"controlled pixel {variant} runtime resource mismatch")
        instances = profile["runtime_oam"].get("instances") or [profile["runtime_oam"]]
        for instance in instances:
            oam_offset = instance["oam_index"] * 8
            attrs = struct.unpack_from(
                "<HHH", states[variant].read_memory(0x07000000, 0x400), oam_offset
            )
            if [f"0x{value:04X}" for value in attrs] != instance["attributes"]:
                raise ValueError(f"controlled pixel {variant} runtime OAM mismatch")
        target_tasks[variant] = target
        phase_transactions[variant] = _phase_transaction(
            source,
            variant,
            definition,
            animation,
            graphics[variant],
            palette,
            contract["palette_prefix"],
            contract["palette_mismatches"],
            contract["submission_counts"],
        )

    graphics_diffs = _diff(graphics["baseline"], graphics["candidate"])
    if graphics_diffs != [profile["graphics_byte_offset"]]:
        raise ValueError("controlled pixel decoded graphics mismatch")
    memory = {
        name: _diff(
            states["baseline"].read_memory(address, size),
            states["candidate"].read_memory(address, size),
        )
        for name, (address, size) in DOMAINS.items()
    }
    if memory != _expected_memory_differences(contract):
        raise ValueError("controlled pixel runtime memory isolation mismatch")
    rendered = {
        variant: render_checkpoint(source / f"runs/{variant}/output/ack-post/capture.ss9")[0]
        for variant in VARIANTS
    }
    pixels = _pixel_changes(rendered["baseline"], rendered["candidate"])
    expected_pixels = [
        {
            "x": x,
            "y": y,
            "before_rgb": profile["before_rgb"],
            "after_rgb": profile["after_rgb"],
        }
        for x, y in profile.get("screen_pixels", [profile["screen_xy"]])
    ]
    if pixels != expected_pixels:
        raise ValueError("controlled pixel final compositor mismatch")
    capture_hashes = {
        variant: _sha256_file(
            source / f"runs/{variant}/output/ack-post/capture.png"
        )
        for variant in VARIANTS
    }
    if capture_hashes["baseline"] != capture_hashes["candidate"]:
        raise ValueError("controlled pixel raw mGBA capture boundary changed")

    output.mkdir(parents=True, exist_ok=True)
    _save_rgb(output / "baseline.png", rendered["baseline"])
    _save_rgb(output / "candidate.png", rendered["candidate"])
    raw_inventory = _write_tar(
        source,
        _raw_paths(source, contract["graphics_filename"]),
        output / "raw.tar",
    )
    run_rows = []
    batch_rows = {row["variant"]: row for row in batch["runs"]}
    for variant in VARIANTS:
        rss = guards[variant].get("peak_tree_rss_mib")
        run_rows.append(
            {
                "variant": variant,
                "rom_sha256": build["variants"][variant]["rom_sha256"],
                "profile_sha256": _sha256_file(source / f"runs/{variant}/profile.json"),
                "audit_sha256": _sha256_file(source / f"runs/{variant}/output/audit.json"),
                "guard_summary_sha256": _sha256_file(source / f"runs/{variant}/guard-summary.json"),
                "ack_state_sha256": _sha256_file(source / f"runs/{variant}/output/ack-post/capture.ss9"),
                "peak_tree_rss_mib_sample": rss,
                "rss_sample_valid_for_statistics": isinstance(rss, (int, float)) and rss >= 10,
                "pgid_clean": batch_rows[variant]["pgid_clean"],
                "target_task": target_tasks[variant],
                "phase_transaction": phase_transactions[variant],
            }
        )
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "verified": True,
        "profile": profile_path.relative_to(root).as_posix(),
        "profile_sha256": _sha256_file(profile_path),
        "case_id": profile["case_id"],
        "group_id": contract["group_id"],
        "sequence_id": contract["sequence_id"],
        "scope": {
            "execution_mode": profile["execution_mode"],
            "production_resource_relocation": True,
            "controlled_final_pixel_writeback": True,
            "natural_gameplay_route": False,
            **(
                {
                    "production_modified_rom_pixel_ab_before": f"{contract['coverage_before']}/18",
                    "production_modified_rom_pixel_ab_after": f"{contract['coverage_after']}/18",
                }
                if sequence_mode
                else {"production_natural_pixel_ab": "5/18"}
            ),
            "mgba_capture_pixel_ab": False,
            "physical_gba_verified": False,
        },
        "edit": build["edit"],
        "build": {
            "manifest_sha256": _sha256_file(source / "build/build-manifest.json"),
            "same_patch_topology": True,
            "same_encoded_size": True,
            "same_probe_bytes": True,
            "encoded_graphics_size": contract["encoded_size"],
            "allocation_offset": contract["allocation_offset"],
            "source_pointer_offsets": contract["source_pointer_offsets"],
            "pointer_offsets": contract["target_pointer_offsets"],
        },
        "runs": run_rows,
        "runtime": {
            "graphics_difference_offsets": graphics_diffs,
            "memory_differences": memory,
            "memory_absolute_difference": contract["absolute_difference"],
            "pixel_changes": pixels,
            "pixel_render_source": "offline-mode0-from-ack-savestate",
            "mgba_capture_pngs": {
                "baseline_sha256": capture_hashes["baseline"],
                "candidate_sha256": capture_hashes["candidate"],
                "byte_equal": True,
                "used_for_pixel_ab": False,
            },
            "oam_index": profile["runtime_oam"]["oam_index"],
            "oam_attributes": profile["runtime_oam"]["attributes"],
            "palette_equal": True,
            "source_palette_matched_prefix_bytes": contract["palette_prefix"],
            "source_palette_mismatch_offsets": contract["palette_mismatches"],
            "full_source_palette_equal": not contract["palette_mismatches"],
        },
        (
            "parent_controlled_runtime_verifier"
            if sequence_mode
            else "parent_direct_spawn_verifier"
        ): parent_result,
        "raw_inventory": raw_inventory,
        "boundary": profile["boundary"],
    }
    _write_json(output / "evidence.json", evidence)
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": EVIDENCE_SCHEMA,
        "artifact_status": "accepted",
        "files": {
            name: _sha256_file(output / name)
            for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar")
        },
        "repository_files": {
            path: _sha256_file(root / path)
            for path in IMPLEMENTATION_PATHS
        },
        "profile": evidence["profile"],
        "profile_sha256": evidence["profile_sha256"],
        "verifier": {
            "command": [
                "python3",
                "tools/verify_controlled_battle_effect_pixel_ab.py",
                "--root",
                ".",
                "--artifact",
                contract["artifact"],
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
    result = export_evidence(args.root, args.profile, args.source, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
