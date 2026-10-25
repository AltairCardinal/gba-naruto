#!/usr/bin/env python3
"""Find the **stable** screens of the original's settlement chain.

Stream U3 (wave 10).  The original's settlement chain was recorded by wave 8's
W4 stream (``build/s49-victory-capture/w4/settlementA/frames``).  Every frame
is hashed and consecutive identical frames become a *run*; a run that is at
least ``--min-run`` frames long is a **stable screen** (the original holds a
screen while it waits for the A button, and the short runs in between are the
page-flip animations).

This answers one yes/no question per run:

    *Which screens does the original's settlement chain contain, in what
     order, and how long does each one hold?*

Usage::

    python tools/s49_u3_settlement/u3_stable_screens.py \
        --frames build/s49-victory-capture/w4/settlementA/frames \
        --out build/s49-u3-settlement/stable-screens.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys


def hash_png(path: pathlib.Path) -> str:
    from PIL import Image

    with Image.open(path) as image:
        return hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frames", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--min-run", type=int, default=120,
                        help="a run at least this long is a stable screen")
    parser.add_argument("--from", dest="first", type=int, default=1)
    parser.add_argument("--to", dest="last", type=int, default=0,
                        help="0 = the last frame")
    parser.add_argument("--extract", type=pathlib.Path, default=None,
                        help="copy one PNG per stable screen into this folder")
    args = parser.parse_args(argv)

    paths = sorted(args.frames.glob("frame-*.png"))
    if not paths:
        print(f"ERR no frames under {args.frames}")
        return 2
    last = args.last or len(paths)

    runs: list[dict] = []
    for index, path in enumerate(paths):
        if index < args.first - 1:
            continue
        if index >= last:
            break
        digest = hash_png(path)
        if runs and runs[-1]["sha256"] == digest:
            runs[-1]["end"] = index + 1
            continue
        runs.append({"start": index + 1, "end": index + 1,
                     "sha256": digest, "file": path.name})
        if index % 2000 == 0:
            print(f"  hashed {index}/{len(paths)}", file=sys.stderr)

    stable = [run for run in runs
              if (run["end"] - run["start"] + 1) >= args.min_run]

    document = {
        "schema": "konoha.s49-u3-stable-screens.v1",
        "frames_dir": str(args.frames),
        "runs": len(runs),
        "min_run": args.min_run,
        "stable_screens": stable,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=1, ensure_ascii=False)
                            + "\n", encoding="utf-8", newline="\n")

    print(f"runs={len(runs)} stable(min_run={args.min_run})={len(stable)}")
    for index, run in enumerate(stable):
        print(f"  #{index + 1:>2} frames {run['start']:>6}..{run['end']:<6} "
              f"len={run['end'] - run['start'] + 1:<6} "
              f"{run['sha256'][:16]} {run['file']}")

    if args.extract:
        import shutil

        args.extract.mkdir(parents=True, exist_ok=True)
        for index, run in enumerate(stable):
            source = args.frames / run["file"]
            target = args.extract / f"screen-{index + 1:02d}-f{run['start']}.png"
            shutil.copyfile(source, target)
        print(f"extracted {len(stable)} screens to {args.extract}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
