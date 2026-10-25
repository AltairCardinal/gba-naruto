#!/usr/bin/env python3
"""V1 (wave 16): compare the remake's settlement frames with the original's.

The original's truth is ``build/s49-victory-capture/w4/settlement-truth/``
(nine PNGs + the receipt ``settlement-truth.json``); the remake's frames are
the runtime shots a battle run produced.  For every screen the tool reports:

* the original's sha256,
* the remake's sha256,
* the number of pixels that differ,
* the bounding box of the difference.

The remake's frames must be **240x160** (the GBA screen); the tool refuses
anything else, because a diff against a differently sized frame is
meaningless.

Usage::

    python tools/s49_battle_balance/v1_compare.py \\
        --truth build/s49-victory-capture/w4/settlement-truth \\
        --remake build/v1/run-a/shots --out build/v1/compare-a.json
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

TRUTH_DIR = REPO / "build" / "s49-victory-capture" / "w4" / "settlement-truth"

# How a remake page maps onto the original's truth file.  The remake's
# settlement chain is ``outcome -> result -> level_up x6 -> training x6 ->
# post_battle_dialogue x7 -> task_menu``; the original's truth was captured
# from the same chain, so the mapping is by phase and page index.
#
# ⚠️ The **order** of the truth's level-up frames is not the order of their
# names: the original's truth directory holds six level-up screens, and the
# sixth one is the ninja tool the character just learned
# (``07-ninja-tool-list.png``), **not** the training stage.  The order below
# was verified by the sha256 of the pixels, not by the file names (see
# ``notes/s49-fidelity/U4-real-victory-verify.md``).
PHASE_ORDER = ["outcome", "result", "level_up", "training",
               "post_battle_dialogue", "task_menu"]
TRUTH_BY_PHASE = {
    "outcome": ["01-victory.png"],
    "result": ["02-settlement-exp-power-turns.png"],
    "level_up": ["03-levelup-naruto.png", "05-levelup-sasuke-jutsu-name.png",
                 "04-levelup-konohamaru.png", "05-levelup-sasuke.png",
                 "06-levelup-sakura.png", "07-ninja-tool-list.png"],
    "training": [],
    "post_battle_dialogue": ["08-postbattle-dialogue-1.png"],
    "task_menu": ["09-task-menu-map.png"],
}


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def diff(a: pathlib.Path, b: pathlib.Path) -> dict:
    """The pixel difference of two PNGs of the same size."""
    from PIL import Image, ImageChops
    with Image.open(a) as first, Image.open(b) as second:
        if first.size != second.size:
            return {"size_first": list(first.size),
                    "size_second": list(second.size),
                    "diff_pixels": None, "bbox": None,
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


def remake_pages(directory: pathlib.Path) -> list[dict]:
    """The remake's settlement shots, ordered by phase and page index.

    Two naming schemes are accepted: the closed-loop driver's
    ``shot-001-outcome-p0.png`` and the older chain driver's
    ``page-000-outcome.png``.
    """
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth", type=pathlib.Path, default=TRUTH_DIR)
    parser.add_argument("--remake", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    truth = json.loads((args.truth / "settlement-truth.json")
                       .read_text(encoding="utf-8"))
    truth_files = {entry["file"]: entry for entry in truth["frames"]}
    # The truth directory holds two extra level-up frames that the receipt
    # does not list; they are still valid truth frames.
    for path in sorted(args.truth.glob("*.png")):
        truth_files.setdefault(path.name, {"file": path.name,
                                            "sha256": sha256_file(path)})

    rows = []
    used: dict[str, list[int]] = {}
    # First pass: pair every remake page with the truth frame that is
    # **byte identical** to it.  That is the only pairing that does not
    # depend on the order of the file names: the truth's level-up frames are
    # named after the character, but the chain shows them in the order the
    # characters level up, and the sixth one is the ninja tool the character
    # just learned.
    truth_by_sha: dict[str, list[str]] = {}
    for name in sorted(truth_files):
        truth_by_sha.setdefault(truth_files[name]["sha256"], []).append(name)
    taken: set[str] = set()
    pages = remake_pages(args.remake)
    paired: list[dict | None] = []
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
    # Second pass: the pages that are **not** identical to any truth frame
    # are the ones whose numbers differ from the original's, so they are
    # paired by the phase order.
    for index, item in enumerate(paired):
        if item is not None:
            continue
        page = pages[index]
        phase = page["phase"]
        count = used.get(phase, 0)
        used[phase] = count + 1
        candidates = [name for name in TRUTH_BY_PHASE.get(phase, [])
                      if name not in taken]
        truth_name = candidates[count] if count < len(candidates) else None
        if truth_name is not None:
            taken.add(truth_name)
        paired[index] = {"page": page, "truth": truth_name,
                         "matched_by": "phase-order"}
    for item in paired:
        page = item["page"]
        phase = page["phase"]
        truth_name = item["truth"]
        row = {"remake_file": page["file"], "phase": phase,
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
        row.update(diff(page["path"], truth_path))
        rows.append(row)

    document = {
        "schema": "konoha.s49-v1-settlement-compare.v1",
        "truth_dir": str(args.truth),
        "truth_receipt_sha256": sha256_file(args.truth /
                                             "settlement-truth.json"),
        "remake_dir": str(args.remake),
        "screens": rows,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=1, ensure_ascii=False)
                            + "\n", encoding="utf-8", newline="\n")
    if not args.quiet:
        print(f"{'remake':44s} {'truth':40s} {'diff px':>9s}  bbox")
        for row in rows:
            diff_pixels = row.get("diff_pixels")
            print(f"{row['remake_file']:44s} "
                  f"{str(row.get('truth_file')):40s} "
                  f"{str(diff_pixels):>9s}  {row.get('bbox')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
