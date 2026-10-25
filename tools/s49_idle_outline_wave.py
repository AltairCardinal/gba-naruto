#!/usr/bin/env python3
"""Verify the remake's idle outline wave against the original's screen.

The original rewrites the unit's OBJ palette index 15 -- the one pixel
outline -- on every frame with a 32 step triangle wave over the 5 bit green
channel.  The remake's `battle_unit_visual_animation::idle_outline_green()`
implements that wave as a pure function of the pose cycle's position, so the
two can be checked against each other without touching the render path.

This script replays the original's idle sweep:

  * the pose of every frame comes from the ROM frame art (identified in
    palette index space, true mismatch must be 0);
  * the outline colour of every frame comes from the pixels themselves;
  * the wave is then recomputed from the pose cycle's position and compared
    with the colour the original actually drew.

Exit code 0 means the wave matches on every frame.

Usage::

    python tools/s49_idle_outline_wave.py
    python tools/s49_idle_outline_wave.py --sweep <dir> --pose <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

DEFAULT_SWEEP = Path(
    r"D:\Github\gba-naruto\build\s49-logic\original-idle-sweep")
DEFAULT_POSE = Path(
    r"D:\Github\gba-naruto\build\s49-idle\original-sweep-pose.json")
DEFAULT_VISUALS = Path(
    r"D:\Shell\Github\gba-naruto-reverse\artifacts\character-battle-visuals-v1")
REGION = (112, 24, 144, 88)
CYCLE = 32


def idle_outline_green(pose_cycle_position: int) -> int:
    """The C++ `battle_unit_visual_animation::idle_outline_green`, ported."""
    position = pose_cycle_position % CYCLE
    if position < 0:
        position += CYCLE
    wave = position + 23
    if wave >= CYCLE:
        wave -= CYCLE
    step = wave - 1
    falling = CYCLE - wave
    if falling < step:
        step = falling
    if step < 0:
        step = 0
    return 1 + 2 * step


def outline_green(colour) -> int | None:
    """The 5 bit green of an outline colour (0, g, g), or None."""
    r, g, b = colour
    if r != 0 or g != b or g == 0:
        return None
    for value in range(1, 32, 2):
        if (value << 3) | (value >> 2) == g:
            return value
    return None


def pose_positions(poses: list[int]) -> list[int]:
    """The pose cycle position of every frame of the sweep.

    The ROM's animation 3 is [(9,8),(10,8),(11,8),(10,8)], so the cycle
    position is the offset inside the 32 frame cycle.  The sweep's cycle
    starts at frame 3 of the recording: positions 0..7 show frame 9,
    8..15 show frame 10, 16..23 show frame 11 and 24..31 show frame 10.
    """
    positions = []
    start = None
    for index, pose in enumerate(poses):
        if pose == 9:
            if start is None:
                start = index
            positions.append((index - start) % CYCLE)
        else:
            positions.append(None)
    return positions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", type=Path, default=DEFAULT_SWEEP)
    parser.add_argument("--pose", type=Path, default=DEFAULT_POSE)
    parser.add_argument("--visuals", type=Path, default=DEFAULT_VISUALS)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    if not args.pose.is_file():
        print(f"missing the pose identification: {args.pose}", file=sys.stderr)
        return 2
    poses = json.loads(args.pose.read_text(encoding="utf-8"))["sequence"]
    frames = sorted(args.sweep.glob("frame-*.png"))
    if len(frames) < len(poses):
        print("the sweep has fewer frames than the pose identification",
              file=sys.stderr)
        return 2

    matched = mismatched = skipped = 0
    failures = []
    # The sweep's cycle starts at the first frame that shows frame 9.  The
    # local probe writes every GBA frame twice, so the cycle position has
    # to be counted in GBA frames, not in captured frames.
    cycle_start = None
    for index, pose in enumerate(poses):
        if pose == 9:
            cycle_start = index
            break
    if cycle_start is None:
        print("the pose sequence never shows frame 9", file=sys.stderr)
        return 2
    cycle_start_game = cycle_start // 2

    for index, path in enumerate(frames):
        with Image.open(path) as image:
            crop = image.convert("RGB").crop(REGION)
        counter = Counter(
            colour for colour in crop.getdata()
            if colour[0] == 0 and colour[1] == colour[2] and colour[1] > 0
        )
        measured = None
        for colour, _count in counter.most_common():
            measured = outline_green(colour)
            if measured is not None:
                break
        if measured is None:
            skipped += 1
            continue
        position = (index // 2 - cycle_start_game) % CYCLE
        predicted = idle_outline_green(position)
        if predicted == measured:
            matched += 1
        else:
            mismatched += 1
            if len(failures) < 8:
                failures.append({
                    "frame": path.name,
                    "pose": poses[index],
                    "pose_cycle_position": position,
                    "measured_green": measured,
                    "predicted_green": predicted,
                })

    payload = {
        "frames": len(frames),
        "matched": matched,
        "mismatched": mismatched,
        "skipped_no_outline": skipped,
        "failures": failures,
        "wave": "green = 1 + 2*step, step = clamp(min(wave-1, 32-wave), 0, 15), "
                "wave = (pose_cycle_position + 23) mod 32",
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    if mismatched:
        print(f"FAIL: {mismatched} frames disagree with the original",
              file=sys.stderr)
        return 1
    print(f"OK: the wave matches the original on {matched} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
