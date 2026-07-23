#!/usr/bin/env python3
"""Bind status 0x13 to Eight Gates action eligibility and presentation."""

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

from tools.thumb_branch import decode_thumb_bl


ROM_BASE = 0x08000000
LIST_BUILDER = 0x0806FDA4
LIST_BUILDER_END = 0x08070416
LIST_BUILDER_SHA256 = (
    "a67eb2e0664ded2394c00ee095d4ff9f4c40f7fbf4ed973e99399d044f187d66"
)
ACTION_JUMP_TABLE = 0x0806FF30
ACTION_JUMP_TABLE_END = 0x0806FFE8
ACTION_JUMP_TABLE_SHA256 = (
    "70e8f03efa99fa88b91aa2bbb6963555c617688855d6414d597aa1cf10e7db1d"
)
STAGE_POLICY_START = 0x08070074
STAGE_POLICY_END = 0x080701B8
STAGE_POLICY_SHA256 = (
    "c78a4082c963318ea96607e00da67d7f4ea1f5558d36543d484eecebe95c7579"
)
DEFENSE_MENU = 0x08070DF8
DEFENSE_MENU_END = 0x080712C8
DEFENSE_MENU_SHA256 = (
    "7de6d44156cbdd6281e5d095987db22744df34a157c604fd9181c4f5fce97051"
)
DEFENSE_PRESENTATION_START = 0x08071114
DEFENSE_PRESENTATION_END = 0x08071156
DEFENSE_PRESENTATION_SHA256 = (
    "ec8735717b4dc689005c555578a9ad36d867ca18e6f04a4fe2d14f4913839305"
)
STATUS_LOOKUP = 0x0806C160
STATUS_UPSERT = 0x0806C204
STATUS_UPSERT_END = 0x0806C308
STATUS_UPSERT_SHA256 = (
    "fddf887db4c97e2d001e952eee0da2758b09cb2826073d6d8084e5910b33d82a"
)
NUMERIC_WRITER = 0x08066A48
EVENT_BUILDER = 0x080754A8
EVENT_BUILDER_END = 0x08075816
EVENT_BUILDER_SHA256 = (
    "bd90433b9b831de35d1bc4a62652c02b4a7bebe0c6b530577137c96580faedde"
)
RESOLVER_QUEUE = 0x08076CE0
RESOLVER_QUEUE_END = 0x08077760
RESOLVER_QUEUE_SHA256 = (
    "f5675aded5a37132820b79ff5cddd7fcc9a83290ae56098604fe41d49eb3b579"
)
ACTIVE_ACTION_TEMPLATE_TABLE = 0x08545458
ACTIVE_ACTION_TEMPLATE_SIZE = 16

ACTION_BRANCHES = {
    43: 0x08070074,
    44: 0x08070092,
    45: 0x080700C0,
    46: 0x080700F6,
    47: 0x0807012C,
    48: 0x08070162,
    49: 0x08070190,
}

ACTION_POLICIES = {
    43: {
        "allowed_when": "status_absent",
        "disabled_reason_codes": {"present": 9},
    },
    44: {
        "allowed_when": "status_present_and_parameter_eq_1",
        "disabled_reason_codes": {"missing_or_lower": 10, "higher": 11},
    },
    45: {
        "allowed_when": "status_present_and_parameter_eq_2",
        "disabled_reason_codes": {"missing_or_lower": 12, "higher": 13},
    },
    46: {
        "allowed_when": "status_present_and_parameter_eq_3",
        "disabled_reason_codes": {"missing_or_lower": 14, "higher": 15},
    },
    47: {
        "allowed_when": "status_present_and_parameter_eq_4",
        "disabled_reason_codes": {"missing_or_lower": 16, "higher": 17},
    },
    48: {
        "allowed_when": "status_present_and_parameter_le_2",
        "disabled_reason_codes": {"missing": 18, "above_2": 19},
    },
    49: {
        "allowed_when": "status_present_and_parameter_gt_2",
        "disabled_reason_codes": {"missing_or_at_most_2": 20},
    },
}


def _offset(address: int) -> int:
    return address - ROM_BASE


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _offset(address))[0]


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _expect_sha256(
    rom: bytes, start: int, end: int, expected: str, label: str
) -> None:
    actual = hashlib.sha256(rom[_offset(start) : _offset(end)]).hexdigest()
    _expect(actual, expected, f"{label} SHA-256")


