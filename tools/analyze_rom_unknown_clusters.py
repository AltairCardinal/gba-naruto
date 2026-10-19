#!/usr/bin/env python3
"""Rank current unknown ROM ranges without assigning them semantics."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


SCHEMA = "rom-unknown-cluster-analysis-v1"
SCOPE = "Candidate ranking only; adjacency and byte patterns are not semantic evidence."
LENGTH_BUCKETS = (
    ("1-3", 1, 3),
    ("4-15", 4, 15),
    ("16-63", 16, 63),
    ("64-255", 64, 255),
    ("256-1023", 256, 1023),
    (">=1024", 1024, None),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entropy(data: bytes) -> float:
    counts = collections.Counter(data)
    length = len(data)
    return -sum(
        (count / length) * math.log2(count / length) for count in counts.values()
    )


def _load_inputs(rom_path: Path, coverage_path: Path) -> tuple[bytes, dict[str, Any], bytes]:
    rom = rom_path.read_bytes()
    coverage_bytes = coverage_path.read_bytes()
    coverage = json.loads(coverage_bytes)
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage schema is not rom-byte-coverage-v1")
    return rom, coverage, coverage_bytes


def analyze(
    rom: bytes,
    coverage: dict[str, Any],
    *,
    top: int,
) -> dict[str, Any]:
    if top <= 0:
        raise ValueError("top must be positive")
    segments = coverage.get("segments")
    summary = coverage.get("summary")
    if not isinstance(segments, list) or not isinstance(summary, dict):
        raise ValueError("coverage segments or summary are missing")
    if summary.get("rom_bytes") != len(rom):
        raise ValueError("ROM size does not match coverage summary")

    unknown_rows: list[dict[str, Any]] = []
    classified_bytes = 0
    cursor = 0
    adjacency: dict[tuple[str, str], dict[str, int]] = collections.defaultdict(
        lambda: {"range_count": 0, "total_bytes": 0, "max_range_bytes": 0}
    )
    buckets = {
        name: {"range_count": 0, "total_bytes": 0}
        for name, _minimum, _maximum in LENGTH_BUCKETS
    }

    for index, segment in enumerate(segments):
        interval = segment.get("range")
        primary_class = segment.get("primary_class")
        if (
            not isinstance(interval, list)
            or len(interval) != 2
            or not all(isinstance(value, int) for value in interval)
            or not isinstance(primary_class, str)
        ):
            raise ValueError(f"coverage segment {index} is malformed")
        start, end = interval
        if start != cursor or end <= start or end > len(rom):
            raise ValueError(f"coverage segment {index} is not a contiguous ROM partition")
        cursor = end
        length = end - start
        if primary_class != "unknown":
            classified_bytes += length
            continue

        left_class = segments[index - 1]["primary_class"] if index else "ROM_START"
        right_class = (
            segments[index + 1]["primary_class"]
            if index + 1 < len(segments)
            else "ROM_END"
        )
        data = rom[start:end]
        unknown_rows.append(
            {
                "range": [start, end],
                "length": length,
                "left_primary_class": left_class,
                "right_primary_class": right_class,
                "distinct_byte_count": len(set(data)),
                "shannon_entropy_bits_per_byte": round(_entropy(data), 6),
                "zero_byte_count": data.count(0),
                "ff_byte_count": data.count(0xFF),
                "bytes_sha256": _sha256(data),
            }
        )
        family = adjacency[(left_class, right_class)]
        family["range_count"] += 1
        family["total_bytes"] += length
        family["max_range_bytes"] = max(family["max_range_bytes"], length)
        for name, minimum, maximum in LENGTH_BUCKETS:
            if length >= minimum and (maximum is None or length <= maximum):
                buckets[name]["range_count"] += 1
                buckets[name]["total_bytes"] += length
                break

    if cursor != len(rom):
        raise ValueError("coverage segments do not span the complete ROM")
    unknown_bytes = sum(row["length"] for row in unknown_rows)
    if summary.get("unknown_bytes") != unknown_bytes:
        raise ValueError("unknown byte total does not match coverage summary")
    if summary.get("classified_bytes") != classified_bytes:
        raise ValueError("classified byte total does not match coverage summary")

    families = [
        {
            "left_primary_class": left,
            "right_primary_class": right,
            **counts,
        }
        for (left, right), counts in adjacency.items()
    ]
    families.sort(
        key=lambda row: (
            -row["total_bytes"],
            -row["range_count"],
            row["left_primary_class"],
            row["right_primary_class"],
        )
    )
    unknown_rows.sort(key=lambda row: (-row["length"], row["range"][0]))
    return {
        "schema": SCHEMA,
        "scope": SCOPE,
        "summary": {
            "rom_bytes": len(rom),
            "unknown_bytes": unknown_bytes,
            "unknown_range_count": len(unknown_rows),
        },
        "length_buckets": buckets,
        "adjacency_families": families[:top],
        "largest_ranges": unknown_rows[:top],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--top", type=int, default=40)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        rom, coverage, coverage_bytes = _load_inputs(args.rom, args.coverage)
        report = analyze(rom, coverage, top=args.top)
        report["inputs"] = {
            "rom_path": args.rom.as_posix(),
            "rom_sha256": _sha256(rom),
            "coverage_path": args.coverage.as_posix(),
            "coverage_sha256": _sha256(coverage_bytes),
        }
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
