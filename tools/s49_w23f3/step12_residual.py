#!/usr/bin/env python3
"""Wave 23 / F3 -- where do the 24,101 px of ``step-12-A`` come from?

The judgement bench's residual for the original's ``step-12-A`` is 24,101 px in
the 240x128 field area -- the single largest block left after wave 22.

This tool answers three questions, all on *already captured* frames (no
emulator, no new recording):

1.  Is the residual a **content** difference or a **one-beat misalignment**?
    (price the whole walk at every constant offset, then price each original
    frame against a sliding window of remake frames.)
2.  Which **presentation element** accounts for the differing pixels?
    The pixels are bucketed with C4's measured signatures (red arrow, the
    "SELECT detail" HUD, the mint move-range fill, the yellow cursor cell, the
    orange attack range, the lattice line, and everything else).
3.  Produce the **side-by-side per-beat boolean matrix** (original beat x
    remake beat) that the brief asks for.

Usage
-----
    python tools/s49_w23f3/step12_residual.py \
        --original build/s49-package-w22/work/s49-report/capture-original \
        --remake   build/s49-package-w22/work/s49-report/capture-remake \
        --out      build/w23-f3/step12-residual.json
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from collections import Counter, deque

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402

# --------------------------------------------------------------------------
# C4's measured signatures (tools/s49_w21c4/detect_presentation.py)
# --------------------------------------------------------------------------
RED_ARROW_RGB = (255, 0, 0)
RED_ARROW_MIN_PIXELS = 10

MOVE_MINT_RGB = frozenset({
    (123, 236, 190), (138, 252, 200), (97, 246, 190),
    (91, 226, 185), (112, 255, 200), (107, 221, 180),
})
ATTACK_ORANGE_RGB = frozenset({(255, 143, 30)})
CURSOR_YELLOW_RGB = frozenset({(255, 226, 30), (255, 241, 41)})
LATTICE_RGB = frozenset({(118, 159, 190), (97, 133, 154)})

HUD_BOX = (190, 10, 236, 26)

FIELD_AREA = (0, 0, 240, 128)
FULL_BOX = (0, 0, 240, 160)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def frame_names(directory: pathlib.Path) -> list[str]:
    return sorted(n for n in os.listdir(directory)
                  if n.startswith("step-") and n.endswith(".png"))


def red_clusters(image: Image.Image, minimum: int = RED_ARROW_MIN_PIXELS) -> list[dict]:
    width, height = image.size
    px = image.load()
    seen = set()
    out = []
    for y in range(height):
        for x in range(width):
            if px[x, y] != RED_ARROW_RGB or (x, y) in seen:
                continue
            queue = deque([(x, y)])
            seen.add((x, y))
            component = []
            while queue:
                cx, cy = queue.popleft()
                component.append((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if (0 <= nx < width and 0 <= ny < height
                            and (nx, ny) not in seen
                            and px[nx, ny] == RED_ARROW_RGB):
                        seen.add((nx, ny))
                        queue.append((nx, ny))
            if len(component) >= minimum:
                xs = [p[0] for p in component]
                ys = [p[1] for p in component]
                out.append({"pixels": len(component),
                            "bbox": [min(xs), min(ys), max(xs), max(ys)]})
    return sorted(out, key=lambda c: c["bbox"])


def features(image: Image.Image, hud_template: Image.Image | None = None) -> dict:
    width, height = image.size
    px = image.load()
    counts = Counter(image.getdata())

    mint = sum(n for c, n in counts.items() if c in MOVE_MINT_RGB)
    orange = sum(n for c, n in counts.items() if c in ATTACK_ORANGE_RGB)
    yellow = sum(n for c, n in counts.items() if c in CURSOR_YELLOW_RGB)
    lattice = sum(n for c, n in counts.items() if c in LATTICE_RGB)

    x0, y0, x1, y1 = HUD_BOX
    hud_bright = 0
    for y in range(y0, min(y1, height)):
        for x in range(x0, min(x1, width)):
            if sum(px[x, y]) > 600:
                hud_bright += 1

    hud_diff = None
    if hud_template is not None:
        tpx = hud_template.load()
        hud_diff = 0
        for y in range(y0, min(y1, height)):
            for x in range(x0, min(x1, width)):
                if px[x, y] != tpx[x, y]:
                    hud_diff += 1

    arrows = red_clusters(image)
    return {
        "red_arrow_px": sum(a["pixels"] for a in arrows),
        "red_arrow_clusters": arrows,
        "mint_cell_px": mint,
        "yellow_cell_px": yellow,
        "orange_cell_px": orange,
        "lattice_px": lattice,
        "overlay_px": mint + yellow + orange,
        "hud_bright_px": hud_bright,
        "hud_template_diff": hud_diff,
    }


def flags(row: dict) -> dict:
    return {
        "move_grid": row["mint_cell_px"] > 0,
        "cursor_cell": row["yellow_cell_px"] > 0,
        "attack_range": row["orange_cell_px"] > 0,
        "red_arrow": row["red_arrow_px"] > 0,
        "select_hud": (row["hud_template_diff"] == 0
                       if row["hud_template_diff"] is not None
                       else row["hud_bright_px"] > 0),
        "hud_any": row["hud_bright_px"] > 0,
    }


# --------------------------------------------------------------------------
# the residual decomposition
# --------------------------------------------------------------------------
CATEGORIES = ("red_arrow", "select_hud", "move_grid", "cursor_cell",
              "attack_range", "lattice", "hud_other", "other")


def category_masks(original: Image.Image, remake: Image.Image) -> dict:
    """Per-category pixel sets, computed on the *difference* between the two
    frames: a pixel belongs to a category when it differs AND it is part of
    that category's signature on at least one of the two sides."""
    width, height = original.size
    opx = original.load()
    rpx = remake.load()

    diff = Image.new("L", original.size, 0)
    dpix = diff.load()
    for y in range(height):
        for x in range(width):
            if opx[x, y] != rpx[x, y]:
                dpix[x, y] = 1

    def build(predicate) -> set:
        out = set()
        for y in range(height):
            for x in range(width):
                if not dpix[x, y]:
                    continue
                if predicate(opx[x, y]) or predicate(rpx[x, y]):
                    out.add((x, y))
        return out

    red = build(lambda c: c == RED_ARROW_RGB)
    mint = build(lambda c: c in MOVE_MINT_RGB)
    orange = build(lambda c: c in ATTACK_ORANGE_RGB)
    yellow = build(lambda c: c in CURSOR_YELLOW_RGB)
    lattice = build(lambda c: c in LATTICE_RGB)

    # the SELECT HUD lives in a fixed box; the pixels of the HUD's own glyph
    # colours are "bright" (sum > 600) inside the box
    x0, y0, x1, y1 = HUD_BOX
    hud = set()
    hud_other = set()
    for y in range(y0, min(y1, height)):
        for x in range(x0, min(x1, width)):
            if not dpix[x, y]:
                continue
            bright_o = sum(opx[x, y]) > 600
            bright_r = sum(rpx[x, y]) > 600
            if bright_o or bright_r:
                hud.add((x, y))
            else:
                hud_other.add((x, y))

    masks = {
        "red_arrow": red,
        "select_hud": hud,
        "move_grid": mint,
        "cursor_cell": yellow,
        "attack_range": orange,
        "lattice": lattice,
        "hud_other": hud_other,
    }
    # priority order: an arrow pixel wins over everything, HUD over hud_other
    masks["select_hud"] -= red
    masks["hud_other"] -= red | masks["select_hud"]
    masks["move_grid"] -= red | masks["select_hud"] | masks["hud_other"]
    masks["cursor_cell"] -= (red | masks["select_hud"] | masks["hud_other"]
                             | masks["move_grid"])
    masks["attack_range"] -= (red | masks["select_hud"] | masks["hud_other"]
                              | masks["move_grid"] | masks["cursor_cell"])
    masks["lattice"] -= (red | masks["select_hud"] | masks["hud_other"]
                         | masks["move_grid"] | masks["cursor_cell"]
                         | masks["attack_range"])
    used = set()
    for key in masks:
        masks[key] -= used
        used |= masks[key]

    diff_set = {(x, y) for y in range(height) for x in range(width)
                if dpix[x, y]}
    masks["other"] = diff_set - used
    return masks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--original", type=pathlib.Path,
                        default=pathlib.Path(
                            r"D:\Github\gba-naruto\build\s49-package-w22"
                            r"\work\s49-report\capture-original"))
    parser.add_argument("--remake", type=pathlib.Path,
                        default=pathlib.Path(
                            r"D:\Github\gba-naruto\build\s49-package-w22"
                            r"\work\s49-report\capture-remake"))
    parser.add_argument("--out", type=pathlib.Path,
                        default=pathlib.Path(
                            r"D:\Github\gba-naruto\build\w23-f3\step12-residual.json"))
    parser.add_argument("--target", default="step-12-A.png",
                        help="the original frame to decompose")
    args = parser.parse_args()

    original_names = frame_names(args.original)
    remake_names = frame_names(args.remake)
    original_images = {n: load_rgb(args.original / n) for n in original_names}
    remake_images = {n: load_rgb(args.remake / n) for n in remake_names}

    document = {
        "schema": "konoha.s49-w23f3-step12-residual.v1",
        "original_dir": str(args.original),
        "remake_dir": str(args.remake),
    }

    # ---- 1. price every constant offset ---------------------------------
    offset_totals = []
    for offset in range(0, 9):
        total = 0
        frames = 0
        for index, name in enumerate(original_names):
            j = index + offset
            if j >= len(remake_names):
                break
            count, _ = diff_mask(original_images[name],
                                 remake_images[remake_names[j]], FIELD_AREA)
            total += count
            frames += 1
        offset_totals.append({"offset": offset, "total_field_px": total,
                              "frames": frames})
    document["offset_totals"] = offset_totals
    best = min(offset_totals, key=lambda r: r["total_field_px"])
    document["best_offset"] = best["offset"]
    document["best_total"] = best["total_field_px"]
    print(f"offset totals: " + ", ".join(
        f"+{r['offset']}={r['total_field_px']}" for r in offset_totals))
    print(f"best offset +{best['offset']} -> {best['total_field_px']} px")

    # ---- 2. per original frame: argmin over a sliding window -------------
    window = []
    for index, name in enumerate(original_names):
        cells = []
        for offset in range(1, 9):
            j = index + offset
            if j >= len(remake_names):
                cells.append(None)
                continue
            count, _ = diff_mask(original_images[name],
                                 remake_images[remake_names[j]], FIELD_AREA)
            cells.append(count)
        usable = [(c, o) for c, o in zip(cells, range(1, 9)) if c is not None]
        argmin = min(usable)
        window.append({"original": name, "cells": cells,
                       "best_offset": argmin[1], "best_px": argmin[0],
                       "at_global_offset": cells[best["offset"] - 1]
                       if best["offset"] >= 1 else None})
    document["window_argmin"] = window

    # ---- 3. the per-frame table at the best offset ------------------------
    per_frame = []
    for index, name in enumerate(original_names):
        j = index + best["offset"]
        if j >= len(remake_names):
            continue
        field, _ = diff_mask(original_images[name],
                             remake_images[remake_names[j]], FIELD_AREA)
        full, _ = diff_mask(original_images[name],
                            remake_images[remake_names[j]], FULL_BOX)
        per_frame.append({"original": name, "remake": remake_names[j],
                          "field_px": field, "full_px": full})
    document["per_frame"] = per_frame

    # ---- 4. C4 features + flags for both sides --------------------------
    template_source = args.original / "step-23-A.png"
    hud_template = load_rgb(template_source) if template_source.is_file() else None
    original_feats = {}
    for name in original_names:
        row = features(original_images[name], hud_template)
        original_feats[name] = {**row, **flags(row)}
    remake_feats = {}
    for name in remake_names:
        row = features(remake_images[name], hud_template)
        remake_feats[name] = {**row, **flags(row)}
    document["original_features"] = original_feats
    document["remake_features"] = remake_feats

    # ---- 5. the side-by-side per-beat boolean matrix ----------------------
    matrix = []
    for index, name in enumerate(original_names):
        j = index + best["offset"]
        if j >= len(remake_names):
            continue
        rname = remake_names[j]
        o = original_feats[name]
        r = remake_feats[rname]
        matrix.append({
            "original": name, "remake": rname,
            "field_px": per_frame[index]["field_px"] if index < len(per_frame) else None,
            "original_flags": {k: o[k] for k in
                               ("move_grid", "cursor_cell", "attack_range",
                                "red_arrow", "select_hud", "hud_any")},
            "remake_flags": {k: r[k] for k in
                             ("move_grid", "cursor_cell", "attack_range",
                              "red_arrow", "select_hud", "hud_any")},
            "original_px": {k: o[k] for k in
                            ("red_arrow_px", "mint_cell_px", "yellow_cell_px",
                             "orange_cell_px", "lattice_px", "hud_bright_px")},
            "remake_px": {k: r[k] for k in
                          ("red_arrow_px", "mint_cell_px", "yellow_cell_px",
                           "orange_cell_px", "lattice_px", "hud_bright_px")},
        })
    document["beat_matrix"] = matrix

    # ---- 6. decompose the target frame ----------------------------------
    target_index = original_names.index(args.target)
    decomposition = []
    for offset in range(1, 9):
        j = target_index + offset
        if j >= len(remake_names):
            continue
        rname = remake_names[j]
        masks = category_masks(original_images[args.target], remake_images[rname])
        total = sum(len(v) for v in masks.values())
        field_total = 0
        x0, y0, x1, y1 = FIELD_AREA
        for key, pixels in masks.items():
            in_field = sum(1 for (x, y) in pixels
                           if x0 <= x < x1 and y0 <= y < y1)
            field_total += in_field
        decomposition.append({
            "offset": offset,
            "remake": rname,
            "field_px": per_frame[target_index]["field_px"]
            if offset == best["offset"] else None,
            "total_diff_px": total,
            "field_diff_px": field_total,
            "by_category_px": {key: len(pixels)
                               for key, pixels in masks.items()},
        })
    document["target_decomposition"] = decomposition

    # ---- 7. the masked (遮蔽) residual for the target at every offset ----
    masked = []
    for offset in range(1, 9):
        j = target_index + offset
        if j >= len(remake_names):
            continue
        rname = remake_names[j]
        masks = category_masks(original_images[args.target], remake_images[rname])
        x0, y0, x1, y1 = FIELD_AREA
        field_by_cat = {}
        for key, pixels in masks.items():
            field_by_cat[key] = sum(1 for (x, y) in pixels
                                    if x0 <= x < x1 and y0 <= y < y1)
        total_field = sum(field_by_cat.values())
        entry = {"offset": offset, "remake": rname,
                 "total_field_px": total_field,
                 "field_by_category_px": field_by_cat,
                 "residual_after_masking_out": {
                     key: total_field - value
                     for key, value in field_by_cat.items()},
                 "drop_px": {key: value
                             for key, value in field_by_cat.items()},
                 }
        masked.append(entry)
    document["target_masking"] = masked

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=1)
    print(f"wrote {args.out}")

    # ---- console summary -------------------------------------------------
    print(f"\n=== {args.target} decomposition (field area only) ===")
    for entry in masked:
        cats = "  ".join(f"{k}={v}" for k, v in entry["field_by_category_px"].items())
        print(f"  +{entry['offset']} {entry['remake']:<16} total={entry['total_field_px']:>6}   {cats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
