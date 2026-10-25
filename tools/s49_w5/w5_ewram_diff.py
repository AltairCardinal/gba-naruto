#!/usr/bin/env python3
"""W5 -- diff the emulated EWRAM between consecutive captured steps.

Why this tool exists
--------------------
The remake's ``battle_runtime_scene_telemetry`` is **not published during the
battle intro** (a full EWRAM scan of every captured remake step finds no
"KBTL" magic anywhere), so the phase telemetry cannot name the moment.  What
*is* available on both sides is the emulated memory itself: every captured
step saved a savestate, and the headless probe can dump EWRAM out of it.

So the question "what did the extra A press change?" is answered directly:
diff EWRAM between two consecutive captured steps and list the words that
moved.  The original's step 9 -> step 10 gap (the extra press) is compared
against the remake's step 13 -> step 14 gap (the same transition, one press
earlier) and against the original's step 8 -> step 9 gap (the press that
raised the title card).

Usage
-----
    python tools/s49_w5/w5_ewram_diff.py \
        --rom build/s49-package-u3-final/work/pinned-rom/measured.gba \
        --capture build/s49-package-u3-final/work/s49-report/capture-remake \
        --exe build/s49-wave18/w5/probe/mgba-probe.exe \
        --states step-12-A.ss9 step-13-A.ss9 step-14-A.ss9 \
        --out build/s49-wave18/w5/ewram-remake.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from s49_fidelity_report.probe import Probe  # noqa: E402

EWRAM_BASE = 0x02000000
EWRAM_SIZE = 0x00040000


def dump_ewram(probe: Probe) -> bytes:
    return probe.dump(EWRAM_BASE, EWRAM_SIZE)


def diff_words(left: bytes, right: bytes) -> list[tuple[int, int, int]]:
    """(address, old_word, new_word) for every 4-byte aligned word that moved."""
    count = len(left) // 4
    out = []
    for index in range(count):
        a = struct.unpack_from("<I", left, index * 4)[0]
        b = struct.unpack_from("<I", right, index * 4)[0]
        if a != b:
            out.append((EWRAM_BASE + index * 4, a, b))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", required=True)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--states", nargs="+", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--max-list", type=int, default=80)
    args = parser.parse_args()

    capture = pathlib.Path(args.capture)
    blobs = {}
    with Probe(pathlib.Path(args.rom), exe=pathlib.Path(args.exe)) as probe:
        for name in args.states:
            state = capture / name
            probe.command(f"load {state}")
            blobs[name] = dump_ewram(probe)
            print(f"dumped {name}: {len(blobs[name])} bytes")

    results = []
    for index in range(len(args.states) - 1):
        left_name = args.states[index]
        right_name = args.states[index + 1]
        changed = diff_words(blobs[left_name], blobs[right_name])
        print()
        print("=" * 72)
        print(f"{left_name}  ->  {right_name}: {len(changed)} words changed")
        print("=" * 72)
        for address, old, new in changed[:args.max_list]:
            print("  0x{:08X}  0x{:08X} -> 0x{:08X}".format(address, old, new))
        if len(changed) > args.max_list:
            print("  ... {} more".format(len(changed) - args.max_list))
        results.append({
            "from": left_name,
            "to": right_name,
            "changed_words": len(changed),
            "changes": [
                {"address": "0x{:08X}".format(address), "old": old, "new": new}
                for address, old, new in changed
            ],
        })

    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {"rom": args.rom, "capture": args.capture, "results": results},
                handle, ensure_ascii=False, indent=1,
            )
        print("\nwrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
