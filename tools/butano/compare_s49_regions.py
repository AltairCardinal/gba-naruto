#!/usr/bin/env python3
"""Compare two S49 step frames region by region, with the pairing stated as data.

Whole-screen same-index comparison was the wrong acceptance gate for this
pair: the original and the remake draw the battlefield from different
scenery, so every step pair differs by tens of thousands of pixels and the
ranking between step indices is noise.  Measured on the 24-A and
Down,Down,A*30 walks, the best and second-best remake candidates for an
original step are separated by 0-147 pixels out of 38,400, which cannot
support any claim.

Region comparison is the comparison that carries information here, because
the shared chrome (status bar, dialogue box, result panel, speaker label) was
reproduced from verified exports while the battlefield was re-drawn.  This
tool therefore takes the region table as explicit input and reports, per
region, the differing pixel count and bounding box.  It never searches for a
better alignment, never masks, and never reorders frames: the pairing is a
declared input so a claim can be cited and re-run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

from PIL import Image, ImageChops

# GBA screen is 240x160.  Regions are (x0, y0, x1, y1) with y1 exclusive.
DEFAULT_REGIONS: dict[str, tuple[int, int, int, int]] = {
    "full-screen": (0, 0, 240, 160),
    "dialogue-area": (0, 96, 240, 160),
    "status-bar": (0, 144, 240, 160),
    "portrait-area": (0, 0, 240, 96),
}

SCREEN_SIZE = (240, 160)


class RegionComparisonError(RuntimeError):
    """The two frames cannot be compared as declared."""


def _normalized(image: Image.Image) -> Image.Image:
    if image.size != SCREEN_SIZE:
        raise RegionComparisonError(
            f"expected a {SCREEN_SIZE[0]}x{SCREEN_SIZE[1]} GBA frame, got {image.size}")
    return image.convert("RGB")


def difference_mask(left: Image.Image, right: Image.Image) -> Image.Image:
    """Binary mask of differing pixels, with no tolerance and no masking.

    The per-channel maximum is used rather than a luminance conversion: a
    luminance round-trip silently drops a one-step difference in a single
    channel (red 10 vs 11 becomes 0), which would undercount instead of
    failing closed.
    """
    difference = ImageChops.difference(left, right)
    red, green, blue = difference.split()
    combined = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return combined.point(lambda value: 255 if value else 0, mode="L")


def compare_regions(
    left: Image.Image,
    right: Image.Image,
    regions: Mapping[str, tuple[int, int, int, int]] = None,
) -> dict[str, object]:
    left = _normalized(left)
    right = _normalized(right)
    regions = DEFAULT_REGIONS if regions is None else regions
    full_mask = difference_mask(left, right)
    report: dict[str, object] = {}
    for name, box in regions.items():
        x0, y0, x1, y1 = box
        if not (0 <= x0 < x1 <= SCREEN_SIZE[0] and 0 <= y0 < y1 <= SCREEN_SIZE[1]):
            raise RegionComparisonError(f"region {name!r} falls outside the screen: {box}")
        mask = full_mask.crop(box)
        bbox = mask.getbbox()
        # histogram()[255] is the count of differing pixels in this region.
        different = mask.histogram()[255]
        area = (x1 - x0) * (y1 - y0)
        report[name] = {
            "box": list(box),
            "area_pixels": area,
            "different_pixels": different,
            "difference_bbox": (
                [x0 + bbox[0], y0 + bbox[1], x0 + bbox[2], y0 + bbox[3]]
                if bbox is not None else None
            ),
        }
    return report


def compare_pair(
    left_path: Path,
    right_path: Path,
    regions: Mapping[str, tuple[int, int, int, int]] = None,
) -> dict[str, object]:
    left_path, right_path = Path(left_path), Path(right_path)
    for path in (left_path, right_path):
        if not path.is_file():
            raise RegionComparisonError(f"missing frame: {path}")
    with Image.open(left_path) as left_image, Image.open(right_path) as right_image:
        regions_report = compare_regions(left_image, right_image, regions)
    return {
        "schema": "konoha.s49-region-comparison.v1",
        "comparison": "declared-pair-no-alignment-search-no-mask",
        "original_frame": left_path.name,
        "remake_frame": right_path.name,
        "regions": regions_report,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--remake", type=Path, required=True)
    parser.add_argument("--regions", type=Path, default=None,
                        help="JSON file mapping region name to [x0,y0,x1,y1]")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def load_regions(path: Path | None) -> dict[str, tuple[int, int, int, int]] | None:
    if path is None:
        return None
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    regions = {}
    for name, box in raw.items():
        if not isinstance(box, list) or len(box) != 4:
            raise RegionComparisonError(f"region {name!r} must be [x0,y0,x1,y1]")
        regions[name] = tuple(int(value) for value in box)
    return regions


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = compare_pair(
            args.original, args.remake, load_regions(args.regions))
    except (RegionComparisonError, OSError, ValueError, KeyError) as error:
        print(f"compare_s49_regions: {error}")
        return 2
    with args.output.open("x") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({
        name: region["different_pixels"]
        for name, region in result["regions"].items()
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
