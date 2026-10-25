#!/usr/bin/env python3
"""Frame-exact brightness scan of the original ROM's battle-14 entry.

Why this exists
---------------
Stream P found two black frames in the *original* (step-11 near-black,
step-18 pure black) and none at all in the remake's 35 frame walk, but it
could not say *where* in the game the original fades to black, nor whether the
fade is a single frame or a gradient.

This scanner answers that with the strongest instrument the probe has:

* ``frames 1 0`` advances the emulated game by **exactly one** frame,
* ``rawshot`` writes the core's video buffer **without** advancing it
  (measured: see notes/s49-fidelity/W3-original-truth.md, experiment W3-E1),

so one (frames, rawshot) pair == one frame, and the frame index in the report
is the true GBA frame index.  The state register (cursor + menu level) is read
in the same frame.

The scan is deliberately *passive*: no keys are pressed.  The battle-14 entry
savestate sits in the middle of the original's battle entry performance
(才会有「开始」标题 → 自动黑场 → 可见对白), so the fade shows up without any
input.

Usage::

    python tools/s49_blackfade/blackfade_scan.py \
        --out build/s49-blackfade/entry-scan --frames 900
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
# the probe client lives with the victory capture driver (same stream)
VICTORY = REPO / "tools" / "s49_victory_capture"
if str(VICTORY) not in sys.path:
    sys.path.insert(0, str(VICTORY))

import probe as probe_module  # noqa: E402

DEFAULT_EXE = REPO / "build" / "mgba-probe-w3" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")

# The aim / move cursor (x, y, active) and the menu level live 20 bytes apart.
ADDR_CURSOR = 0x02026A78
CURSOR_SPAN = 24          # covers 0x02026A78 .. 0x02026A8F
LEVEL_OFFSET = 0x02026A8C - ADDR_CURSOR

RAW_WIDTH = 240
RAW_HEIGHT = 160


def raw_to_png(raw: bytes, path: pathlib.Path) -> None:
    from PIL import Image
    image = Image.frombytes("RGBA", (RAW_WIDTH, RAW_HEIGHT), raw).convert("RGB")
    image.save(path)


def brightness(raw: bytes) -> dict:
    """Darkness profile of one rendered frame."""
    histogram: dict[tuple[int, int, int], int] = {}
    total = RAW_WIDTH * RAW_HEIGHT
    sum_r = sum_g = sum_b = 0
    black = 0          # max(r,g,b) <= 8
    dark = 0           # max(r,g,b) <= 32
    for index in range(0, total * 4, 4):
        r = raw[index]
        g = raw[index + 1]
        b = raw[index + 2]
        sum_r += r
        sum_g += g
        sum_b += b
        key = (r, g, b)
        histogram[key] = histogram.get(key, 0) + 1
        peak = r if r > g else g
        if b > peak:
            peak = b
        if peak <= 8:
            black += 1
        elif peak <= 32:
            dark += 1
    top = max(histogram.items(), key=lambda item: item[1])
    return {
        "mean": [round(sum_r / total, 3), round(sum_g / total, 3),
                 round(sum_b / total, 3)],
        "unique_colors": len(histogram),
        "black_pct": round(100.0 * black / total, 3),
        "dark_pct": round(100.0 * (black + dark) / total, 3),
        "top_color": list(top[0]),
        "top_color_pct": round(100.0 * top[1] / total, 3),
    }


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-blackfade" / "entry-scan")
    parser.add_argument("--frames", type=int, default=900,
                        help="number of frames to scan")
    parser.add_argument("--start-frame", type=int, default=0,
                        help="frames to run before the first capture")
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    parser.add_argument("--keep-png", type=int, default=4,
                        help="how many PNGs to keep around each dark frame")
    parser.add_argument("--raw", action="store_true",
                        help="keep the raw RGBA of every frame (big)")
    args = parser.parse_args(argv)

    out = args.out
    frames_dir = out / "frames"
    raw_dir = out / "raw"
    frames_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    scratch = out / "scratch.raw"

    rows: list[dict] = []
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        if args.start_frame:
            probe.frames(args.start_frame, 0)
        for index in range(args.frames):
            probe.frames(1, 0)
            probe.run(f"rawshot {scratch}")
            raw = scratch.read_bytes()
            state = probe.dump(ADDR_CURSOR, CURSOR_SPAN)
            row = {"frame": index, "cursor": [state[0], state[1], state[2]],
                   "level": state[LEVEL_OFFSET]}
            row.update(brightness(raw))
            rows.append(row)
            if args.raw:
                shutil.copyfile(scratch, raw_dir / f"frame-{index:05d}.raw")

    # keep PNGs around every dark frame so the phase can be eyeballed
    dark_indices = [row["frame"] for row in rows
                    if row["dark_pct"] > 50.0]
    keep: set[int] = set()
    for index in dark_indices:
        for delta in range(-args.keep_png, args.keep_png + 1):
            candidate = index + delta
            if 0 <= candidate < len(rows):
                keep.add(candidate)

    scratch_rows = {row["frame"]: row for row in rows}
    if keep:
        with probe_module.Probe(args.rom, exe=args.exe) as probe:
            probe.load(args.state)
            if args.start_frame:
                probe.frames(args.start_frame, 0)
            for index in sorted(keep):
                probe.frames(index + 1 - args.start_frame, 0)
                probe.run(f"rawshot {scratch}")
                raw_to_png(scratch.read_bytes(), frames_dir / f"frame-{index:05d}.png")

    # group the dark frames into runs
    runs = []
    current: list[dict] = []
    for row in rows:
        if row["dark_pct"] > 50.0:
            current.append(row)
            continue
        if current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)

    run_rows = []
    for run in runs:
        first, last = run[0], run[-1]
        run_rows.append({
            "first_frame": first["frame"],
            "last_frame": last["frame"],
            "duration_frames": last["frame"] - first["frame"] + 1,
            "mean": [round(sum(item["mean"][i] for item in run) / len(run), 3)
                     for i in range(3)],
            "dark_pct_min": min(item["dark_pct"] for item in run),
            "dark_pct_max": max(item["dark_pct"] for item in run),
            "unique_colors_min": min(item["unique_colors"] for item in run),
            "unique_colors_max": max(item["unique_colors"] for item in run),
            "level": sorted({item["level"] for item in run}),
            "frames": [{"frame": item["frame"], "mean": item["mean"],
                        "dark_pct": item["dark_pct"],
                        "unique_colors": item["unique_colors"],
                        "top_color": item["top_color"],
                        "level": item["level"]} for item in run],
        })

    document = {
        "schema": "konoha.s49-blackfade-scan.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "start_state": str(args.state),
        "start_state_sha256": sha256_file(args.state),
        "frames_scanned": len(rows),
        "start_frame": args.start_frame,
        "dark_threshold_pct": 50.0,
        "runs": run_rows,
        "frames": rows,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "scan.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")

    print(f"scanned {len(rows)} frames, {len(run_rows)} dark run(s)")
    for run in run_rows:
        print(f"  frames {run['first_frame']}..{run['last_frame']} "
              f"({run['duration_frames']}f) mean={run['mean']} "
              f"dark {run['dark_pct_min']}..{run['dark_pct_max']}% "
              f"colors {run['unique_colors_min']}..{run['unique_colors_max']} "
              f"level={run['level']}")
        for item in run["frames"]:
            print(f"    frame {item['frame']:5d}  mean={item['mean']} "
                  f"dark={item['dark_pct']}%  colors={item['unique_colors']} "
                  f"top={item['top_color']}")
    print("->", out / "scan.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
