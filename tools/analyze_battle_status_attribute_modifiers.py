#!/usr/bin/env python3
"""Bind the original battle's status-driven attribute reducer and producers."""

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
ACTIVE_ACTION_TABLE = 0x08545458
NINJA_TOOL_TABLE = 0x08545BE4
TEMPLATE_SIZE = 16
ATTRIBUTE_REDUCER = 0x0806D1EC
ATTRIBUTE_REDUCER_END = 0x0806D43C
ATTRIBUTE_REDUCER_SHA256 = (
    "ee5c131932b822bff5d40bf1714241daf5f51e77f65d68f19232b5388ba8b9a6"
)
RECOMPUTE_ALL_UNITS = 0x0806D440
RECOMPUTE_ALL_UNITS_END = 0x0806D46A
RECOMPUTE_ALL_UNITS_SHA256 = (
    "017a388c4482b9a84aab63ccbc81b16f1a769722f4fe3349e0fc641353d4be68"
)
BASE_STAT_LOADER = 0x0806D964
STATUS_UPSERT = 0x0806C204
STATUS_TICK = 0x0806C308
REMOVED_EVENT_PROCESSOR = 0x0806C40C
INTEGER_DIVIDE = 0x0809C14C
GENERIC_STATUS_BRANCH = 0x08077564
COMPOUND_BRANCH = 0x08077590
COMPOUND_BRANCH_END = 0x0807764E
COMPOUND_BRANCH_SHA256 = (
    "ffb8bb9d69dbb3821d4ab3a7039da1e79d7c114a9963da7ae110c36b3c988b3c"
)

ACTIVE_EXPECTED = {
    14: ("0x1E", "01051e10190164000000020001000500"),
    25: ("0x1E", "01051e100f0164000000020001000500"),
    29: ("0x1E", "01051e10190164000000020001000500"),
    31: ("0x21", "020121020a015f0101030a0001000500"),
    37: ("0x12", "01051200140164000004030001000500"),
    38: ("0x12", "01051200140164000004030001000500"),
}

TOOL_EXPECTED = {
    55: ("0x1F", "05001f02190164020104280800000000"),
    56: ("0x1F", "05001f02320164020104370800000000"),
    57: ("0x1F", "05001f024b0164020104381100000000"),
    58: ("0x21", "05002102190164020104280900000000"),
    59: ("0x21", "050021023201640201043a0900000000"),
    60: ("0x21", "050021024b01640201043b1100000000"),
    61: ("0x23", "05002302190164020104280a00000000"),
    62: ("0x23", "050023023201640201043d0a00000000"),
    63: ("0x23", "050023024b01640201043e1100000000"),
    64: ("0x25", "05002502010164020104280b00000000"),
    65: ("0x25", "05002502020164020104400b00000000"),
    66: ("0x25", "05002502030164020104411100000000"),
    79: ("0x1E", "05001e010a0164020104490c00000000"),
    80: ("0x1E", "05001e011e01640201044f0c00000000"),
    81: ("0x1E", "05001e01320164020104501100000000"),
    82: ("0x20", "050020010a0164020104490300000000"),
    83: ("0x20", "050020011e0164020104520300000000"),
    84: ("0x20", "05002001320164020104531100000000"),
    85: ("0x22", "050022010a0164020104490d00000000"),
    86: ("0x22", "050022011e0164020104550d00000000"),
    87: ("0x22", "05002201320164020104561100000000"),
    88: ("0x24", "05002401010164020104490e00000000"),
    89: ("0x24", "05002401020164020104580e00000000"),
    90: ("0x24", "05002401030164020104591100000000"),
    91: ("0x26", "050026010a0164020104491000000000"),
    92: ("0x26", "050026011e01640201045b1000000000"),
    93: ("0x26", "050026013201640201045c1100000000"),
}

MODIFIER_POLICIES = {
    "0x12": {"attribute": "attack", "operation": "percent_increase", "cap": 99},
    "0x1B": {"attribute": "max_hp", "operation": "percent_increase", "cap": 999},
    "0x1E": {"attribute": "attack", "operation": "percent_increase", "cap": 99},
    "0x1F": {"attribute": "attack", "operation": "percent_decrease", "floor": 0},
    "0x20": {"attribute": "defense", "operation": "percent_increase", "cap": 99},
    "0x21": {"attribute": "defense", "operation": "percent_decrease", "floor": 0},
    "0x22": {"attribute": "agility", "operation": "percent_increase", "cap": 99},
    "0x23": {"attribute": "agility", "operation": "percent_decrease", "floor": 0},
    "0x24": {"attribute": "movement", "operation": "absolute_increase", "cap": 9},
    "0x25": {"attribute": "movement", "operation": "absolute_decrease", "floor": 0},
}

