#!/usr/bin/env python3
"""Measure the original's post-move facing and the remake's orientation.

In the original S49 the unit the mission asks the player to protect (木叶丸)
walks two cells east and is then drawn **facing east**.  The focus position
only steers where he goes; it does not decide where he looks.

The original side is measured from the recorded frames:

* the original's command menu frame draws 木叶丸 as the **dimmed** (greyscale)
  non-acting unit, and the dimmed palette is the one read out of the
  original's palette RAM;
* the leftmost column of that art gives his cell on screen, and with the
  camera and the grid formula the cell is scene column 10;
* the S49 deployment layout puts him at column 8, so he walked east;
* the art is **not** bilaterally symmetric, so the facing really is
  observable in the pixels.

The remake side is measured on the *declared* frame pairs of the region
comparison receipts.  The decisive number is the orientation test: the
original's unit region compared with the remake's has to be much closer than
the original's **mirrored** region compared with the remake's.  A remake
that faced the other way would fail that.

The grid formula and the origin model come from the reverse side note
``notes/character-runtime-unit-oam-bindings-20260730.md``.

Usage::

    python3 tools/butano/measure_s49_rule_ai_facing.py
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

#: The region table the comparisons use.
REGION_TABLE = "tools/butano/s49_regions.json"

#: The declared original / remake frame pairs.
PAIR_RECEIPTS = (
    "artifacts/s49-fidelity-20261019-v1/region-diff-banner2/command-menu.json",
    "artifacts/s49-fidelity-20261019-v1/region-diff-banner2/command-menu-row2.json",
)

#: The dimmed palette receipt, read out of the original's palette RAM.
DIMMED_RECEIPT = "artifacts/s49-original-gpu-20261020-v2/dimmed-palette-receipt.json"

#: The original's camera on the command menu frame.  Every frame of the
#: walk uses it except the move range preview screen.
CAMERA_HOFS = 240
CAMERA_VOFS = 24

#: The grid model of the reverse side: the sprite origin sits at
#: ``grid_x * 32 - BG0HOFS + 16`` and the art extends 16 pixels to the left
#: of the origin.
CELL_WIDTH = 32
ART_LEFT_OF_ORIGIN = 16

#: Where the S49 battle 14 variant 0 puts 木叶丸 before he moves.  The
#: reverse side has no per-unit layout table, so this comes from the
#: recorded S49 variant table in ``notes/s49-fidelity-handover-20261019.md``.
DEPLOYMENT_COLUMN = 8

#: The row of 木叶丸's cell after the move.  The vertical measurement of the
#: original's art is polluted by the selection bracket, so the row comes
#: from the recorded S49 measurement (docs/konoha-senki/01-battle-s49.md
#: 4.3.81: the original's 木叶丸 is on scene cell (10, 7)).
DESTINATION_ROW = 7

#: The focus position the S49 mission gives the AI unit.  It lies north east
#: of the destination, so "face the focus" and "face the movement direction"
#: disagree; that disagreement is what makes the facing observable.
FOCUS_POSITION = (12, 3)


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


def _region(root: Path, name: str) -> tuple[int, int, int, int]:
    path = root / REGION_TABLE
    if not path.is_file():
        raise RuleEvidenceError(f"missing the region table: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    box = payload.get("regions", {}).get(name)
    if not box:
        raise RuleEvidenceError(f"{path} has no {name} region")
    return tuple(int(value) for value in box)  # type: ignore[return-value]


def _dimmed_palette(root: Path) -> list[tuple[int, int, int]]:
    path = root / DIMMED_RECEIPT
    if not path.is_file():
        raise RuleEvidenceError(f"missing the dimmed palette receipt: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "konoha.s49-unit-dimmed-palette.v1":
        raise RuleEvidenceError(f"{path} is not the dimmed palette receipt")
    return [tuple(colour) for colour in payload["dimmed"]]


def _difference_pixels(left, right) -> int:
    from PIL import ImageChops

    difference = ImageChops.difference(left, right)
    bands = difference.split()
    peak = ImageChops.lighter(
        ImageChops.lighter(bands[0], bands[1]),
        bands[2],
    )
    return sum(
        count for value, count in enumerate(peak.histogram()) if value
    )


def _facing(dx: int, dy: int) -> str:
    """The dominant axis, the way the remake's ``facing_toward`` reads it."""

    if dx == 0 and dy == 0:
        return "none"
    if abs(dx) >= abs(dy):
        return "east" if dx > 0 else "west"
    return "north" if dy < 0 else "south"


def measure_original(root: Path) -> dict[str, Any]:
    """Measure the original's 木叶丸 cell and the facing's observability."""

    box = _region(root, "left-unit-sprite")
    dimmed = _dimmed_palette(root)
    frame = _load_image(
        root / ORIGINAL_WALK / "step-18-A.png"
    )
    pixels = frame.load()

    columns = [
        x
        for x in range(box[0], box[2])
        if any(pixels[x, y] in dimmed for y in range(box[1], box[3]))
    ]
    if not columns:
        raise RuleEvidenceError(
            "the original's command menu frame has no dimmed unit in the "
            "left unit region"
        )
    art_left = min(columns)
    origin_x = art_left + ART_LEFT_OF_ORIGIN
    column = (origin_x + CAMERA_HOFS - ART_LEFT_OF_ORIGIN) // CELL_WIDTH

    crop = frame.crop(box)
    from PIL import ImageOps

    mirrored = ImageOps.mirror(crop)

    return {
        "frame": f"{ORIGINAL_WALK}/step-18-A.png",
        "left_unit_region": list(box),
        "dimmed_receipt": DIMMED_RECEIPT,
        "art_left_column": art_left,
        "origin_x": origin_x,
        "camera": [CAMERA_HOFS, CAMERA_VOFS],
        "scene_column": column,
        "destination_row": DESTINATION_ROW,
        "focus_position": list(FOCUS_POSITION),
        "facing_the_focus_would_give": _facing(
            FOCUS_POSITION[0] - column,
            FOCUS_POSITION[1] - DESTINATION_ROW,
        ),
        "facing_the_movement_gives": _facing(
            column - DEPLOYMENT_COLUMN,
            0,
        ),
        "deployment_column": DEPLOYMENT_COLUMN,
        "walked_cells": column - DEPLOYMENT_COLUMN,
        "walked_direction": (
            "east"
            if column > DEPLOYMENT_COLUMN
            else "west"
            if column < DEPLOYMENT_COLUMN
            else "none"
        ),
        "art_is_mirror_asymmetric": _difference_pixels(crop, mirrored) > 0,
    }


def measure_pairs(root: Path) -> list[dict[str, Any]]:
    """Compare every declared pair directly and against the mirror."""

    box = _region(root, "left-unit-sprite")
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
        original_crop = _load_image(original_dir / original_frame).crop(box)
        remake_crop = _load_image(remake_dir / remake_frame).crop(box)
        from PIL import ImageOps

        pairs.append(
            {
                "receipt": relative,
                "baseline": receipt.get("baseline"),
                "original_frame": original_frame,
                "remake_frame": remake_frame,
                "direct_different_pixels": _difference_pixels(
                    original_crop, remake_crop
                ),
                "mirrored_different_pixels": _difference_pixels(
                    ImageOps.mirror(original_crop), remake_crop
                ),
            }
        )
    return pairs


def measure(root: Path) -> dict[str, Any]:
    return {
        "schema": "konoha.s49-rule-ai-facing.v1",
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
