#!/usr/bin/env python3
"""Verify that two independent victory-capture runs are byte identical.

The original ROM is deterministic, so the same start savestate plus the same
driver must produce exactly the same frames.  This tool compares the two run
directories frame by frame and writes a machine readable receipt.

Usage::

    python tools/s49_victory_capture/w4_verify.py \
        --a build/s49-victory-capture/w4/victoryA \
        --b build/s49-victory-capture/w4/victoryB \
        --out build/s49-victory-capture/w4/verify.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--a", type=pathlib.Path, required=True)
    parser.add_argument("--b", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)

    frames_a = sorted((args.a / "frames").glob("frame-*.png"))
    frames_b = sorted((args.b / "frames").glob("frame-*.png"))
    names_a = [path.name for path in frames_a]
    names_b = [path.name for path in frames_b]

    only_a = sorted(set(names_a) - set(names_b))
    only_b = sorted(set(names_b) - set(names_a))
    differing = []
    for path_a, path_b in zip(frames_a, frames_b):
        if path_a.name != path_b.name:
            continue
        if sha256_file(path_a) != sha256_file(path_b):
            differing.append(path_a.name)

    play_a = json.loads((args.a / "play.json").read_text(encoding="utf-8"))
    play_b = json.loads((args.b / "play.json").read_text(encoding="utf-8"))

    receipt = {
        "schema": "konoha.s49-victory-verify-w4.v1",
        "a": str(args.a),
        "b": str(args.b),
        "frames_a": len(frames_a),
        "frames_b": len(frames_b),
        "only_in_a": only_a[:20],
        "only_in_b": only_b[:20],
        "differing_frames": differing[:20],
        "differing_count": len(differing),
        "stats_a": play_a.get("stats"),
        "stats_b": play_b.get("stats"),
        "identical": (not only_a and not only_b and not differing
                      and play_a.get("stats") == play_b.get("stats")),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
