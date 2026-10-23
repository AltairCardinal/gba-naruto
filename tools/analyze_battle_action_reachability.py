#!/usr/bin/env python3
"""Classify every active-action identity by its natural production source."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


INPUTS = {
    # 2026-10-22: the banks below gained a ``_provenance`` block
    # (tools/butano/annotate_content_bank_provenance.py), so their bytes
    # changed on purpose.  The pins still guard against *silent* drift.
    "unit_bank": (
        "sequel/content/units/bank.json",
        "f54678398bad6141588f0fb2846d582b1ecdaa29c67637b18698869ca6466853",
    ),
    "formation_bank": (
        "sequel/content/positions/bank.json",
        "d3ff476cc0db595597a9fdd98272d41a5644546ae14c4474685a47aab2df6a3c",
    ),
    "action_bank": (
        "sequel/content/battle-config/bank.json",
        "2126d90a0da8b3c15b827eea06cbe0c6f6edac05359dfd24dc784939f40157db",
    ),
    # The action-identities pin was already stale in the committed tree
    # (the file moved in the 2026-10-21 merge without a pin update).
    "action_identities": (
        "sequel/content/battle-config/action-identities.json",
        "9f1585798fb7bd81e4d72d83a7dd596007b395065f4e14fd6271479942dce3cc",
    ),
    "combination_bindings": (
        "notes/battle-action-combination-bindings-20260725.json",
        "797346f0b06a214d039099f42acb2e507b033082bb9f9e70b57ad471f638c3ce",
    ),
    "progression_bindings": (
        "notes/battle-action-progression-20260726.json",
        "214b9d45f31e0be7f27494e458d05991a7371bea647db71b18103ebd03126a28",
    ),
    "resource_command_bindings": (
        "notes/battle-resource-command-rule-bindings-20260724.json",
        "ea4deacb98f3a8e1b39719b35dc7046542045d1d71d4ae36b7c0bd59077db063",
    ),
}

ORIGINAL_ROM = (
    "rom/base.gba",
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
)

SCENARIO_UNLOCK_ROM_RANGES = {
    "function": (
        0x0899EC,
        0x089AE0,
        "30463276e94bac6f9727ed8975be22ccf0d140a03909c15b3c0cfbf60dda0cc1",
    ),
    "special_case": (
        0x089A1A,
        0x089A4A,
        "fc1be93699732ac44bbb2503a0aff271d25ab24e7f567d029eece500698d8f83",
    ),
    "caller_window": (
        0x089B70,
        0x089B86,
        "31c4b54165a9a0f2dd4ccf9468b49035ab2c8aada673fdae6df6831429341368",
    ),
}

SCENARIO_PRIMARY_ACTION_UNLOCKS = {
    19: {
        "battle_id": 31,
        "variant": 0,
        "character_id": 2,
        "action_id": 19,
        "state_after_unlock": 0,
        "requires_training": True,
    },
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_inputs(
    root: Path,
    input_overrides: dict[str, Path] | None,
) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    overrides = input_overrides or {}
    payloads: dict[str, Any] = {}
    evidence: dict[str, dict[str, str]] = {}
    for name, (relative_path, expected_sha256) in INPUTS.items():
        path = overrides.get(name, root / relative_path)
        payload = path.read_bytes()
        actual_sha256 = _sha256(payload)
        if actual_sha256 != expected_sha256:
            label = name.replace("_", " ")
            raise ValueError(
                f"{label} SHA-256 mismatch: expected "
                f"{expected_sha256}, got {actual_sha256}"
            )
        payloads[name] = json.loads(payload.decode("utf-8"))
        evidence[name] = {
            "path": str(path),
            "sha256": actual_sha256,
        }
    return payloads, evidence


def _load_scenario_unlock_evidence(
    root: Path,
    input_overrides: dict[str, Path] | None,
) -> tuple[dict[str, str], dict[str, str]]:
    overrides = input_overrides or {}
    relative_path, expected_sha256 = ORIGINAL_ROM
    path = overrides.get("original_rom", root / relative_path)
    rom = path.read_bytes()
    actual_sha256 = _sha256(rom)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            "original ROM SHA-256 mismatch: expected "
            f"{expected_sha256}, got {actual_sha256}"
        )
    for label, (start, end, expected_range_sha256) in (
        SCENARIO_UNLOCK_ROM_RANGES.items()
    ):
        actual_range_sha256 = _sha256(rom[start:end])
        if actual_range_sha256 != expected_range_sha256:
            raise ValueError(
                f"scenario unlock {label} SHA-256 mismatch: "
                f"expected {expected_range_sha256}, got "
                f"{actual_range_sha256}"
            )
    action_definition_table = int.from_bytes(
        rom[0x089AD8:0x089ADC], "little"
    )
    chapter_state_address = int.from_bytes(
        rom[0x089ADC:0x089AE0], "little"
    )
    if action_definition_table != 0x0854241C:
        raise ValueError("scenario unlock action table literal mismatch")
    if chapter_state_address != 0x020311D4:
        raise ValueError("scenario unlock chapter state literal mismatch")
    return (
        {
            "function_range": "0x080899EC..0x08089AE0",
            "special_case_range": "0x08089A1A..0x08089A4A",
            "caller": "0x08089B7E",
            "chapter_state_address": "0x020311D4",
            "action_definition_table": "0x0854241C",
        },
        {
            "path": str(path),
            "sha256": actual_sha256,
            "function_sha256": SCENARIO_UNLOCK_ROM_RANGES[
                "function"
            ][2],
            "special_case_sha256": SCENARIO_UNLOCK_ROM_RANGES[
                "special_case"
            ][2],
            "caller_window_sha256": SCENARIO_UNLOCK_ROM_RANGES[
                "caller_window"
            ][2],
        },
    )


def _catalog_accepted(state: int) -> bool:
    return 1 <= state <= 254


def _base_occurrences(
    unit_entries: list[dict[str, Any]],
    action_id: int,
) -> list[dict[str, int]]:
    result = []
    for unit in unit_entries:
        for slot in unit["primary_slots"]:
            if slot["id"] == action_id:
                result.append(
                    {
                        "character_id": unit["character_id"],
                        "slot": slot["slot"],
                        "state": slot["initial_state"],
                        "unlock_level": slot["unlock_level"],
                    }
                )
    return result


def _formation_occurrences(
    formation_entries: list[dict[str, Any]],
    action_id: int,
) -> list[dict[str, Any]]:
    result = []
    for record in formation_entries:
        if not record["active"]:
            continue
        for slot_index, slot in enumerate(
            record["primary_action_slots"]
        ):
            if slot["action"] == action_id:
                result.append(
                    {
                        "record_id": record["id"],
                        "selector": record["selector"],
                        "slot": slot_index,
                        "state": slot["state"],
                    }
                )
    return result


def _classification(
    action_id: int,
    effect_code: int,
    routes: list[str],
) -> str:
    if action_id == 0:
        return "sentinel"
    if "combination_result" in routes:
        return "combination_result"
    if "base_catalog" in routes:
        return "base_catalog"
    if "formation_catalog" in routes:
        return "formation_catalog"
    if "base_training" in routes:
        return "base_training"
    if "base_level_unlock_then_training" in routes:
        return "base_level_unlock_then_training"
    if any(
        route.startswith("scenario_")
        and route.endswith("_unlock_then_training")
        for route in routes
    ):
        return "scenario_unlock_then_training"
    if "base_external_unlock_required" in routes:
        return "base_external_unlock_required"
    if action_id == 20:
        return "separate_resource_command_identity"
    if effect_code == 0:
        return "unreferenced_zero_template"
    return "unclassified"


def build_battle_action_reachability_manifest(
    root: Path | str,
    *,
    input_overrides: dict[str, Path] | None = None,
) -> dict[str, Any]:
    root = Path(root)
    inputs, evidence = _load_inputs(root, input_overrides)
    scenario_unlock_evidence, original_rom_evidence = (
        _load_scenario_unlock_evidence(root, input_overrides)
    )
    evidence["original_rom"] = original_rom_evidence
    unit_entries = inputs["unit_bank"]["entries"]
    formation_entries = inputs["formation_bank"]["entries"]
    action_entries = inputs["action_bank"]["entries"]
    identity_entries = inputs["action_identities"]["entries"]
    combination_bindings = inputs["combination_bindings"]
    progression_bindings = inputs["progression_bindings"]
    resource_command_bindings = inputs["resource_command_bindings"]

    if len(unit_entries) != 63:
        raise ValueError("unit bank must contain 63 templates")
    if len(formation_entries) != 1728:
        raise ValueError(
            "formation bank must contain 1728 records"
        )
    if len(action_entries) != 87:
        raise ValueError("action bank must contain 87 definitions")
    if [entry["action_id"] for entry in identity_entries] != list(
        range(87)
    ):
        raise ValueError(
            "action identities must cover IDs 0 through 86"
        )
    if progression_bindings["state_model"] != {
        "learned_maximum": 3,
        "learned_minimum": 1,
        "locked": 255,
        "unlocked_unlearned": 0,
    }:
        raise ValueError("progression state model mismatch")
    if (
        resource_command_bindings["identity"]
        != "battle_resource_command_rules"
    ):
        raise ValueError("resource command binding identity mismatch")

    combination_ids = sorted(
        {
            recipe["result_action_id"]
            for recipe in combination_bindings["recipes"]
        }
    )
    if combination_ids != [10, 11, 13, 17, 18]:
        raise ValueError("combination result identities mismatch")

    actions = []
    for action_id, action in enumerate(action_entries):
        if action_id == 0:
            base_records = []
            formation_records = []
        else:
            base_records = _base_occurrences(
                unit_entries, action_id
            )
            formation_records = _formation_occurrences(
                formation_entries, action_id
            )
        base_catalog = [
            record
            for record in base_records
            if _catalog_accepted(record["state"])
        ]
        base_training = [
            record
            for record in base_records
            if record["state"] == 0
        ]
        base_level_unlock = [
            record
            for record in base_records
            if record["state"] == 255
            and record["unlock_level"] > 0
        ]
        base_external_unlock = [
            record
            for record in base_records
            if record["state"] == 255
            and record["unlock_level"] == 0
        ]
        scenario_unlock = SCENARIO_PRIMARY_ACTION_UNLOCKS.get(
            action_id
        )
        if scenario_unlock is not None:
            expected_occurrence = {
                "character_id": scenario_unlock["character_id"],
                "slot": 10,
                "state": 255,
                "unlock_level": 0,
            }
            if base_external_unlock != [expected_occurrence]:
                raise ValueError(
                    f"scenario unlock action {action_id} base "
                    "template mismatch"
                )
        formation_catalog = [
            record
            for record in formation_records
            if _catalog_accepted(record["state"])
        ]

        routes = []
        if base_catalog:
            routes.append("base_catalog")
        if base_training:
            routes.append("base_training")
        if base_level_unlock:
            routes.append(
                "base_level_unlock_then_training"
            )
        if scenario_unlock is not None:
            routes.append(
                "scenario_"
                f"{scenario_unlock['battle_id']}_variant_"
                f"{scenario_unlock['variant']}_unlock_then_training"
            )
        elif base_external_unlock:
            routes.append("base_external_unlock_required")
        if formation_catalog:
            routes.append("formation_catalog")
        if action_id in combination_ids:
            routes.append("combination_result")

        effect_code = action["effect_code"]
        classification = _classification(
            action_id, effect_code, routes
        )
        actions.append(
            {
                "action_id": action_id,
                "display_name": identity_entries[action_id][
                    "display_name"
                ],
                "identity_confidence": identity_entries[action_id][
                    "confidence"
                ],
                "effect_code": effect_code,
                "classification": classification,
                "natural_routes": routes,
                "base_template": {
                    "occurrences": base_records,
                    "catalog_accepted_count": len(base_catalog),
                    "unlocked_unlearned_count": len(
                        base_training
                    ),
                    "level_locked_count": len(
                        base_level_unlock
                    ),
                    "external_unlock_required_count": len(
                        base_external_unlock
                    ),
                },
                "formation": {
                    "occurrences": formation_records,
                    "catalog_accepted_records": (
                        formation_catalog
                    ),
                },
                "scenario_unlock": scenario_unlock,
            }
        )

    unclassified = [
        row["action_id"]
        for row in actions
        if row["classification"] == "unclassified"
    ]
    classifications: dict[str, int] = {}
    for row in actions:
        key = row["classification"]
        classifications[key] = classifications.get(key, 0) + 1

    return {
        "schema_version": 1,
        "identity": "battle_action_reachability",
        "action_count": len(actions),
        "unit_template_count": len(unit_entries),
        "formation_record_count": len(formation_entries),
        "inputs": evidence,
        "catalog_state_contract": {
            "accepted": "1..254",
            "unlocked_unlearned": 0,
            "locked": 255,
        },
        "classification_counts": dict(
            sorted(classifications.items())
        ),
        "scenario_unlock_evidence": scenario_unlock_evidence,
        "actions": actions,
        "unclassified_action_ids": unclassified,
        "corrections": [
            {
                "action_id": 62,
                "correction": (
                    "Not resolver-only: two active battle-8 "
                    "formation records supply a catalog-accepted "
                    "level-3 action."
                ),
            },
            {
                "scope": "state_0",
                "correction": (
                    "State 0 means unlocked but unlearned; training "
                    "can raise it to catalog-accepted state 1."
                ),
            },
            {
                "action_id": 19,
                "correction": (
                    "Not an unresolved external unlock: the original "
                    "ROM synchronization function has an exact battle "
                    "31 variant 0 special case for Sasuke action 19. "
                    "It changes the slot to state 0, after which normal "
                    "training is still required."
                ),
            },
        ],
        "special_boundaries": {
            "action_20": (
                "The exact rendered identity is 结印, its action "
                "definition is all-zero, and no catalog-accepted "
                "primary slot references it. The separately proven "
                "resource command performs the hand-seal HP-for-"
                "chakra exchange; this correlation does not turn "
                "action definition 20 into a resolver action."
            ),
            "actions_39_40_52": (
                "These exact rendered identities have all-zero "
                "definitions and no base or formation primary-slot "
                "reference. No effect is invented for them."
            ),
        },
        "boundary": (
            "This manifest classifies data-source reachability, not "
            "presentation fidelity or per-action semantic compliance. "
            "A locked slot with unlock level zero is only promoted "
            "when a fail-closed original-ROM route proves its exact "
            "battle, variant, character, action, and unlocked state."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "notes/battle-action-reachability-20260726.json"
        ),
    )
    args = parser.parse_args()
    manifest = build_battle_action_reachability_manifest(
        args.root
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "action_count": manifest["action_count"],
                "unclassified_action_ids": manifest[
                    "unclassified_action_ids"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
