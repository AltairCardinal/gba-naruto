#!/usr/bin/env python3
"""Y1 (wave 13): per-screen comparison of the remake's settlement chain
against the original ROM's settlement truth.

The original's truth lives in ``build/s49-victory-capture/w4/settlement-truth``
(W4, wave 8).  The remake's running frames are the pages the closed-loop
driver photographed.  For every **distinct screen** of the remake's
settlement chain this tool reports

* the original truth image it matches best,
* the original's sha256 and the remake's sha256 (file digest),
* the number of differing pixels and the bounding box of the difference.

The pixel rule is the project's rule: a pixel counts as different when any of
its three channels differs.

Usage::

    python tools/s49_battle_balance/y1_settlement_table.py \\
        --truth build/s49-victory-capture/w4/settlement-truth \\
        --remake build/y1/settlement-run1/shots \\
        --out build/y1/settlement-table.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

from PIL import Image, ImageChops


def load_rgb(path: pathlib.Path):
    with Image.open(path) as image:
        return image.convert("RGB")


def pixel_sha(image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


def file_sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diff(image_a, image_b):
    """Return (differing pixels, bbox) for two RGB images."""
    if image_a.size != image_b.size:
        return -1, None
    difference = ImageChops.difference(image_a, image_b)
    bands = difference.split()
    merged = ImageChops.lighter(
        ImageChops.lighter(bands[0], bands[1]), bands[2])
    box = merged.getbbox()
    if box is None:
        return 0, None
    mask = merged.point(lambda value: 255 if value else 0)
    count = mask.histogram()[255]
    return count, box


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth", type=pathlib.Path, required=True)
    parser.add_argument("--remake", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--pattern", default="page-*.png")
    args = parser.parse_args(argv)

    truth_files = sorted(args.truth.glob("*.png"))
    if not truth_files:
        raise SystemExit(f"ERR no truth images under {args.truth}")
    truth = []
    for path in truth_files:
        image = load_rgb(path)
        truth.append({"name": path.name, "sha256": file_sha(path),
                      "pixel_sha256": pixel_sha(image), "image": image})

    remake_files = sorted(args.remake.glob(args.pattern))
    if not remake_files:
        raise SystemExit(f"ERR no remake frames under {args.remake}")

    # The PNG writer is deterministic, so identical pixels give identical
    # bytes: the file digest groups the screens without decoding every PNG.
    runs = []
    previous = None
    start = 0
    for index, path in enumerate(remake_files, 1):
        digest = file_sha(path)
        if digest != previous:
            if previous is not None:
                runs.append((start, index - 1, previous))
            previous = digest
            start = index
    runs.append((start, len(remake_files), previous))

    rows = []
    for first, last, digest in runs:
        path = remake_files[first - 1]
        image = load_rgb(path)
        best = None
        for entry in truth:
            count, box = diff(image, entry["image"])
            if best is None or count < best["differing_pixels"]:
                best = {"original": entry["name"],
                        "original_sha256": entry["sha256"],
                        "original_pixel_sha256": entry["pixel_sha256"],
                        "differing_pixels": count,
                        "diff_bbox": list(box) if box else None}
        rows.append({
            "remake_first_page": first - 1,
            "remake_last_page": last - 1,
            "remake_pages": last - first + 1,
            "remake_file": path.name,
            "remake_sha256": file_sha(path),
            "remake_pixel_sha256": pixel_sha(image),
            **best,
        })

    document = {
        "schema": "konoha.s49-y1-settlement-table.v1",
        "truth_dir": str(args.truth),
        "remake_dir": str(args.remake),
        "truth": [{"name": entry["name"], "sha256": entry["sha256"],
                   "pixel_sha256": entry["pixel_sha256"]} for entry in truth],
        "remake_screens": rows,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=1, ensure_ascii=False)
                            + "\n", encoding="utf-8", newline="\n")

    print("| remake pages | remake sha256 (head) | best original | "
          "original sha256 (head) | diff px | diff bbox |")
    print("|---|---|---|---|---:|---|")
    for row in rows:
        print(f"| {row['remake_first_page']}-{row['remake_last_page']} "
              f"({row['remake_pages']}) | `{row['remake_sha256'][:16]}` | "
              f"{row['original']} | `{row['original_sha256'][:16]}` | "
              f"{row['differing_pixels']} | {row['diff_bbox']} |")
    print(f"truth images={len(truth)} remake screens={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