REDUCER_DISPATCH = {
    0x12: 0x0806D28C,
    0x1B: 0x0806D3E8,
    0x1E: 0x0806D28C,
    0x1F: 0x0806D34C,
    0x20: 0x0806D2C0,
    0x21: 0x0806D376,
    0x22: 0x0806D2F4,
    0x23: 0x0806D3A0,
    0x24: 0x0806D326,
    0x25: 0x0806D3CA,
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


def _load_action_names(path: Path | str) -> dict[int, str]:
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
        14: "写轮眼",
        25: "倍化术",
        29: "写轮眼",
        31: "千年杀",
        37: "白眼",
        38: "白眼",
    }
    _expect({key: names.get(key) for key in expected}, expected, "producer names")
    return names


def _template(rom: bytes, table: int, entry_id: int) -> bytes:
    address = table + entry_id * TEMPLATE_SIZE
    return rom[_offset(address) : _offset(address) + TEMPLATE_SIZE]


def _producer_row(
    raw: bytes,
    *,
    entry_id: int,
    table: int,
    identity_key: str,
    identity_value: int,
    display_name: str | None = None,
) -> dict[str, Any]:
    row = {
        identity_key: identity_value,
        "template_address": f"0x{table + entry_id * TEMPLATE_SIZE:08X}",
        "template_raw_hex": raw.hex(),
        "status_code": f"0x{raw[2] & 0x3F:02X}",
        "potency": raw[4],
        "duration_turns": raw[9],
        "stored_duration_ticks": (raw[9] & 0x7F) * 2,
    }
    if display_name is not None:
        row["display_name"] = display_name
    return row


