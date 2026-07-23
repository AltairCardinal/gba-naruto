#!/usr/bin/env python3
"""Bind battle action templates to cost, target, effect, and resolver semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from tools.thumb_branch import decode_thumb_bl


ROM_BASE = 0x08000000
ACTIVE_TABLE = 0x08545458
ACTIVE_COUNT = 87
TOOL_TABLE = 0x08545BE4
TOOL_COUNT = 94
ENTRY_SIZE = 16
DISPATCH_TABLE = 0x08076F44
DISPATCH_COUNT = 0x3F

EVIDENCE_RANGES = {
    "active_initializer": (
        0x0806D85C,
        0x0806D910,
        "dd78df15b6599a2bc73fd04e5b04f8a58cb8d761f7d7ae3a0460a5daae9daa7f",
    ),
    "tool_initializer": (
        0x0806D910,
        0x0806D95E,
        "032c35e2fa3295e906a741e1f58a5351417686fd17826d7849af7c1959138268",
    ),
    "target_policy": (
        0x0806A2F4,
        0x0806A4AC,
        "a30e7de2bdc628e4e631407a4b37d51a77c1aaa7132bf788bb1a56668375f9d4",
    ),
    "event_builder": (
        0x080754A8,
        0x08075816,
        "bd90433b9b831de35d1bc4a62652c02b4a7bebe0c6b530577137c96580faedde",
    ),
    "resource_eligibility": (
        0x080837E2,
        0x0808386E,
        "9a3bbc0a0525827c23c51ba5a3f98b5f4b4905aa2979927213f170d08b921beb",
    ),
    "resolver_dispatch": (
        0x08076F24,
        0x08077040,
        "e45b03dec38fddb123ab43af2b47a08e7d67e49435cabe64f59dc28d453fbbd4",
    ),
}

COST_KINDS = {
    0: "none",
    1: "current_chakra",
    2: "current_hp",
    3: "no_scalar_resource_special",
    5: "battle_local_ninja_tool_slot",
}

TARGET_POLICIES = {
    0: "self_or_implicit_actor",
    1: "friendly_unit_policy_1",
    2: "opponent_unit",
    3: "occupied_unit",
    4: "empty_tile",
    5: "friendly_unit_policy_5",
}

RUNTIME_LAYOUT = {
    "+0": "cost_kind",
    "+1": "display_animation_family",
    "+2_low_6": "effect_code",
    "+2_high_2": "effect_flags",
    "+3_low_3": "target_policy",
    "+3_high_5": "target_flags",
    "+4": "potency",
    "+5": "base_hit_count",
    "+6": "success_rate_percent",
    "+7": "distance_and_line_flags",
    "+8": "area_range_and_shape_flags",
    "+9": "duration_turns",
    "+A..+B": "scalar_resource_cost_u16",
}


def _offset(address: int) -> int:
    return address - ROM_BASE


def _slice(rom: bytes, start: int, end: int) -> bytes:
    if not ROM_BASE <= start <= end <= ROM_BASE + len(rom):
        raise ValueError("action-template evidence range is outside the mapped ROM")
    return rom[_offset(start) : _offset(end)]


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _offset(address))[0]


def _hex(address: int) -> str:
    return f"0x{address:08X}"


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _expect_bl(rom: bytes, callsite: int, target: int) -> None:
    actual = decode_thumb_bl(callsite, _u16(rom, callsite), _u16(rom, callsite + 2))
    _expect(actual, target, f"BL at {_hex(callsite)}")


def _load_bank(root: Path, relative: str, rom: bytes, table: int, count: int) -> tuple[dict[str, Any], list[bytes]]:
    path = root / relative
    bank = json.loads(path.read_text(encoding="utf-8"))
    _expect(bank["entry_count"], count, f"{relative} entry count")
    _expect(len(bank["entries"]), count, f"{relative} entries")
    rows = []
    for index, entry in enumerate(bank["entries"]):
        raw = bytes.fromhex(entry["raw_hex"])
        _expect(len(raw), ENTRY_SIZE, f"{relative} row {index} size")
        start = _offset(table) + index * ENTRY_SIZE
        _expect(raw, rom[start : start + ENTRY_SIZE], f"{relative} row {index} ROM bytes")
        rows.append(raw)
    return bank, rows


def _decode_runtime_template(
    identity: str,
    index: int,
    raw: bytes,
    handlers: dict[int, int],
    *,
    is_empty: bool | None = None,
) -> dict[str, Any]:
    effect_code = raw[2] & 0x3F
    target_policy = raw[3] & 0x07
    cost_kind = raw[0]
    if cost_kind not in COST_KINDS:
        raise ValueError(f"unknown cost kind {cost_kind} in {identity} {index}")
    if target_policy not in TARGET_POLICIES:
        raise ValueError(f"unknown target policy {target_policy} in {identity} {index}")
    is_empty = not any(raw) if is_empty is None else is_empty
    handler = handlers.get(effect_code)
    if not is_empty and handler is None:
        raise ValueError(f"nonempty {identity} {index} has no effect handler")
    scalar = int.from_bytes(raw[10:12], "little") if cost_kind in (1, 2) else None
    key = "action_id" if identity == "active_action" else "ninja_tool_id"
    return {
        key: index,
        "is_empty": is_empty,
        "raw_hex": raw.hex(),
        "cost": {"kind": cost_kind, "name": COST_KINDS[cost_kind], "scalar": scalar},
        "display_animation_family": raw[1],
        "effect": {
            "code": effect_code,
            "flags": raw[2] & 0xC0,
            "handler": _hex(handler) if handler is not None else None,
        },
        "target": {
            "policy": target_policy,
            "name": TARGET_POLICIES[target_policy],
            "flags": raw[3] & 0xF8,
        },
        "potency": raw[4],
        "base_hit_count": raw[5],
        "success_rate_percent": raw[6],
        "distance_and_line_flags": raw[7],
        "area_range_and_shape_flags": raw[8],
        "duration_turns": raw[9],
    }


def build_action_template_semantics_manifest(root: Path | str, rom_path: Path | str) -> dict[str, Any]:
    root = Path(root)
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()

    evidence = {}
    for name, (start, end, expected_sha) in EVIDENCE_RANGES.items():
        actual_sha = hashlib.sha256(_slice(rom, start, end)).hexdigest()
        _expect(actual_sha, expected_sha, f"{name} SHA-256")
        evidence[name] = {"start": _hex(start), "end": _hex(end), "sha256": actual_sha}

    _expect_bl(rom, 0x0807557E, 0x0806D85C)
    _expect_bl(rom, 0x080755A0, 0x0806D910)
    for address, halfword in {
        0x08075606: 0x8808,
        0x08075608: 0x81E8,
        0x0808383A: 0x2902,
        0x0808384C: 0x2901,
        0x08083860: 0x2903,
        0x08083868: 0x2905,
        0x08076F24: 0x89F1,
        0x08076F26: 0x203F,
    }.items():
        _expect(_u16(rom, address), halfword, f"instruction at {_hex(address)}")

    handlers = {code: _u32(rom, DISPATCH_TABLE + (code - 1) * 4) for code in range(1, DISPATCH_COUNT + 1)}
    for code, address in handlers.items():
        if not ROM_BASE <= address < ROM_BASE + len(rom):
            raise ValueError(f"effect {code:02X} handler points outside ROM")

    active_bank, active_rows = _load_bank(
        root, "sequel/content/battle-config/bank.json", rom, ACTIVE_TABLE, ACTIVE_COUNT
    )
    tool_bank, tool_source_rows = _load_bank(
        root, "sequel/content/skills/bank.json", rom, TOOL_TABLE, TOOL_COUNT
    )
    active_actions = [
        _decode_runtime_template("active_action", index, raw, handlers)
        for index, raw in enumerate(active_rows)
    ]
    ninja_tools = []
    for index, source in enumerate(tool_source_rows):
        runtime = bytes([5, source[0], *source[2:10], 0, 0, 0, 0, 0, 0])
        decoded = _decode_runtime_template(
            "ninja_tool", index, runtime, handlers, is_empty=not any(source)
        )
        decoded["source_raw_hex"] = source.hex()
        ninja_tools.append(decoded)

    return {
        "schema_version": 1,
        "identity": "battle_action_template_semantics",
        "rom": str(rom_path),
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "evidence": evidence,
        "content": {
            "active_actions": {
                "path": "sequel/content/battle-config/bank.json",
                "entry_count": active_bank["entry_count"],
                "table": _hex(ACTIVE_TABLE),
                "table_sha256": hashlib.sha256(b"".join(active_rows)).hexdigest(),
            },
            "ninja_tools": {
                "path": "sequel/content/skills/bank.json",
                "entry_count": tool_bank["entry_count"],
                "table": _hex(TOOL_TABLE),
                "table_sha256": hashlib.sha256(b"".join(tool_source_rows)).hexdigest(),
            },
        },
        "semantics": {
            "runtime_layout": RUNTIME_LAYOUT,
            "cost_kinds": {str(key): value for key, value in COST_KINDS.items()},
            "target_policies": {str(key): value for key, value in TARGET_POLICIES.items()},
            "effect_dispatch": {
                "selector": "runtime_u16_at_+2 & 0x003F",
                "table": _hex(DISPATCH_TABLE),
                "handlers": {f"{code:02X}": _hex(address) for code, address in handlers.items()},
            },
        },
        "active_actions": active_actions,
        "ninja_tools": ninja_tools,
        "implementation_contract": [
            "Model cost, display, effect, target, range, and upgrade as orthogonal action-definition policies.",
            "Build one runtime action descriptor for active actions and ninja tools before validation and resolution.",
            "Dispatch effect_code through a data-driven resolver registry; never branch on screenshots or display names.",
            "Validate target policy and resource cost before committing an action transaction.",
            "Keep unresolved target-policy variants and effect handlers numerically stable until stronger evidence names them.",
        ],
        "boundary": (
            "This binds the runtime template layout, five observed cost kinds, six target-policy codes, "
            "and all 63 resolver jump-table entries. Human-facing names for unresolved effect handlers, "
            "target variants 1/5, and packed range flag bits remain intentionally neutral."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-action-template-semantics-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_action_template_semantics_manifest(args.root, args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
