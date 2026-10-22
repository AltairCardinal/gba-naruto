#!/usr/bin/env python3
"""Bind status 0x05 to the original battle identity-transformation lifecycle."""

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
ACTION_ID = 4
ACTION_NAME = "变化术"
STATUS_CODE = 0x05
ACTIVE_ACTION_TEMPLATE_TABLE = 0x08545458
ACTIVE_ACTION_TEMPLATE_SIZE = 16
EXPECTED_TEMPLATE_HEX = "01050503000164010103020006000100"

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
STATUS_UPSERT = 0x0806C204
STATUS_UPSERT_END = 0x0806C308
STATUS_UPSERT_SHA256 = (
    "fddf887db4c97e2d001e952eee0da2758b09cb2826073d6d8084e5910b33d82a"
)
STATUS_LOOKUP = 0x0806C160
STATUS_REMOVE = 0x0806C1A4
UNIT_REFRESH = 0x0806A780

IDENTITY_COPY_HELPER = 0x0806C0A8
IDENTITY_COPY_HELPER_END = 0x0806C0CE
IDENTITY_COPY_HELPER_SHA256 = (
    "96f888e4cd2dc5449957b1c59591827b627f7e694fc5f132d5276abeeec3e6c8"
)
RESTORE_HELPER = 0x0806C0D4
RESTORE_HELPER_END = 0x0806C120
RESTORE_HELPER_SHA256 = (
    "70b27fe1e746ab66b7e7c5d866995d97db33f5de8f470b6ae0000f16e3e8680f"
)
ELIGIBILITY_FUNCTION = 0x0806A2F4
ELIGIBILITY_FUNCTION_END = 0x0806A4AC
ELIGIBILITY_FUNCTION_SHA256 = (
    "a30e7de2bdc628e4e631407a4b37d51a77c1aaa7132bf788bb1a56668375f9d4"
)

APPLY_BRANCH = 0x0807711A
APPLY_BRANCH_END = 0x08077178
APPLY_BRANCH_SHA256 = (
    "2d0bbc66acfa78f536307e1b608f01aaeba4ee4ed1af78a568a9cde06357e209"
)
CLEANUP_BRANCH = 0x08077214
CLEANUP_BRANCH_END = 0x0807726E
CLEANUP_BRANCH_SHA256 = (
    "c845d27e360fbe3d91b1f415054d47d0bd9436484c6c054bf97c1fc9f293cd65"
)

STATUS_TICK = 0x0806C308
STATUS_TICK_END = 0x0806C364
STATUS_TICK_SHA256 = (
    "4c773416a020c8bad1c0104545c03af8fbdc6b6b9833d342e2c1e0c230c48f66"
)
REMOVED_EVENT_PROCESSOR = 0x0806C40C
REMOVED_EVENT_DISPATCH_END = 0x0806C478
REMOVED_EVENT_DISPATCH_SHA256 = (
    "42f0b3573527c990287feb37c579bb094d77acc7729e6870cf97701d7fa7dbc2"
)
REMOVED_STATUS_0X05_BRANCH = 0x0806C568
REMOVED_STATUS_0X05_BRANCH_END = 0x0806C5AA
REMOVED_STATUS_0X05_BRANCH_SHA256 = (
    "a967720b687dd502c3499f13bb9fada102775e7f73217732f2a9e082cf599f47"
)


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


def _load_action_name(path: Path | str) -> str:
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
    _expect(names.get(ACTION_ID), ACTION_NAME, "action 4 checked display name")
    return names[ACTION_ID]


