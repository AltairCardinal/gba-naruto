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
    from tools.verify_battlefield_object_effect_chain import (
        verify_manifest as verify_battlefield_object_effect_chain,
    )
    from tools.verify_battle_effect_natural_checkpoint import (
        verify_artifact as verify_natural_checkpoint,
    )
except ModuleNotFoundError:
    from inspect_mgba_savestate import PNG_SIGNATURE, load_gba_state
    from verify_battlefield_object_effect_chain import (
        verify_manifest as verify_battlefield_object_effect_chain,
    )
    from verify_battle_effect_natural_checkpoint import (
        verify_artifact as verify_natural_checkpoint,
    )


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
EXPECTED_TOOLCHAIN_SCHEMA = "rom-expansion-profile-v1"
EXPECTED_TOOLCHAIN_IDENTITY = "agb_standard_16mib_sequel_rom_profile"
SOURCE_PROVENANCE_SCHEMA = "battle-effect-phase-source-provenance-v1"
DELAYED_OBJECT_TABLE = 0x02026604
DELAYED_OBJECT_STRIDE = 0x10
ANIMATION_CATALOG = ROOT / "artifacts/battle-effect-sprite-animations-v1/manifest.json"


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


def _repository_path(root: Path, raw: Any, label: str) -> Path:
    if not isinstance(raw, str):
        raise ValueError(f"{label} path is missing")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} path is not repository-relative")
    try:
        resolved = (root / relative).resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise ValueError(f"{label} path escapes or is missing") from error
    return resolved