def build_status_attribute_modifier_manifest(
    rom_path: Path | str,
    action_identities_path: Path | str,
) -> dict[str, Any]:
    rom = Path(rom_path).read_bytes()
    names = _load_action_names(action_identities_path)

    _expect_sha256(
        rom,
        ATTRIBUTE_REDUCER,
        ATTRIBUTE_REDUCER_END,
        ATTRIBUTE_REDUCER_SHA256,
        "attribute reducer",
    )
    _expect_sha256(
        rom,
        RECOMPUTE_ALL_UNITS,
        RECOMPUTE_ALL_UNITS_END,
        RECOMPUTE_ALL_UNITS_SHA256,
        "all-unit attribute recompute",
    )
    _expect_sha256(
        rom,
        COMPOUND_BRANCH,
        COMPOUND_BRANCH_END,
        COMPOUND_BRANCH_SHA256,
        "compound effect 0x26",
    )

    # The reducer temporarily restores unit+0xBC as the character identity,
    # loads base stats, restores the current identity, and then applies statuses.
    _expect(_u16(rom, 0x0806D202), 0x1C30, "unit pointer copy")
    _expect(_u16(rom, 0x0806D204), 0x30BC, "original character offset")
    _expect_bl(rom, 0x0806D20C, BASE_STAT_LOADER, "base stat reload")
    _expect(_u16(rom, 0x0806D210), 0x7034, "current identity restoration")
    _expect(_u16(rom, 0x0806D216), 0x4640, "status index zero")
    _expect(_u16(rom, 0x0806D422), 0x280F, "last status index")
    _expect(_u32(rom, 0x0806D43C), 999, "max HP cap")

    dispatch_table = 0x0806D23C
    for code, branch in REDUCER_DISPATCH.items():
        entry = dispatch_table + (code - 0x12) * 4
        _expect(_u32(rom, entry), branch, f"status 0x{code:02X} reducer dispatch")
    for callsite in (
        0x0806D298,
        0x0806D2CC,
        0x0806D300,
        0x0806D358,
        0x0806D382,
        0x0806D3AC,
        0x0806D3F4,
    ):
        _expect_bl(rom, callsite, INTEGER_DIVIDE, f"percent divide at 0x{callsite:08X}")

    # Effect types 0x12 and 0x1E..0x25 share the generic status upsert.
    dispatch_base = 0x08076F40
    for code in (0x12, *range(0x1E, 0x26)):
        _expect(
            _u32(rom, dispatch_base + code * 4),
            GENERIC_STATUS_BRANCH,
            f"effect 0x{code:02X} resolver dispatch",
        )
    _expect(
        _u32(rom, dispatch_base + 0x26 * 4),
        COMPOUND_BRANCH,
        "effect 0x26 resolver dispatch",
    )
    _expect_bl(rom, 0x0807758A, STATUS_UPSERT, "generic status upsert")
    for callsite in (0x080775B2, 0x080775C8, 0x080775DE, 0x080775F4):
        _expect_bl(rom, callsite, STATUS_UPSERT, f"compound upsert 0x{callsite:08X}")

    active_action_producers = []
    for action_id, (status_code, expected_hex) in ACTIVE_EXPECTED.items():
        raw = _template(rom, ACTIVE_ACTION_TABLE, action_id)
        _expect(raw.hex(), expected_hex, f"active action {action_id} template")
        _expect(f"0x{raw[2] & 0x3F:02X}", status_code, f"action {action_id} code")
        active_action_producers.append(
            _producer_row(
                raw,
                entry_id=action_id,
                table=ACTIVE_ACTION_TABLE,
                identity_key="action_id",
                identity_value=action_id,
                display_name=names[action_id],
            )
        )

    ninja_tool_producers = []
    for tool_id, (status_code, expected_hex) in TOOL_EXPECTED.items():
        raw = _template(rom, NINJA_TOOL_TABLE, tool_id)
        _expect(raw.hex(), expected_hex, f"ninja tool {tool_id} template")
        _expect(f"0x{raw[2] & 0x3F:02X}", status_code, f"tool {tool_id} code")
        ninja_tool_producers.append(
            _producer_row(
                raw,
                entry_id=tool_id,
                table=NINJA_TOOL_TABLE,
                identity_key="tool_id",
                identity_value=tool_id,
            )
        )

    # Side-end removes expired records, runs status-specific removed events,
    # then rebuilds every live unit's attributes before the side toggle.
    _expect_bl(rom, 0x0807367C, STATUS_TICK, "side-end status tick")
    _expect_bl(
        rom,
        0x08073680,
        REMOVED_EVENT_PROCESSOR,
        "side-end removed-event processing",
    )
    _expect_bl(rom, 0x08073684, RECOMPUTE_ALL_UNITS, "side-end stat recompute")

    return {
        "schema_version": 1,
        "identity": "battle_status_attribute_modifier_family",
        "attribute_reducer": f"0x{ATTRIBUTE_REDUCER:08X}",
        "attribute_reducer_sha256": ATTRIBUTE_REDUCER_SHA256,
        "recompute_all_units": f"0x{RECOMPUTE_ALL_UNITS:08X}",
        "active_status_slots": 16,
        "status_code_range": ["0x12", "0x25"],
        "status_record_offset": "unit+0xD4",
        "status_record_stride": 8,
        "status_potency_record_offset": 6,
        "status_potency_width": "u16",
        "unit_attribute_offsets": {
            "attack": 2,
            "defense": 3,
            "agility": 4,
            "movement": 5,
            "current_hp": 0x0C,
            "max_hp": 0x0E,
        },
        "recompute_base_identity": "unit_original_character_id_0xBC",
        "current_identity_restored_after_base_load": True,
        "recompute_scan_order": "active_status_slot_order_0_to_15",
        "percentage_base": "current_value_at_each_status_step",
        "post_pass_hp_rule": "clamp_current_hp_to_recomputed_max_hp",
        "modifier_policies": MODIFIER_POLICIES,
        "active_action_producers": active_action_producers,
        "ninja_tool_producers": ninja_tool_producers,
        "generic_resolver_branch": f"0x{GENERIC_STATUS_BRANCH:08X}",
        "compound_effect_type": "0x26",
        "compound_resolver_branch": f"0x{COMPOUND_BRANCH:08X}",
        "compound_status_codes": ["0x1E", "0x20", "0x22", "0x1B"],
        "compound_shared_fields": ["target", "potency", "duration", "source"],
        "compound_hp_apply_rule": (
            "increase_current_hp_by_positive_max_hp_delta_else_clamp_to_new_max"
        ),
        "side_end_tick_callsite": "0x0807367C",
        "side_end_removed_event_callsite": "0x08073680",
        "side_end_recompute_callsite": "0x08073684",
        "positive_duration_policy": "expire_then_recompute_without_modifier",
        "zero_duration_policy": "retained_by_generic_tick",
        "implementation_requirement": (
            "typed_ordered_attribute_modifiers_not_eager_permanent_stat_mutations"
        ),
        "conclusion": (
            "Statuses 0x12, 0x1B, and 0x1E through 0x25 form an ordered typed "
            "attribute-modifier family. Stats are rebuilt from the original character "
            "identity and active records, so expiry removes the modifier rather than "
            "trying to reverse an eager mutation. Effect 0x26 creates attack, defense, "
            "agility, and max-HP increase records as one compound application."
        ),
        "boundary": (
            "The reducer formulas, caps/floors, producer template IDs and parameters, "
            "compound effect, duration behavior, and side-end recompute order are "
            "closed. Ninja-tool visible names and generic status labels remain outside "
            "this operational contract."
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
            "notes/battle-status-attribute-modifier-bindings-20260723.json"
        ),
    )
    args = parser.parse_args()
    result = build_status_attribute_modifier_manifest(
        args.rom,
        args.action_identities,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
