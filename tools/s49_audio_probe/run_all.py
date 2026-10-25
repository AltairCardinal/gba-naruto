#!/usr/bin/env python3
"""Stream J: one command that reproduces the whole S49 audio-event comparison.

    python tools/s49_audio_probe/run_all.py --out build/s49-audio

Steps
-----
1. extract_original  -- capture the original ROM's MP2K cue sequence
                       (three probe runs: MP2K window, PSG window, and a
                       perturbation control) + the determinism control.
2. cue_census        -- which MP2K cue is live in every recorded savestate.
3. extract_remake    -- capture the remake ROM's sound/DMA register window and
                       parse the product code's cue table / dispatch sites.
4. compare_events    -- build the per-event difference table.

Everything is deterministic: two consecutive runs produce byte-identical
`original_events.json`, `remake_events.json`, `cue_census.json` and
`event_diff.json`.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]


def run(script: str, *args: str) -> None:
    command = [sys.executable, str(HERE / script), *args]
    print(f"\n=== {script} {' '.join(args)}")
    result = subprocess.run(command, cwd=str(REPO))
    if result.returncode != 0:
        raise SystemExit(f"ERR {script} failed with {result.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(REPO / "build" / "s49-audio"))
    parser.add_argument("--skip-capture", action="store_true",
                        help="re-decode the dumps already on disk")
    args = parser.parse_args()

    decode = ["--decode-only"] if args.skip_capture else []
    run("extract_original.py", "--out", args.out, *decode)
    run("cue_census.py", "--out", str(pathlib.Path(args.out) / "cue_census.json"))
    run("extract_remake.py", "--out", args.out, *decode)
    run("compare_events.py", "--out", args.out)
    print(f"\nall artifacts in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