def validate_natural_delayed_object_source(
    root: Path,
    evidence_path: Path,
    provenance: dict[str, Any],
    *,
    group_id: int,
    input_state_path: str,
    input_state_sha256: str,
    rom_sha256: str,
) -> None:
    if provenance.get("source_kind") != "natural_delayed_object_checkpoint":
        raise ValueError("natural delayed source kind mismatch")
    if "accepted_parent" in provenance:
        raise ValueError("natural delayed source must not declare an accepted parent")
    evidence = _object(evidence_path)
    output = evidence.get("output", {})
    evidence_provenance = evidence.get("provenance", {})
    runtime_binding = evidence.get("runtime_binding", {})
    scope = evidence.get("scope", {})
    if (
        evidence.get("schema") == PROMOTION_SCHEMA
        and evidence.get("artifact_schema") == "battle-effect-natural-checkpoint-v1"
    ):
        result = verify_natural_checkpoint(evidence_path.parent)
        if result.get("errors"):
            raise ValueError("natural delayed checkpoint artifact verifier rejected source")
        expected_state = {
            "path": input_state_path,
            "sha256": input_state_sha256,
        }
        checkpoint_stage = provenance.get("checkpoint_state", "first-submit")
        source_states = evidence.get("source_states", {})
        source_state = (
            source_states.get(checkpoint_stage)
            if isinstance(source_states, dict)
            else None
        )
        if evidence.get("artifact_status") != "accepted":
            raise ValueError("natural delayed checkpoint artifact is not accepted")
        if (
            evidence.get("group_id") != group_id
            or evidence.get("rom_sha256") != rom_sha256
            or not isinstance(source_state, dict)
            or {
                "path": source_state.get("path"),
                "sha256": source_state.get("sha256"),
            }
            != expected_state
        ):
            raise ValueError("natural delayed checkpoint artifact identity mismatch")
        expected_delayed = {
            "slot": 3,
            "state": 1,
            "x": 13,
            "y": 6,
            "ninja_tool_id": 67,
            "encoded_action": "0xC3",
            "remaining_turns": source_state.get("remaining_turns"),
            "resource_group_id": 18,
        }
        if provenance.get("delayed_object") != expected_delayed:
            raise ValueError("natural delayed object contract mismatch")
        if evidence.get("expiry_route") != provenance.get("expiry_route"):
            raise ValueError("natural delayed expiry route mismatch")
        artifact_scope = evidence.get("scope", {})
        for field in (
            "natural_tool_submission_verified",
            "natural_object_creation_verified",
            "natural_countdown_zero_verified",
            "static_zero_event_expiry_route_verified",
            "natural_expiry_runtime_verified",
        ):
            if not isinstance(artifact_scope, dict) or artifact_scope.get(field) is not True:
                raise ValueError(f"natural delayed checkpoint artifact scope mismatch: {field}")
        return
    if (
        evidence.get("schema") != "runtime-checkpoint-input-chain-evidence-v1"
        or evidence.get("artifact_status") != "accepted"
    ):
        raise ValueError("natural delayed checkpoint evidence is not accepted")
    if (
        not isinstance(output, dict)
        or output.get("path") != input_state_path
        or output.get("sha256") != input_state_sha256
    ):
        raise ValueError("natural delayed checkpoint state identity mismatch")
    if not isinstance(evidence_provenance, dict) or evidence_provenance.get(
        "base_rom_sha256"
    ) != rom_sha256:
        raise ValueError("natural delayed checkpoint base ROM mismatch")
    if not isinstance(scope, dict):
        raise ValueError("natural delayed checkpoint scope mismatch")
    for field, label in (
        ("natural_action_submission_verified", "natural action submission"),
        ("natural_object_creation_verified", "natural object creation"),
        ("natural_countdown_zero_verified", "natural countdown zero"),
    ):
        if scope.get(field) is not True:
            raise ValueError(f"natural delayed checkpoint {label} is not verified")
    if scope.get("natural_expiry_handler_verified") is not False:
        raise ValueError("natural delayed checkpoint natural expiry handler must be unverified")

    delayed = provenance.get("delayed_object", {})
    expected_delayed = {
        "slot": 3,
        "state": 1,
        "encoded_action": "0xC3",
        "remaining_turns": 0,
        "expiry_action": "0xE4",
        "resource_group_id": group_id,
    }
    if not isinstance(delayed, dict) or delayed != expected_delayed:
        if isinstance(delayed, dict) and delayed.get("remaining_turns") != 0:
            raise ValueError("natural delayed object remaining turns mismatch")
        raise ValueError("natural delayed object contract mismatch")
    if not isinstance(runtime_binding, dict):
        raise ValueError("natural delayed object evidence binding mismatch")
    if runtime_binding.get("ninja_tool_id") != 67:
        raise ValueError("natural delayed checkpoint ninja tool mismatch")
    if any(
        runtime_binding.get(field) != expected_delayed[field]
        for field in (
            "slot",
            "state",
            "encoded_action",
            "remaining_turns",
            "expiry_action",
            "resource_group_id",
        )
    ):
        raise ValueError("natural delayed object evidence binding mismatch")

    state_path = _repository_path(root, input_state_path, "profile input state")
    if _sha256(state_path) != input_state_sha256:
        raise ValueError("natural delayed input state hash mismatch")
    state = load_gba_state(state_path)
    raw_object = state.read_memory(
        DELAYED_OBJECT_TABLE + delayed["slot"] * DELAYED_OBJECT_STRIDE,
        DELAYED_OBJECT_STRIDE,
    )
    if (
        raw_object[0] != delayed["state"]
        or raw_object[4] != int(delayed["encoded_action"], 16)
        or int.from_bytes(raw_object[6:8], "little") != delayed["remaining_turns"]
    ):
        raise ValueError("natural delayed object does not match input savestate")

    animation_catalog = _object(ANIMATION_CATALOG)
    definition, animation = effect_group_identity(animation_catalog, group_id)
    active_group_tasks = 0
    for slot in range(TASK_COUNT):
        task = state.read_memory(TASK_BASE + slot * TASK_SIZE, TASK_SIZE)
        if (
            int.from_bytes(task[0:4], "little") & 1
            and int.from_bytes(task[0x1C:0x20], "little") == definition
            and int.from_bytes(task[0x20:0x24], "little") == animation
        ):
            active_group_tasks += 1
    if active_group_tasks:
        raise ValueError("natural delayed input already contains an active target group task")

    chain_info = provenance.get("static_chain", {})
    if not isinstance(chain_info, dict):
        raise ValueError("natural delayed static chain is missing")
    chain_path = _repository_path(
        root, chain_info.get("path"), "natural delayed static chain"
    )
    if _sha256(chain_path) != chain_info.get("sha256"):
        raise ValueError("natural delayed static chain hash mismatch")
    chain = _object(chain_path)
    chain_result = verify_battlefield_object_effect_chain(
        root, Path(chain.get("rom", "")), chain_path
    )
    if chain_result.get("errors"):
        raise ValueError("natural delayed static chain verifier rejected source")
    mappings = chain.get("mappings", [])
    matches = [
        row
        for row in mappings
        if isinstance(row, dict)
        and row.get("encoded_action") == delayed["encoded_action"]
        and row.get("expiry_action") == delayed["expiry_action"]
        and row.get("ninja_tool_id") == 67
        and row.get("primary_handler") == "0x0807F209"
    ]
    if (
        chain.get("rom_sha256") != rom_sha256
        or chain.get("evidence_level") != "static_end_to_end_producer_chain"
        or chain.get("natural_runtime_observed") is not False
        or chain.get("natural_gameplay_route_closed") is not False
        or chain.get("chain", {}).get("native_handler") != "0x0807F208"
        or len(matches) != 1
    ):
        raise ValueError("natural delayed static chain semantics mismatch")


