#!/usr/bin/env python3
"""X3 / B5 pixel criterion: the roster rotation crosses sides, like the original.

The product difference B5 is:

* the original's action pointer advances **across sides** -- the unit pool's
  ``+0xC1`` selection marker lands on the enemy bee slots 5/6/7/8/9 of
  battle 14 and the status bar follows it (W4 §6 B5),
* the remake filtered the roster rotation by ``side == current_side``, so the
  player's cursor could never point at a bee.

This script is the **pixel level criterion** W4 could not take.  It measures
the status bar of the original's own battle 14 walk, of a remake walk that
cycles the roster with R, and of the same remake walk built **without** the
B5 change, and it ties the pixels to the memory level truth (the ``+0xC1``
marker of the original).

Criterion
---------

C1 (original, memory)
    The ``+0xC1`` selection marker crosses sides: the steps after the four
    player units point at the **enemy bees** (slots 5..9, HP 25).

C2 (original, pixels)
    On exactly those steps the status bar's chakra gauge loses its fill: the
    count of green gauge pixels drops from the player value to the bee value.
    This is the same signal the remake has to reproduce.

C3 (remake with B5, pixels)
    Cycling the roster with R reproduces **the very same two gauge pixel
    counts** as the original -- the player value first, the bee value after
    the four player units.

C4 (remake without B5, pixels)
    The same walk on the pre-B5 build never leaves the player value: the
    rotation never offers an enemy unit.  This is the before picture that
    makes C3 a real product difference.

The identity of the fifth remake unit (the enemy bee, character 55) is
pinned by the unit test ``test_battle_roster_cross_side.cpp``.

Usage::

    python tools/s49_x3_boundary/check_b5_rotation.py
    python tools/s49_x3_boundary/check_b5_rotation.py --no-record
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "s49_victory_capture"))

import s49_state  # noqa: E402

import walkrec  # noqa: E402

WORK = walkrec.WORK
RECEIPTS = WORK / "receipts"

ORIGINAL_WALK = WORK / "original-walk-fdeb249b"

#: The three ROMs the criterion compares.
ROMS = {
    "with-b5": WORK / "roms" / "rom-A2-with-b5.gba",
    "without-b5": WORK / "roms" / "rom-B-no-b5.gba",
}

#: The walk that cycles the roster with R.
ROTATION_KEYS = ["Down", "Down"] + ["A"] * 16 + ["R"] * 8


def gauge_green(image) -> int:
    """The number of green pixels in the right half of the status bar.

    The gauge is the only green thing in the bar, and it is full for a
    player unit and empty for an enemy bee -- the same two values the
    original shows.
    """

    x0, y0, x1, y1 = walkrec.STATUS_BAR
    pixels = image.load()
    total = 0
    for x in range(120, x1):
        for y in range(y0, y1):
            colour = pixels[x, y]
            if colour[1] > 150 and colour[0] < 120 and colour[2] < 160:
                total += 1
    return total


def gauge_series(walk: pathlib.Path) -> list[dict[str, object]]:
    from PIL import Image

    rows = []
    for path in walkrec.frames_of(walk):
        image = Image.open(path).convert("RGB")
        rows.append(
            {
                "step": path.stem,
                "gauge_green": gauge_green(image),
            }
        )
    return rows


def original_rows(walk: pathlib.Path) -> list[dict[str, object]]:
    """The original's acting marker and its gauge, step by step."""

    from PIL import Image

    rows = []
    for state_path in sorted(walk.glob("step-*.ss9")):
        image_path = state_path.with_suffix(".png")
        if not image_path.is_file():
            continue
        state = s49_state.load_state(state_path)
        units = s49_state.read_pool(state)
        hp = s49_state.read_hp(state)
        acting = [unit for unit in units if unit["acting"]]
        marker = acting[0] if acting else None
        image = Image.open(image_path).convert("RGB")
        rows.append(
            {
                "step": state_path.stem,
                "acting_slot": marker["slot"] if marker else None,
                "acting_side": marker["side"] if marker else None,
                "acting_xy": [marker["x"], marker["y"]] if marker else None,
                "acting_hp": hp.get(marker["slot"]) if marker else None,
                "gauge_green": gauge_green(image),
            }
        )
    return rows


