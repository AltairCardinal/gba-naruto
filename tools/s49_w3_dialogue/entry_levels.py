"""W3: the original's entry transition, as a table of levels.

The black field of the original's battle entry is a four pointed star shaped
window that shrinks, holds black and grows again.  Z2 modelled 25 levels of
it (12 out, 1 black, 12 in) and stopped there; the original keeps growing
after the last of them, which is what the dialogue box's entry transition
actually shows.

This probe measures the visible window of every GBA frame of the transition
and folds the frames into levels (a level is the run of frames that share
the same visible area), so the level table is measured, not assumed.

    python tools/s49_w3_dialogue/entry_levels.py \
        --frames build/s49-blackfade/original-entry-v2/frames \
        --first 1000 --last 1160 --out build/s49_w3_dialogue/entry-levels.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "s49_starfield"))

from star_geometry import star_mask  # noqa: E402  (shared, read only)

WIDTH = 240
HEIGHT = 160


def visible_area(path: pathlib.Path) -> int:
    mask = star_mask(path)
    return sum(sum(1 for on in row if on) for row in mask)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", required=True)
    parser.add_argument("--first", type=int, default=1000)
    parser.add_argument("--last", type=int, default=1160)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    directory = pathlib.Path(args.frames)
    levels = []
    current = None
    for number in range(args.first, args.last + 1):
        path = directory / f"frame-{number:05d}.png"
        if not path.exists():
            break
        area = visible_area(path)
        if current is None or current["area"] != area:
            if current is not None:
                current["frames"] = number - current["first_frame"]
                levels.append(current)
            current = {
                "first_frame": number,
                "frames": 0,
                "area": area,
            }
    if current is not None:
        current["frames"] = args.last + 1 - current["first_frame"]
        levels.append(current)

    for index, level in enumerate(levels):
        level["level"] = index
        print(f"level {index:3d} frames {level['first_frame']:5d}"
              f"..{level['first_frame'] + level['frames'] - 1:5d} "
              f"({level['frames']:2d} frames) area={level['area']:6d} "
              f"({level['area'] * 100 // (WIDTH * HEIGHT):3d}%)")

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "schema": "konoha.s49-entry-levels.v1",
        "frames_dir": str(directory),
        "levels": levels,
    }, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
