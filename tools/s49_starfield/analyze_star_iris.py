#!/usr/bin/env python3
"""Measure the original's black field: it is a rotating four pointed star.

What this tool answers
----------------------
The original's black field is not a brightness ramp (stream Y2's finding):
the picture stays at full brightness inside a four pointed star shaped
window, and that window shrinks towards the centre while it rotates.

This tool measures, for every frame of the original's fade-out / fade-in:

  * the visible (not covered) pixel count and the covered pixel count,
  * the star's centre,
  * the radial boundary profile r(theta) of the visible window,
  * whether the twelve levels are scaled and rotated copies of one shape
    (self similarity), and
  * the mean brightness curve, so two captures can be compared frame by
    frame.

The output is a JSON receipt plus a markdown table, so the remake's own
capture can be diffed against the original's curve by machine.

Usage::

    python tools/s49_starfield/analyze_star_iris.py \
        --frames build/s49-blackfade/original-entry-v2/frames \
        --out build/s49-starfield/original.json \
        --markdown build/s49-starfield/original.md
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib

from PIL import Image

WIDTH = 240
HEIGHT = 160
PROFILE_ANGLES = 72


def load_covered(path: pathlib.Path) -> list[list[bool]]:
    """True where the frame is covered by the black mask."""
    image = Image.open(path).convert("RGB")
    pixels = image.load()
    return [[pixels[x, y] == (0, 0, 0) for x in range(WIDTH)]
            for y in range(HEIGHT)]


def load_visible(path: pathlib.Path) -> list[list[bool]]:
    """True where the frame shows the picture (not pure black)."""
    image = Image.open(path).convert("RGB")
    pixels = image.load()
    visible = []
    for y in range(HEIGHT):
        row = []
        for x in range(WIDTH):
            red, green, blue = pixels[x, y]
            row.append(red > 8 or green > 8 or blue > 8)
        visible.append(row)
    return visible


def mean_rgb(path: pathlib.Path) -> list[float]:
    image = Image.open(path).convert("RGB")
    total = WIDTH * HEIGHT
    sum_r = sum_g = sum_b = 0
    for red, green, blue in image.get_flattened_data():
        sum_r += red
        sum_g += green
        sum_b += blue
    return [round(sum_r / total, 3), round(sum_g / total, 3),
            round(sum_b / total, 3)]


def centroid(visible: list[list[bool]]) -> tuple[float, float]:
    sum_x = sum_y = count = 0
    for y, row in enumerate(visible):
        for x, on in enumerate(row):
            if on:
                sum_x += x
                sum_y += y
                count += 1
    if count == 0:
        return WIDTH / 2.0, HEIGHT / 2.0
    return sum_x / count, sum_y / count


def radial_profile(visible: list[list[bool]],
                   centre: tuple[float, float]) -> list[float]:
    """Distance from the centre to the last visible pixel, per angle."""
    cx, cy = centre
    profile = []
    for index in range(PROFILE_ANGLES):
        angle = 2.0 * math.pi * index / PROFILE_ANGLES
        dx = math.cos(angle)
        dy = math.sin(angle)
        radius = 0.0
        step = 0.25
        travelled = 0.0
        while travelled < 200.0:
            x = int(round(cx + dx * travelled))
            y = int(round(cy + dy * travelled))
            if x < 0 or x >= WIDTH or y < 0 or y >= HEIGHT:
                break
            if visible[y][x]:
                radius = travelled
            travelled += step
        profile.append(round(radius, 2))
    return profile


def self_similarity(profiles: list[list[float]]) -> dict:
    """Are the levels scaled (and rotated) copies of the first level?"""
    if len(profiles) < 2:
        return {"comparable": False}
    base = profiles[0]
    base_mean = sum(base) / len(base)
    base_peak = max(base)
    rows = []
    for index, profile in enumerate(profiles):
        mean = sum(profile) / len(profile)
        peak = max(profile)
        # Best rotation: try every angle shift, keep the smallest residual.
        best_shift = 0
        best_error = None
        for shift in range(PROFILE_ANGLES):
            total = 0.0
            for position in range(PROFILE_ANGLES):
                a = base[position]
                b = profile[(position + shift) % PROFILE_ANGLES]
                total += (a - b) ** 2
            error = math.sqrt(total / PROFILE_ANGLES)
            if best_error is None or error < best_error:
                best_error = error
                best_shift = shift
        rows.append({
            "level": index,
            "mean_radius": round(mean, 2),
            "peak_radius": round(peak, 2),
            "scale_vs_base": round(mean / base_mean, 4) if base_mean else None,
            "best_rotation_deg": round(360.0 * best_shift / PROFILE_ANGLES, 1),
            "rms_error": round(best_error, 2) if best_error is not None else None,
        })
    return {"comparable": True, "levels": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown", default="")
    parser.add_argument("--first", type=int, default=0,
                        help="first frame number of the fade (0 = auto)")
    parser.add_argument("--last", type=int, default=0)
    args = parser.parse_args(argv)

    directory = pathlib.Path(args.frames)
    paths = sorted(directory.glob("frame-*.png"))
    if not paths:
        raise SystemExit(f"no frames in {directory}")

    first = args.first or int(paths[0].stem.split("-")[1])
    last = args.last or int(paths[-1].stem.split("-")[1])

    rows = []
    profiles = []
    for number in range(first, last + 1):
        path = directory / f"frame-{number:05d}.png"
        if not path.exists():
            continue
        visible = load_visible(path)
        covered = load_covered(path)
        visible_count = sum(sum(1 for on in row if on) for row in visible)
        covered_count = sum(sum(1 for on in row if on) for row in covered)
        centre = centroid(visible)
        profile = radial_profile(visible, centre)
        profiles.append(profile)
        rows.append({
            "frame": number,
            "name": path.name,
            "mean": mean_rgb(path),
            "visible_pixels": visible_count,
            "covered_pixels": covered_count,
            "visible_ratio": round(visible_count / (WIDTH * HEIGHT), 5),
            "covered_ratio": round(covered_count / (WIDTH * HEIGHT), 5),
            "centre": [round(centre[0], 2), round(centre[1], 2)],
            "mean_radius": round(sum(profile) / len(profile), 2),
            "peak_radius": round(max(profile), 2),
        })

    report = {
        "schema": "konoha.s49-star-iris.v1",
        "frames_dir": str(directory),
        "first_frame": rows[0]["frame"] if rows else None,
        "last_frame": rows[-1]["frame"] if rows else None,
        "frame_count": len(rows),
        "screen": [WIDTH, HEIGHT],
        "profile_angles": PROFILE_ANGLES,
        "frames": rows,
        "self_similarity": self_similarity(profiles),
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")

    if args.markdown:
        lines = [
            "| frame | mean r | visible px | visible % | centre | mean r_rad |",
            "|---:|---:|---:|---:|---|---:|",
        ]
        for row in rows:
            lines.append(
                f"| {row['frame']} | {row['mean'][0]:.3f} | "
                f"{row['visible_pixels']} | "
                f"{100.0 * row['visible_ratio']:.2f} | "
                f"({row['centre'][0]:.1f},{row['centre'][1]:.1f}) | "
                f"{row['mean_radius']:.2f} |")
        pathlib.Path(args.markdown).write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    for row in rows:
        print(f"{row['frame']} mean={row['mean'][0]:8.3f} "
              f"visible={row['visible_pixels']:6d} "
              f"({100.0 * row['visible_ratio']:5.2f}%) "
              f"centre=({row['centre'][0]:6.2f},{row['centre'][1]:6.2f}) "
              f"r_mean={row['mean_radius']:6.2f} r_peak={row['peak_radius']:6.2f}")
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
