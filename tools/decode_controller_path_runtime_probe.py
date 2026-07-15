#!/usr/bin/env python3
"""Decode one controller-path observer memory dump into JSON diagnostics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

try:
    from tools.build_controller_path_runtime_probe import OBSERVER_SITES
    from tools.published_call_observer import ObserverSite
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from build_controller_path_runtime_probe import OBSERVER_SITES
    from published_call_observer import ObserverSite


DUMP_BASE = 0x0203F040
DUMP_SIZE = 0xC0


def decode_record(data: bytes, offset: int, site: ObserverSite) -> dict:
    magic, hits, arg0, arg1, arg2, sequence, event = struct.unpack_from(
        "<IIIHHII", data, offset
    )
    valid = (
        magic == site.magic
        and event == site.event_code
        and hits > 0
        and sequence > 0
    )
    return {
        "name": site.name,
        "magic": f"0x{magic:08X}",
        "hit_count": hits,
        "argument0": f"0x{arg0:08X}",
        "argument1": arg1,
        "argument2": arg2,
        "sequence": f"0x{sequence:08X}",
        "event_code": event,
        "valid": valid,
    }


def decode_dump(data: bytes) -> dict:
    if len(data) != DUMP_SIZE:
        raise ValueError(f"controller-path dump must contain exactly {DUMP_SIZE} bytes")
    event_counter = struct.unpack_from("<I", data, 0)[0]
    records = [
        decode_record(data, site.scratch - DUMP_BASE, site) for site in OBSERVER_SITES
    ]
    fresh_records = sorted(
        (record for record in records if record["valid"]),
        key=lambda record: int(record["sequence"], 16),
    )
    return {
        "event_counter": event_counter,
        "records": records,
        "fresh_records": fresh_records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    decoded = decode_dump(args.dump.read_bytes())
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(decoded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
