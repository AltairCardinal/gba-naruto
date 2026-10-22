#!/usr/bin/env python3
"""Bind composite victory and escort failure transitions to original-ROM states."""

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


BATTLE_CONTROL_BASE = 0x02026804
BATTLE_CONTROL_SIZE = 0x10
BATTLE_RESULT_ADDRESS = 0x02026807
UNIT_POOL_BASE = 0x020240C0
UNIT_RECORD_SIZE = 0x1D4
UNIT_CHARACTER_ID_OFFSET = 0x00
UNIT_FACING_OFFSET = 0xC6
UNIT_CURRENT_X_OFFSET = 0xC7
UNIT_CURRENT_Y_OFFSET = 0xC8


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_hash(root: Path, relative: str, expected: str, label: str) -> Path:
    path = root / relative
    if _sha256(path) != expected:
        raise ValueError(f"{label} SHA-256 mismatch for {relative}")
    return path


def _unit_record(state: Any, slot: int) -> bytes:
    return state.read_memory(
        UNIT_POOL_BASE + slot * UNIT_RECORD_SIZE, UNIT_RECORD_SIZE
    )


def _control_diffs(before: bytes, after: bytes) -> list[dict[str, int | str]]:
    return [
        {
            "address": _hex(BATTLE_CONTROL_BASE + offset),
            "offset": _hex(offset, 2),
            "before": old,
            "after": new,
        }
        for offset, (old, new) in enumerate(zip(before, after))
        if old != new
    ]


def _expect(actual: Any, expected: Any, label: str, transition_id: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch for {transition_id}: expected {expected!r}, got {actual!r}"
        )