def build_status_transformation_manifest(
    rom_path: Path | str,
    action_identities_path: Path | str,
) -> dict[str, Any]:
    rom = Path(rom_path).read_bytes()
    display_name = _load_action_name(action_identities_path)

    for start, end, expected, label in (
        (EVENT_BUILDER, EVENT_BUILDER_END, EVENT_BUILDER_SHA256, "event builder"),
        (RESOLVER_QUEUE, RESOLVER_QUEUE_END, RESOLVER_QUEUE_SHA256, "resolver queue"),
        (STATUS_UPSERT, STATUS_UPSERT_END, STATUS_UPSERT_SHA256, "status upsert"),
        (
            IDENTITY_COPY_HELPER,
            IDENTITY_COPY_HELPER_END,
            IDENTITY_COPY_HELPER_SHA256,
            "identity copy helper",
        ),
        (RESTORE_HELPER, RESTORE_HELPER_END, RESTORE_HELPER_SHA256, "restore helper"),
        (
            ELIGIBILITY_FUNCTION,
            ELIGIBILITY_FUNCTION_END,
            ELIGIBILITY_FUNCTION_SHA256,
            "action target eligibility",
        ),
        (APPLY_BRANCH, APPLY_BRANCH_END, APPLY_BRANCH_SHA256, "status 0x05 apply branch"),
        (
            CLEANUP_BRANCH,
            CLEANUP_BRANCH_END,
            CLEANUP_BRANCH_SHA256,
            "cleanup event 0x0B branch",
        ),
        (STATUS_TICK, STATUS_TICK_END, STATUS_TICK_SHA256, "status tick"),
        (
            REMOVED_EVENT_PROCESSOR,
            REMOVED_EVENT_DISPATCH_END,
            REMOVED_EVENT_DISPATCH_SHA256,
            "removed-status dispatcher",
        ),
        (
            REMOVED_STATUS_0X05_BRANCH,
            REMOVED_STATUS_0X05_BRANCH_END,
            REMOVED_STATUS_0X05_BRANCH_SHA256,
            "removed status 0x05 branch",
        ),
    ):
        _expect_sha256(rom, start, end, expected, label)

    template_address = (
        ACTIVE_ACTION_TEMPLATE_TABLE + ACTION_ID * ACTIVE_ACTION_TEMPLATE_SIZE
    )
    template = rom[
        _offset(template_address) : _offset(template_address)
        + ACTIVE_ACTION_TEMPLATE_SIZE
    ]
    _expect(template.hex(), EXPECTED_TEMPLATE_HEX, "action 4 numeric template")
    _expect(template[2] & 0x3F, STATUS_CODE, "action 4 effect type")

    # Resolver dispatch and the direct identity/status operations.
    _expect(_u32(rom, 0x08076F54), APPLY_BRANCH, "effect type 0x05 dispatch")
    _expect(_u32(rom, 0x08076F6C), CLEANUP_BRANCH, "effect type 0x0B dispatch")
    _expect_bl(rom, 0x08077138, IDENTITY_COPY_HELPER, "identity copy call")
    _expect_bl(rom, 0x08077166, STATUS_UPSERT, "transformation status upsert")
    _expect_bl(rom, 0x0806C0C6, UNIT_REFRESH, "identity copy refresh")
    _expect_bl(rom, 0x0806C118, UNIT_REFRESH, "identity restore refresh")
    _expect_bl(rom, 0x0806A41E, STATUS_LOOKUP, "eligibility status lookup")
    _expect_bl(rom, 0x0807723E, RESTORE_HELPER, "cleanup identity restore")
    _expect_bl(rom, 0x0807725A, STATUS_LOOKUP, "cleanup status lookup")
    _expect_bl(rom, 0x08077268, STATUS_REMOVE, "cleanup status removal")

    # Status expiry removes with mode 1, preserving the complete record in the
    # removed-event bank. The side-end state immediately dispatches that bank;
    # status code 0x05 reaches the same identity restoration helper.
    _expect(_u16(rom, 0x0806C346), 0x2201, "expiry removal mode")
    _expect_bl(rom, 0x0806C348, STATUS_REMOVE, "expiry status removal")
    _expect_bl(rom, 0x0807367C, STATUS_TICK, "side-end status tick")
    _expect_bl(
        rom,
        0x08073680,
        REMOVED_EVENT_PROCESSOR,
        "side-end removed-event processing",
    )
    _expect(
        _u32(rom, 0x0806C47C),
        REMOVED_STATUS_0X05_BRANCH,
        "removed status 0x05 dispatch",
    )
    _expect_bl(
        rom,
        0x0806C5A6,
        RESTORE_HELPER,
        "natural expiry identity restore",
    )

    duration_turns = template[9]
    return {
        "schema_version": 1,
        "identity": "battle_status_0x05_identity_transformation",
        "action_id": ACTION_ID,
        "display_name": display_name,
        "action_identity_source": (
            "sequel/content/battle-config/action-identities.json"
        ),
        "status_code": "0x05",
        "template_address": f"0x{template_address:08X}",
        "template_raw_hex": template.hex(),
        "template_effect_type_low_6": f"0x{template[2] & 0x3F:02X}",
        "template_duration_turns": duration_turns,
        "stored_duration_ticks": (duration_turns & 0x7F) * 2,
        "apply_resolver_branch": f"0x{APPLY_BRANCH:08X}",
        "identity_copy_helper": f"0x{IDENTITY_COPY_HELPER:08X}",
        "identity_copy_operation": (
            "source_character_id_equals_target_character_id"
        ),
        "copies_full_unit_record": False,
        "identity_copy_refresh_mode": 8,
        "linked_target_record_offset": 4,
        "linked_target_source": "queued_event_target_unit_slot",
        "restore_helper": f"0x{RESTORE_HELPER:08X}",
        "original_character_id_offset": 0xBC,
        "restore_special_identity_mapping": {"8": 0x39, "15": 0x3A},
        "restore_special_mapping_condition": "unit_offset_0xCA_is_nonzero",
        "restore_refresh_mode": 0,
        "cleanup_event_type_low_6": "0x0B",
        "cleanup_resolver_branch": f"0x{CLEANUP_BRANCH:08X}",
        "cleanup_restore_callsite": "0x0807723E",
        "cleanup_lookup_callsite": "0x0807725A",
        "cleanup_remove_callsite": "0x08077268",
        "cleanup_removal_mode": 1,
        "eligibility_lookup_callsite": "0x0806A41E",
        "eligibility_tile_category": "0x0200",
        "eligibility_status_missing_result": 0,
        "eligibility_requires_linked_opposite_affiliation": True,
        "eligibility_rejects_linked_unit_equal_actor": True,
        "eligibility_cleanup_event_type_low_6": "0x0B",
        "eligibility_cleanup_event_result": 0,
        "eligibility_allowed_path": "preserve_incoming_nonzero_result",
        "eligibility_semantics": (
            "linked_target_affiliation_and_cleanup_event_exception"
        ),
        "side_end_status_tick_callsite": "0x0807367C",
        "side_end_removed_event_callsite": "0x08073680",
        "removed_event_processor": f"0x{REMOVED_EVENT_PROCESSOR:08X}",
        "removed_status_0x05_dispatch": f"0x{REMOVED_STATUS_0X05_BRANCH:08X}",
        "natural_expiry_restore_callsite": "0x0806C5A6",
        "natural_expiry_restore_semantics": (
            "duration_zero_copies_record_then_status_0x05_removed_event_restores_identity"
        ),
        "implementation_requirement": (
            "identity_override_is_domain_state_not_a_sprite_swap"
        ),
        "conclusion": (
            "变化术 applies a timed identity override: the acting unit adopts only "
            "the target character identity, retains the linked target slot in status "
            "0x05, refreshes derived presentation in mode 8, and restores its original "
            "identity both on cleanup event 0x0B and on ordinary duration expiry."
        ),
        "boundary": (
            "Production, identity-copy scope, linked target storage, duration encoding, "
            "defeat cleanup, natural-expiry restoration, and original-identity mapping "
            "are closed. The status-specific target-eligibility branch is closed, while "
            "the generic caller-facing meaning of all return values and any visible "
            "status label remain unresolved."
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
        default=Path(
            "notes/battle-status-transformation-bindings-20260723.json"
        ),
    )
    args = parser.parse_args()
    result = build_status_transformation_manifest(args.rom, args.action_identities)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
