#!/usr/bin/env python3
"""Bind normal damage and substitution to original-ROM resolution boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.analyze_battle_controller_checkpoints import analyze_checkpoint
from tools.inspect_mgba_savestate import load_gba_state


UNIT_POOL_BASE = 0x020240C0
UNIT_RECORD_SIZE = 0x1D4
CURRENT_CHAKRA_OFFSET = 0x07
CURRENT_HP_OFFSET = 0x0C
ACTION_FLAGS_LOW_OFFSET = 0xC0
CURRENT_X_OFFSET = 0xC7
CURRENT_Y_OFFSET = 0xC8
TARGET_RESOLUTION_CODE_OFFSET = 0x154


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_hash(root: Path, relative: str, expected: str, label: str) -> Path:
    path = root / relative
    if _sha256(path) != expected:
        raise ValueError(f"{label} SHA-256 mismatch for {relative}")
    return path


def _expect(actual: Any, expected: Any, label: str, branch_id: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch for {branch_id}: expected {expected!r}, got {actual!r}"
        )


def _unit_record(state: Any, slot: int) -> bytes:
    return state.read_memory(
        UNIT_POOL_BASE + slot * UNIT_RECORD_SIZE, UNIT_RECORD_SIZE
    )


def _unit_values(record: bytes) -> dict[str, Any]:
    return {
        "character_id": record[0],
        "current_chakra": record[CURRENT_CHAKRA_OFFSET],
        "current_hp": int.from_bytes(
            record[CURRENT_HP_OFFSET : CURRENT_HP_OFFSET + 2], "little"
        ),
        "action_flags_low": record[ACTION_FLAGS_LOW_OFFSET],
        "position": [record[CURRENT_X_OFFSET], record[CURRENT_Y_OFFSET]],
        "resolution_code": record[TARGET_RESOLUTION_CODE_OFFSET],
    }


def _record_diffs(
    before: bytes, after: bytes, slot: int
) -> list[dict[str, int | str]]:
    base = UNIT_POOL_BASE + slot * UNIT_RECORD_SIZE
    return [
        {
            "address": _hex(base + offset),
            "offset": _hex(offset, 3),
            "before": old,
            "after": new,
        }
        for offset, (old, new) in enumerate(zip(before, after))
        if old != new
    ]


def _validate_audit(
    root: Path,
    relative: str,
    expected_hash: str,
    label: str,
    branch_id: str,
    expected_mode: str,
    expected_input_hash: str,
    expected_output_hash: str,
    expected_key: str | None,
) -> dict[str, Any]:
    path = _validate_hash(root, relative, expected_hash, label)
    audit = json.loads(path.read_text(encoding="utf-8"))
    _expect(audit["evidence_mode"], expected_mode, f"{label} mode", branch_id)
    _expect(
        audit["input_state_sha256"],
        expected_input_hash,
        f"{label} input checkpoint",
        branch_id,
    )
    _expect(
        audit["output_state_sha256"],
        expected_output_hash,
        f"{label} output checkpoint",
        branch_id,
    )
    inputs = audit["inputs"]
    if expected_key is None:
        _expect(inputs, [], f"{label} inputs", branch_id)
        _expect(audit.get("zero_input_verified"), True, f"{label} zero input", branch_id)
    else:
        _expect(len(inputs), 1, f"{label} input count", branch_id)
        _expect(inputs[0]["key"], expected_key, f"{label} input key", branch_id)
    return audit


def analyze_effect_branch(
    root: Path,
    rom_path: Path | str,
    states_path: Path | str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    branch_id = observation["id"]
    before_path = _validate_hash(
        root, observation["before"], observation["before_sha256"], "checkpoint"
    )
    confirmed_path = _validate_hash(
        root,
        observation["confirmed"],
        observation["confirmed_sha256"],
        "checkpoint",
    )
    resolved_path = _validate_hash(
        root,
        observation["resolved"],
        observation["resolved_sha256"],
        "checkpoint",
    )
    confirm_audit = _validate_audit(
        root,
        observation["confirm_audit"],
        observation["confirm_audit_sha256"],
        "confirm audit",
        branch_id,
        "single-input",
        observation["before_sha256"],
        observation["confirmed_sha256"],
        "A",
    )
    resolve_mode = observation["resolve_evidence_mode"]
    resolve_audit = _validate_audit(
        root,
        observation["resolve_audit"],
        observation["resolve_audit_sha256"],
        "resolve audit",
        branch_id,
        resolve_mode,
        observation["confirmed_sha256"],
        observation["resolved_sha256"],
        observation.get("resolve_key"),
    )

    paths = [before_path, confirmed_path, resolved_path]
    bindings = [analyze_checkpoint(rom_path, states_path, path) for path in paths]
    controller_sequence = [row["controller_state_hex"] for row in bindings]
    _expect(
        controller_sequence,
        ["0x4100", "0x8000", "0x9000"],
        "controller sequence",
        branch_id,
    )
    states = [load_gba_state(path) for path in paths]
    actor_slot = observation["actor_slot"]
    target_slot = observation["target_slot"]
    actor_records = [_unit_record(state, actor_slot) for state in states]
    target_records = [_unit_record(state, target_slot) for state in states]
    actors = [_unit_values(record) for record in actor_records]
    targets = [_unit_values(record) for record in target_records]
    _expect(
        [row["character_id"] for row in actors],
        [observation["actor_character_id"]] * 3,
        "actor identity",
        branch_id,
    )
    _expect(
        [row["character_id"] for row in targets],
        [observation["target_character_id"]] * 3,
        "target identity",
        branch_id,
    )
    actor_chakra = [row["current_chakra"] for row in actors]
    actor_flags = [row["action_flags_low"] for row in actors]
    actor_position = [row["position"] for row in actors]
    target_hp = [row["current_hp"] for row in targets]
    target_position = [row["position"] for row in targets]
    target_resolution_code = [row["resolution_code"] for row in targets]
    _expect(
        actor_chakra,
        observation["expected_actor_chakra"],
        "actor chakra sequence",
        branch_id,
    )
    _expect(
        actor_flags,
        observation["expected_actor_action_flags_low"],
        "actor action-flag sequence",
        branch_id,
    )
    _expect(
        actor_position,
        observation["expected_actor_position"],
        "actor position sequence",
        branch_id,
    )
    _expect(
        target_hp,
        observation["expected_target_hp"],
        "target HP sequence",
        branch_id,
    )
    _expect(
        target_position,
        observation["expected_target_position"],
        "target position sequence",
        branch_id,
    )
    _expect(
        target_resolution_code,
        observation["expected_target_resolution_code"],
        "target resolution-code sequence",
        branch_id,
    )

    damage = (
        observation["kind"] == "damage"
        and target_hp[2] < target_hp[1]
        and target_position[2] == target_position[1]
        and actor_flags[2] != actor_flags[1]
    )
    substitution = (
        observation["kind"] == "substitution"
        and target_hp[2] == target_hp[1]
        and target_position[2] != target_position[1]
        and actor_chakra[2] < actor_chakra[1]
        and actor_flags[2] != actor_flags[1]
    )
    substitution_staged = (
        substitution
        and target_resolution_code[0] == 0
        and target_resolution_code[1] == 0x16
        and target_resolution_code[2] == 0
        and target_hp[0] == target_hp[1]
        and actor_chakra[0] == actor_chakra[1]
        and actor_flags[0] == actor_flags[1]
    )
    if observation["kind"] == "damage" and not damage:
        raise ValueError(f"normal damage branch not proven for {branch_id}")
    if observation["kind"] == "substitution" and not substitution:
        raise ValueError(f"substitution branch not proven for {branch_id}")
    if observation["kind"] not in {"damage", "substitution"}:
        raise ValueError(f"unsupported effect branch kind: {observation['kind']}")

    return {
        "id": branch_id,
        "kind": observation["kind"],
        "states": [observation["before"], observation["confirmed"], observation["resolved"]],
        "state_sha256": [
            observation["before_sha256"],
            observation["confirmed_sha256"],
            observation["resolved_sha256"],
        ],
        "confirm_audit": observation["confirm_audit"],
        "confirm_audit_sha256": observation["confirm_audit_sha256"],
        "confirm_peak_tree_rss_mib": confirm_audit.get("peak_tree_rss_mib"),
        "resolve_audit": observation["resolve_audit"],
        "resolve_audit_sha256": observation["resolve_audit_sha256"],
        "resolve_evidence_mode": resolve_mode,
        "resolve_peak_tree_rss_mib": resolve_audit.get("peak_tree_rss_mib"),
        "controller_sequence": controller_sequence,
        "actor_slot": actor_slot,
        "target_slot": target_slot,
        "actor_chakra": actor_chakra,
        "actor_action_flags_low": actor_flags,
        "actor_position": actor_position,
        "target_hp": target_hp,
        "target_position": target_position,
        "target_resolution_code_offset": _hex(TARGET_RESOLUTION_CODE_OFFSET, 3),
        "target_resolution_code": target_resolution_code,
        "actor_confirm_diffs": _record_diffs(actor_records[0], actor_records[1], actor_slot),
        "actor_resolution_diffs": _record_diffs(actor_records[1], actor_records[2], actor_slot),
        "target_confirm_diffs": _record_diffs(target_records[0], target_records[1], target_slot),
        "target_resolution_diffs": _record_diffs(target_records[1], target_records[2], target_slot),
        "damage_applied_without_target_displacement": damage,
        "substitution_prevented_damage_and_displaced_target": substitution,
        "substitution_reaction_staged_before_domain_commit": substitution_staged,
    }


def build_effect_resolution_manifest(
    root: Path | str,
    rom_path: Path | str,
    states_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported battle effect resolution schema")
    branches = [
        analyze_effect_branch(root, rom_path, states_path, observation)
        for observation in source["observations"]
    ]
    preview_not_committed = all(
        branch["target_hp"][0] == branch["target_hp"][1]
        and branch["actor_chakra"][0] == branch["actor_chakra"][1]
        and branch["actor_action_flags_low"][0]
        == branch["actor_action_flags_low"][1]
        for branch in branches
    )
    reaction_in_shared_resolution = (
        any(branch["substitution_prevented_damage_and_displaced_target"] for branch in branches)
        and all(branch["controller_sequence"][1] == "0x8000" for branch in branches)
    )
    if not preview_not_committed or not reaction_in_shared_resolution:
        raise ValueError("effect resolution boundary is not closed")
    return {
        "schema_version": 1,
        "identity": "battle_effect_resolution_branches",
        "method": source["method"],
        "branch_count": len(branches),
        "branches": branches,
        "preview_is_not_the_committed_outcome": preview_not_committed,
        "reaction_branch_occurs_inside_shared_resolution": reaction_in_shared_resolution,
        "conclusion": (
            "Both samples cross 0x4100 to shared resolution 0x8000 before HP, "
            "chakra cost, or action-complete state changes. The normal branch then "
            "applies 14 HP damage without target displacement; the substitution branch "
            "stages code 0x16 at target +0x154, then commits the actor cost/action "
            "while preserving target HP and displacing "
            "the target before facing state 0x9000."
        ),
        "boundary": (
            "These two samples prove one normal damage outcome and one substitution "
            "reaction. They do not yet establish the general damage formula, hit RNG, "
            "multi-hit ordering, defense modifiers, linked-attack composition, status "
            "priority, or every legal substitution destination."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--states",
        type=Path,
        default=Path("notes/battle-controller-states-20260723.json"),
    )
    parser.add_argument(
        "--observations",
        type=Path,
        default=Path("notes/battle-effect-resolution-observations-20260723.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-effect-resolution-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_effect_resolution_manifest(
        args.root, args.rom, args.states, args.observations
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
