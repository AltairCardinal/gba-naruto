#!/usr/bin/env python3
"""Observe the scenario-41 player-unit selection call without changing behavior."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

try:
    from tools.published_call_observer import (
        ObserverSite,
        assert_non_overlapping_sites,
        patch_observer,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from published_call_observer import ObserverSite, assert_non_overlapping_sites, patch_observer

BASE_SHA1 = "26f60795fa5e63b4f0264b84e453beffd56b9f7d"
ROM_BASE = 0x08000000
HOOK = 0x08073946
ORIGINAL = 0x0806F718
STUB = 0x0809E800
STUB_OFFSET = STUB - ROM_BASE
STUB_SIZE = 96
SCRATCH = 0x0203F080
MAGIC = int.from_bytes(b"PCO1", "little")
PLAYER_CONTROL_EVENT = 1
CURRENT_UNIT_HOOK = 0x080739D8
CURRENT_UNIT_ORIGINAL = 0x08069DB8
CURRENT_UNIT_STUB = 0x0809E880
CURRENT_UNIT_STUB_OFFSET = CURRENT_UNIT_STUB - ROM_BASE
CURRENT_UNIT_SCRATCH = 0x0203F060
CURRENT_UNIT_MAGIC = int.from_bytes(b"PCU1", "little")
CURRENT_UNIT_EVENT = 2
ACTIVE_CURRENT_UNIT_HOOK = 0x08073BAC
ACTIVE_CURRENT_UNIT_ORIGINAL = 0x08069DB8
ACTIVE_CURRENT_UNIT_STUB = 0x0809E900
ACTIVE_CURRENT_UNIT_STUB_OFFSET = ACTIVE_CURRENT_UNIT_STUB - ROM_BASE
ACTIVE_CURRENT_UNIT_SCRATCH = 0x0203F0A0
ACTIVE_CURRENT_UNIT_MAGIC = int.from_bytes(b"PCA1", "little")
ACTIVE_CURRENT_UNIT_EVENT = 3
EVENT_COUNTER = 0x0203F040

PLAYER_CONTROL_SITE = ObserverSite(
    "player-control", HOOK, ORIGINAL, STUB, SCRATCH, MAGIC, PLAYER_CONTROL_EVENT
)
CURRENT_UNIT_SITE = ObserverSite(
    "current-unit",
    CURRENT_UNIT_HOOK,
    CURRENT_UNIT_ORIGINAL,
    CURRENT_UNIT_STUB,
    CURRENT_UNIT_SCRATCH,
    CURRENT_UNIT_MAGIC,
    CURRENT_UNIT_EVENT,
)
ACTIVE_CURRENT_UNIT_SITE = ObserverSite(
    "active-current-unit",
    ACTIVE_CURRENT_UNIT_HOOK,
    ACTIVE_CURRENT_UNIT_ORIGINAL,
    ACTIVE_CURRENT_UNIT_STUB,
    ACTIVE_CURRENT_UNIT_SCRATCH,
    ACTIVE_CURRENT_UNIT_MAGIC,
    ACTIVE_CURRENT_UNIT_EVENT,
)
OBSERVER_SITES = (PLAYER_CONTROL_SITE, CURRENT_UNIT_SITE, ACTIVE_CURRENT_UNIT_SITE)


def build_probe(base: bytes, *, verify_sha1: bool = True) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if verify_sha1 and digest != BASE_SHA1:
        raise ValueError(f"player-control probe requires the immutable base ROM ({BASE_SHA1})")

    assert_non_overlapping_sites(OBSERVER_SITES, EVENT_COUNTER, 4, STUB_SIZE)
    rom = bytearray(base)
    for site in OBSERVER_SITES:
        patch_observer(rom, site, EVENT_COUNTER, STUB_SIZE)
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    args = parser.parse_args()
    output = build_probe(args.base_rom.read_bytes())
    args.output_rom.parent.mkdir(parents=True, exist_ok=True)
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
