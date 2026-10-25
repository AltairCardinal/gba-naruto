#!/usr/bin/env python3
"""Cluster the original's settlement-chain frames into distinct screens.

Stream U3 (wave 10).  The original's settlement chain was recorded by wave 8's
W4 stream (``build/s49-victory-capture/w4/settlementA/frames``, 29,700 frames,
the recorder starts when the battle result byte turns to 1).

This tool answers one yes/no question per run:

    *Which distinct screens does the original's settlement chain contain, and
     in what order?*

It hashes every frame's raw pixels, groups consecutive identical frames into
runs, and then merges runs that are the same screen shown again later (the
original re-shows a screen between two page flips).  The result is the
**ground truth chain** the remake's chain has to match.

Usage::

    python tools/s49_u3_settlement/u3_cluster_truth.py \
        --frames build/s49-victory-capture/w4/settlementA/frames \
        --out build/s49-u3-settlement/truth-chain.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys


def frame_paths(frames_dir: pathlib.Path) -> list[pathlib.Path]:
    return sorted(frames_dir.glob("frame-*.png"))


def hash_png(path: pathlib.Path) -> str:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()
    except Exception:  # pragma: no cover - fallback for missing PIL
        return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frames", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--sample", type=int, default=1,
                        help="hash every Nth frame (1 = every frame)")
    args = parser.parse_args(argv)

    paths = frame_paths(args.frames)
    if not paths:
        print(f"ERR no frames under {args.frames}")
        return 2

    digests: list[str] = []
    for index, path in enumerate(paths):
        if index % args.sample:
            digests.append("")
            continue
        digests.append(hash_png(path))
        if index % 2000 == 0:
            print(f"  hashed {index}/{len(paths)}", file=sys.stderr)

    runs: list[dict] = []
    for index, digest in enumerate(digests):
        if not digest:
            continue
        if runs and runs[-1]["sha256"] == digest:
            runs[-1]["end"] = index + 1
            continue
        runs.append({
            "start": index + 1,
            "end": index + 1,
            "sha256": digest,
            "file": paths[index].name,
        })

    # The original re-shows a screen between page flips; merge runs whose
    # pixels are identical to the previous *screen* (not merely the previous
    # run) so the chain reads as a list of distinct screens.
    screens: list[dict] = []
    for run in runs:
        if screens and screens[-1]["sha256"] == run["sha256"]:
            screens[-1]["last_end"] = run["end"]
            continue
        screens.append({
            "index": len(screens) + 1,
            "sha256": run["sha256"],
            "first_frame": run["start"],
            "last_end": run["end"],
            "file": run["file"],
        })

    document = {
        "schema": "konoha.s49-u3-truth-chain.v1",
        "frames_dir": str(args.frames),
        "frames_total": len(paths),
        "sample": args.sample,
        "runs": len(runs),
        "screens": screens,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=1, ensure_ascii=False)
                            + "\n", encoding="utf-8", newline="\n")

    print(f"frames={len(paths)} runs={len(runs)} distinct_screens={len(screens)}")
    for screen in screens:
        print(f"  #{screen['index']:>2} frames {screen['first_frame']:>6}.."
              f"{screen['last_end']:<6} {screen['sha256'][:16]} {screen['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
