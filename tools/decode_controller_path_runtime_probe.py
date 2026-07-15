#!/usr/bin/env python3
"""Decode or compare controller-path observer memory dumps as JSON."""
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
UINT32_MASK = 0xFFFFFFFF
UINT32_HALF_RANGE = 0x80000000


def _uint32_forward(previous: int, current: int) -> bool:
    delta = (current - previous) & UINT32_MASK
    return 0 < delta < UINT32_HALF_RANGE


def _record_sequence(record: dict) -> int:
    return int(record["sequence"], 16)


def _order_by_shared_sequence(records: list[dict], boundary: int) -> list[dict]:
    return sorted(
        records,
        key=lambda record: (boundary - _record_sequence(record)) & UINT32_MASK,
        reverse=True,
    )


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
    valid_records = _order_by_shared_sequence(
        [record for record in records if record["valid"]], event_counter
    )
    return {
        "mode": "single_dump_decode",
        "freshness_evaluated": False,
        "event_counter": event_counter,
        "records": records,
        "valid_records": valid_records,
    }


def compare_dumps(baseline: bytes, final: bytes) -> dict:
    baseline_decoded = decode_dump(baseline)
    final_decoded = decode_dump(final)
    baseline_boundary = baseline_decoded["event_counter"]
    final_boundary = final_decoded["event_counter"]
    fresh_records = []
    for baseline_record, final_record in zip(
        baseline_decoded["records"], final_decoded["records"], strict=True
    ):
        baseline_sequence = _record_sequence(baseline_record)
        final_sequence = _record_sequence(final_record)
        if (
            final_record["valid"]
            and _uint32_forward(
                baseline_record["hit_count"], final_record["hit_count"]
            )
            and _uint32_forward(baseline_sequence, final_sequence)
            and _uint32_forward(baseline_boundary, final_sequence)
        ):
            fresh_records.append(final_record)
    return {
        "mode": "baseline_final_compare",
        "freshness_evaluated": True,
        "baseline": baseline_decoded,
        "final": final_decoded,
        "fresh_records": _order_by_shared_sequence(fresh_records, final_boundary),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    decode_parser = subparsers.add_parser(
        "decode", help="decode one dump as ABI-valid diagnostics only"
    )
    decode_parser.add_argument("dump", type=Path)
    decode_parser.add_argument("output_json", type=Path)
    compare_parser = subparsers.add_parser(
        "compare", help="compare explicit baseline/final dumps for fresh records"
    )
    compare_parser.add_argument("baseline", type=Path)
    compare_parser.add_argument("final", type=Path)
    compare_parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    if args.command == "decode":
        decoded = decode_dump(args.dump.read_bytes())
    else:
        decoded = compare_dumps(args.baseline.read_bytes(), args.final.read_bytes())
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(decoded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
