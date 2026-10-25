#!/usr/bin/env python3
"""Content anchors: match every original frame against EVERY remake frame.

The judgement bench charges a *constant* walk offset.  This tool prices the
full N x M similarity matrix so a segment-dependent offset (drift) can be seen
directly instead of being charged as "content difference".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402

FIELD = (0, 0, 240, 128)


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True)
    parser.add_argument("--remake", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()

    od = pathlib.Path(args.original)
    rd = pathlib.Path(args.remake)
    onames = sorted(n for n in os.listdir(od)
                    if n.startswith("step-") and n.endswith(".png"))
    rnames = sorted(n for n in os.listdir(rd)
                    if n.startswith("step-") and n.endswith(".png"))
    oimg = {n: load_rgb(od / n) for n in onames}
    rimg = {n: load_rgb(rd / n) for n in rnames}
    osha = {n: sha(od / n) for n in onames}
    rsha = {n: sha(rd / n) for n in rnames}

    matrix = []
    print(f"{'original':<16}" + "".join(f"{i:>7}" for i in range(len(rnames))))
    for oname in onames:
        row = []
        for rname in rnames:
            count, _ = diff_mask(oimg[oname], rimg[rname], FIELD)
            row.append(count)
        matrix.append(row)
        best = min(row)
        bi = row.index(best)
        print(f"{oname:<16}" + "".join(f"{c:>7}" for c in row)
              + f"   best={rnames[bi]} ({best})")

    print("\n=== content anchors (argmin over the whole remake walk) ===")
    anchors = []
    for i, oname in enumerate(onames):
        row = matrix[i]
        best = min(row)
        hits = [rnames[j] for j, c in enumerate(row) if c == best]
        anchors.append({"original": oname, "best_px": best, "remake_hits": hits,
                        "offset": rnames.index(hits[0]) - i if hits else None})
        print(f"  {oname:<16} -> {hits}  {best:>7} px  (offset {anchors[-1]['offset']})")

    print("\n=== exact sha256 matches across the two walks ===")
    rsha_index = {}
    for n in rnames:
        rsha_index.setdefault(rsha[n], []).append(n)
    for i, oname in enumerate(onames):
        for hit in rsha_index.get(osha[oname], []):
            print(f"  {oname:<16} == {hit:<16} (offset {rnames.index(hit) - i:+d})")

    if args.out:
        p = pathlib.Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"original": onames, "remake": rnames,
                       "matrix_field_px": matrix, "anchors": anchors},
                      handle, ensure_ascii=False, indent=1)
        print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