def _expect_bl(rom: bytes, callsite: int, target: int, label: str) -> None:
    actual = decode_thumb_bl(
        callsite,
        _u16(rom, callsite),
        _u16(rom, callsite + 2),
    )
    _expect(actual, target, label)


def _load_checked_action_names(path: Path | str) -> dict[int, str]:
    source = json.loads(Path(path).read_text(encoding="utf-8"))
    _expect(source.get("schema_version"), 1, "action identity schema")
    _expect(
        source.get("identity"),
        "checked_active_action_display_identities",
        "action identity source",
    )
    names = {
        int(row["action_id"]): row["display_name"] for row in source["entries"]
    }
    expected = {
        43: "第一　开门　开",
        44: "第二　休门　开",
        45: "第三　生门　开",
        46: "第四　伤门　开",
        47: "第五　杜门　开",
        48: "表莲华",
        49: "里莲华",
    }
    _expect(
        {action_id: names.get(action_id) for action_id in expected},
        expected,
        "Eight Gates action names",
    )
    return names


def build_status_stage_policy_manifest(
    rom_path: Path | str,
    action_identities_path: Path | str,
) -> dict[str, Any]:
    rom = Path(rom_path).read_bytes()
    names = _load_checked_action_names(action_identities_path)

    _expect_sha256(
        rom,
        LIST_BUILDER,
        LIST_BUILDER_END,
        LIST_BUILDER_SHA256,
        "action list builder",
    )
    _expect_sha256(
        rom,
        ACTION_JUMP_TABLE,
        ACTION_JUMP_TABLE_END,
        ACTION_JUMP_TABLE_SHA256,
        "action jump table",
    )
    _expect_sha256(
        rom,
        STAGE_POLICY_START,
        STAGE_POLICY_END,
        STAGE_POLICY_SHA256,
        "status 0x13 stage policy",
    )
    _expect_sha256(
        rom,
        DEFENSE_MENU,
        DEFENSE_MENU_END,
        DEFENSE_MENU_SHA256,
        "defense menu",
    )
    _expect_sha256(
        rom,
        DEFENSE_PRESENTATION_START,
        DEFENSE_PRESENTATION_END,
        DEFENSE_PRESENTATION_SHA256,
        "status 0x13 defense presentation",
    )
    _expect_sha256(
        rom,
        STATUS_UPSERT,
        STATUS_UPSERT_END,
        STATUS_UPSERT_SHA256,
        "status upsert",
    )
    _expect_sha256(
        rom,
        EVENT_BUILDER,
        EVENT_BUILDER_END,
        EVENT_BUILDER_SHA256,
        "event builder",
    )
    _expect_sha256(
        rom,
        RESOLVER_QUEUE,
        RESOLVER_QUEUE_END,
        RESOLVER_QUEUE_SHA256,
        "resolver queue",
    )
    _expect_sha256(
        rom,
        0x08075602,
        0x0807560A,
        "8f9d4232ecc8f004473870f8db2a3cbeca477c48536301cf707ef8f35ae8db30",
        "template effect type to event",
    )
    _expect_sha256(
        rom,
        0x080757A0,
        0x080757D0,
        "610de18246442b0e22071d3c55a7c7a658f95bf53586c15a8b198a8852bf2258",
        "template potency and duration to event",
    )
    _expect_sha256(
        rom,
        0x08077532,
        0x0807758E,
        "3c9bd0c2aa5d6fa930ae5f3953db828fc688d7a63a3275d4cfdeff1465d4e2ed",
        "effect 0x13 status producer",
    )

    policies = []
    for action_id, branch in ACTION_BRANCHES.items():
        table_entry = ACTION_JUMP_TABLE + (action_id - 4) * 4
        _expect(_u32(rom, table_entry), branch, f"action {action_id} jump target")
        _expect_bl(rom, branch + 4, STATUS_LOOKUP, f"action {action_id} status lookup")
        policies.append(
            {
                "action_id": action_id,
                "display_name": names[action_id],
                "jump_table_entry": f"0x{table_entry:08X}",
                "policy_branch": f"0x{branch:08X}",
                "lookup_callsite": f"0x{branch + 4:08X}",
                **ACTION_POLICIES[action_id],
            }
        )

    _expect_bl(rom, 0x0807112A, STATUS_LOOKUP, "defense status 0x13 lookup")
    _expect_bl(rom, 0x08071152, NUMERIC_WRITER, "defense stage numeric writer")

    expected_templates = {
        43: "020513000101640000000a0000000000",
        44: "02051300020164000000140000000000",
        45: "020513000301640000001e0000000000",
        46: "02051300040164000000280000000000",
        47: "02051300050164000000320000000000",
    }
    stage_producers = []
    for action_id, expected_hex in expected_templates.items():
        address = ACTIVE_ACTION_TEMPLATE_TABLE + action_id * ACTIVE_ACTION_TEMPLATE_SIZE
        raw = rom[_offset(address) : _offset(address) + ACTIVE_ACTION_TEMPLATE_SIZE]
        _expect(raw.hex(), expected_hex, f"action {action_id} numeric template")
        stage_producers.append(
            {
                "action_id": action_id,
                "display_name": names[action_id],
                "template_address": f"0x{address:08X}",
                "template_raw_hex": raw.hex(),
                "effect_type_low_6": raw[2] & 0x3F,
                "stage_value": raw[4],
                "duration_turns": raw[9],
                "raw_resource_cost_value": raw[10],
            }
        )
    _expect(
        _u32(rom, 0x08076F8C),
        0x08077532,
        "effect type 0x13 resolver dispatch",
    )
    _expect_bl(rom, 0x0807758A, STATUS_UPSERT, "stage status upsert")

    return {
        "schema_version": 1,
        "identity": "battle_status_0x13_stage_policy",
        "list_builder": f"0x{LIST_BUILDER:08X}",
        "list_builder_end": f"0x{LIST_BUILDER_END:08X}",
        "list_builder_sha256": LIST_BUILDER_SHA256,
        "action_jump_table": f"0x{ACTION_JUMP_TABLE:08X}",
        "action_jump_table_sha256": ACTION_JUMP_TABLE_SHA256,
        "status_code": "0x13",
        "domain_identity": "eight_gates_stage",
        "record_parameter_offset": 6,
        "eligibility_parameter_width": "u16",
        "action_identity_source": "sequel/content/battle-config/action-identities.json",
        "action_policies": policies,
        "disabled_reason_code_semantics": "stable_but_visible_messages_unresolved",
        "defense_menu": f"0x{DEFENSE_MENU:08X}",
        "defense_menu_sha256": DEFENSE_MENU_SHA256,
        "defense_effect_type_low_6": "0x14",
        "defense_lookup_callsite": "0x0807112A",
        "defense_numeric_writer_callsite": "0x08071152",
        "defense_presentation": (
            "render_status_parameter_as_effect_0x14_numeric_value"
        ),
        "stage_producers": stage_producers,
        "producer_event_builder": f"0x{EVENT_BUILDER:08X}",
        "producer_resolver_branch": "0x08077532",
        "producer_upsert_callsite": "0x0807758A",
        "producer_dataflow": (
            "template_byte_0x04_to_event_amount_to_status_record_u16_0x06"
        ),
        "stage_update_policy": (
            "ordinary_status_0x13_replaces_previous_stage_record"
        ),
        "implementation_requirement": (
            "one_typed_status_instance_drives_eligibility_hit_count_and_presentation"
        ),
        "visible_status_name": None,
        "conclusion": (
            "Status 0x13 is an ordered Eight Gates stage. Actions 43-47 produce "
            "replacement stages 1-5; the same record gates actions 43-49, supplies "
            "the effect 0x14 numeric presentation, and modifies queued hit count."
        ),
        "boundary": (
            "The producer templates, stage replacement dataflow, action IDs, checked "
            "display names, exact eligibility predicates, disabled reason codes, "
            "u16 stage read, defense numeric writer, and post-hit removal are closed. "
            "The visible status label and user-facing reason text remain unresolved."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--action-identities",
        type=Path,
        default=Path("sequel/content/battle-config/action-identities.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-status-stage-policy-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_status_stage_policy_manifest(args.rom, args.action_identities)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