def validate_source_runtime_provenance(
    root: Path,
    profile: dict[str, Any],
    provenance: dict[str, Any],
    *,
    group_id: int,
    input_state_path: str,
    input_state_sha256: str,
    rom_sha256: str,
) -> None:
    if (
        provenance.get("profile_id") != profile.get("profile_id")
        or provenance.get("group_id") != group_id
    ):
        raise ValueError("source runtime provenance profile identity mismatch")
    source = provenance.get("source_evidence", {})
    if (
        not isinstance(source, dict)
        or source.get("path") != profile.get("source_runtime_evidence")
        or source.get("sha256") != profile.get("source_runtime_evidence_sha256")
    ):
        raise ValueError("source runtime evidence differs from capture profile")
    evidence_path = _repository_path(
        root, source.get("path"), "source runtime evidence"
    )
    evidence_hash = _sha256(evidence_path)
    if evidence_hash != source.get("sha256"):
        raise ValueError("source runtime evidence hash mismatch")

    if provenance.get("source_kind") == "natural_delayed_object_checkpoint":
        validate_natural_delayed_object_source(
            root,
            evidence_path,
            provenance,
            group_id=group_id,
            input_state_path=input_state_path,
            input_state_sha256=input_state_sha256,
            rom_sha256=rom_sha256,
        )
        return

    parent = provenance.get("accepted_parent", {})
    if not isinstance(parent, dict):
        raise ValueError("source runtime accepted parent is missing")
    promotion_path = _repository_path(
        root,
        parent.get("manifest_path"),
        "source runtime artifact manifest",
    )
    promotion_hash = _sha256(promotion_path)
    if promotion_hash != parent.get("manifest_sha256"):
        raise ValueError("source runtime artifact manifest hash mismatch")
    promotion = _object(promotion_path)
    artifact_schema = parent.get("artifact_schema")
    if (
        promotion.get("schema") != "git-artifact-promotion-v1"
        or promotion.get("artifact_status") != "accepted"
        or promotion.get("artifact_schema") != artifact_schema
    ):
        raise ValueError("source runtime artifact is not accepted with the declared schema")
    payload_path = _repository_path(
        root, parent.get("payload_path"), "source runtime accepted payload"
    )
    payload_hash = _sha256(payload_path)
    if payload_hash != parent.get("payload_sha256"):
        raise ValueError("source runtime accepted payload hash mismatch")
    try:
        payload_relative = payload_path.relative_to(promotion_path.parent).as_posix()
    except ValueError as error:
        raise ValueError("source runtime accepted payload is outside its promotion") from error
    if promotion.get("files", {}).get(payload_relative) != payload_hash:
        raise ValueError("source runtime accepted payload is not promotion hash-locked")

    evidence = _object(payload_path)
    if artifact_schema == "battle-effect-runtime-oam-task-bindings-v1":
        if evidence.get("schema") != artifact_schema:
            raise ValueError("source task-binding evidence schema mismatch")
        rom = evidence.get("rom", {})
        if not isinstance(rom, dict) or rom.get("sha256") != rom_sha256:
            raise ValueError("source task-binding ROM mismatch")
        states = evidence.get("tracked_checkpoints", []) + evidence.get(
            "supplemental_states", []
        )
        matches = [
            row
            for row in states
            if isinstance(row, dict)
            and row.get("path") == input_state_path
            and row.get("sha256") == input_state_sha256
        ]
        if len(matches) != 1:
            raise ValueError("source task-binding input state identity mismatch")
        groups = {
            task.get("group_id")
            for task in matches[0].get("active_effect_tasks", [])
            if isinstance(task, dict)
        }
        if group_id not in groups:
            raise ValueError("source task-binding group is absent from the input state")
        return

    if artifact_schema not in {
        "battle-effect-pixel-ab-runtime-v1",
        "battle-effect-group5-pixel-ab-runtime-v1",
    }:
        raise ValueError("source runtime artifact schema is unsupported")
    if evidence.get("schema") != artifact_schema or evidence.get("verified") is not True:
        raise ValueError("source pixel A/B evidence schema or verification mismatch")
    binding = evidence.get("binding", {})
    edit = evidence.get("edit", {})
    evidence_group = (
        binding.get("group_id") if isinstance(binding, dict) else None
    )
    if evidence_group is None and isinstance(edit, dict):
        evidence_group = edit.get("group_id")
    if evidence_group != group_id:
        raise ValueError("source pixel A/B group mismatch")
    baseline = evidence.get("runs", {}).get("baseline", {})
    if (
        not isinstance(baseline, dict)
        or baseline.get("state_sha256") != input_state_sha256
        or baseline.get("rom_sha256") != rom_sha256
    ):
        raise ValueError("source pixel A/B baseline state or ROM mismatch")
    try:
        state_relative = _repository_path(
            root, input_state_path, "profile input state"
        ).relative_to(promotion_path.parent).as_posix()
    except ValueError as error:
        raise ValueError("profile input state is outside the source artifact") from error
    if promotion.get("files", {}).get(state_relative) != input_state_sha256:
        raise ValueError("profile input state is not hash-locked by the source artifact")


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


