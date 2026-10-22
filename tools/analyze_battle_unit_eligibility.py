#!/usr/bin/env python3
"""Bind roster browsing and unit command eligibility to single-A ROM replays."""

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
ACTION_FLAGS_LOW_OFFSET = 0xC0
SELECTION_MARKER_OFFSET = 0xC1
AFFILIATION_OFFSET = 0xCC
ACTION_STATE_OFFSET = 0xCD
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


def _expect(actual: Any, expected: Any, label: str, case_id: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch for {case_id}: expected {expected!r}, got {actual!r}"
        )


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


def _selected_unit(state: Any) -> dict[str, int]:
    selected = []
    for slot in range(UNIT_SLOT_COUNT):
        address = UNIT_POOL_BASE + slot * UNIT_RECORD_SIZE
        record = state.read_memory(address, UNIT_RECORD_SIZE)
        if record[0] != 0 and record[SELECTION_MARKER_OFFSET] == 1:
            selected.append(
                {
                    "slot": slot,
                    "character_id": record[0],
                    "action_flags_low": record[ACTION_FLAGS_LOW_OFFSET],
                    "affiliation": record[AFFILIATION_OFFSET],
                    "action_state": record[ACTION_STATE_OFFSET],
                }
            )
    if len(selected) != 1:
        raise ValueError(f"expected exactly one selected live unit, got {selected}")
    return selected[0]


