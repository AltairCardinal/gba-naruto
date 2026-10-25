#!/usr/bin/env python3
"""X3 smoke gate: does the remake ROM survive a walk through the battle?

The walk is described by a key sequence only.  The gate answers one yes/no
question: *does the ROM reach the end of the walk without landing on the
Butano fatal error screen?*

Usage::

    python tools/s49_x3_boundary/check_rom_smoke.py --label romA \
        --keys Down,Down,A,A,A
    python tools/s49_x3_boundary/check_rom_smoke.py --label romA \
        --keys-file build/s49-x3-boundary/keys.txt
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import walkrec  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True,
                        help="the name of this run (the ROM file stem)")
    parser.add_argument("--keys", default="",
                        help="comma separated key sequence")
    parser.add_argument("--keys-file", default="",
                        help="a file with one key per line")
    parser.add_argument("--rom", default="",
                        help="the ROM to run (default: the built remake ROM)")
    parser.add_argument("--zero-input-frames", type=int, default=240)
    parser.add_argument("--settle-frames", type=int, default=90)
    parser.add_argument("--hold-frames", type=int, default=4)
    parser.add_argument("--out", default="",
                        help="the receipt file (default: the walk receipt)")
    args = parser.parse_args(argv)

    if args.keys_file:
        keys = [
            line.strip()
            for line in pathlib.Path(args.keys_file).read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]
    else:
        keys = [token.strip() for token in args.keys.split(",") if token.strip()]
    if not keys:
        print("ERR no key sequence", file=sys.stderr)
        return 2

    rom = pathlib.Path(args.rom) if args.rom else (
        walkrec.REMAKE_ROOT / "butano-sequel" / "butano-sequel.gba"
    )
    if not rom.is_file():
        print("ERR missing ROM: %s" % rom, file=sys.stderr)
        return 2

    walk = walkrec.WORK / ("smoke-%s" % args.label)
    walkrec.record_walk(
        rom,
        keys,
        walk,
        zero_input_frames=args.zero_input_frames,
        settle_frames=args.settle_frames,
        hold_frames=args.hold_frames,
    )

    frames = walkrec.frames_of(walk)
    crash = walkrec.crash_step(walk)
    receipt = {
        "schema_version": 1,
        "identity": "x3_rom_smoke",
        "label": args.label,
        "rom": str(rom),
        "rom_sha256": walkrec.sha256_file(rom),
        "keys": keys,
        "frames": len(frames),
        "last_frame": frames[-1].name if frames else None,
        "crash": crash,
    }
    out = pathlib.Path(args.out) if args.out else (
        walkrec.WORK / "receipts" / ("smoke-%s.json" % args.label)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("walk: %s" % walk)
    print("frames: %d, last: %s" % (len(frames), receipt["last_frame"]))
    if crash is None:
        print("RESULT: no error screen")
    else:
        print("RESULT: CRASH at %s" % crash["frame"])
    print("receipt: %s" % out)
    return 0 if crash is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
