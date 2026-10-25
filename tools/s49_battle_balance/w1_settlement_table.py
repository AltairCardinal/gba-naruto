#!/usr/bin/env python3
"""W1 (wave 11): per-screen comparison of the remake's settlement chain
against the original ROM's settlement truth.

The original's truth lives in ``build/s49-victory-capture/w4/settlement-truth``
(W4, wave 8).  The remake's running frames live in one of this stream's
recording directories.  For every **distinct screen** of the remake's
settlement chain this tool reports

* the original truth image it matches best,
* the original's sha256 and the remake's sha256 (file digest),
* the number of differing pixels and the bounding box of the difference.

The pixel rule is the project's rule: a pixel counts as different when any of
its three channels differs.

Usage::

    python tools/s49_battle_balance/w1_settlement_table.py \\
        --truth build/s49-victory-capture/w4/settlement-truth \\
        --remake build/s49-battle-balance/w1/runA/frames \\
        --out build/s49-battle-balance/w1/settlement-table.json
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
    """Return (differing pixels, bbox) for two RGB images.

    A pixel counts as different when **any** of its three channels differs
    (the project's rule).  ``tools/s49_victory_capture/v4_settlement_compare.py``
    implements the same rule but groups the difference bytes in threes, which
    both under-counts and can walk off the end of the buffer; this version
    counts pixels one by one.
    """
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
    parser.add_argument("--min-run", type=int, default=1,
                        help="only report remake screens that last this long")
    parser.add_argument("--first-frame", type=int, default=0,
                        help="ignore remake frames whose number is below this")
    args = parser.parse_args(argv)

    truth_files = sorted(args.truth.glob("*.png"))
    if not truth_files:
        raise SystemExit(f"ERR no truth images under {args.truth}")
    truth = []
    for path in truth_files:
        image = load_rgb(path)
        truth.append({"name": path.name, "sha256": file_sha(path),
                      "pixel_sha256": pixel_sha(image), "image": image})

    remake_files = sorted(args.remake.glob("frame-*.png"))
    if not remake_files:
        raise SystemExit(f"ERR no remake frames under {args.remake}")

    # The PNG writer is deterministic, so identical pixels give identical
    # bytes: the file digest groups the screens without decoding 100k PNGs.
    runs = []
    previous = None
    start = 0
    digests: dict[str, str] = {}
    for index, path in enumerate(remake_files, 1):
        digest = file_sha(path)
        if digest != previous:
            if previous is not None:
                runs.append((start, index - 1, previous))
            previous = digest
            start = index
        digests.setdefault(path.name, digest)
    runs.append((start, len(remake_files), previous))

    def frame_number(path: pathlib.Path) -> int:
        digits = "".join(character for character in path.stem if character.isdigit())
        return int(digits) if digits else 0

    rows = []
    for first, last, digest in runs:
        if last - first + 1 < args.min_run:
            continue
        if frame_number(remake_files[first - 1]) < args.first_frame:
            continue
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
            "remake_first_frame": frame_number(remake_files[first - 1]),
            "remake_last_frame": frame_number(remake_files[last - 1]),
            "remake_frames": last - first + 1,
            "remake_frame": path.name,
            "remake_sha256": file_sha(path),
            "remake_pixel_sha256": pixel_sha(image),
            **best,
        })

    document = {
        "schema": "konoha.s49-w1-settlement-table.v1",
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

    print(f"| remake frames | remake sha256 (head) | best original | "
          f"original sha256 (head) | diff px | diff bbox |")
    print("|---|---|---|---|---:|---|")
    for row in rows:
        print(f"| {row['remake_first_frame']}-{row['remake_last_frame']} "
              f"({row['remake_frames']}) | `{row['remake_sha256'][:16]}` | "
              f"{row['original']} | `{row['original_sha256'][:16]}` | "
              f"{row['differing_pixels']} | {row['diff_bbox']} |")
    print(f"truth images={len(truth)} remake screens={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