def effect_group_identity(catalog: dict[str, Any], group_id: int) -> tuple[int, int]:
    groups = catalog.get("groups")
    if (
        not isinstance(groups, list)
        or catalog.get("schema") != "battle-effect-sprite-animations-v1"
        or catalog.get("group_count") != len(groups)
        or len(groups) != 18
    ):
        raise ValueError("battle-effect animation catalog denominator mismatch")
    matches = [row for row in groups if row.get("group_id") == group_id]
    if len(matches) != 1:
        raise ValueError("battle-effect group must occur exactly once in animation catalog")
    try:
        return (
            int(matches[0]["definition_pointer_table"], 16),
            int(matches[0]["animation_pointer_table"], 16),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("battle-effect group pointer identity is invalid") from error


def renderer_shadow_change_required(
    profile: dict[str, Any], contract: dict[str, Any], *, group_id: int
) -> bool:
    transaction = profile.get("oam_transaction")
    if transaction is None:
        return True
    if not isinstance(transaction, dict) or not isinstance(
        transaction.get("renderer_shadow_change"), bool
    ):
        raise ValueError("OAM transaction expectation is invalid")
    required = transaction["renderer_shadow_change"]
    if required:
        return True
    expected_route = {
        "kind": "type-1-zero-event",
        "selector_callsite": "0x08081FB8",
        "sequence_id": 7,
        "spawn_callsite": "0x08081FD2",
    }
    if (
        group_id != 18
        or profile.get("profile_id")
        != "group-18-natural-tool67-zero-event-expiry"
        or contract.get("source_kind") != "natural_delayed_object_checkpoint"
        or contract.get("expiry_route") != expected_route
    ):
        raise ValueError("stable OAM transaction lacks verified Group 18 provenance")
    return False


def expected_phase_inputs(
    profile: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    mode = profile.get("input_mode")
    if mode == "zero-input-active-state":
        if profile.get("inputs", []) != []:
            raise ValueError("zero-input phase profile contains inputs")
        return mode, []
    if mode != "explicit-input-sequence":
        raise ValueError("phase profile input mode is unsupported")
    capture = profile.get("capture_frame")
    raw_events = profile.get("inputs")
    if (
        not isinstance(capture, int)
        or isinstance(capture, bool)
        or not isinstance(raw_events, list)
        or not raw_events
    ):
        raise ValueError("explicit phase input sequence is invalid")
    valid_keys = {"Down", "A", "B", "L", "R", "Up", "Right", "Left", "Start"}
    events = []
    previous_up = 0
    for raw in raw_events:
        if not isinstance(raw, str):
            raise ValueError("explicit phase input event is invalid")
        fields = raw.split(":")
        if len(fields) != 3 or fields[0] not in valid_keys:
            raise ValueError("explicit phase input event is invalid")
        try:
            down, up = int(fields[1], 10), int(fields[2], 10)
        except ValueError as error:
            raise ValueError("explicit phase input event is invalid") from error
        if (
            str(down) != fields[1]
            or str(up) != fields[2]
            or not 0 < down < up < capture
            or down < previous_up
        ):
            raise ValueError("explicit phase input event is invalid")
        events.append(
            {
                "key": fields[0],
                "down_frame": down,
                "up_frame": up,
                "hold_frames": up - down,
            }
        )
        previous_up = up
    return mode, events


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
    expected_definition: int | None = None
    expected_animation: int | None = None
    ack_match = False
    renderer_differs = False
    expected_input_mode: str | None = None
    expected_inputs: list[dict[str, Any]] = []

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
    _record_error(
        errors,
        isinstance(group_id, int)
        and not isinstance(group_id, bool)
        and 1 <= group_id <= 18,
        "group id is outside 1..18",
    )
    _record_error(
        errors,
        manifest.get("input_mode")
        in {"zero-input-active-state", "explicit-input-sequence"},
        "input mode mismatch",
    )
    _record_error(errors, isinstance(manifest.get("inputs"), list), "manifest inputs are invalid")
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

    profile: dict[str, Any] = {}
    source_contract: dict[str, Any] = {}
    profile_info = manifest.get("profile", {})
    if isinstance(profile_info, dict):
        profile_path = ROOT / str(profile_info.get("path", ""))
        _record_error(errors, profile_path.is_file(), "capture profile is missing")
        if profile_path.is_file():
            profile_hash = _sha256(profile_path)
            _record_error(errors, profile_hash == profile_info.get("sha256"), "capture profile hash mismatch")
            _record_error(
                errors,
                audit.get("profile_sha256")
                == profile_info.get("sha256")
                == profile_hash,
                "runtime audit profile hash mismatch",
            )
            profile = _object(profile_path)
            try:
                expected_input_mode, expected_inputs = expected_phase_inputs(profile)
            except ValueError as error:
                errors.append(str(error))
            else:
                _record_error(
                    errors,
                    manifest.get("input_mode") == expected_input_mode,
                    "manifest input mode differs from profile",
                )
                _record_error(
                    errors,
                    manifest.get("inputs") == expected_inputs,
                    "manifest inputs differ from profile",
                )
            input_info = manifest.get("input_state", {})
            input_path = ROOT / str(input_info.get("path", "")) if isinstance(input_info, dict) else ROOT
            _record_error(errors, profile.get("schema") == "battle-effect-phase-capture-profile-v1", "capture profile schema mismatch")
            _record_error(errors, profile.get("group_id") == group_id, "capture profile group mismatch")
            _record_error(errors, profile.get("source_rom_sha256") == manifest.get("rom_sha256"), "profile source ROM hash mismatch")
            _record_error(errors, input_path.is_file(), "input savestate is missing")
            if input_path.is_file() and isinstance(input_info, dict):
                _record_error(errors, _sha256(input_path) == input_info.get("sha256"), "input savestate hash mismatch")
                _record_error(errors, profile.get("input_state_sha256") == input_info.get("sha256"), "profile input hash mismatch")
            source_info = manifest.get("source_runtime_provenance", {})
            if not isinstance(source_info, dict):
                errors.append("source runtime provenance is missing")
            else:
                try:
                    catalog_info = source_info.get("catalog", {})
                    catalog_path = _repository_path(
                        ROOT,
                        catalog_info.get("path") if isinstance(catalog_info, dict) else None,
                        "source runtime provenance catalog",
                    )
                    if _sha256(catalog_path) != catalog_info.get("sha256"):
                        raise ValueError("source runtime provenance catalog hash mismatch")
                    catalog = _object(catalog_path)
                    if catalog.get("schema") != SOURCE_PROVENANCE_SCHEMA:
                        raise ValueError("source runtime provenance catalog schema mismatch")
                    matches = [
                        row
                        for row in catalog.get("profiles", [])
                        if isinstance(row, dict)
                        and row.get("profile_id") == profile.get("profile_id")
                        and row.get("group_id") == group_id
                    ]
                    if len(matches) != 1:
                        raise ValueError("source runtime provenance contract mismatch")
                    contract = source_info.get("contract")
                    if not isinstance(contract, dict):
                        raise ValueError("source runtime provenance contract mismatch")
                    source_contract = contract
                    validate_source_runtime_provenance(
                        ROOT,
                        profile,
                        contract,
                        group_id=int(group_id),
                        input_state_path=str(input_info.get("path", "")),
                        input_state_sha256=str(input_info.get("sha256", "")),
                        rom_sha256=str(manifest.get("rom_sha256", "")),
                    )
                    if contract != matches[0]:
                        raise ValueError("source runtime provenance contract mismatch")
                except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
                    errors.append(str(error))
    else:
        errors.append("capture profile provenance is missing")

    animations_info = manifest.get("animations", {})
    if isinstance(animations_info, dict):
        animations_path = ROOT / str(animations_info.get("path", ""))
        _record_error(errors, animations_path.is_file(), "animation catalog is missing")
        if animations_path.is_file():
            _record_error(errors, _sha256(animations_path) == animations_info.get("sha256"), "animation catalog hash mismatch")
            try:
                expected_definition, expected_animation = effect_group_identity(
                    _object(animations_path), int(group_id)
                )
            except (TypeError, ValueError) as error:
                errors.append(str(error))
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
            _record_error(errors, expected_definition is not None and definition == expected_definition, f"{name} definition pointer mismatch")
            _record_error(errors, expected_animation is not None and animation == expected_animation, f"{name} animation pointer mismatch")
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
        len(target_dispatch_ordinals) == 3
        and len(set(target_dispatch_ordinals)) == 1,
        "target task dispatcher ordinal changed across phases",
    )
    if len(buffers) == 3:
        renderer = buffers["renderer-post"]
        submit = buffers["submit-post"]
        ack = buffers["ack-post"]
        renderer_differs = renderer["shadow-oam.bin"] != renderer["hardware-oam.bin"]
        ack_match = ack["shadow-oam.bin"] == ack["hardware-oam.bin"]
        try:
            require_renderer_change = renderer_shadow_change_required(
                profile, source_contract, group_id=int(group_id)
            )
        except (TypeError, ValueError) as error:
            errors.append(str(error))
            require_renderer_change = True
        _record_error(
            errors,
            renderer_differs == require_renderer_change,
            (
                "renderer shadow OAM already equals hardware OAM"
                if require_renderer_change
                else "stable renderer unexpectedly changed shadow OAM"
            ),
        )
        _record_error(errors, submit["shadow-oam.bin"] == renderer["shadow-oam.bin"], "shadow OAM changed before submission")
        _record_error(errors, submit["hardware-oam.bin"] == renderer["hardware-oam.bin"], "hardware OAM changed before acknowledgement")
        _record_error(errors, ack_match, "acknowledged shadow and hardware OAM differ")
        _record_error(errors, ack["hardware-oam.bin"] == renderer["shadow-oam.bin"], "acknowledged hardware OAM is not rendered shadow OAM")
        _record_error(errors, len({buffers[name]["task-pool.bin"] for name, _, _ in PHASES}) == 1, "task pool changed across phases")

    _record_error(errors, audit.get("schema") == "mgba-battle-effect-phase-capture-v1", "runtime audit schema mismatch")
    _record_error(errors, audit.get("outcome") == "three-phase-captured", "runtime audit outcome mismatch")
    _record_error(errors, audit.get("group_id") == group_id, "runtime audit group mismatch")
    _record_error(errors, audit.get("input_mode") == expected_input_mode, "runtime audit input mode mismatch")
    _record_error(errors, audit.get("inputs") == expected_inputs, "runtime audit inputs mismatch")
    for field in ("automatic_inputs", "recovery_inputs"):
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
