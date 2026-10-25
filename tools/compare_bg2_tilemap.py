#!/usr/bin/env python3
"""Cell-level comparison of the second background layer.

The original's BG2 overlay has already been exported as a *cell-level* ground
truth: 1,024 cells, each with a family (blank / solid / edge / hatch /
line_alt / band), a palette bank and a tile index, for four moments of the
S49 battle.

The remake writes the same layer into its own BG2.  Comparing the two cell by
cell turns "these pixels differ" into "these N tilemap entries differ" --
which is directly actionable, and which a pixel diff can never tell you.

The remake's BG2 screen base is read from the measured register value
(BGCNT2 = 0x138A -> screen base block 0x13 -> VRAM 0x4C00, 32x32 cells), but
the tool also scans a range of candidate bases so it does not depend on that
measurement staying true.

Usage::

    python tools/compare_bg2_tilemap.py --dump-dir build/vram-dump --out build/vram-dump/compare.json
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

# Screen bases worth trying, in units of 0x400 (one screen block).
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


def load_frames(dump_dir: pathlib.Path) -> list[dict]:
    frames = []
    for vram_path in sorted(dump_dir.glob("frame-*.vram")):
        raw = vram_path.read_bytes()
        frames.append({"name": vram_path.stem, "vram": raw})
    return frames


def cells_at(vram: bytes, base: int, count: int = 1024) -> list[int]:
    if base + count * 2 > len(vram):
        return []
    return list(struct.unpack_from(f"<{count}H", vram, base))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dump-dir", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    truth = load_ground_truth()
    frames = load_frames(args.dump_dir)
    if not truth:
        print(f"ERR no ground truth under {GT}")
        return 2
    if not frames:
        print(f"ERR no VRAM dumps under {args.dump_dir}")
        return 2
    print(f"ground truth moments: {sorted(truth)}")
    print(f"dumped frames        : {len(frames)}")
    print()

    # Which candidate base makes the remake's tilemap look like the original's?
    # Score by how many cells are non-zero (the original's whole map is built
    # from overlay tiles, so a correct base is densely populated).
    best_base = None
    best_score = -1
    for base in CANDIDATE_BASES:
        score = 0
        for frame in frames:
            cells = cells_at(frame["vram"], base)
            score += sum(1 for c in cells if c != 0)
        if score > best_score:
            best_score = score
            best_base = base
    print(f"densest candidate screen base: 0x{best_base:04X} "
          f"(non-zero cells across all frames: {best_score})")
    print()

    results = {}
    for moment, cells in truth.items():
        want = [int(c.get("raw_hex"), 16) for c in cells]
        ranked = []
        for frame in frames:
            got = cells_at(frame["vram"], best_base)
            n = min(len(want), len(got))
            same = sum(1 for i in range(n) if want[i] == got[i])
            ranked.append((same, frame["name"], got))
        ranked.sort(key=lambda r: -r[0])
        same, name, got = ranked[0]
        n = min(len(want), len(got))
        results[moment] = {
            "best_frame": name,
            "matching_cells": same,
            "total_cells": n,
            "agreement_percent": round(100.0 * same / max(1, n), 2),
        }
        print(f"{moment:<20} best frame {name}  cells equal {same}/{n} "
              f"({results[moment]['agreement_percent']}%)")

    print()
    for moment, cells in truth.items():
        want = [int(c.get("raw_hex"), 16) for c in cells]
        ranked = []
        for frame in frames:
            got = cells_at(frame["vram"], best_base)
            n = min(len(want), len(got))
            ranked.append((sum(1 for i in range(n) if want[i] == got[i]), frame["name"], got))
        ranked.sort(key=lambda r: -r[0])
        _, name, got = ranked[0]
        n = min(len(want), len(got))
        diffs = [i for i in range(n) if want[i] != got[i]]
        print(f"=== {moment} (frame {name}) : {len(diffs)} / {n} cells differ ===")
        families = Counter()
        for i in diffs:
            families[(cells[i].get("family"), cells[i].get("tile"))] += 1
        for (family, tile), count in families.most_common(10):
            print(f"    {count:>5} x  original family={family!s:<10} tile={tile}")
        if diffs:
            print(f"    first differing cell indices: {diffs[:16]}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({"screen_base": best_base, "results": results},
                       ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        print("\nwrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
