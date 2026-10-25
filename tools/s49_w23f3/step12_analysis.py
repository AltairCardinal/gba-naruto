#!/usr/bin/env python3
"""W23 / F3 -- final analysis bundle for the step-12-A residual.

Emits build/w23-f3/step12-analysis.json with
  * the two-sided per-beat boolean matrix (the brief's headline table),
  * the per-category 遮蔽 (mask-out) decomposition of the 24,101 px,
  * the region decomposition,
  * the red-arrow size census (for C4's R-C4-3 status),
and prints the same as markdown so the note can quote it verbatim.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402
from s49_w23f3.step12_residual import (  # noqa: E402
    CATEGORIES, category_masks, features, flags, frame_names,
)

FIELD = (0, 0, 240, 128)
REGIONS = [
    ("top-strip  y0-8", (0, 0, 240, 8)),
    ("forest     y8-48", (0, 8, 240, 48)),
    ("grass      y48-95", (0, 48, 240, 95)),
    ("gap        y95-98", (0, 95, 240, 98)),
    ("box-top    y98-128", (0, 98, 240, 128)),
    ("field      y0-128", (0, 0, 240, 128)),
]


def main() -> int:
    parser = argparse.ArgumentParser()
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
                            r"D:\Github\gba-naruto\build\w23-f3\step12-analysis.json"))
    args = parser.parse_args()

    onames = frame_names(args.original)
    rnames = frame_names(args.remake)
    oimg = {n: load_rgb(args.original / n) for n in onames}
    rimg = {n: load_rgb(args.remake / n) for n in rnames}
    template = load_rgb(args.original / "step-23-A.png")

    ofeat = {n: {**features(oimg[n], template), **flags(features(oimg[n], template))}
             for n in onames}
    rfeat = {n: {**features(rimg[n], template), **flags(features(rimg[n], template))}
             for n in rnames}

    document = {
        "schema": "konoha.s49-w23f3-step12-analysis.v1",
        "original_dir": str(args.original),
        "remake_dir": str(args.remake),
        "alignment": {"offset": 4, "note": "constant +4 for every original beat "
                                          "except step-12-A (see anchors)"},
    }

    # ---- 1. the two-sided boolean matrix --------------------------------
    rows = []
    for index, oname in enumerate(onames):
        rname = rnames[index + 4]
        field, _ = diff_mask(oimg[oname], rimg[rname], FIELD)
        o, r = ofeat[oname], rfeat[rname]
        rows.append({
            "original": oname, "remake": rname, "field_px": field,
            "original_flags": {k: o[k] for k in ("move_grid", "cursor_cell",
                                                "attack_range", "red_arrow",
                                                "select_hud", "hud_any")},
            "remake_flags": {k: r[k] for k in ("move_grid", "cursor_cell",
                                              "attack_range", "red_arrow",
                                              "select_hud", "hud_any")},
            "original_red_clusters": o["red_arrow_clusters"],
            "remake_red_clusters": r["red_arrow_clusters"],
            "original_px": {k: o[k] for k in ("red_arrow_px", "mint_cell_px",
                                             "yellow_cell_px", "orange_cell_px",
                                             "lattice_px", "hud_bright_px")},
            "remake_px": {k: r[k] for k in ("red_arrow_px", "mint_cell_px",
                                           "yellow_cell_px", "orange_cell_px",
                                           "lattice_px", "hud_bright_px")},
        })
    document["beat_matrix"] = rows

    # ---- 2. the 遮蔽 decomposition of the target frame -------------------
    target = "step-12-A.png"
    ti = onames.index(target)
    masks = category_masks(oimg[target], rimg[rnames[ti + 4]])
    x0, y0, x1, y1 = FIELD
    by_cat = {}
    for key in CATEGORIES:
        by_cat[key] = sum(1 for (x, y) in masks[key]
                          if x0 <= x < x1 and y0 <= y < y1)
    total = sum(by_cat.values())
    document["target_masking"] = {
        "original": target, "remake": rnames[ti + 4],
        "field_px": total,
        "by_category_px": by_cat,
        "residual_after_masking_out": {k: total - v for k, v in by_cat.items()},
    }

    # ---- 3. the region decomposition -------------------------------------
    region_rows = []
    for name, box in REGIONS:
        count, _ = diff_mask(oimg[target], rimg[rnames[ti + 4]], box)
        area = (box[2] - box[0]) * (box[3] - box[1])
        region_rows.append({"region": name, "box": list(box), "diff_px": count,
                            "area_px": area,
                            "pct": round(100 * count / area, 2)})
    document["target_regions"] = region_rows

    # ---- 4. controls -----------------------------------------------------
    controls = []
    for side_a, name_a, side_b, name_b, label in [
            ("o", "step-13-A.png", "r", "step-17-A.png",
             "orig-13 vs remake-17 (same UI, settled bg)"),
            ("o", "step-12-A.png", "o", "step-13-A.png",
             "orig-12 vs orig-13 (inside the original)"),
            ("r", "step-16-A.png", "r", "step-17-A.png",
             "remake-16 vs remake-17 (inside the remake)")]:
        image_a = oimg[name_a] if side_a == "o" else rimg[name_a]
        image_b = oimg[name_b] if side_b == "o" else rimg[name_b]
        field, _ = diff_mask(image_a, image_b, FIELD)
        sub = []
        for name, box in REGIONS:
            count, _ = diff_mask(image_a, image_b, box)
            sub.append({"region": name, "diff_px": count})
        controls.append({"label": label, "a": name_a, "b": name_b,
                         "field_px": field, "regions": sub})
    document["controls"] = controls

    # ---- 5. red arrow size census ----------------------------------------
    arrow_rows = []
    for index, oname in enumerate(onames):
        rname = rnames[index + 4]
        arrow_rows.append({
            "original": oname, "remake": rname,
            "original_clusters": ofeat[oname]["red_arrow_clusters"],
            "remake_clusters": rfeat[rname]["red_arrow_clusters"],
        })
    document["red_arrow_census"] = arrow_rows

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=1)
    print(f"wrote {args.out}\n")

    # ---- markdown ---------------------------------------------------------
    print("### two-sided per-beat boolean matrix\n")
    print("| original beat | remake beat | field px | grid O/R | arrow O/R | "
          "SELECT HUD O/R | cursor O/R | attack O/R | lattice O/R |")
    print("|---|---|---:|:--:|:--:|:--:|:--:|:--:|:--:|")
    for row in rows:
        o, r = row["original_flags"], row["remake_flags"]
        f = lambda x: "Y" if x else "-"
        ol = row["original_px"]["lattice_px"]
        rl = row["remake_px"]["lattice_px"]
        print(f"| `{row['original']}` | `{row['remake']}` | {row['field_px']} | "
              f"{f(o['move_grid'])}/{f(r['move_grid'])} | "
              f"{f(o['red_arrow'])}/{f(r['red_arrow'])} | "
              f"{f(o['select_hud'])}/{f(r['select_hud'])} | "
              f"{f(o['cursor_cell'])}/{f(r['cursor_cell'])} | "
              f"{f(o['attack_range'])}/{f(r['attack_range'])} | "
              f"{ol}/{rl} |")

    print("\n### step-12-A 的 24,101 px 分解（逐项遮蔽）\n")
    print("| 项 | px | 遮蔽后的残差 |")
    print("|---|---:|---:|")
    for key in CATEGORIES:
        value = by_cat[key]
        print(f"| {key} | {value} | {total - value} |")
    print(f"| **合计** | **{total}** | 0 |")

    print("\n### step-12-A 的分区分解\n")
    print("| 区 | box | 差 px | 面积 | 占比 |")
    print("|---|---|---:|---:|---:|")
    for row in region_rows:
        print(f"| {row['region']} | {row['box']} | {row['diff_px']} | "
              f"{row['area_px']} | {row['pct']} % |")

    print("\n### 对照组\n")
    for control in controls:
        print(f"- **{control['label']}** ⇒ field {control['field_px']} px")
        for sub in control["regions"]:
            print(f"    - {sub['region']}: {sub['diff_px']}")

    print("\n### 红箭头尺寸普查（原版 / 重制侧）\n")
    for row in arrow_rows:
        def fmt(clusters):
            if not clusters:
                return "—"
            return ", ".join(f"{c['pixels']}px@{tuple(c['bbox'])}" for c in clusters)
        print(f"- `{row['original']}`: {fmt(row['original_clusters'])}  |  "
              f"`{row['remake']}`: {fmt(row['remake_clusters'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
