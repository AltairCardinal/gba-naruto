#!/usr/bin/env python3
"""Verify that the capture is reproducible: two runs must be byte identical.

Runs ``capture_victory.py`` twice into two directories and compares every
produced file byte for byte (the PNG frames, the per-frame memory dumps and
the receipt's manifest).

Usage::

    python tools/s49_victory_capture/verify_capture.py --out build/s49-victory-capture/verify
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import s49_state  # noqa: E402

CAPTURE = HERE / "capture_victory.py"


def run(out_dir: pathlib.Path, extra: list[str]) -> int:
    command = [sys.executable, str(CAPTURE), "--out", str(out_dir)] + extra
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode not in (0, 1):
        print(completed.stdout[-2000:])
        print(completed.stderr[-2000:], file=sys.stderr)
        raise SystemExit(f"capture failed with {completed.returncode}")
    return completed.returncode


def compare(first: pathlib.Path, second: pathlib.Path) -> dict:
    """Compare two capture directories byte for byte.

    ``runtime.json`` holds the wall-clock duration of the run, so it is
    reported separately instead of being counted as a difference.
    """
    ignored = {"runtime.json"}
    left = {str(path.relative_to(first)).replace("\\", "/"): path
            for path in first.rglob("*") if path.is_file()}
    right = {str(path.relative_to(second)).replace("\\", "/"): path
             for path in second.rglob("*") if path.is_file()}
    only_left = sorted(set(left) - set(right) - ignored)
    only_right = sorted(set(right) - set(left) - ignored)
    differing = []
    for name in sorted((set(left) & set(right)) - ignored):
        if s49_state.file_sha256(left[name]) != s49_state.file_sha256(right[name]):
            differing.append(name)
    return {
        "files_first": len(left),
        "files_second": len(right),
        "ignored": sorted(ignored),
        "only_first": only_left[:20],
        "only_second": only_right[:20],
        "differing": differing[:20],
        "differing_count": len(differing),
        "identical": not only_left and not only_right and not differing,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--keep", action="store_true",
                        help="keep the two capture directories")
    parser.add_argument("--capture-arg", action="append", default=[],
                        help="argument forwarded to capture_victory.py "
                             "(repeatable)")
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    first = out_dir / "run-a"
    second = out_dir / "run-b"
    for path in (first, second):
        if path.exists():
            shutil.rmtree(path)

    run(first, args.capture_arg)
    run(second, args.capture_arg)
    result = compare(first, second)
    result["first"] = str(first)
    result["second"] = str(second)
    (out_dir / "verify.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not args.keep:
        shutil.rmtree(first)
        shutil.rmtree(second)
    return 0 if result["identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
