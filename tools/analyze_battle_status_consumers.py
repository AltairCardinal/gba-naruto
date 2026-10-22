#!/usr/bin/env python3
"""Inventory every direct status lookup/upsert reference in the original ROM."""

from __future__ import annotations

import argparse
from collections import Counter
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
STATUS_LOOKUP = 0x0806C160
STATUS_UPSERT = 0x0806C204
LOOKUP_REFERENCE_COUNT = 96
LOOKUP_REFERENCE_SHA256 = "8c8c19f160a99a33b65ca11ac8107278a593ef33914288b8e484a34d65d1c6d3"
UPSERT_REFERENCE_COUNT = 21
UPSERT_REFERENCE_SHA256 = "691c1fe5f9c4559872e01cdd86cd6b2fb5a750258549aad8e8fd04d1886e4fcc"
KNOWN_REACTION_CODES = {0x04, 0x09, 0x0A, 0x10, 0x16, 0x19}
KNOWN_BLOCKER_CODES = {0x0F, 0x11, 0x15, 0x3D, 0x3E, 0x3F}


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, address - ROM_BASE)[0]


def _address_sha256(addresses: list[int]) -> str:
    packed = b"".join(struct.pack("<I", address) for address in addresses)
    return hashlib.sha256(packed).hexdigest()


def _format_code(code: int) -> str:
    return f"0x{code:02X}"


def _format_address(address: int) -> str:
    return f"0x{address:08X}"


def build_status_consumer_manifest(rom_path: Path | str) -> dict[str, Any]:
    rom = Path(rom_path).read_bytes()
    references = {STATUS_LOOKUP: [], STATUS_UPSERT: []}
    for branch in iter_thumb_direct_branches(rom, rom_base=ROM_BASE):
        if branch.mnemonic == "bl" and branch.target in references:
            references[branch.target].append(branch.address)

    lookup_references = references[STATUS_LOOKUP]
    upsert_references = references[STATUS_UPSERT]
    _expect(len(lookup_references), LOOKUP_REFERENCE_COUNT, "status lookup reference count")
    _expect(
        _address_sha256(lookup_references),
        LOOKUP_REFERENCE_SHA256,
        "status lookup reference address SHA-256",
    )
    _expect(len(upsert_references), UPSERT_REFERENCE_COUNT, "status upsert reference count")
    _expect(
        _address_sha256(upsert_references),
        UPSERT_REFERENCE_SHA256,
        "status upsert reference address SHA-256",
    )

    immediate_usage: Counter[int] = Counter()
    dynamic_callsites: list[int] = []
    for callsite in lookup_references:
        previous = _u16(rom, callsite - 2)
        if previous & 0xFF00 == 0x2100:  # MOVS r1, #imm8
            immediate_usage[previous & 0xFF] += 1
        else:
            dynamic_callsites.append(callsite)

    _expect(sum(immediate_usage.values()), 95, "immediate status lookup count")
    _expect(dynamic_callsites, [0x0806C2C6], "dynamic status lookup callsites")
    all_immediate_codes = set(immediate_usage)
    classified_codes = KNOWN_REACTION_CODES | KNOWN_BLOCKER_CODES

    return {
        "schema_version": 1,
        "identity": "battle_status_direct_producer_and_consumer_reference_inventory",
        "lookup": f"0x{STATUS_LOOKUP:08X}",
        "upsert": f"0x{STATUS_UPSERT:08X}",
        "lookup_reference_count": len(lookup_references),
        "lookup_reference_address_sha256": _address_sha256(lookup_references),
        "lookup_references": [_format_address(address) for address in lookup_references],
        "upsert_reference_count": len(upsert_references),
        "upsert_reference_address_sha256": _address_sha256(upsert_references),
        "upsert_references": [_format_address(address) for address in upsert_references],
        "immediate_lookup_count": sum(immediate_usage.values()),
        "dynamic_lookup_callsites": [
            _format_address(address) for address in dynamic_callsites
        ],
        "immediate_lookup_code_usage": {
            _format_code(code): immediate_usage[code]
            for code in sorted(immediate_usage)
        },
        "unique_immediate_lookup_codes": len(all_immediate_codes),
        "known_reaction_lookup_codes": [
            _format_code(code) for code in sorted(KNOWN_REACTION_CODES)
        ],
        "known_blocker_lookup_codes": [
            _format_code(code) for code in sorted(KNOWN_BLOCKER_CODES)
        ],
        "unclassified_immediate_lookup_codes": len(
            all_immediate_codes - classified_codes
        ),
        "conclusion": (
            "The original ROM contains 96 direct status lookup references and 21 "
            "direct status upsert references. Immediate lookups cover 25 status "
            "codes; the already-bound blocker/reaction families cover only 12 of them."
        ),
        "boundary": (
            "This manifest closes direct-reference and immediate-code inventory only. "
            "It does not assign gameplay meaning to the remaining 13 codes, prove "
            "indirect callers absent, or replace per-consumer data-flow analysis."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-status-consumer-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_status_consumer_manifest(args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
