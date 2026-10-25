#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""All-vs-all field-area matching between the original and remake frame sets.

The acceptance report pairs each original frame with the arg-min remake frame
over a *single* step offset.  This tool instead asks, for every original
frame, which remake frame matches best in the field area (screen top 128 rows)
over *all* remake frames and *all* offsets.

That separates two hypotheses:
  * timing shift  -> the best remake frame index moves monotonically with the
    original frame index (a constant or slowly varying lag)
  * content diff  -> the best remake frame index is stable but the residual
    stays high

Usage:
    python tools/s49_w25h1/all_vs_all.py --original <dir> --remake <dir> [--json out.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

FIELD = (0, 0, 240, 128)


def load(directory: Path, stem: str) -> Image.Image:
    return Image.open(directory / f"{stem}.png").convert("RGB")


def field_px(img: Image.Image):
    x0, y0, x1, y1 = FIELD
    return img.crop((x0, y0, x1, y1)).tobytes()


def residual(a: bytes, b: bytes) -> int:
    n = 0
    for i in range(0, len(a), 3):
        if a[i : i + 3] != b[i : i + 3]:
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True)
    ap.add_argument("--remake", required=True)
    ap.add_argument("--json")
    ap.add_argument("--limit", type=int, default=14)
    args = ap.parse_args()

    o_dir = Path(args.original)
    r_dir = Path(args.remake)
    o_stems = sorted(p.stem for p in o_dir.glob("*.png"))
    r_stems = sorted(p.stem for p in r_dir.glob("*.png"))
    o_data = {s: field_px(load(o_dir, s)) for s in o_stems}
    r_data = {s: field_px(load(r_dir, s)) for s in r_stems}

    out = []
    print(f"# original frames: {len(o_stems)}, remake frames: {len(r_stems)}")
    for o_stem in o_stems:
        scores = sorted(
            ((residual(o_data[o_stem], r_data[r_stem]), r_stem) for r_stem in r_stems),
            key=lambda t: t[0],
        )
        best_px, best_stem = scores[0]
        print(f"{o_stem:>14}: best {best_stem:<14} {best_px:6d} px   "
              + "  ".join(f"{s}:{n}" for n, s in scores[1:5]))
        out.append(
            {
                "original": o_stem,
                "best_remake": best_stem,
                "best_px": best_px,
                "top5": [{"remake": s, "px": n} for n, s in scores[:5]],
            }
        )

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"# wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
