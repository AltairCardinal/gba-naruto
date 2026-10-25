#!/usr/bin/env python3
"""Make a deliberately *worse* report, to prove the ratchet gate really bites.

The ratchet gate of the judgment bench is only worth something if it can be
shown to fail.  This script takes a real report and inflates every residual
it contains, deterministically, so the gate has something to catch.

    python tools/s49_fidelity_report/regressed.py \\
        build/s49-report/report-w2.json \\
        --out build/s49-report/report-w2-regressed.json

    python tools/s49_fidelity_report.py --out build/s49-report/report-w2.json \\
        --skip-capture --ratchet build/s49-report/report-w2-regressed.json
    # -> exits non zero: the residual got bigger

Nothing here is a measurement: the output is a **test fixture**, not a
result.  It is written to ``build/`` and is not part of the evidence.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from s49_fidelity_report.capture import write_text  # noqa: E402


def worsen(document: dict, factor: int = 2) -> dict:
    """Inflate every residual the report carries."""
    summary = document.get("summary", {})
    for key in ("field_residual", "full_residual", "overlay_residual"):
        stats = summary.get(key)
        if not stats:
            continue
        for metric in ("min", "median", "max", "sum", "mean"):
            if metric in stats:
                stats[metric] = stats[metric] * factor
        if "zero_frames" in stats:
            stats["zero_frames"] = max(0, stats["zero_frames"] - 1)
    for row in document.get("frames", []):
        for key in ("field_residual_px", "full_residual_px"):
            if key in row:
                row[key] = row[key] * factor
        overlay = row.get("overlay_residual")
        if overlay:
            for key in ("both_lit", "original_only", "remake_only",
                        "family_mismatches", "residual"):
                if key in overlay:
                    overlay[key] = overlay[key] * factor
    document["schema"] = str(document.get("schema")) + "+regressed"
    document["regressed_note"] = (
        "a deliberately worse copy of a real report -- a ratchet test "
        "fixture, not a measurement")
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report", type=pathlib.Path)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--factor", type=int, default=2)
    args = parser.parse_args()

    document = json.loads(args.report.read_text(encoding="utf-8"))
    write_text(args.out, json.dumps(worsen(document, args.factor),
                                    ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
