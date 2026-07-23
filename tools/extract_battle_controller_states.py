#!/usr/bin/env python3
"""Extract the ROM-proven battle-controller state inventory.

This deliberately separates control-flow identity from semantic interpretation.
Every entry address is tied to the checked dispatcher bytes; states whose purpose
has not yet been closed remain explicitly unresolved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
CONTROLLER_ENTRY = 0x080732B4
CONTROLLER_END = 0x08075082
DISPATCH_START = 0x080733A0
DISPATCH_END = 0x080735C6

EXPECTED_CONTROLLER_SHA256 = (
    "30c8e021502cca16fc3f569bbb21dd04f78d20bcbb8e6196550164a0d56429ff"
)
EXPECTED_DISPATCH_SHA256 = (
    "e6af2faa36e8ba6d650b84ad7ad8d3b0581e02c43e11383c9065020064e6e6f0"
)


# State values and branch destinations are decoded from 0x080733A0..0x080735C6.
# Semantic labels are intentionally conservative and must cite a separate static
# or runtime boundary before they are upgraded from unresolved.
STATE_ENTRIES: tuple[tuple[int, int], ...] = (
    (0x0000, 0x080735CA),
    (0x0010, 0x08073638),
    (0x1000, 0x0807364A),
    (0x1020, 0x080739D0),
    (0x1100, 0x0807367C),
    (0x1200, 0x080736B0),
    (0x1220, 0x080736F8),
    (0x1300, 0x080738C0),
    (0x2000, 0x08073940),
    (0x3000, 0x08073A04),
    (0x3100, 0x08073B84),
    (0x3110, 0x08073BA8),
    (0x3200, 0x08073E14),
    (0x3210, 0x08073EB0),
    (0x3300, 0x08074074),
    (0x3310, 0x080740D4),
    (0x4000, 0x0807410C),
    (0x4100, 0x08074190),
    (0x5000, 0x08074200),
    (0x6000, 0x080742A4),
    (0x7000, 0x080742E4),
    (0x8000, 0x080743D4),
    (0x9000, 0x08074550),
    (0x9100, 0x080747E0),
    (0x9200, 0x08074834),
    (0xA000, 0x0807484E),
    (0xB000, 0x08074870),
    (0xC000, 0x080748AC),
    (0xD000, 0x08074918),
    (0xE000, 0x08074988),
    (0xE010, 0x080749CC),
    (0xF000, 0x08074A98),
    (0xF100, 0x08074C2E),
    (0xF200, 0x08074C7C),
    (0xF300, 0x08074E48),
    (0xF400, 0x08074EE6),
)


SEMANTICS: dict[int, tuple[str, str, list[str]]] = {
    0x0000: (
        "battlefield_entry_sequence",
        "static_plus_checkpoint_runtime",
        [
            "scenario-41 controller-entry task resumes directly at 0x08073616",
            "the hash-bound checkpoint visibly shows the live battlefield actor entry",
        ],
    ),
    0x1020: (
        "current_unit_activation",
        "partial_static",
        ["0x080739D0 dereferences selected slot and initializes the current unit UI"],
    ),
    0x1300: (
        "side_scheduler",
        "static_plus_runtime",
        [
            "0x080738C0 scans unit slots 1..12 by affiliation/status",
            "scenario-41 player and enemy phase checkpoints cross this boundary",
        ],
    ),
    0x2000: (
        "player_unit_selection",
        "static_plus_runtime",
        [
            "0x08073940 opens selector input and validates the selected unit",
            "scenario-41 player-control evidence reaches selectable Naruto",
        ],
    ),
    0x1220: (
        "round_transition_script",
        "static_plus_checkpoint_runtime",
        [
            "scenario-41 round tutorial checkpoint has a validated 0x08073780 controller frame",
            "the visible checkpoint is a round-boundary tutorial dialogue, not a unit command",
        ],
    ),
    0x3000: (
        "unit_action_menu",
        "static_plus_checkpoint_runtime",
        [
            "0x08073A04 dispatches on current-unit +0xC0 action-category bits",
            "scenario-41 initial action menu and end-action confirmation bind to 0x08073A4A/0x08073A82",
        ],
    ),
    0x3110: (
        "player_move_selection",
        "static_plus_checkpoint_runtime",
        [
            "scenario-41 selectable movement grid binds through 0x08073C88 -> 0x0806F718",
            "the checkpoint exposes cursor movement and reachable tiles on the live battlefield",
        ],
    ),
    0x3210: (
        "chakra_exchange_result",
        "checkpoint_runtime_transaction",
        [
            "battle-15 single-input checkpoint crosses 0x3000 -> 0x3210",
            "the acting unit changes from 134 HP / 4 chakra to 119 HP / 5 chakra while ninja-tool inventory remains unchanged",
        ],
    ),
    0x3310: (
        "rest_confirmation",
        "checkpoint_runtime_transaction",
        [
            "battle-13 checkpoint binds the rest confirmation immediately before commit",
            "confirming crosses 0x3310 -> 0x1220, heals the acting unit from 24 to 41 HP, preserves chakra, and completes its action",
        ],
    ),
    0x4000: (
        "post_move_action_menu",
        "static_plus_checkpoint_runtime",
        [
            "scenario-41 action menu after movement binds through 0x08074132 -> 0x08067158",
            "its visible command set is reduced relative to the initial 0x3000 menu",
        ],
    ),
    0x4100: (
        "technique_targeting",
        "static_plus_checkpoint_runtime",
        [
            "scenario-41 target selection and attack confirmation both bind through 0x08074192 -> 0x08070DF8",
            "the two visible subphases share this top-level state and remain nested-controller behavior",
        ],
    ),
    0x5000: (
        "side_completion_scan",
        "partial_static",
        ["0x08074200 scans all active unit records and updates per-side state"],
    ),
    0x6000: (
        "player_action_confirmation",
        "static_control_flow",
        [
            "0x0807419E confirmation success in state 0x4100 assigns state 0x6000",
            "0x080742A4 conditionally runs the player confirmation UI and converges on state 0x8000",
        ],
    ),
    0x7000: (
        "enemy_action_preparation",
        "static_plus_checkpoint_runtime",
        [
            "0x080738CA sends non-player side directly to state 0x7000",
            "0x080742E4 scans affiliation-1 units, calls 0x080851F8, copies the action context, and assigns state 0x8000",
            "scenario-45 and scenario-50 checkpoints bind side 1 planning to 0x7000 and the selected enemy to shared 0x8000 resolution",
        ],
    ),
    0x8000: (
        "action_resolution_and_outcome",
        "static_plus_checkpoint_runtime",
        [
            "combat dialogue binds through 0x0807443C -> 0x080722A8",
            "combat result popup and victory presentation bind through 0x0807444E -> 0x0807305C",
            "multiple visible result subphases share this state and must not be collapsed into one screenshot",
        ],
    ),
    0x9000: (
        "facing_selection",
        "static_plus_checkpoint_runtime",
        [
            "scenario-41 facing checkpoint resumes directly at 0x080745A4",
            "0x080745A4 onward consumes directional input and updates the current unit facing field",
        ],
    ),
    0x9100: (
        "defense_preparation",
        "static_plus_checkpoint_runtime",
        [
            "scenario-41 defense confirmation binds through 0x080747F4 -> 0x08067158",
            "the visible prompt selects a defensive response after facing",
        ],
    ),
    0x9200: (
        "technique_menu",
        "static_plus_checkpoint_runtime",
        [
            "scenario-41 technique detail/menu binds through 0x08074836 -> 0x08070DF8",
            "the visible panel exposes technique stats before target selection",
        ],
    ),
    0xD000: (
        "secondary_action_completion",
        "static_plus_runtime",
        [
            "0x08074918 calls the checked 0x080722A8 MOVEDONE queue",
            "scenario-41 turn-1 evidence records a fresh secondary MOVEDONE hit",
        ],
    ),
    0xE010: (
        "victory_exit_check",
        "partial_static",
        ["0x080749CC calls 0x0807305C before scanning active unit records"],
    ),
    0xF000: (
        "result_state_router",
        "partial_static",
        ["0x08074A98 routes result substate 0..3 to 0xF100..0xF400"],
    ),
    0xF100: (
        "result_page_setup",
        "partial_static",
        ["0x08074C2E initializes result UI state"],
    ),
    0xF200: (
        "result_unit_enumeration",
        "partial_static",
        ["0x08074C7C enumerates active slots before result presentation"],
    ),
    0xF300: (
        "result_transition",
        "partial_static",
        ["0x08074E48 performs the bounded result-to-postbattle transition"],
    ),
    0xF400: (
        "postbattle",
        "static_plus_runtime",
        [
            "0x08074EE6 enters the official postbattle/save wrapper",
            "scenario-41 completion evidence reaches stable postbattle naturally",
        ],
    ),
}


def _slice(rom: bytes, start: int, end: int) -> bytes:
    lo = start - ROM_BASE
    hi = end - ROM_BASE
    if lo < 0 or hi > len(rom) or lo >= hi:
        raise ValueError(f"ROM range outside image: 0x{start:08X}..0x{end:08X}")
    return rom[lo:hi]


def extract_controller_states(rom: bytes) -> dict[str, Any]:
    controller = _slice(rom, CONTROLLER_ENTRY, CONTROLLER_END)
    dispatcher = _slice(rom, DISPATCH_START, DISPATCH_END)
    controller_sha = hashlib.sha256(controller).hexdigest()
    dispatcher_sha = hashlib.sha256(dispatcher).hexdigest()
    if dispatcher_sha != EXPECTED_DISPATCH_SHA256:
        raise ValueError("battle-controller dispatcher signature does not match proven ROM")
    if controller_sha != EXPECTED_CONTROLLER_SHA256:
        raise ValueError("battle-controller body signature does not match proven ROM")

    states: list[dict[str, Any]] = []
    for state, entry in sorted(STATE_ENTRIES):
        semantic = SEMANTICS.get(state)
        if semantic is None:
            name = f"unresolved_state_{state:04x}"
            status = "unresolved"
            evidence = ["dispatcher state and entry address only; behavior not yet named"]
        else:
            name, status, evidence = semantic
        entry_bytes = _slice(rom, entry, min(entry + 16, CONTROLLER_END))
        states.append(
            {
                "state": state,
                "state_hex": f"0x{state:04X}",
                "entry": f"0x{entry:08X}",
                "entry_prefix_hex": entry_bytes.hex(),
                "semantic": name,
                "semantic_status": status,
                "evidence": evidence,
            }
        )

    return {
        "schema_version": 1,
        "identity": "battle_controller_dispatch_inventory",
        "controller_entry": f"0x{CONTROLLER_ENTRY:08X}",
        "controller_end": f"0x{CONTROLLER_END:08X}",
        "controller_sha256": controller_sha,
        "dispatcher_range": f"0x{DISPATCH_START:08X}..0x{DISPATCH_END:08X}",
        "dispatcher_sha256": dispatcher_sha,
        "dispatch_state_count": len(states),
        "states": states,
        "runtime_fields": [
            {
                "address": "0x0202680E",
                "semantic": "current side/affiliation selector",
                "status": "partial_static",
            },
            {
                "address": "0x02026810",
                "semantic": "current unit object pointer",
                "status": "partial_static_plus_runtime",
            },
            {
                "address": "0x02026A41",
                "semantic": "selected unit slot",
                "status": "partial_static_plus_runtime",
            },
            {
                "address": "0x020240C0",
                "semantic": "battle unit pool base; slots 1..12 use stride 0x1D4",
                "status": "static_plus_runtime",
            },
            {
                "address": "unit+0xC0",
                "semantic": "battle flags/action category bits",
                "status": "partial_static",
            },
            {
                "address": "unit+0xCC",
                "semantic": "affiliation",
                "status": "static_plus_runtime",
            },
            {
                "address": "unit+0xCD",
                "semantic": "per-unit action state",
                "status": "partial_static_plus_runtime",
            },
            {
                "address": "0x0200A880",
                "semantic": "action-tail/menu substate block",
                "status": "partial_static_plus_runtime",
            },
        ],
        "caveat": (
            "The 36-state inventory is structurally closed for this ROM. Only states "
            "with cited semantic evidence are named; unresolved states must not be "
            "collapsed into guessed Butano phases."
        ),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = extract_controller_states(args.rom.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)


if __name__ == "__main__":
    main()
