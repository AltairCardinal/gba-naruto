#!/usr/bin/env python3
"""Bind status 0x13's queued-hit modifier and post-resolution lifecycle."""

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
STATUS_LOOKUP = 0x0806C160
STATUS_REMOVE = 0x0806C1A4
SHARED_RESOLVER = 0x08076A30


def _offset(address: int) -> int:
    return address - ROM_BASE


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _expect_bytes(rom: bytes, start: int, expected_hex: str, label: str) -> None:
    expected = bytes.fromhex(expected_hex)
    actual = rom[_offset(start) : _offset(start) + len(expected)]
    _expect(actual, expected, label)


def _expect_bl(rom: bytes, callsite: int, target: int, label: str) -> None:
    actual = decode_thumb_bl(
        callsite,
        _u16(rom, callsite),
        _u16(rom, callsite + 2),
    )
    _expect(actual, target, label)


def build_status_hit_count_modifier_manifest(
    rom_path: Path | str,
) -> dict[str, Any]:
    rom = Path(rom_path).read_bytes()
    _expect(
        hashlib.sha256(
            rom[_offset(EVENT_BUILDER) : _offset(EVENT_BUILDER_END)]
        ).hexdigest(),
        EVENT_BUILDER_SHA256,
        "event builder SHA-256",
    )
    _expect(
        hashlib.sha256(
            rom[_offset(RESOLVER_QUEUE) : _offset(RESOLVER_QUEUE_END)]
        ).hexdigest(),
        RESOLVER_QUEUE_SHA256,
        "resolver queue SHA-256",
    )

    _expect_bl(rom, 0x08075654, STATUS_LOOKUP, "builder status 0x13 lookup")
    _expect_bl(rom, 0x08077470, SHARED_RESOLVER, "paired shared resolver call")
    _expect_bl(rom, 0x08077488, STATUS_LOOKUP, "post-resolution status 0x13 lookup")
    _expect_bl(rom, 0x08077496, STATUS_REMOVE, "post-resolution status 0x13 removal")

    # The exact builder slice gates on effect type 0x14, indexes the source's
    # active status record, reads byte +6, and adds it to the shared hit-count
    # modifier accumulator. There is no 0xFF comparison between lookup and read.
    _expect_bytes(
        rom,
        0x08075642,
        "5148484401883f20084014280ed100981321f6f784fd0006400d089c2018da3000780c9908180006000e0c90",
        "status 0x13 hit-count modifier slice",
    )
    # runtime_template[3] plus the accumulator becomes event byte +0x12.
    _expect_bytes(
        rom,
        0x080757BC,
        "1748404400780c9a1018a874",
        "queued hit-count write slice",
    )
    # The paired handler resolves first, clears its transient amount fields,
    # then removes source status 0x13 with mode 1.
    _expect_bytes(
        rom,
        0x08077458,
        "30787178327b73790093f388019333890293002503954346fff7defa0006000e069000203581f58070713478201c1321f4f76afe011c0906090e201c0122f4f785fe",
        "status 0x13 post-resolution removal slice",
    )

    return {
        "schema_version": 1,
        "identity": "battle_status_0x13_hit_count_modifier_and_lifecycle",
        "event_builder": f"0x{EVENT_BUILDER:08X}",
        "event_builder_end": f"0x{EVENT_BUILDER_END:08X}",
        "event_builder_sha256": EVENT_BUILDER_SHA256,
        "resolver_queue": f"0x{RESOLVER_QUEUE:08X}",
        "resolver_queue_sha256": RESOLVER_QUEUE_SHA256,
        "status_code": "0x13",
        "effect_type_low_6": "0x14",
        "builder_lookup_callsite": "0x08075654",
        "modifier_record_offset": 6,
        "modifier_width": "low_u8_of_stored_u16",
        "queued_hit_count_operation": (
            "template_hit_count_plus_shared_modifier_accumulator"
        ),
        "queued_hit_count_event_offset": 0x12,
        "shared_resolver_callsite": "0x08077470",
        "post_resolution_lookup_callsite": "0x08077488",
        "post_resolution_remove_callsite": "0x08077496",
        "post_resolution_removal_mode": 1,
        "post_resolution_emits_removed_status_event_if_capacity": True,
        "builder_checks_not_found_before_record_read": False,
        "implementation_requirement": (
            "effect_type_0x14_requires_status_0x13_or_content_validation_fails"
        ),
        "visible_gameplay_name": None,
        "conclusion": (
            "For effect type 0x14, the low byte of status 0x13 record field +6 "
            "contributes to the queued hit count at event +0x12. The paired "
            "resolver branch removes source status 0x13 afterward using mode 1."
        ),
        "boundary": (
            "The builder field read, hit-count write, resolve-before-removal order, "
            "and removal mode are statically closed. The visible status name, "
            "producer, parameter high byte, natural presentation, and interactions "
            "with other hit-count modifiers remain unresolved."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-status-hit-count-modifier-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_status_hit_count_modifier_manifest(args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
