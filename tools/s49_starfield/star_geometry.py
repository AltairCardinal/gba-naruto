#!/usr/bin/env python3
"""Extract the four pointed star's geometry from the original's frames.

The original's black field is a four pointed star shaped window that rotates
and shrinks.  This tool recovers, for every frame, the star's centre, the
angular position and radius of its four tips and the angular position and
radius of its four waists, so that the family of shapes can be described by
a handful of numbers instead of by pixels.

Usage::

    python tools/s49_starfield/star_geometry.py \
        --frames build/s49-blackfade/original-entry-v2/frames \
        --first 1013 --last 1036 --out build/s49-starfield/geometry-fadeout.json
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib

from PIL import Image

WIDTH = 240
HEIGHT = 160
ANGLES = 720


def star_mask(path: pathlib.Path) -> list[list[bool]]:
    """True where the picture is visible (the star's hole).

    The mask the original draws is pure black and is connected to the screen
    border, so the hole is what is left after a flood fill of the black
    region that touches the border.
    """
    image = Image.open(path).convert("RGB")
    pixels = image.load()
    black = [[pixels[x, y] == (0, 0, 0) for x in range(WIDTH)]
             for y in range(HEIGHT)]
    seen = [[False] * WIDTH for _ in range(HEIGHT)]
    stack = []
    for x in range(WIDTH):
        for y in (0, HEIGHT - 1):
            if black[y][x] and not seen[y][x]:
                seen[y][x] = True
                stack.append((x, y))
    for y in range(HEIGHT):
        for x in (0, WIDTH - 1):
            if black[y][x] and not seen[y][x]:
                seen[y][x] = True
                stack.append((x, y))
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (0 <= nx < WIDTH and 0 <= ny < HEIGHT and black[ny][nx]
                    and not seen[ny][nx]):
                seen[ny][nx] = True
                stack.append((nx, ny))
    return [[not seen[y][x] for x in range(WIDTH)] for y in range(HEIGHT)]


def centre_of(mask: list[list[bool]]) -> tuple[float, float]:
    sum_x = sum_y = count = 0
    for y, row in enumerate(mask):
        for x, on in enumerate(row):
            if on:
                sum_x += x
                sum_y += y
                count += 1
    if count == 0:
        return WIDTH / 2.0, HEIGHT / 2.0
    return sum_x / count, sum_y / count


def radius_profile(mask: list[list[bool]],
                   centre: tuple[float, float]) -> list[float]:
    cx, cy = centre
    profile = []
    for index in range(ANGLES):
        angle = 2.0 * math.pi * index / ANGLES
        dx, dy = math.cos(angle), math.sin(angle)
        radius = 0.0
        travelled = 0.0
        while travelled < 220.0:
            x = int(round(cx + dx * travelled))
            y = int(round(cy + dy * travelled))
            if x < 0 or x >= WIDTH or y < 0 or y >= HEIGHT:
                break
            if mask[y][x]:
                radius = travelled
            travelled += 0.25
        profile.append(radius)
    return profile


def extrema(profile: list[float]) -> tuple[list[tuple[float, float]],
                                           list[tuple[float, float]]]:
    """The four maxima (tips) and the four minima (waists) of the profile."""
    tips = []
    waists = []
    for index in range(ANGLES):
        before = profile[(index - 1) % ANGLES]
        here = profile[index]
        after = profile[(index + 1) % ANGLES]
        if here > before and here >= after:
            tips.append((360.0 * index / ANGLES, here))
        elif here < before and here <= after:
            waists.append((360.0 * index / ANGLES, here))
    # Merge plateaus: keep the strongest of every group of neighbours.
    def merge(entries):
        merged = []
        for angle, radius in entries:
            if merged and angle - merged[-1][0] < 6.0:
                if radius > merged[-1][1]:
                    merged[-1] = (angle, radius)
                continue
            merged.append((angle, radius))
        return merged

    tips = merge(tips)
    waists = merge(waists)
    return tips, waists


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--first", type=int, required=True)
    parser.add_argument("--last", type=int, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    directory = pathlib.Path(args.frames)
    rows = []
    for number in range(args.first, args.last + 1):
        path = directory / f"frame-{number:05d}.png"
        if not path.exists():
            continue
        mask = star_mask(path)
        centre = centre_of(mask)
        profile = radius_profile(mask, centre)
        tips, waists = extrema(profile)
        area = sum(sum(1 for on in row if on) for row in mask)
        rows.append({
            "frame": number,
            "centre": [round(centre[0], 2), round(centre[1], 2)],
            "area": area,
            "tips": [{"angle": round(a, 2), "radius": round(r, 2)}
                     for a, r in tips],
            "waists": [{"angle": round(a, 2), "radius": round(r, 2)}
                       for a, r in waists],
            "mean_radius": round(sum(profile) / len(profile), 3),
        })

    report = {
        "schema": "konoha.s49-star-geometry.v1",
        "frames_dir": str(directory),
        "angles": ANGLES,
        "frames": rows,
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")

    for row in rows:
        tips = " ".join(f"{t['angle']:.0f}/{t['radius']:.1f}" for t in row["tips"])
        waists = " ".join(f"{w['angle']:.0f}/{w['radius']:.1f}"
                          for w in row["waists"])
        print(f"{row['frame']} area={row['area']:6d} "
              f"c=({row['centre'][0]:.1f},{row['centre'][1]:.1f}) "
              f"tips[{tips}] waists[{waists}]")
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
