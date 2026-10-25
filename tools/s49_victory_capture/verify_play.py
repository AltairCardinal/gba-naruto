#!/usr/bin/env python3
"""Verify that the victory capture is reproducible: two runs, byte identical.

Runs ``play_battle_v2.py`` twice into two directories and compares every
produced file byte for byte (the victory / settlement PNG frames and the
receipt).  The comparison口径 is stream K's ``verify_capture.compare``.

Usage::

    python tools/s49_victory_capture/verify_play.py --out build/s49-victory-capture/verify-play
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import verify_capture  # noqa: E402

PLAY = HERE / "play_battle_v2.py"


def run(out_dir: pathlib.Path, extra: list[str]) -> int:
    command = [sys.executable, str(PLAY), "--out", str(out_dir)] + extra
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode not in (0, 1):
        print(completed.stdout[-2000:])
        print(completed.stderr[-2000:], file=sys.stderr)
        raise SystemExit(f"play failed with {completed.returncode}")
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--play-arg", action="append", default=[],
                        help="argument forwarded to play_battle_v2.py (repeatable)")
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    first = out_dir / "run-a"
    second = out_dir / "run-b"
    for path in (first, second):
        if path.exists():
            shutil.rmtree(path)

    run(first, args.play_arg)
    run(second, args.play_arg)
    result = verify_capture.compare(first, second)
    result["first"] = str(first)
    result["second"] = str(second)
    for name, directory in (("first", first), ("second", second)):
        receipt = directory / "play.json"
        if receipt.is_file():
            data = json.loads(receipt.read_text(encoding="utf-8"))
            result[name + "_stats"] = data.get("stats")
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
