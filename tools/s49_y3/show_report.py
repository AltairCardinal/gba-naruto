#!/usr/bin/env python3
"""Print the judgment bench summary of a report (UTF-8 safe)."""
import io
import json
import sys

path = sys.argv[1]
document = json.load(io.open(path, encoding="utf-8"))
summary = document.get("summary") or {}
for key in ("field_residual", "full_residual", "overlay_residual",
            "attribution", "pairing_diff_subclasses", "pairing_quality",
            "confidence", "black_transition_frames", "static_frames"):
    print(f"{key} = {summary.get(key)}")
print("content_sha256 =", document.get("content_sha256"))
