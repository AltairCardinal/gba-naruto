#!/usr/bin/env python3
"""Compare the remake's settlement chain against the original's truth frames.

Stream V4 (wave 9).  The original's settlement chain was recorded by stream
W4 (``build/s49-victory-capture/w4/settlement-truth/``); the remake's was
recorded by this stream (``v4_replay.py``).  This tool

1. groups the remake's frames into runs of pixel-identical screens,
2. matches every remake screen against every original truth image,
3. reports, for the best match, the two sha256 digests, the number of
   differing pixels and the bounding box of the difference.

The pixel rule is the project's rule: a pixel counts as different when any
of its three channels differs (``tools/compare_frame_dirs.py``).

Usage::

    python tools/s49_victory_capture/v4_settlement_compare.py \
        --truth build/s49-victory-capture/w4/settlement-truth \
        --remake build/s49-victory-capture/v4/remake-settlement/frames \
        --out build/s49-victory-capture/v4/settlement-compare.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib


def load_rgb(path: pathlib.Path):
    from PIL import Image
    with Image.open(path) as image:
        return image.convert("RGB")


def pixel_sha(image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


def file_sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diff(image_a, image_b):
    """Return (differing pixels, bbox) for two RGB images."""
    from PIL import ImageChops
    if image_a.size != image_b.size:
        return -1, None
    difference = ImageChops.difference(image_a, image_b)
    bands = difference.split()
    merged = ImageChops.lighter(
        ImageChops.lighter(bands[0], bands[1]), bands[2])
    box = merged.getbbox()
    count = 0
    if box is not None:
        data = merged.crop(box).tobytes()
        count = sum(1 for index in range(0, len(data), 3)
                    if data[index] or data[index + 1] or data[index + 2])
    return count, box


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth", type=pathlib.Path, required=True)
    parser.add_argument("--remake", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--min-run", type=int, default=8,
                        help="only report remake screens that last this long")
    args = parser.parse_args(argv)

    truth_files = sorted(args.truth.glob("*.png"))
    if not truth_files:
        raise SystemExit(f"ERR no truth images under {args.truth}")
    truth = []
    for path in truth_files:
        image = load_rgb(path)
        truth.append({"name": path.name, "path": str(path),
                      "sha256": file_sha(path),
                      "pixel_sha256": pixel_sha(image),
                      "image": image})

    remake_files = sorted(args.remake.glob("frame-*.png"))
    if not remake_files:
        raise SystemExit(f"ERR no remake frames under {args.remake}")

    runs = []
    previous = None
    start = 0
    for index, path in enumerate(remake_files, 1):
        digest = pixel_sha(load_rgb(path))
        if digest != previous:
            if previous is not None:
                runs.append((start, index - 1, previous))
            previous = digest
            start = index
    runs.append((start, len(remake_files), previous))

    rows = []
    for first, last, digest in runs:
        if last - first + 1 < args.min_run:
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
            "remake_first_frame": first,
            "remake_last_frame": last,
            "remake_frames": last - first + 1,
            "remake_frame": path.name,
            "remake_sha256": file_sha(path),
            "remake_pixel_sha256": digest,
            **best,
        })

    document = {
        "schema": "konoha.s49-settlement-compare.v1",
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

    print(f"{'remake frames':>14}  {'best original':<38} "
          f"{'diff px':>8}  bbox")
    for row in rows:
        print(f"{row['remake_first_frame']:6d}-{row['remake_last_frame']:<6d}  "
              f"{row['original']:<38} {row['differing_pixels']:8d}  "
              f"{row['diff_bbox']}")
    print(f"truth images={len(truth)} remake screens={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
