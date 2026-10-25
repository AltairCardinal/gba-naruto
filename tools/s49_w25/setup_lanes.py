#!/usr/bin/env python3
"""Create the wave-25 lane copies of the remake tree.

Every wave-25 stream works in its own copy so that concurrent builds cannot
overwrite each other's `butano-sequel.gba` (AGENTS.md instrument rule 9).

Hard rules baked into this script:

* `graphics/` is a **real directory**, never a symlink into the shared tree.
  Wave 24 / G3 lost three settlement assets because the lane's `graphics/`
  was a symlink and the patch went straight into the shared tree.
* `audio/` may be a symlink (no stream touches audio).
* `benchmark/` **must** be copied: the Makefile lists `benchmark/src` in
  SOURCES, and a lane without it cannot link `main.cpp`.
* The shared tree is read-only for the whole wave.

Usage:
    python tools/s49_w25/setup_lanes.py                       # create all four
    python tools/s49_w25/setup_lanes.py --lane w25-h2         # create one
    python tools/s49_w25/setup_lanes.py --force                # recreate
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHARED = Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel")
LANE_ROOT = REPO / "build"

LANES = {
    "w25-h1": "intro-block forensics",
    "w25-h2": "entry transition (R-G1-A/B/C)",
    "w25-h3": "prepare box wiring",
    "w25-h4": "4bpp L2 overlay palette",
}

# directories that are copied as real trees
COPY_DIRS = ["src", "game", "graphics", "benchmark"]
LINK_DIRS = ["audio"]


def lane_drift(lane: Path) -> list[str]:
    """Relative paths whose content in the lane differs from the shared tree."""
    drift: list[str] = []
    for base in ("game", "graphics", "src", "benchmark"):
        root = lane / base
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(lane)
            shared = SHARED / rel
            if not shared.exists() or shared.read_bytes() != path.read_bytes():
                drift.append(rel.as_posix())
    return drift


def make_lane(name: str, force: bool, force_confirmed: bool = False) -> Path:
    lane = LANE_ROOT / name / "butano-sequel"
    if lane.exists():
        if not force:
            print(f"{name}: lane already exists, keeping it ({lane})")
            return lane
        # 2026-10-26: `--force` wiped a lane that a running stream had already
        # edited.  Refuse unless the lane still matches the shared tree, so a
        # recreation can never silently discard a stream's work.
        drift = lane_drift(lane)
        if drift and not force_confirmed:
            raise SystemExit(
                f"{name}: lane differs from the shared tree in {len(drift)} file(s):\n"
                + "\n".join(f"    {rel}" for rel in drift[:20])
                + "\nRefusing to recreate. Pass --force-confirm if this is intended."
            )
        shutil.rmtree(lane)
    lane.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SHARED / "Makefile", lane / "Makefile")
    for d in COPY_DIRS:
        shutil.copytree(SHARED / d, lane / d)
    for d in LINK_DIRS:
        try:
            (lane / d).symlink_to(SHARED / d, target_is_directory=True)
        except OSError:
            shutil.copytree(SHARED / d, lane / d)
    print(f"{name}: created {lane}")
    return lane


def verify(lane: Path) -> None:
    gfx = lane / "graphics"
    files = sum(1 for p in gfx.rglob("*") if p.is_file())
    print(
        f"  graphics: files={files} is_symlink={gfx.is_symlink()} "
        f"benchmark={(lane / 'benchmark').is_dir()} "
        f"audio_is_link={(lane / 'audio').is_symlink()}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", action="append", default=[])
    ap.add_argument("--force", action="store_true")
    ap.add_argument(
        "--force-confirm",
        action="store_true",
        help="recreate a lane even though it differs from the shared tree",
    )
    args = ap.parse_args()

    names = args.lane or list(LANES)
    for name in names:
        if name not in LANES:
            raise SystemExit(f"unknown lane {name}; known: {sorted(LANES)}")
        lane = make_lane(name, args.force, args.force_confirm)
        verify(lane)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
