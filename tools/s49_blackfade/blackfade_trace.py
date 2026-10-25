#!/usr/bin/env python3
"""Frame-exact trace of a key sequence, with a darkness profile per frame.

This is the instrument behind the black-field truth table.  It combines the
two facts measured in experiment W3-E1 (see
notes/s49-fidelity/W3-original-truth.md):

* ``frames 1 0`` advances the emulated game by exactly one frame,
* ``rawshot`` writes the core's video buffer without advancing it,

so a (frames, rawshot) pair captures exactly one GBA frame and the frame
number in the report is the true frame index inside the key's settle window.

Every frame is described by:

* ``mean`` / ``unique_colors`` / ``black_pct`` / ``dark_pct`` -- the darkness
  profile (this is what finds the black field),
* ``cursor`` / ``level`` -- the game's own state registers, read in the same
  frame (they say *which phase* the frame belongs to),
* the PNG is kept for the frames around a dark run, so the phase can be seen.

Usage::

    python tools/s49_blackfade/blackfade_trace.py \
        --out build/s49-blackfade/trace-a21 --keys "A*21" --settle 60
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
VICTORY = REPO / "tools" / "s49_victory_capture"
if str(VICTORY) not in sys.path:
    sys.path.insert(0, str(VICTORY))

import probe as probe_module  # noqa: E402

DEFAULT_EXE = REPO / "build" / "mgba-probe-w3" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")

ADDR_CURSOR = 0x02026A78
CURSOR_SPAN = 24
LEVEL_OFFSET = 0x02026A8C - ADDR_CURSOR

RAW_WIDTH = 240
RAW_HEIGHT = 160
DARK_THRESHOLD = 50.0     # percent of pixels with max(r,g,b) <= 32


def parse_keys(spec: str) -> list[str]:
    keys: list[str] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "*" in token:
            name, _, count = token.partition("*")
            keys.extend([name.strip()] * int(count))
        else:
            keys.append(token)
    return keys


def raw_to_png(raw: bytes, path: pathlib.Path) -> None:
    from PIL import Image
    image = Image.frombytes("RGBA", (RAW_WIDTH, RAW_HEIGHT), raw).convert("RGB")
    image.save(path)


def brightness(raw: bytes) -> dict:
    histogram: dict[tuple[int, int, int], int] = {}
    total = RAW_WIDTH * RAW_HEIGHT
    sum_r = sum_g = sum_b = 0
    black = 0
    dark = 0
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
                        default=REPO / "build" / "s49-blackfade" / "trace")
    parser.add_argument("--keys", required=True,
                        help="key sequence, e.g. 'A*21,Left*3,A'")
    parser.add_argument("--settle", type=int, default=60,
                        help="frames captured after every key press")
    parser.add_argument("--hold", type=int, default=4)
    parser.add_argument("--release", type=int, default=1)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    parser.add_argument("--keep-png", type=int, default=4)
    parser.add_argument("--png-every", type=int, default=0,
                        help="also keep a PNG every N frames (0 = only dark runs)")
    args = parser.parse_args(argv)

    out = args.out
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    scratch = out / "scratch.raw"

    keys = parse_keys(args.keys)
    rows: list[dict] = []
    pending: dict[int, bytes] = {}

    def capture_frame(probe, index: int) -> dict:
        probe.frames(1, 0)
        probe.run(f"rawshot {scratch}")
        raw = scratch.read_bytes()
        state = probe.dump(ADDR_CURSOR, CURSOR_SPAN)
        row = {"frame": index, "cursor": [state[0], state[1], state[2]],
               "level": state[LEVEL_OFFSET]}
        row.update(brightness(raw))
        return row

    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        index = 0
        for key_index, key in enumerate(keys):
            mask = probe_module.key_mask([key])
            probe.frames(args.hold, mask)
            probe.frames(args.release, 0)
            for _ in range(args.settle):
                row = capture_frame(probe, index)
                row["key"] = key
                row["key_index"] = key_index
                row["settle_frame"] = row["frame"] - rows[-1]["frame"] - 1 \
                    if rows else 0
                rows.append(row)
                index += 1

    # keep PNGs: every dark frame and its neighbourhood, plus optional sampling
    keep: set[int] = set()
    for row in rows:
        if row["dark_pct"] > DARK_THRESHOLD:
            for delta in range(-args.keep_png, args.keep_png + 1):
                candidate = row["frame"] + delta
                if 0 <= candidate < len(rows):
                    keep.add(candidate)
    if args.png_every:
        for row in rows:
            if row["frame"] % args.png_every == 0:
                keep.add(row["frame"])

    if keep:
        with probe_module.Probe(args.rom, exe=args.exe) as probe:
            probe.load(args.state)
            index = 0
            wanted = sorted(keep)
            for key_index, key in enumerate(keys):
                mask = probe_module.key_mask([key])
                probe.frames(args.hold, mask)
                probe.frames(args.release, 0)
                for _ in range(args.settle):
                    if index in wanted:
                        probe.run(f"rawshot {scratch}")
                        raw_to_png(scratch.read_bytes(),
                                   frames_dir / f"frame-{index:05d}.png")
                    else:
                        probe.frames(1, 0)
                    index += 1

    runs: list[list[dict]] = []
    current: list[dict] = []
    for row in rows:
        if row["dark_pct"] > DARK_THRESHOLD:
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
            "key_index": first["key_index"],
            "key": first["key"],
            "settle_frame": first["settle_frame"],
            "level": sorted({item["level"] for item in run}),
            "cursor": first["cursor"],
            "mean_first": first["mean"],
            "mean_last": last["mean"],
            "unique_colors_min": min(item["unique_colors"] for item in run),
            "unique_colors_max": max(item["unique_colors"] for item in run),
            "frames": [{"frame": item["frame"], "mean": item["mean"],
                        "dark_pct": item["dark_pct"],
                        "black_pct": item["black_pct"],
                        "unique_colors": item["unique_colors"],
                        "top_color": item["top_color"],
                        "level": item["level"]} for item in run],
        })

    document = {
        "schema": "konoha.s49-blackfade-trace.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "start_state": str(args.state),
        "start_state_sha256": sha256_file(args.state),
        "keys": keys,
        "settle": args.settle,
        "hold": args.hold,
        "release": args.release,
        "frames": len(rows),
        "dark_threshold_pct": DARK_THRESHOLD,
        "runs": run_rows,
        "frame_log": rows,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "trace.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")

    print(f"traced {len(rows)} frames, {len(run_rows)} dark run(s)")
    for run in run_rows:
        print(f"  frames {run['first_frame']}..{run['last_frame']} "
              f"({run['duration_frames']}f) key#{run['key_index']}({run['key']}) "
              f"settle_frame={run['settle_frame']} level={run['level']} "
              f"mean {run['mean_first']} -> {run['mean_last']} "
              f"colors {run['unique_colors_min']}..{run['unique_colors_max']}")
        for item in run["frames"]:
            print(f"    frame {item['frame']:5d}  mean={item['mean']} "
                  f"dark={item['dark_pct']}% black={item['black_pct']}% "
                  f"colors={item['unique_colors']} top={item['top_color']}")
    print("->", out / "trace.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