def analyze_objective_transition(
    root: Path | str,
    rom_path: Path | str,
    states_path: Path | str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    root = Path(root)
    transition_id = observation["id"]
    before_path = _validate_hash(
        root, observation["before"], observation["before_sha256"], "checkpoint"
    )
    after_path = _validate_hash(
        root, observation["after"], observation["after_sha256"], "checkpoint"
    )
    for prefix in ("before", "after"):
        audit_key = f"{prefix}_audit"
        if audit_key in observation:
            _validate_hash(
                root,
                observation[audit_key],
                observation[f"{audit_key}_sha256"],
                "audit",
            )

    before_binding = analyze_checkpoint(rom_path, states_path, before_path)
    after_binding = analyze_checkpoint(rom_path, states_path, after_path)
    before_state_name = before_binding["controller_state_hex"]
    after_state_name = after_binding["controller_state_hex"]
    _expect(
        before_state_name,
        observation["expected_before_state"],
        "before controller state",
        transition_id,
    )
    _expect(
        after_state_name,
        observation["expected_after_state"],
        "after controller state",
        transition_id,
    )

    before = load_gba_state(before_path)
    after = load_gba_state(after_path)
    battle_id_before = before.read_memory(BATTLE_CONTROL_BASE + 1, 1)[0]
    battle_id_after = after.read_memory(BATTLE_CONTROL_BASE + 1, 1)[0]
    _expect(
        battle_id_before,
        observation["expected_battle_id"],
        "before battle ID",
        transition_id,
    )
    _expect(
        battle_id_after,
        observation["expected_battle_id"],
        "after battle ID",
        transition_id,
    )
    result_before = before.read_memory(BATTLE_RESULT_ADDRESS, 1)[0]
    result_after = after.read_memory(BATTLE_RESULT_ADDRESS, 1)[0]
    _expect(
        result_before,
        observation["expected_result_before"],
        "before result",
        transition_id,
    )
    _expect(
        result_after,
        observation["expected_result_after"],
        "after result",
        transition_id,
    )
    control_before = before.read_memory(BATTLE_CONTROL_BASE, BATTLE_CONTROL_SIZE)
    control_after = after.read_memory(BATTLE_CONTROL_BASE, BATTLE_CONTROL_SIZE)

    result: dict[str, Any] = {
        "id": transition_id,
        "kind": observation["kind"],
        "before": observation["before"],
        "before_sha256": observation["before_sha256"],
        "after": observation["after"],
        "after_sha256": observation["after_sha256"],
        "battle_id": battle_id_before,
        "before_controller_state": before_state_name,
        "after_controller_state": after_state_name,
        "result_before": result_before,
        "result_after": result_after,
        "battle_control_diffs": _control_diffs(control_before, control_after),
    }

    if observation["kind"] == "composite_victory":
        actor_slot = observation["actor_slot"]
        actor = _unit_record(after, actor_slot)
        actor_summary = {
            "slot": actor_slot,
            "character_id": actor[UNIT_CHARACTER_ID_OFFSET],
            "current_x": actor[UNIT_CURRENT_X_OFFSET],
            "current_y": actor[UNIT_CURRENT_Y_OFFSET],
            "facing": actor[UNIT_FACING_OFFSET],
        }
        expected_actor = {
            "slot": actor_slot,
            "character_id": observation["expected_actor_character_id"],
            "current_x": observation["expected_current_x"],
            "current_y": observation["expected_current_y"],
            "facing": observation["expected_facing"],
        }
        _expect(actor_summary, expected_actor, "goal actor", transition_id)
        defeated_slot = observation["required_defeated_slot"]
        defeated_id = _unit_record(after, defeated_slot)[UNIT_CHARACTER_ID_OFFSET]
        _expect(
            defeated_id,
            observation["expected_defeated_character_id"],
            "required defeated unit",
            transition_id,
        )
        result.update(
            {
                "actor": actor_summary,
                "required_defeated_slot": defeated_slot,
                "required_defeated_character_id": defeated_id,
                "composite_goal_observed": (
                    result_before == 0
                    and result_after == 1
                    and before_state_name == "0xE000"
                    and after_state_name == "0xE010"
                ),
            }
        )
        if not result["composite_goal_observed"]:
            raise ValueError(f"composite victory boundary not proven for {transition_id}")
        return result

    if observation["kind"] != "escort_failure":
        raise ValueError(f"unsupported objective transition kind: {observation['kind']}")
    escort_slot = observation["escort_slot"]
    escort_before = _unit_record(before, escort_slot)[UNIT_CHARACTER_ID_OFFSET]
    escort_after = _unit_record(after, escort_slot)[UNIT_CHARACTER_ID_OFFSET]
    _expect(
        escort_before,
        observation["expected_escort_character_id_before"],
        "before escort character ID",
        transition_id,
    )
    _expect(
        escort_after,
        observation["expected_escort_character_id_after"],
        "after escort character ID",
        transition_id,
    )
    living_player_slots = [
        slot
        for slot in range(1, 4)
        if _unit_record(after, slot)[UNIT_CHARACTER_ID_OFFSET] != 0
    ]
    _expect(
        living_player_slots,
        observation["expected_living_player_slots"],
        "living player slots",
        transition_id,
    )
    result.update(
        {
            "escort_slot": escort_slot,
            "escort_character_id_before": escort_before,
            "escort_character_id_after": escort_after,
            "living_player_slots": living_player_slots,
            "outcome_interrupts_within_resolution": (
                before_state_name == "0x8000"
                and after_state_name == "0x8000"
                and result_before == 0
                and result_after == 2
                and result["battle_control_diffs"]
                == [
                    {
                        "address": _hex(BATTLE_RESULT_ADDRESS),
                        "offset": "0x03",
                        "before": 0,
                        "after": 2,
                    }
                ]
            ),
        }
    )
    if not result["outcome_interrupts_within_resolution"]:
        raise ValueError(f"escort failure boundary not proven for {transition_id}")
    return result


def build_objective_manifest(
    root: Path | str,
    rom_path: Path | str,
    states_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported battle objective transition schema")
    transitions = [
        analyze_objective_transition(root, rom_path, states_path, observation)
        for observation in source["observations"]
    ]
    return {
        "schema_version": 1,
        "identity": "battle_objective_and_outcome_boundaries",
        "method": source["method"],
        "rom": str(Path(rom_path)),
        "state_inventory": str(Path(states_path)),
        "transition_count": len(transitions),
        "transitions": transitions,
        "conclusion": (
            "The sampled battle 44 victory is asserted only after the defeated-unit and "
            "position/facing conditions coexist. The sampled battle 15 escort loss changes "
            "only the result byte from 0 to 2 while remaining inside controller state 0x8000."
        ),
        "boundary": (
            "These samples prove two objective/outcome boundaries, not the complete condition "
            "bytecode, every scenario predicate, or global victory/failure precedence."
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
        default=Path("notes/battle-objective-transition-observations-20260723.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-objective-transition-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_objective_manifest(
        args.root, args.rom, args.states, args.observations
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
