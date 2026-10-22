#!/usr/bin/env python3
"""Print the negative-control results of an L2 run."""
from __future__ import annotations

import io
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "build" / "l2-runtime.json"
data = json.loads(path.read_text(encoding="utf-8"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for control in data.get("negative_controls", []):
    detail = control["checks"][0]["detail"] if control["checks"] else ""
    print(f"{control['structure']:28s} ok={control['ok']!s:5s} {detail[:90]}")
print(f"\nstructures ok: "
      f"{sum(1 for s in data['structures'] if s['ok'])}/{len(data['structures'])}")
print("failures:")
for item in data.get("failures", []):
    print("  -", item)
