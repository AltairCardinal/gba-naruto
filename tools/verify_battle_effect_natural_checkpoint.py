#!/usr/bin/env python3
"""Independently verify a natural delayed-object battle-effect checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from tools.inspect_mgba_savestate import load_gba_state
    from tools.verify_battlefield_object_producers import verify as verify_producers
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state
    from verify_battlefield_object_producers import verify as verify_producers


ROOT = Path(__file__).resolve().parents[1]
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "battle-effect-natural-checkpoint-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
OBJECT_BASE = 0x02026604
OBJECT_STRIDE = 0x10
TASK_BASE = 0x03003BB8
TASK_SIZE = 0x3C
TASK_COUNT = 128
ANIMATIONS = ROOT / "artifacts/battle-effect-sprite-animations-v1/manifest.json"
EXPECTED_OBJECT = {
    "slot": 3,
    "state": 1,
    "x": 13,
    "y": 6,
    "ninja_tool_id": 67,
    "encoded_action": "0xC3",
    "remaining_turns": 0,
    "resource_group_id": 18,
}
EXPECTED_ROUTE = {
    "kind": "type-1-zero-event",
    "selector_callsite": "0x08081FB8",
    "sequence_id": 7,
    "spawn_callsite": "0x08081FD2",
}
EXPECTED_RUNTIME_PHASE = {
    "current_thumb_pc": "0x08061126",
    "submission_pending": 1,
    "task_slot": 114,
    "definition_pointer": "0x0834819C",
    "animation_pointer": "0x083481DC",
}
EXPECTED_STAGES = (
    "tool-submitted",
    "target-right2",
    "object-created",
    "expiry-ready",
)


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


def _safe_file(artifact: Path, relative: Any) -> Path:
    if not isinstance(relative, str):
        raise ValueError("artifact path is missing")
    value = Path(relative)
    if value.is_absolute() or ".." in value.parts:
        raise ValueError("artifact path is unsafe")
    path = (artifact / value).resolve(strict=True)
    path.relative_to(artifact)
    return path


def _group_identity(group_id: int) -> tuple[int, int]:
    catalog = _object(ANIMATIONS)
    groups = catalog.get("groups")
    matches = (
        [row for row in groups if row.get("group_id") == group_id]
        if isinstance(groups, list)
        else []
    )
    if len(matches) != 1:
        raise ValueError("battle-effect group identity is not unique")
    return (
        int(matches[0]["definition_pointer_table"], 16),
        int(matches[0]["animation_pointer_table"], 16),
    )


def _state_object(state_path: Path, slot: int) -> bytes:
    state = load_gba_state(state_path)
    return state.read_memory(OBJECT_BASE + slot * OBJECT_STRIDE, OBJECT_STRIDE)


def _active_group_tasks(state_path: Path, group_id: int) -> int:
    definition, animation = _group_identity(group_id)
    state = load_gba_state(state_path)
    count = 0
    for slot in range(TASK_COUNT):
        task = state.read_memory(TASK_BASE + slot * TASK_SIZE, TASK_SIZE)
        if (
            int.from_bytes(task[0:4], "little") & 1
            and int.from_bytes(task[0x1C:0x20], "little") == definition
            and int.from_bytes(task[0x20:0x24], "little") == animation
        ):
            count += 1
    return count


def _record(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def _validate_state_check(
    errors: list[str], path: Path, *, state_sha256: str, remaining_turns: int
) -> None:
    payload = _object(path)
    hits = payload.get("hits")
    hit = hits[0] if isinstance(hits, list) and len(hits) == 1 else {}
    special = hit.get("active_special_objects") if isinstance(hit, dict) else None
    expected = {
        "encoded_action": "0xC3",
        "remaining_turns": remaining_turns,
        "slot": 3,
        "state": 1,
    }
    _record(errors, payload.get("errors") == [], "state check contains errors")
    _record(errors, hit.get("sha256") == state_sha256, "state check hash mismatch")
    _record(errors, special == [expected], "state check delayed object mismatch")
    inventory = hit.get("inventory_special_tools", [])
    _record(
        errors,
        {"count": 1, "ninja_tool_id": 67} in inventory,
        "state check tool-67 inventory mismatch",
    )


def verify_artifact(artifact: Path) -> dict[str, Any]:
    artifact = Path(artifact).resolve()
    errors: list[str] = []
    try:
        manifest = _object(artifact / "manifest.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {"errors": [f"manifest unreadable: {error}"]}

    _record(errors, manifest.get("schema") == PROMOTION_SCHEMA, "promotion schema mismatch")
    _record(errors, manifest.get("artifact_schema") == SCHEMA, "artifact schema mismatch")
    _record(errors, manifest.get("artifact_status") == "accepted", "artifact is not accepted")
    _record(errors, manifest.get("group_id") == 18, "group identity mismatch")
    _record(errors, manifest.get("sequence_id") == 7, "sequence identity mismatch")
    _record(errors, manifest.get("rom_sha256") == ROM_SHA256, "ROM identity mismatch")
    _record(
        errors,
        manifest.get("delayed_object") == EXPECTED_OBJECT,
        "delayed object contract mismatch",
    )
    _record(errors, manifest.get("expiry_route") == EXPECTED_ROUTE, "expiry route contract mismatch")
    _record(
        errors,
        manifest.get("runtime_phase") == EXPECTED_RUNTIME_PHASE,
        "runtime phase contract mismatch",
    )

    files = manifest.get("files")
    if not isinstance(files, dict):
        errors.append("file inventory is missing")
        files = {}
    actual = {
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    _record(errors, actual == set(files), "file inventory mismatch")
    for relative, expected_hash in files.items():
        try:
            path = _safe_file(artifact, relative)
            _record(errors, _sha256(path) == expected_hash, f"file hash mismatch: {relative}")
        except (OSError, ValueError) as error:
            errors.append(f"file unavailable: {relative}: {error}")

    input_state = manifest.get("input_state")
    expected_input = {
        "path": "artifacts/battle-effect-group18-natural-checkpoint-v1/raw/expiry-ready.ss9",
        "sha256": files.get("raw/expiry-ready.ss9"),
    }
    _record(errors, input_state == expected_input, "checkpoint input-state identity mismatch")
    expected_source_states = {
        "object-created": {
            "path": (
                "artifacts/battle-effect-group18-natural-checkpoint-v1/"
                "raw/object-created.ss9"
            ),
            "sha256": files.get("raw/object-created.ss9"),
            "remaining_turns": 2,
            "active_group_tasks": 0,
        },
        "first-submit": {
            "path": (
                "artifacts/battle-effect-group18-natural-checkpoint-v1/"
                "raw/expiry-ready.ss9"
            ),
            "sha256": files.get("raw/expiry-ready.ss9"),
            "remaining_turns": 0,
            "active_group_tasks": 1,
        },
    }
    source_states = manifest.get("source_states")
    _record(
        errors,
        source_states == expected_source_states,
        "checkpoint source-state contract mismatch",
    )

    chain = manifest.get("runtime_chain")
    if not isinstance(chain, list) or [row.get("stage") for row in chain] != list(EXPECTED_STAGES):
        errors.append("runtime chain stage mismatch")
        chain = []
    for row in chain:
        try:
            audit_path = _safe_file(artifact, row.get("audit"))
            guard_path = _safe_file(artifact, row.get("guard"))
            input_path = _safe_file(artifact, row.get("input_state"))
            output_path = _safe_file(artifact, row.get("output_state"))
            audit = _object(audit_path)
            guard = _object(guard_path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"runtime chain file error: {error}")
            continue
        stage = row["stage"]
        _record(errors, audit.get("success") is True, f"{stage} audit is not successful")
        _record(errors, audit.get("status") == "capture-complete", f"{stage} audit is incomplete")
        _record(errors, audit.get("rom_sha256") == ROM_SHA256, f"{stage} ROM mismatch")
        _record(errors, audit.get("staged_rom_sha256") == ROM_SHA256, f"{stage} staged ROM mismatch")
        _record(errors, audit.get("input_state_sha256") == _sha256(input_path), f"{stage} input link mismatch")
        _record(errors, audit.get("output_state_sha256") == _sha256(output_path), f"{stage} output link mismatch")
        _record(errors, audit.get("automatic_inputs") == [], f"{stage} has automatic inputs")
        _record(errors, audit.get("recovery_inputs") == [], f"{stage} has recovery inputs")
        _record(errors, audit.get("pgid_clean") is True, f"{stage} process tree is not clean")
        residue = audit.get("runtime_residue", {})
        _record(
            errors,
            isinstance(residue, dict)
            and residue.get("pgid_clean") is True
            and residue.get("mgba_listener_clean") is True,
            f"{stage} runtime residue mismatch",
        )
        _record(errors, _sha256(guard_path) == audit.get("guard_summary_sha256"), f"{stage} guard hash mismatch")
        _record(errors, guard.get("reason") == "completed", f"{stage} guard did not complete")
        _record(errors, guard.get("exit_code") == 0, f"{stage} guard exit mismatch")
        _record(errors, guard.get("degraded") is False, f"{stage} guard was degraded")

    try:
        created_path = _safe_file(artifact, "raw/object-created.ss9")
        ready_path = _safe_file(artifact, "raw/expiry-ready.ss9")
        created_raw = _state_object(created_path, 3)
        ready_raw = _state_object(ready_path, 3)
        _record(
            errors,
            created_raw.hex() == "010d0600c300020001000202ac560003",
            "created delayed object bytes mismatch",
        )
        _record(
            errors,
            ready_raw.hex() == "010d0600c300000001000202ac560003",
            "expiry-ready delayed object bytes mismatch",
        )
        ready_state = load_gba_state(ready_path)
        current_thumb_pc = (ready_state.registers[15] - 4) & 0xFFFFFFFF
        task = ready_state.read_memory(TASK_BASE + 114 * TASK_SIZE, TASK_SIZE)
        definition, animation = _group_identity(18)
        _record(errors, _active_group_tasks(ready_path, 18) == 1, "checkpoint Group 18 task count mismatch")
        _record(errors, current_thumb_pc == 0x08061126, "checkpoint is not at submit-post")
        _record(
            errors,
            int.from_bytes(ready_state.read_memory(0x0300067C, 2), "little") == 1,
            "checkpoint submission pending mismatch",
        )
        _record(
            errors,
            int.from_bytes(task[0x1C:0x20], "little") == definition
            and int.from_bytes(task[0x20:0x24], "little") == animation,
            "checkpoint Group 18 task identity mismatch",
        )
        _validate_state_check(
            errors,
            _safe_file(artifact, "raw/object-created-check.json"),
            state_sha256=_sha256(created_path),
            remaining_turns=2,
        )
        _validate_state_check(
            errors,
            _safe_file(artifact, "raw/expiry-ready-check.json"),
            state_sha256=_sha256(ready_path),
            remaining_turns=0,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"checkpoint state verification failed: {error}")
        ready_raw = b""

    static = manifest.get("static_producers")
    try:
        static_path = _safe_file(artifact, static.get("path"))
        _record(errors, _sha256(static_path) == static.get("sha256"), "static producer hash mismatch")
        static_result = verify_producers(ROOT, _object(static_path))
        verified_paths = static_result.get("verified_group_18_paths", 0)
    except (AttributeError, OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"static producer verification failed: {error}")
        verified_paths = 0

    scope = manifest.get("scope")
    expected_scope = {
        "natural_tool_submission_verified": True,
        "natural_object_creation_verified": True,
        "natural_countdown_zero_verified": True,
        "static_zero_event_expiry_route_verified": True,
        "natural_expiry_runtime_verified": True,
        "modified_rom_pixel_ab_verified": False,
    }
    _record(errors, scope == expected_scope, "artifact scope mismatch")
    return {
        "errors": errors,
        "group_id": manifest.get("group_id"),
        "sequence_id": manifest.get("sequence_id"),
        "object_raw_hex": ready_raw.hex(),
        "verified_static_selector_paths": verified_paths,
        "verified_source_states": (
            list(expected_source_states) if source_states == expected_source_states else []
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    result = verify_artifact(args.artifact)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
