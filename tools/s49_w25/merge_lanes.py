#!/usr/bin/env python3
"""Three-way merge of several lane copies of the same file back into the shared tree.

`tools/s49_wave18/integrate.py` copies whole files, which silently loses work when
two lanes edit the same file (wave 25 has three lanes editing
`game/src/battle_runtime_scene.cpp`).  This helper does a real three-way merge:

    base   = the shared tree's current copy of the file
    ours   = lane A's copy
    theirs = lane B's copy

using `git merge-file`, applied pairwise for N lanes.  Conflicts are reported and
the merge is aborted (the shared tree is left untouched) unless `--force` is given.

Usage:
    python tools/s49_w25/merge_lanes.py --file game/src/battle_runtime_scene.cpp \
        --lane w25-h2 --lane w25-h3 --lane w25-h4 [--apply]

    # dry run (default): prints the merged file and any conflicts
    python tools/s49_w25/merge_lanes.py --file <rel> --lane ... --out <tmp>
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHARED = Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel")
LANE_ROOT = REPO / "build"


def merge_file(base: bytes, ours: bytes, theirs: bytes) -> tuple[str, bool]:
    """Three-way merge. `base` is the common ancestor and must stay constant
    across lanes; `ours` is the accumulated merge result so far."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "base").write_bytes(base)
        (tmp_path / "ours").write_bytes(ours)
        (tmp_path / "theirs").write_bytes(theirs)
        proc = subprocess.run(
            [
                "git",
                "merge-file",
                "-p",
                "-L",
                "ours",
                "-L",
                "base",
                "-L",
                "theirs",
                str(tmp_path / "ours"),
                str(tmp_path / "base"),
                str(tmp_path / "theirs"),
            ],
            capture_output=True,
        )
        out = proc.stdout.decode("utf-8", errors="replace")
        conflict = proc.returncode != 0
    return out, conflict


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="relative path inside the tree")
    ap.add_argument("--lane", action="append", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", help="write the merged result here instead of the shared tree")
    ap.add_argument("--shared", help="override the shared tree root (for testing)")
    ap.add_argument("--lane-root", help="override the lane root (for testing)")
    args = ap.parse_args()

    shared_root = Path(args.shared) if args.shared else SHARED
    lane_root = Path(args.lane_root) if args.lane_root else LANE_ROOT

    shared_file = shared_root / args.file
    if not shared_file.exists():
        print(f"shared file missing: {shared_file}")
        return 2

    base_bytes = shared_file.read_bytes()
    conflicts = False
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        work.mkdir()
        merged = work / "merged"
        merged.write_bytes(base_bytes)

        for lane in args.lane:
            lane_file = lane_root / lane / "butano-sequel" / args.file
            if not lane_file.exists():
                print(f"{lane}: no copy of {args.file} (skipping)")
                continue
            if lane_file.read_bytes() == merged.read_bytes():
                print(f"{lane}: identical to current merge (no change)")
                continue
            # base stays the shared tree's copy; ours is the accumulated merge
            text, conflict = merge_file(base_bytes, merged.read_bytes(), lane_file.read_bytes())
            print(f"{lane}: merged (conflict={conflict})")
            if conflict:
                conflicts = True
                marker = work / f"conflict-{lane}.txt"
                marker.write_text(text, encoding="utf-8")
                print(f"    conflict text -> {marker}")
                break
            merged.write_text(text, encoding="utf-8", newline="")

        if conflicts:
            print("\nABORT: conflicts detected, shared tree untouched.")
            return 2

        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(merged.read_bytes())
            print(f"wrote {out_path}")
        elif args.apply:
            shutil.copy2(merged, shared_file)
            print(f"applied {args.file} into the shared tree")
        else:
            print(f"\ndry run. {len(merged.read_bytes())} bytes would be written to {shared_file}")
            print("(re-run with --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
