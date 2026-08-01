#!/usr/bin/env python3
"""Independently verify the group-15 allocator-reset side A/B artifact."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
from typing import Any

try:
    from tools.inspect_mgba_savestate import load_gba_state
    from tools.verify_battle_effect_controlled_runtime import (
        read_safe_tar as read_parent_tar,
        verify_artifact as verify_parent_artifact,
    )
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state
    from verify_battle_effect_controlled_runtime import (
        read_safe_tar as read_parent_tar,
        verify_artifact as verify_parent_artifact,
    )


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "battle-effect-group15-allocator-side-runtime-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
CANONICAL_ARTIFACT = "artifacts/battle-effect-group15-allocator-side-runtime-v1"
CASE_ROWS = (
    ("group-15-sequence-17-reset-side-0", 0),
    ("group-15-sequence-17-reset-side-1", 1),
)
CASE_IDS = tuple(row[0] for row in CASE_ROWS)
PHASE_NAMES = ("binder-return", "renderer-post", "submit-post", "ack-post")
CAPTURE_OUTPUT_NAMES = (
    "capture-active-count.bin", "capture-active-pointers.bin",
    "capture-hardware-oam.bin", "capture-io.bin", "capture-phase.json",
    "capture-pram.bin", "capture-runtime-offsets.bin", "capture-shadow-oam.bin",
    "capture-submission.bin", "capture-task-pool.bin", "capture-vram.bin",
    "capture.png", "capture.ss9",
)
EXPECTED_SOURCE_MEMBERS = {
    "source/batch-audit.json",
    *(f"source/{case}/{name}" for case in CASE_IDS for name in (
        "profile.json", "guard-summary.json", "guard-summary.json.done.json",
        "output/audit.json",
    )),
    *(f"source/{case}/output/{phase}/{name}" for case in CASE_IDS
      for phase in PHASE_NAMES for name in CAPTURE_OUTPUT_NAMES),
}
EXPECTED_ARTIFACT_FILES = {"manifest.json", "evidence.json", "raw-batch.tar"}
REPOSITORY_FILES = (
    "tools/build_controlled_battle_effect_allocator_reset_probe.py",
    "tools/run_battle_effect_allocator_reset_batch.py",
    "tools/export_battle_effect_group15_allocator_side_runtime.py",
    "tools/verify_battle_effect_group15_allocator_side_runtime.py",
    "tools/run_macos_mgba_controlled_battle_effect_capture.py",
    "tools/run_macos_mgba_battle_effect_phase_capture.py",
    "tools/run_macos_mgba_input_sequence.py",
    "tools/run_macos_mgba_replay.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_controlled_battle_effect_capture.lua",
    "tools/macos_mgba_runtime_residue.py",
    "tools/run_guarded.py",
    "tools/mgba_runtime_safety.py",
    "tools/project_resource_guard.py",
    "tools/inspect_mgba_savestate.py",
    "tools/build_save_state_runtime_probe.py",
    "tools/thumb_branch.py",
    "tools/verify_battle_effect_controlled_runtime.py",
    "tests/test_build_controlled_battle_effect_allocator_reset_probe.py",
    "tests/test_run_battle_effect_allocator_reset_batch.py",
    "tests/test_export_battle_effect_group15_allocator_side_runtime.py",
    "tests/test_verify_battle_effect_group15_allocator_side_runtime.py",
)
SOURCE_PATHS = {
    "base_rom": "rom/base.gba",
    "input_state": "artifacts/runtime-checkpoints/scenario-50-battle-15-escort-12hp-player-turn.ss9",
    "sequence_catalog": "artifacts/battle-effect-sequence-bindings-v1/manifest.json",
    "animation_catalog": "artifacts/battle-effect-sprite-animations-v1/manifest.json",
    "resource_catalog": "artifacts/battle-effect-resource-pairs-v1/manifest.json",
    "parent_controlled_artifact": "artifacts/battle-effect-controlled-runtime-v1/manifest.json",
    "group15_graphics": "artifacts/battle-effect-resource-pairs-v1/group-15-graphics-4bpp.bin",
    "group15_palette": "artifacts/battle-effect-resource-pairs-v1/group-15-palette-bgr555.bin",
    "toolchain_profile": "artifacts/rom-expansion-profile-v1/profile.json",
    "capture_script": "tools/mgba_controlled_battle_effect_capture.lua",
}
TRUSTED_SOURCE_SHA256 = {
    "base_rom": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
    "input_state": "7d6796a767d574f5f7a91935c3c1e65ce44edbc51aa5a6b587784d4730bbe94f",
    "sequence_catalog": "ec8f41571bb132577ecb7bc57f946a85f219b4c05f3697c89b75be73385b0c73",
    "animation_catalog": "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848",
    "resource_catalog": "716ac580326077127797c634d1f19bbc0aadcfd4db9c577730728b112f002963",
    "parent_controlled_artifact": "ad1baabd5a972e1ef342b80a060084fb450e781b011128c4f7ccd89b5e10825b",
    "group15_graphics": "caf034cec9cf78cf35763eb7416d25ef431f76f06252221390ef05ab21c0407a",
    "group15_palette": "cb86625b5c5d976d388d055aeeb9cbae97effd7efb021bce01e252030b54d1e1",
    "toolchain_profile": "e21d375914dda3c20b05ccec45c39406db310609e69ee19d04dfa342f4b70287",
    "capture_script": "81e9639dedfd3517fcc00032a222b87a870ec6db6396aef9bc41e246aab7ec41",
}
EXPECTED_BINARY_SHA256 = "c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8"
EXPECTED_TOOLCHAIN_SOURCE_COMMIT = "d8bad14b4540f9114246c0281d74985cf81adc68"
PARENT_CONTROLLED_ROOT = "artifacts/battle-effect-controlled-runtime-v1"
PARENT_GROUP15_PROBE_SHA256 = "de882cbee61c407ed1601c1accc9f652fa02de389afe0a56369650ab25f38ed6"
TASK_BASE = 0x03003BB8
TASK_SIZE = 0x3C
TASK_COUNT = 128
ACTIVE_COUNT = 0x03005BB8
ACTIVE_POINTERS = 0x030059B8
SHADOW_OAM = 0x0300027C
HARDWARE_OAM = 0x07000000
OBJ_VRAM = 0x06010000
OBJ_PRAM = 0x05000200
SELECTOR_RESULT = 0x0202C64F
SIDE_OPCODE_OFFSET = 0x0009E852
ROM_BASE = 0x08000000
HOOK = 0x08061F76
SOUND_MAIN = 0x0809AAB4
RESOURCE_ALLOCATOR_RESET = 0x0807FDCC
SEQUENCE_BINDER = 0x0807C5E8
STUB = 0x0809E820
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 68
SCRATCH = 0x0203FF40
NO_RESET_STUB = 0x0809E840
NO_RESET_STUB_OFFSET = NO_RESET_STUB - ROM_BASE
NO_RESET_STUB_SIZE = 36


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _encode_thumb_bl(callsite: int, target: int) -> bytes:
    displacement = target - (callsite + 4)
    if displacement & 1 or not -(1 << 22) <= displacement < (1 << 22):
        raise ValueError("invalid independent Thumb BL")
    encoded = displacement & 0x7FFFFF
    return struct.pack(
        "<HH",
        0xF000 | ((encoded >> 12) & 0x7FF),
        0xF800 | ((encoded >> 1) & 0x7FF),
    )


def build_expected_probe(base: bytes, *, side: int) -> bytes:
    """Rebuild the probe without importing its production builder."""
    if side not in (0, 1):
        raise ValueError("side must be 0 or 1")
    code = struct.pack("<H", 0xB510)
    code += _encode_thumb_bl(STUB + len(code), SOUND_MAIN)
    code += struct.pack(
        "<13H",
        0x4C0E, 0x6820, 0x2800, 0xD115, 0x2001, 0x6020,
        0x20C0, 0x0080, 0x21E0, 0x0089, 0x3901, 0x220C, 0x230E,
    )
    code += _encode_thumb_bl(STUB + len(code), RESOURCE_ALLOCATOR_RESET)
    code += struct.pack("<7H", *(0x46C0 for _ in range(7)))
    code += struct.pack("<2H", 0x2000 | side, 0x2111)
    code += _encode_thumb_bl(STUB + len(code), SEQUENCE_BINDER)
    code += struct.pack("<HHHI", 0xBC10, 0xBC01, 0x4700, SCRATCH)
    if len(code) != STUB_SIZE:
        raise ValueError("independent probe size mismatch")
    hook_offset = HOOK - ROM_BASE
    if base[hook_offset:hook_offset + 4] != _encode_thumb_bl(HOOK, SOUND_MAIN):
        raise ValueError("base SoundMain call mismatch")
    if any(base[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("base probe region is occupied")
    output = bytearray(base)
    output[hook_offset:hook_offset + 4] = _encode_thumb_bl(HOOK, STUB)
    output[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = code
    return bytes(output)


def build_expected_no_reset_probe(base: bytes) -> bytes:
    """Independently rebuild the accepted sequence-17 side-0 baseline."""
    code = struct.pack("<H", 0xB510)
    code += _encode_thumb_bl(NO_RESET_STUB + len(code), SOUND_MAIN)
    code += struct.pack(
        "<8H",
        0x4C06, 0x6820, 0x2800, 0xD105, 0x2001, 0x6020, 0x2000, 0x2111,
    )
    code += _encode_thumb_bl(NO_RESET_STUB + len(code), SEQUENCE_BINDER)
    code += struct.pack("<HHHI", 0xBC10, 0xBC01, 0x4700, SCRATCH)
    if len(code) != NO_RESET_STUB_SIZE:
        raise ValueError("independent no-reset probe size mismatch")
    hook_offset = HOOK - ROM_BASE
    if base[hook_offset:hook_offset + 4] != _encode_thumb_bl(HOOK, SOUND_MAIN):
        raise ValueError("base SoundMain call mismatch")
    if any(base[NO_RESET_STUB_OFFSET:NO_RESET_STUB_OFFSET + NO_RESET_STUB_SIZE]):
        raise ValueError("base no-reset probe region is occupied")
    output = bytearray(base)
    output[hook_offset:hook_offset + 4] = _encode_thumb_bl(HOOK, NO_RESET_STUB)
    output[NO_RESET_STUB_OFFSET:NO_RESET_STUB_OFFSET + NO_RESET_STUB_SIZE] = code
    return bytes(output)


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _payload(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid archived {label}") from error
    if not isinstance(value, dict):
        raise ValueError(f"archived {label} must be an object")
    return value


def read_safe_tar(path: Path) -> dict[str, bytes]:
    result = {}
    with tarfile.open(path, "r:") as archive:
        for member in archive.getmembers():
            name = Path(member.name)
            if (
                not member.isfile() or name.is_absolute() or ".." in name.parts
                or member.name in result
            ):
                raise ValueError("unsafe raw batch member")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("raw batch member is unreadable")
            result[member.name] = stream.read()
    if set(result) != EXPECTED_SOURCE_MEMBERS:
        raise ValueError("raw batch member inventory mismatch")
    return result


def _target_tasks(state: Any, definition: int, animation: int) -> list[dict[str, Any]]:
    rows = []
    for slot in range(TASK_COUNT):
        raw = state.read_memory(TASK_BASE + slot * TASK_SIZE, TASK_SIZE)
        flags = struct.unpack_from("<I", raw)[0]
        if flags & 1 and struct.unpack_from("<II", raw, 0x1C) == (definition, animation):
            rows.append({
                "slot": slot, "flags": f"0x{flags:08X}",
                "anchor_x": struct.unpack_from("<h", raw, 4)[0],
                "anchor_y": struct.unpack_from("<h", raw, 6)[0],
                "tile_base": struct.unpack_from("<H", raw, 0x10)[0],
                "palette_bank": raw[0x12], "animation_id": raw[0x14],
                "keyframe_index": raw[0x16],
            })
    return rows


def _active_slots(state: Any) -> list[int]:
    count = struct.unpack("<I", state.read_memory(ACTIVE_COUNT, 4))[0]
    if count > TASK_COUNT:
        raise ValueError("active task count overflow")
    pointers = struct.unpack(f"<{count}I", state.read_memory(ACTIVE_POINTERS, count * 4))
    slots = []
    for pointer in pointers:
        delta = pointer - TASK_BASE
        if delta < 0 or delta % TASK_SIZE or delta // TASK_SIZE >= TASK_COUNT:
            raise ValueError("active task pointer mismatch")
        slots.append(delta // TASK_SIZE)
    return slots


def _verify_sources(evidence: dict[str, Any]) -> None:
    if set(evidence.get("sources", {})) != set(SOURCE_PATHS):
        raise ValueError("trusted source inventory mismatch")
    for name, relative in SOURCE_PATHS.items():
        record = evidence["sources"][name]
        path = ROOT / relative
        actual = _sha256(path)
        if actual != TRUSTED_SOURCE_SHA256[name]:
            raise ValueError(f"trusted source hash mismatch: {name}")
        if record != {"path": relative, "sha256": actual, "size": path.stat().st_size}:
            raise ValueError(f"source record mismatch: {name}")


def _verify_archive(payloads: dict[str, bytes], evidence: dict[str, Any]) -> dict[str, Any]:
    archive = evidence.get("archive")
    if not isinstance(archive, dict) or archive.get("member_count") != 113:
        raise ValueError("archive member count mismatch")
    ledger = archive.get("members")
    if not isinstance(ledger, dict) or set(ledger) != EXPECTED_SOURCE_MEMBERS:
        raise ValueError("archive ledger mismatch")
    for name, payload in payloads.items():
        if ledger[name] != {"sha256": _sha256_bytes(payload), "size": len(payload)}:
            raise ValueError(f"archive member hash mismatch: {name}")
    batch = _payload(payloads["source/batch-audit.json"], "batch audit")
    if (
        batch.get("schema") != "battle-effect-allocator-reset-batch-audit-v1"
        or batch.get("group_id") != 15 or batch.get("sequence_id") != 17
        or batch.get("sides") != [0, 1]
        or batch.get("input_state_sha256") != TRUSTED_SOURCE_SHA256["input_state"]
        or batch.get("binary_sha256") != EXPECTED_BINARY_SHA256
        or batch.get("toolchain_profile") != SOURCE_PATHS["toolchain_profile"]
        or batch.get("toolchain_profile_sha256") != TRUSTED_SOURCE_SHA256["toolchain_profile"]
    ):
        raise ValueError("archived batch contract mismatch")
    return batch


def _verify_parent_no_reset(base: bytes, evidence: dict[str, Any]) -> list[int]:
    parent_root = ROOT / PARENT_CONTROLLED_ROOT
    result = verify_parent_artifact(parent_root)
    if not result.get("verified"):
        raise ValueError(f"parent controlled artifact failed verification: {result.get('errors')}")
    expected_probe = build_expected_no_reset_probe(base)
    if _sha256_bytes(expected_probe) != PARENT_GROUP15_PROBE_SHA256:
        raise ValueError("independent no-reset probe hash mismatch")
    parent_evidence = _object(parent_root / "evidence.json")
    case = next(
        row for row in parent_evidence["cases"]
        if row.get("case_id") == "group-15-sequence-17"
    )
    if case.get("probe_rom_sha256") != PARENT_GROUP15_PROBE_SHA256:
        raise ValueError("parent group-15 probe hash mismatch")
    payloads = read_parent_tar(parent_root / "raw-batch.tar")
    profile_raw = payloads["source/group-15-sequence-17/profile.json"]
    audit_raw = payloads["source/group-15-sequence-17/output/audit.json"]
    profile = _payload(profile_raw, "parent group-15 profile")
    audit = _payload(audit_raw, "parent group-15 audit")
    if (
        profile.get("group_id") != 15
        or profile.get("sequence_id") != 17
        or profile.get("input_state_sha256") != TRUSTED_SOURCE_SHA256["input_state"]
        or profile.get("source_rom_sha256") != PARENT_GROUP15_PROBE_SHA256
        or audit.get("rom_sha256") != PARENT_GROUP15_PROBE_SHA256
        or audit.get("staged_rom_sha256") != PARENT_GROUP15_PROBE_SHA256
    ):
        raise ValueError("parent no-reset provenance mismatch")
    selectors = []
    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary)
        for phase in PHASE_NAMES:
            state_path = temporary_root / f"parent-{phase}.ss9"
            state_path.write_bytes(
                payloads[
                    f"source/group-15-sequence-17/output/{phase}/capture.ss9"
                ]
            )
            selectors.append(
                load_gba_state(state_path).read_memory(SELECTOR_RESULT, 1)[0]
            )
    if selectors != [0xFF, 0xFF, 0xFF, 0xFF]:
        raise ValueError("parent no-reset selector result mismatch")
    comparison = evidence.get("allocator_reset_ab")
    expected_comparison = {
        "boundary": "same accepted checkpoint, sequence 17 and side 0",
        "no_reset_parent_artifact": PARENT_CONTROLLED_ROOT,
        "no_reset_probe_rom_sha256": PARENT_GROUP15_PROBE_SHA256,
        "no_reset_selector_results": selectors,
        "reset_selector_results": [0, 0, 0, 0],
    }
    if comparison != expected_comparison:
        raise ValueError("allocator reset A/B comparison mismatch")
    return selectors


def verify_artifact(artifact: Path | str) -> dict[str, Any]:
    artifact = Path(artifact).resolve()
    errors = []
    selector_sides: list[int] = []
    target_sides: list[int] = []
    target_slot: int | None = None
    try:
        actual_files = {path.relative_to(artifact).as_posix() for path in artifact.rglob("*") if path.is_file() or path.is_symlink()}
        if actual_files != EXPECTED_ARTIFACT_FILES or any(path.is_symlink() for path in artifact.rglob("*")):
            raise ValueError("artifact directory inventory mismatch")
        manifest = _object(artifact / "manifest.json")
        evidence = _object(artifact / "evidence.json")
        if (
            manifest.get("schema") != PROMOTION_SCHEMA
            or manifest.get("artifact_schema") != SCHEMA
            or manifest.get("artifact_status") != "accepted"
            or manifest.get("artifact_path") != CANONICAL_ARTIFACT
            or evidence.get("schema") != SCHEMA
        ):
            raise ValueError("artifact schema or promotion mismatch")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != {"evidence.json", "raw-batch.tar"}:
            raise ValueError("artifact file manifest mismatch")
        for name, digest in files.items():
            if _sha256(artifact / name) != digest:
                raise ValueError(f"artifact hash mismatch: {name}")
        repository = manifest.get("repository_files")
        if not isinstance(repository, dict) or set(repository) != set(REPOSITORY_FILES):
            raise ValueError("repository dependency inventory mismatch")
        for name in REPOSITORY_FILES:
            if repository[name] != _sha256(ROOT / name):
                raise ValueError(f"repository dependency hash mismatch: {name}")
        _verify_sources(evidence)
        archive_path = artifact / "raw-batch.tar"
        if evidence.get("archive", {}).get("sha256") != _sha256(archive_path) or evidence.get("archive", {}).get("size") != archive_path.stat().st_size:
            raise ValueError("raw batch archive hash mismatch")
        payloads = read_safe_tar(archive_path)
        batch = _verify_archive(payloads, evidence)

        base = (ROOT / SOURCE_PATHS["base_rom"]).read_bytes()
        animation_catalog = _object(ROOT / SOURCE_PATHS["animation_catalog"])
        group = next(row for row in animation_catalog["groups"] if row.get("group_id") == 15)
        definition = int(group["definition_pointer_table"], 16)
        animation = int(group["animation_pointer_table"], 16)
        resource_catalog = _object(ROOT / SOURCE_PATHS["resource_catalog"])
        resource = next(row for row in resource_catalog["entries"] if row.get("group_id") == 15)
        if (
            resource["graphics"].get("output_bin") != Path(SOURCE_PATHS["group15_graphics"]).name
            or resource["graphics"].get("decompressed_sha256")
            != TRUSTED_SOURCE_SHA256["group15_graphics"]
            or resource["palette"].get("output_bin") != Path(SOURCE_PATHS["group15_palette"]).name
            or resource["palette"].get("decompressed_sha256")
            != TRUSTED_SOURCE_SHA256["group15_palette"]
        ):
            raise ValueError("group 15 resource catalog identity mismatch")
        graphics = (ROOT / SOURCE_PATHS["group15_graphics"]).read_bytes()
        palette = (ROOT / SOURCE_PATHS["group15_palette"]).read_bytes()
        _verify_parent_no_reset(base, evidence)
        cases = evidence.get("cases")
        if not isinstance(cases, list) or len(cases) != 2 or len(batch.get("cases", [])) != 2:
            raise ValueError("case denominator mismatch")
        expected_roms = [build_expected_probe(base, side=side) for side in (0, 1)]
        expected_rom_hashes = [_sha256_bytes(rom) for rom in expected_roms]
        differences = [
            index
            for index, pair in enumerate(zip(*expected_roms, strict=True))
            if pair[0] != pair[1]
        ]
        if differences != [SIDE_OPCODE_OFFSET]:
            raise ValueError("independent side ROM difference mismatch")
        rom_hashes = []
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            for recorded, batch_row, (case_id, side) in zip(cases, batch["cases"], CASE_ROWS, strict=True):
                if recorded.get("case_id") != case_id or recorded.get("side") != side or batch_row.get("case_id") != case_id or batch_row.get("side") != side:
                    raise ValueError("case identity mismatch")
                profile_raw = payloads[f"source/{case_id}/profile.json"]
                audit_raw = payloads[f"source/{case_id}/output/audit.json"]
                guard_raw = payloads[f"source/{case_id}/guard-summary.json"]
                done_raw = payloads[f"source/{case_id}/guard-summary.json.done.json"]
                profile = _payload(profile_raw, f"{case_id} profile")
                audit = _payload(audit_raw, f"{case_id} audit")
                guard = _payload(guard_raw, f"{case_id} guard")
                done = _payload(done_raw, f"{case_id} completion marker")
                toolchain = audit.get("toolchain")
                toolchain_valid = (
                    isinstance(toolchain, dict)
                    and toolchain.get("kind") == "current-desktop-runtime-profile"
                    and toolchain.get("patch_sha256") is None
                    and isinstance(toolchain.get("path"), str)
                    and Path(toolchain["path"]).as_posix().endswith(
                        "/" + SOURCE_PATHS["toolchain_profile"]
                    )
                    and toolchain.get("sha256")
                    == TRUSTED_SOURCE_SHA256["toolchain_profile"]
                    and toolchain.get("source_commit")
                    == EXPECTED_TOOLCHAIN_SOURCE_COMMIT
                )
                if (
                    recorded.get("profile_sha256") != _sha256_bytes(profile_raw)
                    or recorded.get("audit_sha256") != _sha256_bytes(audit_raw)
                    or recorded.get("guard_summary_sha256") != _sha256_bytes(guard_raw)
                    or batch_row.get("profile_sha256") != _sha256_bytes(profile_raw)
                    or batch_row.get("audit_sha256") != _sha256_bytes(audit_raw)
                    or batch_row.get("guard_summary_sha256") != _sha256_bytes(guard_raw)
                ):
                    raise ValueError(f"{case_id} provenance hash mismatch")
                if profile.get("side") != side or profile.get("allocator_reset") != {"function": "0x0807FDCC", "tile_start": "0x0300", "tile_end": "0x037F", "palette_start": 12, "palette_end": 14}:
                    raise ValueError(f"{case_id} allocator profile mismatch")
                if guard.get("reason") != "completed" or guard.get("exit_code") != 0 or guard.get("degraded") is not False:
                    raise ValueError(f"{case_id} guard mismatch")
                expected_outputs = {
                    f"{phase}/{name}"
                    for phase in PHASE_NAMES
                    for name in CAPTURE_OUTPUT_NAMES
                }
                audit_files = audit.get("files")
                if not isinstance(audit_files, dict) or set(audit_files) != expected_outputs:
                    raise ValueError(f"{case_id} runtime audit file inventory mismatch")
                for relative, expected_hash in audit_files.items():
                    actual_hash = _sha256_bytes(
                        payloads[f"source/{case_id}/output/{relative}"]
                    )
                    if actual_hash != expected_hash:
                        raise ValueError(
                            f"{case_id} runtime audit file hash mismatch: {relative}"
                        )
                if (
                    audit.get("schema") != "mgba-controlled-battle-effect-capture-v1"
                    or audit.get("outcome") != "binder-plus-three-phase-captured"
                    or audit.get("group_id") != 15
                    or audit.get("sequence_id") != 17
                    or audit.get("profile_sha256") != _sha256_bytes(profile_raw)
                    or audit.get("guard_summary_sha256") != _sha256_bytes(guard_raw)
                    or audit.get("input_state_sha256") != TRUSTED_SOURCE_SHA256["input_state"]
                    or audit.get("animations_sha256") != TRUSTED_SOURCE_SHA256["animation_catalog"]
                    or audit.get("phase_script_sha256")
                    != TRUSTED_SOURCE_SHA256["capture_script"]
                    or audit.get("binary_sha256") != EXPECTED_BINARY_SHA256
                    or not toolchain_valid
                    or audit.get("scratch_before") != 0
                    or audit.get("scratch_after") != 1
                    or done.get("status") != audit.get("outcome")
                    or done.get("phase_count") != 4
                    or done.get("run_id") != audit.get("run_id")
                    or recorded.get("peak_tree_rss_mib_sample")
                    != guard.get("peak_tree_rss_mib")
                ):
                    raise ValueError(f"{case_id} runtime audit provenance mismatch")
                rom_hash = recorded.get("rom_sha256")
                if (
                    rom_hash != profile.get("source_rom_sha256")
                    or rom_hash != audit.get("rom_sha256")
                    or rom_hash != audit.get("staged_rom_sha256")
                    or rom_hash != batch_row.get("rom_sha256")
                ):
                    raise ValueError(f"{case_id} ROM hash mismatch")
                rom_hashes.append(rom_hash)
                states = []
                for phase in PHASE_NAMES:
                    path = temporary_root / f"{side}-{phase}.ss9"
                    path.write_bytes(payloads[f"source/{case_id}/output/{phase}/capture.ss9"])
                    states.append(load_gba_state(path))
                selector = [state.read_memory(SELECTOR_RESULT, 1)[0] for state in states]
                targets = [_target_tasks(state, definition, animation) for state in states]
                active = [_active_slots(state) for state in states]
                if selector != [0, 0, 0, 0] or recorded.get("selector_results") != selector:
                    raise ValueError(f"{case_id} selector handle mismatch")
                selector_sides.append(side)
                if recorded.get("target_tasks") != targets or recorded.get("active_slots") != active:
                    raise ValueError(f"{case_id} task evidence mismatch")
                if side == 0:
                    if targets != [[], [], [], []]:
                        raise ValueError("side 0 target task mismatch")
                else:
                    if targets[0] or any(len(rows) != 1 or rows[0]["slot"] != 108 for rows in targets[1:]):
                        raise ValueError("side 1 target task mismatch")
                    task = targets[1][0]
                    if task["anchor_x"] != -98 or task["anchor_y"] != 62 or task["tile_base"] != 768 or task["palette_bank"] != 12:
                        raise ValueError("side 1 target task metadata mismatch")
                    for state in states[1:]:
                        if state.read_memory(OBJ_VRAM + 768 * 32, len(graphics)) != graphics or state.read_memory(OBJ_PRAM + 12 * 32, len(palette)) != palette:
                            raise ValueError("side 1 target resource mismatch")
                    frame = next(row for row in group["frames"] if row["frame_id"] == 0)
                    component = frame["components"][0]
                    local_x = -component["x"] - component["width"]
                    if task["anchor_x"] + local_x + component["width"] > 0:
                        raise ValueError("target component is no longer fully offscreen")
                    target_sides.append(side)
                    target_slot = 108
                transaction = {
                    "shadow_changed": states[1].read_memory(SHADOW_OAM, 0x400) != states[0].read_memory(SHADOW_OAM, 0x400),
                    "ack_equals_renderer_shadow": states[3].read_memory(HARDWARE_OAM, 0x400) == states[1].read_memory(SHADOW_OAM, 0x400),
                }
                if recorded.get("oam_transaction") != transaction:
                    raise ValueError(f"{case_id} global OAM transaction mismatch")

        if rom_hashes != expected_rom_hashes:
            raise ValueError("recorded ROM does not match independent probe reconstruction")
        side_ab = evidence.get("side_ab")
        if side_ab != {"rom_byte_difference_count": 1, "difference_address": "0x0809E852", "side_0_byte": 0, "side_1_byte": 1}:
            raise ValueError("side ROM single-variable contract mismatch")
        coverage = evidence.get("coverage")
        if not isinstance(coverage, dict) or coverage.get("selector_valid_sides") != [0, 1] or coverage.get("target_task_sides") != [1] or coverage.get("target_task_slot") != 108:
            raise ValueError("coverage contract mismatch")
        if coverage.get("visible_target_oam_binding_count") != 0:
            raise ValueError("visible target OAM scope inflation")
        if coverage.get("natural_entry_complete") is not False:
            raise ValueError("natural entry scope inflation")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, tarfile.TarError) as error:
        errors.append(str(error))
    verified = not errors
    return {
        "verified": verified, "errors": errors,
        "selector_valid_sides": selector_sides if verified else [],
        "target_task_sides": target_sides if verified else [],
        "target_task_slot": target_slot if verified else None,
        "visible_target_oam_binding_count": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", nargs="?", type=Path, default=ROOT / CANONICAL_ARTIFACT)
    args = parser.parse_args()
    result = verify_artifact(args.artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
