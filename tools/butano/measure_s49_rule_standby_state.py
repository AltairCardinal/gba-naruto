#!/usr/bin/env python3
"""Measure the original's status bar 結束 / 待機 criterion.

The original S49 status bar carries a two kanji state word next to the unit
name: red ``結束`` when the unit has already finished its action, blue
``待機`` when it is still waiting.  The criterion is the **unit's** state,
not the screen's phase: the original shows the blue ``待機`` on the unit
selection screen, where the acting unit has not acted yet, and the red
``結束`` on the enemy's turn, where the bee has just acted.

The inks are read straight out of the recorded frames, so the rule is a
measurement and not an interpretation:

* red ``結束`` ink: (231, 24, 0)
* blue ``待機`` ink: (115, 33, 255)

The remake side is measured on the *declared* frame pairs of the region
comparison receipts, so the pairing stays an input and the status bar is
recomputed from the pixels.

Usage::

    python3 tools/butano/measure_s49_rule_standby_state.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

#: The original walk and the remake walk the pairs are taken from.
ORIGINAL_WALK = "artifacts/s49-fidelity-20261019-v1/walk-original-a24"
REMAKE_WALK = "artifacts/s49-fidelity-20261019-v1/walk-remake-dd-a30-banner2"

#: The region table the comparisons use.  The status bar is the bottom band.
REGION_TABLE = "tools/butano/s49_regions.json"

#: The region comparison receipts that declare the original / remake frame
#: pairs.  Every pair is an input; nothing here searches for a better one.
PAIR_RECEIPTS = (
    "artifacts/s49-fidelity-20261019-v1/region-diff-banner2/field-unit-selection.json",
    "artifacts/s49-fidelity-20261019-v1/region-diff-banner2/command-menu.json",
    "artifacts/s49-fidelity-20261019-v1/region-diff-banner2/command-menu-row2.json",
)

#: The two state inks of the original's status bar.
END_INK = (231, 24, 0)
STANDBY_INK = (115, 33, 255)


class RuleEvidenceError(RuntimeError):
    """The original evidence is missing or cannot be measured."""


def _load_image(path: Path):
    from PIL import Image

    if not Path(path).is_file():
        raise RuleEvidenceError(f"missing evidence frame: {path}")
    image = Image.open(path).convert("RGB")
    if image.size != (240, 160):
        raise RuleEvidenceError(
            f"{path} is {image.size}, not a 240x160 GBA frame"
        )
    return image


def _status_box(root: Path) -> tuple[int, int, int, int]:
    path = root / REGION_TABLE
    if not path.is_file():
        raise RuleEvidenceError(f"missing the region table: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    box = payload.get("regions", {}).get("status-bar")
    if not box:
        raise RuleEvidenceError(f"{path} has no status-bar region")
    return tuple(int(value) for value in box)  # type: ignore[return-value]


def classify_status_bar(image, box) -> dict[str, int]:
    """Count the two state inks in the status bar band."""

    x0, y0, x1, y1 = box
    pixels = image.load()
    end = 0
    standby = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            colour = pixels[x, y]
            if colour == END_INK:
                end += 1
            elif colour == STANDBY_INK:
                standby += 1
    return {"end_ink_pixels": end, "standby_ink_pixels": standby}


def _difference_pixels(left, right, box) -> int:
    from PIL import ImageChops

    x0, y0, x1, y1 = box
    difference = ImageChops.difference(
        left.crop(box), right.crop(box)
    )
    bands = difference.split()
    peak = ImageChops.lighter(
        ImageChops.lighter(bands[0], bands[1]),
        bands[2],
    )
    return sum(
        count for value, count in enumerate(peak.histogram()) if value
    )


def measure_original(root: Path) -> dict[str, Any]:
    """Classify the state word of every recorded original frame."""

    box = _status_box(root)
    walk = root / ORIGINAL_WALK
    frames = {}
    for path in sorted(walk.glob("step-*-A.png")):
        frames[path.name] = classify_status_bar(_load_image(path), box)
    if not frames:
        raise RuleEvidenceError(
            f"the original walk {ORIGINAL_WALK} has no recorded frames"
        )
    return {
        "walk": ORIGINAL_WALK,
        "status_bar_box": list(box),
        "end_ink": list(END_INK),
        "standby_ink": list(STANDBY_INK),
        "frames": frames,
    }


def measure_pairs(root: Path) -> list[dict[str, Any]]:
    """Recompute the status bar of every declared original / remake pair."""

    box = _status_box(root)
    original_dir = root / ORIGINAL_WALK
    remake_dir = root / REMAKE_WALK
    pairs = []
    for relative in PAIR_RECEIPTS:
        path = root / relative
        if not path.is_file():
            raise RuleEvidenceError(
                f"missing the region comparison receipt: {path}"
            )
        receipt = json.loads(path.read_text(encoding="utf-8"))
        original_frame = receipt.get("original_frame")
        remake_frame = receipt.get("remake_frame")
        if not original_frame or not remake_frame:
            raise RuleEvidenceError(
                f"{path} does not declare an original / remake frame pair"
            )
        original_image = _load_image(original_dir / original_frame)
        remake_image = _load_image(remake_dir / remake_frame)
        pairs.append(
            {
                "receipt": relative,
                "baseline": receipt.get("baseline"),
                "original_frame": original_frame,
                "remake_frame": remake_frame,
                "status_bar_different_pixels": _difference_pixels(
                    original_image, remake_image, box
                ),
                "original_ink": classify_status_bar(original_image, box),
                "remake_ink": classify_status_bar(remake_image, box),
            }
        )
    return pairs


def measure(root: Path) -> dict[str, Any]:
    return {
        "schema": "konoha.s49-rule-standby-state.v1",
        "original": measure_original(root),
        "pairs": measure_pairs(root),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    try:
        payload = measure(Path(args.root).resolve())
    except RuleEvidenceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
