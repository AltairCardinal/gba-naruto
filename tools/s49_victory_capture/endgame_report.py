#!/usr/bin/env python3
"""Summarise the captured victory / settlement frames.

The endgame capture writes one PNG every N frames.  This script groups the
frames into *scenes* (runs of byte identical frames), reports the sha256 of
every scene's first frame and the pixel difference between two consecutive
scenes, and writes the result as JSON -- that is the receipt of the
settlement screen truth.

Usage::

    python tools/s49_victory_capture/endgame_report.py \
        --frames build/s49-victory-capture/run/endgame --out build/s49-victory-capture/run/endgame.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

from PIL import Image


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def diff(left: pathlib.Path, right: pathlib.Path) -> int:
    a = Image.open(left).convert("RGB")
    b = Image.open(right).convert("RGB")
    if a.size != b.size:
        return -1
    pixels_a = a.get_flattened_data()
    pixels_b = b.get_flattened_data()
    return sum(1 for x, y in zip(pixels_a, pixels_b) if x != y)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    directory = pathlib.Path(args.frames)
    frames = sorted(directory.glob("*.png"))
    if not frames:
        raise SystemExit(f"no frames in {directory}")

    rows = []
    for path in frames:
        rows.append({"name": path.name, "sha256": sha256(path),
                     "bytes": path.stat().st_size})

    scenes = []
    for index, row in enumerate(rows):
        if scenes and scenes[-1]["sha256"] == row["sha256"]:
            scenes[-1]["frames"].append(row["name"])
            scenes[-1]["last_frame"] = row["name"]
            continue
        scenes.append({"sha256": row["sha256"], "first_frame": row["name"],
                       "last_frame": row["name"], "frames": [row["name"]],
                       "bytes": row["bytes"]})

    for scene in scenes:
        first = directory / scene["first_frame"]
        previous = directory / scenes[scenes.index(scene) - 1]["first_frame"] \
            if scenes.index(scene) > 0 else None
        scene["pixel_diff_to_previous"] = diff(previous, first) if previous else 0

    document = {
        "schema": "konoha.s49-endgame-report.v1",
        "frames_dir": str(directory),
        "frame_count": len(rows),
        "scene_count": len(scenes),
        "frames": rows,
        "scenes": scenes,
    }
    pathlib.Path(args.out).write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")

    print(f"frames {len(rows)}  scenes {len(scenes)}")
    for index, scene in enumerate(scenes):
        print(f"  scene {index:02d}  {scene['first_frame']} .. {scene['last_frame']}"
              f"  ({len(scene['frames'])} frames)  sha256 {scene['sha256'][:16]}..."
              f"  diff_to_prev {scene['pixel_diff_to_previous']}")
    print("-> ", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
