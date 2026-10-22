#!/usr/bin/env python3
"""Bind defense-prompt browsing and category rejection to original-ROM states."""

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
UNIT_SLOT_COUNT = 13
BATTLE_CONTROL_BASE = 0x02026804
BATTLE_CONTROL_SIZE = 0x40
ACTION_MENU_BASE = 0x0200A880
ACTION_MENU_SIZE = 0x100


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_hash(root: Path, relative: str, expected: str, label: str) -> Path:
    path = root / relative
    if _sha256(path) != expected:
        raise ValueError(f"{label} SHA-256 mismatch for {relative}")
    return path


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _diff_region(before: bytes, after: bytes, base: int) -> list[dict[str, Any]]:
    return [
        {
            "address": _hex(base + offset),
            "offset": _hex(offset, 2),
            "before": old,
            "after": new,
        }
        for offset, (old, new) in enumerate(zip(before, after))
        if old != new
    ]


def build_defense_preparation_manifest(
    root: Path | str,
    rom_path: Path | str,
    states_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported battle defense preparation schema")

    states: dict[str, dict[str, Any]] = {}
    ordered_states = []
    for observation in source["states"]:
        path = _validate_hash(
            root, observation["checkpoint"], observation["sha256"], "checkpoint"
        )
        binding = analyze_checkpoint(rom_path, states_path, path)
        _expect(
            binding["controller_state_hex"],
            observation["expected_controller_state"],
            f"controller state for {observation['id']}",
        )
        _expect(
            binding["current_unit_pointer"],
            source["expected_actor_pointer"],
            f"actor pointer for {observation['id']}",
        )
        current_unit = binding["current_unit"]
        if current_unit is None:
            raise ValueError(f"missing current actor for {observation['id']}")
        _expect(
            current_unit["slot"],
            source["expected_actor_slot"],
            f"actor slot for {observation['id']}",
        )
        _expect(
            current_unit["character_id"],
            source["expected_actor_character_id"],
            f"actor identity for {observation['id']}",
        )
        _expect(
            current_unit["action_flags"],
            source["expected_actor_action_flags"],
            f"actor action flags for {observation['id']}",
        )
        row = {
            "id": observation["id"],
            "checkpoint": observation["checkpoint"],
            "checkpoint_sha256": observation["sha256"],
            "binding": binding,
            "state": load_gba_state(path),
            "manual_visual_identity": observation.get("manual_visual_identity"),
        }
        states[observation["id"]] = row
        ordered_states.append(row)

    transitions = []
    for observation in source["transitions"]:
        audit_path = _validate_hash(
            root, observation["audit"], observation["audit_sha256"], "audit"
        )
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        before = states[observation["from_state"]]
        after = states[observation["to_state"]]
        _expect(audit["evidence_mode"], "single-input", "audit evidence mode")
        _expect(len(audit["inputs"]), 1, "audit input count")
        _expect(audit["inputs"][0]["key"], observation["expected_key"], "audit input key")
        _expect(
            audit["input_state_sha256"],
            before["checkpoint_sha256"],
            "audit input checkpoint hash",
        )
        _expect(
            audit["output_state_sha256"],
            after["checkpoint_sha256"],
            "audit output checkpoint hash",
        )
        visual = after["manual_visual_identity"]
        if visual:
            _expect(
                audit["output_png_sha256"],
                visual["screenshot_sha256"],
                "visible rejection screenshot hash",
            )
        before_state = before["state"]
        after_state = after["state"]
        unit_pool_diffs = _diff_region(
            before_state.read_memory(
                UNIT_POOL_BASE, UNIT_RECORD_SIZE * UNIT_SLOT_COUNT
            ),
            after_state.read_memory(
                UNIT_POOL_BASE, UNIT_RECORD_SIZE * UNIT_SLOT_COUNT
            ),
            UNIT_POOL_BASE,
        )
        battle_control_diffs = _diff_region(
            before_state.read_memory(BATTLE_CONTROL_BASE, BATTLE_CONTROL_SIZE),
            after_state.read_memory(BATTLE_CONTROL_BASE, BATTLE_CONTROL_SIZE),
            BATTLE_CONTROL_BASE,
        )
        action_menu_diffs = _diff_region(
            before_state.read_memory(ACTION_MENU_BASE, ACTION_MENU_SIZE),
            after_state.read_memory(ACTION_MENU_BASE, ACTION_MENU_SIZE),
            ACTION_MENU_BASE,
        )
        if unit_pool_diffs or battle_control_diffs or not action_menu_diffs:
            raise ValueError(
                f"defense UI transition changed unexpected domain state: {observation['id']}"
            )
        transitions.append(
            {
                "id": observation["id"],
                "key": observation["expected_key"],
                "audit": observation["audit"],
                "audit_sha256": observation["audit_sha256"],
                "from_controller_state": before["binding"]["controller_state_hex"],
                "to_controller_state": after["binding"]["controller_state_hex"],
                "unit_pool_diffs": unit_pool_diffs,
                "battle_control_diffs": battle_control_diffs,
                "action_menu_diffs": action_menu_diffs,
            }
        )

    controller_sequence = [
        row["binding"]["controller_state_hex"] for row in ordered_states
    ]
    input_sequence = [row["key"] for row in transitions]
    final_visual = ordered_states[-1]["manual_visual_identity"]
    if final_visual is None:
        raise ValueError("missing visible rejection identity")
    separated = (
        controller_sequence == ["0x9100", "0x9100", "0x9200", "0x9200"]
        and input_sequence == ["Up", "A", "A"]
        and all(not row["unit_pool_diffs"] for row in transitions)
        and all(not row["battle_control_diffs"] for row in transitions)
    )
    rejected = separated and transitions[-1]["to_controller_state"] == "0x9200"
    if not separated or not rejected:
        raise ValueError("defense category confirmation boundary is not proven")
    return {
        "schema_version": 1,
        "identity": "battle_defense_preparation_category_gate",
        "method": source["method"],
        "controller_sequence": controller_sequence,
        "input_sequence": input_sequence,
        "actor_pointer_sequence": [
            row["binding"]["current_unit_pointer"] for row in ordered_states
        ],
        "actor_action_flags_sequence": [
            row["binding"]["current_unit"]["action_flags"] for row in ordered_states
        ],
        "transitions": transitions,
        "visible_rejection": final_visual,
        "defense_list_is_browsable_but_confirmation_revalidates_category": separated,
        "offensive_action_rejected_without_domain_mutation": rejected,
        "conclusion": (
            "Choosing yes at defense preparation opens state 0x9200 while preserving "
            "the actor and domain state. The sampled learned-action list visibly includes "
            "the offensive Fire Style action; confirming it produces category feedback "
            "and remains in 0x9200 with no unit-pool or battle-control mutation."
        ),
        "boundary": (
            "This sample proves one offensive-action rejection in defense preparation. "
            "It does not yet prove successful defense preparation storage, consumption, "
            "cost timing, damage modification, evasion, counterattack, or inventory rules."
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
        default=Path("notes/battle-defense-preparation-observations-20260723.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-defense-preparation-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_defense_preparation_manifest(
        args.root, args.rom, args.states, args.observations
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
