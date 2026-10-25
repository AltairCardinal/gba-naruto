#!/usr/bin/env python3
"""The ratchet gate on two report documents: "the residual may only shrink".

    python tools/s49_fidelity_report/ratchet_check.py <baseline.json> <candidate.json>

Exit code 0 when the candidate's residual is not worse than the baseline's,
1 when it is.  This is the same gate the judgment bench applies to a fresh
run (``s49_fidelity_report.py --ratchet <baseline>``); it is a separate entry
point so that the gate can be checked against two *stored* reports -- for
instance a deliberately worse one.

    python tools/s49_fidelity_report/regressed.py <baseline.json> \\
        --out <worse.json>
    python tools/s49_fidelity_report/ratchet_check.py <baseline.json> <worse.json>
    # -> exit 1: the residual got bigger
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from s49_fidelity_report import ratchet as ratchet_module  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("baseline", type=pathlib.Path)
    parser.add_argument("candidate", type=pathlib.Path)
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    result = ratchet_module.compare(baseline, candidate)

    for check in result["checks"]:
        direction = ("bigger is worse" if check["direction"] == "higher"
                     else "smaller is worse")
        print(f"  {'PASS' if check['ok'] else 'FAIL'}  {check['label']:<20} "
              f"baseline {check['baseline']} -> candidate {check['candidate']} "
              f"({direction})")
    frames = result["frames"]
    print(f"  per frame: {frames['compared']} compared, "
          f"{frames['worsened']} worse, {frames['improved']} better")
    status = result.get("status") or ("pass" if result["ok"] else "fail")
    print(f"RATCHET {status.upper()}")
    if status == "incomparable":
        # Not a pass: the two readings are not the same measurement.
        print("the baseline ROM differs from the candidate's ROM => the two "
              "residual numbers are not comparable => this is NOT a pass",
              file=sys.stderr)
        return 2
    if status == "fail":
        print("the residual got bigger -- this change must not be accepted",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
