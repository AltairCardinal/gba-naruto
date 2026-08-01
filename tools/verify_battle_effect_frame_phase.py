#!/usr/bin/env python3
"""Independently verify a battle-effect renderer/submission/ack capture."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

try:
    from tools.inspect_mgba_savestate import PNG_SIGNATURE, load_gba_state
except ModuleNotFoundError:
    from inspect_mgba_savestate import PNG_SIGNATURE, load_gba_state


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "battle-effect-frame-phase-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PHASES = (
    ("renderer-post", "0x08063328", 0),
    ("submit-post", "0x08061126", 1),
    ("ack-post", "0x080612AA", 0),
)
MEMORY_DUMPS = {
    "task-pool.bin": (0x03003BB8, 0x1E00),
    "active-count.bin": (0x03005BB8, 1),
    "active-pointers.bin": (0x030059B8, 0x200),
    "runtime-offsets.bin": (0x03000054, 0x20),
    "shadow-oam.bin": (0x0300027C, 0x400),
    "hardware-oam.bin": (0x07000000, 0x400),
    "submission.bin": (0x0300067C, 2),
    "vram.bin": (0x06000000, 0x18000),
    "pram.bin": (0x05000000, 0x400),
}
LIVE_ONLY_DUMPS = {"io.bin": 0x400}
TASK_BASE = 0x03003BB8
TASK_SIZE = 0x3C
TASK_COUNT = 128
EXPECTED_DEFINITION = 0x08345530
EXPECTED_ANIMATION = 0x08345564
EXPECTED_TOOLCHAIN_SCHEMA = "rom-expansion-profile-v1"
EXPECTED_TOOLCHAIN_IDENTITY = "agb_standard_16mib_sequel_rom_profile"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _record_error(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def thumb_breakpoint_address(saved_pc: int, cpsr: int) -> int:
    """Recover mGBA's breakpoint address from a Thumb callback savestate."""

    if not cpsr & 0x20:
        raise ValueError("breakpoint savestate is not in Thumb mode")
    if saved_pc < 2 or saved_pc & 1:
        raise ValueError("saved Thumb PC is invalid")
    return saved_pc - 2


def decode_active_task_slots(count_raw: bytes, pointers_raw: bytes) -> list[int]:
    if len(count_raw) != 1:
        raise ValueError("active task count must be one byte")
    count = count_raw[0]
    if count > TASK_COUNT or len(pointers_raw) < count * 4:
        raise ValueError("active task pointer list is truncated or oversized")
    slots: list[int] = []
    for (pointer,) in struct.iter_unpack("<I", pointers_raw[: count * 4]):
        delta = pointer - TASK_BASE
        if delta < 0 or delta % TASK_SIZE:
            raise ValueError("active task pointer is outside or not aligned to task pool")
        slot = delta // TASK_SIZE
        if slot >= TASK_COUNT:
            raise ValueError("active task pointer is outside or not aligned to task pool")
        slots.append(slot)
    if len(slots) != len(set(slots)):
        raise ValueError("active task pointer list contains duplicates")
    return slots


def target_dispatch_ordinal(slots: list[int], target_slot: int) -> int:
    matches = [index for index, slot in enumerate(slots) if slot == target_slot]
    if len(matches) != 1:
        raise ValueError("target task must occur exactly once in active dispatcher")
    return matches[0]


