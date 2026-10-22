#!/usr/bin/env python3
"""Inventory formation-carried active actions that can reach battle-effect groups."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


FORMATION_TABLE = 0x5461C4
GROUP_COUNT = 48
GROUP_STRIDE = 0x1AAC
VARIANT_COUNT = 3
VARIANT_STRIDE = 0x08E4
RECORD_HEADER = 4
RECORD_COUNT = 12
RECORD_STRIDE = 0xB8
PRIMARY_ACTION_OFFSET = 0x10
PRIMARY_ACTION_SLOT_COUNT = 15
ACTION_SLOT_STRIDE = 4


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_offset(group_id: int, variant_id: int, record_id: int) -> int:
    return (
        FORMATION_TABLE
        + group_id * GROUP_STRIDE
        + variant_id * VARIANT_STRIDE
        + RECORD_HEADER
        + record_id * RECORD_STRIDE
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_battle_effect_formation_route_manifest(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    rom_path = root / "rom/base.gba"
    positions_path = root / "sequel/content/positions/bank.json"
    identities_path = root / "sequel/content/battle-config/action-identities.json"
    bindings_path = root / "artifacts/battle-effect-sequence-bindings-v1/manifest.json"

    rom = rom_path.read_bytes()
    positions = _load_json(positions_path)
    identities = _load_json(identities_path)
    bindings = _load_json(bindings_path)

    expected_count = GROUP_COUNT * VARIANT_COUNT * RECORD_COUNT
    if positions.get("entry_count") != expected_count or len(positions.get("entries", [])) != expected_count:
        raise ValueError("positions bank does not contain the complete formation matrix")
    if positions.get("entry_size") != RECORD_STRIDE:
        raise ValueError("positions record stride mismatch")

    bank_by_id = {entry["id"]: entry for entry in positions["entries"]}
    records: dict[str, dict[str, Any]] = {}
    bank_raw_mismatches: list[str] = []
    action_records: dict[int, list[str]] = defaultdict(list)
    action_occurrences: dict[int, int] = defaultdict(int)

    for group_id in range(GROUP_COUNT):
        for variant_id in range(VARIANT_COUNT):
            for record_id in range(RECORD_COUNT):
                record_key = f"g{group_id:02d}_v{variant_id}_r{record_id:02d}"
                offset = _record_offset(group_id, variant_id, record_id)
                raw = rom[offset : offset + RECORD_STRIDE]
                if len(raw) != RECORD_STRIDE:
                    raise ValueError(f"truncated formation record {record_key}")
                bank_entry = bank_by_id.get(record_key)
                if bank_entry is None or bank_entry.get("raw_hex") != raw.hex():
                    bank_raw_mismatches.append(record_key)

                slot_ids = [
                    raw[PRIMARY_ACTION_OFFSET + slot * ACTION_SLOT_STRIDE]
                    for slot in range(PRIMARY_ACTION_SLOT_COUNT)
                ]
                action_ids = [action_id for action_id in slot_ids if action_id != 0]
                records[record_key] = {
                    "group_id": group_id,
                    "variant_id": variant_id,
                    "record_id": record_id,
                    "rom_offset": f"0x{offset:06X}",
                    "selector": raw[0],
                    "active": any(raw),
                    "primary_action_slot_ids": slot_ids,
                    "primary_action_ids": action_ids,
                }
                for action_id in action_ids:
                    action_occurrences[action_id] += 1
                    if record_key not in action_records[action_id]:
                        action_records[action_id].append(record_key)

    identity_by_id = {entry["action_id"]: entry for entry in identities["entries"]}
    binding_by_id = {entry["action_id"]: entry for entry in bindings["active_action_bindings"]}
    sequence_by_id = {entry["sequence_id"]: entry for entry in bindings["sequences"]}

    actions: dict[str, dict[str, Any]] = {}
    group_actions: dict[int, set[int]] = defaultdict(set)
    for action_id in sorted(binding_by_id):
        binding = binding_by_id[action_id]
        sequence_id = binding["sequence_id"]
        sequence = sequence_by_id[sequence_id]
        resource_group_ids = sorted(set(sequence["nonzero_resource_group_ids"]))
        for resource_group_id in resource_group_ids:
            group_actions[resource_group_id].add(action_id)
        identity = identity_by_id.get(action_id, {})
        formation_records = action_records.get(action_id, [])
        actions[str(action_id)] = {
            "display_name": identity.get("display_name"),
            "display_name_confidence": identity.get("confidence"),
            "sequence_ids": [sequence_id],
            "resource_group_ids": resource_group_ids,
            "formation_occurrence_count": action_occurrences.get(action_id, 0),
            "formation_record_count": len(formation_records),
            "formation_records": formation_records,
        }

    groups: dict[str, dict[str, Any]] = {}
    for resource_group_id in range(1, 19):
        active_action_ids = sorted(group_actions.get(resource_group_id, set()))
        formation_action_ids = [
            action_id
            for action_id in active_action_ids
            if action_records.get(action_id)
        ]
        formation_records = sorted(
            {
                record_key
                for action_id in formation_action_ids
                for record_key in action_records[action_id]
            }
        )
        groups[str(resource_group_id)] = {
            "active_action_ids": active_action_ids,
            "formation_action_ids": formation_action_ids,
            "formation_record_count": len(formation_records),
            "formation_records": formation_records,
            "has_original_formation_action_route": bool(formation_records),
        }

    return {
        "schema_version": 1,
        "identity": "battle_effect_original_formation_action_routes",
        "inputs": {
            "rom": str(rom_path.relative_to(root)),
            "rom_sha256": _sha256(rom_path),
            "positions_bank": str(positions_path.relative_to(root)),
            "positions_bank_sha256": _sha256(positions_path),
            "action_identities": str(identities_path.relative_to(root)),
            "action_identities_sha256": _sha256(identities_path),
            "sequence_bindings": str(bindings_path.relative_to(root)),
            "sequence_bindings_sha256": _sha256(bindings_path),
        },
        "formation_matrix": {
            "table_offset": f"0x{FORMATION_TABLE:06X}",
            "group_count": GROUP_COUNT,
            "variant_count": VARIANT_COUNT,
            "records_per_variant": RECORD_COUNT,
            "record_count": expected_count,
            "record_stride": RECORD_STRIDE,
            "primary_action_offset": PRIMARY_ACTION_OFFSET,
            "primary_action_slots_per_record": PRIMARY_ACTION_SLOT_COUNT,
            "primary_action_slot_stride": ACTION_SLOT_STRIDE,
            "bank_raw_mismatches": bank_raw_mismatches,
        },
        "records": records,
        "actions": actions,
        "groups": groups,
        "scope": {
            "proves": (
                "Which active-action IDs stored in the original 48x3x12 formation matrix "
                "map through the accepted action-to-sequence catalog to effect groups."
            ),
            "does_not_prove": (
                "Story reachability, unlock/menu eligibility, AI selection, hardcoded effect "
                "producers, ninja-tool routes, or runtime execution of any listed action."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-effect-formation-routes-20260802.json"),
    )
    args = parser.parse_args()
    result = build_battle_effect_formation_route_manifest(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "record_count": result["formation_matrix"]["record_count"],
                "group_12": result["groups"]["12"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
