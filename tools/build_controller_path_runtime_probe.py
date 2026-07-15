#!/usr/bin/env python3
"""Build the five-site scenario-41 controller-path observer ROM."""
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
EVENT_COUNTER = 0x0203F040
STUB_SIZE = 96
OBSERVER_SITES = (
    ObserverSite(
        "player-select",
        0x08073946,
        0x0806F718,
        0x0809E800,
        0x0203F060,
        int.from_bytes(b"PCO1", "little"),
        1,
    ),
    ObserverSite(
        "action-1",
        0x08073A16,
        0x08067158,
        0x0809E880,
        0x0203F080,
        int.from_bytes(b"AC01", "little"),
        2,
    ),
    ObserverSite(
        "action-2",
        0x08073A2E,
        0x08067158,
        0x0809E900,
        0x0203F0A0,
        int.from_bytes(b"AC02", "little"),
        3,
    ),
    ObserverSite(
        "action-3",
        0x08073A3E,
        0x08067158,
        0x0809E980,
        0x0203F0C0,
        int.from_bytes(b"AC03", "little"),
        4,
    ),
    ObserverSite(
        "action-4",
        0x08073A4A,
        0x08067158,
        0x0809EA00,
        0x0203F0E0,
        int.from_bytes(b"AC04", "little"),
        5,
    ),
)


def build_probe(base: bytes, *, verify_sha1: bool = True) -> bytes:
    if verify_sha1 and hashlib.sha1(base).hexdigest() != BASE_SHA1:
        raise ValueError("controller-path probe requires the immutable base ROM")
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
