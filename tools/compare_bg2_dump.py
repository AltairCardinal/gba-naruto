#!/usr/bin/env python3
"""Compare a per-frame dump of the remake's BG2 tilemap against the original's
exported ground truth, cell by cell.

The original's BG2 overlay has already been exported as a *cell-level* ground
truth: 1,024 cells, each with a family (blank / solid / edge / hatch /
line_alt / band), a palette bank and a tile index, for four moments of the
S49 battle.

The remake writes the same layer into its own BG2.  Comparing the two cell by
cell turns "these pixels differ" into "these N tilemap entries differ" --
which is directly actionable, and which a pixel diff can never tell you.

The remake's BG2 screen base is read from the measured register value
(BGCNT2 = 0x138A -> screen base block 0x13 -> VRAM 0x4C00, 32x32 cells), and
the tool also scans candidate bases so it does not depend on that measurement
staying true.

Usage::

    python tools/compare_bg2_dump.py --dump-dir build/bg2fd --prefix f14 \
        --out build/bg2fd/compare.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import struct
from collections import Counter

GT = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-movegrid-tilemap-v1"
)
MOMENTS = ("field-frame-v1", "movegrid-frame-v1", "grid16-frame-v1", "banner-frame-v1")
CANDIDATE_BASES = [0x4C00, 0x4800, 0x5000, 0x4400, 0x4000, 0x3800, 0x3000,
                   0x6000, 0x6400, 0x6800, 0x7000, 0x7800, 0x8000, 0x8400,
                   0x8800, 0x9000, 0x9800, 0xA000, 0xA800, 0xB000, 0xC000]


def load_ground_truth() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for moment in MOMENTS:
        path = GT / f"{moment}.bg2-tilemap.json"
        if path.is_file():
            out[moment] = json.loads(path.read_text(encoding="utf-8")).get("cells", [])
    return out


def cells_of(path: pathlib.Path, base: int, count: int = 1024) -> list[int]:
    """Read `count` tilemap cells out of a dump.

    A dump produced by the probe's `framedump` command starts at the address
    that was requested, so the map is at offset 0 of the file.  A base is only
    applied when the dump covers a larger region (a whole-VRAM dump).
    """
    raw = path.read_bytes()
    if base + count * 2 > len(raw):
        return []
    return list(struct.unpack_from(f"<{count}H", raw, base))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dump-dir", type=pathlib.Path, required=True)
    ap.add_argument("--prefix", required=True,
                    help="dump file prefix, e.g. f14 (files are f14-0000.bin ...)")
    ap.add_argument("--base", type=lambda v: int(v, 0), default=None,
                    help="VRAM offset of the BG2 map (default: scan candidates)")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    truth = load_ground_truth()
    dumps = sorted(args.dump_dir.glob(f"{args.prefix}-*.bin"))
    if not truth:
        print(f"ERR no ground truth under {GT}")
        return 2
    if not dumps:
        print(f"ERR no dumps matching {args.prefix}-*.bin under {args.dump_dir}")
        return 2
    print(f"ground truth moments: {sorted(truth)}")
    print(f"dumped frames        : {len(dumps)}")
    print()

    base = args.base
    if base is None:
        # A `framedump` file starts at the requested address, so the map is at
        # offset 0.  Fall back to scanning only when the dump is larger.
        base = 0
        for path in dumps:
            if path.stat().st_size > 2048:
                best_score = -1
                for candidate in CANDIDATE_BASES:
                    score = sum(1 for c in cells_of(path, candidate) if c)
                    if score > best_score:
                        best_score, base = score, candidate
                break
        print(f"screen base used: 0x{base:04X}")
        print()

    results = {}
    for moment, cells in truth.items():
        want = [int(c.get("raw_hex"), 16) for c in cells]
        ranked = []
        for path in dumps:
            got = cells_of(path, base)
            n = min(len(want), len(got))
            same = sum(1 for i in range(n) if want[i] == got[i])
            ranked.append((same, path.name, got))
        ranked.sort(key=lambda r: -r[0])
        same, name, got = ranked[0]
        n = min(len(want), len(got))
        results[moment] = {
            "best_dump": name,
            "matching_cells": same,
            "total_cells": n,
            "agreement_percent": round(100.0 * same / max(1, n), 2),
        }
        print(f"{moment:<20} best {name}  cells equal {same}/{n} "
              f"({results[moment]['agreement_percent']}%)")

    print()
    for moment, cells in truth.items():
        want = [int(c.get("raw_hex"), 16) for c in cells]
        ranked = []
        for path in dumps:
            got = cells_of(path, base)
            n = min(len(want), len(got))
            ranked.append((sum(1 for i in range(n) if want[i] == got[i]), path.name, got))
        ranked.sort(key=lambda r: -r[0])
        _, name, got = ranked[0]
        n = min(len(want), len(got))
        diffs = [i for i in range(n) if want[i] != got[i]]
        print(f"=== {moment} ({name}) : {len(diffs)} / {n} cells differ ===")
        if diffs:
            families = Counter()
            for i in diffs:
                families[(cells[i].get("family"), cells[i].get("tile"))] += 1
            for (family, tile), count in families.most_common(10):
                print(f"    {count:>5} x  original family={family!s:<10} tile={tile}"
                      f"  remake={got[diffs[0]]:#06x}")
            # what the remake actually put there
            got_kinds = Counter(got[i] for i in diffs)
            print("    remake values at the differing cells:",
                  ", ".join(f"{v:#06x}x{c}" for v, c in got_kinds.most_common(6)))
            print(f"    first differing cell indices: {diffs[:16]}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({"screen_base": base, "results": results},
                       ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        print("\nwrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