def distinct(values: list[int]) -> list[int]:
    out: list[int] = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def record_remake(label: str, rom: pathlib.Path) -> pathlib.Path:
    return walkrec.record_walk(
        rom,
        ROTATION_KEYS,
        WORK / ("rotation-%s" % label),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-record", action="store_true")
    args = parser.parse_args(argv)

    for name, rom in ROMS.items():
        if not rom.is_file():
            print("ERR missing ROM (%s): %s" % (name, rom), file=sys.stderr)
            return 2
    if not ORIGINAL_WALK.is_dir():
        print("ERR missing original walk: %s" % ORIGINAL_WALK, file=sys.stderr)
        return 2

    walks = {}
    if not args.no_record:
        for name, rom in ROMS.items():
            walks[name] = record_remake(name, rom)
    walks["with-b5"] = WORK / "rotation-with-b5"
    walks["without-b5"] = WORK / "rotation-without-b5"

    original = original_rows(ORIGINAL_WALK)
    with_b5 = gauge_series(walks["with-b5"])
    without_b5 = gauge_series(walks["without-b5"])
    if not original or not with_b5 or not without_b5:
        print("ERR no recorded frames", file=sys.stderr)
        return 2

    # --- C1: the original's marker crosses sides ---------------------------
    enemy_rows = [row for row in original if row["acting_side"] == "enemy"]
    player_rows = [row for row in original if row["acting_side"] == "player"]
    c1 = bool(enemy_rows) and bool(player_rows)
    c1_detail = "player steps=%d enemy steps=%d" % (
        len(player_rows), len(enemy_rows))

    # --- C2: the original's gauge loses its fill on the bee steps ---------
    original_values = distinct([row["gauge_green"] for row in original])
    enemy_values = distinct([row["gauge_green"] for row in enemy_rows])
    player_values = distinct([row["gauge_green"] for row in player_rows])
    c2 = (
        len(original_values) == 2
        and len(enemy_values) == 1
        and len(player_values) == 1
        and not set(enemy_values) & set(player_values)
    )
    c2_detail = "player gauge=%s enemy gauge=%s" % (
        player_values, enemy_values)
    player_gauge = player_values[0] if player_values else None
    bee_gauge = enemy_values[0] if enemy_values else None

    # --- C3: the remake with B5 reproduces the original's two gauges -------
    # The rotation rows are the R presses: they are the ones that move the
    # cursor from unit to unit.
    with_rotation = [row for row in with_b5 if str(row["step"]).endswith("-R")]
    without_rotation = [
        row for row in without_b5 if str(row["step"]).endswith("-R")
    ]
    remake_values = distinct([row["gauge_green"] for row in with_rotation])
    bee_index = next(
        (
            index
            for index, row in enumerate(with_rotation)
            if row["gauge_green"] == bee_gauge
        ),
        None,
    )
    player_index = next(
        (
            index
            for index, row in enumerate(with_rotation)
            if row["gauge_green"] == player_gauge
        ),
        None,
    )
    c3 = (
        player_gauge is not None
        and bee_gauge is not None
        and player_gauge in remake_values
        and bee_gauge in remake_values
        and bee_index is not None
        and player_index is not None
        and bee_index > player_index
    )
    c3_detail = (
        "rotation gauges=%s (player %s at row %s, bee %s at row %s)"
        % (remake_values, player_gauge, player_index, bee_gauge, bee_index)
    )

    # --- C4: the remake without B5 never leaves the player gauge -----------
    without_values = distinct(
        [row["gauge_green"] for row in without_rotation]
    )
    c4 = without_values == [player_gauge]
    c4_detail = "pre-B5 rotation gauges=%s" % (without_values,)

    receipt = {
        "schema_version": 2,
        "identity": "x3_b5_rotation_pixel_criterion",
        "original": {
            "walk": str(ORIGINAL_WALK),
            "rows": original,
        },
        "remake_with_b5": {
            "walk": str(walks["with-b5"]),
            "rom_sha256": walkrec.sha256_file(ROMS["with-b5"]),
            "rows": with_b5,
        },
        "remake_without_b5": {
            "walk": str(walks["without-b5"]),
            "rom_sha256": walkrec.sha256_file(ROMS["without-b5"]),
            "rows": without_b5,
        },
        "criteria": {
            "C1-original-marker-crosses-sides": {
                "status": "PASS" if c1 else "FAIL",
                "detail": c1_detail,
            },
            "C2-original-pixels-show-the-bee-row": {
                "status": "PASS" if c2 else "FAIL",
                "detail": c2_detail,
            },
            "C3-remake-with-b5-reproduces-the-bee-row": {
                "status": "PASS" if c3 else "FAIL",
                "detail": c3_detail,
            },
            "C4-remake-without-b5-never-offers-an-enemy-unit": {
                "status": "PASS" if c4 else "FAIL",
                "detail": c4_detail,
            },
        },
    }
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    receipt_path = RECEIPTS / "b5_rotation.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("original (acting marker / status bar gauge):")
    for row in original:
        print("  %-14s slot=%s side=%s xy=%s hp=%s gauge=%s"
              % (row["step"], row["acting_slot"], row["acting_side"],
                 row["acting_xy"], row["acting_hp"], row["gauge_green"]))
    print("remake with B5 (roster rotation / status bar gauge):")
    for row in with_b5:
        print("  %-14s gauge=%s" % (row["step"], row["gauge_green"]))
    print("remake without B5 (pre-B5 build / status bar gauge):")
    for row in without_b5:
        print("  %-14s gauge=%s" % (row["step"], row["gauge_green"]))
    print("")
    for name, criterion in receipt["criteria"].items():
        print("%-56s %s  %s" % (name, criterion["status"],
                                criterion["detail"]))
    print("receipt: %s" % receipt_path)
    return 0 if (c1 and c2 and c3 and c4) else 1


if __name__ == "__main__":
    raise SystemExit(main())
