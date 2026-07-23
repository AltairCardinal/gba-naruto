#!/usr/bin/env python3
"""Bind the original battle AI target index, utility weights, and custom rules."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.thumb_branch import iter_thumb_direct_branches


ROM_BASE = 0x08000000
TARGET_INDEX = 0x0808400C
TARGET_INDEX_END = 0x08084266
TARGET_INDEX_SHA256 = "a88f30fb911dd6a20a1dc66bbe593912321f27dc2a45f1164d2b27398642a2fb"
SCORER = 0x08084274
SCORER_END = 0x08085154
SCORER_SHA256 = "c9da91cd096b36f325f3b975a416c83578048a1d588f89cafa1e1ec9dc075830"
CONFIG_TABLE = 0x0853F348
CONFIG_RECORD_SIZE = 0xA8
CONFIG_RECORD_COUNT = 8
CONFIG_TABLE_END = CONFIG_TABLE + CONFIG_RECORD_SIZE * CONFIG_RECORD_COUNT
CONFIG_TABLE_SHA256 = "6bcd51c9faede066805b9f0e427217925b14ad5b7d99e7b98876d17f23e87504"

TARGET_INDEX_CALLS = [
    (0x08084126, 0x0809C14C),
    (0x08084148, 0x0809C14C),
    (0x0808419E, 0x08083AF4),
    (0x080841CA, 0x0806FDA4),
    (0x080841D6, 0x08082280),
    (0x08084212, 0x0806D85C),
    (0x0808422C, 0x0806D910),
]

SCORER_CALLS = [
    (0x080842AC, 0x0809C110),
    (0x080842B6, 0x08085144),
    (0x08084332, 0x08075B58),
    (0x080843CC, 0x08085144),
    (0x08084410, 0x0809C14C),
    (0x08084440, 0x0809C14C),
    (0x0808454C, 0x08083AF4),
    (0x080845E2, 0x0809C14C),
    (0x08084608, 0x0809C14C),
    (0x08084656, 0x0809C14C),
    (0x0808466A, 0x0809C14C),
    (0x080847A6, 0x08083AF4),
    (0x080847B4, 0x08083AF4),
    (0x080848B2, 0x0809C14C),
    (0x08084958, 0x0806C160),
    (0x0808496A, 0x0806C160),
    (0x0808497C, 0x0806C160),
    (0x0808498C, 0x0806C160),
    (0x0808499C, 0x0806C160),
    (0x080849BE, 0x0806C160),
    (0x080849CE, 0x0806C160),
    (0x080849DE, 0x0806C160),
    (0x08084B6A, 0x0806C160),
    (0x08084B92, 0x0806C160),
    (0x08084BBA, 0x0806C160),
    (0x08084BE0, 0x0806C160),
    (0x08084C02, 0x0806C160),
    (0x08084D04, 0x0806C160),
    (0x08084D1E, 0x0806C160),
    (0x08084E2A, 0x08083AF4),
    (0x08084E38, 0x08083AF4),
    (0x08084E56, 0x0809C14C),
    (0x08084E7C, 0x0809C14C),
    (0x08084EE8, 0x08083AF4),
    (0x08084EF6, 0x08083AF4),
    (0x08084F14, 0x0809C14C),
    (0x0808512C, 0x0809C110),
    (0x08085136, 0x0809C14C),
]


def _offset(address: int) -> int:
    return address - ROM_BASE


def _slice(rom: bytes, start: int, end: int) -> bytes:
    if not ROM_BASE <= start <= end <= ROM_BASE + len(rom):
        raise ValueError("AI evidence range is outside the mapped ROM")
    return rom[_offset(start) : _offset(end)]


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _offset(address))[0]


def _i32(blob: bytes, offset: int) -> int:
    return struct.unpack_from("<i", blob, offset)[0]


def _hex(address: int) -> str:
    return f"0x{address:08X}"


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _calls(rom: bytes, start: int, end: int) -> list[tuple[int, int]]:
    return [
        (branch.address, branch.target)
        for branch in iter_thumb_direct_branches(
            rom, rom_base=ROM_BASE, start=start, end=end
        )
        if branch.mnemonic == "bl"
    ]


def _custom_rules(config_blob: bytes) -> list[dict[str, int]]:
    rules = []
    for config_id in range(CONFIG_RECORD_COUNT):
        record = config_blob[
            config_id * CONFIG_RECORD_SIZE : (config_id + 1) * CONFIG_RECORD_SIZE
        ]
        for slot in range(4):
            offset = 0x88 + slot * 8
            kind = record[offset]
            if kind:
                rules.append(
                    {
                        "config_id": config_id,
                        "slot": slot,
                        "kind": kind,
                        "parameter": record[offset + 1],
                        "weight": _i32(record, offset + 4),
                    }
                )
    return rules


def build_ai_utility_policy_manifest(rom_path: Path | str) -> dict[str, Any]:
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()
    target_index_blob = _slice(rom, TARGET_INDEX, TARGET_INDEX_END)
    scorer_blob = _slice(rom, SCORER, SCORER_END)
    config_blob = _slice(rom, CONFIG_TABLE, CONFIG_TABLE_END)
    _expect(
        hashlib.sha256(target_index_blob).hexdigest(),
        TARGET_INDEX_SHA256,
        "AI target-index SHA-256",
    )
    _expect(
        hashlib.sha256(scorer_blob).hexdigest(),
        SCORER_SHA256,
        "AI scorer SHA-256",
    )
    _expect(
        hashlib.sha256(config_blob).hexdigest(),
        CONFIG_TABLE_SHA256,
        "AI configuration table SHA-256",
    )
    _expect(_calls(rom, TARGET_INDEX, TARGET_INDEX_END), TARGET_INDEX_CALLS, "target-index calls")
    _expect(_calls(rom, SCORER, SCORER_END), SCORER_CALLS, "scorer calls")

    # The target builder stores one unit slot per selector in separate banks.
    _expect(_u32(rom, 0x080840B0), 0x020240C0, "unit pool literal")
    _expect(_u32(rom, 0x080840B4), 0x0202D228, "battle globals literal")
    _expect(_u32(rom, 0x080840C0), 0x00003C54, "same-side target bank offset")
    _expect(_u32(rom, 0x0808410C), 0x00003C5B, "opposite-side target bank offset")
    for address in (0x08084132, 0x08084158, 0x08084166, 0x08084174, 0x08084182, 0x08084190, 0x080841AC):
        _expect(_u16(rom, address) & 0xFF00, 0xD200, f"strict-minimum reject at {_hex(address)}")

    standard = config_blob[CONFIG_RECORD_SIZE : 2 * CONFIG_RECORD_SIZE]
    common_prefix = standard[:0x88]
    for config_id in range(2, CONFIG_RECORD_COUNT):
        record = config_blob[
            config_id * CONFIG_RECORD_SIZE : (config_id + 1) * CONFIG_RECORD_SIZE
        ]
        _expect(record[:0x88], common_prefix, f"config {config_id} common weights")
    _expect(config_blob[:CONFIG_RECORD_SIZE], bytes(CONFIG_RECORD_SIZE), "config 0 zero policy")

    selectors = [
        {
            "index": 0,
            "metric": "floor(current_hp * 1000 / max_hp)",
            "comparison": "strictly_lower",
        },
        {"index": 1, "metric": "max_hp", "comparison": "strictly_lower"},
        {"index": 2, "metric": "attack", "comparison": "strictly_lower"},
        {"index": 3, "metric": "defense", "comparison": "strictly_lower"},
        {"index": 4, "metric": "agility", "comparison": "strictly_lower"},
        {"index": 5, "metric": "movement", "comparison": "strictly_lower"},
        {
            "index": 6,
            "metric": "map_distance(actor, candidate)",
            "comparison": "strictly_lower",
        },
    ]
    custom_rules = _custom_rules(config_blob)
    _expect(
        custom_rules,
        [
            {"config_id": 2, "slot": 0, "kind": 1, "parameter": 0, "weight": 10000},
            {"config_id": 3, "slot": 0, "kind": 2, "parameter": 0x1F, "weight": 10000},
            {"config_id": 3, "slot": 1, "kind": 3, "parameter": 0x4A, "weight": 10000},
            {"config_id": 3, "slot": 2, "kind": 3, "parameter": 0x4B, "weight": 10000},
            {"config_id": 4, "slot": 0, "kind": 2, "parameter": 0x1E, "weight": 10000},
            {"config_id": 5, "slot": 0, "kind": 5, "parameter": 0, "weight": 10000},
            {"config_id": 6, "slot": 0, "kind": 5, "parameter": 0, "weight": 10000},
            {"config_id": 7, "slot": 0, "kind": 4, "parameter": 0, "weight": 10000},
        ],
        "active custom AI rules",
    )

    hostile_weights = [_i32(standard, offset) for offset in range(0x2C, 0x48, 4)]
    friendly_weights = [_i32(standard, offset) for offset in range(0x48, 0x64, 4)]
    return {
        "schema_version": 1,
        "identity": "battle_ai_target_and_utility_policy",
        "rom": str(rom_path),
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "target_index": {
            "function": _hex(TARGET_INDEX),
            "end": _hex(TARGET_INDEX_END),
            "sha256": TARGET_INDEX_SHA256,
            "unit_pool": "0x020240C0",
            "unit_record_size": "0x01D4",
            "scan_order": "unit_slots_1_through_12",
            "partition": "unit[0xCC]_equal_to_actor[0xCC]",
            "selectors": selectors,
            "tie_break": "first_scanned_unit",
            "banks": {
                "same_affiliation": "0x02030E7C",
                "opposite_affiliation": "0x02030E83",
            },
            "forced_opponent_override": (
                "When battle role byte[unit_slot] is 2 and the role byte indexed by "
                "unit[0xCA] is 0, that unit fills all seven opposite-affiliation slots."
            ),
            "distance_helper": "0x08083AF4",
            "action_range_summary": {
                "available_action_builder": "0x0806FDA4",
                "runtime_template_builders": ["0x0806D85C", "0x0806D910"],
                "operation": "retain maximum low_5 action-range value",
                "destination": "0x02030E8A",
            },
        },
        "scorer": {
            "function": _hex(SCORER),
            "end": _hex(SCORER_END),
            "sha256": SCORER_SHA256,
            "candidate_source": "simulated battle state and queued effect events",
            "damage_utility": {
                "event_low_6": ["0x01", "0x14", "0x15"],
                "per_event_amount": "signed_u16(event+0x18) * event[0x12]",
                "aggregation": "sum_by_target_then_select_largest_total",
                "damage_fraction": "min(total_damage, target_current_hp) / target_current_hp",
                "success_component": "max(event[0x10]) / 100",
                "coverage_component": "distinct_targets / active_opposite_affiliation_units",
                "range_component": "max_map_distance / actor_max_action_range",
            },
            "hostile_target_matching": (
                "For each of the seven opposite-affiliation selector slots, add its "
                "weight when the simulated event target matches; one unit may match "
                "and accumulate several selector weights."
            ),
            "friendly_target_matching": (
                "The same seven selectors are recomputed for same-affiliation units "
                "and use an independent weight vector for supportive events."
            ),
            "status_filters": "bound separately by battle_ai_status_aware_event_score_policy",
            "component_combiner": "integer_mean",
            "final_random_term": "(rng_value * 10) >> 15",
            "random_only_override": (
                "If actor action-state bits (unit[0xC0] & 0x0E) equal 2, return a "
                "0..99 RNG-derived score without evaluating normal utility."
            ),
        },
        "configuration": {
            "table": _hex(CONFIG_TABLE),
            "end": _hex(CONFIG_TABLE_END),
            "sha256": CONFIG_TABLE_SHA256,
            "record_count": CONFIG_RECORD_COUNT,
            "record_size": CONFIG_RECORD_SIZE,
            "unit_config_field": "unit[0xCD]",
            "standard_policy": {
                "config_id": 1,
                "base_weights": [_i32(standard, 0x00), _i32(standard, 0x0C)],
                "actor_hp_gain_weight": _i32(standard, 0x04),
                "actor_hp_survival_weight": _i32(standard, 0x10),
                "actor_chakra_gain_weight": _i32(standard, 0x08),
                "actor_chakra_retention_weight": _i32(standard, 0x14),
                "hostile_target_selector_weights": hostile_weights,
                "friendly_target_selector_weights": friendly_weights,
                "damage_weight": _i32(standard, 0x64),
                "success_rate_weight": _i32(standard, 0x68),
                "target_coverage_weight": _i32(standard, 0x6C),
                "range_usage_weight": _i32(standard, 0x70),
            },
            "custom_rule_layout": {
                "slot_count": 4,
                "first_offset": "0x88",
                "stride": 8,
                "kind_offset": 0,
                "parameter_offset": 1,
                "weight_offset": 4,
            },
            "active_custom_rules": custom_rules,
            "custom_rule_semantics": [
                {
                    "kind": 1,
                    "operation": (
                        "score average movement-normalized progress toward active "
                        "opponents and add the rule weight on a tile whose flag bit 0 is clear"
                    ),
                },
                {
                    "kind": 2,
                    "operation": (
                        "score movement-normalized progress toward parameter character_id "
                        "and add the rule weight when a damage-family event targets it"
                    ),
                },
                {
                    "kind": 3,
                    "operation": "add the rule weight when a queued event action_id equals parameter",
                },
                {
                    "kind": 4,
                    "operation": (
                        "add the rule weight when the actor occupies tile class 6 and "
                        "the tile-side bit matches the active battle-side selector"
                    ),
                },
                {
                    "kind": 5,
                    "operation": (
                        "when unit[0xCA] is 0, add the rule weight for an eligible "
                        "queued event in low-6 family 0x02, 0x07, or 0x17"
                    ),
                },
            ],
        },
        "implementation_contract": [
            "Build separate same- and opposite-affiliation target indexes before scoring.",
            "Preserve seven selector matches independently; do not collapse them to nearest or lowest HP.",
            "Score a simulated action result and queued events without mutating the committed battle state.",
            "Aggregate multi-hit damage per target before applying damage, hit-rate, coverage, and range utility.",
            "Represent scenario priorities as typed weighted rule records, not scripted turn numbers or screenshots.",
            "Keep deterministic unit-slot tie order and add RNG only at the proven final scoring boundary.",
        ],
        "conclusion": (
            "The original AI is a data-driven utility planner. It indexes seven target "
            "properties separately for allies and opponents, scores simulated effect "
            "events with independent weight vectors, and composes up to four typed "
            "scenario rules from each unit-selected configuration."
        ),
        "boundary": (
            "This closes the target selector order, standard weights, damage utility "
            "shape, active custom rule records, deterministic target ties, and final "
            "random term. Visible names for the five rule kinds and the complete path "
            "algorithm inside 0x08083AF4 remain intentionally neutral."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-ai-utility-policy-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_ai_utility_policy_manifest(args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
