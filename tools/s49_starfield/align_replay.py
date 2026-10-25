#!/usr/bin/env python3
"""Align a probe replay against the project's own frame capture.

Why
---
The original's black field capture (tools/s49_blackfade/blackfade_capture.py)
replays a key schedule inside the emulator's Lua frame callback.  A replay
driven from the outside (the probe's ``frames`` command) does not advance the
emulator in exactly the same way, so the frame numbers of the two runs are
offset by an unknown amount.

This tool finds that offset: it replays the key schedule with the probe,
screenshots every N frames and matches each screenshot against the stored
capture, then reports the offset that reproduces the capture.

The offset is what makes the GPU probe (probe_original_mask.py) trustworthy:
with the offset known, the register dump can be taken at the exact frame of
the star mask.

Usage::

    python tools/s49_starfield/align_replay.py \
        --frames build/s49-blackfade/original-entry-v2/frames \
        --out build/s49-starfield/alignment.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
VICTORY = REPO / "tools" / "s49_victory_capture"
if str(VICTORY) not in sys.path:
    sys.path.insert(0, str(VICTORY))

import probe as probe_module  # noqa: E402

from PIL import Image  # noqa: E402

DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")
DEFAULT_EXE = REPO / "build" / "mgba-probe-z2" / "mgba-probe.exe"

KEY_STEP = 94
KEY_HOLD = 4
KEY_GAP = 90


def mean_red(path: pathlib.Path) -> float:
    image = Image.open(path).convert("RGB")
    total = 240 * 160
    return sum(pixel[0] for pixel in image.get_flattened_data()) / total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--from-frame", type=int, default=900)
    parser.add_argument("--to-frame", type=int, default=1300)
    parser.add_argument("--step", type=int, default=20)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    args = parser.parse_args(argv)

    frames_dir = pathlib.Path(args.frames)
    reference = {}
    for path in sorted(frames_dir.glob("frame-*.png")):
        reference[int(path.stem.split("-")[1])] = mean_red(path)

    work = pathlib.Path(args.out).with_suffix(".shots")
    work.mkdir(parents=True, exist_ok=True)

    mask_a = probe_module.key_mask(["A"])
    samples = []
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        probe.frames(1, 0)
        frame = 1
        while frame < args.from_frame:
            probe.frames(KEY_HOLD, mask_a)
            frame += KEY_HOLD
            probe.frames(KEY_GAP, 0)
            frame += KEY_GAP
        while frame <= args.to_frame:
            shot = work / f"shot-{frame:05d}.png"
            if not shot.exists():
                probe.shot(str(shot))
            samples.append((frame, mean_red(shot)))
            probe.frames(args.step, 0)
            frame += args.step

    rows = []
    for frame, value in samples:
        best = min(reference.items(), key=lambda item: abs(item[1] - value))
        rows.append({
            "replay_frame": frame,
            "mean_red": round(value, 3),
            "closest_reference_frame": best[0],
            "closest_reference_mean": best[1],
            "offset": best[0] - frame,
        })

    report = {
        "schema": "konoha.s49-replay-alignment.v1",
        "rows": rows,
    }
    out = pathlib.Path(args.out)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    for row in rows:
        print("replay %5d mean=%8.3f -> reference %5d mean=%8.3f offset=%+d"
              % (row["replay_frame"], row["mean_red"],
                 row["closest_reference_frame"], row["closest_reference_mean"],
                 row["offset"]))
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
