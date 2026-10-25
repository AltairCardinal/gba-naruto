#!/usr/bin/env python3
"""Collect the wave-25 lanes' owned files back into the shared tree.

`battle_runtime_scene.cpp` is excluded on purpose: H2 / H3 / H4 all edited it in
different regions, and a whole-file copy would drop two of the three edits.
That file goes through the real three-way merge instead
(`tools/s49_w25/merge_lanes.py`).

Every other owned file is copied verbatim, but only when its sha256 differs from
the shared tree's copy, and the report shows what was applied.  Files that a
lane did not touch are left alone.

Usage:
    python tools/s49_w25/collect_owned.py                 # report only
    python tools/s49_w25/collect_owned.py --apply
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHARED = Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel")
LANE_ROOT = REPO / "build"

# files that need the three-way merge, not a whole-file copy
MERGE_ONLY = {"game/src/battle_runtime_scene.cpp"}

OWNED: dict[str, list[str]] = {
    "w25-h1": [
        "game/include/konoha/battle_scene_presentation.h",
        "game/include/konoha/battle_presentation_script.h",
    ],
    "w25-h2": [
        "game/include/konoha/battle_black_field_star_mask.h",
        "game/include/konoha/battle_black_field_timing.h",
        "game/include/konoha/battle_presentation_content.h",
    ],
    "w25-h3": [
        "graphics/battle_ui_prepare_box.bmp",
        "graphics/battle_ui_prepare_box.json",
    ],
    "w25-h4": [
        "game/include/konoha/battle_range_ui_style.h",
    ],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    copied = 0
    for lane, files in OWNED.items():
        lane_root = LANE_ROOT / lane / "butano-sequel"
        print(f"\n=== {lane} ===")
        if not lane_root.is_dir():
            print(f"  lane missing: {lane_root}")
            continue
        for rel in files:
            src = lane_root / rel
            dst = SHARED / rel
            if rel in MERGE_ONLY:
                print(f"  [merge] {rel} -- handled by merge_lanes.py, skipped here")
                continue
            if not src.exists():
                print(f"  [owned] {rel}: MISSING in lane")
                continue
            src_sha = sha256(src)
            dst_sha = sha256(dst) if dst.exists() else "<absent>"
            if src_sha == dst_sha:
                print(f"  [owned] {rel}: unchanged")
                continue
            print(f"  [owned] {rel}: CHANGED {dst_sha[:12]} -> {src_sha[:12]}")
            if args.apply:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"      -> applied")
                copied += 1

    print(f"\n{'applied' if args.apply else 'would apply'} {copied} file(s)")
    if not args.apply:
        print("(re-run with --apply to write into the shared tree)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
