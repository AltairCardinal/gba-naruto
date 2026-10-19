#!/usr/bin/env python3
"""Bind character action slot states to unlock, training, catalog, and growth semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000

EVIDENCE_RANGES = {
    "template_initialization": (
        0x0806D4A0,
        0x0806D580,
        "094dc8b1249e73061d40dccc45e0183b818368cf707b604717e284f0732fa605",
    ),
    "battle_catalog_gate": (
        0x0806FDF2,
        0x0806FE3A,
        "3b72284a0f73ff76c8b6f7b590472cbb29c4580f0d353cf881b53973b24f815a",
    ),
    "level_unlock": (
        0x080899EC,
        0x08089AD0,
        "3c6b60470f9ed33e40f98cdbb434cfac380935ea10fbf2ec55ea797c122b7139",
    ),
    "training_allocation": (
        0x08093070,
        0x080931CE,
        "81a9e46969e5844a003af593ae885e28c518ce343e376525b3d3a267f42dc6c2",
    ),
    "action_growth": (
        0x0806D85C,
        0x0806D910,
        "dd78df15b6599a2bc73fd04e5b04f8a58cb8d761f7d7ae3a0460a5daae9daa7f",
    ),
}


def _slice(rom: bytes, start: int, end: int) -> bytes:
    begin = start - ROM_BASE
    finish = end - ROM_BASE
    if begin < 0 or finish > len(rom) or begin > finish:
        raise ValueError("action progression evidence range is outside ROM")
    return rom[begin:finish]


def _hex(address: int) -> str:
    return f"0x{address:08X}"


def _resolver_capable_actions_only_initially_zero(
    root: Path,
) -> list[int]:
    unit_bank = json.loads(
        (root / "sequel/content/units/bank.json").read_text(
            encoding="utf-8"
        )
    )
    action_bank = json.loads(
        (
            root
            / "sequel/content/battle-config/bank.json"
        ).read_text(encoding="utf-8")
    )
    states_by_action: dict[int, set[int]] = {}
    for unit in unit_bank["entries"]:
        for slot in unit["primary_slots"]:
            action_id = slot["id"]
            if action_id == 0:
                continue
            states_by_action.setdefault(action_id, set()).add(
                slot["initial_state"]
            )

    result = []
    for action_id, states in states_by_action.items():
        raw = bytes.fromhex(
            action_bank["entries"][action_id]["raw_hex"]
        )
        if states == {0} and (raw[2] & 0x3F) != 0:
            result.append(action_id)
    return sorted(result)


def build_battle_action_progression_manifest(
    root: Path | str, rom_path: Path | str
) -> dict[str, Any]:
    root = Path(root)
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()

    evidence = {}
    for name, (start, end, expected_sha) in EVIDENCE_RANGES.items():
        actual_sha = hashlib.sha256(
            _slice(rom, start, end)
        ).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(
                f"{name} SHA-256 mismatch: "
                f"expected {expected_sha}, got {actual_sha}"
            )
        evidence[name] = {
            "start": _hex(start),
            "end": _hex(end),
            "sha256": actual_sha,
        }

    return {
        "schema_version": 1,
        "identity": "battle_action_progression",
        "rom": str(rom_path),
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "evidence": evidence,
        "state_model": {
            "locked": 0xFF,
            "unlocked_unlearned": 0,
            "learned_minimum": 1,
            "learned_maximum": 3,
        },
        "transitions": {
            "template_initialization": (
                "Copy each four-byte slot; when state is 0xFF and "
                "unlock_level is nonzero and <= character level, "
                "materialize runtime state 0."
            ),
            "level_threshold": "0xFF -> 0",
            "spend_training_point": "0..2 -> 1..3",
            "training_point_write": (
                "0x08093160 decrements template +0xBA once; "
                "row type 4 increments template +0x51+slot*4, "
                "all other trainable rows increment "
                "template +0x15+slot*4."
            ),
        },
        "training_allocation": {
            "shared_training_point_field": (
                "character_template+0xBA"
            ),
            "row_type_field": "training_row+4",
            "secondary_row_type": 4,
            "primary_state_base": "character_template+0x15",
            "secondary_state_base": (
                "character_template+0x51"
            ),
            "slot_stride": 4,
            "primary_slot_count": 15,
            "secondary_slot_count": 24,
            "row_identity_field": "training_row+6",
            "row_slot_index_field": "training_row+7",
        },
        "battle_catalog": {
            "builder": "0x0806FDA4",
            "accepted_states": "1..254",
            "rejected_states": [0, 0xFF],
            "runtime_action_builder": "0x0806D85C",
        },
        "growth": {
            "formula": (
                "base_byte + per_level_growth * "
                "(action_level - 1), stored as u8"
            ),
            "target_types": {
                "1": "potency",
                "2": "base_hit_count",
                "3": "success_rate_percent",
                "4": "distance_and_line_flags",
                "5": "area_range_and_shape_flags",
                "6": "duration_turns",
                "7": "no_adjustment",
            },
        },
        "resolver_capable_actions_only_initially_zero": (
            _resolver_capable_actions_only_initially_zero(root)
        ),
        "external_corroboration": {
            "url": "https://www.doyo.cn/article/18782",
            "claim": (
                "Each character level grants one training point; "
                "one point raises one technique; most techniques "
                "have a maximum level of three."
            ),
            "evidence_scope": (
                "The ROM proves point decrement and slot-state "
                "increment. The public guide supplies the level-three "
                "cap and the player-facing training-point description."
            ),
        },
        "implementation_contract": [
            "Persist all 15 primary and 24 secondary slot states per character.",
            "Do not turn a level threshold directly into a battle-usable action.",
            "Only states 1..254 may enter the battle action catalog.",
            "Spend one training point to raise a trainable primary action by one level, capped at three.",
            "Spend one training point to raise a trainable secondary passive by one level, capped at three.",
            "Materialize action numeric growth from the persisted action level before browser validation and resolution.",
            "Scenario enemies without player progression use runtime states derived from their immutable character definition.",
        ],
        "boundary": (
            "This closes shared primary/secondary training allocation "
            "semantics in addition to primary-action catalog reachability "
            "and numeric growth. Individual passive consumer semantics "
            "remain separately evidence-gated."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--rom", type=Path, default=Path("rom/base.gba")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "notes/battle-action-progression-20260726.json"
        ),
    )
    args = parser.parse_args()
    manifest = build_battle_action_progression_manifest(
        args.root, args.rom
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "rom_sha256": manifest["rom_sha256"],
                "initial_zero_action_count": len(
                    manifest[
                        "resolver_capable_actions_only_initially_zero"
                    ]
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
