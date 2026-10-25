#!/usr/bin/env python3
"""Dump the judgment bench's frame rows and anchors (UTF-8 safe)."""
import io
import json
import sys

path = sys.argv[1]
document = json.load(io.open(path, encoding="utf-8"))
frames = document.get("frames") or []
print("frames:", len(frames))
if frames:
    print("first frame keys:", list(frames[0].keys()))
    print(json.dumps(frames[0], ensure_ascii=False, indent=1)[:2500])
