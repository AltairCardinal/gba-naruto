#!/usr/bin/env python3
"""Capture the original's camera motion frame by frame, and turn it into a curve.

Why this tool exists
--------------------
`tools/s49_w20e/camera_delta.py` measured the *net* camera displacement
between two settled walk steps:

    original step-20 -> step-21 = (-40, +7)   (struct 0.6548)
    original step-21 -> step-22 = (-16, +9)   (struct 0.8061)

But the walk's steps are separated by ~94 emulator frames, and the camera
scrolls *continuously* inside that window.  A product fix has to reproduce the
**curve**, not the net value, so the net value alone is not enough to write
the fix.

This tool

  1. replays the original's own input timing from a walk savestate
     (A held for 4 frames, then 90 settle frames -- the same numbers
     `mgba_original_s49_ui_boundaries.lua` uses),
  2. screenshots **every frame** of that window with the probe's `shot`
     command,
  3. measures the per-frame displacement between consecutive dense frames by
     an integer translation search, and
  4. writes a machine readable curve.

Usage
-----
    python tools/s49_w20e/dense_camera_curve.py capture \
        --state build/.../capture-original/step-20-A.ss9 \
        --rom D:/Shell/Github/gba-naruto-butano/rom/base.gba \
        --exe build/mgba-probe-w20e3/mgba-probe.exe \
        --out-dir build/w20-e3/dense/step-20-to-21

    python tools/s49_w20e/dense_camera_curve.py analyze \
        --dense build/w20-e3/dense/step-20-to-21 \
        --out build/w20-e3/dense-camera-curve.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PROBE_CLIENT = os.path.join(REPO, "tools", "mgba_probe", "probe_client.py")

# The original's own input timing (mgba_original_s49_ui_boundaries.lua).
HOLD_FRAMES = 4
SETTLE_FRAMES = 90
GBA_KEY_A = 0x0001

FIELD_AREA = (0, 0, 240, 128)


def run_probe(exe: str, rom: str, commands: list[str], out: str) -> dict:
    argv = [sys.executable, PROBE_CLIENT, "--exe", exe, "--rom", rom]
    for command in commands:
        argv += ["--cmd", command]
    argv += ["--out", out]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=3600)
    if not os.path.isfile(out):
        raise RuntimeError(f"probe produced no output: {proc.stderr[:2000]}")
    with open(out, encoding="utf-8") as handle:
        document = json.load(handle)
    bad = [step for step in document["steps"] if step["status"] != "ok"]
    if bad:
        raise RuntimeError(f"probe step failed: {bad[0]['command']}: {bad[0]['output']}")
    return document


def capture(args) -> int:
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    commands = [f"load {os.path.abspath(args.state)}"]
    # frame 000 is the loaded state itself (no frame advance)
    commands.append(f"shot {os.path.join(out_dir, 'f000.png')}")
    # the A press: held for HOLD_FRAMES, exactly like the original's lua script
    commands.append(f"frames {HOLD_FRAMES} {GBA_KEY_A}")
    for index in range(1, SETTLE_FRAMES + 1):
        commands.append("frames 1 0")
        commands.append(f"shot {os.path.join(out_dir, f'f{index:03d}.png')}")
    print(f"capturing {SETTLE_FRAMES + 1} frames -> {out_dir}")
    run_probe(args.exe, args.rom, commands, os.path.join(out_dir, "probe.json"))
    print(f"wrote {len(os.listdir(out_dir)) - 1} frames")
    return 0


def shift_residual(original, remake, dx: int, dy: int):
    x0, y0, x1, y1 = FIELD_AREA
    ox0 = max(x0, x0 + dx)
    ox1 = min(x1, x1 + dx)
    oy0 = max(y0, y0 + dy)
    oy1 = min(y1, y1 + dy)
    if ox1 <= ox0 or oy1 <= oy0:
        return None, 0
    width = ox1 - ox0
    height = oy1 - oy0
    left = original.crop((ox0, oy0, ox1, oy1))
    right = remake.crop((ox0 - dx, oy0 - dy, ox1 - dx, oy1 - dy))
    count, _ = diff_mask(left, right, (0, 0, width, height))
    return count, width * height


def best_shift(original, remake, radius: int):
    best = None
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            count, area = shift_residual(original, remake, dx, dy)
            if count is None:
                continue
            if best is None or count < best[0]:
                best = (count, dx, dy, area)
    return best


def analyze(args) -> int:
    windows = []
    for entry in sorted(os.listdir(args.dense)):
        directory = os.path.join(args.dense, entry)
        if not os.path.isdir(directory):
            continue
        names = sorted(name for name in os.listdir(directory)
                       if name.startswith("f") and name.endswith(".png"))
        if len(names) < 2:
            continue
        images = [load_rgb(os.path.join(directory, name)) for name in names]
        points = []
        cumulative_x = 0
        cumulative_y = 0
        for index in range(len(images) - 1):
            best = best_shift(images[index], images[index + 1], args.radius)
            if best is None:
                continue
            count, dx, dy, area = best
            mismatch = count / area if area else 1.0
            cumulative_x += dx
            cumulative_y += dy
            points.append({
                "frame": names[index],
                "next_frame": names[index + 1],
                "dx": dx,
                "dy": dy,
                "residual_px": count,
                "overlap_px": area,
                "mismatch_ratio": round(mismatch, 4),
                "cumulative_dx": cumulative_x,
                "cumulative_dy": cumulative_y,
            })
        windows.append({
            "window": entry,
            "frames": len(names),
            "points": points,
            "net_dx": cumulative_x,
            "net_dy": cumulative_y,
            "moving_frames": [p["frame"] for p in points
                              if p["dx"] or p["dy"]],
        })
        print(f"{entry}: {len(names)} frames, net ({cumulative_x:+d}, {cumulative_y:+d}), "
              f"{len(windows[-1]['moving_frames'])} moving frames")

    document = {
        "schema": "konoha.s49-original-camera-curve.v1",
        "unit": "pixel",
        "radius": args.radius,
        "hold_frames": HOLD_FRAMES,
        "settle_frames": SETTLE_FRAMES,
        "windows": windows,
    }
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=1)
        print(f"wrote {args.out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture")
    cap.add_argument("--state", required=True)
    cap.add_argument("--rom", required=True)
    cap.add_argument("--exe", required=True)
    cap.add_argument("--out-dir", required=True)
    cap.set_defaults(func=capture)

    ana = sub.add_parser("analyze")
    ana.add_argument("--dense", required=True)
    ana.add_argument("--out", default=None)
    ana.add_argument("--radius", type=int, default=12)
    ana.set_defaults(func=analyze)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