def analyze_eligibility_case(
    root: Path,
    rom_path: Path | str,
    states_path: Path | str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    case_id = observation["id"]
    before_path = _validate_hash(
        root, observation["before"], observation["before_sha256"], "checkpoint"
    )
    after_path = _validate_hash(
        root, observation["after"], observation["after_sha256"], "checkpoint"
    )
    audit_path = _validate_hash(
        root, observation["audit"], observation["audit_sha256"], "audit"
    )
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    _expect(audit["evidence_mode"], "single-input", "audit evidence mode", case_id)
    _expect(len(audit["inputs"]), 1, "audit input count", case_id)
    _expect(audit["inputs"][0]["key"], "A", "audit input key", case_id)
    _expect(
        audit["input_state_sha256"],
        observation["before_sha256"],
        "audit input checkpoint hash",
        case_id,
    )
    _expect(
        audit["output_state_sha256"],
        observation["after_sha256"],
        "audit output checkpoint hash",
        case_id,
    )

    before_binding = analyze_checkpoint(rom_path, states_path, before_path)
    after_binding = analyze_checkpoint(rom_path, states_path, after_path)
    _expect(
        before_binding["controller_state_hex"],
        observation["expected_before_state"],
        "before controller state",
        case_id,
    )
    _expect(
        after_binding["controller_state_hex"],
        observation["expected_after_state"],
        "after controller state",
        case_id,
    )
    _expect(
        before_binding["current_unit_pointer"],
        "0x00000000",
        "before current-unit pointer",
        case_id,
    )

    before = load_gba_state(before_path)
    after = load_gba_state(after_path)
    selected_before = _selected_unit(before)
    selected_after = _selected_unit(after)
    _expect(selected_after, selected_before, "selected unit after A", case_id)
    expected_fields = {
        "slot": "expected_selected_slot",
        "character_id": "expected_character_id",
        "action_flags_low": "expected_action_flags_low",
        "affiliation": "expected_affiliation",
        "action_state": "expected_action_state",
    }
    for key, expected_key in expected_fields.items():
        _expect(
            selected_before[key],
            observation[expected_key],
            f"selected-unit {key}",
            case_id,
        )

    unit_pool_before = before.read_memory(
        UNIT_POOL_BASE, UNIT_RECORD_SIZE * UNIT_SLOT_COUNT
    )
    unit_pool_after = after.read_memory(
        UNIT_POOL_BASE, UNIT_RECORD_SIZE * UNIT_SLOT_COUNT
    )
    control_before = before.read_memory(BATTLE_CONTROL_BASE, BATTLE_CONTROL_SIZE)
    control_after = after.read_memory(BATTLE_CONTROL_BASE, BATTLE_CONTROL_SIZE)
    menu_before = before.read_memory(ACTION_MENU_BASE, ACTION_MENU_SIZE)
    menu_after = after.read_memory(ACTION_MENU_BASE, ACTION_MENU_SIZE)
    unit_pool_diffs = _diff_region(unit_pool_before, unit_pool_after, UNIT_POOL_BASE)
    control_diffs = _diff_region(control_before, control_after, BATTLE_CONTROL_BASE)
    menu_diffs = _diff_region(menu_before, menu_after, ACTION_MENU_BASE)

    expected_pointer = _hex(
        UNIT_POOL_BASE + selected_before["slot"] * UNIT_RECORD_SIZE
    )
    accepted = (
        observation["kind"] == "accepted"
        and before_binding["controller_state_hex"] == "0x2000"
        and after_binding["controller_state_hex"] == "0x3000"
        and after_binding["current_unit_pointer"] == expected_pointer
        and not unit_pool_diffs
        and bool(control_diffs)
        and bool(menu_diffs)
    )
    rejected = (
        observation["kind"] == "rejected"
        and before_binding["controller_state_hex"] == "0x2000"
        and after_binding["controller_state_hex"] == "0x2000"
        and after_binding["current_unit_pointer"] == "0x00000000"
        and not unit_pool_diffs
        and not control_diffs
        and not menu_diffs
    )
    if observation["kind"] == "accepted" and not accepted:
        raise ValueError(f"eligible command acceptance not proven for {case_id}")
    if observation["kind"] == "rejected" and not rejected:
        raise ValueError(f"ineligible command rejection not proven for {case_id}")
    if observation["kind"] not in {"accepted", "rejected"}:
        raise ValueError(f"unsupported eligibility case kind: {observation['kind']}")

    return {
        "id": case_id,
        "kind": observation["kind"],
        "before": observation["before"],
        "before_sha256": observation["before_sha256"],
        "after": observation["after"],
        "after_sha256": observation["after_sha256"],
        "audit": observation["audit"],
        "audit_sha256": observation["audit_sha256"],
        "selected_unit": selected_before,
        "controller_transition": (
            f"{before_binding['controller_state_hex']} -> "
            f"{after_binding['controller_state_hex']}"
        ),
        "before_current_unit_pointer": before_binding["current_unit_pointer"],
        "after_current_unit_pointer": after_binding["current_unit_pointer"],
        "unit_pool_diffs": unit_pool_diffs,
        "battle_control_diffs": control_diffs,
        "action_menu_diffs": menu_diffs,
        "command_accepted": accepted,
        "command_rejected_without_domain_mutation": rejected,
    }


def build_unit_eligibility_manifest(
    root: Path | str,
    rom_path: Path | str,
    states_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported battle unit eligibility schema")
    cases = [
        analyze_eligibility_case(root, rom_path, states_path, observation)
        for observation in source["observations"]
    ]
    separated = (
        any(case["command_accepted"] for case in cases)
        and sum(
            bool(case["command_rejected_without_domain_mutation"])
            for case in cases
        )
        == 2
    )
    if not separated:
        raise ValueError("roster browsing and command eligibility are not separated")
    return {
        "schema_version": 1,
        "identity": "battle_unit_command_eligibility",
        "method": source["method"],
        "case_count": len(cases),
        "cases": cases,
        "roster_browsing_is_separate_from_command_eligibility": separated,
        "conclusion": (
            "Roster browsing can select an unspent player unit, an action-complete "
            "player unit, or an escort/objective unit. A confirms only the sampled "
            "unspent commandable unit into state 0x3000 and binds the current-unit "
            "pointer; the other two confirmations are domain no-ops in state 0x2000."
        ),
        "boundary": (
            "These samples prove action-complete and escort/objective rejection at "
            "confirmation. They do not yet prove every incapacitation, death, summon, "
            "affiliation, or scenario-specific eligibility rule."
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
        default=Path("notes/battle-unit-eligibility-observations-20260723.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-unit-eligibility-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_unit_eligibility_manifest(
        args.root, args.rom, args.states, args.observations
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