def verify_artifact(artifact: Path) -> dict[str, Any]:
    artifact = Path(artifact).resolve()
    errors: list[str] = []
    pending_sequence: list[int] = []
    cycles: list[int] = []
    task_slots: list[int] = []
    breakpoint_addresses: list[str] = []
    target_dispatch_ordinals: list[int] = []
    buffers: dict[str, dict[str, bytes]] = {}
    group_id: int | None = None
    ack_match = False
    renderer_differs = False

    try:
        manifest = _object(artifact / "manifest.json")
        audit = _object(artifact / "runtime-audit.json")
        guard = _object(artifact / "guard-summary.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {
            "verified": False,
            "errors": [str(error)],
            "group_id": None,
            "pending_sequence": [],
            "ack_shadow_matches_hardware": False,
            "renderer_shadow_differs_from_hardware": False,
            "breakpoint_addresses": [],
            "target_dispatch_ordinals": [],
            "non_state_equivalent_dumps": list(LIVE_ONLY_DUMPS),
        }

    group_id = manifest.get("group_id")
    _record_error(
        errors,
        manifest.get("schema") == PROMOTION_SCHEMA,
        "promotion manifest schema mismatch",
    )
    _record_error(
        errors,
        manifest.get("artifact_schema") == SCHEMA,
        "artifact schema mismatch",
    )
    _record_error(errors, manifest.get("artifact_status") == "accepted", "artifact is not accepted")
    _record_error(errors, group_id == 11, "group id is not 11")
    _record_error(errors, manifest.get("input_mode") == "zero-input-active-state", "input mode mismatch")
    _record_error(errors, manifest.get("inputs") == [], "manifest contains input events")
    dump_semantics = manifest.get("dump_semantics", {})
    _record_error(
        errors,
        isinstance(dump_semantics, dict)
        and dump_semantics.get("savestate_exact") == list(MEMORY_DUMPS)
        and dump_semantics.get("live_byte_read_only") == list(LIVE_ONLY_DUMPS),
        "dump semantics mismatch",
    )

    file_hashes = manifest.get("files")
    if not isinstance(file_hashes, dict):
        errors.append("manifest file hash table is missing")
        file_hashes = {}
    for relative, expected in file_hashes.items():
        path = artifact / relative
        _record_error(errors, path.is_file(), f"artifact file is missing: {relative}")
        if path.is_file():
            _record_error(errors, _sha256(path) == expected, f"artifact file hash mismatch: {relative}")

    repository_hashes = manifest.get("repository_files")
    if not isinstance(repository_hashes, dict):
        errors.append("repository file hash table is missing")
        repository_hashes = {}
    for relative, expected in repository_hashes.items():
        path = ROOT / relative
        _record_error(errors, path.is_file(), f"repository evidence is missing: {relative}")
        if path.is_file():
            _record_error(errors, _sha256(path) == expected, f"repository evidence hash mismatch: {relative}")

    profile_info = manifest.get("profile", {})
    if isinstance(profile_info, dict):
        profile_path = ROOT / str(profile_info.get("path", ""))
        _record_error(errors, profile_path.is_file(), "capture profile is missing")
        if profile_path.is_file():
            _record_error(errors, _sha256(profile_path) == profile_info.get("sha256"), "capture profile hash mismatch")
            profile = _object(profile_path)
            input_info = manifest.get("input_state", {})
            input_path = ROOT / str(input_info.get("path", "")) if isinstance(input_info, dict) else ROOT
            _record_error(errors, profile.get("schema") == "battle-effect-phase-capture-profile-v1", "capture profile schema mismatch")
            _record_error(errors, profile.get("group_id") == group_id, "capture profile group mismatch")
            _record_error(errors, input_path.is_file(), "input savestate is missing")
            if input_path.is_file() and isinstance(input_info, dict):
                _record_error(errors, _sha256(input_path) == input_info.get("sha256"), "input savestate hash mismatch")
                _record_error(errors, profile.get("input_state_sha256") == input_info.get("sha256"), "profile input hash mismatch")
    else:
        errors.append("capture profile provenance is missing")

    animations_info = manifest.get("animations", {})
    if isinstance(animations_info, dict):
        animations_path = ROOT / str(animations_info.get("path", ""))
        _record_error(errors, animations_path.is_file(), "animation catalog is missing")
        if animations_path.is_file():
            _record_error(errors, _sha256(animations_path) == animations_info.get("sha256"), "animation catalog hash mismatch")
    else:
        errors.append("animation catalog provenance is missing")

    manifest_phases = manifest.get("phase_sequence")
    audit_phases = audit.get("phases")
    _record_error(errors, isinstance(manifest_phases, list), "manifest phase sequence is missing")
    _record_error(errors, manifest_phases == audit_phases, "manifest and runtime phase sequences differ")

    breakpoint_semantics = manifest.get("breakpoint_pc_semantics", {})
    _record_error(
        errors,
        isinstance(breakpoint_semantics, dict)
        and breakpoint_semantics.get("mode") == "Thumb"
        and breakpoint_semantics.get("saved_r15_to_breakpoint") == "saved_r15 - 2"
        and breakpoint_semantics.get("mgba_source")
        == "src/arm/debugger/debugger.c:_checkBreakpoints",
        "breakpoint PC semantics mismatch",
    )

    for name, address, expected_pending in PHASES:
        directory = artifact / "raw" / name
        state_path = directory / "capture.ss9"
        png_path = directory / "capture.png"
        phase_path = directory / "capture-phase.json"
        try:
            state = load_gba_state(state_path)
            phase = _object(phase_path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"{name} cannot be parsed: {error}")
            continue
        _record_error(errors, png_path.read_bytes().startswith(PNG_SIGNATURE), f"{name} screenshot is not PNG")
        _record_error(errors, phase.get("name") == name, f"{name} phase name mismatch")
        _record_error(errors, phase.get("address") == address, f"{name} address mismatch")
        try:
            saved_breakpoint = thumb_breakpoint_address(state.registers[15], state.cpsr)
            saved_address = f"0x{saved_breakpoint:08X}"
            breakpoint_addresses.append(saved_address)
            _record_error(errors, saved_address == address, f"{name} savestate PC mismatch")
            _record_error(
                errors,
                phase.get("address") == saved_address,
                f"{name} metadata differs from savestate PC",
            )
        except ValueError as error:
            errors.append(f"{name} breakpoint PC is invalid: {error}")
        pending = phase.get("pending")
        _record_error(errors, pending == expected_pending, f"{name} pending flag mismatch")
        if isinstance(pending, int) and not isinstance(pending, bool):
            pending_sequence.append(pending)
        try:
            cycles.append(int(str(phase["cycle"]), 10))
        except (KeyError, TypeError, ValueError):
            errors.append(f"{name} cycle is invalid")
        slot = phase.get("task_slot")
        _record_error(errors, isinstance(slot, int) and not isinstance(slot, bool) and 0 <= slot < TASK_COUNT, f"{name} task slot is invalid")
        if isinstance(slot, int) and not isinstance(slot, bool) and 0 <= slot < TASK_COUNT:
            task_slots.append(slot)
            record = state.read_memory(TASK_BASE + slot * TASK_SIZE, TASK_SIZE)
            flags = struct.unpack_from("<I", record, 0)[0]
            definition, animation = struct.unpack_from("<II", record, 0x1C)
            _record_error(errors, bool(flags & 1), f"{name} task is inactive")
            _record_error(errors, phase.get("task_flags") == f"0x{flags:08X}", f"{name} task flags mismatch")
            _record_error(errors, phase.get("task_address") == f"0x{TASK_BASE + slot * TASK_SIZE:08X}", f"{name} task address mismatch")
            _record_error(errors, definition == EXPECTED_DEFINITION, f"{name} definition pointer mismatch")
            _record_error(errors, animation == EXPECTED_ANIMATION, f"{name} animation pointer mismatch")
            try:
                active_slots = decode_active_task_slots(
                    state.read_memory(0x03005BB8, 1),
                    state.read_memory(0x030059B8, 0x200),
                )
                target_dispatch_ordinals.append(
                    target_dispatch_ordinal(active_slots, slot)
                )
            except ValueError as error:
                errors.append(f"{name} dispatcher membership mismatch: {error}")
        buffers[name] = {}
        for suffix, (address_int, size) in MEMORY_DUMPS.items():
            path = directory / f"capture-{suffix}"
            raw = path.read_bytes()
            buffers[name][suffix] = raw
            _record_error(errors, len(raw) == size, f"{name} {suffix} size mismatch")
            if len(raw) == size:
                _record_error(errors, raw == state.read_memory(address_int, size), f"{name} {suffix} differs from savestate")
        for suffix, size in LIVE_ONLY_DUMPS.items():
            raw = (directory / f"capture-{suffix}").read_bytes()
            buffers[name][suffix] = raw
            _record_error(errors, len(raw) == size, f"{name} {suffix} size mismatch")

    _record_error(errors, pending_sequence == [0, 1, 0], "pending sequence is not 0,1,0")
    _record_error(errors, len(cycles) == 3 and cycles[0] < cycles[1] < cycles[2], "phase cycles are not strictly increasing")
    _record_error(errors, len(task_slots) == 3 and len(set(task_slots)) == 1, "phase task identity changed")
    _record_error(
        errors,
        target_dispatch_ordinals == [0, 0, 0],
        "target task dispatcher ordinal changed or is not zero",
    )
    if len(buffers) == 3:
        renderer = buffers["renderer-post"]
        submit = buffers["submit-post"]
        ack = buffers["ack-post"]
        renderer_differs = renderer["shadow-oam.bin"] != renderer["hardware-oam.bin"]
        ack_match = ack["shadow-oam.bin"] == ack["hardware-oam.bin"]
        _record_error(errors, renderer_differs, "renderer shadow OAM already equals hardware OAM")
        _record_error(errors, submit["shadow-oam.bin"] == renderer["shadow-oam.bin"], "shadow OAM changed before submission")
        _record_error(errors, submit["hardware-oam.bin"] == renderer["hardware-oam.bin"], "hardware OAM changed before acknowledgement")
        _record_error(errors, ack_match, "acknowledged shadow and hardware OAM differ")
        _record_error(errors, ack["hardware-oam.bin"] == renderer["shadow-oam.bin"], "acknowledged hardware OAM is not rendered shadow OAM")
        _record_error(errors, len({buffers[name]["task-pool.bin"] for name, _, _ in PHASES}) == 1, "task pool changed across phases")

    _record_error(errors, audit.get("schema") == "mgba-battle-effect-phase-capture-v1", "runtime audit schema mismatch")
    _record_error(errors, audit.get("outcome") == "three-phase-captured", "runtime audit outcome mismatch")
    _record_error(errors, audit.get("group_id") == group_id, "runtime audit group mismatch")
    _record_error(errors, audit.get("input_mode") == "zero-input-active-state", "runtime audit input mode mismatch")
    for field in ("inputs", "automatic_inputs", "recovery_inputs"):
        _record_error(errors, audit.get(field) == [], f"runtime audit {field} is not empty")
    _record_error(errors, audit.get("pgid_clean") is True, "runtime audit reports process residue")
    residue = audit.get("runtime_residue", {})
    _record_error(errors, isinstance(residue, dict) and residue.get("pgid_clean") is True and residue.get("mgba_listener_clean") is True, "runtime residue probe is not clean")
    _record_error(errors, guard.get("reason") == "completed", "guard reason mismatch")
    _record_error(errors, guard.get("exit_code") == 0, "guard exit code mismatch")
    _record_error(errors, guard.get("degraded") is False, "guard was degraded")
    _record_error(errors, guard.get("completion_trigger") == "success-marker", "guard completion trigger mismatch")
    _record_error(errors, manifest.get("rom_sha256") == audit.get("rom_sha256") == audit.get("staged_rom_sha256"), "ROM provenance mismatch")
    _record_error(errors, manifest.get("run_id") == audit.get("run_id"), "run id mismatch")
    toolchain = manifest.get("toolchain", {})
    audit_toolchain = audit.get("toolchain", {})
    if isinstance(toolchain, dict) and isinstance(audit_toolchain, dict):
        toolchain_path_raw = toolchain.get("path")
        valid_relative = (
            isinstance(toolchain_path_raw, str)
            and not Path(toolchain_path_raw).is_absolute()
            and ".." not in Path(toolchain_path_raw).parts
        )
        _record_error(errors, valid_relative, "toolchain profile path is not repository-relative")
        if valid_relative:
            toolchain_path = ROOT / toolchain_path_raw
            _record_error(errors, toolchain_path.is_file(), "toolchain profile is missing")
            if toolchain_path.is_file():
                toolchain_hash = _sha256(toolchain_path)
                _record_error(errors, toolchain_hash == toolchain.get("sha256"), "toolchain profile hash mismatch")
                _record_error(errors, repository_hashes.get(toolchain_path_raw) == toolchain_hash, "toolchain profile is not repository hash-locked")
                toolchain_profile = _object(toolchain_path)
                hardware = toolchain_profile.get("hardware_evidence", {})
                _record_error(errors, toolchain_profile.get("schema") == EXPECTED_TOOLCHAIN_SCHEMA, "toolchain profile schema mismatch")
                _record_error(errors, toolchain_profile.get("identity") == EXPECTED_TOOLCHAIN_IDENTITY, "toolchain profile identity mismatch")
                _record_error(errors, isinstance(hardware, dict) and hardware.get("mgba_source_commit") == toolchain.get("source_commit") == audit_toolchain.get("source_commit"), "mGBA source commit mismatch")
                _record_error(errors, isinstance(hardware, dict) and hardware.get("mgba_binary_sha256") == audit.get("binary_sha256"), "mGBA binary hash mismatch")
                _record_error(errors, breakpoint_semantics.get("mgba_source_commit") == toolchain.get("source_commit"), "breakpoint semantics source commit mismatch")
        comparable_audit = dict(audit_toolchain)
        audit_path = comparable_audit.get("path")
        if isinstance(audit_path, str):
            try:
                comparable_audit["path"] = Path(audit_path).resolve().relative_to(ROOT).as_posix()
            except ValueError:
                comparable_audit["path"] = None
        _record_error(errors, toolchain == comparable_audit, "toolchain provenance mismatch")
    else:
        errors.append("toolchain provenance is missing")

    return {
        "verified": not errors,
        "errors": errors,
        "group_id": group_id,
        "pending_sequence": pending_sequence,
        "ack_shadow_matches_hardware": ack_match,
        "renderer_shadow_differs_from_hardware": renderer_differs,
        "non_state_equivalent_dumps": list(LIVE_ONLY_DUMPS),
        "breakpoint_addresses": breakpoint_addresses,
        "target_dispatch_ordinals": target_dispatch_ordinals,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = verify_artifact(args.artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
