#!/usr/bin/env python3
"""Measure where build_manifest spends its wall clock.

This harness does not modify any repository file: it imports the coverage
auditor, wraps every module-level claim producer with a timer, and reports
the distribution.  It exists because the 57-minute rebuild cost had to be
attributed to concrete producers before any cache or concurrency work could
be designed safely.

    python3 tools/profile_coverage_build.py --root . --out <path.json>
"""

from __future__ import annotations

import argparse
import functools
import json
from pathlib import Path
import sys
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _producers(module: Any) -> list[str]:
    return sorted(
        name
        for name in dir(module)
        if name.startswith("_") and name.endswith("_claims")
        and callable(getattr(module, name))
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    from tools import audit_rom_byte_coverage as coverage_auditor

    timings: dict[str, float] = {}
    calls: dict[str, int] = {}
    for name in _producers(coverage_auditor):
        original = getattr(coverage_auditor, name)

        def make_wrapper(function, label):
            @functools.wraps(function)
            def wrapper(*inner_args, **inner_kwargs):
                started = time.monotonic()
                try:
                    return function(*inner_args, **inner_kwargs)
                finally:
                    timings[label] = timings.get(label, 0.0) + (
                        time.monotonic() - started
                    )
                    calls[label] = calls.get(label, 0) + 1

            return wrapper

        setattr(coverage_auditor, name, make_wrapper(original, name))

    started = time.monotonic()
    manifest = coverage_auditor.build_manifest(args.root)
    total = time.monotonic() - started

    rows = sorted(timings.items(), key=lambda item: item[1], reverse=True)
    payload = {
        "schema": "rom-coverage-build-profile-v1",
        "total_seconds": round(total, 3),
        "producer_count": len(rows),
        "producers": [
            {
                "name": name,
                "seconds": round(seconds, 3),
                "calls": calls.get(name, 0),
                "share_of_total": round(seconds / total, 4) if total else 0.0,
            }
            for name, seconds in rows
        ],
        "accounted_seconds": round(sum(timings.values()), 3),
        "unaccounted_seconds": round(total - sum(timings.values()), 3),
        "summary": {
            "unknown_bytes": manifest["summary"]["unknown_bytes"],
            "classified_bytes": manifest["summary"]["classified_bytes"],
            "claim_count": manifest["summary"]["claim_count"],
            "segment_count": manifest["summary"]["segment_count"],
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
