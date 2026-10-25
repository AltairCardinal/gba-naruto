#!/usr/bin/env python3
"""Group a captured frame directory into runs of pixel-identical frames.

Stream V4 (wave 9).  The settlement chain is a sequence of *screens*, and a
screen is a long run of identical frames (the original's 「勝利」 screen sits
still for thousands of frames; the remake's screens sit still too).  This
tool turns a frame directory into the run list, which is what the
settlement-chain comparison is built on.

The identity test is the **sha256 of the decoded RGB pixels**, not of the
PNG bytes: two PNGs of the same picture with different encoders must count
as one screen.

Usage::

    python tools/s49_victory_capture/v4_frame_runs.py \
        --frames build/s49-victory-capture/v4/remake-boot/frames \
        --out build/s49-victory-capture/v4/remake-boot/runs.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib


def pixel_sha(path: pathlib.Path) -> str:
    from PIL import Image
    with Image.open(path) as image:
        return hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()


def file_sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frames", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--min-run", type=int, default=1,
                        help="only report runs at least this long")
    parser.add_argument("--copy", type=pathlib.Path, default=None,
                        help="directory to copy the first frame of every run into")
    args = parser.parse_args(argv)

    files = sorted(args.frames.glob("frame-*.png"))
    if not files:
        raise SystemExit(f"ERR no frames under {args.frames}")

    runs: list[dict] = []
    previous = None
    start = 0
    for index, path in enumerate(files, 1):
        digest = pixel_sha(path)
        if digest != previous:
            if previous is not None:
                runs.append({"first": start, "last": index - 1,
                             "length": index - start, "pixel_sha256": previous,
                             "frame": files[start - 1].name})
            previous = digest
            start = index
    runs.append({"first": start, "last": len(files),
                 "length": len(files) - start + 1, "pixel_sha256": previous,
                 "frame": files[start - 1].name})

    if args.copy:
        args.copy.mkdir(parents=True, exist_ok=True)
        for run in runs:
            source = args.frames / run["frame"]
            target = args.copy / f"run-{run['first']:06d}-{run['last']:06d}.png"
            target.write_bytes(source.read_bytes())
            run["copy"] = str(target)

    document = {
        "schema": "konoha.s49-frame-runs.v1",
        "frames_dir": str(args.frames),
        "frames": len(files),
        "runs": runs,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=1, ensure_ascii=False)
                            + "\n", encoding="utf-8", newline="\n")
    for run in runs:
        if run["length"] >= args.min_run:
            print(f"{run['first']:6d}-{run['last']:6d} len={run['length']:5d} "
                  f"{run['pixel_sha256'][:16]} {run['frame']}")
    print(f"frames={len(files)} runs={len(runs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
