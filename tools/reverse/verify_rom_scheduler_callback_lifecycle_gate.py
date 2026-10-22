#!/usr/bin/env python3
"""Fail-closed gate for the scheduler lifecycle behind the 0x59EAE0 candidate.

This verifier deliberately produces no coverage claim.  It independently
rebuilds the fixed direct registration and consumer denominators from the raw
ROM, closes the two literal-registered callbacks, and records the remaining
computed/indirect entry as a promotion blocker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.thumb_branch import (  # noqa: E402
    decode_thumb_bl,
    iter_thumb_direct_branches,
)


SCHEMA = "rom-scheduler-callback-lifecycle-gate-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

CANDIDATE_RANGE = (0x59EAE0, 0x59F560)
CANDIDATE_SHA256 = "05cefb7a73e68d196dd4349c3eb553703d497a438468b1e8e52069d86a7096b3"
SCENARIO_50_RANGE = (0x3EE81, 0x3EFF4)
SCENARIO_50_SHA256 = "5721530a386aded4cf07ba7954a65c9a18fa583ebd379c7f285bb5fa1ca92661"
LOOKUP_OFFSET = 0x348DAC

REGISTRATION_WRAPPER = 0x08061D7C
DISPATCH_COMMON = 0x08061C58
CLEANUP_HELPER = 0x08061E00

# callsite, one-based slot (zero is the scheduler process), literal offset,
# exact Thumb callback pointer.  The slot-zero initializer loads its callback
# through r8 from the listed literal; every other call uses a local LDR r1.
REGISTRATION_SPECS = (
    (0x6106C, 1, 0x6107C, 0x0808F73D),
    (0x61D4E, 0, 0x61D64, 0x08061D71),
    (0x6EAC4, 2, 0x6EAD4, 0x0806E959),
    (0x7AAE0, 4, 0x7AB28, 0x0807A34D),
    (0x8599A, 1, 0x859B4, 0x0808F73D),
    (0x85A08, 5, 0x85A14, 0x0808584D),
    (0x8C1E0, 2, 0x8C1F8, 0x0808C175),
    (0x8F1CE, 2, 0x8F204, 0x0808EF2D),
)

CALLBACK_SPECS = {
    0x0808F654: {
        "thumb_pointer": 0x0808F655,
        "pointer_occurrences": (),
        "direct_branch_callsites": (),
        "lifecycle_status": "open_computed_or_indirect_entry",
    },
    0x0808F73C: {
        "thumb_pointer": 0x0808F73D,
        "pointer_occurrences": (0x6107C, 0x859B4),
        "direct_branch_callsites": (),
        "lifecycle_status": "registration_dispatch_return_closed",
    },
    0x0808EF2C: {
        "thumb_pointer": 0x0808EF2D,
        "pointer_occurrences": (0x8F204,),
        "direct_branch_callsites": (),
        "lifecycle_status": "registration_dispatch_return_closed",
    },
}

DIRECT_BRANCH_DENOMINATORS = {
    REGISTRATION_WRAPPER: (
        0x0806106C,
        0x08061D4E,
        0x0806EAC4,
        0x0807AAE0,
        0x0808599A,
        0x08085A08,
        0x0808C1E0,
        0x0808F1CE,
    ),
    DISPATCH_COMMON: tuple(0x08061C90 + index * 12 for index in range(11)),
    CLEANUP_HELPER: (
        0x08061C74,
        0x0806EADC,
        0x0807AC26,
        0x0807C74A,
        0x080858A2,
        0x080858A8,
        0x080858AE,
        0x080858B4,
        0x080859A0,
        0x08085A32,
        0x0808C200,
        0x0808F49E,
    ),
    0x0808F618: (0x0808F668,),
    0x0808F9C0: (0x0808F7CE,),
    0x0808A0F0: (0x0808F644, 0x0808F9C0),
    0x0808F654: (),
    0x0808F73C: (),
    0x0808EF2C: (),
}

WINDOW_SPECS = (
    (
        "registration_wrapper",
        0x61D7C,
        0x61DEA,
        "a95b7b4ebd38bd2422bad8c1ac40a932dae4f2173577b466152c8e1f0410660d",
    ),
    (
        "dispatch_common_and_literals",
        0x61C58,
        0x61C8C,
        "0ca2de9fa13697d6042e3792360a08a5d76278b172ad6fdda8316d387611ad37",
    ),
    (
        "eleven_slot_wrappers",
        0x61C8C,
        0x61D10,
        "b9637acd9938285609cc74c04ee173a63968d582b54f827c987959d1ffb6ec59",
    ),
    (
        "return_cleanup",
        0x61E00,
        0x61E1C,
        "6561d7b14adb45317767fa3ade10b54cc0b3d384274a0c77e504d999e95eb9b9",
    ),
    (
        "indirect_bx_r1_veneer",
        0x9C110,
        0x9C11C,
        "c8d1aed5a733599658000ec7d89114ae60194ea47863ccedba181604312a7f5e",
    ),
    (
        "open_callback_8f654",
        0x8F654,
        0x8F68A,
        "dc08329df508b18fe2bb71c1dcd185c095b9897cf5af382c0dfc103bdd440412",
    ),
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _addr(value: int) -> str:
    return f"0x{value:08X}"


def _safe_file(root: Path, relative: Path) -> Path:
    root = Path(root).resolve(strict=True)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"repository path escapes root: {relative}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository path uses a symlink: {relative}")
    resolved = (root / relative).resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"repository file is invalid: {relative}")
    return resolved


def _pointer_offsets(rom: bytes, pointer: int) -> list[int]:
    needle = pointer.to_bytes(4, "little")
    offsets: list[int] = []
    cursor = 0
    while True:
        cursor = rom.find(needle, cursor)
        if cursor < 0:
            return offsets
        offsets.append(cursor)
        cursor += 1


def _branch_denominators(rom: bytes) -> dict[int, list[int]]:
    targets = set(DIRECT_BRANCH_DENOMINATORS)
    found = {target: [] for target in targets}
    for branch in iter_thumb_direct_branches(rom, rom_base=ROM_BASE):
        if branch.target in found:
            found[branch.target].append(branch.address)
    return found


def _decode_registration(
    rom: bytes,
    callsite_offset: int,
    slot: int,
    literal_offset: int,
    callback_thumb: int,
) -> dict[str, Any]:
    first, second = struct.unpack_from("<HH", rom, callsite_offset)
    target = decode_thumb_bl(ROM_BASE + callsite_offset, first, second)
    if target != REGISTRATION_WRAPPER:
        raise ValueError(
            f"registration call at 0x{ROM_BASE + callsite_offset:08X} changed"
        )
    if int.from_bytes(rom[literal_offset : literal_offset + 4], "little") != callback_thumb:
        raise ValueError(
            f"registration callback literal at 0x{ROM_BASE + literal_offset:08X} changed"
        )

    if callsite_offset == 0x61D4E:
        if rom[0x61D4A:0x61D4E] != bytes.fromhex("00204146"):
            raise ValueError("slot-zero registration argument flow changed")
    else:
        move_slot = struct.unpack_from("<H", rom, callsite_offset - 2)[0]
        load_callback = struct.unpack_from("<H", rom, callsite_offset - 4)[0]
        if move_slot != 0x2000 | slot:
            raise ValueError(
                f"registration slot at 0x{ROM_BASE + callsite_offset:08X} changed"
            )
        if load_callback & 0xF800 != 0x4800 or (load_callback >> 8) & 7 != 1:
            raise ValueError(
                f"registration callback LDR at 0x{ROM_BASE + callsite_offset:08X} changed"
            )
        instruction_address = ROM_BASE + callsite_offset - 4
        decoded_literal = (
            ((instruction_address + 4) & ~3) + (load_callback & 0xFF) * 4
        ) - ROM_BASE
        if decoded_literal != literal_offset:
            raise ValueError(
                f"registration callback literal binding at 0x{instruction_address:08X} changed"
            )

    return {
        "callsite": callsite_offset,
        "callsite_address": _addr(ROM_BASE + callsite_offset),
        "slot": slot,
        "callback_literal_offset": literal_offset,
        "callback_thumb": _addr(callback_thumb),
    }


def verify_scheduler_callback_lifecycle_gate(
    root: Path, *, rom: bytes | None = None
) -> dict[str, Any]:
    errors: list[str] = []
    if rom is None:
        try:
            rom = _safe_file(root, ROM_PATH).read_bytes()
        except (OSError, ValueError) as exc:
            rom = b""
            errors.append(str(exc))

    rom_sha256 = _sha(rom)
    if len(rom) != ROM_SIZE:
        errors.append(f"fixed ROM size changed: expected {ROM_SIZE}, got {len(rom)}")
    if rom_sha256 != ROM_SHA256:
        errors.append("fixed ROM SHA-256 changed")

    candidate_raw = rom[CANDIDATE_RANGE[0] : CANDIDATE_RANGE[1]]
    candidate_sha256 = _sha(candidate_raw)
    if candidate_sha256 != CANDIDATE_SHA256:
        errors.append("candidate bytes changed")

    windows: list[dict[str, Any]] = []
    for name, start, end, expected_sha256 in WINDOW_SPECS:
        actual_sha256 = _sha(rom[start:end])
        if actual_sha256 != expected_sha256:
            errors.append(f"{name} raw window changed")
        windows.append(
            {
                "name": name,
                "range": [start, end],
                "sha256": actual_sha256,
            }
        )

    branch_denominators = _branch_denominators(rom)
    for target, expected in DIRECT_BRANCH_DENOMINATORS.items():
        actual = tuple(branch_denominators[target])
        if actual != expected:
            label = (
                "registration wrapper callsite denominator"
                if target == REGISTRATION_WRAPPER
                else f"{_addr(target)} direct branch denominator"
            )
            errors.append(f"{label} changed")

    direct_registrations: list[dict[str, Any]] = []
    for spec in REGISTRATION_SPECS:
        try:
            direct_registrations.append(_decode_registration(rom, *spec))
        except (ValueError, struct.error) as exc:
            errors.append(str(exc))

    callbacks: dict[str, dict[str, Any]] = {}
    for entry, spec in CALLBACK_SPECS.items():
        pointer_occurrences = _pointer_offsets(rom, spec["thumb_pointer"])
        if tuple(pointer_occurrences) != spec["pointer_occurrences"]:
            errors.append(f"{_addr(entry)} pointer denominator changed")
        direct_callsites = [
            address - ROM_BASE for address in branch_denominators[entry]
        ]
        expected_direct = [
            address - ROM_BASE for address in spec["direct_branch_callsites"]
        ]
        if direct_callsites != expected_direct:
            errors.append(f"{_addr(entry)} direct entry denominator changed")
        callbacks[_addr(entry)] = {
            "entry": _addr(entry),
            "thumb_pointer": _addr(spec["thumb_pointer"]),
            "pointer_occurrences": pointer_occurrences,
            "direct_branch_callsites": direct_callsites,
            "lifecycle_status": spec["lifecycle_status"],
        }

    slot_histories: dict[str, list[str]] = {}
    for registration in direct_registrations:
        slot_histories.setdefault(str(registration["slot"]), []).append(
            registration["callback_thumb"]
        )

    scenario_raw = rom[SCENARIO_50_RANGE[0] : SCENARIO_50_RANGE[1]]
    if _sha(scenario_raw) != SCENARIO_50_SHA256:
        errors.append("scenario 50 counterexample bytes changed")
    if rom[0x3EE81:0x3EE83] != bytes.fromhex("0f1e"):
        errors.append("scenario 50 state+0x19 writer changed")
    if rom[0x3EFEE:0x3EFF1] != bytes.fromhex("1a1f00"):
        errors.append("scenario 50 state+0x16 writer changed")
    if rom[0x3EFF3:0x3EFF4] != b"\x00":
        errors.append("scenario 50 terminal changed")
    lookup_value = rom[LOOKUP_OFFSET + 31] if len(rom) > LOOKUP_OFFSET + 31 else None
    if lookup_value != 90:
        errors.append("scenario 50 lookup value changed")

    consumer_paths = {
        _addr(target): {
            "direct_callsites": [
                address - ROM_BASE for address in branch_denominators[target]
            ],
            "direct_branch_denominator_complete": True,
        }
        for target in (0x0808F618, 0x0808F9C0, 0x0808A0F0)
    }
    counterexample = {
        "scenario": 50,
        "scenario_range": list(SCENARIO_50_RANGE),
        "state_16": 31,
        "state_19": 30,
        "lookup_value": lookup_value,
        "combined_index": None if lookup_value is None else lookup_value + 30,
        "claimed_safe_max": 111,
        "disproves_local_safe_bound": lookup_value == 90,
    }
    scope = {
        "fixed_rom_identity_verified": not any(
            error.startswith("fixed ROM") for error in errors
        ),
        "raw_thumb_pointer_occurrence_denominators_complete": True,
        "raw_direct_branch_denominators_complete": True,
        "literal_registered_callback_dispatch_structure_complete": True,
        "computed_producer_denominator_complete": False,
        "state_writer_and_inheritance_denominator_complete": False,
        "natural_runtime_oob_proven": False,
        "candidate_record_count_proven": False,
        "coverage_claim_created": False,
        "artifact_created": False,
    }
    decision = {
        "candidate_range": list(CANDIDATE_RANGE),
        "candidate_bytes": CANDIDATE_RANGE[1] - CANDIDATE_RANGE[0],
        "bytes_promoted": 0,
        "promotion_eligible": False,
        "lifecycle_closed": False,
        "coverage_action": "keep_unknown",
        "blocking_callback": "0x0808F654",
    }
    return {
        "schema": SCHEMA,
        "verified": not errors,
        "errors": errors,
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": rom_sha256,
        },
        "candidate": {
            "range": list(CANDIDATE_RANGE),
            "size": len(candidate_raw),
            "sha256": candidate_sha256,
        },
        "decision": decision,
        "callbacks": callbacks,
        "scheduler_dispatch": {
            "registration_wrapper": _addr(REGISTRATION_WRAPPER),
            "dispatch_common": _addr(DISPATCH_COMMON),
            "indirect_call_veneer": "0x0809C114 (BX r1)",
            "return_cleanup": _addr(CLEANUP_HELPER),
            "direct_registrations": direct_registrations,
            "slot_histories": slot_histories,
            "window_contracts": windows,
        },
        "consumer_paths": consumer_paths,
        "counterexample": counterexample,
        "unresolved_frontiers": [
            {
                "id": "callback-8f654-entry-producer",
                "entry": "0x0808F654",
                "reason": "no raw direct branch or exact Thumb pointer producer; computed/RAM/indirect producer denominator remains open",
            },
            {
                "id": "state-writer-inheritance-denominator",
                "reason": "all state+0x16/+0x19 writers, copies, clears and inheritance paths are not closed",
            },
        ],
        "scope": scope,
        "non_claims": [
            "No natural gameplay out-of-bounds access is claimed.",
            "No 112-entry or 118-entry physical table denominator is claimed.",
            "No computed, RAM-derived or indirect callback producer denominator is claimed complete.",
            "No candidate bytes are classified, promoted, made editable or declared allocatable.",
        ],
    }


def _canonical(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = verify_scheduler_callback_lifecycle_gate(args.root)
    rendered = _canonical(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
