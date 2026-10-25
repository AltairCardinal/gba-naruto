#!/usr/bin/env python3
"""W19-D: per-screen diff of a settlement chain against the original's truth.

Why this tool exists
--------------------
Wave 17..18 compared the settlement chain with ``tools/s49_battle_balance/
v1_compare.py``.  That tool pairs the remake's pages with the original's
frames **by sha256 first** (the only pairing that does not depend on file
names) and by phase order afterwards.  Wave 19's D stream has to produce the
same table **from a real battle** and has to **re-check** the level-up
screens independently, so this tool

* pairs the same way (sha256 first, phase order second) but **derives the
  phase order from the truth receipt's own file order** instead of a
  hard coded table, so a wrong hard coded order cannot hide a difference;
* reports the difference **per screen**: pixel count, bounding box, and a
  row-band breakdown, so a screen's residual can be attributed to a part of
  the picture (portraits / numbers / panel);
* splits the settlement screen's residual into the **portrait band** and the
  **number band**, which is what makes the "684 px of real battle result
  numbers" claim checkable instead of a number somebody wrote down;
* re-checks the level-up screens **independently**: every level-up page must
  be byte identical to a **distinct** original frame, and the pixel diff is
  computed here from the pixels, not copied from another tool.

Usage::

    python tools/s49_w19d/w19d_diff.py \\
        --remake build/w19-d/run-poked/shots \\
        --truth build/s49-victory-capture/w4/settlement-truth \\
        --out build/w19-d/compare-poked.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

DEFAULT_TRUTH = REPO / "build" / "s49-victory-capture" / "w4" / "settlement-truth"

# The settlement chain's phases, in the order the chain walks them.
PHASE_ORDER = ["outcome", "result", "level_up", "training",
               "post_battle_dialogue", "task_menu"]

# Which truth frames belong to which phase, **derived from the truth
# receipt's own file order** (the receipt lists the frames in the order the
# original showed them).  The truth directory holds two extra level-up
# frames that the receipt does not list; they are appended to the level-up
# slot so that the phase-order fallback can still reach them.
RECEIPT_PHASE_OF_FILE = {
    "01-victory.png": "outcome",
    "02-settlement-exp-power-turns.png": "result",
    "03-levelup-naruto.png": "level_up",
    "04-levelup-konohamaru.png": "level_up",
    "05-levelup-sasuke.png": "level_up",
    "06-levelup-sakura.png": "level_up",
    "07-ninja-tool-list.png": "level_up",
    "08-postbattle-dialogue-1.png": "post_battle_dialogue",
    "09-task-menu-map.png": "task_menu",
}

# The two truth frames the receipt does not list.  Their content is checked
# against the pixels, so their position in the level-up slot only matters
# for the phase-order fallback.
EXTRA_TRUTH_FILES = ["04-levelup-sasuke.png", "05-levelup-sasuke-jutsu-name.png"]

# The settlement screen's picture is split into two bands: the three
# character busts and the four number rows.  The band boundary is the
# original's own layout (the numbers start at row 104 of the 160 rows).
SETTLEMENT_PORTRAIT_BAND = (0, 104)
SETTLEMENT_NUMBER_BAND = (104, 160)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_pixels(path: pathlib.Path) -> list[list[tuple[int, int, int]]]:
    from PIL import Image
    with Image.open(path) as image:
        return [list(row) for row in image.convert("RGB").getdata()]


def diff_pixels(a: pathlib.Path, b: pathlib.Path) -> dict:
    """The pixel difference of two PNGs of the same size."""
    from PIL import Image, ImageChops
    with Image.open(a) as first, Image.open(b) as second:
        if first.size != second.size:
            return {"size_first": list(first.size),
                    "size_second": list(second.size),
                    "diff_pixels": None,
                    "bbox": None,
                    "note": "the frames have different sizes"}
        left = first.convert("RGB")
        right = second.convert("RGB")
        difference = ImageChops.difference(left, right)
        bbox = difference.getbbox()
        raw = difference.tobytes()
        pixels = 0
        for index in range(0, len(raw), 3):
            if raw[index] or raw[index + 1] or raw[index + 2]:
                pixels += 1
        return {"size": list(first.size),
                "diff_pixels": pixels,
                "bbox": list(bbox) if bbox is not None else None}


def row_bands(a: pathlib.Path, b: pathlib.Path, band: int = 8) -> list[dict]:
    """The difference counted per horizontal band of rows."""
    from PIL import Image
    with Image.open(a) as first, Image.open(b) as second:
        if first.size != second.size:
            return []
        left = first.convert("RGB").load()
        right = second.convert("RGB").load()
        width, height = first.size
        bands = []
        for top in range(0, height, band):
            count = 0
            for y in range(top, min(height, top + band)):
                for x in range(width):
                    if left[x, y] != right[x, y]:
                        count += 1
            if count:
                bands.append({"y0": top, "y1": min(height, top + band),
                              "diff_pixels": count})
        return bands


def settlement_band_split(a: pathlib.Path, b: pathlib.Path) -> dict:
    """Split the settlement screen's residual into portraits / numbers."""
    from PIL import Image
    with Image.open(a) as first, Image.open(b) as second:
        if first.size != second.size:
            return {}
        left = first.convert("RGB").load()
        right = second.convert("RGB").load()
        width, height = first.size
        portrait = 0
        numbers = 0
        boundary = SETTLEMENT_NUMBER_BAND[0]
        for y in range(height):
            in_numbers = y >= boundary
            for x in range(width):
                if left[x, y] != right[x, y]:
                    if in_numbers:
                        numbers += 1
                    else:
                        portrait += 1
        return {
            "portrait_band": list(SETTLEMENT_PORTRAIT_BAND),
            "portrait_diff_pixels": portrait,
            "number_band": list(SETTLEMENT_NUMBER_BAND),
            "number_diff_pixels": numbers,
        }


