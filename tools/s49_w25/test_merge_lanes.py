#!/usr/bin/env python3
"""Self-test for tools/s49_w25/merge_lanes.py.

The wave-25 close-out merges three lanes that all touched
`game/src/battle_runtime_scene.cpp`.  `integrate.py` copies whole files and
would silently drop two of the three edits, so the three-way merge has to be
proven before it is used on the real tree.

This script builds a synthetic shared tree with one file, forks two lanes that
edit *different* regions of it, and asserts:

  1. both edits survive the merge,
  2. edits in the *same* region are reported as a conflict and the shared tree
     is left untouched (exit code 2),
  3. an unchanged lane is reported as "no change".

Usage:
    python tools/s49_w25/test_merge_lanes.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "s49_w25" / "merge_lanes.py"
REL = "game/src/fake.cpp"

BASE = """#include "x.h"

int alpha() { return 1; }

int beta() { return 2; }

int gamma() { return 3; }
"""


def build_tree(root: Path) -> Path:
    shared = root / "shared"
    (shared / "game" / "src").mkdir(parents=True)
    (shared / REL).write_text(BASE, encoding="utf-8")
    for lane, marker in (("laneA", "alpha"), ("laneB", "gamma")):
        lane_dir = root / "build" / lane / "butano-sequel" / "game" / "src"
        lane_dir.mkdir(parents=True)
        text = BASE.replace(f"int {marker}()", f"int {marker}_v2()")
        (lane_dir / "fake.cpp").write_text(text, encoding="utf-8")
    return shared


def run(shared: Path, lanes: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--file",
            REL,
            "--shared",
            str(shared),
            "--lane-root",
            str(shared.parent / "build"),
            "--out",
            str(shared.parent / "merged.cpp"),
        ]
        + [arg for lane in lanes for arg in ("--lane", lane)],
        capture_output=True,
        text=True,
    )


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shared = build_tree(root)

        # 1. disjoint edits -> both survive
        proc = run(shared, ["laneA", "laneB"])
        merged = (root / "merged.cpp").read_text(encoding="utf-8")
        if proc.returncode != 0:
            print(f"FAIL: merge exited {proc.returncode}\n{proc.stdout}{proc.stderr}")
            failures += 1
        for want in ("alpha_v2", "gamma_v2", "int beta() { return 2; }"):
            if want not in merged:
                print(f"FAIL: merged result lost {want!r}")
                failures += 1
        print("case 1 (disjoint edits):", "ok" if failures == 0 else "FAILED")

        # 2. conflicting edits -> reported, shared tree untouched
        conflict_lane = root / "build" / "laneC" / "butano-sequel" / "game" / "src"
        conflict_lane.mkdir(parents=True)
        (conflict_lane / "fake.cpp").write_text(
            BASE.replace("int alpha()", "int alpha_XYZ()"), encoding="utf-8"
        )
        before = (shared / REL).read_text(encoding="utf-8")
        proc = run(shared, ["laneA", "laneC"])
        after = (shared / REL).read_text(encoding="utf-8")
        if proc.returncode != 2:
            print(f"FAIL: conflicting merge should exit 2, got {proc.returncode}")
            failures += 1
        if before != after:
            print("FAIL: shared tree was modified despite the conflict")
            failures += 1
        print("case 2 (conflicting edits):", "ok" if failures == 0 else "FAILED")

        # 3. unchanged lane -> "no change"
        proc = run(shared, ["laneA", "laneA"])
        if "identical to current merge" not in proc.stdout:
            print("FAIL: an unchanged lane was not reported as identical")
            failures += 1
        print("case 3 (unchanged lane):", "ok" if failures == 0 else "FAILED")

    print("\n" + ("ALL PASS" if failures == 0 else f"{failures} FAILURE(S)"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
