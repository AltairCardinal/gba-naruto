#!/usr/bin/env python3
"""E4: write the mavis-trash target list (paths only, LF, no BOM)."""

from __future__ import annotations

import json
import pathlib

MANIFEST = pathlib.Path(
    r"D:\Github\gba-naruto\build\w20-e4\dialogue-asset-cleanup-manifest.json"
)
ARGS = pathlib.Path(r"D:\Github\gba-naruto\build\w20-e4\rm-args.txt")


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    paths = [entry["lane_path"] for entry in manifest["entries"]]
    # D:\Github is a reparse point (junction) -> D:\Shell\Github.
    # mavis-trash refuses to trash a redirecting path, so use the real path.
    paths = [path.replace("D:\\Github\\", "D:\\Shell\\Github\\") for path in paths]
    ARGS.write_text(" ".join(paths) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {ARGS} with {len(paths)} targets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
