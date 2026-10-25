#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dump the per-frame residual breakdown of an s49 fidelity report (acceptance instrument).

Usage:
    python tools/s49_w25/baseline_breakdown.py [report.json]

Reads the JSON report produced by tools/s49_fidelity_report.py and prints one
line per original frame: which remake frame it was paired with, the field /
full / overlay residuals, the chosen offset and the classifier verdict.
The total field residual is the number the acceptance ratchet is defined on.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT = Path("build/s49-package/baseline-accepted/report.json")


def _name(side: dict) -> str:
    for key in ("name", "step", "label", "file"):
        if isinstance(side, dict) and side.get(key):
            return str(side[key])
    return "?"


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT
    data = json.loads(path.read_text(encoding="utf-8"))
    frames = data.get("frames", [])
    total = 0
    print(f"# report: {path}")
    print(f"# frames: {len(frames)}")
    for idx, frame in enumerate(frames):
        original = frame.get("original") or {}
        best = frame.get("best_match")
        if isinstance(best, dict):
            best_name = _name(best)
            best_off = best.get("offset")
        else:
            best_name = str(best)
            best_off = (frame.get("signals") or {}).get("offset")
        field = int(frame.get("field_residual_px") or 0)
        full = int(frame.get("full_residual_px") or 0)
        overlay = int((frame.get("overlay_residual") or {}).get("residual") or 0)
        total += field
        print(
            f"{idx:2d} {_name(original):<16} -> {best_name:<16} "
            f"field={field:6d} full={full:6d} ov={overlay:5d} "
            f"off={best_off} {frame.get('verdict')}"
        )
    summary = data.get("summary", {})
    print(f"# sum(field) = {total}")
    print(f"# summary.field_residual.sum = {summary.get('field_residual', {}).get('sum')}")
    print(f"# attribution = {summary.get('attribution')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