def remake_pages(directory: pathlib.Path) -> list[dict]:
    """The remake's settlement shots, ordered by phase and page index."""
    pages = []
    for path in sorted(directory.glob("*.png")):
        match = re.search(r"(outcome|result|level_up|training|"
                          r"post_battle_dialogue|task_menu)", path.name)
        if not match:
            continue
        pages.append({"file": path.name, "path": path,
                      "phase": match.group(1)})
    order = {name: index for index, name in enumerate(PHASE_ORDER)}
    pages.sort(key=lambda item: (order.get(item["phase"], 99), item["file"]))
    counters: dict[str, int] = {}
    for page in pages:
        index = counters.get(page["phase"], 0)
        page["page"] = index
        counters[page["phase"]] = index + 1
    return pages


def truth_index(truth_dir: pathlib.Path) -> tuple[dict, list[dict]]:
    """The truth frames, and the phase-ordered list used as the fallback."""
    receipt_path = truth_dir / "settlement-truth.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    files: dict[str, dict] = {}
    for entry in receipt["frames"]:
        files[entry["file"]] = dict(entry)
    for path in sorted(truth_dir.glob("*.png")):
        files.setdefault(path.name, {"file": path.name,
                                     "sha256": sha256_file(path)})
    by_phase: dict[str, list[str]] = {}
    for name in files:
        phase = RECEIPT_PHASE_OF_FILE.get(name)
        if phase is None:
            phase = "level_up" if name in EXTRA_TRUTH_FILES else None
        if phase:
            by_phase.setdefault(phase, []).append(name)
    # The receipt's own order first, then the extra frames.
    ordered: list[dict] = []
    for entry in receipt["frames"]:
        phase = RECEIPT_PHASE_OF_FILE.get(entry["file"], "level_up")
        ordered.append({"file": entry["file"], "phase": phase})
    for name in EXTRA_TRUTH_FILES:
        if name in files:
            ordered.append({"file": name, "phase": "level_up"})
    return files, ordered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth", type=pathlib.Path, default=DEFAULT_TRUTH)
    parser.add_argument("--remake", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--label", default="",
                        help="what this chain is (real battle / tool check)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    truth_files, truth_ordered = truth_index(args.truth)
    truth_by_sha: dict[str, list[str]] = {}
    for name in sorted(truth_files):
        truth_by_sha.setdefault(truth_files[name]["sha256"], []).append(name)

    pages = remake_pages(args.remake)
    taken: set[str] = set()
    paired: list[dict | None] = []
    # Pass one: byte identical pairing (the only name independent pairing).
    for page in pages:
        sha = sha256_file(page["path"])
        candidates = [name for name in truth_by_sha.get(sha, [])
                      if name not in taken]
        if candidates:
            taken.add(candidates[0])
            paired.append({"page": page, "truth": candidates[0],
                           "matched_by": "sha256"})
        else:
            paired.append(None)
    # Pass two: phase order for the pages that are **not** identical.
    counters: dict[str, int] = {}
    for index, item in enumerate(paired):
        if item is not None:
            continue
        phase = pages[index]["phase"]
        count = counters.get(phase, 0)
        counters[phase] = count + 1
        candidates = [entry["file"] for entry in truth_ordered
                      if entry["phase"] == phase and entry["file"] not in taken]
        truth_name = candidates[count] if count < len(candidates) else None
        if truth_name is not None:
            taken.add(truth_name)
        paired[index] = {"page": pages[index], "truth": truth_name,
                         "matched_by": "phase-order"}

    rows = []
    for item in paired:
        page = item["page"]
        truth_name = item["truth"]
        row = {"remake_file": page["file"], "phase": page["phase"],
               "page": page["page"], "truth_file": truth_name,
               "matched_by": item["matched_by"],
               "remake_sha256": sha256_file(page["path"])}
        if truth_name is None:
            row["note"] = "no original frame for this page"
            rows.append(row)
            continue
        truth_path = args.truth / truth_name
        row["truth_sha256"] = truth_files.get(truth_name, {}).get(
            "sha256", sha256_file(truth_path))
        row.update(diff_pixels(page["path"], truth_path))
        bands = row_bands(page["path"], truth_path)
        if bands:
            row["row_bands"] = bands
        if page["phase"] == "result":
            row["band_split"] = settlement_band_split(page["path"], truth_path)
        rows.append(row)

    # ---- independent re-check of the level-up screens --------------------
    level_rows = [row for row in rows if row["phase"] == "level_up"]
    matched_truth = [row["truth_file"] for row in level_rows
                     if row.get("matched_by") == "sha256"]
    level_check = {
        "level_up_pages": len(level_rows),
        "sha256_matched": sum(1 for row in level_rows
                               if row.get("matched_by") == "sha256"),
        "distinct_truth_frames": len(set(matched_truth)),
        "all_zero_pixels": all(row.get("diff_pixels") == 0
                               for row in level_rows),
        "per_page": [{"remake_file": row["remake_file"],
                      "truth_file": row["truth_file"],
                      "matched_by": row["matched_by"],
                      "diff_pixels": row.get("diff_pixels"),
                      "bbox": row.get("bbox")} for row in level_rows],
        "verdict": ("independent re-check: every level-up page is byte "
                    "identical to a distinct original frame"
                    if (level_rows
                        and all(row.get("matched_by") == "sha256"
                                for row in level_rows)
                        and len(set(matched_truth)) == len(level_rows)
                        and all(row.get("diff_pixels") == 0
                                for row in level_rows))
                    else "the level-up pages are NOT all byte identical"),
    }

    document = {
        "schema": "konoha.s49-w19d-settlement-diff.v1",
        "label": args.label,
        "truth_dir": str(args.truth),
        "truth_receipt_sha256": sha256_file(args.truth / "settlement-truth.json"),
        "remake_dir": str(args.remake),
        "pages": len(rows),
        "screens": rows,
        "level_up_recheck": level_check,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=1, ensure_ascii=False)
                            + "\n", encoding="utf-8", newline="\n")
    if not args.quiet:
        print(f"{'remake':44s} {'truth':40s} {'diff px':>9s}  bbox")
        for row in rows:
            print(f"{row['remake_file']:44s} "
                  f"{str(row.get('truth_file')):40s} "
                  f"{str(row.get('diff_pixels')):>9s}  {row.get('bbox')}")
        print()
        print("level-up re-check:", json.dumps(level_check["verdict"]))
        for row in level_check["per_page"]:
            print(f"  {row['remake_file']:44s} {str(row['truth_file']):40s} "
                  f"{str(row['diff_pixels']):>6s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
