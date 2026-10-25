#!/usr/bin/env python3
"""Verify the frame-exact battle replay is reproducible: two runs, byte identical.

The instrument under test is the black field capture of a replayed battle
(``blackfade_capture.py --key-log``), which is the deliverable that stands in
for the victory capture: the original battle cannot be won by the driver yet
(see the report), but the *frame exact replay* of the battle it does play is
deterministic and therefore verifiable.

The comparison口径 is stream K's ``verify_capture.compare``: every produced
file is compared byte for byte.

Usage::

    python tools/s49_blackfade/verify_replay.py \\
        --out build/s49-blackfade/verify-replay
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
VICTORY = REPO / "tools" / "s49_victory_capture"
for path in (str(HERE), str(VICTORY)):
    if path not in sys.path:
        sys.path.insert(0, path)

import verify_capture  # noqa: E402

CAPTURE = HERE / "blackfade_capture.py"
REPORT = HERE / "blackfade_report.py"
DEFAULT_KEY_LOG = REPO / "build" / "s49-victory-capture" / "v3run24" / "play.json"
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")


def capture(out_dir: pathlib.Path, key_log: pathlib.Path, state: pathlib.Path) -> None:
    command = [sys.executable, str(CAPTURE), "--out", str(out_dir),
               "--state", str(state), "--key-log", str(key_log), "--capture", "all"]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        print(completed.stdout[-1500:])
        print(completed.stderr[-1500:], file=sys.stderr)
        raise SystemExit(f"capture failed with {completed.returncode}")
    report = subprocess.run(
        [sys.executable, str(REPORT), "--frames", str(out_dir / "frames"),
         "--out", str(out_dir / "blackfade.json")],
        capture_output=True, text=True)
    if report.returncode != 0:
        print(report.stdout[-1500:])
        print(report.stderr[-1500:], file=sys.stderr)
        raise SystemExit(f"report failed with {report.returncode}")


def compare_receipts(first: pathlib.Path, second: pathlib.Path) -> dict:
    """Compare the two truth tables, ignoring the directory they live in.

    The receipt carries the path of the frame directory, which is different
    by construction (run-a vs run-b).  Everything else has to match.
    """
    left = json.loads((first / "blackfade.json").read_text(encoding="utf-8"))
    right = json.loads((second / "blackfade.json").read_text(encoding="utf-8"))
    left.pop("frames_dir", None)
    right.pop("frames_dir", None)
    return {
        "receipt_identical": left == right,
        "receipt_differs": [] if left == right else ["blackfade.json"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-blackfade" / "verify-replay")
    parser.add_argument("--key-log", type=pathlib.Path, default=DEFAULT_KEY_LOG)
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--reuse", action="store_true",
                        help="compare the two runs that are already on disk")
    args = parser.parse_args(argv)

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    first = out_dir / "run-a"
    second = out_dir / "run-b"
    if not args.reuse:
        for path in (first, second):
            if path.exists():
                shutil.rmtree(path)
        capture(first, args.key_log, args.state)
        capture(second, args.key_log, args.state)
    result = verify_capture.compare(first, second)
    result.update(compare_receipts(first, second))
    # the receipt carries the directory it was written for (run-a vs run-b),
    # so it is compared separately; everything else has to be byte identical
    payload_diff = [name for name in result["differing"]
                    if name != "blackfade.json"]
    result["frames_identical"] = (not result["only_first"]
                                  and not result["only_second"]
                                  and not payload_diff)
    result["path_only_differences"] = [name for name in result["differing"]
                                       if name == "blackfade.json"]
    result["identical"] = bool(result["frames_identical"]
                               and result["receipt_identical"])
    result["first"] = str(first)
    result["second"] = str(second)
    for name, directory in (("first", first), ("second", second)):
        table = directory / "blackfade.json"
        if table.is_file():
            document = json.loads(table.read_text(encoding="utf-8"))
            result[name + "_black_events"] = [
                {"first": event["first_frame"], "last": event["last_frame"],
                 "frames": event["total_frames"],
                 "sha256": event["first_black_sha256"]}
                for event in document["events"]]
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
